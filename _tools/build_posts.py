import json, re, html, os, math, datetime

SITE = "https://www.coastaldental.com.au"
BUILD = "/home/claude/finalbuild"
posts = json.load(open('/home/claude/migration/posts_final.json'))

# ---------- shell from an existing page ----------
src = open(os.path.join(BUILD, 'blog.html')).read()
nav_end = src.find('</nav>') + len('</nav>')
# mobile menu sits right after </nav>
mm_end = src.find('</div>\n</div>', src.find('id="mMenu"'))
mm_end = src.find('\n', src.find('</div>', src.find('m-phone')))
head_start = src[:nav_end]
# capture the mobile menu block too
mob_i = src.find('\n\n<!-- MOBILE MENU -->')
mob_j = src.find('<main>')
mobile_block = src[mob_i:mob_j] if mob_i > 0 and mob_j > mob_i else ''
foot = src[src.find('<!-- FOOTER -->'):]


def strip_head_tags(h):
    """Remove any canonical/OG/twitter tags already in the base head so
    re-running the build cannot stack duplicates."""
    import re as _re
    for pat in (r'<link rel="canonical"[^>]*>\s*',
                r'<meta property="og:(?:type|title|description|url|image)"[^>]*>\s*',
                r'<meta name="twitter:card"[^>]*>\s*'):
        h = _re.sub(pat, '', h)
    return h

def clean_txt(s):
    return html.unescape(re.sub(r'<[^>]+>', '', s)).strip()

def esc(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
             .replace('"', '&quot;'))

def local_img(url):
    if not url:
        return ''
    return url.split('coastaldental.com.au/')[-1].lstrip('/')

def wp_body(content):
    """WordPress classic content: block tags stay as-is, loose text becomes
    paragraphs (blank line = new paragraph, single newline = <br>)."""
    if not content.strip():
        return ''
    BLOCK = r'h1|h2|h3|h4|h5|h6|ul|ol|table|blockquote|figure|div|p|pre'
    out, pos = [], 0
    text = content

    def flush(chunk):
        chunk = chunk.strip('\n')
        if not chunk.strip():
            return
        for para in re.split(r'\n\s*\n', chunk):
            para = para.strip()
            if para:
                out.append('<p>' + para.replace('\n', '<br>') + '</p>')

    while pos < len(text):
        m = re.search(r'<(' + BLOCK + r')\b[^>]*>', text[pos:], re.I)
        if not m:
            flush(text[pos:])
            break
        start = pos + m.start()
        flush(text[pos:start])
        tag = m.group(1).lower()
        # find matching close tag, accounting for nesting of the same tag
        depth, i = 0, start
        open_re = re.compile(r'<' + tag + r'\b[^>]*>', re.I)
        close_re = re.compile(r'</' + tag + r'\s*>', re.I)
        end = None
        while i < len(text):
            o = open_re.search(text, i)
            c = close_re.search(text, i)
            if not c:
                break
            if o and o.start() < c.start():
                depth += 1
                i = o.end()
            else:
                depth -= 1
                i = c.end()
                if depth == 0:
                    end = i
                    break
        if end is None:
            flush(text[start:])
            break
        out.append(text[start:end].strip())
        pos = end

    body = '\n'.join(out)
    body = body.replace('https://www.coastaldental.com.au/wp-content/', 'wp-content/')
    body = body.replace('http://www.coastaldental.com.au/wp-content/', 'wp-content/')
    return body

def make_excerpt(content, limit=190):
    t = clean_txt(content)
    t = re.sub(r'\s+', ' ', t)
    if len(t) <= limit:
        return t
    cut = t[:limit]
    return cut[:cut.rfind(' ')] + '...'

def fmt_date(d):
    try:
        dt = datetime.datetime.strptime(d[:10], '%Y-%m-%d')
        return dt.strftime('%-d %B %Y')
    except Exception:
        return d[:10]

def iso(d):
    try:
        return datetime.datetime.strptime(d[:19], '%Y-%m-%d %H:%M:%S').isoformat()
    except Exception:
        return d[:10]

POST_CSS = '''
<style>
.post-hero{position:relative;min-height:46vh;display:flex;align-items:flex-end;padding:0 0 clamp(2rem,5vw,3.6rem);overflow:hidden;margin-top:78px}
.post-hero .ph-bg{position:absolute;inset:0}
.post-hero .ph-bg img{width:100%;height:100%;object-fit:cover}
.post-hero .ph-bg::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(42,53,55,.35) 0%,rgba(42,53,55,.88) 100%)}
.ph-inner{position:relative;z-index:2;width:min(880px,92vw);margin:0 auto;color:var(--white)}
.ph-inner .crumb{margin-bottom:18px}
.ph-inner .crumb a,.ph-inner .crumb span{color:rgba(255,255,255,.8)}
.ph-inner .crumb a:hover{color:var(--white)}
.ph-cat{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;background:var(--mint);color:var(--primary);padding:6px 14px;border-radius:100px;margin-bottom:16px}
.ph-inner h1{font-family:var(--serif);font-size:clamp(28px,4.4vw,48px);line-height:1.16;color:var(--white);margin-bottom:16px}
.ph-meta{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:13px;color:rgba(255,255,255,.82)}
.ph-meta .mdot{width:4px;height:4px;border-radius:50%;background:rgba(255,255,255,.5)}
.post-wrap{background:var(--white);padding:clamp(2.6rem,6vw,4.6rem) 0}
.post-body{width:min(760px,92vw);margin:0 auto;font-size:16px;line-height:1.85;color:var(--muted)}
.post-body>p{margin-bottom:1.35em}
.post-body h2{font-family:var(--serif);font-size:clamp(22px,2.8vw,30px);color:var(--primary);margin:2em 0 .7em;line-height:1.3}
.post-body h3{font-family:var(--serif);font-size:clamp(19px,2.2vw,23px);color:var(--primary);margin:1.7em 0 .6em}
.post-body h4,.post-body h5{font-size:16px;font-weight:700;color:var(--primary);margin:1.5em 0 .5em}
.post-body ul,.post-body ol{margin:0 0 1.35em 1.1em;display:flex;flex-direction:column;gap:.55em}
.post-body li{padding-left:.3em}
.post-body strong{color:var(--primary);font-weight:700}
.post-body a{color:var(--primary);text-decoration:underline;text-underline-offset:3px}
.post-body a:hover{color:var(--primary-light)}
.post-body img{max-width:100%;height:auto;border-radius:var(--r2);margin:1.6em 0}
.post-body table{width:100%;border-collapse:collapse;margin:1.6em 0;font-size:14.5px;display:block;overflow-x:auto}
.post-body th,.post-body td{border:1px solid var(--border);padding:11px 14px;text-align:left}
.post-body th{background:var(--secondary);color:var(--primary);font-weight:700}
.post-share{width:min(760px,92vw);margin:clamp(2rem,4vw,3rem) auto 0;padding-top:1.6rem;border-top:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}
.post-share .ps-label{font-size:12px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.ps-links{display:flex;gap:10px}
.ps-links a{width:38px;height:38px;border-radius:50%;border:1.5px solid var(--border);display:flex;align-items:center;justify-content:center;transition:all .3s var(--ease)}
.ps-links a:hover{background:var(--primary);border-color:var(--primary)}
.ps-links svg{width:16px;height:16px;stroke:var(--primary);fill:none;stroke-width:1.9}
.ps-links a:hover svg{stroke:var(--white)}
.post-rel{background:var(--off-white);padding:var(--section-pad)}
.pr-head{text-align:center;margin-bottom:clamp(1.8rem,3vw,2.6rem)}
.pr-head h2{font-family:var(--serif);font-size:clamp(24px,3vw,34px);color:var(--primary)}
.pr-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
@media(max-width:900px){.pr-grid{grid-template-columns:1fr 1fr}}
@media(max-width:620px){.pr-grid{grid-template-columns:1fr}.post-hero{min-height:40vh}}
</style>
'''

CAT_FALLBACK = 'Dental Tips'


def card(p, delay=1):
    cat = (p['categories'] or [CAT_FALLBACK])[0]
    return f'''        <article class="bp-card" data-r data-d="{delay}">
          <a href="{p['slug']}.html" aria-label="Read: {esc(clean_txt(p['title']))}">
            <div class="bp-media">
              <img src="{local_img(p['featured'])}" alt="{esc(p['featured_alt'] or clean_txt(p['title']))}" loading="lazy">
              <span class="bp-cat">{esc(cat)}</span>
            </div>
            <div class="bp-body">
              <div class="bp-tag">{fmt_date(p['date'])}</div>
              <h3>{esc(clean_txt(p['title']))}</h3>
              <p>{esc(make_excerpt(p['content']))}</p>
              <span class="bp-more">Read More <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg></span>
            </div>
          </a>
        </article>'''


# ---------------- build post pages ----------------
built = 0
for idx, p in enumerate(posts):
    title = clean_txt(p['title'])
    seo_title = p.get('_yoast_wpseo_title') or f"{title} | Coastal Dental"
    seo_desc = p.get('_yoast_wpseo_metadesc') or make_excerpt(p['content'], 155)
    cat = (p['categories'] or [CAT_FALLBACK])[0]
    img = local_img(p['featured'])
    body = wp_body(p['content'])
    canonical = f"{SITE}/{p['slug']}/"

    head = head_start
    head = re.sub(r'<title>.*?</title>', f'<title>{esc(seo_title)}</title>', head, count=1, flags=re.S)
    head = re.sub(r'(name="description" content=")[^"]*(")',
                  lambda m: m.group(1) + esc(seo_desc) + m.group(2), head, count=1)
    head = strip_head_tags(head)
    head = head.replace('</head>', POST_CSS + '</head>')

    schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title,
        "description": seo_desc,
        "image": SITE + "/" + img,
        "datePublished": iso(p['date']),
        "dateModified": iso(p.get('modified') or p['date']),
        "author": {"@type": "Organization", "name": "Coastal Dental"},
        "publisher": {"@type": "Organization", "name": "Coastal Dental"},
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
    }
    crumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Blog", "item": SITE + "/blog/"},
            {"@type": "ListItem", "position": 3, "name": title, "item": canonical},
        ],
    }
    head = head.replace('</head>',
        f'<link rel="canonical" href="{canonical}">\n'
        f'<meta property="og:type" content="article">\n'
        f'<meta property="og:title" content="{esc(title)}">\n'
        f'<meta property="og:description" content="{esc(seo_desc)}">\n'
        f'<meta property="og:image" content="{SITE}/{img}">\n'
        f'<meta property="og:url" content="{canonical}">\n'
        f'<meta property="article:published_time" content="{iso(p["date"])}">\n'
        f'<meta property="article:modified_time" content="{iso(p.get("modified") or p["date"])}">\n'
        f'<meta name="twitter:card" content="summary_large_image">\n'
        f'<script type="application/ld+json">{json.dumps(schema)}</script>\n'
        f'<script type="application/ld+json">{json.dumps(crumbs)}</script>\n</head>')

    # related = 3 nearest posts sharing a category, else nearest by date
    same = [q for q in posts if q is not p and set(q['categories']) & set(p['categories'])]
    rel = (same or [q for q in posts if q is not p])[:3]
    rel_html = '\n'.join(card(r, i + 1) for i, r in enumerate(rel))

    page = head + mobile_block + f'''
<main>

  <article>
  <section class="post-hero">
    <div class="ph-bg"><img src="{img}" alt="{esc(p['featured_alt'] or title)}"></div>
    <div class="ph-inner">
      <nav class="crumb" aria-label="Breadcrumb"><a href="index.html">Home</a><span class="sep">&rsaquo;</span><a href="blog.html">Blog</a><span class="sep">&rsaquo;</span><span>{esc(title)}</span></nav>
      <span class="ph-cat">{esc(cat)}</span>
      <h1>{esc(title)}</h1>
      <div class="ph-meta">
        <time datetime="{p['date'][:10]}">{fmt_date(p['date'])}</time>
        <span class="mdot"></span>
        <span>Coastal Dental</span>
      </div>
    </div>
  </section>

  <div class="post-wrap">
    <div class="post-body">
{body}
    </div>
    <div class="post-share">
      <span class="ps-label">Share this article</span>
      <div class="ps-links">
        <a href="https://www.facebook.com/sharer/sharer.php?u={canonical}" target="_blank" rel="noopener" aria-label="Share on Facebook"><svg viewBox="0 0 24 24"><path d="M18 2h-3a5 5 0 00-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 011-1h3z"/></svg></a>
        <a href="https://www.linkedin.com/sharing/share-offsite/?url={canonical}" target="_blank" rel="noopener" aria-label="Share on LinkedIn"><svg viewBox="0 0 24 24"><path d="M16 8a6 6 0 016 6v7h-4v-7a2 2 0 00-4 0v7h-4v-7a6 6 0 016-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg></a>
        <a href="mailto:?subject={esc(title)}&amp;body={canonical}" aria-label="Share by email"><svg viewBox="0 0 24 24"><path d="M4 4h16a2 2 0 012 2v12a2 2 0 01-2 2H4a2 2 0 01-2-2V6a2 2 0 012-2z"/><polyline points="22,6 12,13 2,6"/></svg></a>
      </div>
    </div>
  </div>
  </article>

  <section class="post-rel">
    <div class="wrap">
      <div class="pr-head" data-r><h2>More from our <em style="font-style:italic">blog</em></h2></div>
      <div class="pr-grid">
{rel_html}
      </div>
    </div>
  </section>

  <div class="sp-cta">
    <div class="wrap">
      <div class="sp-cta-inner">
        <div data-r>
          <h2>Have a question about <em>your smile?</em></h2>
          <p>Our team at Coastal Dental Gosford is always happy to talk things through. Book a consultation and get answers specific to you.</p>
        </div>
        <div class="sp-cta-side" data-r data-d="1">
          <div class="sp-cta-num">(02) 4306 7053</div>
          <a href="book-now.html" class="btn btn-white"><span>Book an Appointment</span></a>
          <a href="tel:0243067053" class="btn btn-ghost"><span>Call Now</span></a>
        </div>
      </div>
    </div>
  </div>

</main>

'''
    open(os.path.join(BUILD, p['slug'] + '.html'), 'w').write(page + foot)
    built += 1

print("post pages built:", built)
json.dump([{'slug': p['slug'], 'title': clean_txt(p['title']), 'date': p['date'],
            'cat': (p['categories'] or [CAT_FALLBACK])[0]} for p in posts],
          open('/home/claude/migration/built_index.json', 'w'), indent=1)
