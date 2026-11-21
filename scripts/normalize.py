"""Normalisation helpers for domain, IP and CIDR source lists."""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path

from .pb import DomainEntry

_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_COMMENT_RE = re.compile(r"\s+#.*$")
_IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


class NormalizeError(ValueError):
    pass


def decode_text(raw: bytes) -> str:
    """Decode a source file, tolerating UTF-8 BOM and legacy CP1251."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1251", "replace")


def clean_line(line: str) -> str:
    line = line.strip().strip('"').strip("'")
    if not line or line.startswith(("#", "!", ";")):
        return ""
    line = _COMMENT_RE.sub("", line).strip()
    return line


def _idna(value: str) -> str | None:
    try:
        return value.encode("idna").decode("ascii").lower()
    except (UnicodeError, UnicodeDecodeError):
        return None


def normalize_domain(raw: str, allow_single_label: bool = False) -> DomainEntry | None:
    """Convert one source line into a ``DomainEntry`` (or ``None``).

    Accepted input examples::

        example.com
        domain:example.com
        full:example.com
        *.example.com
        https://example.com/path?q=1
        пример.рф
    """
    line = clean_line(raw)
    if not line:
        return None

    token = line.split()[0]
    kind = "root"

    if token.startswith("domain:"):
        token = token[7:]
    elif token.startswith("full:"):
        token = token[5:]
        kind = "full"
    elif token.startswith(("keyword:", "regexp:")):
        # Keyword/regexp matching is deliberately not used: these entries are
        # too broad for a block list and impossible to verify safely.
        return None
    elif token.startswith("*."):
        token = token[2:]

    token = token.strip().strip(".")

    if "://" in token:
        token = token.split("://", 1)[1]
    token = token.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]

    # Strip a port, but do not touch IPv6 literals.
    if token.count(":") == 1:
        token = token.split(":", 1)[0]

    token = token.strip(".")
    if not token:
        return None

    if _IPV4_RE.match(token):
        return None

    ascii_domain = _idna(token)
    if not ascii_domain:
        return None

    labels = ascii_domain.split(".")
    if len(labels) < 2 and not allow_single_label:
        return None
    if len(ascii_domain) > 253:
        return None
    for label in labels:
        if not label or len(label) > 63 or not _LABEL_RE.match(label):
            return None

    if ascii_domain.replace(".", "").isdigit():
        return None

    return DomainEntry(ascii_domain, kind)


def dedupe_domains(entries: list[DomainEntry]) -> list[DomainEntry]:
    """Deduplicate by value, preferring a root-domain entry over ``full:``."""
    best: dict[str, DomainEntry] = {}
    for entry in entries:
        previous = best.get(entry.value)
        if previous is None:
            best[entry.value] = entry
        elif previous.kind == "full" and entry.kind == "root":
            best[entry.value] = entry
    return sorted(best.values(), key=DomainEntry.sort_key)


def parse_domain_text(text: str, allow_single_label: bool = False) -> list[DomainEntry]:
    entries: list[DomainEntry] = []
    for line in text.splitlines():
        entry = normalize_domain(line, allow_single_label=allow_single_label)
        if entry is not None:
            entries.append(entry)
    return dedupe_domains(entries)


def parse_domain_file(path: Path, allow_single_label: bool = False) -> list[DomainEntry]:
    return parse_domain_text(decode_text(path.read_bytes()), allow_single_label=allow_single_label)


def normalize_cidr(raw: str, allow_private: bool = False) -> ipaddress._BaseNetwork | None:
    line = clean_line(raw)
    if not line:
        return None
    token = line.split()[0]

    if "/" not in token:
        token = f"{token}/32" if ":" not in token else f"{token}/128"

    try:
        network = ipaddress.ip_network(token, strict=False)
    except ValueError:
        return None

    if network.prefixlen == 0:
        return None

    if network.version == 4:
        first_octet = int(str(network.network_address).split(".", 1)[0])
        if first_octet == 0 or first_octet >= 224:
            return None
        if first_octet == 127 and not allow_private:
            return None
    else:
        if network.is_multicast:
            return None
        if network.is_link_local and not allow_private:
            return None

    if not allow_private and (
        network.is_private
        or network.is_loopback
        or network.is_link_local
        or network.is_multicast
        or network.is_reserved
        or network.is_unspecified
    ):
        return None

    return network


def parse_cidr_text(text: str, allow_private: bool = False) -> list[ipaddress._BaseNetwork]:
    networks: list[ipaddress._BaseNetwork] = []
    for line in text.splitlines():
        network = normalize_cidr(line, allow_private=allow_private)
        if network is not None:
            networks.append(network)
    return networks


def collapse_networks(networks: list[ipaddress._BaseNetwork]) -> list[ipaddress._BaseNetwork]:
    v4 = [net for net in networks if net.version == 4]
    v6 = [net for net in networks if net.version == 6]
    collapsed: list[ipaddress._BaseNetwork] = []
    if v4:
        collapsed.extend(ipaddress.collapse_addresses(v4))
    if v6:
        collapsed.extend(ipaddress.collapse_addresses(v6))
    return sorted(
        collapsed,
        key=lambda net: (net.version, int(net.network_address), net.prefixlen),
    )
