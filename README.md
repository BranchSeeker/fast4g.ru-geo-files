# fast4g.ru geo files

Универсальные `geosite.dat` и `geoip.dat` для Xray/V2Ray/Happ/INCY: всё, что
заблокировано в РФ, отдельная категория `whitelist` для обхода белых списков и
отдельный YouTube.

Списки собираются ежедневно в 03:00 МСК и публикуются в rolling-релиз
[`latest`](https://github.com/BranchSeeker/fast4g.ru-geo-files/releases/latest).
Одни и те же файлы используются и для «умного» маршрута, где в прокси уходит
только заблокированное, и для серверов обхода белых списков.

## Скачать

| Файл | Ссылка |
|---|---|
| `geosite.dat` | https://github.com/BranchSeeker/fast4g.ru-geo-files/releases/latest/download/geosite.dat |
| `geoip.dat` | https://github.com/BranchSeeker/fast4g.ru-geo-files/releases/latest/download/geoip.dat |
| Пресет «только заблокированное» | https://github.com/BranchSeeker/fast4g.ru-geo-files/releases/latest/download/HAPP-BLOCKED-ONLY.JSON |
| Пресет «белые списки» | https://github.com/BranchSeeker/fast4g.ru-geo-files/releases/latest/download/HAPP-WHITELIST.JSON |
| Контрольные суммы | https://github.com/BranchSeeker/fast4g.ru-geo-files/releases/latest/download/SHA256SUMS |

## Категории

### `geosite.dat` (~2.5 МБ)

| Категория | Что внутри | Записей |
|---|---|---:|
| `russian-block` | домены, заблокированные в РФ (lite: AntiZapret + itdog) | ~124 000 |
| `whitelist` | домены, доступные при белых списках мобильного интернета | ~1 340 |
| `youtube` | YouTube / GoogleVideo | ~180 |
| `geoblock` | сервисы, которые сами ограничивают доступ из РФ | ~960 |
| `telegram` | Telegram | 26 |
| `github` | GitHub | 27 |
| `google-play` | Google Play / Android | 29 |
| `private` | локальные и служебные домены | 129 |

### `geoip.dat` (~0.5 МБ)

| Категория | Что внутри | Записей |
|---|---|---:|
| `russian-block` | подсети РКН + Meta/Twitter/Discord | ~16 800 |
| `whitelist` | CIDR белого списка (RoscomVPN + hxehex) | ~30 700 |
| `youtube` | AS36040, IPv4 + IPv6 | ~64 после схлопывания |
| `private` | приватные диапазоны | 15 |

`russian-block` и `youtube` пересекаются: YouTube есть в общем списке и отдельно.
Разделять маршруты удобно порядком правил.

## Две схемы маршрутизации

### 1. BLOCKED-ONLY — для обычных зарубежных серверов

В прокси уходит **только** заблокированное и проблемное, остальное — напрямую.
Это исправляет главную проблему DEFAULT-профилей, где в прокси попадает весь
легитимный зарубежный трафик.

```
final: direct
proxy:  geosite:russian-block, geosite:geoblock, geosite:youtube,
        geosite:telegram, geosite:github, geosite:google-play,
        geoip:russian-block, geoip:youtube
direct: geosite:whitelist, geosite:private, geoip:whitelist, geoip:private
```

### 2. WHITELIST — для серверов обхода белых списков

Напрямую идёт только белый список, всё остальное — через VPN.

```
final: proxy
direct: geosite:whitelist, geosite:private, geoip:whitelist, geoip:private
```

Оба пресета лежат в релизе: `HAPP-BLOCKED-ONLY.JSON` и `HAPP-WHITELIST.JSON`.
Ключевое отличие от RoscomVPN DEFAULT — `GlobalProxy: false` в BLOCKED-ONLY.

### Happ / INCY

1. Скачайте нужный `.JSON` из релиза.
2. Импортируйте его как профиль маршрутизации (Routing → Import) или замените
   `Geoipurl` / `Geositeurl` в своём профиле на ссылки выше.
3. Проверьте, что в профиле остались ваши `DirectSites` / `ProxySites`, если вы
   добавляли свои.

### Xray / V2Ray

```json
{
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
      {
        "type": "field",
        "domain": ["geosite:private", "geosite:whitelist"],
        "outboundTag": "direct"
      },
      {
        "type": "field",
        "ip": ["geoip:private", "geoip:whitelist"],
        "outboundTag": "direct"
      },
      {
        "type": "field",
        "domain": [
          "geosite:russian-block",
          "geosite:geoblock",
          "geosite:youtube",
          "geosite:telegram",
          "geosite:github",
          "geosite:google-play"
        ],
        "outboundTag": "proxy"
      },
      {
        "type": "field",
        "ip": ["geoip:russian-block", "geoip:youtube"],
        "outboundTag": "proxy"
      }
    ]
  }
}
```

Первый outbound в конфиге должен быть `direct`, второй — `proxy`, тогда
`final` будет direct. Если файлы лежат не в asset-каталоге Xray, используйте
`ext:`:

```json
"domain": ["ext:geosite.dat:russian-block"],
"ip": ["ext:geoip.dat:russian-block"]
```

Для `ext:` файл ищется в `XRAY_LOCATION_ASSET` (или рядом с бинарником Xray).

### Совместимость с RoscomVPN

Файлы можно подставить в существующий профиль RoscomVPN, заменив только
`Geoipurl` и `Geositeurl`. Категории `whitelist`, `youtube`, `telegram`,
`github`, `google-play`, `private` совпадают по смыслу. Категории
`russian-block` в RoscomVPN нет — её нужно добавить в `ProxySites` /
`ProxyIp` самостоятельно.

## Источники

| Источник | Что даёт |
|---|---|
| [AntiZapret](https://antizapret.prostovpn.org/domains-export.txt) | домены `russian-block` |
| [Antifilter.Download](https://antifilter.download/list/allyouneed.lst) | подсети `geoip:russian-block` |
| [itdoginfo/allow-domains](https://github.com/itdoginfo/allow-domains) | домены itdog, YouTube, geoblock, подсети сервисов |
| [RoscomVPN Geosite](https://github.com/hydraponique/roscomvpn-geosite) (MIT) | `whitelist`, `youtube`, `geoblock`, сервисные категории |
| [russia-mobile-internet-whitelist](https://github.com/hxehex/russia-mobile-internet-whitelist) (MIT) | `whitelist` домены и CIDR |
| [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community) | дополнительные YouTube-домены |
| [RIPE Stat AS36040](https://stat.ripe.net/data/announced-prefixes/data.json?resource=AS36040) | `geoip:youtube` |

Подробная атрибуция и лицензии — в [NOTICE](NOTICE).

> [!IMPORTANT]
> Для публикации релиза в GitHub Actions должны быть разрешены права на запись:
> Settings → Actions → General → Workflow permissions → **Read and write
> permissions**. Если этого не сделать, сборка пройдёт, но `gh release`
> завершится ошибкой.

## Обновление

GitHub Actions запускается:

- ежедневно в 00:00 UTC (03:00 МСК);
- вручную через `workflow_dispatch`;
- при пуше в `main`, если изменились скрипты, конфиг, данные или workflow.

Сборка проверяется unit-тестами, обратным разбором `.dat`, проверкой ссылок
пресетов на существующие категории и smoke-тестом настоящим Xray. Если
источник отдал меньше данных, чем ожидалось, сборка падает, а прошлый релиз
остаётся на месте.

## Разработка

Нужен Python 3.11+ (в CI — 3.12), сторонних зависимостей нет.

```bash
python -m unittest discover -s tests -t . -v
python -m scripts.build --out dist
python -m scripts.verify dist
python -m scripts.smoke_xray dist
```

Полезные файлы:

- `config/sources.json` — URL и форматы источников;
- `data/exclude-domains.txt` — что принудительно убрать из `russian-block`;
- `data/extra-domains.txt` — что добавить в `russian-block`;
- `data/extra-whitelist-domains.txt` — что добавить в `whitelist`;
- `data/youtube-ips.txt` — снапшот AS36040 на случай недоступности RIPE.

## Ограничения

- Белый список зависит от оператора и региона. Объединение RoscomVPN + hxehex
  даёт широкое покрытие, но не гарантирует, что каждый IP открыт у вашего
  оператора.
- `russian-block` — lite-список: в нём есть мёртвые и парковочные домены.
  Полный реестр РКН (1.8 млн доменов, ~42 МБ) сюда намеренно не включён.
- `geoip:russian-block` и `geoip:whitelist` — IPv4; IPv6 есть только у
  `geoip:youtube`.
- `geoip:youtube` — best-effort: Google Global Cache внутри российских сетей
  в AS36040 не входит, основная защита — доменная категория `youtube`.
- Это `.dat` для Xray/V2Ray-совместимых клиентов. Mihomo (`.mrs`) и sing-box
  (`.srs`) в этот репозиторий пока не входят.

## Лицензия

Код — MIT, см. [LICENSE](LICENSE). Данные — по лицензиям источников, см.
[NOTICE](NOTICE).
