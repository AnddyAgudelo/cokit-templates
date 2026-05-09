# F1 Segmentation Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-only Next.js + Python LangGraph app where a marketer chats with an AI agent that queries read-only Zoho CRM and renders segmentation charts on demand.

**Architecture:** Two-process local dev — Python LangGraph agent on port 8124 owns Zoho integration (rate-limited HTTP client, audit log, in-memory session cache, OAuth refresh). Next.js frontend on port 3000 uses CopilotKit v2 (`useAgent`, `CopilotChat`, Zod-validated agent state) to render dynamic Recharts visualizations alongside a chat panel. No shared infra; each marketer runs their own process with their own Zoho credentials.

**Tech Stack:** Next.js 16, React 19, TypeScript 5, Tailwind 4, CopilotKit 1.56.5, Recharts, Zod, Python 3.12, LangGraph 1.1.6, langchain-openai 1.1.9, copilotkit 0.1.87, httpx, tenacity, pytest, pytest-httpx, freezegun, uv (Python package manager).

**Spec:** `docs/specs/2026-05-09-f1-segmentation-explorer-design.md`

---

## File map

After all phases the repo will look like this. Files marked **(P1)** appear in Phase 1 (skeleton), **(P2)** in Phase 2 (Python backend), **(P3)** in Phase 3 (frontend), **(P4)** in Phase 4 (E2E + docs).

```
cokit-templates/
├── .gitignore                                                    (P1)
├── .env.example                                                  (P1)
├── package.json                                                  (P1)
├── tsconfig.json                                                 (P1)
├── next.config.ts                                                (P1)
├── postcss.config.mjs                                            (P1)
├── README.md                                                     (P4)
├── docs/
│   ├── specs/2026-05-09-f1-segmentation-explorer-design.md       (existing)
│   ├── specs/2026-05-09-f1-segmentation-explorer-design.es.md    (existing)
│   └── plans/2026-05-09-f1-segmentation-explorer.md              (this file)
├── scripts/
│   ├── setup-agent.sh                                            (P1)
│   └── run-agent.sh                                              (P1)
├── src/
│   ├── app/
│   │   ├── globals.css                                           (P1)
│   │   ├── layout.tsx                                            (P3)
│   │   ├── page.tsx                                              (P3)
│   │   └── api/copilotkit/[[...slug]]/route.ts                   (P3)
│   ├── features/segmentation/
│   │   ├── schemas.ts                                            (P3)
│   │   └── components/
│   │       ├── chart-canvas.tsx                                  (P3)
│   │       ├── pie-chart.tsx                                     (P3)
│   │       ├── bar-chart.tsx                                     (P3)
│   │       └── metric-card.tsx                                   (P3)
│   ├── hooks/use-segmentation-charts.tsx                         (P3)
│   └── lib/env.ts                                                (P3)
└── agent/
    ├── pyproject.toml                                            (P1)
    ├── langgraph.json                                            (P1)
    ├── main.py                                                   (P1, finalized P2)
    ├── audit/.gitkeep                                            (P1)
    ├── src/
    │   ├── __init__.py                                           (P1)
    │   ├── state.py                                              (P2)
    │   ├── system_prompt.py                                      (P2)
    │   ├── tools/
    │   │   ├── __init__.py                                       (P2)
    │   │   ├── zoho_queries.py                                   (P2)
    │   │   └── chart_renderers.py                                (P2)
    │   └── zoho/
    │       ├── __init__.py                                       (P2)
    │       ├── audit.py                                          (P2)
    │       ├── cache.py                                          (P2)
    │       └── client.py                                         (P2)
    └── tests/
        ├── __init__.py                                           (P1)
        ├── conftest.py                                           (P2)
        ├── test_audit.py                                         (P2)
        ├── test_cache.py                                         (P2)
        ├── test_zoho_client.py                                   (P2)
        ├── test_zoho_queries.py                                  (P2)
        └── test_chart_renderers.py                               (P2)
```

## Testing approach

**Python (TDD):** Every business-logic file in `agent/src/zoho/` and `agent/src/tools/` is built test-first using **pytest** + **pytest-httpx** (HTTP-level Zoho mocking) + **freezegun** (deterministic timestamps). Each task ends with all tests green.

**Frontend:** No test framework in F1. Zod schemas at the agent→frontend boundary catch shape errors at runtime; visual correctness is verified via manual browser smoke tests at the end of Phase 3 and Phase 4. Unit/integration testing for React components is deferred to F5.

**E2E:** Phase 4 ends with a manual smoke test against real Zoho production data driven by the user.

---

## Phase 1: Project bootstrap

After Phase 1 the repo boots cleanly: `npm install` succeeds, `npm run dev` starts both processes, the Next.js page loads at `http://localhost:3000`, and the agent responds to a trivial chat message ("hello") through CopilotKit. No Zoho integration yet.

---

### Task 1: gitignore and env example

**Files:**
- Create: `.gitignore`
- Create: `.env.example`

- [ ] **Step 1: Write `.gitignore`**

Create `/Users/anddyagudelo/Documents/Dev/Local/cokit-templates/.gitignore`:

```gitignore
# Node
node_modules/
.next/
.turbo/
out/
*.log

# Python
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.mypy_cache/
*.egg-info/

# Env
.env
.env.local
.env.*.local
!.env.example

# Audit logs (runtime artifact)
agent/audit/*.jsonl

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
```

- [ ] **Step 2: Write `.env.example`**

Create `.env.example`:

```env
# OpenAI
OPENAI_API_KEY=sk-...
# Optional: override default model (gpt-5.2-mini)
# OPENAI_MODEL=gpt-5.2-mini

# Zoho CRM (read-only OAuth — see README for refresh token instructions)
ZOHO_CLIENT_ID=
ZOHO_CLIENT_SECRET=
ZOHO_REFRESH_TOKEN=
# Adjust per data center: zohoapis.com / zohoapis.eu / zohoapis.in / zohoapis.com.au
ZOHO_API_DOMAIN=https://www.zohoapis.com
ZOHO_ACCOUNTS_DOMAIN=https://accounts.zoho.com

# Frontend → agent connection
AGENT_URL=http://localhost:8124

# Optional LangSmith tracing
LANGSMITH_API_KEY=
```

- [ ] **Step 3: Verify .gitignore is effective**

Run: `cd /Users/anddyagudelo/Documents/Dev/Local/cokit-templates && touch .env && git status --short`
Expected: `.env` does NOT appear in the output (only `.env.example` and `.gitignore` should be untracked).

Then: `rm .env`

- [ ] **Step 4: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add .gitignore .env.example
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Add .gitignore and .env.example for F1 setup"
```

---

### Task 2: Next.js scaffold

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `next.config.ts`
- Create: `postcss.config.mjs`
- Create: `src/app/globals.css`

- [ ] **Step 1: Write `package.json`**

```json
{
  "name": "cokit-templates",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "concurrently \"npm run dev:ui\" \"npm run dev:agent\" --names ui,agent --prefix-colors blue,green --kill-others",
    "dev:ui": "next dev --turbopack",
    "dev:agent": "./scripts/run-agent.sh",
    "build": "next build",
    "start": "next start",
    "install:agent": "./scripts/setup-agent.sh",
    "postinstall": "npm run install:agent"
  },
  "dependencies": {
    "@copilotkit/react-core": "1.56.5",
    "@copilotkit/react-ui": "1.56.5",
    "@copilotkit/runtime": "1.56.5",
    "@copilotkit/shared": "1.56.5",
    "clsx": "^2.1.1",
    "hono": "^4.12.10",
    "lucide-react": "^0.577.0",
    "next": "16.1.6",
    "react": "^19.2.4",
    "react-dom": "^19.2.4",
    "recharts": "^3.7.0",
    "tailwind-merge": "^3.5.0",
    "zod": "^3.23.8"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4",
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "concurrently": "^9.1.2",
    "tailwindcss": "^4",
    "typescript": "^5"
  }
}
```

- [ ] **Step 2: Write `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Write `next.config.ts`**

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {};

export default nextConfig;
```

- [ ] **Step 4: Write `postcss.config.mjs`**

```javascript
const config = {
  plugins: ["@tailwindcss/postcss"],
};

export default config;
```

- [ ] **Step 5: Write `src/app/globals.css`**

```css
@import "tailwindcss";

:root {
  --background: #ffffff;
  --foreground: #0a0a0a;
  --border: #e5e7eb;
}

@media (prefers-color-scheme: dark) {
  :root {
    --background: #0a0a0a;
    --foreground: #fafafa;
    --border: #27272a;
  }
}

body {
  background: var(--background);
  color: var(--foreground);
  font-family: ui-sans-serif, system-ui, sans-serif;
}
```

- [ ] **Step 6: Run `npm install`**

```bash
cd /Users/anddyagudelo/Documents/Dev/Local/cokit-templates
npm install --ignore-scripts
```

We pass `--ignore-scripts` because `postinstall` runs `setup-agent.sh` which doesn't exist yet. We'll do a full install in Task 4.

Expected: package-lock.json created, `node_modules/` populated, no errors.

- [ ] **Step 7: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add package.json package-lock.json tsconfig.json next.config.ts postcss.config.mjs src/app/globals.css
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Scaffold Next.js 16 app with Tailwind 4 and CopilotKit deps"
```

---

### Task 3: Python agent scaffold

**Files:**
- Create: `agent/pyproject.toml`
- Create: `agent/langgraph.json`
- Create: `agent/main.py` (stub — finalized in Task 16)
- Create: `agent/src/__init__.py`
- Create: `agent/tests/__init__.py`
- Create: `agent/audit/.gitkeep`
- Create: `scripts/setup-agent.sh`
- Create: `scripts/run-agent.sh`

- [ ] **Step 1: Write `agent/pyproject.toml`**

```toml
[project]
name = "cokit-templates-agent"
version = "0.1.0"
description = "F1 Segmentation Explorer agent"
requires-python = ">=3.12"
dependencies = [
  "langchain==1.2.15",
  "langgraph==1.1.6",
  "langchain-openai==1.1.9",
  "copilotkit==0.1.87",
  "langgraph-cli[inmem]==0.4.21",
  "langgraph-api==0.7.101",
  "httpx>=0.27,<1.0",
  "tenacity>=9.0,<10.0",
  "python-dotenv>=1.0.0,<2.0.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0,<9.0",
  "pytest-httpx>=0.30,<1.0",
  "freezegun>=1.5,<2.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

- [ ] **Step 2: Write `agent/langgraph.json`**

```json
{
  "python_version": "3.12",
  "dependencies": ["."],
  "package_manager": "uv",
  "graphs": {
    "segmentation_agent": "./main.py:graph"
  },
  "env": "../.env"
}
```

- [ ] **Step 3: Write stub `agent/main.py`**

```python
"""Entry point for the LangGraph agent. Finalized in Task 16."""
from copilotkit import CopilotKitMiddleware
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

agent = create_agent(
    model=ChatOpenAI(model="gpt-5.2-mini"),
    tools=[],
    middleware=[CopilotKitMiddleware()],
    system_prompt="You are a stub agent for the bootstrap phase.",
)

graph = agent
```

- [ ] **Step 4: Create empty package files**

```bash
cd /Users/anddyagudelo/Documents/Dev/Local/cokit-templates
mkdir -p agent/src agent/tests agent/audit
touch agent/src/__init__.py agent/tests/__init__.py agent/audit/.gitkeep
```

- [ ] **Step 5: Write `scripts/setup-agent.sh`**

```bash
#!/bin/bash
set -e

cd "$(dirname "$0")/../agent"

if ! command -v uv &> /dev/null; then
  echo "uv not found. Install from https://docs.astral.sh/uv/"
  exit 1
fi

uv venv --python 3.12
uv pip install -e ".[dev]"

echo "Agent setup complete. Run from repo root: npm run dev"
```

- [ ] **Step 6: Write `scripts/run-agent.sh`**

```bash
#!/bin/bash
set -e

cd "$(dirname "$0")/../agent"

source .venv/bin/activate
exec npx @langchain/langgraph-cli dev --port 8124 --no-browser
```

- [ ] **Step 7: Make scripts executable**

```bash
cd /Users/anddyagudelo/Documents/Dev/Local/cokit-templates
chmod +x scripts/setup-agent.sh scripts/run-agent.sh
```

- [ ] **Step 8: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add agent/ scripts/
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Scaffold Python LangGraph agent with uv and bootstrap scripts"
```

---

### Task 4: Bootstrap smoke test

**Files:** none modified

- [ ] **Step 1: Run setup script**

```bash
cd /Users/anddyagudelo/Documents/Dev/Local/cokit-templates
./scripts/setup-agent.sh
```

Expected: virtualenv created at `agent/.venv`, dependencies install with no errors. Final line: "Agent setup complete."

If `uv` is missing, install it first: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

- [ ] **Step 2: Populate minimal `.env`**

```bash
cd /Users/anddyagudelo/Documents/Dev/Local/cokit-templates
cp .env.example .env
```

Then edit `.env` and set ONLY `OPENAI_API_KEY=sk-...` to your real value. Leave Zoho vars empty for now — the bootstrap stub doesn't touch Zoho.

- [ ] **Step 3: Start the dev stack**

```bash
cd /Users/anddyagudelo/Documents/Dev/Local/cokit-templates
npm run dev
```

Expected within ~30 seconds:
- `[ui] ▲ Next.js 16.x` followed by `Ready in ...`
- `[agent] ... Welcome to LangGraph Server` (or similar)
- Agent listening on `http://localhost:8124`

- [ ] **Step 4: Verify Next.js loads**

In a browser, open `http://localhost:3000`. Expected: Next.js default page (we haven't written `page.tsx` yet, so 404 is also acceptable here).

- [ ] **Step 5: Verify agent responds**

In a separate terminal:

```bash
curl -s http://localhost:8124/info | head -20
```

Expected: JSON response containing `"graphs":{"segmentation_agent":...}`.

- [ ] **Step 6: Stop the stack**

In the `npm run dev` terminal: press `Ctrl+C`. Wait until both processes report shutdown.

- [ ] **Step 7: No commit** — this task only verifies; no files changed.

---

## Phase 2: Agent backend (TDD)

Each task ends with `pytest agent/tests/ -v` green. The agent gains real Zoho capabilities incrementally.

---

### Task 5: AgentState (state.py)

**Files:**
- Create: `agent/src/state.py`

State has no logic, so no test file. Type-only.

- [ ] **Step 1: Write `agent/src/state.py`**

```python
"""TypedDicts that define what the agent knows about. Mirrored in Zod on the frontend."""
from typing import Literal, TypedDict

from langchain.agents import AgentState as BaseAgentState

ChartType = Literal["pie", "bar", "metric"]


class ChartDataPoint(TypedDict):
    label: str
    value: float


class ChartSpec(TypedDict):
    id: str
    type: ChartType
    title: str
    data: list[ChartDataPoint]
    x_label: str | None
    y_label: str | None
    source_query: str


class AgentState(BaseAgentState):
    charts: list[ChartSpec]
    last_segment_filter: dict | None
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
cd /Users/anddyagudelo/Documents/Dev/Local/cokit-templates/agent
source .venv/bin/activate
python -c "from src.state import AgentState, ChartSpec, ChartType; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add agent/src/state.py
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Add AgentState and ChartSpec TypedDicts"
```

---

### Task 6: AuditLogger (audit.py)

**Files:**
- Create: `agent/src/zoho/__init__.py`
- Create: `agent/src/zoho/audit.py`
- Create: `agent/tests/conftest.py`
- Create: `agent/tests/test_audit.py`

- [ ] **Step 1: Create empty package**

```bash
cd /Users/anddyagudelo/Documents/Dev/Local/cokit-templates/agent
touch src/zoho/__init__.py
```

- [ ] **Step 2: Write the failing test**

`agent/tests/test_audit.py`:

```python
import json
from datetime import UTC, datetime
from pathlib import Path

from freezegun import freeze_time

from src.zoho.audit import AuditLogger


@freeze_time("2026-05-09 12:00:00", tz_offset=0)
def test_log_success_writes_jsonl_entry(tmp_path: Path) -> None:
    logger = AuditLogger(audit_dir=tmp_path)
    logger.log_success(
        path="Contacts/search",
        params={"criteria": "(Tier:equals:premium)"},
        response={"data": [{"id": "1"}, {"id": "2"}]},
        latency_ms=145.7,
    )

    audit_file = tmp_path / "zoho-audit-2026-05-09.jsonl"
    assert audit_file.exists()
    entry = json.loads(audit_file.read_text().strip())
    assert entry["tool"] == "Contacts/search"
    assert entry["params"] == {"criteria": "(Tier:equals:premium)"}
    assert entry["record_count"] == 2
    assert entry["latency_ms"] == 145.7
    assert entry["status"] == "ok"


@freeze_time("2026-05-09 12:00:00", tz_offset=0)
def test_log_error_records_exception(tmp_path: Path) -> None:
    logger = AuditLogger(audit_dir=tmp_path)
    logger.log_error(
        path="Contacts/search",
        params={"criteria": "broken"},
        error=ValueError("simulated"),
    )

    audit_file = tmp_path / "zoho-audit-2026-05-09.jsonl"
    entry = json.loads(audit_file.read_text().strip())
    assert entry["status"] == "error"
    assert entry["error"] == "simulated"


def test_log_appends_multiple_entries(tmp_path: Path) -> None:
    logger = AuditLogger(audit_dir=tmp_path)
    for i in range(3):
        logger.log_success(
            path=f"call-{i}",
            params=None,
            response={"data": []},
            latency_ms=10.0,
        )

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    lines = (tmp_path / f"zoho-audit-{today}.jsonl").read_text().strip().split("\n")
    assert len(lines) == 3


def test_log_handles_response_without_data_list(tmp_path: Path) -> None:
    logger = AuditLogger(audit_dir=tmp_path)
    logger.log_success(
        path="settings/fields",
        params={"module": "Contacts"},
        response={"fields": [{"api_name": "x"}]},
        latency_ms=20.0,
    )

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    entry = json.loads(
        (tmp_path / f"zoho-audit-{today}.jsonl").read_text().strip()
    )
    assert entry["record_count"] == 0
```

- [ ] **Step 3: Run test — expect failure (no module yet)**

```bash
cd /Users/anddyagudelo/Documents/Dev/Local/cokit-templates/agent
source .venv/bin/activate
pytest tests/test_audit.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.zoho.audit'`.

- [ ] **Step 4: Implement `agent/src/zoho/audit.py`**

```python
"""Append-only JSONL logger for Zoho API calls. Files rotate daily."""
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class AuditLogger:
    def __init__(self, audit_dir: str | Path = "audit"):
        self._audit_dir = Path(audit_dir)
        self._audit_dir.mkdir(parents=True, exist_ok=True)

    def _path_for_today(self) -> Path:
        date = datetime.now(UTC).strftime("%Y-%m-%d")
        return self._audit_dir / f"zoho-audit-{date}.jsonl"

    def log_success(
        self,
        path: str,
        params: dict[str, Any] | None,
        response: dict[str, Any],
        *,
        latency_ms: float,
    ) -> None:
        self._write({
            "ts": datetime.now(UTC).isoformat(),
            "tool": path,
            "params": params or {},
            "record_count": self._count_records(response),
            "latency_ms": round(latency_ms, 1),
            "status": "ok",
        })

    def log_error(
        self,
        path: str,
        params: dict[str, Any] | None,
        error: Exception,
    ) -> None:
        self._write({
            "ts": datetime.now(UTC).isoformat(),
            "tool": path,
            "params": params or {},
            "status": "error",
            "error": str(error),
        })

    def _count_records(self, response: dict[str, Any]) -> int:
        if not isinstance(response, dict):
            return 0
        data = response.get("data")
        return len(data) if isinstance(data, list) else 0

    def _write(self, entry: dict[str, Any]) -> None:
        with self._path_for_today().open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
```

- [ ] **Step 5: Run tests — expect green**

```bash
pytest tests/test_audit.py -v
```

Expected: 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add agent/src/zoho/__init__.py agent/src/zoho/audit.py agent/tests/test_audit.py
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Add AuditLogger with daily-rotating JSONL output"
```

---

### Task 7: SessionCache (cache.py)

**Files:**
- Create: `agent/src/zoho/cache.py`
- Create: `agent/tests/test_cache.py`

- [ ] **Step 1: Write the failing test**

`agent/tests/test_cache.py`:

```python
import pytest

from src.zoho.cache import SessionCache


def test_set_and_get_returns_stored_value() -> None:
    cache = SessionCache()
    cache.set("k", {"hello": "world"})
    assert cache.get("k") == {"hello": "world"}


def test_get_missing_key_returns_none() -> None:
    cache = SessionCache()
    assert cache.get("missing") is None


def test_expired_entry_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = SessionCache(default_ttl_seconds=10)

    fake_time = [1000.0]
    monkeypatch.setattr("src.zoho.cache.time.monotonic", lambda: fake_time[0])

    cache.set("k", "v")
    fake_time[0] = 1011.0
    assert cache.get("k") is None


def test_explicit_ttl_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = SessionCache(default_ttl_seconds=10)

    fake_time = [1000.0]
    monkeypatch.setattr("src.zoho.cache.time.monotonic", lambda: fake_time[0])

    cache.set("k", "v", ttl_seconds=100)
    fake_time[0] = 1050.0
    assert cache.get("k") == "v"


def test_clear_removes_all_entries() -> None:
    cache = SessionCache()
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None
```

- [ ] **Step 2: Run test — expect failure**

```bash
pytest tests/test_cache.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `agent/src/zoho/cache.py`**

```python
"""In-process TTL cache. Data lives only for the lifetime of the agent process."""
import time
from typing import Any


class SessionCache:
    def __init__(self, default_ttl_seconds: int = 300):
        self._store: dict[str, tuple[float, Any]] = {}
        self._default_ttl = default_ttl_seconds

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        self._store[key] = (time.monotonic() + ttl, value)

    def clear(self) -> None:
        self._store.clear()
```

- [ ] **Step 4: Run tests — expect green**

```bash
pytest tests/test_cache.py -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add agent/src/zoho/cache.py agent/tests/test_cache.py
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Add SessionCache with monotonic TTL"
```

---

### Task 8: ZohoClient skeleton + OAuth refresh + RateLimiter

**Files:**
- Create: `agent/src/zoho/client.py`
- Modify: `agent/tests/test_zoho_client.py` (new file)

- [ ] **Step 1: Write the failing tests**

`agent/tests/test_zoho_client.py`:

```python
import time
from pathlib import Path

import pytest

from src.zoho.audit import AuditLogger
from src.zoho.cache import SessionCache
from src.zoho.client import RateLimiter, ZohoClient, ZohoConfig


@pytest.fixture
def config() -> ZohoConfig:
    return ZohoConfig(
        client_id="test-id",
        client_secret="test-secret",
        refresh_token="test-refresh",
        api_domain="https://www.zohoapis.com",
        accounts_domain="https://accounts.zoho.com",
    )


@pytest.fixture
def audit(tmp_path: Path) -> AuditLogger:
    return AuditLogger(audit_dir=tmp_path)


@pytest.fixture
def cache() -> SessionCache:
    return SessionCache()


def test_zoho_config_from_env_missing_var_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZOHO_CLIENT_ID", raising=False)
    monkeypatch.delenv("ZOHO_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("ZOHO_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("ZOHO_API_DOMAIN", raising=False)
    monkeypatch.delenv("ZOHO_ACCOUNTS_DOMAIN", raising=False)
    with pytest.raises(RuntimeError, match="Missing"):
        ZohoConfig.from_env()


def test_zoho_config_from_env_strips_trailing_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZOHO_CLIENT_ID", "id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "secret")
    monkeypatch.setenv("ZOHO_REFRESH_TOKEN", "refresh")
    monkeypatch.setenv("ZOHO_API_DOMAIN", "https://www.zohoapis.com/")
    monkeypatch.setenv("ZOHO_ACCOUNTS_DOMAIN", "https://accounts.zoho.com/")
    cfg = ZohoConfig.from_env()
    assert cfg.api_domain == "https://www.zohoapis.com"
    assert cfg.accounts_domain == "https://accounts.zoho.com"


def test_refresh_token_calls_oauth_endpoint(
    config: ZohoConfig,
    audit: AuditLogger,
    cache: SessionCache,
    httpx_mock,
) -> None:
    httpx_mock.add_response(
        url="https://accounts.zoho.com/oauth/v2/token",
        method="POST",
        json={"access_token": "new-token", "expires_in": 3600},
    )
    client = ZohoClient(config, audit=audit, cache=cache)
    client._refresh_token_if_needed()
    assert client._access_token == "new-token"


def test_refresh_token_skipped_when_token_fresh(
    config: ZohoConfig,
    audit: AuditLogger,
    cache: SessionCache,
    httpx_mock,
) -> None:
    client = ZohoClient(config, audit=audit, cache=cache)
    client._access_token = "still-valid"
    client._token_expires_at = time.monotonic() + 3600

    client._refresh_token_if_needed()
    assert len(httpx_mock.get_requests()) == 0
    assert client._access_token == "still-valid"


def test_rate_limiter_allows_under_capacity() -> None:
    limiter = RateLimiter(per_minute=3)
    limiter.acquire()
    limiter.acquire()
    limiter.acquire()


def test_rate_limiter_resets_after_window(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_time = [1000.0]
    monkeypatch.setattr("src.zoho.client.time.monotonic", lambda: fake_time[0])
    monkeypatch.setattr("src.zoho.client.time.sleep", lambda _: None)

    limiter = RateLimiter(per_minute=2)
    limiter.acquire()
    limiter.acquire()
    fake_time[0] = 1061.0
    limiter.acquire()
```

- [ ] **Step 2: Run test — expect failure**

```bash
pytest tests/test_zoho_client.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `agent/src/zoho/client.py`**

```python
"""Zoho CRM read-only HTTP client. ALL Zoho calls flow through this module."""
import os
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

import httpx

from src.zoho.audit import AuditLogger
from src.zoho.cache import SessionCache


@dataclass(frozen=True)
class ZohoConfig:
    client_id: str
    client_secret: str
    refresh_token: str
    api_domain: str
    accounts_domain: str

    @classmethod
    def from_env(cls) -> "ZohoConfig":
        required = {
            "ZOHO_CLIENT_ID": os.environ.get("ZOHO_CLIENT_ID"),
            "ZOHO_CLIENT_SECRET": os.environ.get("ZOHO_CLIENT_SECRET"),
            "ZOHO_REFRESH_TOKEN": os.environ.get("ZOHO_REFRESH_TOKEN"),
            "ZOHO_API_DOMAIN": os.environ.get("ZOHO_API_DOMAIN"),
            "ZOHO_ACCOUNTS_DOMAIN": os.environ.get("ZOHO_ACCOUNTS_DOMAIN"),
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise RuntimeError(f"Missing required Zoho env vars: {missing}")
        return cls(
            client_id=required["ZOHO_CLIENT_ID"],
            client_secret=required["ZOHO_CLIENT_SECRET"],
            refresh_token=required["ZOHO_REFRESH_TOKEN"],
            api_domain=required["ZOHO_API_DOMAIN"].rstrip("/"),
            accounts_domain=required["ZOHO_ACCOUNTS_DOMAIN"].rstrip("/"),
        )


class RateLimiter:
    """Per-minute token bucket. Blocks until window resets if exhausted."""

    def __init__(self, per_minute: int):
        self._capacity = per_minute
        self._tokens = per_minute
        self._window_start = time.monotonic()
        self._lock = Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                if now - self._window_start >= 60.0:
                    self._tokens = self._capacity
                    self._window_start = now
                if self._tokens > 0:
                    self._tokens -= 1
                    return
                sleep_for = 60.0 - (now - self._window_start)
            time.sleep(max(sleep_for, 0))


class ZohoClient:
    """Read-only Zoho client. NO post/put/delete methods on purpose."""

    def __init__(
        self,
        config: ZohoConfig,
        *,
        audit: AuditLogger,
        cache: SessionCache,
        http: httpx.Client | None = None,
        rate_limiter: RateLimiter | None = None,
    ):
        self._config = config
        self._audit = audit
        self._cache = cache
        self._http = http or httpx.Client(timeout=10.0)
        self._rate_limiter = rate_limiter or RateLimiter(per_minute=90)
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    def _refresh_token_if_needed(self) -> None:
        if self._access_token and time.monotonic() < self._token_expires_at - 30:
            return

        resp = self._http.post(
            f"{self._config.accounts_domain}/oauth/v2/token",
            data={
                "refresh_token": self._config.refresh_token,
                "client_id": self._config.client_id,
                "client_secret": self._config.client_secret,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        self._access_token = body["access_token"]
        expires_in = body.get("expires_in", 3600)
        self._token_expires_at = time.monotonic() + expires_in
```

- [ ] **Step 4: Run tests — expect green**

```bash
pytest tests/test_zoho_client.py -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add agent/src/zoho/client.py agent/tests/test_zoho_client.py
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Add ZohoConfig, RateLimiter, ZohoClient with OAuth refresh"
```

---

### Task 9: ZohoClient.get with cache and audit

**Files:**
- Modify: `agent/src/zoho/client.py`
- Modify: `agent/tests/test_zoho_client.py`

- [ ] **Step 1: Add the failing tests at the bottom of `test_zoho_client.py`**

Append to `agent/tests/test_zoho_client.py`:

```python
def test_get_returns_response_and_audits(
    config: ZohoConfig,
    audit: AuditLogger,
    cache: SessionCache,
    httpx_mock,
    tmp_path: Path,
) -> None:
    httpx_mock.add_response(
        url="https://accounts.zoho.com/oauth/v2/token",
        method="POST",
        json={"access_token": "test-token", "expires_in": 3600},
    )
    httpx_mock.add_response(
        url="https://www.zohoapis.com/crm/v6/Contacts/search?criteria=%28Tier%3Aequals%3Apremium%29",
        method="GET",
        json={"data": [{"id": "1", "Last_Name": "Alice"}]},
    )

    client = ZohoClient(config, audit=audit, cache=cache)
    result = client.get("Contacts/search", params={"criteria": "(Tier:equals:premium)"})

    assert result == {"data": [{"id": "1", "Last_Name": "Alice"}]}
    audit_files = list(tmp_path.glob("zoho-audit-*.jsonl"))
    assert len(audit_files) == 1
    assert "Contacts/search" in audit_files[0].read_text()


def test_get_uses_cache_on_second_call(
    config: ZohoConfig,
    audit: AuditLogger,
    cache: SessionCache,
    httpx_mock,
) -> None:
    httpx_mock.add_response(
        url="https://accounts.zoho.com/oauth/v2/token",
        method="POST",
        json={"access_token": "test-token", "expires_in": 3600},
    )
    httpx_mock.add_response(
        url="https://www.zohoapis.com/crm/v6/settings/fields?module=Contacts",
        method="GET",
        json={"fields": [{"api_name": "City"}]},
    )

    client = ZohoClient(config, audit=audit, cache=cache)
    client.get(
        "settings/fields",
        params={"module": "Contacts"},
        cache_key="fields:Contacts",
    )
    client.get(
        "settings/fields",
        params={"module": "Contacts"},
        cache_key="fields:Contacts",
    )

    # Token POST + 1 GET = 2 requests; cache hit means second GET didn't fire
    assert len(httpx_mock.get_requests()) == 2


def test_get_logs_error_on_http_failure(
    config: ZohoConfig,
    audit: AuditLogger,
    cache: SessionCache,
    httpx_mock,
    tmp_path: Path,
) -> None:
    httpx_mock.add_response(
        url="https://accounts.zoho.com/oauth/v2/token",
        method="POST",
        json={"access_token": "test-token", "expires_in": 3600},
    )
    httpx_mock.add_response(
        url="https://www.zohoapis.com/crm/v6/Contacts/search",
        method="GET",
        status_code=500,
    )

    client = ZohoClient(config, audit=audit, cache=cache)
    with pytest.raises(httpx.HTTPStatusError):
        client.get("Contacts/search")

    audit_files = list(tmp_path.glob("zoho-audit-*.jsonl"))
    assert len(audit_files) == 1
    assert "error" in audit_files[0].read_text()
```

Add the import at the top of the file if missing:

```python
import httpx
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_zoho_client.py -v -k "get_"
```

Expected: tests fail because `ZohoClient.get` doesn't exist.

- [ ] **Step 3: Implement `get()` on `ZohoClient`**

Append the following method to the `ZohoClient` class in `agent/src/zoho/client.py`:

```python
    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        cache_key: str | None = None,
        cache_ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        """
        Read-only Zoho GET with caching, rate limiting, and audit logging.
        `cache_key=None` disables caching for this call.
        """
        if cache_key:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        self._rate_limiter.acquire()
        self._refresh_token_if_needed()

        url = f"{self._config.api_domain}/crm/v6/{path.lstrip('/')}"
        t0 = time.monotonic()
        try:
            resp = self._http.get(
                url,
                headers={"Authorization": f"Zoho-oauthtoken {self._access_token}"},
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self._audit.log_error(path, params, e)
            raise

        latency_ms = (time.monotonic() - t0) * 1000
        self._audit.log_success(path, params, data, latency_ms=latency_ms)

        if cache_key:
            self._cache.set(cache_key, data, ttl_seconds=cache_ttl_seconds)

        return data
```

- [ ] **Step 4: Run tests — expect green**

```bash
pytest tests/test_zoho_client.py -v
```

Expected: 9 tests pass (6 from Task 8 + 3 new).

- [ ] **Step 5: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add agent/src/zoho/client.py agent/tests/test_zoho_client.py
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Add ZohoClient.get with cache, rate limit, and audit logging"
```

---

### Task 10: Retry on 429 with tenacity

**Files:**
- Modify: `agent/src/zoho/client.py`
- Modify: `agent/tests/test_zoho_client.py`

- [ ] **Step 1: Add the failing test**

Append to `agent/tests/test_zoho_client.py`:

```python
def test_get_retries_once_on_429(
    monkeypatch: pytest.MonkeyPatch,
    config: ZohoConfig,
    audit: AuditLogger,
    cache: SessionCache,
    httpx_mock,
) -> None:
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda _: None)

    httpx_mock.add_response(
        url="https://accounts.zoho.com/oauth/v2/token",
        method="POST",
        json={"access_token": "t", "expires_in": 3600},
    )
    httpx_mock.add_response(
        url="https://www.zohoapis.com/crm/v6/Contacts/search",
        method="GET",
        status_code=429,
    )
    httpx_mock.add_response(
        url="https://www.zohoapis.com/crm/v6/Contacts/search",
        method="GET",
        json={"data": []},
    )

    client = ZohoClient(config, audit=audit, cache=cache)
    result = client.get("Contacts/search")
    assert result == {"data": []}


def test_get_gives_up_after_3_attempts_on_429(
    monkeypatch: pytest.MonkeyPatch,
    config: ZohoConfig,
    audit: AuditLogger,
    cache: SessionCache,
    httpx_mock,
) -> None:
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda _: None)

    httpx_mock.add_response(
        url="https://accounts.zoho.com/oauth/v2/token",
        method="POST",
        json={"access_token": "t", "expires_in": 3600},
    )
    for _ in range(3):
        httpx_mock.add_response(
            url="https://www.zohoapis.com/crm/v6/Contacts/search",
            method="GET",
            status_code=429,
        )

    client = ZohoClient(config, audit=audit, cache=cache)
    with pytest.raises(httpx.HTTPStatusError):
        client.get("Contacts/search")
```

- [ ] **Step 2: Run test — expect failure**

```bash
pytest tests/test_zoho_client.py -v -k "retries_once or gives_up"
```

Expected: first test fails — currently 429 raises immediately, no retry.

- [ ] **Step 3: Add retry decorator helper to `client.py`**

Add the following at the **module level** of `agent/src/zoho/client.py` (just below the imports):

```python
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential


def _is_rate_limited(exc: BaseException) -> bool:
    return (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response.status_code == 429
    )
```

Refactor `ZohoClient.get` to extract the HTTP call into a retried helper. Replace the body of `ZohoClient.get` with:

```python
    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        cache_key: str | None = None,
        cache_ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        if cache_key:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        self._rate_limiter.acquire()
        self._refresh_token_if_needed()

        url = f"{self._config.api_domain}/crm/v6/{path.lstrip('/')}"
        t0 = time.monotonic()
        try:
            data = self._http_get_with_retry(url, params)
        except Exception as e:
            self._audit.log_error(path, params, e)
            raise

        latency_ms = (time.monotonic() - t0) * 1000
        self._audit.log_success(path, params, data, latency_ms=latency_ms)

        if cache_key:
            self._cache.set(cache_key, data, ttl_seconds=cache_ttl_seconds)

        return data

    @retry(
        retry=retry_if_exception(_is_rate_limited),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _http_get_with_retry(
        self, url: str, params: dict[str, Any] | None
    ) -> dict[str, Any]:
        resp = self._http.get(
            url,
            headers={"Authorization": f"Zoho-oauthtoken {self._access_token}"},
            params=params,
        )
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 4: Run all client tests — expect green**

```bash
pytest tests/test_zoho_client.py -v
```

Expected: 11 tests pass.

- [ ] **Step 5: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add agent/src/zoho/client.py agent/tests/test_zoho_client.py
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Add tenacity-based retry on Zoho 429 (max 3 attempts)"
```

---

### Task 11: query_customers tool

**Files:**
- Create: `agent/src/tools/__init__.py`
- Create: `agent/src/tools/zoho_queries.py`
- Create: `agent/tests/test_zoho_queries.py`

- [ ] **Step 1: Create empty package**

```bash
cd /Users/anddyagudelo/Documents/Dev/Local/cokit-templates/agent
touch src/tools/__init__.py
```

- [ ] **Step 2: Write the failing test**

`agent/tests/test_zoho_queries.py`:

```python
from unittest.mock import MagicMock

from src.tools.zoho_queries import make_zoho_tools


def _client_returning(payload: dict) -> MagicMock:
    client = MagicMock()
    client.get.return_value = payload
    return client


def test_query_customers_returns_records_and_count() -> None:
    client = _client_returning({
        "data": [
            {"id": "1", "Last_Name": "Alice"},
            {"id": "2", "Last_Name": "Bob"},
        ],
        "info": {"count": 2, "more_records": False},
    })
    [query_customers, *_] = make_zoho_tools(client)

    result = query_customers.invoke({
        "filters": {"Tier": "premium"},
        "limit": 50,
    })

    assert result["count"] == 2
    assert len(result["records"]) == 2
    assert result["records"][0]["id"] == "1"


def test_query_customers_requires_filters() -> None:
    client = _client_returning({"data": []})
    [query_customers, *_] = make_zoho_tools(client)

    result = query_customers.invoke({"filters": {}, "limit": 10})
    assert result["count"] == 0
    assert "error" in result


def test_query_customers_caps_limit_at_200() -> None:
    client = _client_returning({"data": [], "info": {"count": 0}})
    [query_customers, *_] = make_zoho_tools(client)

    query_customers.invoke({"filters": {"Tier": "premium"}, "limit": 9999})

    call_kwargs = client.get.call_args.kwargs
    assert call_kwargs["params"]["per_page"] == 200


def test_query_customers_returns_error_on_client_failure() -> None:
    client = MagicMock()
    client.get.side_effect = RuntimeError("zoho down")
    [query_customers, *_] = make_zoho_tools(client)

    result = query_customers.invoke({"filters": {"Tier": "premium"}, "limit": 50})
    assert result["count"] == 0
    assert result["records"] == []
    assert "zoho down" in result["error"]
```

- [ ] **Step 3: Run test — expect failure**

```bash
pytest tests/test_zoho_queries.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement `agent/src/tools/zoho_queries.py`**

```python
"""Zoho CRM query tools. All tools are READ-ONLY by design — no write tools exist."""
from typing import Any

from langchain.tools import tool

from src.zoho.client import ZohoClient


# Default fields surfaced to the LLM. Excludes Email/Phone/Address to keep PII out of context.
DEFAULT_QUERY_FIELDS = ["id", "Last_Name", "First_Name", "Account_Name"]


def _build_criteria(filters: dict[str, str]) -> str:
    """Build a Zoho COQL-like criteria string: (k:equals:v)and(k2:equals:v2)."""
    return "and".join(f"({k}:equals:{v})" for k, v in filters.items())


def make_zoho_tools(client: ZohoClient) -> list:
    """Bind tools to a ZohoClient instance via closure."""

    @tool
    def query_customers(
        filters: dict[str, str],
        limit: int = 50,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Query Zoho contacts matching `filters`.
        `filters` example: {"Tier": "premium", "City": "Bogota"}.
        Returns aggregate count and a list of records.
        Default `fields` exclude PII (email, phone, address) — pass explicit
        `fields` ONLY when the user explicitly drills down on individual contacts.
        """
        if not filters:
            return {
                "count": 0,
                "records": [],
                "error": "filters is required (e.g., {'Tier': 'premium'})",
            }

        capped_limit = min(limit, 200)
        criteria = _build_criteria(filters)
        select = ",".join(fields or DEFAULT_QUERY_FIELDS)

        try:
            response = client.get(
                "Contacts/search",
                params={
                    "criteria": criteria,
                    "fields": select,
                    "per_page": capped_limit,
                },
            )
        except Exception as e:
            return {"count": 0, "records": [], "error": str(e)}

        records = response.get("data", []) or []
        info = response.get("info", {}) or {}
        return {
            "count": info.get("count", len(records)),
            "records": records[:capped_limit],
        }

    @tool
    def get_field_distribution(
        field: str,
        filters: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Aggregate distribution of `field` over the (filtered) Contacts set.
        Returns: {"field": str, "buckets": [{"label": str, "count": int}, ...], "total": int}.
        Prefer this over query_customers + manual aggregation.
        """
        params: dict[str, Any] = {"fields": f"id,{field}", "per_page": 200}
        if filters:
            params["criteria"] = _build_criteria(filters)
            endpoint = "Contacts/search"
        else:
            endpoint = "Contacts"

        try:
            response = client.get(endpoint, params=params)
        except Exception as e:
            return {"field": field, "buckets": [], "total": 0, "error": str(e)}

        records = response.get("data", []) or []
        counts: dict[str, int] = {}
        for rec in records:
            value = rec.get(field)
            label = str(value) if value is not None else "(unknown)"
            counts[label] = counts.get(label, 0) + 1

        buckets = [
            {"label": label, "count": count}
            for label, count in sorted(counts.items(), key=lambda kv: -kv[1])
        ]
        return {"field": field, "buckets": buckets, "total": len(records)}

    @tool
    def list_custom_fields(module: str = "Contacts") -> list[dict[str, Any]]:
        """
        Returns metadata of all fields in a Zoho module (default: Contacts).
        Cached for 1 hour. Use BEFORE proposing segments based on custom fields
        so you don't hallucinate field names.
        """
        try:
            response = client.get(
                "settings/fields",
                params={"module": module},
                cache_key=f"fields:{module}",
                cache_ttl_seconds=3600,
            )
        except Exception:
            return []

        fields = response.get("fields", []) or []
        return [
            {
                "api_name": f.get("api_name"),
                "display_name": f.get("display_label") or f.get("field_label"),
                "type": f.get("data_type"),
                "picklist_values": [
                    pv.get("display_value")
                    for pv in (f.get("pick_list_values") or [])
                ] or None,
            }
            for f in fields
        ]

    return [query_customers, get_field_distribution, list_custom_fields]
```

- [ ] **Step 5: Run query_customers tests — expect green**

```bash
pytest tests/test_zoho_queries.py -v
```

Expected: 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add agent/src/tools/__init__.py agent/src/tools/zoho_queries.py agent/tests/test_zoho_queries.py
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Add Zoho query tools (query_customers + get_field_distribution + list_custom_fields)"
```

---

### Task 12: get_field_distribution tests

**Files:**
- Modify: `agent/tests/test_zoho_queries.py`

The implementation already exists from Task 11. We add tests now to lock down behavior.

- [ ] **Step 1: Append tests**

Add to `agent/tests/test_zoho_queries.py`:

```python
def test_get_field_distribution_buckets_records_by_field() -> None:
    client = _client_returning({
        "data": [
            {"id": "1", "City": "Bogota"},
            {"id": "2", "City": "Medellin"},
            {"id": "3", "City": "Bogota"},
            {"id": "4", "City": None},
        ],
    })
    [_, get_field_distribution, _] = make_zoho_tools(client)

    result = get_field_distribution.invoke({"field": "City"})

    assert result["field"] == "City"
    assert result["total"] == 4
    labels = {b["label"]: b["count"] for b in result["buckets"]}
    assert labels == {"Bogota": 2, "Medellin": 1, "(unknown)": 1}


def test_get_field_distribution_orders_by_count_desc() -> None:
    client = _client_returning({
        "data": [
            {"City": "A"}, {"City": "B"}, {"City": "B"}, {"City": "C"},
            {"City": "C"}, {"City": "C"},
        ],
    })
    [_, get_field_distribution, _] = make_zoho_tools(client)
    result = get_field_distribution.invoke({"field": "City"})
    counts = [b["count"] for b in result["buckets"]]
    assert counts == sorted(counts, reverse=True)


def test_get_field_distribution_with_filters_uses_search_endpoint() -> None:
    client = _client_returning({"data": []})
    [_, get_field_distribution, _] = make_zoho_tools(client)

    get_field_distribution.invoke({
        "field": "City",
        "filters": {"Tier": "premium"},
    })

    call_args = client.get.call_args
    assert call_args.args[0] == "Contacts/search"
    assert "(Tier:equals:premium)" in call_args.kwargs["params"]["criteria"]


def test_get_field_distribution_returns_error_on_failure() -> None:
    from unittest.mock import MagicMock
    client = MagicMock()
    client.get.side_effect = RuntimeError("zoho down")
    [_, get_field_distribution, _] = make_zoho_tools(client)
    result = get_field_distribution.invoke({"field": "City"})
    assert result["buckets"] == []
    assert "zoho down" in result["error"]
```

- [ ] **Step 2: Run tests — expect green**

```bash
pytest tests/test_zoho_queries.py -v -k "distribution"
```

Expected: 4 tests pass.

- [ ] **Step 3: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add agent/tests/test_zoho_queries.py
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Test get_field_distribution buckets, ordering, and filter routing"
```

---

### Task 13: list_custom_fields tests

**Files:**
- Modify: `agent/tests/test_zoho_queries.py`

- [ ] **Step 1: Append tests**

```python
def test_list_custom_fields_normalizes_response() -> None:
    client = _client_returning({
        "fields": [
            {
                "api_name": "Tier",
                "display_label": "Tier",
                "data_type": "picklist",
                "pick_list_values": [
                    {"display_value": "free"},
                    {"display_value": "premium"},
                ],
            },
            {
                "api_name": "City",
                "display_label": "City",
                "data_type": "text",
                "pick_list_values": [],
            },
        ],
    })
    [_, _, list_custom_fields] = make_zoho_tools(client)

    fields = list_custom_fields.invoke({"module": "Contacts"})
    assert fields[0]["api_name"] == "Tier"
    assert fields[0]["picklist_values"] == ["free", "premium"]
    assert fields[1]["api_name"] == "City"
    assert fields[1]["picklist_values"] is None


def test_list_custom_fields_passes_cache_key_to_client() -> None:
    client = _client_returning({"fields": []})
    [_, _, list_custom_fields] = make_zoho_tools(client)

    list_custom_fields.invoke({"module": "Deals"})
    call_kwargs = client.get.call_args.kwargs
    assert call_kwargs["cache_key"] == "fields:Deals"
    assert call_kwargs["cache_ttl_seconds"] == 3600


def test_list_custom_fields_returns_empty_on_failure() -> None:
    from unittest.mock import MagicMock
    client = MagicMock()
    client.get.side_effect = RuntimeError("boom")
    [_, _, list_custom_fields] = make_zoho_tools(client)
    assert list_custom_fields.invoke({}) == []
```

- [ ] **Step 2: Run tests — expect green**

```bash
pytest tests/test_zoho_queries.py -v -k "custom_fields"
```

Expected: 3 tests pass.

- [ ] **Step 3: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add agent/tests/test_zoho_queries.py
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Test list_custom_fields normalization and caching"
```

---

### Task 14: render_chart tool

**Files:**
- Create: `agent/src/tools/chart_renderers.py`
- Create: `agent/tests/test_chart_renderers.py`

- [ ] **Step 1: Write the failing test**

`agent/tests/test_chart_renderers.py`:

```python
from unittest.mock import MagicMock

import pytest

from src.tools.chart_renderers import render_chart


def _runtime(state: dict | None = None) -> MagicMock:
    runtime = MagicMock()
    runtime.state = state if state is not None else {}
    runtime.tool_call_id = "tc-123"
    return runtime


def test_render_chart_appends_chart_to_state() -> None:
    runtime = _runtime(state={"charts": []})
    cmd = render_chart.invoke({
        "type": "pie",
        "title": "Customers by city",
        "data": [
            {"label": "Bogota", "value": 120},
            {"label": "Medellin", "value": 80},
        ],
        "source_query": "Premium customers grouped by city",
    }, runtime=runtime)

    update = cmd.update
    assert "charts" in update
    assert len(update["charts"]) == 1
    chart = update["charts"][0]
    assert chart["type"] == "pie"
    assert chart["title"] == "Customers by city"
    assert chart["data"] == [
        {"label": "Bogota", "value": 120.0},
        {"label": "Medellin", "value": 80.0},
    ]
    assert chart["source_query"] == "Premium customers grouped by city"
    assert chart["id"]


def test_render_chart_preserves_existing_charts() -> None:
    existing = [{"id": "old", "type": "bar", "title": "x", "data": [{"label": "a", "value": 1}], "x_label": None, "y_label": None, "source_query": "y"}]
    runtime = _runtime(state={"charts": existing})

    cmd = render_chart.invoke({
        "type": "metric",
        "title": "Total",
        "data": [{"label": "Total", "value": 500}],
        "source_query": "Sum of customers",
    }, runtime=runtime)

    assert len(cmd.update["charts"]) == 2
    assert cmd.update["charts"][0]["id"] == "old"


def test_render_chart_rejects_invalid_type() -> None:
    runtime = _runtime()
    with pytest.raises(ValueError, match="Unsupported chart type"):
        render_chart.invoke({
            "type": "scatter",
            "title": "x",
            "data": [{"label": "a", "value": 1}],
            "source_query": "y",
        }, runtime=runtime)


def test_render_chart_rejects_empty_data() -> None:
    runtime = _runtime()
    with pytest.raises(ValueError, match="at least one"):
        render_chart.invoke({
            "type": "pie",
            "title": "x",
            "data": [],
            "source_query": "y",
        }, runtime=runtime)


def test_render_chart_skips_invalid_data_points() -> None:
    runtime = _runtime(state={"charts": []})
    cmd = render_chart.invoke({
        "type": "bar",
        "title": "x",
        "data": [
            {"label": "a", "value": 1},
            {"label": "b", "value": "not-a-number"},  # skipped
            {"value": 2},  # missing label, skipped
            {"label": "c", "value": 3},
        ],
        "source_query": "y",
    }, runtime=runtime)
    assert cmd.update["charts"][0]["data"] == [
        {"label": "a", "value": 1.0},
        {"label": "c", "value": 3.0},
    ]
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_chart_renderers.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `agent/src/tools/chart_renderers.py`**

```python
"""Generative-UI tools. The agent calls render_chart after fetching real data."""
import uuid
from typing import Any

from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command

ALLOWED_CHART_TYPES = {"pie", "bar", "metric"}


@tool
def render_chart(
    type: str,
    title: str,
    data: list[dict[str, Any]],
    source_query: str,
    runtime: ToolRuntime,
    x_label: str | None = None,
    y_label: str | None = None,
) -> Command:
    """
    Render a chart of the given type (pie | bar | metric).

    `data` must be a list of {label, value} pairs. Items with non-numeric
    values or missing keys are silently skipped.

    Call AFTER getting real data from a query tool. NEVER invent data.

    `source_query` is a brief human-readable description of what was queried
    (e.g., "Premium customers grouped by city"); shown as the chart subtitle.
    """
    if type not in ALLOWED_CHART_TYPES:
        raise ValueError(
            f"Unsupported chart type: {type}. Use one of {sorted(ALLOWED_CHART_TYPES)}."
        )

    cleaned: list[dict[str, Any]] = []
    for d in data:
        if not isinstance(d, dict) or "label" not in d or "value" not in d:
            continue
        try:
            cleaned.append({"label": str(d["label"]), "value": float(d["value"])})
        except (TypeError, ValueError):
            continue

    if not cleaned:
        raise ValueError(
            "data must contain at least one {label, value} pair with a numeric value"
        )

    chart = {
        "id": str(uuid.uuid4()),
        "type": type,
        "title": title,
        "data": cleaned,
        "x_label": x_label,
        "y_label": y_label,
        "source_query": source_query,
    }

    existing = runtime.state.get("charts", []) or []

    return Command(update={
        "charts": existing + [chart],
        "messages": [ToolMessage(
            content=f"Rendered {type} chart: {title}",
            tool_call_id=runtime.tool_call_id,
        )],
    })
```

- [ ] **Step 4: Run tests — expect green**

```bash
pytest tests/test_chart_renderers.py -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Run the full test suite to confirm nothing regressed**

```bash
pytest -v
```

Expected: all tests pass (4 audit + 5 cache + 11 client + 11 zoho_queries + 5 chart_renderers = 36 tests).

- [ ] **Step 6: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add agent/src/tools/chart_renderers.py agent/tests/test_chart_renderers.py
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Add render_chart tool with type/data validation"
```

---

### Task 15: System prompt

**Files:**
- Create: `agent/src/system_prompt.py`

No tests — it's a string constant. We verify it imports.

- [ ] **Step 1: Write `agent/src/system_prompt.py`**

```python
"""System prompt for the Segmentation Explorer agent.

Kept as a module constant so it can be imported into main.py and (later)
tested for prompt regressions if needed. Written in English; the rule
'Use the user's language' makes the agent respond in Spanish when the user
writes in Spanish.
"""

SYSTEM_PROMPT = """\
You are a marketing analytics assistant. The user is a marketer exploring
their company's Zoho CRM. Your job is to help them understand customer
segments through queries and charts, and proactively suggest interesting
angles you notice in the data.

## Tool usage
- ALWAYS call list_custom_fields before proposing a segment that uses a
  custom field — never assume a field exists.
- For "how many" or "distribution" questions, prefer get_field_distribution
  over query_customers + manual aggregation.
- After getting data, ALWAYS call render_chart to visualize it. Don't dump
  raw numbers in chat when a chart is available.
- query_customers default to id+name only. Only request emails/phones if the
  user explicitly asks to see individual contact info.

## Honesty
- If a Zoho tool returns an error, say so clearly. NEVER fabricate counts or
  records. If a query fails, tell the user "I couldn't reach Zoho" — don't
  guess.
- If a query would return more than the limit (200), say so and ask the user
  to narrow filters.

## Proactive suggestions
- After answering the user's primary question, end with ONE proposal of a
  related segment or metric you noticed. Example: "I notice 60% of premium
  customers are in 3 cities. Want me to break those down by tier?"
- Don't propose more than ONE follow-up at a time.

## Style
- Keep chat replies to 2-3 sentences. The chart speaks for itself.
- Use the user's language (Spanish or English) — match their query.
"""
```

- [ ] **Step 2: Verify import**

```bash
cd /Users/anddyagudelo/Documents/Dev/Local/cokit-templates/agent
source .venv/bin/activate
python -c "from src.system_prompt import SYSTEM_PROMPT; assert 'list_custom_fields' in SYSTEM_PROMPT; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add agent/src/system_prompt.py
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Add system prompt for Segmentation Explorer agent"
```

---

### Task 16: Finalize main.py and verify agent boots end-to-end

**Files:**
- Modify: `agent/main.py`

- [ ] **Step 1: Replace `agent/main.py` with the production version**

```python
"""Entry point for the LangGraph Segmentation Explorer agent."""
import os

from copilotkit import CopilotKitMiddleware
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from src.state import AgentState
from src.system_prompt import SYSTEM_PROMPT
from src.tools.chart_renderers import render_chart
from src.tools.zoho_queries import make_zoho_tools
from src.zoho.audit import AuditLogger
from src.zoho.cache import SessionCache
from src.zoho.client import ZohoClient, ZohoConfig


def _build_agent():
    zoho_config = ZohoConfig.from_env()
    zoho_client = ZohoClient(
        zoho_config,
        audit=AuditLogger(audit_dir="audit"),
        cache=SessionCache(),
    )

    model = ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-5.2-mini"),
        model_kwargs={"parallel_tool_calls": False},
    )

    tools = [*make_zoho_tools(zoho_client), render_chart]

    return create_agent(
        model=model,
        tools=tools,
        middleware=[CopilotKitMiddleware()],
        state_schema=AgentState,
        system_prompt=SYSTEM_PROMPT,
    )


agent = _build_agent()
graph = agent
```

Note: `StateStreamingMiddleware` is intentionally **not** used in F1. Charts are appended to the list atomically when `render_chart` returns — chart rendering is fast enough that progressive streaming isn't a UX win at this stage. We can add it in F2 if needed.

- [ ] **Step 2: Add real Zoho credentials to `.env` (or use placeholder values for the smoke test below)**

If you don't yet have Zoho OAuth credentials, populate `.env` with placeholder strings to let `ZohoConfig.from_env()` succeed:

```env
ZOHO_CLIENT_ID=placeholder
ZOHO_CLIENT_SECRET=placeholder
ZOHO_REFRESH_TOKEN=placeholder
ZOHO_API_DOMAIN=https://www.zohoapis.com
ZOHO_ACCOUNTS_DOMAIN=https://accounts.zoho.com
```

Calls to Zoho will fail with HTTP errors — that's fine for the boot smoke test. Real values needed in Phase 4.

- [ ] **Step 3: Verify agent boots**

```bash
cd /Users/anddyagudelo/Documents/Dev/Local/cokit-templates
npm run dev
```

Expected:
- `[ui] ▲ Next.js ... Ready in ...`
- `[agent] ... Welcome to LangGraph Server`
- No import errors in agent logs.

In another terminal:

```bash
curl -s http://localhost:8124/info | python -m json.tool
```

Expected: JSON output with `"graphs":{"segmentation_agent":{...}}` and the tool list including `query_customers`, `get_field_distribution`, `list_custom_fields`, `render_chart`.

- [ ] **Step 4: Stop the stack**

`Ctrl+C` in the dev terminal.

- [ ] **Step 5: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add agent/main.py
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Wire production agent: Zoho client + tools + system prompt"
```

---

## Phase 3: Frontend wiring

After Phase 3 the user can chat with the agent in the browser, see chart components render from agent state. With placeholder Zoho creds this means errors flowing back nicely; with real creds it means real charts.

---

### Task 17: env validation + Zod schemas

**Files:**
- Create: `src/lib/env.ts`
- Create: `src/features/segmentation/schemas.ts`

- [ ] **Step 1: Write `src/lib/env.ts`**

```typescript
import { z } from "zod";

const envSchema = z.object({
  AGENT_URL: z.string().url().default("http://localhost:8124"),
});

export const env = envSchema.parse({
  AGENT_URL: process.env.AGENT_URL,
});
```

- [ ] **Step 2: Write `src/features/segmentation/schemas.ts`**

```typescript
import { z } from "zod";

export const ChartTypeSchema = z.enum(["pie", "bar", "metric"]);

export const ChartDataPointSchema = z.object({
  label: z.string(),
  value: z.number(),
});

export const ChartSpecSchema = z.object({
  id: z.string(),
  type: ChartTypeSchema,
  title: z.string(),
  data: z.array(ChartDataPointSchema).min(1),
  x_label: z.string().nullable(),
  y_label: z.string().nullable(),
  source_query: z.string(),
});

export type ChartType = z.infer<typeof ChartTypeSchema>;
export type ChartDataPoint = z.infer<typeof ChartDataPointSchema>;
export type ChartSpec = z.infer<typeof ChartSpecSchema>;
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/anddyagudelo/Documents/Dev/Local/cokit-templates
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add src/lib/env.ts src/features/segmentation/schemas.ts
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Add env validation and ChartSpec Zod schema"
```

---

### Task 18: CopilotKit runtime endpoint

**Files:**
- Create: `src/app/api/copilotkit/[[...slug]]/route.ts`

- [ ] **Step 1: Write `src/app/api/copilotkit/[[...slug]]/route.ts`**

```typescript
import {
  CopilotRuntime,
  createCopilotEndpoint,
  InMemoryAgentRunner,
} from "@copilotkit/runtime/v2";
import { LangGraphAgent } from "@copilotkit/runtime/langgraph";
import { handle } from "hono/vercel";

import { env } from "@/lib/env";

const defaultAgent = new LangGraphAgent({
  deploymentUrl: env.AGENT_URL,
  graphId: "segmentation_agent",
  langsmithApiKey: process.env.LANGSMITH_API_KEY ?? "",
});

const runtime = new CopilotRuntime({
  agents: { default: defaultAgent },
  runner: new InMemoryAgentRunner(),
  openGenerativeUI: true,
});

const app = createCopilotEndpoint({
  runtime,
  basePath: "/api/copilotkit",
});

export const GET = handle(app);
export const POST = handle(app);
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add src/app/api/copilotkit
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Add CopilotKit runtime endpoint targeting segmentation_agent"
```

---

### Task 19: Chart components (pie, bar, metric)

**Files:**
- Create: `src/features/segmentation/components/pie-chart.tsx`
- Create: `src/features/segmentation/components/bar-chart.tsx`
- Create: `src/features/segmentation/components/metric-card.tsx`

- [ ] **Step 1: Write `pie-chart.tsx`**

```tsx
"use client";
import {
  Cell,
  Legend,
  Pie,
  PieChart as RechartsPieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import type { ChartSpec } from "../schemas";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"];

export function PieChart({ chart }: { chart: ChartSpec }) {
  return (
    <div className="rounded-lg border border-[var(--border)] p-4 bg-[var(--background)]">
      <h3 className="font-semibold text-sm">{chart.title}</h3>
      <p className="text-xs text-gray-500 mb-2">{chart.source_query}</p>
      <ResponsiveContainer width="100%" height={280}>
        <RechartsPieChart>
          <Pie
            data={chart.data}
            dataKey="value"
            nameKey="label"
            cx="50%"
            cy="50%"
            outerRadius={90}
            label
          >
            {chart.data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </RechartsPieChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 2: Write `bar-chart.tsx`**

```tsx
"use client";
import {
  Bar,
  BarChart as RechartsBarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ChartSpec } from "../schemas";

export function BarChart({ chart }: { chart: ChartSpec }) {
  return (
    <div className="rounded-lg border border-[var(--border)] p-4 bg-[var(--background)]">
      <h3 className="font-semibold text-sm">{chart.title}</h3>
      <p className="text-xs text-gray-500 mb-2">{chart.source_query}</p>
      <ResponsiveContainer width="100%" height={280}>
        <RechartsBarChart data={chart.data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="label" label={chart.x_label ? { value: chart.x_label, position: "insideBottom", offset: -5 } : undefined} />
          <YAxis label={chart.y_label ? { value: chart.y_label, angle: -90, position: "insideLeft" } : undefined} />
          <Tooltip />
          <Legend />
          <Bar dataKey="value" fill="#3b82f6" />
        </RechartsBarChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 3: Write `metric-card.tsx`**

```tsx
"use client";
import type { ChartSpec } from "../schemas";

export function MetricCard({ chart }: { chart: ChartSpec }) {
  const point = chart.data[0];
  const formatted = new Intl.NumberFormat().format(point.value);
  return (
    <div className="rounded-lg border border-[var(--border)] p-6 bg-[var(--background)]">
      <p className="text-xs uppercase tracking-wide text-gray-500">{chart.title}</p>
      <p className="text-4xl font-bold mt-2">{formatted}</p>
      <p className="text-xs text-gray-500 mt-1">{chart.source_query}</p>
    </div>
  );
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add src/features/segmentation/components
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Add Recharts wrappers for pie, bar, metric chart types"
```

---

### Task 20: ChartCanvas + useSegmentationCharts hook

**Files:**
- Create: `src/features/segmentation/components/chart-canvas.tsx`
- Create: `src/hooks/use-segmentation-charts.tsx`

- [ ] **Step 1: Write `chart-canvas.tsx`**

```tsx
"use client";
import { useAgent } from "@copilotkit/react-core/v2";

import { ChartSpecSchema, type ChartSpec } from "../schemas";
import { BarChart } from "./bar-chart";
import { MetricCard } from "./metric-card";
import { PieChart } from "./pie-chart";

export function ChartCanvas() {
  const { agent } = useAgent();
  const rawCharts = (agent.state?.charts ?? []) as unknown[];

  const charts: ChartSpec[] = rawCharts
    .map((c) => {
      const result = ChartSpecSchema.safeParse(c);
      if (!result.success) {
        console.warn("Skipping invalid chart spec:", result.error.flatten());
        return null;
      }
      return result.data;
    })
    .filter((c): c is ChartSpec => c !== null);

  if (charts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center">
        <p className="text-lg font-medium">Ask me about your customers</p>
        <p className="text-sm text-gray-500 mt-2">
          Try: "Show me distribution by city for premium customers"
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {charts.map((chart) => {
        switch (chart.type) {
          case "pie":
            return <PieChart key={chart.id} chart={chart} />;
          case "bar":
            return <BarChart key={chart.id} chart={chart} />;
          case "metric":
            return <MetricCard key={chart.id} chart={chart} />;
        }
      })}
    </div>
  );
}
```

- [ ] **Step 2: Write `use-segmentation-charts.tsx`**

```tsx
"use client";
import { useDefaultRenderTool } from "@copilotkit/react-core/v2";

const HIDDEN_TOOL_RENDERS = new Set(["render_chart"]);

export function useSegmentationCharts() {
  // Render data tool calls inline as small text indicators; hide render_chart
  // because it has its own canvas display.
  useDefaultRenderTool({
    render: ({ name, status }) => {
      if (HIDDEN_TOOL_RENDERS.has(name)) return null;
      const label = name.replaceAll("_", " ");
      const dot = status === "complete" ? "✓" : "…";
      return (
        <div className="text-xs text-gray-500 italic">
          {dot} {label}
        </div>
      );
    },
  });
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add src/features/segmentation/components/chart-canvas.tsx src/hooks/use-segmentation-charts.tsx
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Add ChartCanvas and useSegmentationCharts hook"
```

---

### Task 21: page.tsx + layout.tsx

**Files:**
- Create: `src/app/layout.tsx`
- Create: `src/app/page.tsx`

- [ ] **Step 1: Write `src/app/layout.tsx`**

```tsx
import type { Metadata } from "next";

import { CopilotKit } from "@copilotkit/react-core";

import "./globals.css";

export const metadata: Metadata = {
  title: "Segmentation Explorer",
  description: "Conversational Zoho CRM segmentation",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <CopilotKit runtimeUrl="/api/copilotkit">{children}</CopilotKit>
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Write `src/app/page.tsx`**

```tsx
"use client";
import { CopilotChat } from "@copilotkit/react-core/v2";

import { ChartCanvas } from "@/features/segmentation/components/chart-canvas";
import { useSegmentationCharts } from "@/hooks/use-segmentation-charts";

export default function HomePage() {
  useSegmentationCharts();

  return (
    <div className="flex h-screen">
      <aside className="w-1/3 border-r border-[var(--border)] flex flex-col">
        <div className="p-4 border-b border-[var(--border)]">
          <h1 className="font-bold">Segmentation Explorer</h1>
          <p className="text-xs text-gray-500">Read-only Zoho CRM</p>
        </div>
        <div className="flex-1 overflow-y-auto">
          <CopilotChat input={{ disclaimer: () => null }} />
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto p-6">
        <ChartCanvas />
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add src/app/layout.tsx src/app/page.tsx
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Add root layout and home page wiring chat to chart canvas"
```

---

## Phase 4: Integration and docs

---

### Task 22: Frontend ↔ agent smoke test (placeholder Zoho creds)

This task verifies the chat UI talks to the agent end-to-end without depending on Zoho being reachable.

**Files:** none modified.

- [ ] **Step 1: Confirm `.env` has `OPENAI_API_KEY` set and Zoho placeholders present**

Open `.env`, verify `OPENAI_API_KEY` is real and Zoho vars are at minimum populated with placeholder strings (any non-empty value).

- [ ] **Step 2: Start the dev stack**

```bash
cd /Users/anddyagudelo/Documents/Dev/Local/cokit-templates
npm run dev
```

Wait for both processes to be ready (Next.js + LangGraph).

- [ ] **Step 3: Open the app**

Browser → `http://localhost:3000`. You should see:
- Left pane: chat interface with header "Segmentation Explorer"
- Right pane: "Ask me about your customers" empty state

- [ ] **Step 4: Send a chat message**

Type in the chat: `Hi, can you tell me what tools you have?`

Expected:
- Agent responds in 2-3 sentences listing roughly: customer queries, distributions, listing fields, rendering charts.
- Chart canvas remains in empty state (agent didn't call render_chart).

- [ ] **Step 5: Trigger a Zoho-hitting flow (will fail gracefully)**

Type: `How many premium customers do we have?`

Expected:
- Agent likely calls `query_customers` or `get_field_distribution`.
- The tool returns an error (placeholder Zoho creds → 401 / DNS failure).
- Agent says something like "I couldn't reach Zoho right now" — no fabricated counts.
- Audit log file appears in `agent/audit/zoho-audit-YYYY-MM-DD.jsonl` with an `error` entry.

If the agent fabricates a number, that's a system-prompt regression — re-read `system_prompt.py`.

- [ ] **Step 6: Stop the stack**

`Ctrl+C`.

- [ ] **Step 7: No commit** — verification only.

---

### Task 23: README with Zoho OAuth setup

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
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

Expected: 36 tests pass (audit, cache, client, query tools, render tool).
```

- [ ] **Step 2: Commit**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add README.md
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Add README with Zoho OAuth setup, troubleshooting, and roadmap"
```

---

### Task 24: End-to-end smoke test against real Zoho

This task is **manual and user-driven**. The user is the only one who can validate against their real Zoho data.

**Files:** none modified.

- [ ] **Step 1: Confirm real Zoho credentials are in `.env`**

Open `.env` and verify the 5 ZOHO_* values are real (not placeholders).

- [ ] **Step 2: Start the stack**

```bash
cd /Users/anddyagudelo/Documents/Dev/Local/cokit-templates
npm run dev
```

- [ ] **Step 3: Open the app and run the DoD checklist from the spec**

Browser → `http://localhost:3000`. Run each of these checks. Each must pass:

- [ ] **DoD #2**: Ask "How many [tier-name] customers do we have?" (substitute a real tier in your Zoho). Expected: a number from real Zoho within ~3 seconds.

- [ ] **DoD #3**: Ask "Show me distribution by city for [tier-name] customers." Expected: a pie or bar chart in the canvas with real city names.

- [ ] **DoD #4**: Verify `agent/audit/zoho-audit-$(date +%Y-%m-%d).jsonl` has entries for the queries you just ran:

  ```bash
  cat agent/audit/zoho-audit-$(date +%Y-%m-%d).jsonl | python -m json.tool --json-lines
  ```

- [ ] **DoD #5**: Stop the agent (`Ctrl+C`), restart it with `npm run dev`, and ask the same question — confirm Zoho is hit again (cache is per-session).

- [ ] **DoD #6**: Temporarily corrupt `ZOHO_REFRESH_TOKEN` in `.env`, restart agent, ask "How many customers?". Expected: agent replies "I couldn't reach Zoho" or similar, NOT a fabricated number. Audit log shows an error entry. Restore the real token after.

- [ ] **DoD #8**: In a 3-turn conversation about [tier-name] customers, confirm the agent **proactively suggests** at least one follow-up segment without you asking.

- [ ] **DoD #9**: Re-read `README.md` from a fresh perspective — could a teammate without context follow it to set up from zero? Adjust if any step is unclear.

- [ ] **Step 4: Run pytest one more time**

```bash
cd agent
source .venv/bin/activate
pytest -v
```

Expected: 36 tests pass.

- [ ] **Step 5: Commit any README adjustments from Step 3 last bullet, then push**

If you tweaked the README:

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates add README.md
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates commit -m "Polish README based on E2E walkthrough"
```

Push everything:

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates push
```

- [ ] **Step 6: Tag the F1 milestone**

```bash
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates tag -a f1-shipped -m "F1 Segmentation Explorer ready for use"
git -C /Users/anddyagudelo/Documents/Dev/Local/cokit-templates push origin f1-shipped
```

F1 is complete. Move on to specing F2 (Template Builder).
