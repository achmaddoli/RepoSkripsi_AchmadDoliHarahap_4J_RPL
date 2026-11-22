# Repository Guidelines

## Project Overview

GeoKurir Malang compares PT Pos courier assignments with K-Means++ and HBCDP delivery zones. A Flask SPA ingests CSV/XLSX/XLS, preprocesses Malang addresses, geocodes them, evaluates the actual courier baseline, then runs user-requested clustering.

Work in this repository. Its Docker project is `geokurir-actual`, separate from the existing deployment in another directory. Do not edit that deployment or copy its `.env` or database. Source files in this checkout were restored from it; research documents and older alternate files remain outside the application pipeline.

## Architecture & Data Flow

- `app.py`: Flask page/API routes, upload/geocoding orchestration, clustering persistence, downloads. `templates/index.html` is the SPA shell; `js/app.js` owns browser state and requests.
- `services/preprocessing_service.py` preserves optional Petugas alongside each resi. `database/db.py` commits upload metadata, points, and history atomically.
- Geocoding stores WGS84 and projected meter coordinates on `data_pengiriman`. After geocoding, `ActualEvaluationService.evaluate(points)` calculates actual metrics; persistence completes before the geocoding response enables clustering.
- `evaluasi_aktual` has one current baseline per `id_dataset` with counts, distribution, nullable metrics, availability/reason, calculation time, and a content fingerprint. There is no separate geocoding-results table.
- Clustering requires a matching stored fingerprint and never recalculates actual metrics. K stays manual. Both algorithms use all SUCCESS points with complete coordinates, regardless of Petugas.
- `ActualEvaluationService.compare(points, km_labels, hb_labels, k)` evaluates existing assignments on the same Petugas-valid subset, without reclustering. No Petugas means actual N/A and algorithm-only evaluation on all points. Save comparison metrics in `hasil_clustering.evaluasi_perbandingan`; Z₂ and HBCDP steps remain full-set diagnostics.
- Timer scope: start of K-Means++ through completion of HBCDP; actual evaluation and subset comparison are outside it.

## Key Directories

- `services/`: preprocessing, geocoding, K-Means, HBCDP, and actual-evaluation logic.
- `database/`: connection helpers, fresh schema, incremental SQL under `migrations/`, optional seed examples.
- `templates/`, `js/`, `css/`: SPA views, state, Leaflet/SVG map rendering, responsive styling.
- `tests/`: unittest coverage, including actual metric edge cases and isolated PostgreSQL lifecycle/migration regressions.
- `referensi_jurnal/`, `hasil_pengujian/`: research/QA artifacts; preserve documents, notebooks, and dumps unless the task requires editing them.

## Development Commands

From this directory:

```sh
docker compose up -d --build
docker compose exec -T web python migrate.py up
docker compose exec -T web python migrate.py status
docker compose restart web
curl --fail http://127.0.0.1:5001/api/health
docker compose exec -T -e GEOKURIR_INTEGRATION_TESTS=1 web python -m unittest discover -s tests -v
```

Web startup runs `migrate.py up` automatically. `fresh` and `docker compose down -v` destroy data: never use them for an upgrade. Backend changes require a web restart with DEBUG=false. No configured lint/build pipeline beyond Docker was found; optional JavaScript syntax checks use `node --check js/app.js` and `node --check js/map.js`.

## Code Conventions & Common Patterns

Follow existing Python modules, Flask JSON responses (`success`, `data`, `error`), parameterized SQL, and connection context managers for commit/rollback. Keep metric computation in the new pure service, not route handlers or JavaScript.

Z₁ is population variance of group counts; algorithm subset evaluation retains empty groups up to K. Petugas names collapse whitespace but remain case-sensitive. Undefined metrics use SQL NULL / JSON null plus a reason, displayed as N/A; do not substitute zero. Changes to points/Petugas require geocoding/baseline refresh, while changes to K reuse the baseline.

Frontend uses async fetch and explicit shared state. Reset baseline/readiness when switching, cancelling, or deleting datasets. Escape user-provided values in HTML. Reuse Leaflet instances per container; replacing maps during transitions leaves stale callbacks.

## Important Files

- `services/actual_evaluation_service.py`: baseline, fingerprint, fair subset metrics.
- `database/migrations/001_actual_evaluation.sql`: additive baseline/Petugas/comparison schema changes.
- `database/01_schema.sql`, `migrate.py`: fresh schema and transactional versioned migrations.
- `docker-compose.yml`, `.env.example`, `config/config.py`: isolated runtime and configuration.
- `README.md`, `DEPLOYMENT.md`, `database/README.md`: workflows and schema details.

## Runtime/Tooling Preferences

Docker uses Python 3.13, pip with `requirements.txt`, and PostgreSQL 16. No npm/Bun build is required. Defaults bind localhost: web 5001, PostgreSQL 5433, Adminer 8081; internal database port is 5432. Volume: `geokurir-actual_postgres_data`.

Configure your own Google Maps key in `.env` for new-address geocoding. Missing keys produce failures, not simulated coordinates. Browser maps depend on external assets/tile providers; verify provider availability separately. Never commit secrets.

## Testing & QA

Use the Docker unittest command above. Integration classes create/drop temporary databases and require a PostgreSQL account with CREATE DATABASE privileges; never point ad-hoc fixture writes at the other deployment. No coverage percentage is configured.

Exercise real API and browser paths as well as tests: baseline visible and persisted before clustering, K different from actual courier count, partial/missing Petugas, reload/switch/delete state, shared-subset comparisons, exports, and mobile layout. Coordinate fixtures can isolate these checks from paid geocoding; label that limitation and remove QA datasets afterward.
