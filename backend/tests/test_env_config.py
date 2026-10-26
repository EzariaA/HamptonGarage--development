# Unit tests that keep secrets out of .ebextensions/env.config
# Created by Mattie Edozie - 10/26/26
# Run: python -m unittest backend.tests.test_env_config

import os
import re
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
ENV_CONFIG = os.path.join(PROJECT_ROOT, ".ebextensions", "env.config")

# Settings that must be set in the Elastic Beanstalk console, never committed
SECRET_SETTINGS = (
    "DB_PASSWORD",
    "SECRET_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_ACCESS_KEY_ID",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
)


def committed_settings():
    """Returns {NAME: value} for every `NAME: value` line that isn't a comment."""
    settings = {}
    with open(ENV_CONFIG) as f:
        for line in f:
            match = re.match(r"^\s*([A-Z][A-Z0-9_]*)\s*:\s*(.*?)\s*$", line)
            if match and not line.lstrip().startswith("#"):
                settings[match.group(1)] = match.group(2)
    return settings


class TestEnvConfigHasNoSecrets(unittest.TestCase):
    def test_no_secret_settings_committed(self):
        settings = committed_settings()
        for name in SECRET_SETTINGS:
            self.assertNotIn(name, settings, f"{name} must be set in the EB console, not env.config")

    def test_no_secret_looking_values(self):
        with open(ENV_CONFIG) as f:
            text = f.read()
        # Stripe keys and AWS access key ids have fixed prefixes
        self.assertIsNone(re.search(r"\b(sk|rk)_(live|test)_\w+", text))
        self.assertIsNone(re.search(r"\bwhsec_\w+", text))
        self.assertIsNone(re.search(r"\bAKIA[0-9A-Z]{16}\b", text))

    def test_old_leaked_values_are_gone(self):
        with open(ENV_CONFIG) as f:
            text = f.read()
        self.assertNotIn("vault_secure_key_2026", text)
        self.assertNotIn("vault_admin", text)

    def test_demo_data_is_enabled_for_live_site(self):
        self.assertEqual(committed_settings().get("SEED_DEMO_DATA"), '"true"')


if __name__ == "__main__":
    unittest.main()
