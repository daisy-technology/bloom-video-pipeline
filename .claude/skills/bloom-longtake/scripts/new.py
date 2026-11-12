"""Start a 16:9 long-take Bloom project: the template with the iso and motion kits inlined, a script.md
skeleton for the chosen mode, and the Mitr font.

    uv run python .claude/skills/bloom-longtake/scripts/new.py scripts/<name> [--mode intro|demo|explainer|release]

Refuses to overwrite an existing scenes.html or script.md. Then replace the template's example stations
(script → voice → video) and the skeleton's lines with the subject's own (bloom-longtake, sections 2–4).
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
MOTION = Path.cwd() / "bloom" / "compose" / "assets"  # the motion and iso kits live in the Bloom package
FONTS = Path.cwd() / "scripts" / "no-internet-doc" / "fonts"  # Mitr, OFL

SKELETON = {  # scene ids and what each one is for; the lines are placeholders to rewrite
    "intro": [("hook", "~calm", "ปัญหาหรือคำสัญญาในประโยคเดียว"), ("what", "", "มันคืออะไร: ชื่อ กับนิยามหนึ่งบรรทัด"),
              ("does1", "", "ทำอะไรได้ ข้อหนึ่ง: ให้เห็นมันทำงาน"), ("does2", "", "ข้อสอง"), ("does3", "~bright", "ข้อสาม"),
              ("end +1.2", "", "คำถามกลับไปที่ผู้ชม หรือตัวอย่างของตอนต่อไป")],
    "demo": [("hook", "~calm", "ผลลัพธ์ที่จะได้ ก่อนเริ่ม"), ("open", "", "เปิดหน้าจอแรก"), ("step1", "", "คลิกแรก และสิ่งที่เปลี่ยน"),
             ("step2", "", "ขั้นที่สอง"), ("step3", "~bright", "ผลลัพธ์"), ("end +1.2", "", "คำถาม หรือตัวอย่างฟีเจอร์ถัดไป")],
    "explainer": [("hook", "~calm", "คำถามที่วิดีโอจะตอบ"), ("in", "", "สิ่งที่เข้าไป"), ("stage1", "", "ขั้นที่หนึ่งข้างใน"),
                  ("stage2", "", "ขั้นที่สอง"), ("out", "~bright", "สิ่งที่ออกมา"), ("end +1.2", "", "คำถาม หรือตัวอย่างตอนต่อไป")],
    "release": [("hook", "~bright", "เวอร์ชันใหม่ กับสิ่งที่ใหญ่ที่สุด"), ("new1", "", "ของใหม่ ข้อหนึ่ง ก่อนกับหลัง"),
                ("new2", "", "ข้อสอง"), ("new3", "", "ข้อสาม"), ("end +1.2", "", "ตัวอย่างของเวอร์ชันหน้า ตัดก่อนเฉลย")],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", type=Path)
    ap.add_argument("--mode", choices=sorted(SKELETON), default="intro")
    a = ap.parse_args()
    a.project.mkdir(parents=True, exist_ok=True)
    page, script = a.project / "scenes.html", a.project / "script.md"
    for f in (page, script):
        if f.exists():
            print(f"new: {f} exists; not overwriting", file=sys.stderr)
            return 1
    html = (HERE / "assets" / "template.html").read_text(encoding="utf-8")
    for marker, src in (("/*KIT:motion.css*/", MOTION / "motion.css"), ("//KIT:iso.js", MOTION / "iso.js"),
                        ("//KIT:motion.js", MOTION / "motion.js")):
        assert marker in html, marker
        html = html.replace(marker, src.read_text(encoding="utf-8"))
    page.write_text(html, encoding="utf-8")
    outline = "\n".join(f"     ## {sid}{' ' + mood if mood else ''}: {what}" for sid, mood, what in SKELETON[a.mode])
    lines = [f"# {a.project.name}", "",
             f"<!-- bloom-longtake, mode: {a.mode}. Render: uv run python -m bloom build {a.project} --size 1920x1080 --voice <voice>",
             f"     The scenes below are the template's working example (hello, voice, video). Rewrite them to this outline,",
             f"     and rename the sections and data-cam-<scene> keys in scenes.html to match:",
             outline + " -->", "",
             "## hello ~calm", "นี่คือบลูม ส่งสคริปต์ภาษาไทยเข้าไป ได้วิดีโอออกมา", "",
             "## voice", "บลูมพากย์ทุกฉากให้ แล้วจัดจังหวะภาพให้ตรงกับเสียง", "",
             "## video +1.2", "ได้วิดีโอพร้อมซับและเพลง แล้วคุณจะเล่าเรื่องอะไร", ""]
    script.write_text("\n".join(lines), encoding="utf-8")
    if FONTS.exists() and not (a.project / "fonts").exists():
        shutil.copytree(FONTS, a.project / "fonts")
    print(f"new: {page} and {script}: a working 3-scene example; rewrite it to the {a.mode} outline at the top of script.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
