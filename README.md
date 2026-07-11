# ESP E-Paper Dashboard

A self-hosted dashboard for a **LaskaKit ESPink** (ESP32) driving a **GDEY116Z91** 960×640 three-colour e-paper display.
The ESP32 wakes up on a schedule, fetches a pre-rendered bitmap from the server, displays it, and goes back to deep sleep until the next server-supplied wake-up time.

```
┌─────────────────────┐          HTTP          ┌──────────────────────┐
│  server/            │  ◄────────────────────  │  esp-controller/     │
│  Flask + Pillow     │   GET /api/v1/image.bin │  ESP32 + GxEPD2      │
│  calendar + weather │  ─────────────────────► │  GDEY116Z91 e-paper  │
└─────────────────────┘   X-Next-Wakeup header  └──────────────────────┘
```

The server renders a portrait dashboard (calendar, weather, sun times) onto a 640×960 canvas, rotates it into the panel's native 960×640, and packs it into a 153 600 B binary frame.
The firmware streams that frame to the display controller in strips, then enters deep sleep until the server-supplied wake-up timestamp.

## Repository layout

```
esp/
├── server/            Python server (Flask) — rendering + HTTP API
├── esp-controller/    Arduino/PlatformIO firmware
└── docs/
    └── frame-format.md  Wire format spec (bitmap encoding, HTTP headers)
```

## Hardware

| Component | Detail |
|-----------|--------|
| MCU board | LaskaKit ESPink (ESP32-WROOM-32) |
| Display   | GDEY116Z91 — 960×640, 3-colour (black / white / red), SSD1677 |
| Battery   | LiPo via resistive divider on GPIO 34 (`BAT_DIVIDER = 2.0`); optional, verify on your board |

### Pin mapping (firmware)

| Signal  | GPIO |
|---------|------|
| EPD_PWR | 2    |
| EPD_CS  | 5    |
| EPD_DC  | 17   |
| EPD_RST | 16   |
| EPD_BUSY| 4    |
| BAT_ADC | 34   |

## Quick start

### 1. Server

Requires [uv](https://docs.astral.sh/uv/).

```sh
cd server/
uv sync --extra dev     # create .venv and install all deps
cp config.example.toml config.toml
$EDITOR config.toml     # fill in calendars, VictoriaMetrics, etc.
uv run flask --app wsgi:app --debug run --host 0.0.0.0 --port 8080
```

Open `http://localhost:8080/api/v1/preview` in a browser to see the current rendering as a PNG.

### 2. Firmware

Requires the [PlatformIO CLI](https://docs.platformio.org/en/latest/core/installation/) or the [PlatformIO IDE extension](https://platformio.org/install/ide?install=vscode) for VS Code.

```sh
cd esp-controller/
cp src/secrets.h.example src/secrets.h
$EDITOR src/secrets.h        # fill in WiFi credentials and server URLs
pio run -t upload            # compile and flash over USB
```

On LaskaKit ESPink you may need to hold the BOOT button during the upload if the board doesn't enter flashing mode automatically.
The `reset.py` script handles the reset sequence on boards that support it.

---

# Server

Flask server that renders a weather + calendar dashboard as a packed bitmap and serves it over HTTP to the firmware client.
The firmware fetches `/api/v1/image.bin` on every wake-up, streams the bitmap to the display, then sleeps until the next scheduled refresh.

## Configuration

All settings, secrets, and deployment-specific values live in **`config.toml`** (gitignored).
`config.example.toml` documents every option with inline comments.
A missing file is fine, the server starts with development defaults and placeholder data.

`DASHBOARD_CONFIG` overrides the path to the config file.

### Calendar feeds (ICS)

```toml
[[calendars]]
label = "P"          # single-character badge; omit for no badge
url = "https://calendar.google.com/calendar/ical/…/basic.ics"
```

### CalDAV (e.g. Fastmail)

```toml
[[caldav]]
url = "https://caldav.fastmail.com/"
username = "you@fastmail.com"
password = "app-password"          # use an app-specific password
[[caldav.calendars]]
name = "Personal"
label = "P"
```

### Live weather (VictoriaMetrics)

```toml
[victoriametrics]
url = "http://victoria.lan:8428"
temp_selector = 'ws90_temperature_celsius{id="15132"}'
rain_selector  = "ws90_rain_m"
```

### Wake policy

```toml
[wake]
interval_s  = 1800      # refresh every 30 min during the day
align       = true      # snap to :00/:30 instead of drifting
quiet_start = "23:00"   # sleep through quiet hours
quiet_end   = "06:00"
```

**`align = true`** snaps wake-ups to the `interval_s` grid measured from local midnight, so the schedule is fixed regardless of when the device last woke.
For `interval_s = 1800` the grid is 00:00, 00:30, 01:00, … and stays that way every day.
Any arbitrary interval works — e.g. `interval_s = 3333` produces a grid at 00:55:33, 01:51:06, 02:46:39, … with the last slot of the day at 23:08:45, after which the firmware wakes just after midnight and the grid resets.

**`align = false`** simply adds `interval_s` to the current time on each wake-up, so the schedule slowly drifts over time.

Either way the device never sleeps blindly past local midnight: if the next aligned slot would land after 00:00, the firmware is woken at 00:00:01 instead, so the day-based dashboard layout flips over promptly.

### Telemetry forwarding

```toml
[telemetry]
url    = "http://victoria.lan:8428"
device = "dashboard"
```

Exported metrics: `esp_rssi_dbm`, `esp_free_heap_bytes`, `esp_battery_volts`, `esp_render_ok`, `esp_wake_info{reason=…}`, `esp_sleep_interval_seconds`, `esp_last_seen_seconds`.

## API

| Method | Path                   | Description                              |
|--------|------------------------|------------------------------------------|
| GET    | `/api/v1/image.bin`    | Packed frame for the firmware (`Content-Type: application/octet-stream`), with `X-Next-Wakeup` header (Unix timestamp) |
| GET    | `/api/v1/preview`      | Current rendering as PNG (for humans)    |
| POST   | `/api/v1/telemetry`    | Device telemetry sink (JSON body)        |

## Tests

```sh
uv run pytest
```

## Production deployment

```sh
uv add gunicorn                     # add to project deps
uv run gunicorn wsgi:app -b 0.0.0.0:8080
```

Or point any WSGI server at the `app` object in `wsgi.py`.

## Grafana

`grafana/esp-telemetry.json` is an importable dashboard for monitoring device health metrics forwarded via the telemetry endpoint.

---

# Firmware

Arduino/ESP32 firmware for the LaskaKit ESPink. On each wake-up the device:

1. Connects to WiFi
2. Fetches a packed bitmap from the dashboard server (`/api/v1/image.bin`)
3. Streams the image to the e-paper controller in strips
4. Posts a telemetry report to the server
5. Reads the `X-Next-Wakeup` response header and enters deep sleep until then

## Secrets

`secrets.h` is gitignored. The four constants to fill in:

```cpp
SECRET_WIFI_ESSID       // network name
SECRET_WIFI_PASSWORD    // WiFi password
SECRET_API_PREFIX       // http://<server-ip>:<port> — firmware appends /api/v1/…
```

## Serial monitor

```sh
pio device monitor         # 115200 baud; stack traces are decoded automatically
```

Crash dumps are decoded in place thanks to `monitor_filters = esp32_exception_decoder` in `platformio.ini`.

## Battery monitoring

`BAT_ADC_PIN 34` reads the battery voltage through a resistive divider.
`BAT_DIVIDER 2.0` must match the actual ratio on your board — if `esp_battery_volts` in the server telemetry looks wrong, measure the real divider and update the constant.
Comment out the `#define BAT_ADC_PIN` block entirely if your board has no divider.

## Sleep and wake policy

The server's `X-Next-Wakeup` response header carries a Unix timestamp.
The firmware computes `sleep_seconds = next_wakeup - now` (clamped to `MIN_SLEEP_SECONDS`…`MAX_SLEEP_SECONDS`) and calls `esp_deep_sleep`.

If the header is absent or the fetch fails the device falls back to `DEFAULT_SLEEP_SECONDS` (1800 s).

## Libraries

| Library | Version |
|---------|---------|
| [GxEPD2](https://github.com/ZinggJM/GxEPD2) | ^1.5.9 |
| [Adafruit GFX](https://github.com/adafruit/Adafruit-GFX-Library) | ^1.11.9 |

---

## Frame format

See [`docs/frame-format.md`](docs/frame-format.md) for the binary frame encoding, HTTP headers, colour bit polarity, and reference Python packing code.
