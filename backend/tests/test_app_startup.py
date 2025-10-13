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
