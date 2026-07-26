from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]


def test_home_assistant_default_apparmor_stays_enabled():
    config = (APP_ROOT / "config.yaml").read_text(encoding="utf-8")
    assert "apparmor: true" in config
    assert not (APP_ROOT / "apparmor.txt").exists()


def test_changelog_matches_app_version():
    config = (APP_ROOT / "config.yaml").read_text(encoding="utf-8")
    changelog = (APP_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert 'version: "5.1.4"' in config
    assert "## 5.1.4" in changelog
