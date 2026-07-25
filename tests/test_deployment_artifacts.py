import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DeploymentArtifactsTest(unittest.TestCase):
    def test_systemd_service_is_always_on(self):
        service = (ROOT / "linkedin-autoposter.service").read_text(encoding="utf-8")

        self.assertIn("After=network-online.target", service)
        self.assertIn("EnvironmentFile=/home/ubuntu/linkedin-autoposter/.env", service)
        self.assertIn("ExecStart=/home/ubuntu/linkedin-autoposter/venv/bin/python run.py", service)
        # Restart-on-failure with a sane backoff.
        self.assertIn("Restart=on-failure", service)
        self.assertIn("RestartSec=10", service)
        # Manual stops shouldn't trigger the restart loop.
        self.assertIn("RestartPreventExitStatus=0 130 143", service)
        self.assertIn("WantedBy=multi-user.target", service)
        # .env must exist or systemd refuses to start.
        self.assertIn("ConditionPathExists=/home/ubuntu/linkedin-autoposter/.env", service)

    def test_installer_runs_healthcheck_before_restart(self):
        script = (ROOT / "scripts" / "install_service_ubuntu.sh").read_text(encoding="utf-8")

        healthcheck_index = script.index("./venv/bin/python healthcheck.py")
        restart_index = script.index('sudo systemctl restart "${SERVICE_NAME}"')

        self.assertLess(healthcheck_index, restart_index)
        self.assertIn('APP_DIR="${APP_DIR:-/home/ubuntu/linkedin-autoposter}"', script)
        self.assertIn("python3 -m venv venv", script)
        # Idempotent venv: skip if already exists.
        self.assertIn('[[ ! -d "venv" ]]', script)
        # Fail loud if healthcheck fails — don't keep restarting a broken service.
        self.assertIn("Not touching the service", script)

    def test_readme_points_to_installer(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("bash scripts/install_service_ubuntu.sh", readme)
        self.assertIn("python setup_linkedin_oauth.py", readme)
        self.assertIn("python healthcheck.py", readme)

    def test_env_example_exists(self):
        # The install script and README both reference .env.example. It must
        # live in the repo, otherwise fresh clones have no template to copy.
        env_example = ROOT / ".env.example"
        self.assertTrue(env_example.exists(), ".env.example is missing from the repo root")
        contents = env_example.read_text(encoding="utf-8")
        for var in [
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_USER_ID",
            "GROQ_API_KEY",
            "GROQ_MODEL",
            "LINKEDIN_CLIENT_ID",
            "LINKEDIN_CLIENT_SECRET",
            "LINKEDIN_REDIRECT_URI",
            "LINKEDIN_VERSION",
            "TREND_SEARCH_QUERY",
            "TAVILY_API_KEY",
            "TAVILY_TIME_RANGE",
            "DB_PATH",
        ]:
            self.assertIn(var, contents, f"{var} missing from .env.example")

    def test_bootstrap_script_exists(self):
        bootstrap = ROOT / "scripts" / "bootstrap.sh"
        self.assertTrue(bootstrap.exists(), "scripts/bootstrap.sh is missing")
        contents = bootstrap.read_text(encoding="utf-8")
        # Must reference the repo URL so user can override with REPO_URL=...
        self.assertIn("https://github.com/abnsrishik/linkedin_autopost.git", contents)
        # Must handle existing .env, existing repo, and missing .env.example.
        self.assertIn('[[ -f ".env.example" ]]', contents)
        self.assertIn('[[ -d "${APP_DIR}/.git" ]]', contents)


if __name__ == "__main__":
    unittest.main()
