import unittest
from markitdown_service.llm_factory import LLMConfig, extract_llm_config_from_headers


class TestLLMFactory(unittest.TestCase):
    def test_extract_llm_config_from_headers(self):
        headers = {
            "X-LLM-Api-Key": "test-key-123",
            "X-LLM-Base-Url": "https://custom-ai.endpoint/v1",
            "X-LLM-Model": "gemini-2.0-flash",
            "X-LLM-Prompt": "Custom OCR Prompt",
        }
        config = extract_llm_config_from_headers(headers)
        self.assertEqual(config.api_key, "test-key-123")
        self.assertEqual(config.base_url, "https://custom-ai.endpoint/v1")
        self.assertEqual(config.model, "gemini-2.0-flash")
        self.assertEqual(config.prompt, "Custom OCR Prompt")
        self.assertTrue(config.has_client)

    def test_extract_empty_headers(self):
        headers = {}
        config = extract_llm_config_from_headers(headers)
        self.assertEqual(config.model, "gpt-4o")
        self.assertFalse(config.has_client)
        self.assertIsNone(config.create_client())


if __name__ == "__main__":
    unittest.main()

