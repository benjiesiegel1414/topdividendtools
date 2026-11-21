#!/usr/bin/env python3
"""Fetch a logo for every tool in the directory that does not have one yet.

Reads the published listings sheet, downloads each new tool's site icon,
saves it as logos/<domain>.png (64x64) and rewrites logos/manifest.json,
which the homepage reads to know which tools have a logo.
Runs daily from .github/workflows/logos.yml.
"""
import csv, io, json, os, re, sys, urllib.request
from urllib.parse import urlparse
from PIL import Image

CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQyl3IN9OtH6Ux2mS1Ojx3hqlXF8Bqztx4hQKsKilSaRLpovens0Wv-aWRfUON54vgS8RghFV7ZSV-K/pub?output=csv"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logos")
UA = {"User-Agent": "Mozilla/5.0 (compatible; TopDividendToolsLogoBot/1.0)"}


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
            return r.read() if r.status == 200 else None
    except Exception:
        return None


def domain_of(site):
    site = site.strip()
    if not re.match(r"https?://", site, re.I):
        site = "https://" + site
    try:
        host = (urlparse(site).hostname or "").lower()
    except Exception:
        return None
    host = re.sub(r"^www\.", "", host)
    return host if "." in host and " " not in host else None


def usable(data):
    """Return a 64x64 RGBA image, or None if the icon is missing, tiny or blank."""
    try:
        im = Image.open(io.BytesIO(data))
        if im.format == "ICO":
            im = im.ico.getimage(max(im.ico.sizes()))
        im = im.convert("RGBA")
    except Exception:
        return None
    if min(im.size) < 30:
        return None
    flat = Image.new("RGBA", im.size, "#fff")
    flat.alpha_composite(im)
    if flat.convert("L").getextrema()[0] > 235:
        return None
    return im.resize((64, 64), Image.LANCZOS)


def fetch(domain):
    tries = [domain]
    parts = domain.split(".")
    if len(parts) > 2:
        tries.append(".".join(parts[1:]))
    for d in tries:
        for url in ("https://www.google.com/s2/favicons?domain=%s&sz=128" % d,
                    "https://icons.duckduckgo.com/ip3/%s.ico" % d,
                    "https://%s/apple-touch-icon.png" % d):
            data = get(url)
            im = usable(data) if data else None
            if im:
                return im
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    raw = get(CSV_URL)
    if not raw:
        sys.exit("Could not read the listings sheet")
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8", "replace"))))[1:]
    domains = sorted({d for d in (domain_of(r[0]) for r in rows if len(r) > 1 and r[1].strip()) if d})
    added, missing = [], []
    for d in domains:
        path = os.path.join(OUT, d + ".png")
        if os.path.exists(path):
            continue
        im = fetch(d)
        if im:
            im.save(path, optimize=True)
            added.append(d)
        else:
            missing.append(d)
    have = sorted(f[:-4] for f in os.listdir(OUT) if f.endswith(".png"))
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(have, f, separators=(",", ":"))
        f.write("\n")
    print("logos: %d total, %d added %s, %d still missing %s" % (len(have), len(added), added, len(missing), missing))


if __name__ == "__main__":
    main()
