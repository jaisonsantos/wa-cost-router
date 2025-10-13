import pytest
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings
from app.main import create_app


def test_custom_cors_origins_are_applied():
    settings = Settings(
        _env_file=None,
        API_CORS_ORIGINS="https://app.example.com, https://admin.example.com",
        ENVIRONMENT="production",
    )

    app = create_app(settings=settings)

    cors_middleware = next(
        (middleware for middleware in app.user_middleware if middleware.cls is CORSMiddleware),
        None,
    )

    assert cors_middleware is not None
    assert cors_middleware.kwargs["allow_origins"] == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


def test_empty_string_cors_origins_does_not_crash():
    settings = Settings(
        _env_file=None,
        API_CORS_ORIGINS="",
        ENVIRONMENT="production",
    )

    app = create_app(settings=settings)

    cors_middleware = next(
        (middleware for middleware in app.user_middleware if middleware.cls is CORSMiddleware),
        None,
    )

    assert cors_middleware is not None
    assert cors_middleware.kwargs["allow_origins"] == []


def test_blank_env_variable_is_treated_as_empty_list(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_CORS_ORIGINS", "")

    settings = Settings(_env_file=None, ENVIRONMENT="production")

    assert settings.API_CORS_ORIGINS == []


def test_blank_env_file_entry_is_treated_as_empty_list(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("API_CORS_ORIGINS=\n")

    settings = Settings(_env_file=env_file, ENVIRONMENT="production")

    assert settings.API_CORS_ORIGINS == []
