# -*- coding: utf-8 -*-
"""Fetch 100%-free-to-use assets ON THE GITHUB RUNNER (local machine spends
nothing): photos + music, packed into one artifact.

photos : Wikimedia Commons only -> every file there is PD / CC0 / CC-BY /
         CC-BY-SA, i.e. legal for a monetised YouTube video (we keep the
         attribution in manifest.json for the CC-BY ones).
music  : CC-BY / CC0 instrumental tracks (Kevin MacLeod, incompetech).

Also scores each photo for a QUIET TOP band, because the headline goes above
the subject and must never cover the thing the photo was picked for.
"""
import json
import os
import urllib.parse
import urllib.request

UA = "fyosamu-asset-fetch/1.0 (github runner)"
OUT = os.path.join(os.path.abspath("assets"))
PH = os.path.join(OUT, "photos")
MU = os.path.join(OUT, "music")
os.makedirs(PH, exist_ok=True)
os.makedirs(MU, exist_ok=True)


def get(url, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def api(params):
    return json.loads(get("https://commons.wikimedia.org/w/api.php?format=json&"
                          + urllib.parse.urlencode(params)).decode("utf-8"))


FREE_OK = ("public domain", "pd-", "cc0", "cc-zero", "cc by", "cc-by",
           "cc by-sa", "cc-by-sa", "no restrictions", "gfdl", "pd old")


def is_free(meta):
    blob = " ".join(str(v.get("value", "")) for v in (meta or {}).values())
    b = blob.lower()
    # an explicit "non-free" or "fair use" note disqualifies the file
    if "non-free" in b or "fair use" in b or "copyrighted" in b and "not" not in b:
        if "non-free" in b or "fair use" in b:
            return False, ""
    return (any(k in b for k in FREE_OK), b)


def quiet_top(img_path):
    """0..1 -> how calm the top 30% of the photo is (head-line real estate)."""
    try:
        from PIL import Image, ImageFilter
        im = Image.open(img_path).convert("L")
        w, h = im.size
        band = im.crop((0, 0, w, max(1, int(h * 0.30))))
        small = band.resize((160, max(1, int(160 * band.height / band.width))))
        e = small.filter(ImageFilter.FIND_EDGES)
        px = list(e.getdata())
        if not px:
            return 0.0
        mean = sum(px) / float(len(px))
        return max(0.0, min(1.0, 1.0 - mean / 60.0))
    except Exception:
        return 0.0


def search(name, limit=45, width=1800):
    p = {"action": "query", "formatversion": "2", "generator": "search",
         "gsrsearch": 'filetype:bitmap %s' % name, "gsrnamespace": "6",
         "gsrlimit": str(limit), "prop": "imageinfo",
         "iiprop": "url|size|extmetadata", "iiurlwidth": str(width)}
    data = api(p)
    out = []
    for page in data.get("query", {}).get("pages", []):
        ii = (page.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata") or {}
        ok, licblob = is_free(meta)
        if not ok or not ii.get("thumburl"):
            continue
        w, h = ii.get("width", 0), ii.get("height", 0)
        if w < 900 or h < 600:
            continue
        out.append({
            "title": page.get("title", ""),
            "url": ii.get("thumburl"),
            "w": w, "h": h,
            "license": (meta.get("LicenseShortName", {}) or {}).get("value", ""),
            "artist": (meta.get("Artist", {}) or {}).get("value", ""),
            "page": ii.get("descriptionurl", ""),
        })
    return out


def fetch_photos(name, limit=40):
    print("== photos for %r" % name, flush=True)
    cands = search(name, limit=max(limit, 30))
    cands = [c for c in cands if c["w"] / float(c["h"] or 1) >= 0.75]
    cands.sort(key=lambda c: (c["w"] / float(c["h"] or 1) >= 1.3, c["w"]),
               reverse=True)
    kept, manifest = 0, []
    for c in cands:
        if kept >= limit:
            break
        try:
            blob = get(c["url"])
        except Exception as e:                                # noqa: PERF203
            print("   skip dl", e, flush=True)
            continue
        if len(blob) < 25000:
            continue
        fn = "p%02d.jpg" % (kept + 1)
        path = os.path.join(PH, fn)
        with open(path, "wb") as fh:
            fh.write(blob)
        c["file"] = fn
        c["quiet_top"] = round(quiet_top(path), 3)
        manifest.append(c)
        kept += 1
        print("   %-18s %4dx%-4d quiet_top=%.2f  %s"
              % (fn, c["w"], c["h"], c["quiet_top"], c["license"]), flush=True)
    json.dump({"person": name, "photos": manifest},
              open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    return kept


# name -> direct, licence-stated download url  (CC-BY -> credit in description)
TRACKS = [
    ("serenity",    "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Serenity.mp3"),
    ("inspired",    "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Inspired.mp3"),
    ("heavenly",    "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Heavenly.mp3"),
    ("carefree",    "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Carefree.mp3"),
    ("wholesome",   "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Wholesome.mp3"),
    ("mountain",    "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Mountain%20View.mp3"),
    ("reflective",  "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Reflective%20Momentum.mp3"),
    ("meditation",  "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Meditation%20Impromptu%2002.mp3"),
    ("pianoir",     "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Almost%20in%20F%20-%20Tranquillity.mp3"),
    ("vivacity",    "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Vivacity.mp3"),
]


def fetch_music(limit=8):
    print("== music", flush=True)
    got, cred = [], []
    for name, url in TRACKS:
        if len(got) >= limit:
            break
        try:
            blob = get(url)
        except Exception as e:                                # noqa: PERF203
            print("   fail", name, e, flush=True)
            continue
        if len(blob) < 200000:
            print("   tiny", name, len(blob), flush=True)
            continue
        fn = "m_%s.mp3" % name
        open(os.path.join(MU, fn), "wb").write(blob)
        got.append(fn)
        cred.append({"file": fn, "title": name,
                     "artist": "Kevin MacLeod (incompetech.com)",
                     "license": "CC BY 4.0",
                     "credit": 'Music: "%s" Kevin MacLeod (incompetech.com) - '
                               'Licensed under Creative Commons: By Attribution 4.0'
                               % name})
        print("   ok", fn, len(blob), flush=True)
    json.dump({"music": cred}, open(os.path.join(OUT, "music.json"), "w",
                                    encoding="utf-8"), indent=1)
    return len(got)


if __name__ == "__main__":
    argv = sys_argv = __import__("sys").argv[1:]
    kw = dict(a[2:].split("=", 1) for a in argv if a.startswith("--"))
    kind = kw.get("kind", "photos+music")
    name = kw.get("name", "Donald Trump")
    n = int(kw.get("limit", "40"))
    tot = 0
    if "photos" in kind:
        tot += fetch_photos(name, n)
    if "music" in kind:
        tot += fetch_music(int(kw.get("muz", "8")))
    print("TOTAL", tot, flush=True)
