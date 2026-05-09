# Cokit Templates — F1 Segmentation Explorer

Local-only chat tool for marketing analysts to explore Zoho CRM customer
segmentation conversationally with AI. Built on Next.js + LangGraph (Python)
+ CopilotKit. Read-only by design — this app never writes to Zoho.

## What you can do

Ask questions like:

- *"How many premium customers do we have in Bogota?"*
- *"Show me distribution by city for active customers."*
- *"What custom fields are in our Contacts module?"*
- *"Suggest 3 interesting segments for an email campaign."*

The agent will call Zoho, return aggregates, render pie / bar / metric
charts in the right pane, and proactively propose related segments.

## Setup

### 1. Prerequisites

- Node.js 20+
- Python 3.12 (managed via `uv`)
- `uv` package manager: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### 2. Clone and install

```bash
git clone git@github.com:AnddyAgudelo/cokit-templates.git
cd cokit-templates
npm install
```

The `postinstall` hook runs `scripts/setup-agent.sh`, which creates the
Python venv at `agent/.venv` and installs the agent's dependencies.

### 3. Generate Zoho OAuth credentials

This app uses Zoho's "self-client" OAuth flow with a refresh token.

1. Go to https://api-console.zoho.com/ and click **Add Client → Self Client**.
2. Note the `Client ID` and `Client Secret`.
3. In the **Generate Code** tab, request scope `ZohoCRM.modules.contacts.READ,ZohoCRM.settings.fields.READ` for `10 min`. Copy the resulting code.
4. Exchange the code for a refresh token:

   ```bash
   curl -X POST https://accounts.zoho.com/oauth/v2/token \
     -d "code=THE_CODE_FROM_STEP_3" \
     -d "client_id=YOUR_CLIENT_ID" \
     -d "client_secret=YOUR_CLIENT_SECRET" \
     -d "grant_type=authorization_code"
   ```

   The response contains `refresh_token` — save it.

> **Data center note:** if your Zoho is in EU, India, Australia, or another
> region, replace the domains: `accounts.zoho.eu`, `www.zohoapis.eu`, etc.

### 4. Configure `.env`

```bash
cp .env.example .env
```

Edit `.env`:

```env
OPENAI_API_KEY=sk-...
ZOHO_CLIENT_ID=...
ZOHO_CLIENT_SECRET=...
ZOHO_REFRESH_TOKEN=...
ZOHO_API_DOMAIN=https://www.zohoapis.com
ZOHO_ACCOUNTS_DOMAIN=https://accounts.zoho.com
```

### 5. Start dev

```bash
npm run dev
```

- Frontend: http://localhost:3000
- Agent: http://localhost:8124 (LangGraph dev server)

## Architecture

- `src/` — Next.js 16 frontend with CopilotKit v2.
- `agent/` — Python LangGraph agent with read-only Zoho client.
- `agent/audit/` — JSONL audit log of every Zoho call (gitignored).
- See `docs/specs/2026-05-09-f1-segmentation-explorer-design.md` for the full
  design rationale.

## Limits

- **Read-only**: this app never writes to Zoho. There are no `POST` / `PUT`
  / `DELETE` methods on the Zoho client by design.
- **Rate limit**: 90 req/min per process (Zoho's typical limit is 100).
- **Cache**: queries are cached for 5 minutes per session. `list_custom_fields`
  is cached for 1 hour.
- **Single-user**: this is a local tool. Each marketer runs their own copy
  with their own Zoho credentials.

## Troubleshooting

- **"Port 8124 is already in use"** — a stale agent is still running. Kill it
  with `lsof -ti:8124 | xargs kill`.
- **"Missing required Zoho env vars"** — check `.env` has all 5 ZOHO_* keys.
- **Agent says "I couldn't reach Zoho"** — check `agent/audit/` for the
  exact error. Common causes: wrong data center domain, expired refresh
  token, revoked OAuth scope.

## Roadmap

This is **F1 of 5**. Subsequent phases:

- F2: Template Builder (build WhatsApp templates with the agent)
- F3: Approval Workflow (Aprobar / Editar / Rechazar)
- F4: Kapso Distribution (publish approved templates → Meta)
- F5: Production Hardening (multi-user auth, deploy, observability)

Each phase has its own spec in `docs/specs/`.

## Tests

```bash
cd agent
source .venv/bin/activate
pytest -v
```

Expected: 39 tests pass (audit, cache, client, query tools, render tool).
