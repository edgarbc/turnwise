import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from turnwise.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_loads_jev_credentials_and_default_model_from_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("TYPESAFE_API_KEY=jev-test-key\n")

            with patch.dict(os.environ, {}, clear=True):
                settings = Settings.load(env_file)

        provider = settings.for_provider("jev")
        self.assertEqual(provider.model, "jev-latest")
        self.assertEqual(provider.api_key, "jev-test-key")

    def test_process_environment_overrides_dotenv_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "OPENAI_API_KEY=file-key\nOPENAI_MODEL=file-model\n"
            )

            with patch.dict(
                os.environ,
                {"OPENAI_API_KEY": "process-key", "OPENAI_MODEL": "process-model"},
                clear=True,
            ):
                settings = Settings.load(env_file)

        provider = settings.for_provider("openai")
        self.assertEqual(provider.api_key, "process-key")
        self.assertEqual(provider.model, "process-model")

    def test_missing_credentials_name_the_required_variable(self) -> None:
        settings = Settings()

        with self.assertRaisesRegex(ValueError, "TYPESAFE_API_KEY"):
            settings.for_provider("jev")

    def test_openai_requires_an_explicit_model(self) -> None:
        settings = Settings(openai_api_key="openai-test-key")

        with self.assertRaisesRegex(ValueError, "OPENAI_MODEL"):
            settings.for_provider("openai")

    def test_secrets_are_not_in_object_representations(self) -> None:
        settings = Settings(typesafe_api_key="secret-value")
        provider = settings.for_provider("jev")

        self.assertNotIn("secret-value", repr(settings))
        self.assertNotIn("secret-value", repr(provider))


if __name__ == "__main__":
    unittest.main()