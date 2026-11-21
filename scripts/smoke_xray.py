"""Smoke-test generated geo files with a real Xray binary."""

from __future__ import annotations

import argparse
import json
import os
import platform
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

from .fetch import fetch

XRAY_URLS = {
    "windows": "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-windows-64.zip",
    "linux": "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip",
}


def _platform_key() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    raise RuntimeError(f"unsupported platform for smoke test: {sys.platform}")


def ensure_xray(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    binary_name = "xray.exe" if _platform_key() == "windows" else "xray"
    binary = cache_dir / binary_name
    if binary.is_file():
        return binary

    archive = cache_dir / "xray.zip"
    if not archive.is_file():
        url = XRAY_URLS[_platform_key()]
        print(f"downloading {url} ...")
        result = fetch(url, timeout=120)
        archive.write_bytes(result.data)

    with zipfile.ZipFile(archive) as zf:
        zf.extractall(cache_dir)

    if not binary.is_file():
        # Some releases keep the binary in a subdirectory.
        matches = list(cache_dir.rglob(binary_name))
        if not matches:
            raise RuntimeError("xray binary not found in archive")
        binary = matches[0]

    if _platform_key() == "linux":
        binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
    return binary


def make_config(dist: Path) -> dict:
    # Xray splits ext:<file>:<category> on ":", so absolute Windows paths
    # (C:\...) are unusable. Relative names plus cwd=dist work everywhere.
    geosite = "geosite.dat"
    geoip = "geoip.dat"
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "listen": "127.0.0.1",
                "port": 10809,
                "protocol": "socks",
                "settings": {"udp": True},
            }
        ],
        "outbounds": [
            {"protocol": "freedom", "tag": "direct"},
            {"protocol": "blackhole", "tag": "proxy"},
        ],
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "rules": [
                {
                    "type": "field",
                    "domain": [
                        f"ext:{geosite}:whitelist",
                        f"ext:{geosite}:private",
                    ],
                    "outboundTag": "direct",
                },
                {
                    "type": "field",
                    "ip": [f"ext:{geoip}:whitelist", f"ext:{geoip}:private"],
                    "outboundTag": "direct",
                },
                {
                    "type": "field",
                    "domain": [
                        f"ext:{geosite}:russian-block",
                        f"ext:{geosite}:youtube",
                        f"ext:{geosite}:geoblock",
                        f"ext:{geosite}:telegram",
                        f"ext:{geosite}:github",
                        f"ext:{geosite}:google-play",
                    ],
                    "outboundTag": "proxy",
                },
                {
                    "type": "field",
                    "ip": [
                        f"ext:{geoip}:russian-block",
                        f"ext:{geoip}:youtube",
                    ],
                    "outboundTag": "proxy",
                },
            ],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", nargs="?", default="dist")
    parser.add_argument("--cache", default=".cache")
    args = parser.parse_args(argv)

    dist = Path(args.dist).resolve()
    cache = Path(args.cache).resolve()
    for name in ("geosite.dat", "geoip.dat"):
        if not (dist / name).is_file():
            raise RuntimeError(f"missing {dist / name}")

    binary = ensure_xray(cache)
    config_path = cache / "xray-smoke.json"
    config_path.write_text(
        json.dumps(make_config(dist), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["XRAY_LOCATION_ASSET"] = str(dist)

    print(f"running {binary.name} -test ...")
    result = subprocess.run(
        [str(binary), "run", "-test", "-c", str(config_path)],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        cwd=str(dist),
    )
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        print(output, file=sys.stderr)
        raise RuntimeError(f"xray smoke test failed with exit code {result.returncode}")
    if "Configuration OK" not in output and "test" not in output.lower():
        # Older Xray builds may not print a marker; exit code is authoritative.
        print(output.strip())
    print("xray smoke test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
