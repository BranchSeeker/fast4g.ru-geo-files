from __future__ import annotations

import unittest

from scripts.normalize import (
    collapse_networks,
    dedupe_domains,
    normalize_cidr,
    normalize_domain,
    parse_domain_text,
)
from scripts.pb import DomainEntry


class DomainNormalizationTest(unittest.TestCase):
    def test_plain_domain(self) -> None:
        entry = normalize_domain("Example.COM")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.value, "example.com")
        self.assertEqual(entry.kind, "root")

    def test_domain_prefix(self) -> None:
        entry = normalize_domain("domain:example.com")
        assert entry is not None
        self.assertEqual(entry.value, "example.com")
        self.assertEqual(entry.kind, "root")

    def test_full_prefix(self) -> None:
        entry = normalize_domain("full:example.com")
        assert entry is not None
        self.assertEqual(entry.kind, "full")

    def test_wildcard(self) -> None:
        entry = normalize_domain("*.example.com")
        assert entry is not None
        self.assertEqual(entry.value, "example.com")
        self.assertEqual(entry.kind, "root")

    def test_url(self) -> None:
        entry = normalize_domain("https://example.com/path?q=1")
        assert entry is not None
        self.assertEqual(entry.value, "example.com")

    def test_url_with_port(self) -> None:
        entry = normalize_domain("http://example.com:8080/path")
        assert entry is not None
        self.assertEqual(entry.value, "example.com")

    def test_idn(self) -> None:
        entry = normalize_domain("пример.рф")
        assert entry is not None
        self.assertTrue(entry.value.startswith("xn--"))

    def test_reject_ip(self) -> None:
        self.assertIsNone(normalize_domain("192.0.2.1"))

    def test_reject_single_label(self) -> None:
        self.assertIsNone(normalize_domain("localhost"))
        self.assertIsNotNone(normalize_domain("localhost", allow_single_label=True))

    def test_reject_keyword_and_regexp(self) -> None:
        self.assertIsNone(normalize_domain("keyword:example"))
        self.assertIsNone(normalize_domain("regexp:^example"))


class DedupeTest(unittest.TestCase):
    def test_root_wins_over_full(self) -> None:
        entries = [DomainEntry("example.com", "full"), DomainEntry("example.com", "root")]
        result = dedupe_domains(entries)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].kind, "root")

    def test_parse_text(self) -> None:
        text = """
        # comment
        example.com
        domain:example.com
        full:only.example.com
        bad_domain
        192.0.2.1
        """
        result = parse_domain_text(text)
        self.assertEqual(
            [(entry.value, entry.kind) for entry in result],
            [("example.com", "root"), ("only.example.com", "full")],
        )


class CidrTest(unittest.TestCase):
    def test_collapse_adjacent(self) -> None:
        a = normalize_cidr("8.8.8.0/25")
        b = normalize_cidr("8.8.8.128/25")
        assert a is not None and b is not None
        collapsed = collapse_networks([a, b])
        self.assertEqual([str(net) for net in collapsed], ["8.8.8.0/24"])

    def test_reject_unspecified(self) -> None:
        self.assertIsNone(normalize_cidr("0.0.0.0/0"))
        self.assertIsNone(normalize_cidr("224.0.0.0/4"))

    def test_private_allowed_only_when_requested(self) -> None:
        self.assertIsNone(normalize_cidr("10.0.0.0/8"))
        self.assertIsNotNone(normalize_cidr("10.0.0.0/8", allow_private=True))

    def test_ipv6(self) -> None:
        net = normalize_cidr("2a00:1450::/32")
        assert net is not None
        self.assertEqual(net.version, 6)


if __name__ == "__main__":
    unittest.main()
