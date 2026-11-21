from __future__ import annotations

import json
import unittest

from scripts.presets import PresetConfig, build_presets


class PresetsTest(unittest.TestCase):
    def test_presets(self) -> None:
        config = PresetConfig(
            repository="owner/repo",
            release_url="https://github.com/owner/repo/releases/latest/download",
            mirror_url="https://cdn.jsdelivr.net/gh/owner/repo@release",
            updated_at=1700000000,
        )
        presets = build_presets(config)
        self.assertEqual(
            sorted(presets),
            [
                "HAPP-BLOCKED-ONLY-JSDELIVR.JSON",
                "HAPP-BLOCKED-ONLY.JSON",
                "HAPP-WHITELIST-JSDELIVR.JSON",
                "HAPP-WHITELIST.JSON",
            ],
        )
        blocked = json.loads(presets["HAPP-BLOCKED-ONLY.JSON"])
        whitelist = json.loads(presets["HAPP-WHITELIST.JSON"])
        blocked_mirror = json.loads(presets["HAPP-BLOCKED-ONLY-JSDELIVR.JSON"])

        self.assertFalse(blocked["GlobalProxy"])
        self.assertTrue(whitelist["GlobalProxy"])
        self.assertIn("geosite:russian-block", blocked["ProxySites"])
        self.assertIn("geoip:russian-block", blocked["ProxyIp"])
        self.assertEqual(whitelist["ProxySites"], [])
        self.assertEqual(blocked["Geositeurl"], config.release_url + "/geosite.dat")
        self.assertEqual(blocked["Geoipurl"], config.release_url + "/geoip.dat")
        self.assertEqual(
            blocked_mirror["Geositeurl"], config.mirror_url + "/geosite.dat"
        )
        self.assertEqual(
            blocked_mirror["Geoipurl"], config.mirror_url + "/geoip.dat"
        )
        self.assertEqual(blocked["LastUpdated"], "1700000000")


if __name__ == "__main__":
    unittest.main()
