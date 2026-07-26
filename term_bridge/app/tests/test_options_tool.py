import json

from options_tool import prepare_options, write_export


def test_prepare_options_adds_new_defaults(tmp_path):
    source = tmp_path / "old-options.json"
    source.write_text(
        json.dumps(
            {
                "mqtt_host": "broker",
                "mqtt_port": 1883,
                "hmpd_path": "/app/hmpd",
                "controllers": [{"name": "main", "dev": "/dev/ttyUSB0", "baud": 4800, "expected_regs": 10}],
            }
        ),
        encoding="utf-8",
    )

    migrated = prepare_options(str(source))

    assert migrated["mqtt_tls"] is False
    assert migrated["mqtt_tls_ca"] == ""


def test_export_can_redact_password(tmp_path):
    source = tmp_path / "options.json"
    output = tmp_path / "export.json"
    source.write_text(
        json.dumps(
            {
                "mqtt_host": "broker",
                "mqtt_password": "secret",
                "controllers": [{"name": "main", "dev": "/dev/ttyUSB0", "baud": 4800, "expected_regs": 10}],
            }
        ),
        encoding="utf-8",
    )

    write_export(prepare_options(str(source), redact_secrets=True), str(output))

    assert json.loads(output.read_text(encoding="utf-8"))["mqtt_password"] == "<redacted>"
