/* =====================================================================
   GYA Site CMS  |  RUNTIME
   ---------------------------------------------------------------------
   Loaded on every public page. It never talks to a database directly,
   only to window.CMS_ADAPTER, so it works unchanged with any backend.

   What it does:
   1. Applies saved edits: text, images, SEO tags, section order.
   2. Applies practice details sitewide (phone, email, address, hours,
      booking link, health funds) by swapping the built-in defaults.
   3. Shows dashboard-created blog posts on the blog index and renders
      them on post.html?slug=...
   4. When the page is opened inside the dashboard, switches on
      click-to-edit. A visitor adding ?cms-edit=1 gets nothing: editing
      only starts when the dashboard (same origin) sends the handshake.

   If nothing has been saved, it changes nothing: the page stays exactly
   as built.
   ===================================================================== */

(function () {
  const A = window.CMS_ADAPTER;
  const SITE = window.CMS_SITE || { defaults: {} };
  if (!A) return;

  const html = document.documentElement;
  const SLUG = html.getAttribute('data-cms-page') || '';
  const IN_FRAME = window.parent && window.parent !== window;
  const WANTS_EDIT = IN_FRAME && new URLSearchParams(location.search).get('cms-edit') === '1';

  /* ------------------------------------------------------------ safety */
  const ALLOWED = { B: 1, STRONG: 1, I: 1, EM: 1, U: 1, BR: 1, A: 1, SPAN: 1, SUP: 1, SUB: 1 };

  function sanitizeInline(input) {
    const doc = new DOMParser().parseFromString('<div>' + String(input || '') + '</div>', 'text/html');
    const root = doc.body.firstChild;
    (function walk(node) {
      [...node.childNodes].forEach(ch => {
        if (ch.nodeType === 3) return;
        if (ch.nodeType !== 1) { ch.remove(); return; }
        if (!ALLOWED[ch.tagName]) {
          walk(ch);
          while (ch.firstChild) ch.parentNode.insertBefore(ch.firstChild, ch);
          ch.remove();
          return;
        }
        [...ch.attributes].forEach(at => {
          const keep = ch.tagName === 'A' && (at.name === 'href' || at.name === 'target' || at.name === 'rel');
          if (!keep) ch.removeAttribute(at.name);
        });
        if (ch.tagName === 'A') {
          const h = (ch.getAttribute('href') || '').trim();
          if (/^\s*(javascript|data|vbscript):/i.test(h)) ch.removeAttribute('href');
        }
        walk(ch);
      });
    })(root);
    return root.innerHTML;
  }

  const BLOCK_ALLOWED = Object.assign({}, ALLOWED, {
    P: 1, H2: 1, H3: 1, H4: 1, UL: 1, OL: 1, LI: 1, BLOCKQUOTE: 1,
    TABLE: 1, THEAD: 1, TBODY: 1, TR: 1, TD: 1, TH: 1, IMG: 1,
  });

  function sanitizeBlock(input) {
    const doc = new DOMParser().parseFromString('<div>' + String(input || '') + '</div>', 'text/html');
    const root = doc.body.firstChild;
    (function walk(node) {
      [...node.childNodes].forEach(ch => {
        if (ch.nodeType === 3) return;
        if (ch.nodeType !== 1) { ch.remove(); return; }
        if (!BLOCK_ALLOWED[ch.tagName]) {
          walk(ch);
          while (ch.firstChild) ch.parentNode.insertBefore(ch.firstChild, ch);
          ch.remove();
          return;
        }
        [...ch.attributes].forEach(at => {
          const ok = (ch.tagName === 'A' && ['href', 'target', 'rel'].includes(at.name)) ||
                     (ch.tagName === 'IMG' && ['src', 'alt'].includes(at.name));
          if (!ok) ch.removeAttribute(at.name);
        });
        ['href', 'src'].forEach(a => {
          const v = ch.getAttribute && ch.getAttribute(a);
          if (v && /^\s*(javascript|vbscript):/i.test(v)) ch.removeAttribute(a);
        });
        walk(ch);
      });
    })(root);
    return root.innerHTML;
  }

  const esc = s => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  /* -------------------------------------------------------- page edits */
  function setMeta(attr, key, value) {
    if (!value) return;
    let m = document.head.querySelector(`meta[${attr}="${key}"]`);
    if (!m) { m = document.createElement('meta'); m.setAttribute(attr, key); document.head.appendChild(m); }
    m.setAttribute('content', value);
  }

  function applyImage(el, v) {
    if (!v) return;
    const src = typeof v === 'string' ? v : v.src;
    if (!src) {                       // alt text only
      if (v.alt) { if (el.tagName === 'IMG') el.alt = v.alt; else el.setAttribute('aria-label', v.alt); }
      return;
    }
    if (el.tagName === 'IMG') {
      el.removeAttribute('srcset');
      el.removeAttribute('sizes');
      el.src = src;
      if (v.alt != null && v.alt !== '') el.alt = v.alt;
    } else {
      el.style.backgroundImage = `url("${src.replace(/"/g, '%22')}")`;
      if (v.alt) el.setAttribute('aria-label', v.alt);
    }
  }

  function sectionsOf(main) {
    return [...main.children].filter(el => el.hasAttribute('data-cms-section'));
  }

  function applyOrder(order) {
    const main = document.querySelector('main');
    if (!main || !Array.isArray(order) || !order.length) return;
    const secs = sectionsOf(main);
    const byId = Object.fromEntries(secs.map(s => [s.getAttribute('data-cms-section'), s]));
    const pinned = secs.filter(s => s.hasAttribute('data-cms-pinned'));
    const movable = secs.filter(s => !s.hasAttribute('data-cms-pinned'));
    const wanted = order.map(id => byId[id]).filter(el => el && !el.hasAttribute('data-cms-pinned'));
    const rest = movable.filter(el => !wanted.includes(el));
    const anchor = pinned.length ? pinned[pinned.length - 1] : null;
    let after = anchor;
    [...wanted, ...rest].forEach(el => {
      if (after) after.after(el); else main.prepend(el);
      after = el;
    });
  }

  function applyPage(doc) {
    if (!doc) return;
    const text = doc.text || {};
    Object.keys(text).forEach(id => {
      const el = document.querySelector(`[data-cms="${id}"]`);
      if (el) el.innerHTML = sanitizeInline(text[id]);
    });
    const img = doc.img || {};
    Object.keys(img).forEach(id => {
      document.querySelectorAll(`[data-cms-img="${id}"]`).forEach(el => applyImage(el, img[id]));
    });
    const seo = doc.seo || {};
    if (seo.title) {
      document.title = seo.title;
      setMeta('property', 'og:title', seo.title);
    }
    if (seo.description) {
      setMeta('name', 'description', seo.description);
      setMeta('property', 'og:description', seo.description);
    }
    if (seo.ogImage) {
      const abs = /^https?:|^data:/.test(seo.ogImage) ? seo.ogImage
        : new URL(seo.ogImage, location.href).href;
      setMeta('property', 'og:image', abs);
    }
    if (doc.order) applyOrder(doc.order);
  }

  /* -------------------------------------------------- practice details */
  function replaceTextEverywhere(from, to) {
    if (!from || !to || from === to) return;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: n => (n.nodeValue.indexOf(from) !== -1 && !n.parentNode.closest('script,style,[contenteditable="true"]'))
        ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT,
    });
    const hits = [];
    while (walker.nextNode()) hits.push(walker.currentNode);
    hits.forEach(n => { n.nodeValue = n.nodeValue.split(from).join(to); });
  }

  function applyPractice(p) {
    if (!p) return;
    const d = SITE.defaults || {};

    if (p.phone && d.phone) replaceTextEverywhere(d.phone, p.phone);
    if (p.tel && d.tel && p.tel !== d.tel) {
      document.querySelectorAll(`a[href="tel:${d.tel}"]`).forEach(a => a.setAttribute('href', 'tel:' + p.tel));
    }

    if (p.email && d.email && p.email !== d.email) {
      replaceTextEverywhere(d.email, p.email);
      document.querySelectorAll(`a[href^="mailto:${d.email}"]`).forEach(a => {
        a.setAttribute('href', a.getAttribute('href').replace(d.email, p.email));
      });
    }

    if (p.address1 && d.address1) replaceTextEverywhere(d.address1, p.address1);
    if (p.address2 && d.address2) replaceTextEverywhere(d.address2, p.address2);

    if (Array.isArray(p.hours) && p.hours.length) {
      const byDay = {};
      p.hours.forEach(h => { if (h && h.day) byDay[h.day.trim().toLowerCase()] = h.time; });
      document.querySelectorAll('.f-hours > div, .cm-hours > div').forEach(row => {
        const spans = row.querySelectorAll('span');
        if (spans.length < 2) return;
        const t = byDay[spans[0].textContent.trim().toLowerCase()];
        if (t != null && t !== '') spans[1].textContent = t;
      });
    }

    if (p.bookingUrl && d.bookingUrl && p.bookingUrl !== d.bookingUrl) {
      document.querySelectorAll('iframe').forEach(f => {
        if (f.getAttribute('src') === d.bookingUrl) f.setAttribute('src', p.bookingUrl);
      });
    }

    if (Array.isArray(p.funds) && p.funds.length) {
      document.querySelectorAll('.funds-track').forEach(track => {
        const items = p.funds.filter(f => f && f.logo).map(f =>
          `<span class="fund-box"><img class="fund-logo" src="${esc(f.logo)}" alt="${esc(f.name || '')}" loading="lazy"></span>`
        ).join('');
        // keep the seamless loop if the original strip was duplicated
        const dup = track.children.length > 0 && track.children.length >= (d.fundsCount || 0) * 2;
        track.innerHTML = dup ? items + items : items;
      });
    }
  }

  /* --------------------------------------------- dashboard blog posts */
  const fmtDate = s => {
    const d = new Date(s);
    return isNaN(d) ? '' : d.toLocaleDateString('en-AU', { day: 'numeric', month: 'long', year: 'numeric' });
  };

  function postCard(p) {
    return `<article class="bp-card is-visible">
          <a href="post.html?slug=${encodeURIComponent(p.slug)}" aria-label="Read: ${esc(p.title)}">
            <div class="bp-media">
              ${p.image ? `<img src="${esc(p.image)}" alt="${esc(p.imageAlt || p.title)}" loading="lazy">` : ''}
              <span class="bp-cat">${esc(p.category || 'Blog')}</span>
            </div>
            <div class="bp-body">
              <div class="bp-tag">${esc(fmtDate(p.date))}</div>
              <h3>${esc(p.title)}</h3>
              <p>${esc(p.excerpt || '')}</p>
              <span class="bp-more">Read More <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg></span>
            </div>
          </a>
        </article>`;
  }

  function applyPosts(posts) {
    const live = (posts || []).filter(p => p && p.status === 'published' && p.slug)
      .sort((a, b) => String(b.date).localeCompare(String(a.date)));

    // blog index: new posts go to the top of the first page's grid
    if (SLUG === 'blog' && live.length) {
      const grid = document.querySelector('.bg-grid');
      if (grid) grid.insertAdjacentHTML('afterbegin', live.map(postCard).join(''));
    }

    // post.html?slug=...
    if (SLUG === 'post') {
      const slug = new URLSearchParams(location.search).get('slug');
      const all = posts || [];
      const p = all.find(x => x.slug === slug && (x.status === 'published' || WANTS_EDIT));
      const holder = document.querySelector('[data-cms-post]');
      if (!holder) return;
      if (!p) {
        holder.innerHTML = '<div class="post-body" style="padding:4rem 0;text-align:center"><h2>Post not found</h2><p>This article may have been moved or unpublished.</p><p><a href="blog.html">Back to the blog</a></p></div>';
        document.title = 'Post not found | ' + (SITE.name || '');
        return;
      }
      document.title = p.seoTitle || (p.title + ' | ' + (SITE.name || ''));
      setMeta('name', 'description', p.seoDescription || p.excerpt || '');
      setMeta('property', 'og:title', p.seoTitle || p.title);
      setMeta('property', 'og:description', p.seoDescription || p.excerpt || '');
      if (p.image) setMeta('property', 'og:image', /^https?:|^data:/.test(p.image) ? p.image : new URL(p.image, location.href).href);
      const t = holder.querySelector('[data-post-title]');
      const c = holder.querySelector('[data-post-cat]');
      const dt = holder.querySelector('[data-post-date]');
      const im = holder.querySelector('[data-post-image]');
      const bd = holder.querySelector('[data-post-body]');
      const cr = holder.querySelector('[data-post-crumb]');
      if (t) t.textContent = p.title;
      if (cr) cr.textContent = p.title;
      if (c) c.textContent = p.category || 'Blog';
      if (dt) { dt.textContent = fmtDate(p.date); dt.setAttribute('datetime', String(p.date).slice(0, 10)); }
      if (im) { if (p.image) { im.src = p.image; im.alt = p.imageAlt || p.title; } else im.remove(); }
      if (bd) bd.innerHTML = sanitizeBlock(p.body);
    }
  }

  /* ------------------------------------------------------ edit mode */
  function sectionLabel(el, i) {
    return el.getAttribute('data-cms-label') || ('Section ' + (i + 1));
  }

  function startEditing(pageDoc) {
    const style = document.createElement('style');
    style.textContent = `
      [data-r]{opacity:1!important;transform:none!important}
      [data-cms]{outline:1.5px dashed transparent;outline-offset:3px;border-radius:3px;cursor:text;transition:outline-color .15s}
      [data-cms]:hover{outline-color:rgba(61,122,120,.55)}
      [data-cms]:focus{outline:2px solid #3d7a78;background:rgba(222,234,232,.35)}
      [data-cms-img]{cursor:pointer}
      img[data-cms-img]:hover,[data-cms-img]:not(img):hover{outline:3px solid #3d7a78;outline-offset:-3px}
      .cms-img-tip{position:fixed;z-index:99999;pointer-events:none;background:#2a3537;color:#fff;font:600 12px/1 system-ui,sans-serif;padding:7px 10px;border-radius:7px;opacity:0;transition:opacity .15s}
    `;
    document.head.appendChild(style);

    const tip = document.createElement('div');
    tip.className = 'cms-img-tip';
    tip.textContent = 'Click to replace image';
    document.body.appendChild(tip);

    const post = (m) => window.parent.postMessage(Object.assign({ source: 'gya-cms' }, m), location.origin);

    // links and buttons must not navigate while editing
    document.addEventListener('click', e => {
      const a = e.target.closest('a,button');
      if (a && !e.target.closest('[data-cms-img]')) e.preventDefault();
    }, true);
    document.querySelectorAll('form').forEach(f => f.addEventListener('submit', e => e.preventDefault(), true));

    document.querySelectorAll('[data-cms]').forEach(el => {
      el.setAttribute('contenteditable', 'true');
      el.setAttribute('spellcheck', 'true');
      el.addEventListener('input', () => post({ type: 'text', id: el.getAttribute('data-cms'), html: sanitizeInline(el.innerHTML) }));
      el.addEventListener('paste', e => {
        e.preventDefault();
        const t = (e.clipboardData || window.clipboardData).getData('text/plain');
        document.execCommand('insertText', false, t);
      });
      el.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !/^(LI|P)$/.test(el.tagName)) e.preventDefault();
      });
    });

    document.querySelectorAll('[data-cms-img]').forEach(el => {
      el.addEventListener('mousemove', e => {
        tip.style.opacity = 1; tip.style.left = (e.clientX + 14) + 'px'; tip.style.top = (e.clientY + 14) + 'px';
      });
      el.addEventListener('mouseleave', () => { tip.style.opacity = 0; });
      el.addEventListener('click', e => {
        e.preventDefault(); e.stopPropagation();
        post({ type: 'pick-image', id: el.getAttribute('data-cms-img') });
      }, true);
    });

    const main = document.querySelector('main');
    const secs = main ? sectionsOf(main) : [];
    const imgs = [...document.querySelectorAll('[data-cms-img]')].map(el => ({
      id: el.getAttribute('data-cms-img'),
      src: el.tagName === 'IMG' ? (el.currentSrc || el.src)
        : (getComputedStyle(el).backgroundImage.replace(/^url\(["']?|["']?\)$/g, '') || ''),
      alt: el.getAttribute('alt') || el.getAttribute('aria-label') || '',
    }));
    const og = document.head.querySelector('meta[property="og:image"]');
    const desc = document.head.querySelector('meta[name="description"]');

    post({
      type: 'page-info',
      slug: SLUG,
      title: document.title,
      description: desc ? desc.getAttribute('content') : '',
      ogImage: og ? og.getAttribute('content') : '',
      sections: secs.map((s, i) => ({
        id: s.getAttribute('data-cms-section'),
        label: sectionLabel(s, i),
        pinned: s.hasAttribute('data-cms-pinned'),
      })),
      images: imgs,
      editableCount: document.querySelectorAll('[data-cms]').length,
    });

    window.addEventListener('message', e => {
      if (e.origin !== location.origin || !e.data || e.data.source !== 'gya-cms-admin') return;
      const m = e.data;
      if (m.type === 'set-image') {
        document.querySelectorAll(`[data-cms-img="${m.id}"]`).forEach(el => applyImage(el, { src: m.src, alt: m.alt }));
      }
      if (m.type === 'set-order') applyOrder(m.order);
      if (m.type === 'scroll-to') {
        const el = document.querySelector(`[data-cms-section="${m.id}"],[data-cms-img="${m.id}"]`);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          el.animate([{ outline: '3px solid #3d7a78' }, { outline: '3px solid transparent' }], { duration: 1400 });
        }
      }
    });
  }

  /* ------------------------------------------------------------ boot */
  async function boot() {
    try {
      const [pageDoc, practice, posts] = await Promise.all([
        SLUG ? A.get('page:' + SLUG) : null,
        A.get('site:practice'),
        A.get('site:posts'),
      ]);
      applyPage(pageDoc);
      applyPractice(practice);
      applyPosts(posts);

      if (WANTS_EDIT) {
        window.addEventListener('message', e => {
          if (e.origin !== location.origin || !e.data || e.data.source !== 'gya-cms-admin') return;
          if (e.data.type === 'start-edit' && !window.__cmsEditing) {
            window.__cmsEditing = true;
            startEditing(pageDoc || {});
          }
        });
        window.parent.postMessage({ source: 'gya-cms', type: 'ready', slug: SLUG }, location.origin);
      }
    } catch (err) {
      // never let a CMS problem break the public page
      if (window.console) console.warn('[cms] could not apply saved content:', err);
    }
  }

  window.CMS_RUNTIME = { sanitizeInline, sanitizeBlock };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
