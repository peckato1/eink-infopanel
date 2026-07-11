"""Firmware wire format.

Packs a portrait design image into the interleaved black/red strip format the firmware draws directly.
See ``docs/frame-format.md`` for the byte layout.
"""

from __future__ import annotations

from PIL import Image

from .config import PanelSpec

# 3-color panel palette: white=0, black=1, red=2 (index order matters).
_PALETTE = [255, 255, 255, 0, 0, 0, 255, 0, 0] + [0, 0, 0] * 253


def pack_frame(design: Image.Image, panel: PanelSpec) -> bytes:
    """Pack a portrait design image into the native strip format.

    The design is rotated to native landscape, quantized to the 3-color panel palette, and emitted as interleaved black/red strips.
    """
    img = design.rotate(-90, expand=True).convert("RGB")
    if img.size != (panel.native_w, panel.native_h):
        raise ValueError(
            f"rotated design is {img.size}, expected {(panel.native_w, panel.native_h)}"
        )

    palette = Image.new("P", (1, 1))
    palette.putpalette(_PALETTE)
    # No dithering: the design is text, lines, solid fills and line icons — not
    # photos — so nearest-color thresholding keeps anti-aliased edges crisp
    # instead of scattering them into speckle on the 3-color panel.
    quantized = img.quantize(palette=palette, dither=Image.Dither.NONE)
    px = quantized.load()

    stride, strip_h = panel.stride, panel.strip_h
    plane_bytes = stride * strip_h

    body = bytearray()
    for sy in range(0, panel.native_h, strip_h):
        black = bytearray(b"\xff" * plane_bytes)
        red = bytearray(b"\xff" * plane_bytes)
        for row in range(strip_h):
            y = sy + row
            base = row * stride
            for x in range(panel.native_w):
                c = px[x, y]
                if c == 0:  # white — leave both planes set
                    continue
                mask = 0x80 >> (x & 7)
                idx = base + (x >> 3)
                if c == 1:  # black
                    black[idx] &= ~mask & 0xFF
                else:  # red
                    red[idx] &= ~mask & 0xFF
        body += black + red

    if len(body) != panel.frame_bytes:
        raise AssertionError(f"packed {len(body)} bytes, expected {panel.frame_bytes}")
    return bytes(body)
