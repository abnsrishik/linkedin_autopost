import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DeploymentArtifactsTest(unittest.TestCase):
    def test_systemd_service_is_always_on(self):
        service = (ROOT / "linkedin-autoposter.service").read_text(encoding="utf-8")

        self.assertIn("After=network-online.target", service)
        self.assertIn("EnvironmentFile=/home/ubuntu/linkedin-autoposter/.env", service)
        self.assertIn("ExecStart=/home/ubuntu/linkedin-autoposter/venv/bin/python run.py", service)
        self.assertIn("Restart=always", service)
        self.assertIn("WantedBy=multi-user.target", service)

    def test_installer_runs_healthcheck_before_restart(self):
        script = (ROOT / "scripts" / "install_service_ubuntu.sh").read_text(encoding="utf-8")

        healthcheck_index = script.index("./venv/bin/python healthcheck.py")
        restart_index = script.index('sudo systemctl restart "${SERVICE_NAME}"')

        self.assertLess(healthcheck_index, restart_index)
        self.assertIn('APP_DIR="${APP_DIR:-/home/ubuntu/linkedin-autoposter}"', script)
        self.assertIn("python3 -m venv venv", script)

    def test_readme_points_to_installer(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("bash scripts/install_service_ubuntu.sh", readme)
        self.assertIn("python setup_linkedin_oauth.py", readme)
        self.assertIn("python healthcheck.py", readme)


if __name__ == "__main__":
    unittest.main()
