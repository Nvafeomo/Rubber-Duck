from rubberduck.cli import _settings


def test_settings_use_current_flash_default(monkeypatch):
    monkeypatch.delenv("RUBBERDUCK_MODEL", raising=False)

    assert _settings(None, 400).model == "gemini-3.8-flash"


def test_settings_allow_model_override(monkeypatch):
    monkeypatch.setenv("RUBBERDUCK_MODEL", "custom-model")

    assert _settings(None, 400).model == "custom-model"
    assert _settings("cli-model", 400).model == "cli-model"
