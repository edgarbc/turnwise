from pathlib import Path

import pytest

from turnwise.settings import Settings


def test_loads_jev_credentials_and_default_model_from_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("TYPESAFE_API_KEY=jev-test-key\n")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("JEV_MODEL", raising=False)

    provider = Settings.load(env_file).for_provider("jev")

    assert provider.model == "jev-1.13.0"
    assert provider.api_key == "jev-test-key"


def test_process_environment_overrides_dotenv_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=file-key\nOPENAI_MODEL=file-model\n")
    monkeypatch.setenv("OPENAI_API_KEY", "process-key")
    monkeypatch.setenv("OPENAI_MODEL", "process-model")

    provider = Settings.load(env_file).for_provider("openai")

    assert provider.api_key == "process-key"
    assert provider.model == "process-model"


def test_missing_credentials_name_the_required_variable() -> None:
    with pytest.raises(ValueError, match="TYPESAFE_API_KEY"):
        Settings().for_provider("jev")


def test_openai_requires_an_explicit_model() -> None:
    settings = Settings(openai_api_key="openai-test-key", openai_model=None)

    with pytest.raises(ValueError, match="OPENAI_MODEL"):
        settings.for_provider("openai")


def test_secrets_are_not_in_object_representations() -> None:
    settings = Settings(typesafe_api_key="secret-value")
    provider = settings.for_provider("jev")

    assert "secret-value" not in repr(settings)
    assert "secret-value" not in repr(provider)