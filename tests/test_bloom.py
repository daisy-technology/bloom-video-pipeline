"""Run: python tests/test_bloom.py (or pytest). No TTS, browser or ffmpeg needed."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bloom import script, subs  # noqa: E402


def test_parse():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "script.md"
        p.write_text("# Title\n<!-- note -->\n## hook\nสวัสดี\nครับ\n\n## end +1.5\nดู {ภ.ง.ด.90|ภองอดอเก้าสิบ} นะ\n", encoding="utf-8")
        assert script.parse(p) == [
            {"id": "hook", "text": "สวัสดี ครับ", "speech": "สวัสดี ครับ", "hold": 0.0},
            {"id": "end", "text": "ดู ภ.ง.ด.90 นะ", "speech": "ดู ภองอดอเก้าสิบ นะ", "hold": 1.5},
        ]
        p.write_text("## end 1.5\nx\n", encoding="utf-8")  # a typo'd hold must not become a silent new id
        try:
            script.parse(p)
            raise AssertionError("bad heading accepted")
        except ValueError:
            pass
        p.write_text("## a\nx\n## a\ny\n", encoding="utf-8")
        try:
            script.parse(p)
            raise AssertionError("duplicate ids accepted")
        except ValueError:
            pass


def test_cues():
    long = "ก" * 50
    assert subs.chunk(f"หนึ่ง สองสามสี่ห้า {long} เจ็ดแปดเก้าสิบ", 20) == ["หนึ่ง สองสามสี่ห้า", long, "เจ็ดแปดเก้าสิบ"]
    # Thai spelling spaces around ๆ and numbers glue (NBSP), so no cue or wrap strands them
    nb = " "
    assert subs.chunk("ก็ได้เทมเพลตของไทยออยล์ไปเงียบ ๆ", 30) == [f"ก็ได้เทมเพลตของไทยออยล์ไปเงียบ{nb}ๆ"]
    assert subs.chunk("ดูกระดาษ บรรทัดที่ 18 ของไทยออยล์คือสารเติมแต่ง", 18) == \
        ["ดูกระดาษ", f"บรรทัดที่{nb}18", "ของไทยออยล์คือสารเติมแต่ง"]
    # a short stub never stands alone: it folds into the line before it (or forward, if first)
    assert subs.chunk("ถ้ามาจากโรงอื่นหรือจากที่ไหน SPRC ก็ได้เทมเพลตกับรหัสบริษัทของไทยออยล์", 28) == \
        ["ถ้ามาจากโรงอื่นหรือจากที่ไหน SPRC", "ก็ได้เทมเพลตกับรหัสบริษัทของไทยออยล์"]
    assert subs.chunk("ครับ สิบแปดสิบแปดสิบแปด", 5) == ["ครับ สิบแปดสิบแปดสิบแปด"]
    c = subs.cues("aaaa bbbb", 1.0, 2.0)  # two phrases fit on one line -> one cue
    assert c == [(1.0, 3.0, "aaaa bbbb")]
    c = subs.cues("a" * 30 + " " + "b" * 10, 0.0, 4.0)
    assert c[0][1] == 3.0 and c[-1][1] == 4.0  # time split by character count, ends on time
    assert subs._ts(3661.5) == "01:01:01,500"


def test_voice_spec():
    from bloom import voice

    assert voice.resolve("elevenlabs:eleven_flash_v2_5") == ("elevenlabs", "eleven_flash_v2_5")
    assert voice.resolve("say")[0] == "say" and voice.resolve("say")[1]  # variant gets its default
    assert voice.resolve("omnivoice:male, low pitch") == ("omnivoice", "male, low pitch")
    try:
        voice.resolve("polly")
        raise AssertionError("unknown provider accepted")
    except ValueError:
        pass


def test_bench_scoring():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bench"))
    from tts_bench import cer, thai_number

    for n, words in [(3, "สาม"), (10, "สิบ"), (11, "สิบเอ็ด"), (21, "ยี่สิบเอ็ด"), (101, "หนึ่งร้อยเอ็ด"),
                     (1250, "หนึ่งพันสองร้อยห้าสิบ"), (1_000_000, "หนึ่งล้าน")]:
        assert thai_number(n) == words, (n, thai_number(n))
    assert cer("ราคา 1,250 บาท", "ราคาหนึ่งพันสองร้อยห้าสิบบาท") == 0  # digits vs words is not an error
    assert cer("ใช้ Python", "ใช้ python.") == 0
    assert abs(cer("กขคง", "กขจง") - 0.25) < 1e-9


if __name__ == "__main__":
    test_parse()
    test_cues()
    test_voice_spec()
    test_bench_scoring()
    print("ok")
