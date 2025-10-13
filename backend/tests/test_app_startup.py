import pytest
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings
from app.main import create_app


def test_custom_cors_origins_are_applied():
    settings = Settings(
        _env_file=None,
        API_CORS_ORIGINS="https://app.example.com, https://admin.example.com",
        ENVIRONMENT="production",
        JWT_SECRET="prod-secret",
        APP_SECRET_KEY="prod-app-secret",
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


def test_local_environment_includes_default_cors_hosts():
    settings = Settings(
        _env_file=None,
        API_CORS_ORIGINS="http://localhost:5173",
        ENVIRONMENT="local",
    )

    app = create_app(settings=settings)

    cors_middleware = next(
        (middleware for middleware in app.user_middleware if middleware.cls is CORSMiddleware),
        None,
    )

    assert cors_middleware is not None
    assert cors_middleware.kwargs["allow_origins"] == [
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ]


def test_empty_string_cors_origins_does_not_crash():
    settings = Settings(
        _env_file=None,
        API_CORS_ORIGINS="",
        ENVIRONMENT="production",
        JWT_SECRET="prod-secret",
        APP_SECRET_KEY="prod-app-secret",
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

    settings = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        JWT_SECRET="prod-secret",
        APP_SECRET_KEY="prod-app-secret",
    )

    assert settings.API_CORS_ORIGINS == []


def test_blank_env_file_entry_is_treated_as_empty_list(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("API_CORS_ORIGINS=\n")

    settings = Settings(
        _env_file=env_file,
        ENVIRONMENT="production",
        JWT_SECRET="prod-secret",
        APP_SECRET_KEY="prod-app-secret",
    )

    assert settings.API_CORS_ORIGINS == []
