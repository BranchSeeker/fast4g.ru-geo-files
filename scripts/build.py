"""Build geosite.dat, geoip.dat and distribution assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import pb
from .fetch import FetchResult, fetch, fetch_json
from .normalize import (
    collapse_networks,
    decode_text,
    dedupe_domains,
    normalize_cidr,
    parse_cidr_text,
    parse_domain_text,
)
from .presets import build_presets, default_preset_config

ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "BranchSeeker/fast4g.ru-geo-files")
BUILTIN_PRIVATE = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "100.64.0.0/10",
    "192.0.0.0/24",
    "192.0.2.0/24",
    "198.18.0.0/15",
    "198.51.100.0/24",
    "203.0.113.0/24",
    "::1/128",
    "fc00::/7",
    "fe80::/10",
    "2001:db8::/32",
]


@dataclass
class SourceRecord:
    category: str
    url: str
    sha256: str
    bytes: int
    items: int
    fetched_at: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def git_commit() -> str:
    env_sha = os.environ.get("GITHUB_SHA", "").strip()
    if env_sha:
        return env_sha[:12]
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _local_file(root: Path, relative: str) -> tuple[str, FetchResult]:
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(f"local source not found: {path}")
    raw = path.read_bytes()
    return decode_text(raw), FetchResult(
        url=relative,
        data=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
        fetched_at=datetime.fromtimestamp(
            path.stat().st_mtime, timezone.utc
        ).isoformat(timespec="seconds"),
    )


def _read_text_source(
    root: Path,
    source: dict,
    cache_dir: Path | None,
    refresh: bool,
) -> tuple[str, FetchResult]:
    url = source["url"]
    if url.startswith("data/"):
        return _local_file(root, url)
    result = fetch(url, cache_dir=cache_dir, refresh=refresh)
    return decode_text(result.data), result


def _apply_domain_overrides(root: Path, entries: list[pb.DomainEntry]) -> list[pb.DomainEntry]:
    exclude_path = root / "data" / "exclude-domains.txt"
    if exclude_path.is_file():
        excluded = {entry.value for entry in parse_domain_text(decode_text(exclude_path.read_bytes()), allow_single_label=True)}
        entries = [entry for entry in entries if entry.value not in excluded]

    extra_path = root / "data" / "extra-domains.txt"
    if extra_path.is_file():
        entries.extend(parse_domain_text(decode_text(extra_path.read_bytes()), allow_single_label=True))

    return dedupe_domains(entries)


def _apply_cidr_overrides(
    root: Path, networks: list, allow_private: bool
) -> list:
    exclude_path = root / "data" / "exclude-ips.txt"
    if exclude_path.is_file():
        excluded = [
            normalize_cidr(line, allow_private=allow_private)
            for line in decode_text(exclude_path.read_bytes()).splitlines()
        ]
        excluded = [net for net in excluded if net is not None]
        if excluded:
            def overlaps(net) -> bool:
                return any(
                    net.version == other.version
                    and (net.subnet_of(other) or net.supernet_of(other))
                    for other in excluded
                )

            networks = [net for net in networks if not overlaps(net)]

    extra_path = root / "data" / "extra-ips.txt"
    if extra_path.is_file():
        networks.extend(parse_cidr_text(decode_text(extra_path.read_bytes()), allow_private=allow_private))

    return networks


def build_geosite(
    config: dict,
    root: Path,
    cache_dir: Path | None,
    refresh: bool,
) -> tuple[list[pb.GeoSite], dict[str, int], list[SourceRecord]]:
    sites: list[pb.GeoSite] = []
    stats: dict[str, int] = {}
    records: list[SourceRecord] = []

    for name, category in config["geosite"].items():
        entries: list[pb.DomainEntry] = []
        for source in category["sources"]:
            text, result = _read_text_source(root, source, cache_dir, refresh)
            parsed = parse_domain_text(
                text,
                allow_single_label=bool(category.get("allow_single_label", False)),
            )
            entries.extend(parsed)
            records.append(
                SourceRecord(
                    category=name,
                    url=result.url,
                    sha256=result.sha256,
                    bytes=len(result.data),
                    items=len(parsed),
                    fetched_at=result.fetched_at,
                )
            )
        if name == "russian-block":
            entries = _apply_domain_overrides(root, entries)
        elif name == "whitelist":
            extra_path = root / "data" / "extra-whitelist-domains.txt"
            if extra_path.is_file():
                entries.extend(parse_domain_text(decode_text(extra_path.read_bytes()), allow_single_label=True))
                entries = dedupe_domains(entries)

        entries = dedupe_domains(entries)
        if not entries:
            raise RuntimeError(f"geosite category {name!r} is empty")
        sites.append(pb.GeoSite(name.upper(), entries))
        stats[name] = len(entries)

    # Small categories first: Xray scans the dat sequentially for the requested
    # code, so keeping the 2.5 MB russian-block entry last makes lookups for
    # whitelist/youtube/geoblock noticeably cheaper.
    sites.sort(key=lambda site: len(site.domains))
    return sites, stats, records


def build_geoip(
    config: dict,
    root: Path,
    cache_dir: Path | None,
    refresh: bool,
) -> tuple[list[tuple[str, list]], dict[str, int], list[SourceRecord]]:
    categories: list[tuple[str, list]] = []
    stats: dict[str, int] = {}
    records: list[SourceRecord] = []

    for name, category in config["geoip"].items():
        allow_private = name == "private"
        networks: list = []

        for source in category["sources"]:
            fmt = source.get("format")
            url = source["url"]
            count_before = len(networks)

            if fmt == "cidr":
                text, result = _read_text_source(root, source, cache_dir, refresh)
                parsed = parse_cidr_text(text, allow_private=allow_private)
                networks.extend(parsed)
                items = len(parsed)
            elif fmt == "snapshot":
                text, result = _local_file(root, url)
                parsed = parse_cidr_text(text, allow_private=allow_private)
                networks.extend(parsed)
                items = len(parsed)
            elif fmt == "builtin-private":
                parsed = [
                    net
                    for net in (
                        normalize_cidr(item, allow_private=True) for item in BUILTIN_PRIVATE
                    )
                    if net is not None
                ]
                networks.extend(parsed)
                items = len(parsed)
                result = FetchResult(
                    url=url,
                    data=b"",
                    sha256=hashlib.sha256(b"").hexdigest(),
                    fetched_at=utc_now(),
                )
            elif fmt == "ripe-asn":
                try:
                    payload = fetch_json(url, cache_dir=cache_dir, refresh=refresh)
                    prefixes = payload["data"]["prefixes"]  # type: ignore[index]
                    parsed = []
                    for prefix in prefixes:
                        net = normalize_cidr(prefix["prefix"], allow_private=allow_private)
                        if net is not None:
                            parsed.append(net)
                    networks.extend(parsed)
                    items = len(parsed)
                    result = FetchResult(
                        url=url,
                        data=json.dumps(payload).encode("utf-8"),
                        sha256=hashlib.sha256(json.dumps(payload).encode("utf-8")).hexdigest(),
                        fetched_at=utc_now(),
                    )
                except Exception as exc:  # noqa: BLE001 - fallback source is optional
                    print(f"warning: {url} failed ({exc}); using snapshot only", file=sys.stderr)
                    continue
            else:
                raise RuntimeError(f"unknown source format: {fmt!r}")

            records.append(
                SourceRecord(
                    category=name,
                    url=result.url,
                    sha256=result.sha256,
                    bytes=len(result.data),
                    items=items,
                    fetched_at=result.fetched_at,
                )
            )
            if len(networks) == count_before and fmt != "builtin-private":
                print(f"warning: source {url} produced no networks", file=sys.stderr)

        if name == "russian-block":
            networks = _apply_cidr_overrides(root, networks, allow_private=allow_private)

        networks = collapse_networks(networks)
        if not networks:
            raise RuntimeError(f"geoip category {name!r} is empty")
        categories.append((name.upper(), networks))
        stats[name] = len(networks)

    # Same reason as for geosite: keep the largest block last.
    categories.sort(key=lambda item: len(item[1]))
    return categories, stats, records


def write_text_domains(path: Path, domains: list[pb.DomainEntry]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for domain in domains:
            prefix = "full:" if domain.kind == "full" else ""
            handle.write(f"{prefix}{domain.value}\n")


def write_text_cidrs(path: Path, networks: list) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for network in networks:
            handle.write(f"{network}\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_utf8(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def write_sha256sums(directory: Path, files: list[Path]) -> None:
    lines = []
    for path in sorted(files, key=lambda item: item.name):
        lines.append(f"{sha256_file(path)}  {path.name}")
    write_utf8(directory / "SHA256SUMS", "\n".join(lines) + "\n")


def release_notes(
    geosite_stats: dict[str, int],
    geoip_stats: dict[str, int],
    built_at: str,
    commit: str,
) -> str:
    lines = [
        "# fast4g.ru geo files",
        "",
        f"Сборка: `{built_at}`  ",
        f"Коммит: `{commit}`",
        "",
        "## Категории",
        "",
        "| Файл | Категория | Записей |",
        "|---|---|---:|",
    ]
    for name, count in geosite_stats.items():
        lines.append(f"| `geosite.dat` | `{name}` | {count} |")
    for name, count in geoip_stats.items():
        lines.append(f"| `geoip.dat` | `{name}` | {count} |")
    lines.extend(
        [
            "",
            "## Использование",
            "",
            "```json",
            '"domain": ["geosite:russian-block"],',
            '"ip": ["geoip:russian-block"],',
            "```",
            "",
            "Готовые пресеты Happ лежат в ассетах: `HAPP-BLOCKED-ONLY.JSON`, `HAPP-WHITELIST.JSON`.",
            "",
            "Источники и лицензии перечислены в `NOTICE` основного репозитория.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="dist", help="output directory")
    parser.add_argument("--config", default="config/sources.json")
    parser.add_argument("--cache", default=".cache", help="download cache directory")
    parser.add_argument("--refresh", action="store_true", help="ignore cached downloads")
    parser.add_argument("--no-cache", action="store_true", help="disable download cache")
    args = parser.parse_args(argv)

    root = ROOT
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    cache_dir: Path | None
    if args.no_cache:
        cache_dir = None
    else:
        cache_dir = Path(args.cache)
        if not cache_dir.is_absolute():
            cache_dir = root / cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(root / args.config)
    built_at = utc_now()

    print("building geosite.dat ...")
    sites, geosite_stats, geosite_records = build_geosite(
        config, root, cache_dir, args.refresh
    )
    geosite_bytes = pb.build_geosite(sites)
    (out_dir / "geosite.dat").write_bytes(geosite_bytes)

    print("building geoip.dat ...")
    geoips, geoip_stats, geoip_records = build_geoip(
        config, root, cache_dir, args.refresh
    )
    geoip_bytes = pb.build_geoip(geoips)
    (out_dir / "geoip.dat").write_bytes(geoip_bytes)

    for site in sites:
        slug = site.code.lower()
        write_text_domains(out_dir / f"{slug}-domains.txt", site.domains)
    for code, networks in geoips:
        slug = code.lower()
        write_text_cidrs(out_dir / f"{slug}-ips.txt", networks)

    preset_config = default_preset_config(REPOSITORY)
    for filename, text in build_presets(preset_config).items():
        write_utf8(out_dir / filename, text)

    files = [
        path
        for path in out_dir.iterdir()
        if path.is_file() and path.name not in {"SHA256SUMS", "build-info.json", "RELEASE_NOTES.md"}
    ]

    build_info = {
        "schema": 1,
        "repository": REPOSITORY,
        "built_at": built_at,
        "commit": git_commit(),
        "categories": {
            "geosite": geosite_stats,
            "geoip": geoip_stats,
        },
        "sources": [asdict(record) for record in geosite_records + geoip_records],
        "files": {
            path.name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in files
        },
    }
    write_utf8(
        out_dir / "build-info.json",
        json.dumps(build_info, ensure_ascii=False, indent=2) + "\n",
    )

    write_utf8(
        out_dir / "RELEASE_NOTES.md",
        release_notes(geosite_stats, geoip_stats, built_at, build_info["commit"]),
    )

    all_assets = [
        path
        for path in out_dir.iterdir()
        if path.is_file() and path.name not in {"SHA256SUMS", "RELEASE_NOTES.md"}
    ]
    write_sha256sums(out_dir, all_assets)

    print()
    print("geosite.dat")
    for name, count in geosite_stats.items():
        print(f"  {name:<16} {count:>8}")
    print("geoip.dat")
    for name, count in geoip_stats.items():
        print(f"  {name:<16} {count:>8}")
    print()
    print(f"geosite.dat: {len(geosite_bytes):,} bytes")
    print(f"geoip.dat:   {len(geoip_bytes):,} bytes")
    print(f"output:      {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
