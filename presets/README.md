# Пресеты Happ

В релизе лежат четыре готовых профиля. Они генерируются при каждой сборке из
`scripts/presets.py`, поэтому `Geoipurl`/`Geositeurl` всегда указывают на
актуальный релиз или зеркало.

| Файл | `GlobalProxy` | Откуда geo-файлы |
|---|---|---|
| `HAPP-BLOCKED-ONLY.JSON` | `false` | GitHub Release |
| `HAPP-WHITELIST.JSON` | `true` | GitHub Release |
| `HAPP-BLOCKED-ONLY-JSDELIVR.JSON` | `false` | jsDelivr (`@release`) |
| `HAPP-WHITELIST-JSDELIVR.JSON` | `true` | jsDelivr (`@release`) |

BLOCKED-ONLY: в прокси только `russian-block`, `geoblock`, `youtube`,
`telegram`, `github`, `google-play`; остальное напрямую. WHITELIST: напрямую
только `whitelist` + `private`, остальное через VPN.

## BLOCKED-ONLY

Профиль для обычных зарубежных серверов. Главное отличие от RoscomVPN DEFAULT:
`GlobalProxy: false`, поэтому легитимный трафик не уходит в прокси.

- `DirectSites`: `geosite:private`, `geosite:whitelist`
- `DirectIp`: `geoip:private`, `geoip:whitelist`
- `ProxySites`: `geosite:russian-block`, `geosite:geoblock`, `geosite:youtube`,
  `geosite:telegram`, `geosite:github`, `geosite:google-play`
- `ProxyIp`: `geoip:russian-block`, `geoip:youtube`

## WHITELIST

Профиль для серверов, предназначенных для обхода белых списков.

- `DirectSites`: `geosite:private`, `geosite:whitelist`
- `DirectIp`: `geoip:private`, `geoip:whitelist`
- `ProxySites` / `ProxyIp`: пусто, всё остальное — через прокси

## Импорт

1. Скачайте JSON из последнего релиза.
2. В Happ откройте Routing → Import и выберите файл (или вставьте JSON).
3. Убедитесь, что в профиле остались ваши собственные правила, если вы
   добавляли их вручную.

`LastUpdated` — Unix timestamp сборки. `DnsHosts` содержит записи для
`lkfl2.nalog.ru` и `lknpd.nalog.ru`, как в профилях RoscomVPN.
