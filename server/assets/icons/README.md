# Weather icons

Icons are from [Lucide](https://lucide.dev) (ISC License), pinned to the
version recorded in `svg/VERSION`.

- `svg/*.svg` — original Lucide sources (black stroke, `currentColor`).
- `*.png` — 128×128 black-on-transparent masters, rasterized from the SVGs.

The renderer (`render.py`) loads a PNG master once, scales it to the needed
size and tints it via its alpha channel (see `_icon`). The mapping from a
weather condition string to an icon name lives in `_CONDITION_ICONS`.

## Regenerate the PNG masters

```sh
cd assets/icons
for f in svg/*.svg; do
  rsvg-convert -w 128 -h 128 "$f" -o "$(basename "$f" .svg).png"
done
```

## Add / update icons

Download more Lucide SVGs into `svg/` (keep the pinned version) and re-run the
command above:

```sh
VER=$(cat svg/VERSION)
curl -sSLf "https://unpkg.com/lucide-static@$VER/icons/<name>.svg" -o "svg/<name>.svg"
```
