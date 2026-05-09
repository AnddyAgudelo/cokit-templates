# F1 — Segmentation Explorer (design spec)

- **Project**: Campaign Approval Flow (CopilotKit + LangGraph + Zoho CRM)
- **Phase**: F1 of 5
- **Date**: 2026-05-09
- **Status**: Draft pending user review
- **Repo**: `/Users/anddyagudelo/Documents/Dev/Local/cokit-templates`

## TL;DR

Local-only Next.js + Python LangGraph app where a marketing user chats with an
AI agent that queries **read-only** against production Zoho CRM, generates
charts of customer segmentations on demand, and proactively proposes additional
metrics. F1 ships no template builder, no approval flow, no message sending —
those are F2–F5.

## Context: where F1 fits

The full system is decomposed into 5 phases, each independently shippable:

| # | Phase | Adds | Integrations |
|---|---|---|---|
| **F1** | **Segmentation Explorer** | **Chat-driven CRM exploration with charts** | **Zoho (read)** |
| F2 | Template Builder | Build WhatsApp templates (text + variables + image header), live preview | F1 + image storage |
| F3 | Approval Workflow | HITL Approve/Edit/Reject + audit log | F2 + auth + audit DB |
| F4 | Kapso Distribution | On approval → Kapso CLI → Meta WABA, send tracking | F3 + Kapso + Meta WABA |
| F5 | Production Hardening | Multi-user auth, observability, deploy, CI/CD | Infra |

This spec covers **only F1**. Each subsequent phase will get its own spec,
informed by F1's lessons.

## Goals (F1)

1. Enable a marketing user to explore Zoho customer data conversationally
   without writing queries or knowing Zoho's data model.
2. Render results as **charts** (pie, bar) or **metric cards** dynamically,
   inferred from query intent.
3. Have the agent **proactively propose** additional segments/metrics it found
   interesting in the data — not just answer.
4. Establish CopilotKit + LangGraph patterns reusable in F2–F5.

## Non-goals (F1)

- ❌ Writing to Zoho (read-only, no exceptions)
- ❌ Building WhatsApp templates (F2)
- ❌ Approval / HITL flows (F3)
- ❌ Sending messages or any contact with Kapso/Meta (F4)
- ❌ Multi-user auth (F5) — single-user local-only
- ❌ Deployment infrastructure (F5)
- ❌ Persisting conversations between sessions
- ❌ Custom Zoho field discovery UI (only via tool)

## Production safety rules (non-negotiable)

F1 reads production Zoho CRM with real customer PII. The following are
mandatory and enforced in code, not by convention:

| Concern | Mitigation |
|---|---|
| Accidental writes | OAuth scope limited to `ZohoCRM.modules.contacts.READ` (and equivalent for any other module used). No write tools exist. |
| Rate limiting | All Zoho calls go through `agent/src/zoho/client.py`. Client implements per-minute rate limiter (default 90 req/min, leaves headroom under typical 100 limit) and exponential backoff on 429. |
| PII in LLM context | Zoho query tools default to **aggregates** (counts, distributions). Individual records returned only when the user explicitly drills down. List-type tools cap at 50 records and never include emails/phones unless requested. |
| Audit trail | Every Zoho call writes a JSONL line to `./audit/zoho-audit-YYYY-MM-DD.jsonl` with `{ts, tool, params, fields_returned, record_count, latency_ms, status}`. |
| API outage | Tools surface explicit error messages. System prompt forbids the agent from inventing data. On `query_customers` failure, agent must say "I couldn't reach Zoho right now" — never fabricate counts. |
| Credential leakage | `.env` is `.gitignored`. `.env.example` documents required vars but contains no secrets. README explains how each marketer generates their own OAuth refresh token. |

## Architecture

### Deployment model

- **Local-only**. Each marketer clones the repo, populates `.env` with their
  own Zoho credentials, runs `npm install && npm run dev`.
- No shared backend, no shared DB, no shared cache.
- Zoho RBAC enforces what each user can see (their personal Zoho permissions).
- No multi-tenant concerns in F1.

### Stack

- **Frontend**: Next.js 16, React 19, Tailwind 4, CopilotKit `1.56.5`
  (`@copilotkit/react-core/v2`), Recharts (chart rendering).
- **Agent**: Python 3.12, LangGraph, `langchain-openai`, `copilotkit` middleware,
  `httpx` (Zoho client), `tenacity` (retry/backoff).
- **Model**: GPT-5.2-mini (cheap iteration; switchable via env var).
- **Agent server**: LangGraph dev server on **port 8124** (avoid clashing with
  any reference template on 8123).

### High-level data flow

```
Marketer types message in chat
        ↓
CopilotKit /api/copilotkit (Next.js)
        ↓ (HTTP)
LangGraph agent (port 8124)
        ↓
Agent decides: query_customers / get_field_distribution / list_custom_fields / render_chart
        ↓
zoho/client.py → Zoho API (rate-limited, audited, cached per session)
        ↓
Tool returns aggregates → Command(update={...})
        ↓
StateStreamingMiddleware streams partial state to frontend
        ↓
Frontend renders via useComponent (chart) or chat message
```

## Repository structure

```
cokit-templates/
├── docs/
│   └── specs/
│       └── 2026-05-09-f1-segmentation-explorer-design.md   ← this file
├── src/                                    # Next.js frontend
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                        # CopilotChat + chart canvas
│   │   ├── globals.css
│   │   └── api/copilotkit/[[...slug]]/route.ts
│   ├── features/
│   │   └── segmentation/
│   │       ├── components/
│   │       │   ├── chart-canvas.tsx        # container; reads agent state
│   │       │   ├── pie-chart.tsx           # Recharts wrapper
│   │       │   ├── bar-chart.tsx           # Recharts wrapper
│   │       │   └── metric-card.tsx         # single-number display
│   │       ├── schemas.ts                  # Zod schemas
│   │       └── types.ts                    # z.infer types
│   ├── hooks/
│   │   └── use-segmentation-charts.tsx     # registers useComponent renderers
│   ├── lib/
│   │   └── env.ts                          # Zod env validation
│   └── components/ui/                      # primitive UI (Button, Input)
├── agent/
│   ├── main.py                             # create_agent + middleware
│   ├── src/
│   │   ├── state.py                        # AgentState TypedDict
│   │   ├── system_prompt.py                # SYSTEM_PROMPT constant
│   │   ├── tools/
│   │   │   ├── __init__.py                 # exports tool list
│   │   │   ├── zoho_queries.py             # query_customers, get_field_distribution, list_custom_fields
│   │   │   └── chart_renderers.py          # render_chart
│   │   └── zoho/
│   │       ├── __init__.py
│   │       ├── client.py                   # httpx + OAuth refresh + rate limit
│   │       ├── audit.py                    # JSONL audit logger
│   │       └── cache.py                    # in-process session cache
│   ├── tests/
│   │   ├── test_zoho_client.py             # mocks Zoho via httpx_mock
│   │   ├── test_zoho_queries_tool.py       # tool behavior with mocked client
│   │   └── test_audit.py                   # audit writes JSONL correctly
│   ├── audit/                              # gitignored; runtime audit logs land here
│   │   └── .gitkeep
│   ├── langgraph.json
│   └── pyproject.toml
├── scripts/
│   ├── setup-agent.sh                      # uv venv + install
│   ├── setup-agent.bat
│   ├── run-agent.sh                        # langgraph dev --port 8124
│   └── run-agent.bat
├── .env.example
├── .gitignore                              # excludes .env, audit/, node_modules, .venv
├── package.json
├── postcss.config.mjs
├── next.config.ts
├── tsconfig.json
└── README.md                               # setup, Zoho OAuth instructions, limits
```

### Folder rationale

| Choice | Why |
|---|---|
| `src/features/segmentation/` not flat `components/` | Screaming architecture; F2 will add `src/features/templates/` independently. |
| `agent/src/zoho/` separate from `tools/` | Single responsibility: tools express intent (`query_customers`), client handles transport (auth, rate limit, audit). Tools can be tested without hitting Zoho. |
| No `domain/` layer in F1 | YAGNI — only one storage (Zoho), no swap target yet. The `zoho/client.py` boundary IS the abstraction. |
| `audit/` outside `src/` | Runtime artifacts, not code. Gitignored. |

## Data model

### `AgentState` (Python, `agent/src/state.py`)

```python
from langchain.agents import AgentState as BaseAgentState
from typing import TypedDict, Literal

ChartType = Literal["pie", "bar", "metric"]

class ChartSpec(TypedDict):
    id: str                      # uuid; lets the frontend keep stable keys
    type: ChartType
    title: str
    data: list[dict]             # [{label: str, value: number}, ...] for pie/bar
                                 # [{label: str, value: number}] of length 1 for metric
    x_label: str | None
    y_label: str | None
    source_query: str            # human-readable description: "Customers by city, premium tier"

class AgentState(BaseAgentState):
    charts: list[ChartSpec]      # rendered charts in this session, append-only
    last_segment_filter: dict | None  # last filters used; useful for "and broken down by city"
```

`charts` is append-only within a session. The frontend renders all of them
stacked. Marketer dismisses individual charts via UI (frontend-only state).

### Zod mirror (`src/features/segmentation/schemas.ts`)

```typescript
import { z } from "zod";

export const ChartTypeSchema = z.enum(["pie", "bar", "metric"]);

export const ChartSpecSchema = z.object({
  id: z.string().uuid(),
  type: ChartTypeSchema,
  title: z.string().min(1),
  data: z.array(z.object({
    label: z.string(),
    value: z.number(),
  })).min(1),
  x_label: z.string().nullable(),
  y_label: z.string().nullable(),
  source_query: z.string(),
});

export type ChartSpec = z.infer<typeof ChartSpecSchema>;
export type ChartType = z.infer<typeof ChartTypeSchema>;
```

Frontend validates each chart spec arriving from agent state via
`ChartSpecSchema.safeParse()` before rendering. Invalid specs are logged
and skipped (not crashed).

## Agent tools (F1)

### `query_customers(filters, limit=50)`

Returns customer records or aggregated count, depending on how it's called.

```python
@tool
def query_customers(
    filters: dict,           # {"tier": "premium", "city": "Bogota"}
    limit: int = 50,
    fields: list[str] | None = None,  # default: minimal — id, name only
    runtime: ToolRuntime = ...,
) -> dict:
    """
    Query Zoho contacts matching `filters`. By default returns only id+name
    (no PII). Pass `fields` to request more, but ONLY do this when the user
    explicitly drills down on individual records.

    Returns: {"count": int, "records": [...]}.
    """
```

**Constraints:**
- Always paginates internally; surface errors clearly if filter set is too large.
- `fields` defaults exclude email, phone, address. System prompt enforces
  drill-down norms.
- Rate-limited and audited via `zoho/client.py`.

### `get_field_distribution(field, filters=None)`

Returns aggregated distribution of `field` over the (filtered) customer set.

```python
@tool
def get_field_distribution(
    field: str,                  # "city", "tier", "subscription_status", ...
    filters: dict | None = None,
    runtime: ToolRuntime = ...,
) -> dict:
    """
    Group customers by `field` and return counts per bucket.
    Returns: {"field": str, "buckets": [{"label": str, "count": int}, ...], "total": int}.
    """
```

**Why a separate tool from `query_customers`:** distribution is the most common
analytical query and benefits from a structured response shape that maps
cleanly to chart data. Avoids the LLM hand-rolling aggregations.

### `list_custom_fields(module="Contacts")`

Returns the schema of available fields in a Zoho module. The agent calls this
**before** proposing segments to avoid hallucinating field names.

```python
@tool
def list_custom_fields(
    module: str = "Contacts",
    runtime: ToolRuntime = ...,
) -> list[dict]:
    """
    Returns: [{"api_name": str, "display_name": str, "type": str, "picklist_values": [...] | None}, ...]
    Cache: 1h TTL — schema rarely changes.
    """
```

### `render_chart(type, title, data, x_label=None, y_label=None, source_query)`

The only "frontend-touching" tool. Appends a `ChartSpec` to `state.charts`.

```python
@tool
def render_chart(
    type: ChartType,
    title: str,
    data: list[dict],
    source_query: str,
    x_label: str | None = None,
    y_label: str | None = None,
    runtime: ToolRuntime = ...,
) -> Command:
    """
    Render `data` as a `type` chart in the canvas. Call AFTER you have data
    from a query tool; never invent the data.

    `source_query`: human-readable description of what was queried, used in
    chart subtitle so the user knows what they're looking at.
    """
```

Returns `Command(update={"charts": [..., new_chart]})`.

### Why this split (data vs render)

In mi-cokit, `query_data` and chart rendering are two separate concepts (one
backend tool, one `useComponent` registration). F1 follows the same split:

- **Data tools** (`query_customers`, `get_field_distribution`, `list_custom_fields`)
  know about Zoho. They don't know about UI.
- **Render tool** (`render_chart`) knows about UI. It doesn't know about Zoho.

This keeps each tool testable in isolation and makes adding new render types
in F2+ trivial.

## Zoho client (`agent/src/zoho/client.py`)

```python
class ZohoClient:
    def __init__(self, config: ZohoConfig, *, audit: AuditLogger, cache: SessionCache):
        self._config = config
        self._http = httpx.Client(timeout=10.0)
        self._access_token = None
        self._token_expires_at = None
        self._audit = audit
        self._cache = cache
        self._rate_limiter = RateLimiter(per_minute=90)

    def get(self, path: str, params: dict | None = None, *, cache_key: str | None = None) -> dict:
        if cache_key and (cached := self._cache.get(cache_key)):
            return cached

        self._rate_limiter.acquire()
        self._refresh_token_if_needed()

        t0 = time.monotonic()
        try:
            resp = self._http.get(
                f"{self._config.api_domain}/crm/v6/{path}",
                headers={"Authorization": f"Zoho-oauthtoken {self._access_token}"},
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Backoff and retry once via tenacity
                ...
            self._audit.log_error(path, params, e)
            raise

        latency = (time.monotonic() - t0) * 1000
        self._audit.log_success(path, params, data, latency_ms=latency)

        if cache_key:
            self._cache.set(cache_key, data, ttl_seconds=300)
        return data
```

Key design points:

1. **Single chokepoint**: every Zoho HTTP call goes through `get()`. Easy to
   instrument, mock, swap.
2. **Constructor injection**: `audit` and `cache` are injected — tests pass
   fakes.
3. **OAuth refresh internal**: the agent never sees access tokens. Refresh
   token from env, access token cached in memory with 1-hour TTL.
4. **No write methods**: there is no `post()`, `put()`, or `delete()` on
   purpose. Adding write requires a code change reviewable in PR.

## Frontend

### `src/app/page.tsx`

```tsx
"use client";
import { CopilotChat } from "@copilotkit/react-core/v2";
import { ChartCanvas } from "@/features/segmentation/components/chart-canvas";
import { useSegmentationCharts } from "@/hooks/use-segmentation-charts";

export default function HomePage() {
  useSegmentationCharts();
  return (
    <div className="flex h-screen">
      <aside className="w-1/3 border-r">
        <CopilotChat input={{ disclaimer: () => null }} />
      </aside>
      <main className="flex-1 overflow-y-auto p-6">
        <ChartCanvas />
      </main>
    </div>
  );
}
```

### `useSegmentationCharts` hook

Registers controlled generative UI components. The agent renders charts by
calling the `render_chart` tool, which streams a `ChartSpec` into
`state.charts`. The hook also registers the `useComponent` renderers for
inline chart cards in chat (optional — can defer).

### `ChartCanvas`

Reads `agent.state.charts`, validates each via Zod, renders by `type`:
`pie` → `<PieChart>`, `bar` → `<BarChart>`, `metric` → `<MetricCard>`.

Empty state: friendly message *"Ask me about your customers — try 'show me
distribution by city for premium clients'."*

## System prompt outline

The full prompt lives in `agent/src/system_prompt.py`. Key rules:

```
You are a marketing analytics assistant. The user is a marketer exploring
their company's Zoho CRM. Your job is to help them understand customer
segments through queries and charts, and proactively suggest interesting
angles you notice in the data.

## Tool usage
- ALWAYS call list_custom_fields before proposing a segment using a custom
  field — never assume a field exists.
- For "how many" or "distribution" questions, prefer get_field_distribution
  over query_customers + manual aggregation.
- After getting data, ALWAYS call render_chart to visualize. Don't dump raw
  numbers in chat when a chart is available.
- query_customers default to id+name only. Only request emails/phones if the
  user explicitly asks to see individual contact info.

## Honesty
- If a Zoho tool returns an error, say so clearly. NEVER fabricate counts or
  records.
- If a query would return more than the limit, say so and ask the user to
  narrow filters.

## Proactive suggestions
- After answering the user's primary question, end with ONE proposal of a
  related segment or metric you noticed (e.g., "I notice 60% of premium
  customers are in 3 cities. Want me to break those down by tier?").
- Don't propose more than ONE follow-up at a time.

## Style
- Keep chat replies to 2-3 sentences. The chart speaks for itself.
- Use the user's language (Spanish/English) — match their query.
```

## CopilotKit patterns used in F1

| Pattern | Where | Why |
|---|---|---|
| `useAgent()` + `agent.state` | `ChartCanvas` | Read agent-side state (`charts`) reactively. |
| `useComponent(...)` | `useSegmentationCharts` | Register chart renderers as controlled generative UI. |
| `StateStreamingMiddleware` | `agent/main.py` | Stream `charts` updates as `render_chart` runs. |
| `CopilotKitMiddleware` | `agent/main.py` | Bridge LangGraph state with CopilotKit runtime. |
| MCP / `useFrontendTool` | **NOT used in F1** | No frontend-only tools needed. |
| `useHumanInTheLoop` | **NOT used in F1** | HITL is F3. |

## Definition of Done (F1)

F1 is complete when:

1. ✅ A marketer can run `npm install && npm run dev` from a clean clone with a
   populated `.env`, and reach `http://localhost:3000`.
2. ✅ Asking "how many premium customers do we have?" returns a number from
   real Zoho (not mocked) within 3 seconds.
3. ✅ Asking "show me distribution by city for premium customers" produces a
   pie or bar chart in the canvas with real data.
4. ✅ Every Zoho API call appears in `agent/audit/zoho-audit-YYYY-MM-DD.jsonl`.
5. ✅ Restarting the agent and asking the same question hits Zoho again
   (caches are per-session, not persistent).
6. ✅ Killing Zoho connectivity (e.g., revoking token temporarily) results in
   a clear "I couldn't reach Zoho" message — no fabricated data.
7. ✅ Test suite passes: `pytest agent/tests/`.
8. ✅ The agent proactively suggests a follow-up segment at least once in a
   3-turn conversation about premium customers.
9. ✅ README documents how to obtain Zoho OAuth refresh token end-to-end.

## Open questions / decisions deferred

| # | Question | Default if not answered |
|---|---|---|
| O1 | Marketing team size & timeline | Assumed: small team (≤5), no hard deadline. Affects F5 only. |
| O2 | Specific Zoho modules used (Contacts only? Deals? Custom modules?) | Assumed: Contacts module is primary in F1. Spec extends if user clarifies otherwise during implementation. |
| O3 | Custom field naming conventions in their Zoho | Discoverable via `list_custom_fields` — handled at runtime. |
| O4 | Should chart data be exportable (CSV)? | Out of scope F1. Add to F2 backlog if requested. |
| O5 | Internationalization (Spanish UI) | System prompt mirrors user language. Frontend strings: English in F1, can localize later. |
| O6 | Logging tool calls in addition to audit (for debugging) | LangSmith integration deferred until F3 (audit needs centralization). |

## Out of scope (explicitly)

These are **not** F1 — adding them is scope creep:

- Saving/loading chart sessions
- Sharing charts with other users (no users yet)
- Custom dashboards
- SQL-like query builder UI
- Direct Zoho field editing
- Email/Slack integration of any kind
- Importing/exporting customer lists

## References

- mi-cokit reference template: `/Users/anddyagudelo/Documents/Dev/Local/copilot-kit-practice/mi-cokit/`
- mi-cokit chart pattern: `src/components/generative-ui/charts/` and
  `src/hooks/use-generative-ui-examples.tsx` — F1 reuses this approach for
  pie/bar.
- mi-cokit `StateStreamingMiddleware` pattern: `agent/main.py` lines 24–28.
- Zoho CRM API v6 docs: https://www.zoho.com/crm/developer/docs/api/v6/
- CopilotKit v2 docs: https://docs.copilotkit.ai/

## Next step after spec approval

Invoke `superpowers:writing-plans` to create a phased implementation plan
broken into `P1.1` … `P1.N` work packages, each independently testable.
