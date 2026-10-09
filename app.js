/* The Real Republican - renders headlines.json as a phone-first card feed,
   with in-app story pages at #/story/<n> (n = 1-based rank). */
(() => {
  'use strict';
  const TZ = 'America/Phoenix';
  const feed = document.getElementById('feed');
  const storyEl = document.getElementById('story');
  const tpl = document.getElementById('card-tpl');
  const dateEl = document.getElementById('digest-date');
  const metaEl = document.getElementById('meta');
  const refreshBtn = document.getElementById('refresh');
  const backBtn = document.getElementById('back');
  const footEl = document.querySelector('.foot');

  if ('scrollRestoration' in history) history.scrollRestoration = 'manual';

  const timeFmt = new Intl.DateTimeFormat('en-US', {
    timeZone: TZ, hour: 'numeric', minute: '2-digit', month: 'short', day: 'numeric'
  });
  const longTimeFmt = new Intl.DateTimeFormat('en-US', {
    timeZone: TZ, weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
  });
  const dateFmt = new Intl.DateTimeFormat('en-US', {
    timeZone: 'UTC', weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
  });

  function safeUrl(u) {
    if (!u) return null;
    try {
      const url = new URL(u, location.href);
      return (url.protocol === 'https:' || url.protocol === 'http:') ? url.href : null;
    } catch { return null; }
  }
  const isFile = (u) => /\.(mp4|m3u8|webm|mov)(\?|#|$)/i.test(u);

  function fmtTime(iso, fmt = timeFmt) {
    if (!iso) return '';
    const d = new Date(iso);
    return isNaN(d) ? '' : fmt.format(d) + ' AZ';
  }
  function fmtDate(ymd) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(ymd || '');
    if (!m) return ymd || '';
    return dateFmt.format(new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])));
  }
  const storyHref = (i) => '#/story/' + (i + 1);

  /* Video element for a story: a <video> for direct files, else the publisher's embed player. */
  function videoEl(story, videoUrl, autoplay) {
    let el;
    if (isFile(videoUrl)) {
      el = document.createElement('video');
      el.src = videoUrl;
      el.controls = true;
      el.autoplay = !!autoplay;
      el.playsInline = true;
      el.preload = autoplay ? 'auto' : 'metadata';
      el.setAttribute('playsinline', '');
      if (story.image) el.poster = story.image;
      el.addEventListener('error', () => {
        // If the publisher blocks playback, fall back to opening the video page.
        const page = safeUrl(story.video_page) || safeUrl(story.url);
        if (page && autoplay) window.open(page, '_blank', 'noopener');
      }, { once: true });
    } else {
      el = document.createElement('iframe');
      el.src = videoUrl;
      el.allow = 'autoplay; fullscreen; picture-in-picture; encrypted-media';
      el.allowFullscreen = true;
      el.referrerPolicy = 'strict-origin-when-cross-origin';
      el.loading = 'lazy';
      el.title = 'Video: ' + (story.headline || '');
    }
    return el;
  }

  function playInline(media, story, videoUrl) {
    const el = videoEl(story, videoUrl, true);
    media.querySelector('.media-link').replaceWith(el);
    const play = media.querySelector('.play'); if (play) play.remove();
    const rank = media.querySelector('.rank'); if (rank) rank.remove();
    const p = el.play && el.play();
    if (p && p.catch) p.catch(() => {});
  }

  function card(story, i) {
    const node = tpl.content.firstElementChild.cloneNode(true);
    const href = storyHref(i);
    const img = safeUrl(story.image);
    const videoUrl = safeUrl(story.video_url);
    const videoPage = safeUrl(story.video_page);

    const media = node.querySelector('.media');
    const mediaLink = node.querySelector('.media-link');
    const lead = node.querySelector('.lead');
    mediaLink.href = href;
    mediaLink.setAttribute('aria-label', 'Open story: ' + (story.headline || ''));
    if (img) {
      lead.src = img;
      lead.alt = story.headline || '';
      if (i === 0) { lead.loading = 'eager'; lead.fetchPriority = 'high'; }
      lead.addEventListener('error', () => media.classList.add('noimg'), { once: true });
    } else {
      media.classList.add('noimg');
    }
    node.querySelector('.rank').textContent = String(i + 1);

    node.querySelector('.source').textContent = story.source || '';
    const t = node.querySelector('.time');
    t.textContent = fmtTime(story.published);
    if (story.published) t.dateTime = story.published;
    if (!t.textContent) node.querySelector('.dot').hidden = true;

    const h = node.querySelector('.headline a');
    h.textContent = story.headline || '';
    h.href = href;
    node.querySelector('.note').textContent = story.note || '';
    node.querySelector('.read').href = href;

    const watch = node.querySelector('.watch');
    const play = node.querySelector('.play');
    if (videoUrl || videoPage) {
      play.hidden = false;
      watch.hidden = false;
      const go = (e) => {
        e.preventDefault();
        if (videoUrl) playInline(media, story, videoUrl);
        else window.open(videoPage, '_blank', 'noopener');
      };
      play.addEventListener('click', go);
      watch.href = videoPage || videoUrl;
      watch.addEventListener('click', go);
    }
    return node;
  }

  /* ---------- story page ---------- */
  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function renderStory(story, i, total) {
    const url = safeUrl(story.url);
    const img = safeUrl(story.image);
    const videoUrl = safeUrl(story.video_url);
    const videoPage = safeUrl(story.video_page);
    const parts = [];

    const fig = el('div', 'story-media');
    if (img) {
      const im = el('img', 'lead');
      im.src = img; im.alt = story.headline || ''; im.decoding = 'async';
      im.referrerPolicy = 'no-referrer';
      im.addEventListener('error', () => fig.classList.add('noimg'), { once: true });
      fig.append(im);
    } else {
      fig.classList.add('noimg');
    }
    parts.push(fig);

    const wrap = el('div', 'story-body');
    const by = el('p', 'byline');
    by.append(el('span', 'source', story.source || ''));
    const when = fmtTime(story.published, longTimeFmt);
    if (when) {
      by.append(el('span', 'dot', '·'));
      const t = el('time', 'time', when); t.dateTime = story.published; by.append(t);
    }
    wrap.append(by);
    wrap.append(el('h2', 'story-headline', story.headline || ''));

    if (videoUrl) {
      const v = el('div', 'story-video');
      v.append(videoEl(story, videoUrl, false));
      wrap.append(v);
    } else if (videoPage) {
      const a = el('a', 'btn watch', 'Watch the video');
      a.href = videoPage; a.target = '_blank'; a.rel = 'noopener';
      wrap.append(a);
    }

    const body = Array.isArray(story.body) ? story.body.filter((p) => typeof p === 'string' && p.trim()) : [];
    const text = el('div', 'story-text');
    if (body.length) {
      body.forEach((p) => text.append(el('p', null, p)));
    } else {
      if (story.note) text.append(el('p', null, story.note));
      text.append(el('p', 'muted', 'The full write-up for this story isn\'t ready yet.'));
    }
    wrap.append(text);

    if (url) {
      const orig = el('p', 'original');
      const a = el('a', null, 'Original article on ' + (story.source || new URL(url).hostname));
      a.href = url; a.target = '_blank'; a.rel = 'noopener';
      orig.append(a);
      wrap.append(orig);
    }

    const nav = el('nav', 'story-nav');
    const back = el('a', 'btn', '← All headlines');
    back.href = '#/';
    back.addEventListener('click', (e) => { e.preventDefault(); goBack(); });
    nav.append(back);
    if (i + 1 < total) {
      const next = el('a', 'btn next', 'Next story →');
      next.href = storyHref(i + 1);
      next.addEventListener('click', (e) => { e.preventDefault(); location.replace(storyHref(i + 1)); });
      nav.append(next);
    }
    wrap.append(nav);
    parts.push(wrap);

    storyEl.replaceChildren(...parts);
    document.title = (story.headline || 'Story') + ' · The Real Republican';
  }

  /* ---------- routing ---------- */
  let data = null;
  let feedScroll = 0;
  let view = 'feed';
  let enteredFromFeed = false;

  function storyIndex() {
    const m = /^#\/story\/(\d+)/.exec(location.hash);
    return m ? parseInt(m[1], 10) - 1 : -1;
  }

  function showFeed() {
    const wasStory = view === 'story';
    view = 'feed';
    document.body.classList.remove('in-story');
    storyEl.hidden = true;
    storyEl.replaceChildren(); // stops any playing video
    feed.hidden = false;
    backBtn.hidden = true;
    metaEl.hidden = false;
    if (data) document.title = 'Digest · ' + fmtDate(data.date);
    if (wasStory) requestAnimationFrame(() => window.scrollTo(0, feedScroll));
  }

  function route() {
    const i = storyIndex();
    const stories = data && Array.isArray(data.stories) ? data.stories : [];
    if (i < 0) { showFeed(); return; }
    if (!data) return; // will route again after load
    if (i >= stories.length) { location.replace('#/'); return; }
    if (view === 'feed') feedScroll = window.scrollY;
    view = 'story';
    document.body.classList.add('in-story');
    feed.hidden = true;
    storyEl.hidden = false;
    backBtn.hidden = false;
    metaEl.hidden = true;
    renderStory(stories[i], i, stories.length);
    window.scrollTo(0, 0);
  }

  function goBack() {
    // Use real history when we came from the feed, so Android's back gesture and this button agree.
    if (enteredFromFeed) history.back();
    else location.replace('#/');
  }

  document.addEventListener('click', (e) => {
    const a = e.target.closest && e.target.closest('a[href^="#/story/"]');
    if (a && view === 'feed') enteredFromFeed = true;
  }, true);
  window.addEventListener('hashchange', () => {
    if (storyIndex() < 0) enteredFromFeed = false;
    route();
  });
  backBtn.addEventListener('click', goBack);

  /* ---------- data ---------- */
  let lastStamp = null;
  function render(d) {
    const stamp = (d.generated_at || '') + '|' + (d.date || '') + '|' + JSON.stringify(d.stories || []).length;
    if (stamp === lastStamp && feed.querySelector('.card')) return; // unchanged: keep playing videos
    lastStamp = stamp;
    data = d;
    dateEl.textContent = fmtDate(d.date);
    const stories = Array.isArray(d.stories) ? d.stories : [];
    const gen = d.generated_at ? fmtTime(d.generated_at) : '';
    metaEl.textContent = `${stories.length} stories` + (gen ? ` · updated ${gen}` : '');
    feed.replaceChildren(...stories.map(card));
    if (!stories.length) feed.innerHTML = '<p class="status">No stories in today\'s digest yet.</p>';
    route();
  }

  async function load() {
    refreshBtn.classList.add('spin');
    try {
      const res = await fetch('headlines.json?t=' + Date.now(), { cache: 'no-store' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      render(await res.json());
    } catch (err) {
      if (!feed.children.length) {
        feed.innerHTML = '<p class="status">Couldn\'t load today\'s digest. Check your connection and tap refresh.</p>';
        dateEl.textContent = 'Daily Digest';
      }
      console.error(err);
    } finally {
      refreshBtn.classList.remove('spin');
    }
  }

  refreshBtn.addEventListener('click', load);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') load(); });
  load();

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(console.error));
  }
})();
