# TERM Bridge

TERM Bridge connects serial HMPD thermostat controllers to Home Assistant. It
discovers enabled zones, publishes them as MQTT climate entities, keeps their
state synchronized, and sends target-temperature changes back to each controller.

## Features

- Multiple independent serial controllers
- Home Assistant MQTT climate discovery
- Per-controller command queues with retry and backoff
- MQTT username/password and TLS support
- Server CA validation and optional client certificates
- Persistent, installation-specific MQTT client identity
- Retained availability and structured health diagnostics
- One Home Assistant connectivity sensor per serial controller
- Automatic retained-topic cleanup for removed and renamed zones
- Strict startup configuration validation
- Rotating debug logs

## Installation

1. Add `https://github.com/domin211/term-bridge` as a Home Assistant add-on repository.
2. Install **TERM Bridge**.
3. Configure MQTT and the attached serial controllers.
4. Start the add-on.

## Configuration

| Option | Description | Default |
| --- | --- | --- |
| `debug` | Enable verbose logs and `/config/term_bridge.log` | `false` |
| `mqtt_host` | MQTT broker hostname | `core-mosquitto` |
| `mqtt_port` | MQTT broker port | `1883` |
| `mqtt_username` | MQTT username | empty |
| `mqtt_password` | MQTT password | empty |
| `mqtt_tls` | Enable TLS | `false` |
| `mqtt_tls_ca` | CA certificate bundle path | empty/system CAs |
| `mqtt_tls_cert` | Optional client certificate path | empty |
| `mqtt_tls_key` | Optional client private-key path | empty |
| `hmpd_path` | HMPD controller executable | `/app/hmpd` |
| `controllers` | Serial controller definitions | example USB controllers |

Certificate files can be stored under `/config`, which is writable and persistent.
Hostname and certificate validation are always enforced. When client authentication
is used, both `mqtt_tls_cert` and `mqtt_tls_key` are required.

Each controller requires:

```yaml
- name: main
  dev: /dev/ttyUSB0
  baud: 4800
  expected_regs: 64
```

TERM Bridge rejects malformed JSON, invalid ports, invalid TLS combinations,
duplicate controller identities, empty controller lists, and non-positive serial
settings before connecting to hardware or MQTT.

## MQTT

The default topic root is `term_bridge`.

Each zone is represented as a single-entity device, so Home Assistant displays
the room name once rather than repeating it as both the device and entity name.

| Topic | Purpose |
| --- | --- |
| `term_bridge/<zone>/state` | Retained zone state |
| `term_bridge/<zone>/set_target` | Target-temperature command |
| `term_bridge/bridge/status` | Retained `online`/`offline` availability |
| `term_bridge/bridge/health` | Retained structured health document |
| `term_bridge/bridge/resync` | Request a full controller resync |

The health document includes MQTT connection state, uptime, discovered zone count,
queue state, and the last successful temperature/register sync for each controller.

Each configured controller also creates a diagnostic connectivity binary sensor.
It reports `online` after a successful controller synchronization and `offline`
after all retries for a temperature or register request fail.

Each installation stores a random identity in `/data/term_bridge_instance_id`.
This gives every instance a stable MQTT client ID and prevents instances from
disconnecting each other.

## Options export and transfer

The bundled helper validates and exports an options file while adding any newly
introduced defaults:

```bash
python /app/options_tool.py \
  --source /data/options.json \
  --output /config/term-bridge-options.json
```

Add `--redact-secrets` when the output is intended for diagnostics rather than
direct import. Exported files are written with owner-only permissions on Linux.

## Development

```text
term_bridge/app/
  main.py
  options_tool.py
  term_bridge/
    bridge.py
    config.py
    hmpd_cli.py
    models.py
    queue.py
    topics.py
  tests/
```

Run the checks:

```bash
cd term_bridge/app
pip install --require-hashes -r requirements.txt
pip install -r requirements-dev.txt
ruff check .
mypy
pytest
```

The MQTT integration test starts a disposable Eclipse Mosquitto container when
`RUN_MQTT_INTEGRATION=1` and Docker is available:

```bash
RUN_MQTT_INTEGRATION=1 pytest -m integration
```

Build the Home Assistant add-on image:

```bash
docker build -t term-bridge-add-on term_bridge
```

Unit and MQTT tests do not exercise physical serial controllers. Hardware-facing
changes should be verified through at least one complete synchronization cycle.

## Troubleshooting

- Enable `debug: true` and inspect `/config/term_bridge.log`.
- Subscribe to `term_bridge/bridge/health`.
- Confirm the MQTT hostname, port, credentials, and certificate paths.
- Confirm each serial device exists and is accessible.
- Confirm `hmpd_path` points to an executable HMPD binary.

## Security and long-term operation

TERM Bridge uses Home Assistant's default AppArmor protection, protection mode, an
add-on-specific configuration mount, a digest-pinned supported base image, hashed
runtime dependencies, immutable CI actions, dependency auditing, CodeQL, and
container vulnerability scanning. See [SECURITY.md](SECURITY.md) for the deployment
baseline.

Automated checks reduce maintenance effort but cannot eliminate it. Apply Home
Assistant and TERM Bridge security updates and review automated alerts at least
quarterly.
