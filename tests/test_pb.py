from __future__ import annotations

import unittest

from scripts import pb


class GeoSiteRoundTripTest(unittest.TestCase):
    def test_round_trip(self) -> None:
        data = pb.build_geosite(
            [
                pb.GeoSite(
                    "RUSSIAN-BLOCK",
                    [
                        pb.DomainEntry("example.com", "root"),
                        pb.DomainEntry("only.example.com", "full"),
                    ],
                ),
                pb.GeoSite("WHITELIST", [pb.DomainEntry("gosuslugi.ru", "root")]),
            ]
        )
        parsed = pb.parse_geosite(data)
        self.assertEqual([site.code for site in parsed], ["RUSSIAN-BLOCK", "WHITELIST"])
        self.assertEqual(parsed[0].domains[0], pb.DomainEntry("example.com", "root"))
        self.assertEqual(parsed[0].domains[1], pb.DomainEntry("only.example.com", "full"))
        self.assertEqual(parsed[1].domains[0].value, "gosuslugi.ru")

    def test_empty(self) -> None:
        self.assertEqual(pb.parse_geosite(pb.build_geosite([])), [])


class GeoIPRoundTripTest(unittest.TestCase):
    def test_round_trip(self) -> None:
        data = pb.build_geoip(
            [
                (
                    "RUSSIAN-BLOCK",
                    [
                        pb.ipaddress.ip_network("192.0.2.0/24"),
                        pb.ipaddress.ip_network("2001:db8::/32"),
                    ],
                )
            ]
        )
        parsed = pb.parse_geoip(data)
        self.assertEqual(parsed[0][0], "RUSSIAN-BLOCK")
        self.assertEqual(
            [str(net) for net in parsed[0][1]],
            ["192.0.2.0/24", "2001:db8::/32"],
        )


if __name__ == "__main__":
    unittest.main()
