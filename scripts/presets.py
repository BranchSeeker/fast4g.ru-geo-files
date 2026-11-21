"""Generation of ready-to-import Happ routing presets."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class PresetConfig:
    repository: str
    release_url: str
    updated_at: int


def _base_preset(
    *,
    name: str,
    global_proxy: bool,
    direct_sites: list[str],
    direct_ip: list[str],
    proxy_sites: list[str],
    proxy_ip: list[str],
    config: PresetConfig,
) -> dict:
    return {
        "Name": name,
        "GlobalProxy": global_proxy,
        "UseChunkFiles": "true",
        "RemoteDns": "8.8.8.8",
        "DomesticDns": "77.88.8.8",
        "RemoteDNSType": "DoH",
        "RemoteDNSDomain": "https://8.8.8.8/dns-query",
        "RemoteDNSIP": "8.8.8.8",
        "DomesticDNSType": "DoH",
        "DomesticDNSDomain": "https://77.88.8.8/dns-query",
        "DomesticDNSIP": "77.88.8.8",
        "Geoipurl": f"{config.release_url}/geoip.dat",
        "Geositeurl": f"{config.release_url}/geosite.dat",
        "LastUpdated": str(config.updated_at),
        "DnsHosts": {
            "lkfl2.nalog.ru": "213.24.64.175",
            "lknpd.nalog.ru": "213.24.64.181",
        },
        "RouteOrder": "block-proxy-direct",
        "DirectSites": direct_sites,
        "DirectIp": direct_ip,
        "ProxySites": proxy_sites,
        "ProxyIp": proxy_ip,
        "BlockSites": [],
        "BlockIp": [],
        "DomainStrategy": "IPIfNonMatch",
        "FakeDNS": False,
    }


def build_presets(config: PresetConfig) -> dict[str, str]:
    """Return ``{filename: json_text}`` for the two supported presets."""

    blocked_only = _base_preset(
        name="BLOCKED-ONLY",
        global_proxy=False,
        direct_sites=["geosite:private", "geosite:whitelist"],
        direct_ip=["geoip:private", "geoip:whitelist"],
        proxy_sites=[
            "geosite:russian-block",
            "geosite:geoblock",
            "geosite:youtube",
            "geosite:telegram",
            "geosite:github",
            "geosite:google-play",
        ],
        proxy_ip=["geoip:russian-block", "geoip:youtube"],
        config=config,
    )

    whitelist = _base_preset(
        name="WHITELIST",
        global_proxy=True,
        direct_sites=["geosite:private", "geosite:whitelist"],
        direct_ip=["geoip:private", "geoip:whitelist"],
        proxy_sites=[],
        proxy_ip=[],
        config=config,
    )

    return {
        "HAPP-BLOCKED-ONLY.JSON": json.dumps(blocked_only, ensure_ascii=False, indent=2) + "\n",
        "HAPP-WHITELIST.JSON": json.dumps(whitelist, ensure_ascii=False, indent=2) + "\n",
    }


def default_preset_config(repository: str) -> PresetConfig:
    return PresetConfig(
        repository=repository,
        release_url=f"https://github.com/{repository}/releases/latest/download",
        updated_at=int(time.time()),
    )
