# F1 — Segmentation Explorer (spec de diseño)

- **Proyecto**: Campaign Approval Flow (CopilotKit + LangGraph + Zoho CRM)
- **Fase**: F1 de 5
- **Fecha**: 2026-05-09
- **Estado**: Borrador pendiente de revisión del usuario
- **Repo**: `/Users/anddyagudelo/Documents/Dev/Local/cokit-templates`

> Versión en inglés: [`2026-05-09-f1-segmentation-explorer-design.md`](./2026-05-09-f1-segmentation-explorer-design.md)

## Resumen ejecutivo (TL;DR)

App local-only de Next.js + LangGraph (Python) donde un usuario de marketing
chatea con un agente de IA que consulta Zoho CRM en producción **solo lectura**,
genera charts de segmentaciones de clientes bajo demanda, y propone
proactivamente métricas adicionales. F1 NO incluye constructor de templates,
flujo de aprobación, ni envío de mensajes — eso es F2–F5.

## Contexto: dónde encaja F1

El sistema completo se descompone en 5 fases, cada una entregable de forma
independiente:

| # | Fase | Aporta | Integraciones |
|---|---|---|---|
| **F1** | **Segmentation Explorer** | **Exploración conversacional del CRM con charts** | **Zoho (read)** |
| F2 | Template Builder | Construir templates de WhatsApp (texto + variables + imagen header), preview en vivo | F1 + storage de imágenes |
| F3 | Approval Workflow | HITL Aprobar/Editar/Rechazar + log de auditoría | F2 + auth + DB de auditoría |
| F4 | Kapso Distribution | Al aprobar → Kapso CLI → Meta WABA, tracking de envío | F3 + Kapso + Meta WABA |
| F5 | Production Hardening | Auth multi-usuario, observabilidad, deploy, CI/CD | Infra |

Este spec cubre **solo F1**. Cada fase posterior tendrá su propio spec,
informado por las lecciones de F1.

## Objetivos (F1)

1. Permitir al usuario de marketing explorar datos de clientes de Zoho de forma
   conversacional sin escribir queries ni conocer el modelo de datos de Zoho.
2. Renderizar resultados como **charts** (pie, bar) o **metric cards**
   dinámicamente, inferidos del intent del query.
3. Que el agente **proponga proactivamente** segmentos/métricas adicionales que
   notó interesantes en los datos — no solo responder.
4. Establecer patrones CopilotKit + LangGraph reusables en F2–F5.

## No-objetivos (F1)

- ❌ Escribir a Zoho (read-only, sin excepciones)
- ❌ Construir templates de WhatsApp (F2)
- ❌ Flujos de aprobación / HITL (F3)
- ❌ Enviar mensajes o cualquier contacto con Kapso/Meta (F4)
- ❌ Auth multi-usuario (F5) — single-user local-only
- ❌ Infraestructura de deployment (F5)
- ❌ Persistir conversaciones entre sesiones
- ❌ UI de descubrimiento de campos custom de Zoho (solo vía tool)

## Reglas de safety en producción (no negociables)

F1 lee Zoho CRM de producción con PII real de clientes. Las siguientes son
obligatorias y enforced en código, no por convención:

| Riesgo | Mitigación |
|---|---|
| Escrituras accidentales | OAuth scope limitado a `ZohoCRM.modules.contacts.READ` (y equivalente para cualquier otro módulo usado). No existen tools de escritura. |
| Rate limiting | Toda llamada a Zoho pasa por `agent/src/zoho/client.py`. El client implementa rate limiter por minuto (default 90 req/min, deja margen bajo el límite típico de 100) y backoff exponencial en 429. |
| PII en context del LLM | Los tools de query a Zoho devuelven **agregados** por defecto (counts, distribuciones). Records individuales solo cuando el usuario explícitamente hace drill-down. Tools de tipo lista limitan a 50 records y nunca incluyen emails/teléfonos a menos que se pidan. |
| Audit trail | Cada llamada a Zoho escribe una línea JSONL en `./audit/zoho-audit-YYYY-MM-DD.jsonl` con `{ts, tool, params, fields_returned, record_count, latency_ms, status}`. |
| Outage del API | Los tools surface errores explícitos. El system prompt prohíbe al agente inventar data. Ante una falla de `query_customers`, el agente debe decir "no pude alcanzar Zoho ahora" — nunca fabricar counts. |
| Filtración de credenciales | `.env` está en `.gitignore`. `.env.example` documenta variables requeridas pero no contiene secrets. El README explica cómo cada usuario de marketing genera su propio refresh token de OAuth. |

## Arquitectura

### Modelo de despliegue

- **Local-only**. Cada usuario de marketing clona el repo, llena su `.env` con
  sus propias credenciales de Zoho, corre `npm install && npm run dev`.
- Sin backend compartido, sin DB compartida, sin cache compartido.
- Zoho RBAC enforza qué ve cada usuario (sus permisos personales en Zoho).
- F1 no tiene preocupaciones de multi-tenant.

### Stack

- **Frontend**: Next.js 16, React 19, Tailwind 4, CopilotKit `1.56.5`
  (`@copilotkit/react-core/v2`), Recharts (renderizado de charts).
- **Agente**: Python 3.12, LangGraph, `langchain-openai`, middleware de
  `copilotkit`, `httpx` (client de Zoho), `tenacity` (retry/backoff).
- **Modelo**: GPT-5.2-mini (barato para iterar; intercambiable vía env var).
- **Servidor de agente**: LangGraph dev server en **puerto 8124** (evita
  choque con cualquier template de referencia en 8123).

### Flujo de datos de alto nivel

```
Marketer escribe mensaje en chat
        ↓
CopilotKit /api/copilotkit (Next.js)
        ↓ (HTTP)
Agente LangGraph (puerto 8124)
        ↓
Agente decide: query_customers / get_field_distribution / list_custom_fields / render_chart
        ↓
zoho/client.py → API de Zoho (rate-limited, audited, cacheado por sesión)
        ↓
Tool retorna agregados → Command(update={...})
        ↓
StateStreamingMiddleware streamea estado parcial al frontend
        ↓
Frontend renderiza vía useComponent (chart) o mensaje en chat
```

## Estructura del repo

```
cokit-templates/
├── docs/
│   └── specs/
│       └── 2026-05-09-f1-segmentation-explorer-design.md   ← este archivo
├── src/                                    # Frontend Next.js
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                        # CopilotChat + canvas de charts
│   │   ├── globals.css
│   │   └── api/copilotkit/[[...slug]]/route.ts
│   ├── features/
│   │   └── segmentation/
│   │       ├── components/
│   │       │   ├── chart-canvas.tsx        # contenedor; lee agent state
│   │       │   ├── pie-chart.tsx           # wrapper de Recharts
│   │       │   ├── bar-chart.tsx           # wrapper de Recharts
│   │       │   └── metric-card.tsx         # display de un único número
│   │       ├── schemas.ts                  # schemas Zod
│   │       └── types.ts                    # tipos via z.infer
│   ├── hooks/
│   │   └── use-segmentation-charts.tsx     # registra renderers useComponent
│   ├── lib/
│   │   └── env.ts                          # validación Zod de env vars
│   └── components/ui/                      # UI primitivo (Button, Input)
├── agent/
│   ├── main.py                             # create_agent + middleware
│   ├── src/
│   │   ├── state.py                        # TypedDict de AgentState
│   │   ├── system_prompt.py                # constante SYSTEM_PROMPT
│   │   ├── tools/
│   │   │   ├── __init__.py                 # exporta lista de tools
│   │   │   ├── zoho_queries.py             # query_customers, get_field_distribution, list_custom_fields
│   │   │   └── chart_renderers.py          # render_chart
│   │   └── zoho/
│   │       ├── __init__.py
│   │       ├── client.py                   # httpx + OAuth refresh + rate limit
│   │       ├── audit.py                    # logger JSONL
│   │       └── cache.py                    # cache en memoria por sesión
│   ├── tests/
│   │   ├── test_zoho_client.py             # mockea Zoho con httpx_mock
│   │   ├── test_zoho_queries_tool.py       # comportamiento de tool con client mockeado
│   │   └── test_audit.py                   # audit escribe JSONL correcto
│   ├── audit/                              # gitignored; logs de auditoría runtime
│   │   └── .gitkeep
│   ├── langgraph.json
│   └── pyproject.toml
├── scripts/
│   ├── setup-agent.sh                      # uv venv + install
│   ├── setup-agent.bat
│   ├── run-agent.sh                        # langgraph dev --port 8124
│   └── run-agent.bat
├── .env.example
├── .gitignore                              # excluye .env, audit/, node_modules, .venv
├── package.json
├── postcss.config.mjs
├── next.config.ts
├── tsconfig.json
└── README.md                               # setup, instrucciones OAuth Zoho, límites
```

### Rationale de carpetas

| Decisión | Por qué |
|---|---|
| `src/features/segmentation/` en vez de `components/` flat | Screaming architecture; F2 agregará `src/features/templates/` independientemente. |
| `agent/src/zoho/` separado de `tools/` | Single responsibility: los tools expresan intent (`query_customers`), el client maneja transporte (auth, rate limit, audit). Los tools se pueden testear sin pegarle a Zoho. |
| Sin capa `domain/` en F1 | YAGNI — solo un storage (Zoho), sin target de swap todavía. El boundary de `zoho/client.py` ES la abstracción. |
| `audit/` fuera de `src/` | Artefactos de runtime, no código. Gitignored. |

## Modelo de datos

### `AgentState` (Python, `agent/src/state.py`)

```python
from langchain.agents import AgentState as BaseAgentState
from typing import TypedDict, Literal

ChartType = Literal["pie", "bar", "metric"]

class ChartSpec(TypedDict):
    id: str                      # uuid; permite al frontend mantener keys estables
    type: ChartType
    title: str
    data: list[dict]             # [{label: str, value: number}, ...] para pie/bar
                                 # [{label: str, value: number}] de longitud 1 para metric
    x_label: str | None
    y_label: str | None
    source_query: str            # descripción human-readable: "Clientes por ciudad, tier premium"

class AgentState(BaseAgentState):
    charts: list[ChartSpec]      # charts renderizados en esta sesión, append-only
    last_segment_filter: dict | None  # últimos filtros usados; útil para "y desglosado por ciudad"
```

`charts` es append-only dentro de una sesión. El frontend renderiza todos
apilados. El usuario descarta charts individuales vía UI (state solo del
frontend).

### Mirror Zod (`src/features/segmentation/schemas.ts`)

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

El frontend valida cada chart spec que llega del agent state vía
`ChartSpecSchema.safeParse()` antes de renderizar. Specs inválidos se loguean
y se saltan (sin crashear).

## Tools del agente (F1)

### `query_customers(filters, limit=50)`

Devuelve records de clientes o count agregado, dependiendo de cómo se llame.

```python
@tool
def query_customers(
    filters: dict,           # {"tier": "premium", "city": "Bogota"}
    limit: int = 50,
    fields: list[str] | None = None,  # default: mínimo — id, name solamente
    runtime: ToolRuntime = ...,
) -> dict:
    """
    Consulta contactos de Zoho que matchean `filters`. Por defecto devuelve
    solo id+name (no PII). Pasa `fields` para pedir más, pero SOLO cuando el
    usuario explícitamente hace drill-down sobre records individuales.

    Returns: {"count": int, "records": [...]}.
    """
```

**Restricciones:**
- Pagina internamente siempre; surface errores claros si el set de filtros
  es muy grande.
- `fields` por defecto excluye email, phone, address. El system prompt
  enforza normas de drill-down.
- Rate-limited y auditado vía `zoho/client.py`.

### `get_field_distribution(field, filters=None)`

Devuelve distribución agregada de `field` sobre el set (filtrado) de clientes.

```python
@tool
def get_field_distribution(
    field: str,                  # "city", "tier", "subscription_status", ...
    filters: dict | None = None,
    runtime: ToolRuntime = ...,
) -> dict:
    """
    Agrupa clientes por `field` y devuelve counts por bucket.
    Returns: {"field": str, "buckets": [{"label": str, "count": int}, ...], "total": int}.
    """
```

**Por qué un tool separado de `query_customers`:** la distribución es el query
analítico más común y se beneficia de un response shape estructurado que mapea
limpio a chart data. Evita que el LLM haga agregaciones a mano.

### `list_custom_fields(module="Contacts")`

Devuelve el schema de campos disponibles en un módulo de Zoho. El agente lo
llama **antes** de proponer segmentos para no alucinar nombres de campos.

```python
@tool
def list_custom_fields(
    module: str = "Contacts",
    runtime: ToolRuntime = ...,
) -> list[dict]:
    """
    Returns: [{"api_name": str, "display_name": str, "type": str, "picklist_values": [...] | None}, ...]
    Cache: TTL de 1h — el schema rara vez cambia.
    """
```

### `render_chart(type, title, data, x_label=None, y_label=None, source_query)`

El único tool que "toca" el frontend. Hace append de un `ChartSpec` a
`state.charts`.

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
    Renderiza `data` como un chart de tipo `type` en el canvas. Llamar
    DESPUÉS de tener data de un tool de query; nunca inventes la data.

    `source_query`: descripción human-readable de qué se consultó, usada en
    el subtítulo del chart para que el usuario sepa qué está viendo.
    """
```

Devuelve `Command(update={"charts": [..., new_chart]})`.

### Por qué este split (data vs render)

En mi-cokit, `query_data` y el rendering de charts son dos conceptos separados
(un tool de backend, un registro de `useComponent`). F1 sigue el mismo split:

- **Tools de data** (`query_customers`, `get_field_distribution`,
  `list_custom_fields`) saben de Zoho. No saben de UI.
- **Tool de render** (`render_chart`) sabe de UI. No sabe de Zoho.

Esto mantiene cada tool testeable de forma aislada y hace que agregar nuevos
tipos de render en F2+ sea trivial.

## Client de Zoho (`agent/src/zoho/client.py`)

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
                # Backoff y retry una vez vía tenacity
                ...
            self._audit.log_error(path, params, e)
            raise

        latency = (time.monotonic() - t0) * 1000
        self._audit.log_success(path, params, data, latency_ms=latency)

        if cache_key:
            self._cache.set(cache_key, data, ttl_seconds=300)
        return data
```

Puntos clave del diseño:

1. **Chokepoint único**: cada llamada HTTP a Zoho pasa por `get()`. Fácil de
   instrumentar, mockear, intercambiar.
2. **Inyección por constructor**: `audit` y `cache` se inyectan — los tests
   pasan fakes.
3. **OAuth refresh interno**: el agente nunca ve los access tokens. Refresh
   token desde env, access token cacheado en memoria con TTL de 1 hora.
4. **Sin métodos de escritura**: no hay `post()`, `put()`, ni `delete()` a
   propósito. Agregar escritura requiere un cambio de código revisable en PR.

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

### Hook `useSegmentationCharts`

Registra componentes de generative UI controlled. El agente renderiza charts
llamando al tool `render_chart`, que streamea un `ChartSpec` a `state.charts`.
El hook también registra los renderers de `useComponent` para chart cards
inline en chat (opcional — se puede deferir).

### `ChartCanvas`

Lee `agent.state.charts`, valida cada uno vía Zod, renderiza por `type`:
`pie` → `<PieChart>`, `bar` → `<BarChart>`, `metric` → `<MetricCard>`.

Empty state: mensaje amable *"Pregúntame sobre tus clientes — prueba 'muéstrame
distribución por ciudad para clientes premium'."*

## Outline del system prompt

El prompt completo vive en `agent/src/system_prompt.py`. Reglas clave (el
prompt SE MANTIENE EN INGLÉS porque va literalmente al LLM y el original fue
afinado en inglés; traducirlo cambiaría la instrucción que recibe el agente):

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

> Nota: la última regla "Use the user's language" hace que el agente le
> responda al usuario en español si este escribe en español. La instrucción
> al modelo se queda en inglés; la respuesta del agente al marketer es
> bilingüe.

## Patrones de CopilotKit usados en F1

| Patrón | Dónde | Por qué |
|---|---|---|
| `useAgent()` + `agent.state` | `ChartCanvas` | Lee state agent-side (`charts`) reactivamente. |
| `useComponent(...)` | `useSegmentationCharts` | Registra renderers de charts como controlled generative UI. |
| `StateStreamingMiddleware` | `agent/main.py` | Streamea updates de `charts` mientras corre `render_chart`. |
| `CopilotKitMiddleware` | `agent/main.py` | Conecta state de LangGraph con runtime de CopilotKit. |
| MCP / `useFrontendTool` | **NO usado en F1** | No se necesitan tools frontend-only. |
| `useHumanInTheLoop` | **NO usado en F1** | HITL es F3. |

## Definition of Done (F1)

F1 está completo cuando:

1. ✅ Un usuario de marketing puede correr `npm install && npm run dev` desde
   un clone limpio con un `.env` poblado, y llegar a `http://localhost:3000`.
2. ✅ Preguntar "¿cuántos clientes premium tenemos?" devuelve un número desde
   Zoho real (no mockeado) en menos de 3 segundos.
3. ✅ Preguntar "muéstrame distribución por ciudad para clientes premium"
   produce un pie o bar chart en el canvas con data real.
4. ✅ Cada llamada al API de Zoho aparece en
   `agent/audit/zoho-audit-YYYY-MM-DD.jsonl`.
5. ✅ Reiniciar el agente y hacer la misma pregunta vuelve a pegarle a Zoho
   (los caches son por-sesión, no persistentes).
6. ✅ Matar la conectividad a Zoho (ej: revocar token temporalmente) resulta
   en un mensaje claro de "no pude alcanzar Zoho" — sin data fabricada.
7. ✅ Suite de tests pasa: `pytest agent/tests/`.
8. ✅ El agente sugiere proactivamente un segmento de seguimiento al menos
   una vez en una conversación de 3 turnos sobre clientes premium.
9. ✅ El README documenta cómo obtener un refresh token de OAuth de Zoho
   end-to-end.

## Preguntas abiertas / decisiones diferidas

| # | Pregunta | Default si no se responde |
|---|---|---|
| O1 | Tamaño del equipo de marketing & timeline | Asumido: equipo pequeño (≤5), sin deadline duro. Afecta solo a F5. |
| O2 | Módulos específicos de Zoho usados (¿solo Contacts? ¿Deals? ¿Custom modules?) | Asumido: Contacts es primario en F1. El spec se extiende si el usuario clarifica diferente durante implementación. |
| O3 | Convenciones de naming de campos custom en su Zoho | Descubrible vía `list_custom_fields` — manejado en runtime. |
| O4 | ¿Debería ser exportable la data de los charts (CSV)? | Fuera de scope F1. Agregar al backlog de F2 si se solicita. |
| O5 | Internacionalización (UI en español) | El system prompt espeja el idioma del usuario. Strings de frontend: inglés en F1, se puede localizar después. |
| O6 | Loguear tool calls además del audit (para debugging) | Integración con LangSmith deferida hasta F3 (audit necesita centralización). |

## Fuera de scope (explícitamente)

Esto **no** es F1 — agregarlo es scope creep:

- Guardar/cargar sesiones de charts
- Compartir charts con otros usuarios (no hay usuarios todavía)
- Dashboards customizables
- UI de query builder tipo SQL
- Edición directa de campos de Zoho
- Cualquier integración con email/Slack
- Importar/exportar listas de clientes

## Referencias

- Template de referencia mi-cokit: `/Users/anddyagudelo/Documents/Dev/Local/copilot-kit-practice/mi-cokit/`
- Patrón de chart en mi-cokit: `src/components/generative-ui/charts/` y
  `src/hooks/use-generative-ui-examples.tsx` — F1 reusa este enfoque para
  pie/bar.
- Patrón de `StateStreamingMiddleware` en mi-cokit: `agent/main.py` líneas 24–28.
- Docs del API Zoho CRM v6: https://www.zoho.com/crm/developer/docs/api/v6/
- Docs CopilotKit v2: https://docs.copilotkit.ai/

## Siguiente paso después de aprobar el spec

Invocar `superpowers:writing-plans` para crear un plan de implementación
faseado dividido en paquetes de trabajo `P1.1` … `P1.N`, cada uno testeable
de forma independiente.
