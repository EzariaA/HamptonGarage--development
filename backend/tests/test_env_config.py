# Unit tests that keep secrets out of .ebextensions/env.config
# Created by Mattie Edozie - 10/26/26
#
# env.config is uploaded to GitHub, so anyone who can see the repo can read it.
# Passwords and keys must go in the AWS Elastic Beanstalk settings page instead.
# These tests fail if someone puts a secret back in the file by accident.
#
# Run: python -m unittest backend.tests.test_env_config -v

import os
import unittest

# Path to .ebextensions/env.config
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
ENV_CONFIG = os.path.join(PROJECT_ROOT, ".ebextensions", "env.config")

# Setting names that must NEVER be in env.config
SECRET_SETTINGS = [
    "DB_PASSWORD",
    "SECRET_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_ACCESS_KEY_ID",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
]


def read_settings():
    """
    Reads env.config and returns its settings as a dictionary.
    Example: the line "AWS_REGION: us-east-2" becomes {"AWS_REGION": "us-east-2"}.
    Comment lines (starting with #) are skipped.
    """
    settings = {}
    with open(ENV_CONFIG) as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or ":" not in line:
                continue
            name, value = line.split(":", 1)
            settings[name.strip()] = value.strip()
    return settings


def read_whole_file():
    with open(ENV_CONFIG) as f:
        return f.read()


class TestEnvConfigHasNoSecrets(unittest.TestCase):

    def test_no_secret_settings(self):
        settings = read_settings()
        for name in SECRET_SETTINGS:
            self.assertNotIn(name, settings, name + " must be set in the AWS settings page, not env.config")

    def test_no_stripe_or_aws_keys(self):
        text = read_whole_file()
        # Real Stripe keys start with sk_live_ / sk_test_ / whsec_, AWS keys start with AKIA
        for start_of_key in ["sk_live_", "sk_test_", "whsec_", "AKIA"]:
            self.assertNotIn(start_of_key, text)

    def test_old_leaked_values_are_gone(self):
        text = read_whole_file()
        self.assertNotIn("vault_secure_key_2026", text)   # the old SECRET_KEY
        self.assertNotIn("vault_admin", text)              # the old database username

    def test_demo_data_is_turned_on_for_live_site(self):
        self.assertEqual(read_settings().get("SEED_DEMO_DATA"), '"true"')


if __name__ == "__main__":
    unittest.main()
