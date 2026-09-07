# QUASAR v2.0 Feature Manifest

Implemented in this package:

- Source provenance, confidence, station identity, freshness/staleness and evidence hashes.
- Entity resolution and cross-domain satellite/aircraft/vessel correlation.
- Risk scoring with corroboration, persistence and time-to-event inputs.
- Deduplicated anomaly emission with configurable cooldown.
- Alert lifecycle and incident/case workflow with timeline, assignment fields and evidence export.
- Task lifecycle, persistence, retry/offline queueing, priority, expiry and completion verification state.
- Watchlists and geofences.
- Historical replay through current rules/correlation engine.
- Config validation, version history and audit logging.
- SQLite local/offline mode plus PostgreSQL `DATABASE_URL` mode.
- IAM/JANUS-compatible RBAC and QUASAR service-key fallback.
- Authenticated ARGUS REST calls; QUASAR remains hardware-isolated.
- HERMES notification hook and severity routing.
- Health/readiness/metrics endpoints.
- Retention tiers for raw observations while incidents/reports remain durable.
- Network-wide station selection helper based on capability, visibility, load, link quality and priority.
- API v1 namespace plus legacy `/api` compatibility.
- Command dashboard additions for Incidents, Correlation Timeline, Watchlists and Replay.
- Automated core regression tests for emergency squawk transition, correlation, station selection and risk bounds.
