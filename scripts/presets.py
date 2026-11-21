"""Generation of ready-to-import Happ routing presets."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class PresetConfig:
    repository: str
    release_url: str
    mirror_url: str
    updated_at: int


def _base_preset(
    *,
    name: str,
    global_proxy: bool,
    direct_sites: list[str],
    direct_ip: list[str],
    proxy_sites: list[str],
    proxy_ip: list[str],
    base_url: str,
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
        "Geoipurl": f"{base_url}/geoip.dat",
        "Geositeurl": f"{base_url}/geosite.dat",
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


def _blocked_only(config: PresetConfig, base_url: str, name: str) -> dict:
    return _base_preset(
        name=name,
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
        base_url=base_url,
        config=config,
    )


def _whitelist(config: PresetConfig, base_url: str, name: str) -> dict:
    return _base_preset(
        name=name,
        global_proxy=True,
        direct_sites=["geosite:private", "geosite:whitelist"],
        direct_ip=["geoip:private", "geoip:whitelist"],
        proxy_sites=[],
        proxy_ip=[],
        base_url=base_url,
        config=config,
    )


def build_presets(config: PresetConfig) -> dict[str, str]:
    """Return ``{filename: json_text}`` for GitHub and jsDelivr variants."""

    presets = {
        "HAPP-BLOCKED-ONLY.JSON": _blocked_only(
            config, config.release_url, "BLOCKED-ONLY"
        ),
        "HAPP-WHITELIST.JSON": _whitelist(config, config.release_url, "WHITELIST"),
    }
    if config.mirror_url:
        presets["HAPP-BLOCKED-ONLY-JSDELIVR.JSON"] = _blocked_only(
            config, config.mirror_url, "BLOCKED-ONLY (jsDelivr)"
        )
        presets["HAPP-WHITELIST-JSDELIVR.JSON"] = _whitelist(
            config, config.mirror_url, "WHITELIST (jsDelivr)"
        )
    return {
        name: json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        for name, payload in presets.items()
    }


def default_preset_config(repository: str) -> PresetConfig:
    return PresetConfig(
        repository=repository,
        release_url=f"https://github.com/{repository}/releases/latest/download",
        mirror_url=f"https://cdn.jsdelivr.net/gh/{repository}@release",
        updated_at=int(time.time()),
    )
