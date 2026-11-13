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
        # delivery tags are performed, never shown; one between phrases keeps the break, one inside a phrase leaves none
        p.write_text("## a\n[laughter] สวัสดี ว้าว[surprise-wa]สวย {ค.ศ.|คอสอ} [sigh]\n", encoding="utf-8")
        a = script.parse(p)[0]
        assert a["text"] == "สวัสดี ว้าวสวย ค.ศ." and a["speech"] == "[laughter] สวัสดี ว้าว[surprise-wa]สวย คอสอ [sigh]"
        assert script.untagged(a["speech"]) == "สวัสดี ว้าวสวย คอสอ" and script.untagged("[B EY1 S]") == "[B EY1 S]"
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
    # each voice gets the tags it can perform, in its own words; the rest are left out, never read aloud
    line = "[laughs] สวัสดี [excited] ว้าว[surprise-wa]"
    assert voice.delivery(line, "omnivoice") == "[laughter] สวัสดี ว้าว[surprise-wa]"
    assert voice.delivery(line, "elevenlabs") == "[laughs] สวัสดี [excited] ว้าว[gasps]"
    assert voice.delivery(line, "say") == "สวัสดี ว้าว"
    assert voice.delivery("ไม่มีแท็ก  เลย", "say") == "ไม่มีแท็ก  เลย"  # no tag: the text (and its cache key) untouched
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
    assert spell("เลขที่ 012345678901") == "เลขที่ ศูนย์หนึ่งสองสาม สี่ห้าหกเจ็ด แปดเก้าศูนย์หนึ่ง"  # an ID, not 12 billion
    assert spell("review.01") == "review.ศูนย์หนึ่ง" and spell("ถัง TK-101") == "ถัง TKหนึ่งศูนย์หนึ่ง"
    assert spell("41.54%") == "สี่สิบเอ็ดจุดห้าสี่ เปอร์เซ็นต์" and spell("691.00 ลิตร") == "หกร้อยเก้าสิบเอ็ด ลิตร"
    assert spell("วันที่ 18/09/2569") == "วันที่ สิบแปด กันยายน สองพันห้าร้อยหกสิบเก้า" and spell("1234/2569") == "หนึ่งสองสามสี่ สองห้าหกเก้า"
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
    # a riser is made to its animation's length and is loudest at its very end, where the hit lands
    r = sound.sfx("riser", 1.5)
    assert abs(len(r) / sound.SR - 1.5) < 0.001 and np.abs(r[: len(r) // 2]).max() < 0.5 * np.abs(r[len(r) // 2:]).max()
    # the hit reaches a phone: its lows (under 250 Hz) within ~8 dB of its mids (250 Hz-4 kHz)
    X, f = np.abs(np.fft.rfft(sound.sfx("hit"))) ** 2, np.fft.rfftfreq(len(sound.sfx("hit")), 1 / sound.SR)
    assert 10 * np.log10(X[(f >= 20) & (f < 250)].sum() / X[(f >= 250) & (f < 4000)].sum()) < 8
    # the drop is louder than the build: a hit peaks over the riser that leads to it
    assert sound.LEVEL_DB["hit"] > sound.LEVEL_DB["riser"] and sound.LEVEL_DB["hit"] > sound.LEVEL_DB["blip"]
    try:
        sound.place([{"sfx": "kaboom", "t": 0.0}], 1.0)
        raise AssertionError("unknown effect accepted")
    except ValueError:
        pass
    # the bed breathes before a hit and ducks under a riser; a pop asks nothing of it
    autos = sound.automation([{"sfx": "riser", "t": 1.0, "dur": 1.0}, {"sfx": "hit", "t": 2.0}, {"sfx": "pop", "t": 3.0}])
    assert autos == [(1.0, 2.0, 0.55), (1.7, 2.55, 0.45)], autos
    g = sound.gain_curve(autos, 4.0)
    at = lambda sec: g[int(sec * sound.SR)]  # noqa: E731
    assert at(0.5) == 1.0 and at(1.5) == 0.55 and at(2.2) == 0.45 and at(3.5) == 1.0
    assert np.abs(np.diff(g)).max() < 1 / (sound.RAMP * sound.SR)  # ramps, never a step: no click
    # the ending: a cut silences the bed at once and for good, a fade takes its animation's length
    cut = [{"sfx": "hit", "t": 3.0}, {"sfx": "cut", "t": 3.0, "dur": .001}]
    assert sound.ending(cut) == (3.0, sound.RAMP) and sound.ending([{"sfx": "pop", "t": 1}]) is None
    g = sound.gain_curve(sound.automation(cut), 4.0, sound.ending(cut))
    assert at(1.0) == 1.0 and at(3.1) == 0 and g[-1] == 0
    g = sound.gain_curve([], 4.0, sound.ending([{"sfx": "fade", "t": 2.0, "dur": 1.0}]))
    assert at(1.9) == 1.0 and 0.4 < at(2.5) < 0.6 and at(3.2) == 0
    assert not sound.place(cut[1:], 4.0).any()  # an ending makes no sound of its own
    # a music file follows the story: calm sits back, bright is full, the closing question lower; cues on words
    tl = [{"id": "a", "start": 0.0, "dur": 2.0, "mood": "calm"}, {"id": "b", "start": 2.0, "dur": 2.0, "mood": "bright"},
          {"id": "c", "start": 4.0, "dur": 2.0, "mood": None}]
    moves = sound.follow(tl, [(2.5, "drop"), (3.0, "lift")])
    assert (0.0, 2.0, 0.7) in moves and (2.5, 3.0, 0.15) in moves and (4.0, 6.0, 0.6) in moves, moves
    assert not any(a <= 3.5 < b for a, b, _ in moves)  # lifted back to full for the rest of the bright scene
    assert sound.follow(tl, [], by_mood=False) == [] and (5.0, 6.0, 0.0) in sound.follow(tl, [(5.0, "stop")])


def test_cue_tokens():
    from bloom import render

    found = {"sfx": "riser hit@end zip@.2", "at": 0.5, "dur": 0.8, "iterations": 1, "steps": 0}
    ev = render.cue_events(found, 10.0, 5.0)
    assert [(e["sfx"], round(e["t"], 3), round(e["dur"], 3)) for e in ev] == \
        [("riser", 10.5, 0.8), ("hit", 11.3, 0.8), ("zip", 10.7, 0.8)], ev  # the riser spans the motion and ends on the hit
    assert render.cue_events({**found, "sfx": "pop"}, 0.0, 5.0)[0]["t"] == 0.5  # one bare name: as before
    assert render.cue_events({**found, "sfx": "hit@end"}, 0.0, 1.0) == []  # lands after the scene: dropped
    fade = render.cue_events({**found, "sfx": "fade"}, 2.0, 5.0)[0]  # a fade spans its animation, like a riser
    assert (fade["sfx"], fade["t"], round(fade["dur"], 3)) == ("fade", 2.5, 0.8), fade
    for bad in ("kaboom", "hit@soon"):
        try:
            render.cue_events({**found, "sfx": bad}, 0.0, 5.0)
            raise AssertionError(f"bad data-sfx accepted: {bad}")
        except ValueError as e:
            assert bad in str(e)


def test_video_clock():
    """What stays across cuts (outside every section) runs on the video's clock; scene content on the scene's."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return
    from bloom import render

    html = ("<style>body { margin: 0 } @keyframes go { to { transform: translateX(-1000px) } } i { display: block; width: 10px; height: 10px;"
            " animation: go 10s linear infinite }</style><section data-scene='a'><i id='s'></i></section>"
            "<section data-scene='b'></section><i id='p'></i>")
    with tempfile.TemporaryDirectory() as d, sync_playwright() as pw:
        f = Path(d) / "p.html"
        f.write_text(html)
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(f.as_uri())
        page.evaluate(render.SHOW, ["a", 4])
        page.evaluate(render.SEEK, ["a", 1.0, "", None, 5.0])  # one second into a scene that starts at 4 s
        x = lambda sel: page.evaluate(f"document.querySelector('{sel}').getBoundingClientRect().left")  # noqa: E731
        assert round(x("#s")) == -100 and round(x("#p")) == -500, (x("#s"), x("#p"))
        page.evaluate(render.SEEK, ["a", 1.0, ""])  # an older caller without the clock: everything on scene time
        assert round(x("#p")) == -100
        browser.close()


def test_lipsync():
    import numpy as np
    from bloom import lipsync

    # 1 s of silence, 1 s of syllables (loud 0.1 s, quiet 0.1 s), a long held vowel, silence
    db = np.array([-120.0] * 30 + [-20.0, -20, -20, -45, -45, -45] * 5 + [-20.0] * 12 + [-120.0] * 10)
    st = [s for s, _ in lipsync.shapes(db)]
    assert set(st[:30]) == {0} and set(st[-10:]) == {0}  # shut where nothing is said
    assert st[30:33] == [2, 2, 2] and st[33] == 0  # opens on a syllable, shuts between them
    held = st[60:72]
    assert 2 in held and 1 in held and 0 not in held  # a held vowel stays open but the jaw moves
    assert lipsync.shapes(np.array([-120.0] * 5)) == [(0, 0.0)] * 5
    blink = np.array([-20.0, -20, -120, -20, -20])
    assert [s for s, _ in lipsync.shapes(blink)][2] == 1  # never one shut frame inside a word


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
    import subprocess
    from bloom import dub, voice

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
        assert lexicon.apply("ระบบ (เชื่อมโยง API)", words) == "ระบบ เชื่อมโยงเอพีไอ"  # ทับศัพท์ joins the Thai: no pause
        assert lexicon.apply("เลือกไฟล์ Excel ที่เตรียมไว้", [("Excel", "เอ็กเซล")]) == "เลือกไฟล์เอ็กเซลที่เตรียมไว้"
        assert lexicon.apply("ปริมาณ API 1,250 ครั้ง", words) == "ปริมาณเอพีไอ หนึ่งพันสองร้อยห้าสิบ ครั้ง"  # a break before a number stays

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
        a.dur, b.dur = 6.2, 4.4  # hold (the default): natural pace, and the frame before b's caption waits for a
        holds = dub.hold(lines, chapters, 30.0, 30.0)
        assert all(ln.tempo == 1.0 for ln in lines) and len(holds) == 1
        (at, secs), = holds
        assert abs(at - (8.0 - 1 / 30)) < 1e-6 and abs(secs * 30 - round(secs * 30)) < 1e-6
        assert a.start + a.dur + dub.GAP <= b.start + 1e-6 and abs(b.start - (b.cue + secs + dub.LEAD)) < 1e-6
        # two seconds of picture joined from two parts whose colour tags differ, as a video made of separately
        # encoded parts can be; held for half a second in the second part. ffmpeg's default would restart
        # its filters at the join and keep 31 of the 75 frames
        for part, tag in (("a", "bt709"), ("b", "bt470bg")):
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=d=1:s=64x36:r=30", "-c:v", "libx264",
                            "-colorspace", tag, str(Path(d) / f"{part}.ts")], check=True)
        src = Path(d) / "v.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-i", f"concat:{Path(d) / 'a.ts'}|{Path(d) / 'b.ts'}", "-c", "copy",
                        str(src)], check=True)
        out = dub.held(src, [(1.5, 0.5)], 30.0, Path(d) / "h.mp4")
        assert dub._frames(out) == 75 and abs(voice.duration(out) - 2.5) < 0.05
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


def test_prompt_cache():
    import omnivoice
    import torch
    from bloom import voice

    made = []

    class Model:
        def create_voice_clone_prompt(self, ref_audio, ref_text):
            made.append(ref_audio)
            return omnivoice.VoiceClonePrompt(ref_audio_tokens=torch.tensor([[1, 2, 3]]), ref_text=ref_text, ref_rms=0.1)

    with tempfile.TemporaryDirectory() as d:
        ref = Path(d) / "ref.wav"
        ref.write_bytes(b"RIFF fake recording")
        saved = voice._ov_model, voice.profile, voice.PROMPTS
        voice._ov_model, voice.profile, voice.PROMPTS = (lambda: Model()), (lambda name: (ref, "hello")), Path(d) / "prompts"
        try:
            first = voice._ov_prompt("@cache-test", d, "a")
            again = voice._ov_prompt("@cache-test", d, "b")  # a new run, or another machine: loaded, not tokenized
            assert len(made) == 1 and again.ref_text == "hello" and again.ref_audio_tokens.tolist() == [[1, 2, 3]]
            assert first.ref_rms == again.ref_rms and len(list((Path(d) / "prompts").glob("*.pt"))) == 1
        finally:
            voice._ov_model, voice.profile, voice.PROMPTS = saved


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

    # a delivery tag survives the lexicon (which drops other brackets), so the voice performs it instead of reading it
    assert lexicon.apply("ใหม่ค่ะ [laughter]", []) == "ใหม่ค่ะ [laughter]"
    assert lexicon.apply("ว้าว[surprise-wa]สวย 5 บาท (ดู)", []) == "ว้าว[surprise-wa]สวย ห้า บาท ดู"

    with tempfile.TemporaryDirectory() as d:
        os.environ["BLOOM_HOME"] = d
        try:
            shared = sorted(lexicon.read(lexicon.SHARED).items(), key=lambda kv: -len(kv[0]))
            assert lexicon.load() == shared  # no global lexicon yet: only Bloom's shared one
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
            assert lexicon.apply("ข้อ 2 - 9 ใน view v_oil_x", []) == "ข้อ สอง ถึง เก้า ใน view v oil x"  # a range; no underscores
            assert lexicon.remove("พาธ") and not lexicon.remove("พาธ")
            assert lexicon.load() == shared
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


def voice_duration(path: Path) -> float:
    from bloom import voice

    return round(voice.duration(path), 2)


def test_master():
    import wave
    import numpy as np
    from bloom import mix

    with tempfile.TemporaryDirectory() as d:
        # a quiet, buzzy voice in syllables, some louder, each starting with a sharp burst like a consonant
        sr, rng = 24000, np.random.default_rng(0)
        t = np.arange(sr * 3) / sr
        env = np.where((t * 4) % 1 < 0.7, 1.0, 0.0) * np.where((t * 2) % 1 < 0.5, 0.04, 0.12)
        x = (2 * ((150 * t) % 1) - 1) * env
        for s in np.flatnonzero(np.diff(env, prepend=0) > 0):
            x[s:s + 72] += rng.uniform(-0.4, 0.4, 72)
        clip = Path(d) / "a.wav"
        with wave.open(str(clip), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(sr), w.writeframes((x * 32767).astype("<i2").tobytes())
        presence, mix.PRESENCE = mix.PRESENCE, "anull"  # this signal is all bursts; on real OmniVoice lines the EQ moves nothing
        try:
            out = mix.master([(clip, 0.5)], 4.0, Path(d) / "m.wav")
        finally:
            mix.PRESENCE = presence
        with wave.open(str(out)) as w:
            y = np.frombuffer(w.readframes(w.getnframes()), "<i2") / 32768
        assert np.abs(y).max() <= 0.85  # limited below -1.4 dBFS
        # near the target; the safety limiter may take a little (here 2 dB: a burst on every syllable, seen at 48 kHz;
        # 0.0 dB on the flower-cat lines, 0.3 dB on a real dub). A limiter riding the speech takes 7.
        assert abs(mix._lufs(["ffmpeg", "-hide_banner", "-nostats", "-i", str(out)], [], "[0:a]") - mix.VOICE_LUFS) < 2.5
        # it must not bend the voice: a fast compressor once put 2.4% distortion on loud syllables
        tone = Path(d) / "tone.wav"
        with wave.open(str(tone), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(48000)
            w.writeframes((0.3 * np.sin(2 * np.pi * 150 * np.arange(48000 * 3) / 48000) * 32767).astype("<i2").tobytes())
        with wave.open(str(mix.master([(tone, 0.0)], 3.0, Path(d) / "t.wav"))) as w:
            y = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2)[48000:96000, 0] / 32768
        s = np.abs(np.fft.rfft(y * np.hanning(len(y))))
        h = [s[k * 150 - 2:k * 150 + 3].max() for k in range(1, 12)]
        assert np.sqrt(sum(x * x for x in h[1:])) / h[0] < 0.01  # under 1% THD
        with_bed = mix.master([(clip, 0.5)], 4.0, Path(d) / "b.wav", music=clip, sfx=clip)  # the build path: music and effects
        with wave.open(str(with_bed)) as w:
            assert np.abs(np.frombuffer(w.readframes(w.getnframes()), "<i2") / 32768).max() <= 0.85
        # delivered: -14 LUFS integrated, true peak under the ceiling, the bed automated by a gain track
        gain = Path(d) / "g.wav"
        with wave.open(str(gain), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(48000)
            w.writeframes((np.full(48000 * 4, 0.5) * 32767).astype("<i2").tobytes())
        loud = mix.master([(clip, 0.5)], 4.0, Path(d) / "l.wav", music=clip, sfx=clip, bed_gain=gain, lufs=-14)
        m = mix.measure(loud)
        assert abs(m["i"] + 14) < 1 and m["tp"] <= mix.TRUE_PEAK + 0.2, m
        assert not (Path(d) / "l.premaster.wav").exists() and voice_duration(loud) == 4.0


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


def test_portable_caches():
    import hashlib
    import os
    import time
    from bloom import dub, voice

    with tempfile.TemporaryDirectory() as d:
        d, cache = Path(d), Path(d) / "cache"
        for where in ("a", "b"):  # one recording, kept in two places and copied at different times
            (d / where / "me").mkdir(parents=True)
            (d / where / "me" / "ref.wav").write_bytes(b"RIFF the same recording")
            (d / where / "me" / "ref.txt").write_text("สวัสดี", encoding="utf-8")
            time.sleep(0.01)
        names = []
        for where in ("a", "b"):
            os.environ["BLOOM_VOICES"] = str(d / where)
            names.append(voice._clip("ทดสอบ", cache, "omnivoice:@me", None)[3].name)
        assert names[0] == names[1]  # a clip made on another computer is found here
        old = voice._clip("ทดสอบ", cache, "omnivoice:@me", 4.5)[3]  # keyed by path + mtime, as before Nov 2026
        legacy = old.with_name("omnivoice-" + hashlib.sha1(
            f"omnivoice|{voice._settings('omnivoice', '@me', legacy=True)}|ทดสอบ|4.500s".encode()).hexdigest()[:16] + ".wav")
        cache.mkdir()
        legacy.write_bytes(b"made earlier")
        assert voice.cached("ทดสอบ", cache, "omnivoice:@me", 4.5) and old.read_bytes() == b"made earlier" and not legacy.exists()
        del os.environ["BLOOM_VOICES"]

        for top in ("here", "there/mirror"):  # the same folders under two roots: the same work dir
            (d / top / "src").mkdir(parents=True)
            (d / top / "src" / "v.mp4").write_bytes(b"")
        works = [dub.paths(d / top / "src" / "v.mp4", d / top / "out" / "v-voice.mp4")[1].name for top in ("here", "there/mirror")]
        assert works[0] == works[1]
        video = d / "here" / "src" / "v.mp4"
        earlier = d / "here" / "out" / ".bloom" / hashlib.sha1(str(video.resolve()).encode()).hexdigest()[:10]
        (earlier / "voice").mkdir(parents=True)  # named from the absolute path before: renamed, clips kept
        out, work = dub.paths(video, d / "here" / "out" / "v-voice.mp4")
        assert (work / "voice").is_dir() and not earlier.exists() and out.name == "v-voice.mp4"
        assert dub.paths(video, None)[0] == video.with_name("v-voice.mp4")


def test_remote():
    import contextlib
    import io
    import json
    import os
    from pathlib import PurePosixPath, PureWindowsPath
    import bloom.__main__ as cli
    from bloom import remote, voice

    assert remote._rel(PurePosixPath("/Users/me/my clip.mp4")) == "Users/me/my clip.mp4"
    assert remote._rel(PureWindowsPath(r"C:\Users\me\ไฟล์.mp4")) == "C/Users/me/ไฟล์.mp4"
    assert str(remote._back("Users/me/a.mp4", windows=False)) == "/Users/me/a.mp4"
    assert str(remote._back("C/Users/me/a.mp4", windows=True)).replace("\\", "/") == "C:/Users/me/a.mp4"

    argv = ["dub", "./v.mp4", "--srt", "c.srt", "--music", "auto", "--on", "box", "--lexicon=w.tsv", "--retake", "3"]
    there = {"v.mp4": "M/v.mp4", "c.srt": "M/c.srt", "w.tsv": "M/w.tsv"}
    assert remote._rewrite(argv, there, ("--on", "--voice-on")) == \
        ["dub", "M/v.mp4", "--srt", "M/c.srt", "--music", "auto", "--lexicon=M/w.tsv", "--retake", "3"]
    assert remote._rewrite(argv + ["--voice-on=x"], {}, ("--on", "--voice-on", *remote.STATEFUL)) == \
        ["dub", "./v.mp4", "--srt", "c.srt", "--music", "auto", "--lexicon=w.tsv"]  # the finish here: retakes were applied there
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            cli.parser().parse_args(["dub", "v.mp4", "--srt", "c.srt", "--on", "a", "--voice-on", "b"])
        raise AssertionError("--on with --voice-on accepted")
    except SystemExit:
        pass

    assert remote._whole("Users/me/out/.bloom/0123456789/voice/x.wav") and remote._whole("Users/me/out/picture.mp4")
    assert not remote._whole("Users/me/out/.bloom/0123456789/picture.mp4") and not remote._whole("p/.bloom/music.wav")
    assert remote._voice("Users/me/out/.bloom/0123456789/voice/x.wav") and remote._voice("Users/me/out/v.takes.json")
    assert remote._voice("p/.bloom/voice/x.wav") and remote._voice("p/.bloom/takes.json") and remote._voice("o/v.audition.html")
    assert not remote._voice("Users/me/out/v.mp4") and not remote._voice("Users/me/out/v.review.html")
    calls, saved_serve = [], remote.serve
    remote.serve = lambda argv: calls.append(argv) or 0
    try:  # a render worker on Windows or macOS runs run.py again as __mp_main__: it must not start the job twice
        boot = {"__file__": str(Path(remote.__file__).resolve().parent.parent / "run.py")}
        exec(compile(remote.RUN_PY, "run.py", "exec"), {**boot, "__name__": "__mp_main__"})
        assert calls == []
        try:
            exec(compile(remote.RUN_PY, "run.py", "exec"), {**boot, "__name__": "__main__"})
        except SystemExit as e:
            assert e.code == 0 and len(calls) == 1
    finally:
        remote.serve = saved_serve
    lines = remote._puts([("r/a b/ไทย.wav", Path('/x/say "hi".wav'))])
    assert lines == ['-mkdir "r"', '-mkdir "r/a b"', 'put -p "/x/say \\"hi\\".wav" "r/a b/ไทย.wav"']

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        same, new = d / "same.txt", d / "new.txt"
        same.write_text("a"), new.write_text("bb")
        st = same.stat()
        assert remote._changed({"r/same": same, "r/new": new}, {"r/same": [st.st_size, int(st.st_mtime)], "r/new": None}) \
            == [("r/new", new)]
        clip = d / ".bloom" / "abcdef0123" / "voice" / "omnivoice-1.wav"  # made here: the same clip, never replaced
        clip.parent.mkdir(parents=True)
        clip.write_bytes(b"heard here")
        results = [[remote._mirror(same), st.st_size, int(st.st_mtime)], [remote._mirror(d / "gone.mp4"), 5, 0],
                   [remote._mirror(d / ".bloom" / "abcdef0123" / "picture.mp4"), 9, 0], [remote._mirror(clip), 99, 0]]
        assert remote._to_pull(results, remote._whole, "root") == [(f"root/{remote._mirror(d / 'gone.mp4')}", (d / "gone.mp4").resolve())]

        # a job as sent: its inputs, the designed voice's take, and argv in the other computer's terms
        (d / "src").mkdir()
        video, srt = d / "src" / "v.mp4", d / "src" / "c.srt"
        video.write_bytes(b""), srt.write_text("1\n")
        argv = ["dub", str(video), "--srt", str(srt), "--voice", "say:Kanya", "--out", str(d / "out" / "v.mp4"), "--voice-on", "box"]
        a = cli.parser().parse_args(argv)
        anchor = remote.dub.paths(video, a.out)[1] / "voice" / "omnivoice-anchor-1.wav"
        anchor.parent.mkdir(parents=True)
        anchor.write_bytes(b"one take")
        files, job, out = remote._job(a, argv, {"name": "box", "root": "bloom-jobs/me", "path": ["C:/tools"]}, True, "again")
        sent = {p for p in files.values()}
        assert {video, srt, anchor} <= sent and out == d / "out" / "v.mp4"
        there = job["argvs"][0]
        assert there[:2] == ["dub", remote._mirror(video)] and "--voice-on" not in there and "box" not in there
        assert there[-5:] == ["--out", remote._mirror(out), "--voice-only", "--again", "again"]
        assert job["absent"] == [remote._mirror(out.with_suffix(".takes.json"))] and job["path"] == ["C:/tools"]

        # the other side, in-process: settle the job's world, run it, list what it wrote
        root = d / "root"
        (root / ".jobs").mkdir(parents=True)
        (root / ".home" / "prompts").mkdir(parents=True)
        (root / ".home" / "prompts" / "k.pt").write_bytes(b"prompt")
        (root / "Users" / "me").mkdir(parents=True)
        (root / "Users" / "me" / "v.takes.json").write_text("{}")  # deleted here, so reset there
        job = {"argvs": [["dub", "Users/me/v.mp4", "--srt", "Users/me/c.srt", "--out", "Users/me/out/v.mp4"]],
               "env": {"BLOOM_OV_STEPS": "16", "BLOOM_OV_SEED": None}, "cli": "bloom", "path": [],
               "home": {"lexicon.tsv": "API\tเอพีไอ\n", "voices/me/ref.txt": "สวัสดี"}, "absent": ["Users/me/v.takes.json"]}
        (root / ".jobs" / "j.json").write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        seen = {}

        def fake_main(argv):
            seen.update(steps=os.environ.get("BLOOM_OV_STEPS"), seed=os.environ.get("BLOOM_OV_SEED"),
                        cli=os.environ.get("BLOOM_CLI"), home=os.environ.get("BLOOM_HOME"))
            out, work = remote.dub.paths(Path("Users/me/v.mp4"), Path("Users/me/out/v.mp4"))
            (work / "voice").mkdir(parents=True)
            (work / "voice" / "a.wav").write_bytes(b"clip")
            out.write_bytes(b"video")

        saved = (dict(os.environ), os.getcwd(), cli.main, voice.PROMPTS)
        os.environ["BLOOM_OV_SEED"] = "3"
        cli.main, voice.PROMPTS = fake_main, d / "prompts-here"
        printed = io.StringIO()
        try:
            with contextlib.redirect_stdout(printed):
                assert remote.serve(["run", ".jobs/j.json"], root) == 0
        finally:
            os.chdir(saved[1])
            os.environ.clear()
            os.environ.update(saved[0])
            cli.main, voice.PROMPTS = saved[2], saved[3]
        result = json.loads(printed.getvalue().split(remote.RESULT, 1)[1])
        names = {f[0] for f in result["files"]}
        assert seen["steps"] == "16" and seen["seed"] is None and seen["cli"] == "bloom"  # set as here, unset as here
        assert Path(seen["home"]) == root / ".home" and (root / ".home" / "lexicon.tsv").read_text(encoding="utf-8") == "API\tเอพีไอ\n"
        assert (root / ".home" / "voices" / "me" / "ref.txt").exists() and (d / "prompts-here" / "k.pt").exists()
        assert not (root / "Users" / "me" / "v.takes.json").exists() and not (root / ".jobs" / "j.json").exists()
        assert "Users/me/out/v.mp4" in names and any(n.endswith("/voice/a.wav") for n in names)
        assert not (root / ".jobs" / "j.pid").exists()  # a job that ended leaves nothing to stop

        # Ctrl-C here stops a job there with all it started (losing the connection doesn't, on Windows)
        import subprocess
        sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
        (root / ".jobs" / "k.pid").write_text(str(sleeper.pid))
        assert remote.serve(["stop", ".jobs/k.json"], root) == 0
        assert sleeper.wait(timeout=10) != 0 and not (root / ".jobs" / "k.pid").exists()
        assert remote.serve(["stop", ".jobs/k.json"], root) == 0  # one that ended already: nothing to do


def test_shared_lexicon():
    """Bloom's shared lexicon (in the repo) is read first; a personal or project entry wins over it."""
    import tempfile
    from bloom import lexicon
    assert ("ไฟล์", "ไฟ") in lexicon.load()  # ไฟล์ was read as "five": fixed once, for every voice
    assert lexicon.apply("ลงในไฟล์เดียว", lexicon.load()) == "ลงในไฟเดียว"
    with tempfile.TemporaryDirectory() as tmp:
        own = Path(tmp) / "lexicon.tsv"
        own.write_text("ไฟล์\tฟาย\n", encoding="utf-8")
        assert dict(lexicon.load(own))["ไฟล์"] == "ฟาย"


def test_compose_spec():
    """Spec-first: draft.md <-> spec round-trips, approval gates the spec, words become times, the page holds."""
    import tempfile
    from bloom import compose
    from bloom.compose import draft, page, spec
    from bloom.compose.timing import moment

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "v"
        compose.new_draft(d)
        s0, status = draft.read(d)
        assert status == "draft" and not spec.check(s0), spec.check(s0)
        try:
            compose.make_spec(d)
            raise AssertionError("an unapproved draft became a spec")
        except PermissionError:
            pass
        assert draft.parse(draft.write(s0))[0] == s0  # the draft and the spec never drift
        (d / "draft.md").write_text((d / "draft.md").read_text().replace("status: draft", "status: approved"))
        compose.make_spec(d)
        assert spec.load(d) == s0 and (d / "script.md").read_text().count("## ") == 2
    bad = {"video": {"size": "1920x1080", "motion": "calmm"}, "cast": [{"id": "b", "kind": "boxx", "args": ""}],
           "scenes": [{"id": "a", "say": "x", "beats": [{"on": "x", "do": "shw", "what": "b", "args": ""}]}]}
    errs = "\n".join(spec.check(bad))
    assert "'calm'" in errs and "'box'" in errs and "'show'" in errs, errs  # each names the nearest valid value

    # the same word lands on its own spot in a fast take and a slow one
    fast = {"id": "a", "dur": 4.0, "text": "ab cd", "phrases": [(0.35, 1.5, "ab"), (1.5, 3.0, "cd")]}
    slow = {"id": "a", "dur": 6.0, "text": "ab cd", "phrases": [(0.35, 2.5, "ab"), (2.5, 5.0, "cd")]}
    assert moment("cd", fast) == 1.5 and moment("cd", slow) == 2.5 and moment("cd+0.2", slow) == 2.7
    assert moment("-1", slow) == 5.0 and moment("50%", slow) == 3.0 and moment("end", fast) == 4.0
    try:
        moment("zz", fast)
        raise AssertionError("a word that isn't said was accepted")
    except ValueError as e:
        assert "zz" in str(e)

    sp = {"video": {"size": "1920x1080", "cam": "#a 0.8"},
          "cast": [{"id": "a", "kind": "box", "args": 'at="0 0 0"'}, {"id": "b", "kind": "box", "args": 'at="6 0 0"'},
                   {"id": "q", "kind": "ask", "args": "text=hi"}],
          "scenes": [{"id": "one", "say": "ab cd", "beats": [{"on": "cd", "do": "cam", "what": "b", "args": "zoom=1.2"},
                                                            {"on": "ab", "do": "show", "what": "b", "args": ""},
                                                            {"on": "ab", "do": "sfx", "what": "pop", "args": ""}]},
                     {"id": "two", "say": "ab cd", "beats": [{"on": "cd", "do": "show", "what": "q", "args": ""},
                                                            {"on": "-0.5", "do": "end", "what": "cut", "args": ""}]}]}
    html = page.compose(sp, [{**fast, "id": "one"}, {**fast, "id": "two"}], Path("."))
    assert 'data-cam-one="0 0.8 #a, 1.5 0.8 #a, 2.7 1.2 #b"' in html, html[html.find("data-cam-one"):][:120]
    assert 'data-cam-two="0 1.2 #b"' in html  # the next scene starts where the camera stopped: no jump at the cut
    assert 'data-after="one@0.35"' in html and 'class="cue" data-sfx="pop" style="--at: 0.35s"' in html
    assert '<section data-scene="two">' in html and 'data-sfx="hit cut" style="--at: 3.5s"' in html
    assert html.index('id="q"') > html.index('<section data-scene="two">')  # a screen thing lives in its scene

    # a line drawn again (--retake) is timed from that take, not the first one
    import json
    import wave
    from bloom import voice
    from bloom.compose.timing import timing
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "script.md").write_text("## a\nสวัสดี\n", encoding="utf-8")
        (d / ".bloom" / "voice").mkdir(parents=True)
        (d / ".bloom" / "takes.json").write_text(json.dumps({"a": 1}))
        clip = voice._clip("สวัสดี", d / ".bloom" / "voice", "say", None, 1)[3]
        with wave.open(str(clip), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b"\0\0" * 16000)
        got = timing(d, "say")[0]
        assert not got.get("missing") and abs(got["speak"] - 1.0) < 0.01, got


def test_batch():
    import contextlib
    import io
    import os
    import bloom.__main__ as cli
    from bloom import batch

    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "videos.txt"
        f.write_text("# three videos\na.mp4 --srt a.srt --retake 2\n\n\"b c.mp4\" --srt b.srt\nd.mp4 --srt d.srt --out v/d.mp4\n",
                     encoding="utf-8")
        events = []

        def voice(argv):  # the second video's voice fails: it is never finished
            events.append(("voice", argv[1]))
            if argv[1] == "b c.mp4":
                raise SystemExit(1)

        def finish(argv, label):
            events.append(("finish", argv[1]))
            assert "--retake" not in argv and "--again" in argv  # voicing applied the retake already
            return 0

        saved = (cli.main, batch._finish, os.getcwd())
        cli.main, batch._finish = voice, finish
        try:
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                code = batch.batch(f)
        finally:
            cli.main, batch._finish = saved[:2]
            os.chdir(saved[2])
        assert code == 1 and "failed: b c-voice.mp4" in printed.getvalue()
        assert [e for e in events if e[0] == "finish"] == [("finish", "a.mp4"), ("finish", "d.mp4")]
        for video in ("a.mp4", "d.mp4"):  # each video is finished only once its own voice is done
            assert events.index(("voice", video)) < events.index(("finish", video))


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
    test_prompt_cache()
    test_omnivoice_batches_back_off()
    test_partition()
    test_lexicon()
    test_takes()
    test_master()
    test_cue_tokens()
    test_video_clock()
    test_lipsync()
    test_audition()
    test_review()
    test_bench_scoring()
    test_portable_caches()
    test_remote()
    test_batch()
    test_compose_spec()
    test_shared_lexicon()
    print("ok")
