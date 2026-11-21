"""Validate generated .dat files, presets and checksums."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from . import pb

REF_RE = re.compile(r"^(?:geosite|geoip):([a-z0-9-]+)$")

MIN_COUNTS = {
    ("geosite", "russian-block"): 100_000,
    ("geosite", "whitelist"): 800,
    ("geosite", "youtube"): 100,
    ("geosite", "geoblock"): 500,
    ("geoip", "russian-block"): 10_000,
    ("geoip", "whitelist"): 20_000,
    ("geoip", "youtube"): 20,
}


class VerifyError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_sha256sums(directory: Path) -> int:
    path = directory / "SHA256SUMS"
    if not path.is_file():
        raise VerifyError("SHA256SUMS is missing")
    checked = 0
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        digest, name = line.split("  ", 1)
        target = directory / name
        if not target.is_file():
            raise VerifyError(f"SHA256SUMS references missing file: {name}")
        actual = sha256_file(target)
        if actual != digest:
            raise VerifyError(f"checksum mismatch: {name}")
        seen.add(name)
        checked += 1
    if not seen:
        raise VerifyError("SHA256SUMS is empty")
    return checked


def check_build_info(directory: Path) -> dict:
    path = directory / "build-info.json"
    if not path.is_file():
        raise VerifyError("build-info.json is missing")
    info = json.loads(path.read_text(encoding="utf-8"))
    if info.get("schema") != 1:
        raise VerifyError("unexpected build-info schema")
    for name, meta in info.get("files", {}).items():
        target = directory / name
        if not target.is_file():
            raise VerifyError(f"build-info references missing file: {name}")
        if target.stat().st_size != meta["bytes"]:
            raise VerifyError(f"size mismatch: {name}")
        if sha256_file(target) != meta["sha256"]:
            raise VerifyError(f"hash mismatch: {name}")
    return info


def check_geosite(path: Path) -> dict[str, int]:
    sites = pb.parse_geosite(path.read_bytes())
    if not sites:
        raise VerifyError("geosite.dat is empty")
    result: dict[str, int] = {}
    for site in sites:
        code = site.code.lower()
        if code in result:
            raise VerifyError(f"duplicate geosite category: {site.code}")
        seen: set[str] = set()
        for domain in site.domains:
            value = domain.value
            if value in seen:
                raise VerifyError(f"duplicate domain in {site.code}: {value}")
            seen.add(value)
            if not value or value.startswith(".") or "*" in value:
                raise VerifyError(f"invalid domain in {site.code}: {value!r}")
            if len(value) > 253 or any(ord(char) > 127 for char in value):
                raise VerifyError(f"non-ASCII or too long domain in {site.code}: {value!r}")
            if " " in value or "://" in value:
                raise VerifyError(f"unclean domain in {site.code}: {value!r}")
        result[code] = len(site.domains)
    return result


def check_geoip(path: Path) -> dict[str, int]:
    entries = pb.parse_geoip(path.read_bytes())
    if not entries:
        raise VerifyError("geoip.dat is empty")
    result: dict[str, int] = {}
    for code, networks in entries:
        slug = code.lower()
        if slug in result:
            raise VerifyError(f"duplicate geoip category: {code}")
        seen: set[str] = set()
        for network in networks:
            if network.prefixlen == 0:
                raise VerifyError(f"0.0.0.0/0 in {code}")
            text = str(network)
            if text in seen:
                raise VerifyError(f"duplicate network in {code}: {text}")
            seen.add(text)
        result[slug] = len(networks)
    return result


def check_presets(directory: Path, geosite: set[str], geoip: set[str]) -> list[str]:
    names: list[str] = []
    for path in sorted(directory.glob("HAPP-*.JSON")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise VerifyError(f"{path.name}: invalid JSON: {exc}") from exc
        for key in ("Name", "GlobalProxy", "Geoipurl", "Geositeurl", "DirectSites", "ProxySites"):
            if key not in payload:
                raise VerifyError(f"{path.name}: missing key {key}")
        for key in ("DirectSites", "ProxySites"):
            for reference in payload[key]:
                match = REF_RE.match(reference)
                if not match:
                    raise VerifyError(f"{path.name}: unsupported reference {reference!r}")
                kind, category = reference.split(":", 1)
                known = geosite if kind == "geosite" else geoip
                if category not in known:
                    raise VerifyError(f"{path.name}: unknown category {reference!r}")
        for key in ("DirectIp", "ProxyIp"):
            for reference in payload[key]:
                match = REF_RE.match(reference)
                if not match:
                    raise VerifyError(f"{path.name}: unsupported reference {reference!r}")
                kind, category = reference.split(":", 1)
                known = geosite if kind == "geosite" else geoip
                if category not in known:
                    raise VerifyError(f"{path.name}: unknown category {reference!r}")
        names.append(path.name)
    if not names:
        raise VerifyError("no Happ presets found")
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", nargs="?", default="dist")
    args = parser.parse_args(argv)
    directory = Path(args.dist)
    if not directory.is_absolute():
        directory = Path.cwd() / directory

    geosite = check_geosite(directory / "geosite.dat")
    geoip = check_geoip(directory / "geoip.dat")

    for (kind, name), minimum in MIN_COUNTS.items():
        counts = geosite if kind == "geosite" else geoip
        if counts.get(name, 0) < minimum:
            raise VerifyError(
                f"{kind}:{name} has {counts.get(name, 0)} entries, expected at least {minimum}"
            )

    presets = check_presets(directory, set(geosite), set(geoip))
    sums = check_sha256sums(directory)
    info = check_build_info(directory)

    print("geosite.dat")
    for name, count in geosite.items():
        print(f"  {name:<16} {count:>8}")
    print("geoip.dat")
    for name, count in geoip.items():
        print(f"  {name:<16} {count:>8}")
    print(f"presets: {', '.join(presets)}")
    print(f"sha256sums: {sums} files")
    print(f"build: {info.get('built_at')} ({info.get('commit')})")
    print("verify OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerifyError as exc:
        print(f"verify failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
