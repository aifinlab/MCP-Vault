import os
import unittest
from mcpuniverse.mcp.config import ServerConfig


FINANCE_MARKET_DATA_MODULE = "mcpuniverse.mcp.servers.finance_market_data"


class TestAppConfig(unittest.TestCase):

    def test_from_dict(self):
        data = {
            "stdio": {
                "command": "python3",
                "args": [
                    "-m", FINANCE_MARKET_DATA_MODULE
                ]
            },
            "sse": {
                "command": "python3",
                "args": [
                    "-m", FINANCE_MARKET_DATA_MODULE,
                    "--transport", "sse",
                    "--port", "{{PORT}}"
                ]
            }
        }
        config = ServerConfig.from_dict(data)
        self.assertEqual(config.stdio.command, "python3")
        self.assertListEqual(config.stdio.args, ["-m", FINANCE_MARKET_DATA_MODULE])
        self.assertEqual(config.sse.command, "python3")
        self.assertListEqual(config.sse.args,
                             ["-m", FINANCE_MARKET_DATA_MODULE, "--transport", "sse", "--port", "{{PORT}}"])

        data = {
            "stdio": {
                "command": "python3",
                "args": [
                    "-m", FINANCE_MARKET_DATA_MODULE
                ]
            }
        }
        config = ServerConfig.from_dict(data)
        self.assertEqual(config.stdio.command, "python3")
        self.assertListEqual(config.stdio.args, ["-m", FINANCE_MARKET_DATA_MODULE])
        self.assertEqual(config.sse.command, "")
        self.assertListEqual(config.sse.args, [])

    def test_to_dict(self):
        data = {
            "stdio": {
                "command": "python3",
                "args": [
                    "-m", FINANCE_MARKET_DATA_MODULE
                ]
            },
            "sse": {
                "command": "python3",
                "args": [
                    "-m", FINANCE_MARKET_DATA_MODULE,
                    "--transport", "sse",
                    "--port", "{{PORT}}"
                ]
            },
            "env": {}
        }
        config = ServerConfig.from_dict(data)
        self.assertDictEqual(config.to_dict(), data)

    def test_render_template(self):
        data = {
            "sse": {
                "command": "python3",
                "args": [
                    "-m", FINANCE_MARKET_DATA_MODULE,
                    "--transport", "sse",
                    "--port", "{{PORT}}"
                ]
            }
        }
        config = ServerConfig.from_dict(data)
        config.render_template(params={"PORT": 8001})
        self.assertListEqual(config.sse.args,
                             ["-m", FINANCE_MARKET_DATA_MODULE, "--transport", "sse", "--port", "8001"])

        config = ServerConfig.from_dict(data)
        os.environ["PORT"] = "8002"
        config.render_template()
        self.assertListEqual(config.sse.args,
                             ["-m", FINANCE_MARKET_DATA_MODULE, "--transport", "sse", "--port", "8002"])

    def test_list_unspecified_params(self):
        data = {
            "sse": {
                "command": "python3",
                "args": [
                    "-m", FINANCE_MARKET_DATA_MODULE,
                    "--transport", "sse",
                    "--port", "{{ PORT }}"
                ]
            }
        }
        config = ServerConfig.from_dict(data)
        self.assertListEqual(config.list_unspecified_params(), ["{{ PORT }}"])


if __name__ == "__main__":
    unittest.main()
