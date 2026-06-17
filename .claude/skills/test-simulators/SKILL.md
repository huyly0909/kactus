---
name: test-simulators
description: Run integration tests for simulators — upload files, submit SYNC+ASYNC+DSS, verify results match
---

# Test Simulators

Test one or all simulators against the live Docker containers.

Usage: `/test-simulators` (all) or `/test-simulators $ARGUMENTS` (specific: eplus, hem, sap10, phpp, radiance, sbem, uvalue)

## How to Run

### Pytest (recommended)

```bash
# All simulators × 3 modes (sync, async, dss) + parallel tests
uv run pytest -m integration

# Specific simulator
uv run pytest -m "integration and sap10"
uv run pytest -m "integration and energyplus"

# Skip slow simulators (radiance, phpp, sbem)
uv run pytest -m "integration and not slow"
```

### Verify script (quick environment check inside code-server)

```bash
docker exec -u abc uso-code-server bash /opt/.usonia/docker-hub/scripts/dss/verify.sh
```

## Setup

- Container: `uso-simulators` on `localhost:3026`
- Base URL: `http://localhost:3026/api/projects/@1/simulations/documents/1`
- Example files: `docs/simulators/{name}/`
- SBEM test data: `packages/usonia-sbem/data/`
- Integration tests: `packages/usonia-simulators/tests/integration/`

## For each simulator:

1. Upload real example files (not empty/dummy files)
2. Submit task in **SYNC** mode
3. Submit task in **ASYNC** mode (poll until complete)
4. Submit task in **DSS** mode (poll until complete)
5. **Verify actual result data matches** between all 3 modes
6. Compare against expected values

## Expected Results

| Simulator | Upload | Expected Output |
|-----------|--------|----------------|
| **eplus** | IDF + EPW | 17 output files |
| **hem** | project JSON + EPW | 8760 rows, HTC=45.36, HLP=1.51 |
| **sap10** | inputs JSON | SAP=75.23, EI=68.07 |
| **phpp** | XLSX + input JSON | status=success |
| **radiance** | .mat + .rad files | 2 output figures, rtrace data |
| **sbem** | .inp file | 22 output files |
| **uvalue** | API: material + construction + layer | U-value=3.3348 |

## Key Gotchas

- UValue layers endpoint requires `material_id` (not just `conductivity`)
- EPlus/Radiance files default to `user_id=1` regardless of form param
- HEM polls via `GET /tasks/detail?user_id=X&version=Y` (no per-ID endpoint)
- PHPP polls via `GET /tasks/detail?user_id=X&version=Y`
- SBEM submit body needs `file_id` from upload response
- Radiance sync can take >60s (ray-tracing computation)
