from app.core.config import Settings, get_settings


def test_settings_load_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "Test FileMino")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("CORS_ORIGINS", '["https://frontend.example"]')

    settings = Settings()

    assert settings.app_name == "Test FileMino"
    assert settings.debug is True
    assert settings.cors_origins == ["https://frontend.example"]


def test_get_settings_creates_temp_directory(monkeypatch, tmp_path) -> None:
    scratch = tmp_path / "nested" / "scratch"
    monkeypatch.setenv("TEMP_DIRECTORY", str(scratch))
    get_settings.cache_clear()
    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.temp_directory == scratch
    assert scratch.is_dir()
