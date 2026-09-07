# UNG-QUASAR
## Quantified Universal Analytics, Signals & Reporting

QUASAR is the command-intelligence layer above ARGUS. ARGUS owns sensors, radios, RF collection, and real-time hardware-facing tracking. QUASAR consumes ARGUS REST data, fuses observations, correlates entities, detects patterns, creates incidents, keeps history, generates reports, and returns prioritization/tasking to ARGUS. QUASAR never touches hardware directly.

**Architecture:** `Hardware → ARGUS :8000 → QUASAR :8001 → command dashboard / UNG services`

## v2.0 capabilities

- Provenance, confidence, station/source identity, freshness, stale/lost-track state, and raw-event evidence hashes.
- Cross-domain correlation and entity resolution across satellites, aircraft, and vessels.
- Pattern detection with cooldown/deduplication, watchlists, geofences, risk scoring, and anomaly lifecycle.
- Incident/case workflow: NEW → ACKNOWLEDGED → INVESTIGATING → RESOLVED / DISMISSED, with timeline and evidence export.
- Task lifecycle: QUEUED → EXECUTING → COMPLETED / RETRYING / FAILED / EXPIRED, with offline retry and audit trail.
- Historical storage and replay mode for testing new rules against past observations.
- Readable intelligence reports with integrity hashes; scheduled/notification hooks via HERMES.
- IAM/JANUS-compatible authentication plus local service-key mode and RBAC (viewer, analyst, operator, commander, admin).
- SQLite for Pi/Mac local/offline operation; PostgreSQL via `DATABASE_URL` for cloud/Railway deployments.
- Health, readiness, metrics, audit, config versioning, station selection/failover scoring, retention controls.
- API versioning under `/v1/...` while preserving legacy `/api/...` endpoints used by the original dashboard.

## Core modules

- `fusion.py` — ARGUS ingestion, unified state, provenance/freshness.
- `correlation.py` — entity resolution, cross-feed correlation, risk scoring.
- `patterns.py` — anomaly detectors and lost-track detection.
- `incidents.py` — incident lifecycle and case handling.
- `history.py` — SQLite/PostgreSQL persistence, raw evidence, audit, tasks, reports.
- `reports.py` — intelligence summaries and integrity hashes.
- `tasking.py` — authenticated QUASAR → ARGUS task execution.
- `replay.py` — historical replay through current detection/correlation logic.
- `geofences.py` / `watchlists` API — zones and high-priority identities.
- `scheduling.py` — best-station selection by visibility, load, link quality, capability and priority.
- `security.py` — IAM/JANUS token introspection or service API key, RBAC.
- `health.py` — runtime health/collection status.
- `notifications.py` — HERMES notification integration.
- `evidence.py` — incident evidence bundles with SHA-256 integrity.
- `config.py` — typed validated configuration and deploy-safe environment overrides.
- `main.py` — FastAPI server, background fusion/detection/task-retry loops, API and dashboard.

## Start locally

```bash
cd quasar
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Open `http://localhost:8001`.

## Production security

Set `QUASAR_API_KEY` for service-key authentication or configure `IAM_BASE_URL` to use JANUS/IAM bearer-token introspection. Configure `ARGUS_API_KEY` so QUASAR signs its calls to ARGUS. Never expose ARGUS hardware endpoints directly to the public Internet. CORS is restricted by default and can be set with `QUASAR_CORS_ORIGINS`.

## Database modes

If `DATABASE_URL` is unset, QUASAR uses `data/quasar.db` (SQLite). If `DATABASE_URL` is a PostgreSQL URL, QUASAR creates and uses the PostgreSQL schema automatically. SQLite is the intended resilient Pi/Mac local mode; PostgreSQL is the intended Railway/cloud mode.

## Important API groups

- `/health`, `/ready`, `/v1/metrics`
- `/v1/picture`, `/v1/timeline`
- `/api/history/*` (legacy-compatible historical queries)
- `/v1/anomalies`, `/v1/incidents/*`, `/v1/incidents/{id}/evidence`
- `/v1/watchlists`, `/v1/geofences`, `/v1/replay`
- `/v1/reports/*`
- `/api/task/*`, `/v1/tasks`
- `/v1/stations/select`
- `/v1/config`, `/v1/config/versions`
- `/v1/audit`

## Safety boundary

QUASAR is a coordination, analysis, and tasking layer. It does not directly drive radios, SDRs, rotators, aircraft, vessels, satellites, or other hardware. ARGUS remains the hardware boundary. Any transmit-capable operations should remain disabled by default and only be enabled for authorized equipment/frequencies under the appropriate operational controls.
