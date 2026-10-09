#!/usr/bin/env python3
"""Phone-sized (390x844) preview screenshots of the local site (needs Playwright + Chrome).

  python3 screenshot.py [URL] [--full]
Writes preview.png (feed), preview-dark.png (feed, dark), preview-story.png (story #1 page),
and with --full also preview-full.png (whole feed). Also checks story -> back keeps scroll.
"""
import sys
from playwright.sync_api import sync_playwright

args = [a for a in sys.argv[1:] if not a.startswith("--")]
URL = (args[0] if args else "http://localhost:8765/").split("#")[0]
FULL = "--full" in sys.argv
UA = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/129.0 Mobile Safari/537.36")

shots = [("light", "preview.png", "feed"), ("dark", "preview-dark.png", "feed"),
         ("light", "preview-story.png", "story")]
if FULL:
    shots.append(("light", "preview-full.png", "full"))

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    for scheme, out, kind in shots:
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True,
                            has_touch=True, color_scheme=scheme, timezone_id="America/Phoenix", user_agent=UA)
        pg = ctx.new_page()
        errs = []
        pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
        pg.goto(URL, wait_until="networkidle")
        pg.wait_for_selector(".card")
        if kind == "full":  # force lazy images to load
            pg.evaluate("document.querySelectorAll('img.lead').forEach(i => i.loading = 'eager')")
            for y in range(0, 20000, 600):
                pg.evaluate(f"window.scrollTo(0, {y})"); pg.wait_for_timeout(120)
            pg.evaluate("window.scrollTo(0, 0)")
        if kind == "story":
            # Scroll a bit, tap the 2nd card's headline, then later verify back restores scroll.
            pg.evaluate("window.scrollTo(0, 700)"); pg.wait_for_timeout(200)
            y0 = pg.evaluate("window.scrollY")
            pg.locator(".card").nth(1).locator(".headline a").click()
            pg.wait_for_selector("#story:not([hidden]) .story-text p")
            pg.evaluate("window.scrollTo(0, 0)")
            pg.wait_for_function("[...document.querySelectorAll('#story img.lead')].every(i=>i.complete)", timeout=20000)
            pg.wait_for_timeout(2500)  # let the video embed paint
            pg.screenshot(path=out)
            info = pg.evaluate("""() => ({hash: location.hash, paras: document.querySelectorAll('.story-text p').length,
                video: !!document.querySelector('.story-video iframe, .story-video video'),
                original: document.querySelector('.original a')?.textContent})""")
            pg.click("#back"); pg.wait_for_selector("#feed:not([hidden])"); pg.wait_for_timeout(300)
            info.update(back_hash=pg.evaluate("location.hash"), scroll_before=y0, scroll_after=pg.evaluate("window.scrollY"))
        else:
            pg.wait_for_function("[...document.querySelectorAll('img.lead')].filter(i=>i.loading==='eager').every(i=>i.complete)", timeout=20000)
            pg.wait_for_timeout(800)
            pg.screenshot(path=out, full_page=(kind == "full"))
            info = pg.evaluate("""() => ({cards: document.querySelectorAll('.card').length,
                plays: document.querySelectorAll('.play:not([hidden])').length,
                date: document.getElementById('digest-date').textContent})""")
        print(out, info, "console errors:", errs)
        ctx.close()
    b.close()
