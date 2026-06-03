import unittest
from mcpuniverse.common.context import Context
from mcpuniverse.llm.aaaapi import AAAAPIModel
from mcpuniverse.llm.manager import ModelManager


class TestModelManager(unittest.TestCase):
    def test(self):
        manager = ModelManager()
        model = manager.build_model("openai", config={"model_name": "gpt-4o-mini"})
        self.assertIsNotNone(model)
        self.assertEqual(model.config.model_name, "gpt-4o-mini")

    def test_aaaapi_provider_registration(self):
        manager = ModelManager()
        model = manager.build_model(
            "aaaapi",
            config={
                "model_name": "deepseek-v3.1",
                "api_key": "test-key",
                "base_url": "https://example.test/v1",
            },
        )

        self.assertIsInstance(model, AAAAPIModel)
        self.assertEqual(model.config.model_name, "deepseek-v3.1")
        self.assertEqual(model.config.base_url, "https://example.test/v1")

    def test_aaaapi_context_updates_api_settings(self):
        model = AAAAPIModel(config={"model_name": "test-model"})

        model.set_context(Context(env={
            "AAAAPI_API_KEY": "context-key",
            "AAAAPI_BASE_URL": "https://context.example/v1",
        }))

        self.assertEqual(model.config.api_key, "context-key")
        self.assertEqual(model.config.base_url, "https://context.example/v1")


if __name__ == "__main__":
    unittest.main()
