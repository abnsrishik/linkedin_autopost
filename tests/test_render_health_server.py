import json
import unittest
from unittest.mock import patch

import requests

from bot.render_health_server import start_render_health_server


class RenderHealthServerTest(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_server_is_disabled_without_port(self):
        self.assertIsNone(start_render_health_server())

    @patch.dict("os.environ", {"PORT": "0"}, clear=True)
    def test_server_responds_when_port_is_set(self):
        server = start_render_health_server()
        try:
            port = server.server_address[1]
            response = requests.get(f"http://127.0.0.1:{port}/", timeout=5)
            payload = json.loads(response.text)
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(200, response.status_code)
        self.assertTrue(payload["ok"])
        self.assertEqual("linkedin-autoposter", payload["service"])


if __name__ == "__main__":
    unittest.main()
