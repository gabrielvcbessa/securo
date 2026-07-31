import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _production_settings(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "secret_key": "a" * 64,
        "frontend_url": "https://securo.example.com",
        "database_url": "postgresql+asyncpg://securo:strong@db:5432/securo",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_settings_accept_independent_secrets_and_https():
    settings = _production_settings()
    assert settings.app_env == "production"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("secret_key", "short"),
        ("frontend_url", "http://192.168.1.20:3000"),
        (
            "database_url",
            "postgresql+asyncpg://postgres:postgres@db:5432/securo",
        ),
    ],
)
def test_production_settings_reject_insecure_defaults(field, value):
    with pytest.raises(ValidationError):
        _production_settings(**{field: value})
