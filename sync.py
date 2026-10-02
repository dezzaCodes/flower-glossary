"""Refresh the Flower Glossary page data from its Google Sheet.

Usage: SHEET_ID=... python3 sync.py
Replaces the contents of <script type="application/json" id="flower-data"> in index.html
and rewrites images.json. Exits non-zero without writing anything if the sheet is not readable.
The sheet ID comes from the environment so it never appears in this public repository.
"""
import base64, csv, datetime, io, json, os, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from PIL import Image

SHEET = "https://docs.google.com/spreadsheets/d/" + os.environ["SHEET_ID"]
IMG_WIDTH, WEBP_QUALITY = 360, 70


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.headers.get("Content-Type", "")


class SheetImages(HTMLParser):
    """Collects {sheet row number: first image URL in that row} from the htmlview table."""
    def __init__(self):
        super().__init__()
        self.images, self.row, self.cell, self.rownum = {}, False, -1, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tr":
            self.row, self.cell, self.rownum = True, -1, None
        elif tag in ("td", "th") and self.row:
            self.cell += 1
        elif tag == "img" and self.rownum and self.cell > 0 and "sheets-images-rt" in a.get("src", ""):
            self.images.setdefault(self.rownum, a["src"])

    def handle_data(self, data):
        if self.row and self.cell == 0 and data.strip().isdigit() and self.rownum is None:
            self.rownum = int(data.strip())


def webp_data_uri(url):
    raw, _ = get(re.sub(r"=[^=/]*$", "", url) + f"=w{IMG_WIDTH}")
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    out = io.BytesIO()
    im.save(out, "WEBP", quality=WEBP_QUALITY, method=6)
    return "data:image/webp;base64," + base64.b64encode(out.getvalue()).decode()


def main(page="index.html", out_dir="."):
    raw, ctype = get(SHEET + "/export?format=csv&gid=0")
    text = raw.decode("utf-8")
    if "csv" not in ctype or text.lstrip().startswith("<"):
        sys.exit("Sheet did not return CSV (probably no longer shared by link). Nothing published.")
    allrows = list(csv.reader(io.StringIO(text)))
    cols = allrows[0]
    # CSV row index i corresponds to sheet row i + 1; keep that link while dropping blank rows.
    kept = [(i + 1, r) for i, r in enumerate(allrows[1:], start=1) if any(c.strip() for c in r)]
    if not kept:
        sys.exit("Sheet has no data rows. Nothing published.")

    html_view, _ = get(SHEET + "/htmlview/sheet?headers=true&gid=0")
    parser = SheetImages()
    parser.feed(html_view.decode("utf-8", "replace"))

    jobs = {k: parser.images[sheet_row] for k, (sheet_row, _) in enumerate(kept) if sheet_row in parser.images}
    images = {}
    with ThreadPoolExecutor(8) as pool:
        for k, uri in zip(jobs, pool.map(lambda u: _safe(webp_data_uri, u), jobs.values())):
            if uri:
                images[str(k)] = uri

    data = {
        "synced": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "columns": cols,
        "rows": [r + [""] * (len(cols) - len(r)) for _, r in kept],
        "images": len(images),
    }
    blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    html = open(page, encoding="utf-8").read()
    pattern = r'(<script type="application/json" id="flower-data">)(.*?)(</script>)'
    if not re.search(pattern, html, re.S):
        sys.exit("Page has no flower-data block. Nothing published.")
    html = re.sub(pattern, lambda m: m.group(1) + blob + m.group(3), html, count=1, flags=re.S)

    os.makedirs(out_dir, exist_ok=True)
    open(os.path.join(out_dir, os.path.basename(page)), "w", encoding="utf-8").write(html)
    json.dump(images, open(os.path.join(out_dir, "images.json"), "w"), separators=(",", ":"))
    print(f"{len(cols)} columns, {len(kept)} rows, {len(images)} images "
          f"({os.path.getsize(os.path.join(out_dir, 'images.json')) // 1024} KB)")


def _safe(fn, arg):
    try:
        return fn(arg)
    except Exception as e:
        print("image failed:", arg[:80], e, file=sys.stderr)
        return None


if __name__ == "__main__":
    main(*sys.argv[1:3])
