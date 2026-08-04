# -*- coding: utf-8 -*-
"""בונה את חוברת החומר הפתוח: מזריק content.js לתוך template.html.

הדפדוף, מספור העמודים, השער והמפתח נבנים בזמן טעינה בדפדפן — כך
מספרי העמודים במפתח תמיד נכונים גם אחרי עריכת תוכן, בלי לתחזק אותם ביד.

הרצה:  python build.py
"""
import io, os, re, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)                       # .../leadership-quiz
OUT  = [os.path.join(REPO, "חומר-פתוח.html"),
        os.path.join(REPO, "..", "חומר פתוח - מנהיגות בניהול.html")]

tpl = io.open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
dat = io.open(os.path.join(HERE, "content.js"),   encoding="utf-8").read()

html = re.sub(r"/\*DATA\*/.*?/\*DATA\*/", lambda m: dat.strip(), tpl, flags=re.S)

for p in OUT:
    io.open(os.path.abspath(p), "w", encoding="utf-8").write(html)
    print("נכתב:", os.path.abspath(p))

secs  = re.findall(r'\{name:"(.*?)"', dat)
items = dat.count(" :: ")
rows  = dat.count("],[") + dat.count("],\n[")
print("\n%d תווים · %d פרקים · ~%d פריטים · ~%d שורות טבלה"
      % (len(html), len(secs), items, rows))
for s in secs:
    print("   ·", s)

# מספר העמודים נקבע רק בדפדפן, ולכן הבנייה אינה יכולה לחשב אותו.
# מה שהיא כן יכולה: להראות מי מצהיר עליו בטקסט קבוע, כדי שהצהרה
# ישנה לא תישאר אחרי שהחוברת גדלה.
CLAIMS = [("../src/template.html", r"(\d+) עמודי A4"),
          ("../README.md",         r"(\d+) עמודי A4")]
found = []
for rel, pat in CLAIMS:
    p = os.path.join(HERE, rel)
    if not os.path.exists(p):
        continue
    for m in re.finditer(pat, io.open(p, encoding="utf-8").read()):
        found.append("%s → %s" % (rel, m.group(1)))
if found:
    print("\nהצהרות על מספר עמודים (ודאו שהן עדכניות):")
    for f in found:
        print("   ", f)
