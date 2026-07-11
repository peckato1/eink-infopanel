# Frame format for e-paper (GDEY116Z91, 3-colour)

The firmware downloads a single binary frame over HTTP GET and renders it.
This document describes the **exact response body format** that the server must produce.

## Endpoint (image)

- **HTTP GET** to the URL stored in `secrets.h` as `SECRET_IMAGE_URL` (e.g. `http://192.168.1.10:8080/frame.bin`).
- Response: `200 OK`, body = raw binary data (see below).
- Recommended headers: `Content-Type: application/octet-stream`, `Content-Length: 153600`.
- No encoding, no in-body header — just the raw planes.

### Header: when to wake up next

- **`X-Next-Wakeup: <epoch>`** — absolute Unix timestamp (seconds) of the next wake-up.
  The firmware computes the sleep duration as `X-Next-Wakeup − Date`, where `Date` is the standard HTTP response header (RFC 1123, GMT) — the board therefore **does not need NTP or its own RTC**.
- If `X-Next-Wakeup` is missing, `Date` cannot be parsed, or the resulting duration is out of range, the firmware falls back to **1 h** and clamps the value to `[60 s, 24 h]`.

Example response:

```
200 OK
Content-Type: application/octet-stream
Content-Length: 153600
Date: Wed, 09 Jul 2026 12:00:00 GMT
X-Next-Wakeup: 1783166400

<153600 B of planes>
```

## Endpoint (telemetry)

- **HTTP POST** to `secrets.h` → `SECRET_TELEMETRY_URL` (empty string = disabled).
- Best-effort: short timeout (~2.5 s), the **response is ignored** — a failed POST does not affect rendering or sleep.
- Body `application/json`, sent **after** rendering:

```json
{
  "rssi": -67,
  "heap": 108231,
  "render_ok": true,
  "wake": "timer",
  "vbat": 3.92
}
```

- `render_ok` — whether the full frame was downloaded and a display refresh was issued.
- `wake` — `"timer"` (deep-sleep timer expiry) or `"poweron"` (first boot / reset).
- `vbat` — battery voltage in V; the key is **absent** when the board has no battery measurement.

## Dimensions and orientation

- The panel is natively **960 × 640 px** (landscape).
  The firmware writes directly in this native orientation (`writeImage` ignores rotation).
- The display is physically mounted **portrait**, so the server should render a **640 × 960 (portrait)** canvas and then **rotate it 90°** into the native 960 × 640.
  Verify the rotation direction on your board: if the image appears upside-down, rotate the other way (or add 180°).

## Colours

- Only **3 hard colours**: white, black, red.
  No shades.
- Continuous-tone content / photos → **dithering** (Floyd–Steinberg) during quantisation on the server side.
- Text and icons → no dithering (crisp edges), otherwise they look grainy.

## Body structure

The frame is split into **8 horizontal strips of 80 rows each** (top to bottom).
For **each strip**, two 1 bpp planes follow in sequence:

```
[strip 0: black plane (9600 B)][strip 0: red plane (9600 B)]
[strip 1: black plane (9600 B)][strip 1: red plane (9600 B)]
...
[strip 7: black plane (9600 B)][strip 7: red plane (9600 B)]
```

- One strip of one plane = 80 rows × **120 bytes per row** = 9 600 B.
- **Total: 8 × (9 600 + 9 600) = 153 600 B.**

### Bit layout within a plane

- One row = 120 bytes, **MSB (0x80) = leftmost pixel**.
  Pixel `x`: byte = `row * 120 + x / 8`, mask = `0x80 >> (x % 8)`.
- Rows run top to bottom (row 0 = top).

### Bit polarity (important!)

Matches the native GxEPD2 format:

| Pixel colour | bit in **black** plane | bit in **red** plane |
|--------------|:----------------------:|:--------------------:|
| white        | 1                      | 1                    |
| black        | 0                      | 1                    |
| red          | 1                      | 0                    |

- A red pixel requires black bit `1` (white) and red bit `0`.
- An all-white blank frame = 153 600 bytes of `0xFF`.

## Reference packing (Python + Pillow)

```python
from PIL import Image

W, H = 960, 640          # native (landscape)
STRIP_H = 80
STRIDE = W // 8          # 120

def build_frame(design_portrait: Image.Image) -> bytes:
    # portrait 640x960 -> native 960x640 (rotate 90° CW; if the result is
    # upside-down use rotate(90) or add .rotate(180))
    img = design_portrait.rotate(-90, expand=True).convert("RGB")
    assert img.size == (W, H), img.size

    # quantise to palette {white=0, black=1, red=2}
    pal = Image.new("P", (1, 1))
    pal.putpalette([255, 255, 255,  0, 0, 0,  255, 0, 0] + [0, 0, 0] * 253)
    q = img.quantize(palette=pal, dither=Image.FLOYDSTEINBERG)
    px = q.load()

    # pack strip by strip: for each strip black plane then red plane
    body = bytearray()
    for sy in range(0, H, STRIP_H):
        black = bytearray(b"\xff" * (STRIDE * STRIP_H))
        red   = bytearray(b"\xff" * (STRIDE * STRIP_H))
        for row in range(STRIP_H):
            y = sy + row
            base = row * STRIDE
            for x in range(W):
                c = px[x, y]                 # 0 white, 1 black, 2 red
                if c == 0:
                    continue
                mask = 0x80 >> (x & 7)
                idx = base + (x >> 3)
                if c == 1:
                    black[idx] &= ~mask & 0xFF   # black: black bit 0
                else:
                    red[idx] &= ~mask & 0xFF     # red: red bit 0
        body += black + red

    assert len(body) == 153600, len(body)
    return bytes(body)
```

The server simply returns `build_frame(...)` as the GET response body.

## Firmware behaviour (for context)

- The board wakes up (deep-sleep timer), connects to WiFi, issues the GET, streams strips via `writeImage`, triggers a single full refresh, and goes back to sleep.
- On error (WiFi / HTTP / timeout) it **does not refresh** — the last image stays on the display and it retries after the fallback sleep interval.
- Strip order (top to bottom) matches the stream; the firmware reads sequentially and never buffers more than one strip in RAM.
