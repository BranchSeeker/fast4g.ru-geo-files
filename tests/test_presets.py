from __future__ import annotations

import json
import unittest

from scripts.presets import PresetConfig, build_presets


class PresetsTest(unittest.TestCase):
    def test_presets(self) -> None:
        config = PresetConfig(
            repository="owner/repo",
            release_url="https://github.com/owner/repo/releases/latest/download",
            updated_at=1700000000,
        )
        presets = build_presets(config)
        self.assertEqual(
            sorted(presets),
            ["HAPP-BLOCKED-ONLY.JSON", "HAPP-WHITELIST.JSON"],
        )
        blocked = json.loads(presets["HAPP-BLOCKED-ONLY.JSON"])
        whitelist = json.loads(presets["HAPP-WHITELIST.JSON"])

        self.assertFalse(blocked["GlobalProxy"])
        self.assertTrue(whitelist["GlobalProxy"])
        self.assertIn("geosite:russian-block", blocked["ProxySites"])
        self.assertIn("geoip:russian-block", blocked["ProxyIp"])
        self.assertEqual(whitelist["ProxySites"], [])
        self.assertEqual(blocked["Geositeurl"], config.release_url + "/geosite.dat")
        self.assertEqual(blocked["Geoipurl"], config.release_url + "/geoip.dat")
        self.assertEqual(blocked["LastUpdated"], "1700000000")


if __name__ == "__main__":
    unittest.main()
