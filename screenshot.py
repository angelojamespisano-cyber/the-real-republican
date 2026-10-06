#!/usr/bin/env python3
"""Render phone-sized screenshots of the local site (needs Playwright + Chrome)."""
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765/"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    for scheme, out, full in [("light", "preview.png", False), ("dark", "preview-dark.png", False),
                              ("light", "preview-full.png", True)]:
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True,
                            has_touch=True, color_scheme=scheme, timezone_id="America/Phoenix",
                            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
                                       "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
        pg = ctx.new_page()
        errs = []
        pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
        pg.goto(URL, wait_until="networkidle")
        if full:  # force lazy images to load
            pg.evaluate("document.querySelectorAll('img.lead').forEach(i => i.loading = 'eager')")
            for y in range(0, 20000, 600):
                pg.evaluate(f"window.scrollTo(0, {y})"); pg.wait_for_timeout(120)
            pg.evaluate("window.scrollTo(0, 0)")
        pg.wait_for_function("[...document.querySelectorAll('img.lead')].filter(i=>i.loading==='eager').every(i=>i.complete)", timeout=20000)
        pg.wait_for_timeout(800)
        pg.screenshot(path=out, full_page=full)
        info = pg.evaluate("""() => ({cards: document.querySelectorAll('.card').length,
            imgsLoaded: [...document.querySelectorAll('img.lead')].filter(i => i.complete && i.naturalWidth > 0).length,
            plays: document.querySelectorAll('.play:not([hidden])').length,
            date: document.getElementById('digest-date').textContent,
            sw: !!navigator.serviceWorker})""")
        print(out, info, "console errors:", errs)
        ctx.close()
    b.close()
