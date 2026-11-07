"""Run: python tests/test_bloom.py (or pytest). No TTS, browser or ffmpeg needed."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bloom import script, subs  # noqa: E402


def test_parse():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "script.md"
        p.write_text("# Title\n<!-- note -->\n## hook ~tense\nสวัสดี\nครับ\n\n## end +1.5 ~bright\nดู {ภ.ง.ด.90|ภองอดอเก้าสิบ} นะ\n",
                     encoding="utf-8")
        assert script.parse(p) == [
            {"id": "hook", "text": "สวัสดี ครับ", "speech": "สวัสดี ครับ", "hold": 0.0, "mood": "tense"},
            {"id": "end", "text": "ดู ภ.ง.ด.90 นะ", "speech": "ดู ภองอดอเก้าสิบ นะ", "hold": 1.5, "mood": "bright"},
        ]
        for bad in ("## end 1.5\nx\n", "## end ~happy\nx\n"):  # a typo must fail, not become a new id or mood
            p.write_text(bad, encoding="utf-8")
            try:
                script.parse(p)
                raise AssertionError(f"bad heading accepted: {bad!r}")
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


def test_thainum():
    from bloom.thainum import spell, thai_number

    for n, words in [(3, "สาม"), (10, "สิบ"), (11, "สิบเอ็ด"), (21, "ยี่สิบเอ็ด"), (101, "หนึ่งร้อยเอ็ด"),
                     (1250, "หนึ่งพันสองร้อยห้าสิบ"), (1_000_000, "หนึ่งล้าน")]:
        assert thai_number(n) == words, (n, thai_number(n))
    assert spell("ราคา 1,250 บาท ใน 3 วัน") == "ราคา หนึ่งพันสองร้อยห้าสิบ บาท ใน สาม วัน"
    assert spell("22.19 ลิตร") == "ยี่สิบสองจุดหนึ่งเก้า ลิตร"
    assert spell("ภ.ง.ด.90") == "ภ.ง.ด.เก้าสิบ"
    assert spell("ยอด 69,650,222.16 บาท") == "ยอด หกสิบเก้าล้านหกแสนห้าหมื่นสองร้อยยี่สิบสองบาท สิบหกสตางค์"
    assert spell("รวม 1,250.00 บาท") == "รวม หนึ่งพันสองร้อยห้าสิบบาท"
    assert spell("ทร.03-07") == "ทร.ศูนย์สามศูนย์เจ็ด"  # a short code is one unit, no pause inside
    assert spell("INV8-202609-000539") == "INVแปด สองศูนย์สองหกศูนย์เก้า ศูนย์ศูนย์ศูนย์ห้าสามเก้า"
    assert spell("9,361,589 ลิตร") == "เก้าล้านสามแสนหกหมื่นหนึ่งพันห้าร้อยแปดสิบเก้า ลิตร"


def test_sound():
    import numpy as np
    from bloom import sound

    for name in sound.SFX[:-1] + ("click",):  # every effect: finite, peak exactly 1, not empty
        x = sound.sfx(name)
        assert len(x) > 100 and np.isfinite(x).all() and abs(np.max(np.abs(x)) - 1) < 1e-9, name
    tl = [{"start": 0.0, "dur": 3.0, "mood": "tense"}, {"start": 3.0, "dur": 2.5, "mood": "bright"},
          {"start": 5.5, "dur": 2.0, "mood": None}]
    m = sound.music(tl, 7.5)
    assert len(m) == int(7.5 * sound.SR) + 1 and np.isfinite(m).all() and np.max(np.abs(m)) <= 0.98
    assert np.abs(m[: sound.SR // 100]).max() < 0.01  # fades in from silence
    y = sound.place([{"sfx": "pop", "t": 1.0}, {"sfx": "type", "t": 2.0, "dur": 0.2, "steps": 10}], 3.0)
    first = np.flatnonzero(np.abs(y) > 1e-4)[0] / sound.SR
    assert abs(first - 1.0) < 0.002, first  # the pop lands where the cue says
    assert np.abs(y[int(2.0 * sound.SR) - 400: int(2.25 * sound.SR)]).max() > 0  # typing clicks are there


def test_foley():
    import subprocess
    from bloom import foley

    with tempfile.TemporaryDirectory() as d:
        v = Path(d) / "v.mp4"
        # 3 s of black; a box appears at 1.0 s, the whole frame flashes white at 2.0 s
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=270x480:r=30:d=3",
                        "-vf", "drawbox=x=100:y=200:w=60:h=60:color=white:t=fill:enable='gte(t,1)',"
                               "drawbox=x=0:y=0:w=270:h=480:color=white:t=fill:enable='gte(t,2)'",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(v)], check=True)
        cues = foley.detect(v)
        assert [c["sfx"] for c in cues] == ["pop", "whoosh"], cues
        assert abs(cues[0]["t"] - 1.0) < 0.05 and abs(cues[1]["t"] - (2.0 - foley.WHOOSH_LEAD)) < 0.05, cues
        assert foley.detect(v, cuts=(2.0,)) == cues[:1]  # a known cut swallows the detected whoosh


def test_voice_profile():
    import os
    import wave
    import numpy as np
    from bloom import clone, voice

    with tempfile.TemporaryDirectory() as d:
        os.environ["BLOOM_VOICES"] = d
        try:
            try:
                voice.profile("me")
                raise AssertionError("missing profile accepted")
            except FileNotFoundError as e:
                assert "bloom voice record me" in str(e)
            def take(noise: float, lead: float) -> Path:
                # `lead` s of room only (a late start), then 13 s of "speech": a bursty tone at about -8 dBFS
                sr = 48000
                t = np.arange(int((lead + 13) * sr)) / sr
                x = noise * np.random.default_rng(1).standard_normal(len(t))
                x += 0.4 * np.sin(2 * np.pi * 180 * t) * (np.sin(2 * np.pi * 2.5 * t) > -0.6) * (t >= lead)
                src = Path(d) / "take.wav"
                with wave.open(str(src), "wb") as w:
                    w.setnchannels(1), w.setsampwidth(2), w.setframerate(sr)
                    w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
                return src

            clone._save("me", take(0.0003, 0.0), " สวัสดี ")  # quiet room (-70 dBFS)
            ref, text = voice.profile("me")
            assert text == "สวัสดี" and ref.exists()
            m = clone.measure(ref)
            states = {row[0]: row[2] for row in clone.verdicts(m, None)}
            assert set(states.values()) == {"ok"}, (m, states)
            # noisy room (-40 dBFS) and a 3 s late start: the lead-in still trims away
            clone._save("me", take(0.01, 3.0), "สวัสดี")
            assert clone.measure(voice.profile("me")[0])["seconds"] < 13.6
            loud = dict(m, peak_db=-0.1, seconds=3.0, snr_db=16)
            states = {row[0]: row[2] for row in clone.verdicts(loud, 0.4)}
            assert states["loudest peak"] == states["length"] == states["voice above room"] == "fail"
            assert states["words match ref.txt"] == "fail"
            assert voice.resolve("omnivoice:@me") == ("omnivoice", "@me")
            assert "|สวัสดี" in voice._settings("omnivoice", "@me")  # re-recording changes the cache key
        finally:
            del os.environ["BLOOM_VOICES"]


def test_estimate():
    from bloom import voice

    with tempfile.TemporaryDirectory() as d:
        old, voice.SPEED_FILE = voice.SPEED_FILE, Path(d) / "speed.json"
        try:
            line = "ก" * 150  # 10 s of speech at 15 characters a second
            assert voice.estimate([], "say") == 0
            assert abs(voice.estimate([line], "say") - 1.5) < 1e-9  # the M1 default for say: 0.15
            voice._learn("say", "Kanya", 3.0, 10.0)  # this machine took 3 s for 10 s of speech
            assert abs(voice.estimate([line], "say:Kanya") - 3.0) < 1e-9
            voice._learn("say", "Kanya", 1.0, 10.0)  # running average of 0.3 and 0.1
            assert abs(voice.estimate([line], "say:Kanya") - 2.0) < 1e-9
            assert abs(voice.estimate([line], "say:Alex") - 1.5) < 1e-9  # another voice keeps the default until timed
            assert voice.fmt_seconds(45) == "45 s" and voice.fmt_seconds(190) == "3 min 10 s"
        finally:
            voice.SPEED_FILE = old


def test_dub_plan():
    from bloom import dub

    with tempfile.TemporaryDirectory() as d:
        srt = Path(d) / "c.srt"
        srt.write_text("1\n00:00:05,000 --> 00:00:08,000\nเริ่มจาก API\n\n2\n00:00:08,000 --> 00:00:17,167\nบรรทัดสอง\n\n"
                       "3\n00:03:20,000 --> 00:03:23,000\nแบบ INV8-202609-000539\n\n"
                       "4\n00:03:23,000 --> 00:03:32,700\nแบบ INV8-202609-000539\n", encoding="utf-8")
        cues = dub.read_srt(srt)
        assert len(cues) == 3 and cues[2] == (200.0, 212.7, "แบบ INV8-202609-000539")  # split caption merged
        import os
        from bloom import lexicon
        os.environ["BLOOM_HOME"] = d  # never read the real ~/.bloom/lexicon.tsv from a test
        lex = Path(d) / "lex.tsv"
        lex.write_text("# comment\nINV8\tอินวอยซ์ 8\nAPI\tเอพีไอ\n", encoding="utf-8")
        words = lexicon.load(lex)
        assert lexicon.apply("แบบ INV8-202609-000539", words) == "แบบ อินวอยซ์ แปด สองศูนย์สองหกศูนย์เก้า ศูนย์ศูนย์ศูนย์ห้าสามเก้า"
        assert lexicon.apply("ระบบ (เชื่อมโยง API)", words) == "ระบบ เชื่อมโยง เอพีไอ"

        chapters = [{"start": 0.0, "end": 5.0, "title": "สาธิต\nการชำระภาษี"},
                    {"start": 5.0, "end": 17.167, "title": "1 · รายการ"}, {"start": 17.167, "end": 30.0, "title": "2 · เข้า"}]
        lines = dub.plan(cues[:2], chapters, words)
        assert [ln.spoken for ln in lines][:1] == ["สาธิต การชำระภาษี"]  # a title card speaks its title
        assert len(lines) == 4  # title, two captions, and chapter 3's title (no captions there)
        a, b = lines[1], lines[2]  # a: caption at 5.0, b: caption at 8.0, chapter 1 ends 17.167
        for ln, dur in zip(lines, (3.0, 3.5, 4.4, 2.0)):
            ln.dur = dur
        assert dub.place(lines, chapters, 30.0) == []
        assert a.tempo == 1.0 and abs(a.start - 5.15) < 1e-6  # fits within 1 s of the next caption: natural pace
        assert b.start - (b.cue + dub.LEAD) <= dub.MAX_LAG + 1e-6
        a.dur = 4.5  # would run 1.75 s into b's caption: spoken faster, so b starts exactly MAX_LAG late
        assert dub.place(lines, chapters, 30.0) == []
        assert 1.0 < a.tempo < dub.MAX_SPEEDUP and abs(b.start - (b.cue + dub.LEAD + dub.MAX_LAG)) < 1e-6
        a.dur = 6.2  # 6.2 s for a 3 s caption: capped at MAX_SPEEDUP, b starts late, still never overlaps
        assert dub.place(lines, chapters, 30.0) == []
        assert a.tempo == dub.MAX_SPEEDUP and b.start >= a.start + a.dur / a.tempo + dub.GAP - 1e-6
        assert b.tempo == 1.0 and b.start + b.dur <= 17.167 - dub.TAIL  # b has room, so b keeps its natural pace
        b.dur = 20.0  # hopeless: b is capped too, and the run warns to shorten chapter 2's captions
        warnings = dub.place(lines, chapters, 30.0)
        assert b.tempo == dub.MAX_SPEEDUP and warnings and "chapter 2" in warnings[0]
        del os.environ["BLOOM_HOME"]


def test_synth_many_say():
    import shutil
    from bloom import voice

    if not shutil.which("say"):
        return  # macOS only
    with tempfile.TemporaryDirectory() as d:
        old, voice.SPEED_FILE = voice.SPEED_FILE, Path(d) / "speed.json"
        try:
            seen = []
            texts = ["สวัสดี", "ทดสอบ", "สวัสดี"]
            paths = voice.synth_many(texts, Path(d), "say:Kanya", progress=lambda a, b: seen.append((a, b)))
            assert paths[0] == paths[2] != paths[1] and all(p.exists() for p in paths)
            assert seen == [(1, 2), (2, 2)]  # the repeated line is made once
            seen.clear()
            assert voice.synth_many(texts, Path(d), "say:Kanya", progress=lambda a, b: seen.append((a, b))) == paths
            assert seen == []  # all cached
        finally:
            voice.SPEED_FILE = old


def test_omnivoice_batches_back_off():
    import os
    import numpy as np
    from bloom import voice

    calls = []

    class Fake:  # an OmniVoice that runs out of memory above 2 lines per pass
        def generate(self, text, **kw):
            if len(text) > 2:
                raise RuntimeError("MPS backend out of memory (MPS allocated: 9.10 GB)")
            calls.append(list(text))
            return [np.zeros(int(24000 * (d or 1.0)), dtype=np.float32) for d in (kw.get("duration") or [None] * len(text))]

    saved = voice._ov_model, voice._ov_prompt, voice._empty_gpu_cache, voice.SPEED_FILE
    with tempfile.TemporaryDirectory() as d:
        voice._ov_model, voice._ov_prompt, voice._empty_gpu_cache = (lambda: Fake()), (lambda *a: "prompt"), (lambda: None)
        voice.SPEED_FILE = Path(d) / "speed.json"
        os.environ["BLOOM_OV_BATCH"] = "8"
        try:
            texts = [f"บรรทัดที่{'ก' * k}" for k in range(5)]
            texts.append(texts[0])
            fits = [1.5, 2.0, None, 1.0, 2.5, 1.5]
            paths = voice.synth_many(texts, Path(d), "omnivoice:male", fits=fits)
            assert paths[0] == paths[5] and len(set(paths)) == 5
            assert all(len(c) <= 2 for c in calls) and sum(map(len, calls)) == 5  # backed off from 8 to 2
            for p, f in zip(paths, fits):
                assert abs(voice.duration(p) - (f or 1.0)) < 0.02, (p, f)
            assert voice.synth_many(texts, Path(d), "omnivoice:male", fits=fits) == paths
            assert sum(map(len, calls)) == 5  # nothing re-made
        finally:
            voice._ov_model, voice._ov_prompt, voice._empty_gpu_cache, voice.SPEED_FILE = saved
            del os.environ["BLOOM_OV_BATCH"]


def test_partition():
    from bloom import render

    tl = [{"id": str(i), "start": 0, "dur": d} for i, d in enumerate([4.4, 7.6, 7.2, 5.4, 4.7, 5.5, 7.8, 5.3, 4.9])]
    longest = max(round(s["dur"] * 30) for s in tl)
    for w in (1, 2, 3, 4, 9, 20):
        groups = render._partition(tl, 30, w)
        assert [s for g in groups for s in g] == tl and all(groups) and len(groups) == min(w, len(tl))
        sizes = [sum(round(s["dur"] * 30) for s in g) for g in groups]
        assert max(sizes) - min(sizes) <= longest, (w, sizes)  # balanced within one scene
    assert render._partition(tl, 30, 1) == [tl]


def test_lexicon():
    import os
    from bloom import lexicon

    with tempfile.TemporaryDirectory() as d:
        os.environ["BLOOM_HOME"] = d
        try:
            assert lexicon.load() == []  # no global lexicon yet
            lexicon.add("พาธ", "พาธ")
            path = lexicon.add("พาธ", "พาด")  # add replaces
            assert path == Path(d) / "lexicon.tsv" and lexicon.read(path) == {"พาธ": "พาด"}
            assert path.read_text(encoding="utf-8").startswith("# ")  # keeps a header comment
            project = Path(d) / "project.tsv"
            lexicon.add("API", "เอพีไอ", project)
            lexicon.add("API2", "เอพีไอ 2", project)
            lexicon.add("พาธ", "พาท", project)
            pairs = lexicon.load(project)
            assert dict(pairs)["พาธ"] == "พาท"  # the project wins over the global entry
            order = [s for s, _ in pairs]
            assert order.index("API2") < order.index("API")  # longer first, so API2 is never read as API + 2
            assert lexicon.apply("ดูจากพาธ API2", pairs) == "ดูจากพาท เอพีไอ สอง"  # Thai respelt in place, API2 padded
            # no pause between a form's name and its number, one after: "ทอ รอ ศูนย์สามศูนย์เจ็ด ⏸"
            lexicon.add("ทร.", "ทอ รอ", project)
            assert lexicon.apply("แบบ ทร.03-07 ทุกประเภท", lexicon.load(project)) == "แบบ ทอ รอศูนย์สามศูนย์เจ็ด ทุกประเภท"
            # a Thai word respelt in place adds no pauses around it
            lexicon.add("เลขที่", "เลข ที่", project)
            assert lexicon.apply("แสดงเลขที่แบบ", lexicon.load(project)) == "แสดงเลข ที่แบบ"
            assert lexicon.apply("เปิด Wi-Fi (ใหม่) - ที่บ้าน", []) == "เปิด Wi-Fi ใหม่ ที่บ้าน"  # hyphen kept, dash dropped
            assert lexicon.remove("พาธ") and not lexicon.remove("พาธ")
            assert lexicon.load() == []
        finally:
            del os.environ["BLOOM_HOME"]


def test_takes():
    import hashlib
    from bloom import review, voice

    with tempfile.TemporaryDirectory() as d:
        p0, p1 = voice._clip("สวัสดี", Path(d), "say:Kanya", None)[3], voice._clip("สวัสดี", Path(d), "say:Kanya", None, 1)[3]
        old = hashlib.sha1(f"say|{voice._settings('say', 'Kanya')}|สวัสดี".encode()).hexdigest()[:16]
        assert p0.name == f"say-{old}.wav" and p1 != p0  # take 0 keeps every existing cache valid
        f = Path(d) / "x.takes.json"
        assert review.update_takes(f, None) == {} and not f.exists()
        assert review.update_takes(f, "12, 17") == {"12": 1, "17": 1}
        assert review.update_takes(f, "12") == {"12": 2, "17": 1}  # retakes stack, and are kept
        assert review.update_takes(f, None) == {"12": 2, "17": 1}
        assert review.update_takes(f, None, "4=2, 12=1") == {"12": 0, "17": 1, "4": 1}  # picks: page take K -> K-1


def test_audition():
    from bloom import dub, review

    ln = dub.Line("x", "x", 0.0, 0, dur=4.0, tempo=1.0)
    assert dub._fit(ln, 0) is None and dub._fit(ln, 2) == 4.0  # another take keeps take 0's length and place
    ln.tempo = 1.25
    assert dub._fit(ln, 0) == dub._fit(ln, 3) == 3.2
    with tempfile.TemporaryDirectory() as d:
        w = Path(d) / "a.wav"
        w.write_bytes(b"")
        page = review.audition_page([{"n": 4, "shown": "x Wi-Fi", "spoken": "x ไวไฟ", "tempo": 1.2, "current": 1,
                                      "takes": [(0, w, "ไวไฟ"), (1, w, "วายฟาย")]}], Path(d) / "p.html", "omnivoice:@me",
                                     "bloom dub v.mp4 --use-take ")
        t = page.read_text(encoding="utf-8")
        assert t.count('type="radio" name="l4"') == 2 and 'value="2" checked' in t and "in the video now" in t
        assert '"bloom dub v.mp4 --use-take "' in t and "spoken 1.20x" in t and 'src="a.wav"' in t


def test_review():
    from bloom import asr, review

    heard = {"a.wav": "ระบบ API ดึงข้อมูล", "b.wav": "ดูจากผ้าทที่วางสแกน"}
    saved = asr.transcribe
    asr.transcribe = lambda wav: heard[Path(wav).name]
    try:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "voice").mkdir()
            lines = [{"n": 1, "start": 1.0, "shown": "ระบบ API ดึงข้อมูล", "spoken": "ระบบ เอพีไอ ดึงข้อมูล",
                      "wav": Path(d) / "voice/a.wav"},
                     {"n": 2, "start": 4.5, "shown": "ดูจากพาธที่วางสแกน", "spoken": "ดูจากพาธที่วางสแกน",
                      "wav": Path(d) / "voice/b.wav"}]
            review.check(lines, Path(d) / "heard.json", flag_at=0.05)
            assert not lines[0]["flag"]  # heard as shown ("API"): fine, though it differs from the spoken form
            assert lines[1]["flag"] and lines[1]["heard"] == "ดูจากผ้าทที่วางสแกน"
            asr.transcribe = lambda wav: (_ for _ in ()).throw(AssertionError("transcribed twice"))
            review.check(lines, Path(d) / "heard.json", flag_at=0.05)  # second run: all from the cache
            page = review.page(lines, Path(d) / "v.review.html", Path(d) / "v.mp4", "v", "omnivoice:@me",
                               "bloom dub v.mp4 --retake {n}")
            text = page.read_text(encoding="utf-8")
            assert text.index("#2 ·") < text.index("#1 ·")  # flagged lines first
            assert "bloom dub v.mp4 --retake 2" in text and 'src="voice/b.wav"' in text and "<mark>" in text
    finally:
        asr.transcribe = saved


def test_bench_scoring():
    from bloom.asr import cer

    assert cer("ราคา 1,250 บาท", "ราคาหนึ่งพันสองร้อยห้าสิบบาท") == 0  # digits vs words is not an error
    assert cer("ใช้ Python", "ใช้ python.") == 0
    assert abs(cer("กขคง", "กขจง") - 0.25) < 1e-9

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bench"))
    import word_bench

    a, b = word_bench.span("หน้าแรก ไวไฟ รวมการตั้งค่าทั้งหมดของเครือข่ายในบ้าน", ["ไวไฟ"])
    assert 0.0 <= a < 0.1 and 0.4 < b < 0.6  # the word sits about a fifth of the way in: never at the line's end
    a, b = word_bench.span("เชื่อมต่อด้วยรหัสผ่านที่ตั้งไว้กับเราเตอร์ ไวไฟ", ["ไวไฟ"])
    assert 0.6 < a < 0.75 and b == 1.0
    assert word_bench.span("ยืนยันการยื่นแบบ", ["ไวไฟ"]) is None


if __name__ == "__main__":
    test_parse()
    test_cues()
    test_voice_spec()
    test_thainum()
    test_sound()
    test_foley()
    test_voice_profile()
    test_estimate()
    test_dub_plan()
    test_synth_many_say()
    test_omnivoice_batches_back_off()
    test_partition()
    test_lexicon()
    test_takes()
    test_audition()
    test_review()
    test_bench_scoring()
    print("ok")
