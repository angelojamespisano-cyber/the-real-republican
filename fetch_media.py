#!/usr/bin/env python3
"""
fetch_media.py - fill in images, videos and publish times for a picked list of
stories, then write headlines.json for the News Digest PWA.

Input (JSON on stdin, or a file path as the first argument). Either:
  * a list of stories:  [{"url": ..., "headline": ..., "note": ...}, ...]
  * or an object:       {"date": "2026-10-05", "stories": [ ... ]}
  * or plain text, one story per line:  URL | headline | note

Optional per-story keys that are kept as-is if you supply them (they override
anything scraped): source, published, image, video_url, video_page.

Nothing is invented: every image / video value comes from the article's own
HTML (og:image, twitter:image, JSON-LD, Fox video embeds / video links).
If something can't be found, the field is left null.

Usage:
  python3 fetch_media.py draft.json            # writes ./headlines.json
  cat draft.json | python3 fetch_media.py -o headlines.json
  python3 fetch_media.py draft.txt --date 2026-10-05
"""
import argparse
import datetime as dt
import html
import json
import re
import sys
import time
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

AZ = ZoneInfo("America/Phoenix")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

SOURCE_NAMES = {
    "foxnews.com": "Fox News", "foxbusiness.com": "Fox Business",
    "nypost.com": "New York Post", "washingtonexaminer.com": "Washington Examiner",
    "dailywire.com": "The Daily Wire", "freebeacon.com": "Washington Free Beacon",
    "wsj.com": "Wall Street Journal",
}
# Site-wide video reels that are not about the story itself.
GENERIC_VIDEO = re.compile(r"video headlines|top stories|today'?s video|latest videos|"
                           r"trending|daily video|news ?minute", re.I)
FOX_VIDEO_PAGE = re.compile(r"https?://(?:www\.)?fox(?:news|business)\.com/video/(\d{6,})")
FOX_EMBED = "https://video.foxnews.com/v/video-embed.html?video_id={}"


def log(*a):
    print(*a, file=sys.stderr)


def fetch(url, tries=3):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            if r.status_code == 200 and r.text:
                return r.text
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(last)


def source_for(url, soup=None):
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for dom, name in SOURCE_NAMES.items():
        if host == dom or host.endswith("." + dom):
            return name
    if soup:
        m = soup.find("meta", property="og:site_name")
        if m and m.get("content"):
            return m["content"].strip()
    return host


def meta(soup, *keys):
    for k in keys:
        m = soup.find("meta", attrs={"property": k}) or soup.find("meta", attrs={"name": k})
        if m and m.get("content", "").strip():
            return html.unescape(m["content"].strip())
    return None


def https(u, base):
    if not u:
        return None
    u = urljoin(base, u.strip())
    if u.startswith("http://"):
        u = "https://" + u[7:]
    return u


def ld_items(soup):
    out = []
    for sc in soup.find_all("script", type=lambda t: t and "ld+json" in t):
        try:
            d = json.loads(sc.string or sc.get_text())
        except Exception:
            continue
        stack = d if isinstance(d, list) else [d]
        while stack:
            it = stack.pop(0)
            if isinstance(it, list):
                stack.extend(it)
                continue
            if not isinstance(it, dict):
                continue
            out.append(it)
            if "@graph" in it:
                stack.extend(it["@graph"] if isinstance(it["@graph"], list) else [it["@graph"]])
            v = it.get("video")
            if v:
                stack.extend(v if isinstance(v, list) else [v])
    return out


def has_type(it, name):
    t = it.get("@type")
    return name in (t if isinstance(t, list) else [t])


def to_az(s):
    if not s:
        return None
    try:
        d = dt.datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    except ValueError:
        return s
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(AZ).isoformat(timespec="seconds")


def first_image(v):
    if isinstance(v, str):
        return v
    if isinstance(v, list) and v:
        return first_image(v[0])
    if isinstance(v, dict):
        return v.get("url") or v.get("contentUrl")
    return None


def extract(url, page):
    soup = BeautifulSoup(page, "html.parser")
    items = ld_items(soup)
    articles = [i for i in items if has_type(i, "NewsArticle") or has_type(i, "Article")
                or has_type(i, "ReportageNewsArticle")]
    res = {"source": source_for(url, soup)}

    # ---- image
    img = meta(soup, "og:image:secure_url", "og:image", "twitter:image", "twitter:image:src")
    if not img:
        for a in articles:
            img = first_image(a.get("image"))
            if img and not img.startswith(url + "#"):
                break
            img = None
    res["image"] = https(img, url)

    # ---- published
    pub = None
    for a in articles:
        if a.get("datePublished"):
            pub = a["datePublished"]
            break
    pub = pub or meta(soup, "article:published_time", "parsely-pub-date", "pubdate", "date")
    if not pub:
        for i in items:
            if i.get("datePublished"):
                pub = i["datePublished"]
                break
    res["published"] = to_az(pub)

    # ---- video
    video_url = video_page = None
    ogv = meta(soup, "og:video:secure_url", "og:video:url", "og:video", "twitter:player")
    if ogv:
        video_url = https(ogv, url)

    for v in (i for i in items if has_type(i, "VideoObject")):
        name = str(v.get("name") or "")
        if GENERIC_VIDEO.search(name):
            log(f"   skipping generic site video: {name!r}")
            continue
        for cand in (v.get("contentUrl"), v.get("embedUrl"), v.get("url")):
            if not cand or not isinstance(cand, str):
                continue
            c = https(cand, url)
            if FOX_VIDEO_PAGE.match(c) and not video_page:
                video_page = c
            elif re.search(r"\.(mp4|m3u8)(\?|$)", c) and not (video_url and video_url.endswith((".mp4", ".m3u8"))):
                video_url = c
            elif not video_url and ("embed" in c or "player" in c):
                video_url = c
        if video_url or video_page:
            break

    host = urlparse(url).netloc
    if "foxnews.com" in host or "foxbusiness.com" in host:
        # Fox featured video / inline videos in the article body (not sidebars).
        scopes = soup.select(".featured-video, .featured.video-ct, .article-body")
        vid = None
        for sc in scopes:
            el = sc.select_one("[data-video-id]")
            if el and el.get("data-video-id", "").isdigit():
                vid = el["data-video-id"]
                break
            for a in sc.find_all("a", href=True):
                m = FOX_VIDEO_PAGE.match(https(a["href"], url))
                if m:
                    vid = m.group(1)
                    break
            if vid:
                break
        if vid and not video_page:
            video_page = f"https://www.foxnews.com/video/{vid}"
        # Prefer Fox's official embed player: Fox's raw .mp4 files are served without a
        # Content-Type header, so Chrome/Android blocks them inside a <video> tag (ORB).
        m = FOX_VIDEO_PAGE.match(video_page or "")
        if m and (not video_url or "vod.foxnews.com" in video_url):
            video_url = FOX_EMBED.format(m.group(1))
    else:
        # Non-Fox article that links to a Fox video page inside its body.
        body = soup.select_one("article, .entry-content, .article-body, main") or soup
        for a in body.find_all("a", href=True):
            h = https(a["href"], url)
            if FOX_VIDEO_PAGE.match(h):
                video_page = video_page or h
                break

    res["video_url"] = video_url
    res["video_page"] = video_page
    return res


def parse_input(text):
    text = text.strip()
    if text.startswith(("[", "{")):
        d = json.loads(text)
        if isinstance(d, dict):
            return d.get("date"), d.get("stories", [])
        return None, d
    stories = []
    for line in text.splitlines():
        line = line.strip().lstrip("-* ").strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if not parts[0].startswith("http"):
            continue
        stories.append({"url": parts[0], "headline": parts[1] if len(parts) > 1 else "",
                        "note": parts[2] if len(parts) > 2 else ""})
    return None, stories


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", help="draft file (JSON or 'url | headline | note' lines); default stdin")
    ap.add_argument("-o", "--output", default="headlines.json")
    ap.add_argument("--date", help="digest date YYYY-MM-DD (default: today in Arizona)")
    args = ap.parse_args()

    raw = open(args.input, encoding="utf-8").read() if args.input else sys.stdin.read()
    in_date, drafts = parse_input(raw)
    if not drafts:
        sys.exit("no stories in input")

    now = dt.datetime.now(AZ)
    out = {"date": args.date or in_date or now.date().isoformat(),
           "generated_at": now.isoformat(timespec="seconds"), "stories": []}
    problems = []
    for n, d in enumerate(drafts, 1):
        url = d["url"].strip()
        log(f"[{n}/{len(drafts)}] {url}")
        story = {"headline": d.get("headline", "").strip(), "url": url,
                 "source": source_for(url), "published": None, "note": d.get("note", "").strip(),
                 "image": None, "video_url": None, "video_page": None}
        try:
            story.update({k: v for k, v in extract(url, fetch(url)).items() if v})
        except Exception as e:
            problems.append(f"{url}: {e}")
            log(f"   !! fetch failed: {e}")
        for k in ("source", "published", "image", "video_url", "video_page"):
            if d.get(k):  # manual overrides win
                story[k] = d[k]
        log(f"   image={'yes' if story['image'] else 'NO'} video_url={'yes' if story['video_url'] else 'no'} "
            f"video_page={'yes' if story['video_page'] else 'no'} published={story['published']}")
        out["stories"].append(story)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    imgs = sum(1 for s in out["stories"] if s["image"])
    vids = sum(1 for s in out["stories"] if s["video_url"] or s["video_page"])
    log(f"\nWrote {args.output}: {len(out['stories'])} stories, {imgs} with images, {vids} with video")
    for p in problems:
        log("PROBLEM:", p)


if __name__ == "__main__":
    main()
