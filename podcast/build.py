# -*- coding: utf-8 -*-
"""Build original course podcasts with the two voices used in the other course sites.

python nikud.py 01
python build.py 01
python build.py --page-only

Plain scripts are the editable source; scripts/ contains the pronunciation copy.
Synthesis is cached by voice, text, and rate. A source digest also detects reordering,
removal, and pause changes even when all utterances are already cached.
"""
import asyncio
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import edge_tts

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
OUT = HERE / "mp3"
VOICES = {"א": "he-IL-AvriNeural", "ש": "he-IL-HilaNeural"}
RATE = "+0%"
AUDIO_ARGS = ["-c:a", "libmp3lame", "-b:a", "64k", "-ar", "24000", "-ac", "1"]
ALBUM = "מנהיגות בניהול אנשים — פודקאסט תרגול"


def run(args):
    result = subprocess.run(args, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace")[-2000:])
    return result.stdout.decode("utf-8", "replace")


def duration(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries",
                      "format=duration", "-of", "csv=p=0", str(path)]).strip())


def replace_audio(source, target):
    # Windows readers and OneDrive can briefly retain a handle on an old MP3.
    for attempt in range(8):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.75)


def parse(path):
    parts, chapters, pending_gap = [], [], 0.0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("# chapter:"):
            chapters.append({"title": line.split(":", 1)[1].strip(), "part": len(parts)})
            continue
        if line.startswith("#"):
            continue
        if not line:
            pending_gap = max(pending_gap, 0.9)
            continue
        if re.fullmatch(r"~[\d.]+", line):
            pending_gap = max(pending_gap, float(line[1:]))
            continue
        match = re.fullmatch(r"([אש])[֑-ׇ]*\s*:\s*(.+)", line)
        if not match:
            raise ValueError("Unrecognized script line: " + line)
        if parts:
            parts.append(("gap", pending_gap or 0.45))
        parts.append(("say", VOICES[match[1]], match[2]))
        pending_gap = 0.0
    if not parts:
        raise ValueError("Empty script: " + str(path))
    return parts, chapters


def cache_path(kind, key):
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return CACHE / (kind + "_" + digest + ".mp3")


async def synth_one(voice, text, dest, sem):
    async with sem:
        for attempt in range(4):
            try:
                await edge_tts.Communicate(text, voice, rate=RATE).save(str(dest) + ".part")
                os.replace(str(dest) + ".part", dest)
                return
            except Exception:
                if attempt == 3:
                    raise
                await asyncio.sleep(1.5 * (attempt + 1))


async def synth(jobs):
    sem = asyncio.Semaphore(4)
    await asyncio.gather(*(synth_one(*job, sem) for job in jobs))


def silence(seconds):
    dest = cache_path("gap", str(seconds))
    if not dest.exists():
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             "anullsrc=r=24000:cl=mono", "-t", str(seconds), *AUDIO_ARGS, str(dest)])
    return dest


def build_episode(ep, force=False):
    path = HERE / "scripts" / (ep["id"] + "-" + ep["slug"] + ".txt")
    parts, chapters = parse(path)
    digest = hashlib.sha256(json.dumps([RATE, parts, chapters, ep["title"]],
                                      ensure_ascii=False).encode("utf-8")).hexdigest()
    manifest_path = CACHE / (ep["id"] + "-manifest.json")
    previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    out = OUT / (ep["id"] + "-" + ep["slug"] + ".mp3")
    if not force and previous.get("digest") == digest and out.exists():
        print("Unchanged:", out.name)
        return
    pieces, jobs = [], []
    for part in parts:
        if part[0] == "gap":
            pieces.append(silence(part[1]))
        else:
            _, voice, text = part
            dest = cache_path("say", voice + "|" + RATE + "|" + text)
            if force or not dest.exists():
                jobs.append((voice, text, dest))
            pieces.append(dest)
    print("Synthesizing", len(jobs), "utterances…", flush=True)
    asyncio.run(synth(jobs))
    concat = CACHE / (ep["id"] + "-concat.txt")
    concat.write_text("".join("file '" + str(p).replace("\\", "/").replace("'", r"'\''") + "'\n"
                              for p in pieces), encoding="utf-8")
    temporary = CACHE / (ep["id"] + "-building.mp3")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
         *AUDIO_ARGS, "-metadata", "title=" + ep["id"] + " · " + ep["title"],
         "-metadata", "album=" + ALBUM, "-metadata", "artist=מנהיגות בניהול אנשים",
         "-metadata", "track=" + str(int(ep["id"])), "-metadata", "genre=Education",
         "-id3v2_version", "3", str(temporary)])
    replace_audio(temporary, out)
    # Chapter times follow the actual synthesized pieces, including pauses.
    offsets, cursor = [], 0.0
    for piece in pieces:
        offsets.append(cursor)
        cursor += duration(piece)
    cues = [{"title": ch["title"], "time": round(offsets[ch["part"]], 2)} for ch in chapters]
    # Encoder padding in the small cached files accumulates slightly in a concat.
    # Scale to the final duration so the last cue stays aligned to the final audio.
    final_duration = duration(out)
    cues = [{**ch, "time": round(ch["time"] * final_duration / cursor, 2)} for ch in cues]
    manifest_path.write_text(json.dumps({
        "digest": digest, "duration": final_duration, "chapters": cues,
        "voices": VOICES, "rate": RATE
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Built:", out.name, clock(final_duration), flush=True)


def esc(value):
    return html.escape(str(value), quote=True)


def clock(seconds):
    value = int(seconds)
    return str(value // 60) + ":" + str(value % 60).zfill(2)


def transcript(ep):
    path = HERE / "scripts" / "plain" / (ep["id"] + "-" + ep["slug"] + ".txt")
    parts = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("# chapter:"):
            parts.append("<h3>" + esc(raw.split(":", 1)[1].strip()) + "</h3>")
        elif re.fullmatch(r"~[\d.]+", raw):
            parts.append('<p class="pause">הפסקה לחשיבה · ' + esc(raw[1:]) + " שניות</p>")
        elif re.match(r"^[אש]:", raw):
            speaker, text = raw.split(":", 1)
            label = "מראיינת" if speaker == "ש" else "מסביר"
            parts.append("<p><b>" + label + ":</b> " + esc(text.strip()) + "</p>")
    return "\n".join(parts)


def write_index(episodes):
    cards, navigation, total = [], [], 0.0
    for ep in episodes:
        out = OUT / (ep["id"] + "-" + ep["slug"] + ".mp3")
        manifest_path = CACHE / (ep["id"] + "-manifest.json")
        if not out.exists() or not manifest_path.exists():
            continue
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        total += data["duration"]
        sources = "".join('<li><a href="' + esc(s["url"]) + '" target="_blank" rel="noopener">'
                          + esc(s["label"]) + "</a><p>" + esc(s["use"]) + "</p></li>" for s in ep["sources"])
        pending = "".join("<li>" + esc(item) + "</li>" for item in ep["pending_checks"])
        questions = "".join('<details class="question"><summary>' + str(i) + ". " + esc(q["q"])
                            + '</summary><p>' + esc(q["a"]) + '</p><small>' + esc(q["ref"])
                            + '</small></details>' for i, q in enumerate(ep["questions"], 1))
        chapters = "".join('<button type="button" class="chapter" data-audio="audio-' + ep["id"]
                           + '" data-time="' + str(ch["time"]) + '"><bdi>' + clock(ch["time"])
                           + "</bdi> " + esc(ch["title"]) + "</button>" for ch in data["chapters"])
        from urllib.parse import quote
        topics = ep.get("quiz_topics", [ep["quiz_topic"]])
        quiz_links = "".join('<a href="../index.html?topic=' + esc(quote(topic))
                             + '">תרגול: ' + esc(topic) + '</a>' for topic in topics)
        guide_links = "".join('<a href="../חומר-פתוח.html#page-' + str(page)
                              + '">חוברת: ' + esc(label) + '</a>'
                              for page, label in ep.get("guide_pages", [[3, "אדיג׳ס והנורמות"]]))
        navigation.append('<a href="#ep' + ep["id"] + '"><bdi>' + ep["id"]
                          + '</bdi> · ' + esc(ep["title"]) + '</a>')
        audio = "mp3/" + out.name
        script_link = "scripts/plain/" + ep["id"] + "-" + ep["slug"] + ".txt"
        cards.append(
            '<article class="ep" id="ep' + ep["id"] + '"><div class="episode-heading">'
            + '<span class="num"><bdi>' + ep["id"] + "</bdi></span><h2>" + esc(ep["title"])
            + '</h2><bdi class="duration">' + clock(data["duration"]) + '</bdi></div>'
            + '<p class="description">' + esc(ep["description"]) + '</p>'
            + '<p class="status">' + esc(ep["status"]) + '</p>'
            + '<audio id="audio-' + ep["id"] + '" aria-label="' + esc(ep["title"])
            + '" controls preload="metadata" src="' + esc(audio) + '"></audio>'
            + '<div class="links"><a href="' + esc(audio) + '" download>הורדת MP3</a>'
            + quiz_links + guide_links + '</div>'
            + '<div class="chapters" aria-label="מעבר לחלק בפרק">' + chapters + '</div>'
            + '<details class="panel"><summary>חמש שאלות חזרה · חשבו לפני פתיחת התשובה</summary>'
            + '<div class="panel-body">' + questions + '</div></details>'
            + '<details class="panel"><summary>תמליל הפרק</summary><div class="panel-body transcript">'
            + '<a href="' + esc(script_link) + '" download>הורדת התסריט לעריכה</a>'
            + transcript(ep) + '</div></details>'
            + '<details class="panel"><summary>מקורות ומה עוד נצליב עם הכיתה</summary>'
            + '<div class="panel-body"><ul class="sources">' + sources + '</ul>'
            + '<h3>להשלמת ההתאמה</h3><ul>' + pending + '</ul>'
            + '<p>' + esc(ep.get("basis_note", "הפרק מבוסס על המצגת והשאלון; ההקלטות טרם שולבו."))
            + ' הסיכום המקיף של הכיתה עדיין לא צורף.</p>'
            + '</div></details></article>'
        )
    page = (HERE / "template.html").read_text(encoding="utf-8")
    page = page.replace("<!--__EPISODES__-->", "\n".join(cards))
    page = page.replace("<!--__EPISODE_NAV__-->", "".join(navigation))
    basis = "הפרקים מבוססים על המצגות והשאלונים של קורס 111762. פרטי ההצלבה עם ההקלטות מופיעים בכל פרק; באדיג׳ס נבדק גם גרף הנורמות שהוצג בשיעור."
    page = page.replace("<!--__BASIS__-->", esc(basis))
    count = len(cards)
    stat = ("פרק אחד" if count == 1 else str(count) + " פרקים") + " · " + clock(total) + " דקות האזנה"
    page = page.replace("<!--__STATS__-->", esc(stat))
    (HERE / "index.html").write_text(page, encoding="utf-8")
    print("Player updated:", count, "episodes")


def main():
    args = sys.argv[1:]
    episodes = json.loads((HERE / "episodes.json").read_text(encoding="utf-8"))
    CACHE.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    if "--page-only" not in args:
        selected = [arg for arg in args if not arg.startswith("--")]
        for ep in episodes:
            if not selected or ep["id"] in selected:
                build_episode(ep, "--force" in args)
    write_index(episodes)


if __name__ == "__main__":
    main()
