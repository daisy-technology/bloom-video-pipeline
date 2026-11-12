"""Icons for a Bloom page, saved once as files, so every computer renders the same picture.

    uv run python .claude/skills/bloom-visual/scripts/icons.py scripts/<project> volcano=🌋 island=🏝️ fire=🔥
    uv run --with pilmoji --with emoji python .claude/skills/bloom-visual/scripts/icons.py scripts/<project> --png rice=🍚

Default: <project>/icons/<name>.svg, the Twemoji vector artwork (CC-BY 4.0), sharp at any size on a
1080-wide frame. Use them as <img src="icons/volcano.svg">. `--png` draws <name>.png through the
web-asset-generator skill (its emoji_utils), for places that need a bitmap; it upsamples Twemoji's
72 px images, so keep PNG icons under about 120 px on screen.
An emoji typed into the page instead is drawn by whatever emoji font the rendering computer has (Apple
on a Mac, Segoe on Windows, none on a bare Linux box), so the same video looks different, or shows
empty boxes, depending on where it was rendered.

It renders with the web-asset-generator skill's emoji_utils.generate_emoji_icon when that skill is
found (BLOOM_WEB_ASSETS, or ~/.claude/skills/web-asset-generator, or this repo's .claude/skills), and
otherwise with pilmoji directly, which is what that skill uses underneath.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def renderer():
    candidates = [os.environ.get("BLOOM_WEB_ASSETS", ""), str(Path.home() / ".claude/skills/web-asset-generator"),
                  str(Path.cwd() / ".claude/skills/web-asset-generator")]
    for c in candidates:
        scripts = Path(c) / "scripts"
        if c and (scripts / "emoji_utils.py").exists():
            sys.path.insert(0, str(scripts))
            from emoji_utils import generate_emoji_icon  # noqa: E402
            return generate_emoji_icon, f"web-asset-generator ({c})"
    from PIL import Image
    from pilmoji import Pilmoji

    def draw(ch: str, size: tuple[int, int], bg=None):
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        em = int(min(size) * 0.8)
        from PIL import ImageFont
        font = ImageFont.load_default(size=em)
        with Pilmoji(img) as p:
            p.text(((size[0] - em) // 2, (size[1] - em) // 2), ch, font=font, emoji_scale_factor=1.0)
        return img
    return draw, "pilmoji"


TWEMOJI = "https://cdn.jsdelivr.net/gh/jdecked/twemoji@latest/assets/svg/{}.svg"


def svg(ch: str) -> bytes:
    """Twemoji's SVG for one emoji: file names are its code points in hex, usually without U+FE0F."""
    import urllib.error
    import urllib.request

    cps = [f"{ord(c):x}" for c in ch]
    tried = []
    for name in ("-".join(c for c in cps if c != "fe0f"), "-".join(cps)):
        if name in tried:
            continue
        tried.append(name)
        try:
            with urllib.request.urlopen(urllib.request.Request(TWEMOJI.format(name), headers={"User-Agent": "bloom"}), timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError:
            continue
    raise SystemExit(f"icons: no Twemoji artwork for {ch!r} (tried {', '.join(tried)})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", type=Path)
    ap.add_argument("icons", nargs="+", help="name=emoji")
    ap.add_argument("--size", type=int, default=256, help="PNG size")
    ap.add_argument("--png", action="store_true", help="bitmaps through web-asset-generator instead of SVG")
    a = ap.parse_args()
    out = a.project / "icons"
    out.mkdir(parents=True, exist_ok=True)
    if not a.png:
        for pair in a.icons:
            name, _, ch = pair.partition("=")
            if not ch:
                raise SystemExit(f"icons: {pair!r} should be name=emoji")
            (out / f"{name}.svg").write_bytes(svg(ch))
            print(f"  {out / (name + '.svg')}  {ch}")
        print("Twemoji by Twitter / jdecked, CC-BY 4.0: credit it in the video's description")
        return 0
    draw, how = renderer()
    for pair in a.icons:
        name, _, ch = pair.partition("=")
        if not ch:
            raise SystemExit(f"icons: {pair!r} should be name=emoji")
        img = draw(ch, (a.size, a.size), None)
        bbox = img.getbbox()  # trim the padding, then centre on a square canvas again
        if bbox:
            from PIL import Image
            crop = img.crop(bbox)
            side = max(crop.size)
            sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            sq.paste(crop, ((side - crop.size[0]) // 2, (side - crop.size[1]) // 2))
            img = sq.resize((a.size, a.size))
        img.save(out / f"{name}.png")
        print(f"  {out / (name + '.png')}  {ch}")
    print(f"drawn with {how}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
