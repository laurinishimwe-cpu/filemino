from app.core.config import Settings


def test_settings_load_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "Test FluxFile")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("CORS_ORIGINS", '["https://frontend.example"]')

    settings = Settings()

    assert settings.app_name == "Test FluxFile"
    assert settings.debug is True
    assert settings.cors_origins == ["https://frontend.example"]
