/* The Real Republican - renders headlines.json as a phone-first card feed. */
(() => {
  'use strict';
  const TZ = 'America/Phoenix';
  const feed = document.getElementById('feed');
  const tpl = document.getElementById('card-tpl');
  const dateEl = document.getElementById('digest-date');
  const metaEl = document.getElementById('meta');
  const refreshBtn = document.getElementById('refresh');

  const timeFmt = new Intl.DateTimeFormat('en-US', {
    timeZone: TZ, hour: 'numeric', minute: '2-digit', month: 'short', day: 'numeric'
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

  function fmtTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return isNaN(d) ? '' : timeFmt.format(d) + ' AZ';
  }
  function fmtDate(ymd) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(ymd || '');
    if (!m) return ymd || '';
    return dateFmt.format(new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])));
  }

  function playInline(media, story, videoUrl) {
    let el;
    if (isFile(videoUrl)) {
      el = document.createElement('video');
      el.src = videoUrl;
      el.controls = true;
      el.autoplay = true;
      el.playsInline = true;
      el.setAttribute('playsinline', '');
      if (story.image) el.poster = story.image;
      el.addEventListener('error', () => {
        // If the publisher blocks playback, fall back to opening the video page.
        const page = safeUrl(story.video_page) || safeUrl(story.url);
        if (page) window.open(page, '_blank', 'noopener');
      }, { once: true });
    } else {
      el = document.createElement('iframe');
      el.src = videoUrl;
      el.allow = 'autoplay; fullscreen; picture-in-picture; encrypted-media';
      el.allowFullscreen = true;
      el.referrerPolicy = 'strict-origin-when-cross-origin';
      el.title = 'Video: ' + (story.headline || '');
    }
    media.querySelector('.media-link').replaceWith(el);
    media.querySelector('.play').remove();
    const rank = media.querySelector('.rank'); if (rank) rank.remove();
    const p = el.play && el.play();
    if (p && p.catch) p.catch(() => {});
  }

  function card(story, i) {
    const node = tpl.content.firstElementChild.cloneNode(true);
    const url = safeUrl(story.url);
    const img = safeUrl(story.image);
    const videoUrl = safeUrl(story.video_url);
    const videoPage = safeUrl(story.video_page);

    const media = node.querySelector('.media');
    const mediaLink = node.querySelector('.media-link');
    const lead = node.querySelector('.lead');
    mediaLink.href = url || '#';
    mediaLink.setAttribute('aria-label', story.headline || 'Open story');
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
    if (url) h.href = url;
    node.querySelector('.note').textContent = story.note || '';
    const read = node.querySelector('.read');
    if (url) read.href = url; else read.hidden = true;
    if (story.source) read.textContent = 'Read on ' + story.source;

    const watch = node.querySelector('.watch');
    const play = node.querySelector('.play');
    if (videoUrl || videoPage) {
      play.hidden = false;
      if (videoUrl) {
        play.addEventListener('click', () => playInline(media, story, videoUrl));
      } else {
        play.addEventListener('click', () => window.open(videoPage, '_blank', 'noopener'));
      }
      watch.hidden = false;
      watch.href = videoPage || videoUrl;
      if (videoPage && /fox(news|business)\.com\/video/.test(videoPage)) {
        watch.lastChild.textContent = ' Watch on Fox';
      }
    }
    return node;
  }

  let lastStamp = null;
  function render(data) {
    const stamp = (data.generated_at || '') + '|' + (data.date || '');
    if (stamp === lastStamp && feed.querySelector('.card')) return; // unchanged: keep playing videos
    lastStamp = stamp;
    dateEl.textContent = fmtDate(data.date);
    document.title = 'Digest · ' + fmtDate(data.date);
    const stories = Array.isArray(data.stories) ? data.stories : [];
    const gen = data.generated_at ? fmtTime(data.generated_at) : '';
    metaEl.textContent = `${stories.length} stories` + (gen ? ` · updated ${gen}` : '');
    feed.replaceChildren(...stories.map(card));
    if (!stories.length) feed.innerHTML = '<p class="status">No stories in today\'s digest yet.</p>';
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
