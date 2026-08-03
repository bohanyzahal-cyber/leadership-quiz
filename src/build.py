"""בונה את index.html מהתבנית + בנקי השאלות.

הרצה:  python build.py      (מתוך התיקייה הזו)
כותב גם ל-leadership-quiz/index.html וגם לעותק הנוח בתיקיית הקורס.
"""
import os, sys, re, glob
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE   = os.path.dirname(os.path.abspath(__file__))
REPO   = os.path.dirname(HERE)                     # .../leadership-quiz
COURSE = os.path.dirname(REPO)                     # תיקיית הקורס

TARGETS = [
    os.path.join(REPO, "index.html"),
    os.path.join(COURSE, "בוחן תרגול - מנהיגות בניהול.html"),
]

def bank_files():
    """מיון מספרי — מיון לקסיקוגרפי היה שם את bank10 לפני bank2."""
    fs = glob.glob(os.path.join(HERE, "bank*.js"))
    return sorted(fs, key=lambda f: int(re.search(r"bank(\d+)", os.path.basename(f)).group(1)))

tpl  = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
bank = "\n".join(open(f, encoding="utf-8").read() for f in bank_files())
html = tpl.replace("/*__BANK__*/", bank)

for t in TARGETS:
    open(t, "w", encoding="utf-8").write(html)
    print("נכתב:", t)
print("גודל: %.0f KB" % (len(html) / 1024))

# ---------- בדיקות שפיות ----------
objs = re.findall(r'\{t:"(.*?)",s:"(.*?)",q:', bank)
# המחרוזות במקור הן JS מוברח — \" חוזר להיות "
objs = [(t.replace('\\"', '"'), s.replace('\\"', '"')) for t, s in objs]
print("\nשאלות:", len(objs))

topics, srcs = {}, {}
for t, s in objs:
    topics[t] = topics.get(t, 0) + 1
    srcs[s]   = srcs.get(s, 0) + 1
print("\nלפי נושא:")
for k, v in sorted(topics.items(), key=lambda x: -x[1]):
    print("  %-34s %3d" % (k, v))
print("לפי מקור:")
for k, v in sorted(srcs.items(), key=lambda x: -x[1]):
    print("  %-16s %3d" % (k, v))

# פיזור התשובה הנכונה בקוד המקור (האפליקציה ממילא מערבבת אותן בכל סבב)
cs = re.findall(r',c:(\d),e:"', bank)
dist = {}
for c in cs:
    dist[c] = dist.get(c, 0) + 1
print("\nפיזור אינדקס התשובה הנכונה במקור:", dict(sorted(dist.items())))
if len(cs) != len(objs):
    print("!! אזהרה: לא כל השאלות נותחו (%d מתוך %d)" % (len(cs), len(objs)))

# ---------- עדכון אוטומטי של ה-README ----------
# הטבלה התיישנה בכל פעם שנוספו שאלות, ולכן היא נבנית מהנתונים עצמם.
def update_readme():
    path = os.path.join(REPO, "README.md")
    if not os.path.exists(path):
        return
    txt = open(path, encoding="utf-8").read()
    start, end = "<!-- STATS:START", "<!-- STATS:END -->"
    i, j = txt.find(start), txt.find(end)
    if i < 0 or j < 0:
        return
    ordered = sorted(topics.items(), key=lambda x: -x[1])
    rows = (len(ordered) + 1) // 2      # שתי עמודות, מילוי לפי שורות
    cols = [ordered[k*rows:(k+1)*rows] for k in range(2)]
    lines = ["| נושא | | נושא |", "|---|---|---|"]
    for r in range(rows):
        cells = []
        for c in range(2):
            cells.append("%s · %d" % cols[c][r] if r < len(cols[c]) else "")
        lines.append("| %s | | %s |" % tuple(cells))
    src_line = " · ".join("%s (%d)" % (k, v) for k, v in sorted(srcs.items(), key=lambda x: -x[1]))
    block = (
        "<!-- STATS:START — נוצר אוטומטית על ידי src/build.py, אין לערוך ידנית -->\n"
        "**%d שאלות** בפורמט המבחן — רב-ברירתי (אמריקאי), 4 תשובות לשאלה.\n\n"
        "%s\n\n"
        "**לפי מקור:** %s\n"
        % (len(objs), "\n".join(lines), src_line)
    )
    open(path, "w", encoding="utf-8").write(txt[:i] + block + txt[j:])
    print("עודכן:", path)

update_readme()

# ---------- בדיקות מבנה ----------
import json, subprocess, tempfile

STRUCT = r"""
const fs=require('fs');
eval(fs.readFileSync(process.argv[2],'utf8'));
/* דפוסים תלויי-מיקום: האפליקציה מערבבת את סדר האפשרויות בכל סבב,
   ולכן מסיח כמו "כל התשובות נכונות" או "תשובות א'+ב'" נשבר. */
const POS=/כל התשובות נכונות|כל ההיגדים נכונים|כל הנ["״']ל|תשובות? א['׳']\s*\+|א['׳']\s*\+\s*ב['׳']|אף תשובה אינה|כל האמור לעיל/;
const err=[], seen={};
BANK.forEach((q,i)=>{
  const at=`#${i} ${(q.q||'').slice(0,40)}`;
  if(!q.t||!q.s||!q.q||!q.e)             err.push(at+' — שדה חסר');
  if(!Array.isArray(q.o)||q.o.length!==4) err.push(at+' — אין בדיוק 4 אפשרויות');
  else if(new Set(q.o).size!==4)          err.push(at+' — אפשרות כפולה');
  if(typeof q.c!=='number'||q.c<0||q.c>3) err.push(at+' — c מחוץ לתחום');
  if((q.o||[]).some(o=>POS.test(o)))      err.push(at+' — מסיח תלוי-מיקום');
  /* כפילות ניסוח: נוצרת כשמאריכים מסיח בטקסט שכבר מופיע בסופו. */
  (q.o||[]).forEach((o)=>{
    const w=String(o).split(/\s+/);
    for(let k=0;k+1<w.length;k++){
      if(w[k].length>=4 && w[k]===w[k+1]) { err.push(at+' — מילה כפולה ברצף: "'+w[k]+'"'); break; }
      if(k+3<w.length && w[k].length>=4 && w[k]===w[k+3] && w[k+1]===w[k+4]) {
        err.push(at+' — ביטוי חוזר: "'+w.slice(k,k+2).join(' ')+'"'); break;
      }
    }
  });
  if((q.e||'').length<40)                 err.push(at+' — הסבר קצר מדי');
  if(seen[q.q]!==undefined)               err.push(at+' — שאלה כפולה (גם ב-#'+seen[q.q]+')');
  else seen[q.q]=i;
});

/* מפתח תשובה שגוי: c מצביע על מסיח בעוד ההסבר מתאר אפשרות אחרת.
   ההיגיון: ההסבר תמיד מרחיב את התשובה הנכונה ולכן חופף לה יותר.
   מדד רועש — לכן זו התראה לבדיקה ידנית ולא שגיאה. */
const STOP=new Set(('של את על אל כי גם רק אם לא זה זו אלה הוא היא הם הן אני אתה אנחנו יש אין כל כמו אבל או אז מה מי איך למה כאשר לאחר לפני בתוך בין עם ללא אשר היה היו יהיה להיות אינו אינה אינם מפני מכיוון בגלל כדי לכן ולכן אלא אף כך יותר פחות מאוד ממש בדרך כלל למשל דוגמה בהרצאה המרצה שהוא שהיא ניתן צריך יכול אפשר בפועל בלבד כמובן עדיין זאת אותו אותה אותם').split(' '));
const stem=w=>w.replace(/^(כש|לכ|מה|שה|וה|וב|ול|ומ|ו|ה|ב|ל|מ|ש|כ)/,'');
const toks=s=>{const o=new Set();String(s).split(/[^\wא-ת]+/).forEach(w=>{
  if(w.length>=4 && !STOP.has(w)) o.add(stem(w));});return o;};
const key=[];
BANK.forEach((q,i)=>{
  if(!q.e||!Array.isArray(q.o)) return;
  const E=toks(q.e);
  const sc=q.o.map(o=>{const O=toks(o);let n=0;O.forEach(x=>{if(E.has(x))n++;});
                       return O.size? n/Math.sqrt(O.size):0;});
  const best=sc.indexOf(Math.max(...sc));
  if(best!==q.c && sc[best]-sc[q.c] > 1.5)
    key.push('#'+i+' מסומן '+q.c+' אך ההסבר מתאים ל-'+best+' — '+(q.q||'').slice(0,44));
});
console.log(JSON.stringify({n:BANK.length,err,key}));
"""

try:
    with tempfile.TemporaryDirectory() as td:
        jsf = os.path.join(td, "all.js")
        open(jsf, "w", encoding="utf-8").write(bank)
        chk = os.path.join(td, "struct.js")
        open(chk, "w", encoding="utf-8").write(STRUCT)
        r = subprocess.run(["node", chk, jsf], capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            raise RuntimeError((r.stderr or "")[:300])
        s = json.loads(r.stdout.strip())
        print("\nבדיקות מבנה (%d שאלות):" % s["n"])
        if s["err"]:
            for e in s["err"][:30]:
                print("  !!", e)
            if len(s["err"]) > 30:
                print("  ... ועוד %d" % (len(s["err"]) - 30))
        else:
            print("  תקין — ללא כפילויות, שדות חסרים או מסיחים תלויי-מיקום.")
        for k in s.get("key", []):
            print("  !! מפתח תשובה:", k)
except Exception as e:
    print("\n(בדיקות המבנה דילגו — נדרש node:", e, ")")

# ---------- בדיקת "תל האורך" ----------
# כשכותבים שאלות בכמות, התשובה הנכונה יוצאת כמעט תמיד הארוכה ביותר,
# ואז אפשר לענות נכון בלי לקרוא. זו בדיקה שהבעיה לא חזרה.
CHECK = r"""
const fs=require('fs');
eval(fs.readFileSync(process.argv[2],'utf8'));
const n=BANK.length, rank=[0,0,0,0];
let long=0, short=0, outlierHit=0;
const outliers=[];
BANK.forEach((q,qi)=>{
  const L=q.o.map(o=>o.length), max=Math.max(...L), min=Math.min(...L);
  if(L.indexOf(max)===q.c) long++;
  if(L.indexOf(min)===q.c) short++;
  rank[L.map((l,i)=>[l,i]).sort((a,b)=>b[0]-a[0]).map(x=>x[1]).indexOf(q.c)]++;
  /* חריגה בולטת לעין: לא הדירוג אלא הפער. */
  const d=L.filter((_,i)=>i!==q.c), avg=d.reduce((a,b)=>a+b,0)/d.length;
  const gap=(L[q.c]-avg)/avg;
  if(Math.abs(gap)>=0.40) outliers.push({i:qi,q:q.q.slice(0,42),pct:Math.round(gap*100)});
  /* האם ניתן לנצל: "בחר את האפשרות שאורכה חורג ביותר מממוצע הארבע". */
  const mean=L.reduce((a,b)=>a+b,0)/4;
  const far=L.map((l,i)=>[Math.abs(l-mean),i]).sort((a,b)=>b[0]-a[0])[0][1];
  if(far===q.c) outlierHit++;
});
console.log(JSON.stringify({n,long,short,rank,outliers,outlierHit}));
"""
def length_stats(js_text, td, tag):
    """מריץ את בדיקת האורך על קטע קוד נתון ומחזיר סטטיסטיקה."""
    jsf = os.path.join(td, "b_%s.js" % tag)
    # קובץ ראשון מגדיר את BANK בעצמו; השאר מוסיפים אליו
    prefix = "" if js_text.lstrip().startswith("var BANK") else "var BANK=[];\n"
    open(jsf, "w", encoding="utf-8").write(prefix + js_text)
    chk = os.path.join(td, "check.js")
    if not os.path.exists(chk):
        open(chk, "w", encoding="utf-8").write(CHECK)
    r = subprocess.run(["node", chk, jsf], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "")[:200])
    return json.loads(r.stdout.strip())

def report(s, label, indent="  "):
    """שתי אסטרטגיות שאדם באמת מסוגל להפעיל בעין: 'בחר את הארוכה'
       ו'בחר את הקצרה'. פיזור הדירוג המלא מוצג כמידע בלבד."""
    n = s["n"]
    if not n:
        return False
    pct = lambda x: int(round(x / n * 100))
    flag = "  <-- !!" if max(pct(s["long"]), pct(s["short"])) > 45 else ""
    print("%s%-14s n=%-4d ארוכה=%3d%%  קצרה=%3d%%  (פיזור %s)%s"
          % (indent, label, n, pct(s["long"]), pct(s["short"]),
             "/".join("%d" % pct(x) for x in s["rank"]), flag))
    return bool(flag)

try:
    with tempfile.TemporaryDirectory() as td:
        print("\nבדיקת אורך התשובות (כדי שלא ניתן יהיה לענות בלי לקרוא) — [מקרי ≈ 25%, אחיד = 25/25/25/25]:")
        bad_files = []
        for f in bank_files():
            name = os.path.basename(f)
            txt = open(f, encoding="utf-8").read()
            if report(length_stats(txt, td, name), name):
                bad_files.append(name)
        print("  " + "-" * 58)
        all_stats = length_stats(bank, td, "all")
        report(all_stats, "סה\"כ")
        out = all_stats.get("outliers", [])
        n_all = all_stats["n"]
        hit = all_stats.get("outlierHit", 0)
        pct_hit = int(round(hit / n_all * 100)) if n_all else 0
        longish = sum(1 for o in out if o["pct"] > 0)
        print("\n  חריגות אורך (פער מממוצע המסיחים, לא דירוג):")
        print("    %d שאלות חורגות ב-40%% ומעלה — %d ארוכות מדי, %d קצרות מדי"
              % (len(out), longish, len(out) - longish))
        print("    אסטרטגיית \"בחר את החורגת ביותר\": %d%%%s"
              % (pct_hit, "   <-- !!" if pct_hit > 45 else "   (מקרי 25%)"))
        if bad_files:
            print("  !! חריגה ב:", ", ".join(bad_files),
                  "— אפשר לצבור שם מעל 45% בלי לקרוא. הארך (או קצר) מסיחים בקובץ החורג.")
        else:
            print("  תקין — אף אסטרטגיה עיוורת אינה עוברת 45% באף קובץ.")
except Exception as e:
    print("\n(בדיקת האורך דילגה — נדרש node:", e, ")")
