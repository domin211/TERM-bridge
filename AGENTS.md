# Agent instructions

## Commands

From the repository root:

```bash
docker build -t term-bridge-add-on term_bridge
```

From `term_bridge/app`:

```bash
pip install --require-hashes -r requirements.txt
pip install -r requirements-dev.txt
ruff check .
mypy
python -m pip_audit --require-hashes -r requirements.txt
pytest
RUN_MQTT_INTEGRATION=1 pytest -m integration
```

The integration test requires a running Docker daemon and creates a disposable
Mosquitto container.

## Important files

- Add-on metadata and schema: `term_bridge/config.yaml`
- Container build: `term_bridge/Dockerfile`
- AppArmor policy: `term_bridge/apparmor.txt`
- Entrypoint: `term_bridge/app/main.py`
- Options transfer helper: `term_bridge/app/options_tool.py`
- Application package: `term_bridge/app/term_bridge/`
- Tests: `term_bridge/app/tests/`

## Runtime contracts

- Add-on options are read from `/data/options.json`.
- The stable installation identity is stored at `/data/term_bridge_instance_id`.
- The HMPD executable defaults to `/app/hmpd`.
- Debug logs use `/config/term_bridge.log`.
- MQTT defaults to the `term_bridge` topic root.
- Every controller publishes a retained connectivity sensor and health state.
- Certificate files can be mounted from `/config`.
- The HMPD executable's command-line and output formats are external hardware
  contracts. Do not change them without hardware verification.
- Tests cover deterministic logic and MQTT interoperability, but not physical
  serial controllers.
