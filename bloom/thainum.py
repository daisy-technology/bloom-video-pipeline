"""Digits -> Thai words, the way they are read aloud. OmniVoice reads digits badly
("1,250" came out as noise in the benchmark), so its text goes through spell() first.
Codes and dates that aren't read as amounts belong in {shown|spoken} instead.
"""
from __future__ import annotations

import re

DIGITS = "ศูนย์ หนึ่ง สอง สาม สี่ ห้า หก เจ็ด แปด เก้า".split()
PLACES = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน"]
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
MONEY = re.compile(r"(\d[\d,]*)\.(\d\d)(\s*)บาท")                   # 69,650,222.16 บาท -> ...บาท สิบหกสตางค์
CODE = re.compile(r"[A-Za-z]*\d[A-Za-z0-9]*(?:[-/][A-Za-z0-9]+)+")  # 03-07, INV8-202609-000539: digit by digit


def thai_number(n: int) -> str:
    """1250 -> หนึ่งพันสองร้อยห้าสิบ, 21 -> ยี่สิบเอ็ด, 1000000 -> หนึ่งล้าน."""
    if n == 0:
        return DIGITS[0]
    if n >= 1_000_000:
        rest = n % 1_000_000
        return thai_number(n // 1_000_000) + "ล้าน" + (thai_number(rest) if rest else "")
    s = str(n)
    out = []
    for i, ch in enumerate(s):
        d, place = int(ch), len(s) - 1 - i
        if d == 0:
            continue
        if place == 1 and d == 1:
            out.append("สิบ")
        elif place == 1 and d == 2:
            out.append("ยี่สิบ")
        elif place == 0 and d == 1 and len(s) > 1:
            out.append("เอ็ด")
        else:
            out.append(DIGITS[d] + PLACES[place])
    return "".join(out)


def _say(m: re.Match) -> str:
    whole, _, frac = m.group().replace(",", "").partition(".")
    words = thai_number(int(whole))
    return words + ("จุด" + "".join(DIGITS[int(d)] for d in frac) if frac else "")  # 22.19 -> ...จุดหนึ่งเก้า


def _money(m: re.Match) -> str:
    baht, satang = int(m.group(1).replace(",", "")), int(m.group(2))
    return f"{thai_number(baht)}บาท" + (f" {thai_number(satang)}สตางค์" if satang else "")


SHORT_CODE = 6  # digits; a form number like 03-07 is said as one unit, a long reference in groups


def _code(m: re.Match) -> str:
    """Codes are read digit by digit; letters stay for the voice to spell. A short code is one unit
    (03-07 -> ศูนย์สามศูนย์เจ็ด, the way a form number like ทร.03-07 is said); a long one keeps a breath between its groups
    so a listener can follow it (202609-000539 -> สองศูนย์สองหกศูนย์เก้า ศูนย์ศูนย์ศูนย์ห้าสามเก้า)."""
    groups = ["".join(DIGITS[int(c)] if c.isdigit() else c for c in g) for g in re.split(r"[-/]", m.group())]
    return ("" if sum(c.isdigit() for c in m.group()) <= SHORT_CODE else " ").join(groups)


def spell(text: str) -> str:
    """Digits as spoken Thai: money as baht and satang, codes digit by digit, other numbers as amounts."""
    return NUMBER.sub(_say, CODE.sub(_code, MONEY.sub(_money, text)))
