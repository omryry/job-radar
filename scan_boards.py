"""Israeli job boards scan (Drushim, AllJobs, JobMaster): search -> title/location/age triage -> skip known ids -> read pages.
Usage: python3 scan_boards.py <known_ids_file> > boards.jsonl 2> boards.log
Ids look like drushim:38650924 / alljobs:8827622 / jobmaster:9889035."""
import re, html, sys, time, json, datetime, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
KNOWN = {k.replace(":", "") for k in open(sys.argv[1], encoding="utf-8").read().split()} if len(sys.argv) > 1 else set()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
TERMS = ["מנהל פרויקטים טכנולוגיים", "מנהל פרויקטים IT", "מנהל תוכניות", "PMO", "Technical Program Manager",
         "Program Manager", "Project Manager", "מנהל פרויקטים תשתיות", "מנהל מוצר", "Product Manager",
         "מנהל מוצר AI", "AI Product Manager", "טרנספורמציה דיגיטלית", "הטמעת AI", "Delivery Manager"]
MAX_AGE_DAYS = 30  # Drushim shows a publish date; older posts are usually stale or already filled
KEEP = re.compile(r"program|project|pmo|delivery|chief of staff|product|operations|transformation|implementation|adoption|enablement|"
                  r"\bpm\b|\btpm\b|פרויקט|פרוייקט|תוכני|תכני|מוצר|טרנספורמציה|הטמע|\bAI\b", re.I)
DROP = re.compile(r"hardware|firmware|silicon|\bchip|asic|mechanic|electric|civil|construction|building|real estate|בני[יה]|בינוי|"
                  r"clinical|pharma|sales (manager|representative|executive|engineer|development)|business development|account (manager|executive)|"
                  r"presales|pre-sales|marketing manager|intern\b|student|סטודנט|junior|ג'וניור|associate|software engineer|developer|"
                  r"data scientist|מהנדס|ייצור|production planner|אינסטלציה|מיזוג|חשמל|התחדשות עירונית|תמ\"א|קבלן|שיפוצים|אחזקה|נדל\"ן|"
                  r"רכש|לוגיסטיקה|מכירות|מחסן|אמל\"ח|כטב\"ם|מוטס|איכות", re.I)
OUTSIDE_CENTER = re.compile(r"jerusalem|haifa|yokneam|caesarea|beer|be'er|negev|nazareth|karmiel|nesher|beit shemesh|"
                            r"ירושלים|חיפה|יקנעם|באר שבע|נשר|כרמיאל|קריית (מוצקין|ים|ביאליק|אתא|שמונה|גת)|עכו|נהריה|טבריה|עפולה|צפת|"
                            r"אשדוד|אשקלון|אילת|דימונה|שדרות|נצרת|מגדל העמק|בית שמש|מעלה אדומים|קיסריה|הצפון|הדרום", re.I)

def get(url):
    for wait in (0, 20, 60):
        time.sleep(wait)
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=25).read().decode("utf-8", "ignore")
        except Exception as e:
            err = e
            if re.search(r"HTTP Error (404|410)", str(e)): break  # gone for good; anything else (429, 503, reset) is retried
    raise err

def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()

def anchors(page, pat):
    """{id: longest anchor text} for links matching pat (group 1 = id)."""
    out = {}
    for m in re.finditer(pat, page):
        a, b = page.rfind("<a", 0, m.start()), page.find("</a>", m.end())
        t = clean(page[a:b])
        if t and len(t) > len(out.get(m.group(1), "")): out[m.group(1)] = t
    return out

found, stats = {}, {"searches": 0, "errors": 0}
for term in TERMS:
    q = urllib.parse.quote(term)
    try:  # Drushim: the job list is embedded as JSON (__NEXT_DATA__)
        p = get("https://www.drushim.co.il/jobs/search/" + q + "/")
        d = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', p, re.S).group(1))
        for qq in d["props"]["pageProps"]["dehydratedState"]["queries"]:
            data = qq["state"]["data"]
            if isinstance(data, dict) and "pages" in data:
                for j in data["pages"][0]["jobs"]:
                    found.setdefault("drushim:" + j["id"], {"id": "drushim:" + j["id"], "source": "Drushim", "title": j["title"],
                        "company": j.get("companyName") or "", "location": j.get("city") or "", "posted": (j.get("publishedAtIso") or "")[:10],
                        "experience": j.get("experience") or "", "url": "https://www.drushim.co.il" + j["jobUrl"], "term": term})
        stats["searches"] += 1
    except Exception as e:
        stats["errors"] += 1; print("#ERR drushim", term, e, file=sys.stderr)
    try:
        p = get("https://www.alljobs.co.il/SearchResultsGuest.aspx?page=1&position=&type=&freetxt=" + q)
        for jid, t in anchors(p, r"JobID=(\d+)").items():
            found.setdefault("alljobs:" + jid, {"id": "alljobs:" + jid, "source": "AllJobs", "title": t, "company": "", "location": "",
                "posted": "", "url": "https://www.alljobs.co.il/Search/UploadSingle.aspx?JobID=" + jid, "term": term})
        stats["searches"] += 1
    except Exception as e:
        stats["errors"] += 1; print("#ERR alljobs", term, e, file=sys.stderr)
    try:
        p = get("https://www.jobmaster.co.il/jobs/?q=" + urllib.parse.quote_plus(term))
        for jid, t in anchors(p, r"checknum\.asp\?key=(\d+)").items():
            found.setdefault("jobmaster:" + jid, {"id": "jobmaster:" + jid, "source": "JobMaster", "title": t, "company": "", "location": "",
                "posted": "", "url": "https://www.jobmaster.co.il/jobs/checknum.asp?key=" + jid, "term": term})
        stats["searches"] += 1
    except Exception as e:
        stats["errors"] += 1; print("#ERR jobmaster", term, e, file=sys.stderr)
    time.sleep(1)

cutoff = (datetime.date.today() - datetime.timedelta(days=MAX_AGE_DAYS)).isoformat()
stats.update(unique=len(found), known=0, title_drop=0, too_old=0, outside_center=0)
cands = []
for j in found.values():
    if j["id"].replace(":", "") in KNOWN: stats["known"] += 1; continue
    if not KEEP.search(j["title"]) or DROP.search(j["title"]): stats["title_drop"] += 1; continue
    if j["posted"] and j["posted"] < cutoff: stats["too_old"] += 1; continue
    if OUTSIDE_CENTER.search(j["location"] + " " + j["title"]): stats["outside_center"] += 1; continue
    cands.append(j)

def read(j):
    try:
        p = get(j["url"])
        t = re.search(r"<title>(.*?)</title>", p, re.S)
        j["page_title"] = clean(t.group(1)) if t else ""
        p = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", p, flags=re.S | re.I)
        text = clean(p)
        j["closed"] = bool(re.search(r"המשרה (נסגרה|אינה פעילה|כבר לא)|no longer (available|accepting)|לא נמצאה", text))
        r = re.search(r"דרישות|requirements|qualifications", text, re.I)
        j["requirements"] = text[r.start():r.start() + 1500] if r else ""
        j["text"] = text[:4000]
    except Exception as e:
        j["error"] = str(e)
    time.sleep(1)
    return j

with ThreadPoolExecutor(3) as ex:
    out = list(ex.map(read, cands))
kept = 0
for j in out:  # AllJobs/JobMaster give the city only on the page itself
    if "error" not in j and OUTSIDE_CENTER.search(j.get("page_title", "")):
        stats["outside_center"] += 1; continue
    kept += 1
    print(json.dumps(j, ensure_ascii=False))
stats.update(candidates=kept, page_errors=sum(1 for j in out if "error" in j))
print("# STATS " + json.dumps(stats), file=sys.stderr)
