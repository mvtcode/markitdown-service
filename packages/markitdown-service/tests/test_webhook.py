import hashlib
import hmac
import unittest
from markitdown_service.queue.webhook import generate_hmac_signature


class TestWebhookSecurity(unittest.TestCase):
    def test_hmac_signature_generation(self):
        secret = "super_secret_webhook_key_2026"
        payload_bytes = b'{"event":"task.completed","task_id":"123"}'

        expected_hash = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        generated_sig = generate_hmac_signature(payload_bytes, secret)

        self.assertEqual(generated_sig, f"sha256={expected_hash}")

    def test_tampered_payload_verification(self):
        secret = "secret_key"
        original_bytes = b'{"status":"completed"}'
        tampered_bytes = b'{"status":"failed"}'

        sig1 = generate_hmac_signature(original_bytes, secret)
        sig2 = generate_hmac_signature(tampered_bytes, secret)

        self.assertNotEqual(sig1, sig2)


if __name__ == "__main__":
    unittest.main()

