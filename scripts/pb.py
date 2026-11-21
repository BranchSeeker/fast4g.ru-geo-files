"""Minimal protobuf wire-format codec for V2Ray/Xray geo files.

Only the subset of ``app/router/routercommon/common.proto`` that is needed
for ``geoip.dat`` and ``geosite.dat`` is implemented.  Keeping this in pure
Python means the build has no third-party dependencies and works in any
GitHub Actions runner.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Iterable, Iterator


class ProtoError(ValueError):
    """Raised when a .dat payload cannot be decoded."""


def encode_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("varint cannot be negative")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def decode_varint(data: bytes, pos: int = 0) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        if pos >= len(data):
            raise ProtoError("truncated varint")
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7
        if shift > 63:
            raise ProtoError("varint is too long")


def tag(field_number: int, wire_type: int) -> bytes:
    return encode_varint((field_number << 3) | wire_type)


def len_field(field_number: int, payload: bytes) -> bytes:
    return tag(field_number, 2) + encode_varint(len(payload)) + payload


def uint_field(field_number: int, value: int) -> bytes:
    return tag(field_number, 0) + encode_varint(value)


def _iter_fields(data: bytes) -> Iterator[tuple[int, int, object]]:
    pos = 0
    while pos < len(data):
        key, pos = decode_varint(data, pos)
        field_number, wire_type = key >> 3, key & 0x07
        if wire_type == 0:
            value, pos = decode_varint(data, pos)
            yield field_number, wire_type, value
        elif wire_type == 2:
            length, pos = decode_varint(data, pos)
            if pos + length > len(data):
                raise ProtoError("truncated length-delimited field")
            value = data[pos : pos + length]
            pos += length
            yield field_number, wire_type, value
        elif wire_type == 1:
            value = data[pos : pos + 8]
            pos += 8
            yield field_number, wire_type, value
        elif wire_type == 5:
            value = data[pos : pos + 4]
            pos += 4
            yield field_number, wire_type, value
        else:
            raise ProtoError(f"unsupported wire type: {wire_type}")


# ---------------------------------------------------------------------------
# geosite.dat


DOMAIN_TYPE_BY_KIND = {"plain": 0, "root": 2, "full": 3}
KIND_BY_DOMAIN_TYPE = {value: key for key, value in DOMAIN_TYPE_BY_KIND.items()}


@dataclass(frozen=True)
class DomainEntry:
    value: str
    kind: str = "root"  # root | full | plain

    def sort_key(self) -> tuple[str, int]:
        return self.value, DOMAIN_TYPE_BY_KIND.get(self.kind, 2)


@dataclass
class GeoSite:
    code: str
    domains: list[DomainEntry]


def _encode_domain(domain: DomainEntry) -> bytes:
    payload = uint_field(1, DOMAIN_TYPE_BY_KIND.get(domain.kind, 2))
    payload += len_field(2, domain.value.encode("utf-8"))
    return payload


def build_geosite(entries: Iterable[GeoSite]) -> bytes:
    out = bytearray()
    for site in entries:
        body = bytearray(len_field(1, site.code.encode("ascii")))
        for domain in site.domains:
            body.extend(len_field(2, _encode_domain(domain)))
        out.extend(len_field(1, bytes(body)))
    return bytes(out)


def parse_geosite(data: bytes) -> list[GeoSite]:
    sites: list[GeoSite] = []
    for field_number, wire_type, payload in _iter_fields(data):
        if field_number != 1 or wire_type != 2:
            continue
        code = ""
        domains: list[DomainEntry] = []
        for fnum, wtype, value in _iter_fields(payload):  # type: ignore[arg-type]
            if fnum == 1 and wtype == 2:
                code = value.decode("ascii", "replace")  # type: ignore[union-attr]
            elif fnum == 2 and wtype == 2:
                kind = "root"
                domain_value = ""
                for dnum, dtype, dvalue in _iter_fields(value):  # type: ignore[arg-type]
                    if dnum == 1 and dtype == 0:
                        kind = KIND_BY_DOMAIN_TYPE.get(dvalue, "root")  # type: ignore[arg-type]
                    elif dnum == 2 and dtype == 2:
                        domain_value = dvalue.decode("utf-8", "replace")  # type: ignore[union-attr]
                if domain_value:
                    domains.append(DomainEntry(domain_value, kind))
        sites.append(GeoSite(code, domains))
    return sites


# ---------------------------------------------------------------------------
# geoip.dat


def cidr_field(network: ipaddress._BaseNetwork) -> bytes:
    return len_field(1, network.network_address.packed) + uint_field(2, network.prefixlen)


def build_geoip(entries: Iterable[tuple[str, Iterable[ipaddress._BaseNetwork]]]) -> bytes:
    out = bytearray()
    for code, networks in entries:
        body = bytearray(len_field(1, code.encode("ascii")))
        for network in networks:
            body.extend(len_field(2, cidr_field(network)))
        out.extend(len_field(1, bytes(body)))
    return bytes(out)


def parse_geoip(data: bytes) -> list[tuple[str, list[ipaddress._BaseNetwork]]]:
    result: list[tuple[str, list[ipaddress._BaseNetwork]]] = []
    for field_number, wire_type, payload in _iter_fields(data):
        if field_number != 1 or wire_type != 2:
            continue
        code = ""
        networks: list[ipaddress._BaseNetwork] = []
        for fnum, wtype, value in _iter_fields(payload):  # type: ignore[arg-type]
            if fnum == 1 and wtype == 2:
                code = value.decode("ascii", "replace")  # type: ignore[union-attr]
            elif fnum == 2 and wtype == 2:
                raw_ip = b""
                prefix = 0
                for cnum, ctype, cvalue in _iter_fields(value):  # type: ignore[arg-type]
                    if cnum == 1 and ctype == 2:
                        raw_ip = cvalue  # type: ignore[assignment]
                    elif cnum == 2 and ctype == 0:
                        prefix = cvalue  # type: ignore[assignment]
                if raw_ip:
                    address = ipaddress.ip_address(raw_ip)
                    networks.append(ipaddress.ip_network((address, prefix), strict=False))
        result.append((code, networks))
    return result
