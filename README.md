# The Real Republican (PWA)

A static, installable, phone-first web app that shows a daily digest of 5–8 US
political stories (Fox News first, then NY Post, Washington Examiner, Daily Wire,
Washington Free Beacon, WSJ) with lead images and video. No build step, no frameworks.

## Files

| File | Purpose |
|---|---|
| `index.html`, `styles.css`, `app.js` | The app. Loads `headlines.json` and renders the card feed (light/dark aware, times shown in Arizona time). |
| `headlines.json` | Today's digest: `{date, generated_at, stories:[{headline,url,source,published,note,image,video_url,video_page}]}` |
| `fetch_media.py` | Fills in image / video / publish time / source for a draft list of stories and writes `headlines.json`. |
| `manifest.webmanifest`, `sw.js`, `icons/` | Makes it installable (home screen, full-screen) and usable offline with the last digest. |
| `make_icons.py` | Regenerates the icons with Pillow. |
| `screenshot.py` | Optional: phone-sized preview screenshots via Playwright (`preview*.png`). |
| `draft-YYYY-MM-DD.txt` | The day's picked stories (input to `fetch_media.py`). |

## Daily refresh

1. **Pick the stories** (5–8, recent, good for Republicans and/or bad for Democrats,
   Fox News first). Write them to a draft file, one per line:

   ```
   https://www.foxnews.com/politics/some-story | Exact headline from the article | One-sentence note
   ```

   JSON works too: `[{"url": "...", "headline": "...", "note": "..."}]` or
   `{"date": "2026-10-05", "stories": [...]}`. You may also add `image`, `video_url`,
   `video_page`, `source` or `published` to any story to override what's scraped.

2. **Fetch media and write `headlines.json`:**

   ```bash
   python3 fetch_media.py draft-2026-10-05.txt --date 2026-10-05
   # or: cat draft.json | python3 fetch_media.py -o headlines.json
   ```

   For each URL it downloads the article and takes, from the page itself:
   - `image`: `og:image` → `twitter:image` → JSON-LD article image
   - `published`: JSON-LD `datePublished` / `article:published_time`, converted to Arizona time
   - `video_url` / `video_page`: `og:video`, JSON-LD `VideoObject`, and for Fox the article's
     featured video (`data-video-id`) or `foxnews.com/video/…` links in the article body.
     Fox videos use Fox's official embed player
     (`https://video.foxnews.com/v/video-embed.html?video_id=…`), because Fox's raw `.mp4`
     files are served without a Content-Type and Chrome/Android blocks them in a `<video>` tag.
     Site-wide reels (e.g., NY Post's "Today's Video Headlines") are skipped because
     they aren't about the story.

   Nothing is made up: missing values stay `null` and the card just omits them.
   A summary line plus any `PROBLEM:` lines (blocked or failed fetches) print at the end.
   Needs `requests` and `beautifulsoup4`.

3. **Check it locally** (optional): `python3 -m http.server 8765` and open
   `http://localhost:8765/`.

4. **Commit and push:**

   ```bash
   git add headlines.json draft-*.txt
   git commit -m "Digest for 2026-10-05"
   git push
   ```

   GitHub Pages redeploys in about a minute. The app always fetches `headlines.json`
   from the network first (falling back to the cached copy offline), and it re-checks
   when you come back to it, so no app update is needed.

## Deploying to GitHub Pages

1. Create a repo (e.g. `news-app`) and push the contents of this folder to `main`.
   (`.nojekyll` is included so Pages serves files as-is.)
2. Repo → **Settings → Pages** → *Build and deployment* → Source: **Deploy from a branch**,
   Branch: `main`, folder `/ (root)` → Save.
3. The site appears at `https://<user>.github.io/news-app/`. All paths are relative,
   so it works from a sub-path with no changes. Pages serves HTTPS, which service workers need.
4. **Install on a phone**
   - iPhone (Safari): Share → *Add to Home Screen*.
   - Android (Chrome): ⋮ menu → *Install app* / *Add to Home screen*.
   It opens full-screen like a native app.

If you change `index.html`, `app.js` or `styles.css`, bump `VERSION` in `sw.js`
so installed copies pick up the new app shell.

## Automating later

The daily step can run anywhere that has Python and git (a cron job, or a GitHub
Actions workflow that runs `fetch_media.py` on a committed draft file and commits the result).
Picking the stories is the one step that needs a human or agent.
