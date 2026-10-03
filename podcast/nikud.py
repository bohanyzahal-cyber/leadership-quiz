# -*- coding: utf-8 -*-
"""
מנקד את התסריטים שב-scripts/ במקום, כדי שהסינתזה תבטא נכון.

  cd podcast && python nikud.py             # מנקד מה שעדיין לא מנוקד
  python nikud.py 03                        # קובץ בודד
  python nikud.py --dry                     # מראה מה ישתנה, לא כותב
  python nikud.py --map                     # מדפיס מיפוי מילה->ניקוד לבדיקה

הקול העברי של edge-tts מגיב לניקוד: אותן אותיות בניקוד שונה נשמעות שונה.
בלי ניקוד המנוע מנחש, ובמילים כמו „בעלות אפס״ הוא מנחש „בַּעֲלוּת״ במקום
„בְּעָלוּת״. לכן התסריטים נשמרים מנוקדים.

הניקוד מגיע מ-Nakdan של דיקטה, ומעליו שכבת ידנית: nikud-overrides.txt.
דיקטה טובה בעברית כללית ונופלת בדיוק על המונחים של הקורס (שיטעון, אן פי
קשה, קודקודי מעבר), ולכן כל מונח שנבדק ידנית יושב בקובץ ההחלפות וגובר.

הכלי אידמפוטנטי: מילה שכבר מנוקדת לא נגעת בה. אפשר לתקן ניקוד ביד בתסריט
ולהריץ שוב בלי לאבד את התיקון, ואפשר להוסיף שורות חדשות בלי ניקוד ולהריץ
רק עליהן.

בסוף כל הרצה עובר על כל שורות הדיבור שלב „התאמות לקול״ (tts_safe): הסרת דגש
מאותיות שאינן בכ״פ, „כֹּל״ במקום „כָּל״, ווי״ו כפולה בכתיב מלא. הכללים נמצאו
בתמלול של פרק 1, ופירוטם ליד הפונקציה. (נוסף בקורס שיטות וכלי ניהול מתקדמים.)
"""
import json
import os
import re
import ssl
import sys
import time
import urllib.request

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "scripts")
CACHE = os.path.join(HERE, ".cache", "nikud")
OVERRIDES = os.path.join(HERE, "nikud-overrides.txt")

API = "https://nakdan-4-0.loadbalancer.dicta.org.il/api"
BATCH = 25                       # שורות לבקשה

NIKUD = "ְ-ּ־ׇׁׂ"       # סימני ניקוד בלבד
TEAMIM = "֑-ֽֿ֯׀׃-׆"  # טעמים, מתג, פסק
HEBREW_WORD = re.compile(r"[א-ת][א-ת'֑-ׇ]*")
HAS_NIKUD = re.compile(f"[{NIKUD}]")
SPEECH = re.compile(r"^([אש])(\s*:\s*)(.+)$")


def strip_nikud(s):
    return re.sub(f"[{NIKUD}{TEAMIM}|]", "", s)


def clean(s):
    """מוריד טעמים, מתגים וקווי הפרדה של תחיליות — המנוע מבטא אותם."""
    return re.sub(f"[{TEAMIM}|]", "", s)


def same_consonants(a, b):
    """
    טקסט מנוקד נכתב בכתיב חסר: „שווה״ הופך ל„שָׁוָה״ ו„אלפיים״ ל„אַלְפַּיִם״.
    זה הכתיב התקני לטקסט מנוקד, ולכן אֵם קריאה (אהו״י) שנוספה ככתיב מלא
    מותר לה להיעלם. כל שינוי אחר באותיות הוא שיבוש ועוצר את הריצה.
    """
    kill = str.maketrans("", "", "אהוי")
    return a.translate(kill) == b.translate(kill)


def load_overrides():
    table = {}
    if not os.path.exists(OVERRIDES):
        return table
    with open(OVERRIDES, encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            parts = re.split(r"\s{2,}|\t", line, maxsplit=1)
            if len(parts) != 2:
                sys.exit(f"שורה {n} ב-nikud-overrides.txt לא בפורמט 'מילה<טאב>מנוקדת':\n  {line}")
            bare, voweled = parts[0].strip(), clean(parts[1].strip())
            # כמו בבדיקת הפלט של דיקטה: מותר להשמיט אֵם קריאה (אהו״י) — „תֹּכְנִית״
            # בחולם חסר במקום „תוֹכְנִית״ — אבל לא לשנות עיצורים
            if not same_consonants(strip_nikud(voweled), bare):
                sys.exit(f"שורה {n}: '{voweled}' בלי ניקוד הוא '{strip_nikud(voweled)}' "
                         f"ולא '{bare}' — אותיות לא תואמות")
            table[bare] = voweled
    return table


_ctx = ssl.create_default_context()


def nakdan(text):
    """שולח בלוק טקסט ל-Nakdan ומחזיר אותו מנוקד, עם אותם רווחים וסימני פיסוק."""
    body = json.dumps({"task": "nakdan", "data": text, "genre": "modern",
                       "addmorph": False, "keepqq": False, "nodageshdefmem": False,
                       "patachma": False, "keepmetagim": False}).encode("utf-8")
    req = urllib.request.Request(API, data=body,
                                 headers={"Content-Type": "application/json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60, context=_ctx) as r:
                items = json.loads(r.read().decode("utf-8"))
            break
        except Exception as e:
            if attempt == 5:
                raise RuntimeError(f"Nakdan נכשל: {e}") from e
            time.sleep(2 * (attempt + 1))     # השרת מחזיר לפעמים 502 רגעי
    out = []
    for it in items:
        if it.get("sep"):
            out.append(it["word"])
            continue
        opts = it.get("options") or []
        if not opts:
            out.append(it["word"])
            continue
        first = opts[0]
        out.append(first[0] if isinstance(first, (list, tuple)) else first)
    return clean("".join(out))


def cached_nakdan(lines):
    """מנקד רשימת שורות, עם מטמון לכל שורה בנפרד."""
    os.makedirs(CACHE, exist_ok=True)
    import hashlib
    result, todo, seen = {}, [], set()
    for line in lines:
        h = hashlib.sha1(line.encode("utf-8")).hexdigest()[:16]
        p = os.path.join(CACHE, h + ".txt")
        if os.path.exists(p):
            result[line] = open(p, encoding="utf-8").read()
        elif line not in seen:
            seen.add(line)
            todo.append(line)

    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        voweled = nakdan("\n".join(chunk)).split("\n")
        if len(voweled) != len(chunk):
            raise RuntimeError("Nakdan החזיר מספר שורות שונה — הבלוק לא ניתן לפיצול")
        for src, dst in zip(chunk, voweled):
            if not same_consonants(strip_nikud(dst), src):
                raise RuntimeError("Nakdan שינה את האותיות, לא רק את הניקוד:\n"
                                   f"  לפני: {src}\n  אחרי: {strip_nikud(dst)}")
            result[src] = dst
            h = hashlib.sha1(src.encode("utf-8")).hexdigest()[:16]
            with open(os.path.join(CACHE, h + ".txt"), "w", encoding="utf-8") as f:
                f.write(dst)
        print(f"  ניקדתי {min(i + BATCH, len(todo))}/{len(todo)} שורות חדשות")
    return result


# ── התאמות לקול, אחרי הניקוד ──────────────────────────────────────────
# נמצאו בתמלול (faster-whisper) של פרק 1, ולא נראים בעין בתסריט:
#  1. דגש על אות שאינה בכ״פ מבלבל את הקול, והוא מוסיף תנועה או צליל v:
#     „אִרְגּוּן״ נשמע „איר גאון״, „עִדָּן״ נשמע „עידיון״, „תּוֹמֶכֶת״ נשמע „תבומכת״.
#     בעברית מדוברת לדגש כזה אין צליל, ולכן מורידים אותו. בבכ״פ הדגש קובע
#     b/k/p מול v/kh/f ונשאר; ובווי״ו הוא שורוק ונשאר.
#  2. „כָּל״ נקרא „קַל״. חולם חסר נקרא נכון, ולכן כל צורות המילה עוברות לחולם.
#  3. וי״ו כפולה בכתיב חסר („כִּוּוּנִים״) נשמעת „כיהונים״. כותבים בכתיב מלא עם
#     יו״ד ווי״ו עיצורית: „כִּיווּנִים״.
#  4. וי״ו עיצורית עם דגש ותנועה („לְשַׁוֵּק״) נקראת כשורוק. מורידים את הדגש.
KEEP_DAGESH = set("בכפךףו")
KOL_FORMS = {"כל", "בכל", "לכל", "וכל", "מכל", "שכל", "ככל", "ובכל", "ולכל",
             "וככל", "ומכל", "שבכל", "שלכל", "כשכל"}


def tts_safe(word):
    out, base = [], ""
    for ch in word:
        if "\u05D0" <= ch <= "\u05EA":                     # אות
            base = ch
        elif ch == "\u05BC" and base not in KEEP_DAGESH:   # דגש או מפיק
            continue
        out.append(ch)
    w = "".join(out)
    # וי״ו עיצורית עם דגש ותנועה („לְשַׁוֵּק״) נקראת כשורוק: „לשאועק״. מורידים את הדגש.
    w = re.sub("וּ([ְ-ֻ])", "ו" + r"\1", w)
    w = re.sub("ו([ְ-ֻ])ּ", "ו" + r"\1", w)
    if strip_nikud(w) in KOL_FORMS:
        w = w.replace("\u05B8", "\u05B9")                  # קמץ -> חולם חסר
    # חיריק (ואחריו אולי דגש או נקודת שי״ן), וּ, וּ  ->  אותם סימנים, י, ו, וּ
    return re.sub("(\u05B4[\u05BC\u05C1\u05C2]*)\u05D5\u05BC\u05D5\u05BC",
                  r"\1" + "\u05D9\u05D5\u05D5\u05BC", w)


def safe_line(text):
    return HEBREW_WORD.sub(lambda m: tts_safe(m.group(0)), text)


def needs_work(text):
    """מחזיר True אם יש בשורה מילה עברית בלי ניקוד."""
    return any(not HAS_NIKUD.search(w) and len(strip_nikud(w)) > 1
               for w in HEBREW_WORD.findall(text))


def merge(original, voweled, table, hits, collect=None):
    """
    בונה את השורה הסופית מילה במילה, לפי סדר עדיפויות:
    ניקוד ידני שכבר בתסריט > nikud-overrides.txt > מה שדיקטה החזירה.
    """
    orig_words = iter(HEBREW_WORD.findall(original))

    def sub(m):
        auto = m.group(0)
        orig = next(orig_words, None)
        if orig is None:
            return auto
        bare = strip_nikud(orig)
        if HAS_NIKUD.search(orig):
            out = orig                        # תוקן ביד — לא נוגעים
        elif bare in table:
            hits[bare] = hits.get(bare, 0) + 1
            out = table[bare]
        else:
            out = auto
        if collect is not None:
            slot = collect.setdefault(bare, {})
            slot[out] = slot.get(out, 0) + 1
        return out
    return HEBREW_WORD.sub(sub, voweled)


def process(path, table, dry=False, collect=None):
    lines = open(path, encoding="utf-8").read().split("\n")
    hits = {}
    pending, index = [], {}

    for i, raw in enumerate(lines):
        m = SPEECH.match(raw.strip())
        if not m:
            continue
        text = m.group(3)
        # דיקטה תמיד מקבלת טקסט נקי מניקוד, גם אם בתסריט כבר יש ניקוד ידני
        bare = strip_nikud(text)
        if needs_work(text):
            pending.append(bare)
            index[i] = (text, bare)
        else:
            lines[i] = f"{m.group(1)}: {text}"

    voweled = cached_nakdan(sorted(set(pending))) if pending else {}
    changed = 0
    for i, (text, bare) in index.items():
        out = merge(text, voweled[bare], table, hits, collect)
        new = f"{SPEECH.match(lines[i].strip()).group(1)}: {out}"
        if new != lines[i]:
            changed += 1
        lines[i] = new

    # התאמות הקול חלות על כל שורת דיבור, גם על שורות שנוקדו בהרצה קודמת
    safe = 0
    for i, raw in enumerate(lines):
        m = SPEECH.match(raw.strip())
        if m:
            new = f"{m.group(1)}: {safe_line(m.group(3))}"
            if new != lines[i]:
                safe += 1
            lines[i] = new

    text = "\n".join(lines)
    if not dry:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    top = sorted(hits.items(), key=lambda x: -x[1])[:6]
    print(f"  {changed} שורות נוקדו · {len(hits)} החלפות ידניות"
          + (f" ({', '.join(w for w, _ in top)}…)" if top else "")
          + f" · {safe} שורות הותאמו לקול")
    return text


def main():
    args = sys.argv[1:]
    dry = "--dry" in args
    want_map = "--map" in args
    only = [a for a in args if not a.startswith("--")]

    table = load_overrides()
    print(f"החלפות ידניות: {len(table)}")

    files = sorted(f for f in os.listdir(SCRIPTS) if f.endswith(".txt"))
    if only:
        files = [f for f in files if any(f.startswith(o) for o in only)]

    collect = {} if want_map else None
    for f in files:
        print(f"\n▸ {f}")
        process(os.path.join(SCRIPTS, f), table, dry or want_map, collect)

    if want_map:
        rows = sorted(collect.items(),
                      key=lambda kv: (-sum(kv[1].values()), kv[0]))
        for bare, forms in rows:
            n = sum(forms.values())
            best = "  ".join(w for w, _ in
                             sorted(forms.items(), key=lambda x: -x[1]))
            flags = []
            if len(forms) > 1:
                flags.append("לא עקבי")
            if any(strip_nikud(w) != bare for w in forms):
                flags.append("אותיות השתנו")
            print(f"{n:>4}  {bare:<20} {best}"
                  + ("   <<< " + ", ".join(flags) if flags else ""))


if __name__ == "__main__":
    main()
