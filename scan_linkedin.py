"""LinkedIn job scan: search -> title triage -> skip known ids -> fetch job pages -> one JSON line per job.
Usage: python3 scan_linkedin.py <seconds_back> <known_ids_file> > jobs.jsonl 2> scan.log
known_ids_file: one LinkedIn job id per line (ids already in the tracker); may be empty."""
import re, html, sys, time, json, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
SECS = sys.argv[1] if len(sys.argv) > 1 else "259200"
KNOWN = set(open(sys.argv[2], encoding="utf-8").read().split()) if len(sys.argv) > 2 else set()
# Broad terms are read to the end of the results (LinkedIn matches loosely, so they also catch most specific
# titles); specific terms only need their first, most relevant pages.
DEEP = ["Project Manager", "Program Manager", "Product Manager", "PMO", "מנהל פרויקטים", "מנהל מוצר"]
KW = DEEP + ["Technical Program Manager", "Technical Project Manager", "Engineering Program Manager",
             "Infrastructure Project Manager", "IT Project Manager", "Delivery Manager", "Operations Program Manager",
             "Chief of Staff", "AI Product Manager", "Product Operations", "AI Transformation", "AI Implementation",
             "מנהלת פרויקטים", "מנהל תוכניות"]
KEEP = re.compile(r"program|project|pmo|delivery|chief of staff|product|operations|transformation|implementation|adoption|enablement|"
                  r"\bpm\b|\btpm\b|פרויקט|פרוייקט|תוכני|תכני|מוצר", re.I)
DROP = re.compile(r"hardware|firmware|silicon|\bchip|asic|mechanic|electric|civil|construction|building|real estate|בני[יה]|בינוי|"
                  r"clinical|pharma|sales (manager|representative|executive|engineer|development)|business development|account (manager|executive)|presales|pre-sales|marketing manager|intern\b|student|סטודנט|"
                  r"junior|ג'וניור|associate|software engineer|developer|data scientist|מהנדס|ייצור|production planner", re.I)
OUTSIDE_CENTER = re.compile(r"jerusalem|haifa|yokneam|caesarea|beer|be'er|negev|north district|south district|nazareth|karmiel|"
                            r"migdal|afula|ashdod|ashkelon|eilat|dimona|kiryat gat|sderot|tiberias|nahariya|acre|akko|nesher|beit shemesh|"
                            r"ירושלים|חיפה|יקנעם|באר שבע|נשר|כרמיאל|קריית (מוצקין|ים|ביאליק|אתא|שמונה|גת)|עכו|נהריה|טבריה|עפולה|צפת|"
                            r"אשדוד|אשקלון|אילת|דימונה|שדרות|נצרת|מגדל העמק|בית שמש|מעלה אדומים|קיסריה", re.I)

def fetch(url):
    for wait in (0, 30, 90, 180):  # back off when LinkedIn rate-limits (HTTP 429)
        time.sleep(wait)
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read().decode("utf-8", "ignore")
        except Exception as e:
            err = e
            if re.search(r"HTTP Error (404|410)", str(e)): break  # gone for good; anything else (429, reset) is retried
    raise err

def grab(pat, c):
    m = re.search(pat, c, re.S)
    return html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""

def text(fragment):
    t = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", fragment)
    t = re.sub(r"<li[^>]*>", "• ", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", t)).strip()

# 1. search
seen, total = {}, 0
for kw in KW:
    for start in range(0, 1000 if kw in DEEP else 50, 10):
        url = ("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords="
               + urllib.parse.quote(kw) + "&location=Israel&f_TPR=r" + SECS + "&start=" + str(start))
        try:
            page = fetch(url)
        except Exception as e:
            print("#ERR search", kw, start, e, file=sys.stderr); break
        n = 0
        for c in page.split("<li>")[1:]:
            jid = grab(r"jobPosting:(\d+)", c)
            if not jid: continue
            n += 1; total += 1
            seen.setdefault(jid, {"id": jid, "title": grab(r'base-search-card__title">(.*?)<', c),
                                  "company": grab(r"hidden-nested-link[^>]*>(.*?)<", c),
                                  "location": grab(r'job-search-card__location">(.*?)<', c),
                                  "posted": grab(r'datetime="([^"]+)"', c), "keyword": kw})
        if n == 0: break
        time.sleep(1.5)

# 2. triage + dedupe
cands, stats = [], {"unique": len(seen), "known": 0, "title_drop": 0, "outside_center": 0}
for j in seen.values():
    if j["id"] in KNOWN: stats["known"] += 1; continue
    if not KEEP.search(j["title"]) or DROP.search(j["title"]): stats["title_drop"] += 1; continue
    if OUTSIDE_CENTER.search(j["location"]): stats["outside_center"] += 1; continue
    cands.append(j)

# 3. fetch job pages, 3 at a time
def detail(j):
    try:
        p = fetch("https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/" + j["id"])
    except Exception as e:
        j["error"] = str(e); return j
    j["closed"] = "No longer accepting applications" in p
    j["applicants"] = grab(r'num-applicants__caption[^>]*>(.*?)<', p)
    j["age"] = grab(r'posted-time-ago__text[^>]*>(.*?)<', p)
    crit = re.findall(r'description__job-criteria-text[^>]*>(.*?)<', p, re.S)
    j["criteria"] = " | ".join(html.unescape(re.sub(r"\s+", " ", x)).strip() for x in crit)
    m = re.search(r'show-more-less-html__markup[^>]*>(.*?)</div>', p, re.S)
    d = text(m.group(1)) if m else ""
    j["description"] = d
    r = REQ.search(d)
    j["requirements"] = d[r.start():r.start() + 1800] if r else d[-1800:]
    j["years"] = sorted({int(y) for y in re.findall(r"(\d{1,2})\s*\+?\s*(?:-\s*\d+\s*)?(?:years|שנ)", d) if 0 < int(y) < 20})
    j["flags"] = [k for k, p in FLAGS.items() if p.search(d)]
    j["work_model"] = "; ".join(sorted({x.group(0).strip() for x in WM.finditer(d)}))[:200]
    time.sleep(1.5)
    return j

REQ = re.compile(r"requirements|qualifications|what you.ll bring|what we.re looking for|what we need|who you are|you have|you bring|about you|must have|דרישות|כישורים", re.I)
FLAGS = {"degree_required": re.compile(r"(degree|b\.?sc|תואר)[^.\n]{0,80}(required|must|חובה)|(required|must|חובה)[^.\n]{0,40}(degree|b\.?sc|תואר)", re.I),
         "coding": re.compile(r"hands-on (coding|development|programming)|write code|(python|sql|java)\b[^.\n]{0,40}(required|must|חובה)", re.I),
         "customer_facing": re.compile(r"customer-facing|client-facing|customers? (directly|on-site)|presales|מול לקוחות", re.I),
         "office_only": re.compile(r"on-?site (only|5 days|full[- ]time)|fully on-?site|office-based|from the office (5|five)|no remote|עבודה מהמשרד בלבד|5 ימים במשרד", re.I),
         "shifts_oncall": re.compile(r"on-?call|shifts|night|משמרות|כוננות", re.I),
         "relocation": re.compile(r"relocat", re.I),
         "hebrew_required": re.compile(r"hebrew", re.I)}
WM = re.compile(r"[^.\n]{0,60}(hybrid|remote|work from home|office-based|on-?site|היברידי|מהבית|ימים במשרד|days (a week )?(in|from) the office)[^.\n]{0,60}", re.I)

with ThreadPoolExecutor(3) as ex:
    out = list(ex.map(detail, cands))
for j in out:
    print(json.dumps(j, ensure_ascii=False))
stats.update(results=total, candidates=len(out), errors=sum(1 for j in out if "error" in j),
             closed=sum(1 for j in out if j.get("closed")))
print("# STATS " + json.dumps(stats), file=sys.stderr)
