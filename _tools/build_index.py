import json, re, html, os, math, datetime

BUILD = '/home/claude/finalbuild'
SITE = 'https://www.coastaldental.com.au'
posts = json.load(open('/home/claude/migration/posts_final.json'))
PER_PAGE = 12

src = open(os.path.join(BUILD, 'blog.html')).read()
nav_end = src.find('</nav>') + len('</nav>')
head_start = src[:nav_end]
mob_i = src.find('\n\n<!-- MOBILE MENU -->')
mob_j = src.find('<main>')
mobile_block = src[mob_i:mob_j]
foot = src[src.find('<!-- FOOTER -->'):]
hero_i = src.find('<section class="hero')
hero_j = src.find('<!-- FEATURED POST -->')
hero = src[hero_i:hero_j]



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
    return url.split('coastaldental.com.au/')[-1].lstrip('/') if url else ''


def excerpt(content, limit=185):
    t = re.sub(r'\s+', ' ', clean_txt(content))
    if len(t) <= limit:
        return t
    return t[:limit][:t[:limit].rfind(' ')] + '...'


def fmt_date(d):
    try:
        return datetime.datetime.strptime(d[:10], '%Y-%m-%d').strftime('%-d %B %Y')
    except Exception:
        return d[:10]


def card(p, delay=1):
    cat = (p['categories'] or ['Dental Tips'])[0]
    return f'''        <article class="bp-card" data-r data-d="{delay}">
          <a href="{p['slug']}.html" aria-label="Read: {esc(clean_txt(p['title']))}">
            <div class="bp-media">
              <img src="{local_img(p['featured'])}" alt="{esc(p['featured_alt'] or clean_txt(p['title']))}" loading="lazy">
              <span class="bp-cat">{esc(cat)}</span>
            </div>
            <div class="bp-body">
              <div class="bp-tag">{fmt_date(p['date'])}</div>
              <h3>{esc(clean_txt(p['title']))}</h3>
              <p>{esc(excerpt(p['content']))}</p>
              <span class="bp-more">Read More <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg></span>
            </div>
          </a>
        </article>'''


featured = posts[0]
rest = posts[1:]
pages = math.ceil(len(rest) / PER_PAGE)


def pager(current):
    if pages <= 1:
        return ''
    out = ['      <div class="bg-pager">']
    prev = 'blog.html' if current == 2 else f'blog-{current-1}.html'
    if current > 1:
        out.append(f'        <a href="{prev}" class="pg-btn">Prev</a>')
    else:
        out.append('        <span class="pg-btn disabled">Prev</span>')
    for n in range(1, pages + 1):
        href = 'blog.html' if n == 1 else f'blog-{n}.html'
        if n == current:
            out.append(f'        <span class="pg-btn active">{n}</span>')
        else:
            out.append(f'        <a href="{href}" class="pg-btn">{n}</a>')
    if current < pages:
        out.append(f'        <a href="blog-{current+1}.html" class="pg-btn">Next</a>')
    else:
        out.append('        <span class="pg-btn disabled">Next</span>')
    out.append('      </div>')
    return '\n'.join(out)


for pg in range(1, pages + 1):
    chunk = rest[(pg - 1) * PER_PAGE: pg * PER_PAGE]
    fname = 'blog.html' if pg == 1 else f'blog-{pg}.html'
    canonical = f'{SITE}/blog/' if pg == 1 else f'{SITE}/blog/page/{pg}/'

    title = ('Dental Health Blog | Coastal Dental Gosford' if pg == 1
             else f'Dental Health Blog - Page {pg} | Coastal Dental Gosford')
    desc = ('Dental health advice, treatment guides and practice news from the team at '
            'Coastal Dental Gosford, serving the Central Coast.')

    head = strip_head_tags(head_start)
    head = re.sub(r'<title>.*?</title>', f'<title>{esc(title)}</title>', head, count=1, flags=re.S)
    head = re.sub(r'(name="description" content=")[^"]*(")',
                  lambda m: m.group(1) + esc(desc) + m.group(2), head, count=1)
    head = head.replace('</head>',
        f'<link rel="canonical" href="{canonical}">\n'
        f'<meta property="og:type" content="website">\n'
        f'<meta property="og:title" content="{esc(title)}">\n'
        f'<meta property="og:description" content="{esc(desc)}">\n'
        f'<meta property="og:url" content="{canonical}">\n</head>')

    if pg == 1:
        feat_block = f'''
  <!-- FEATURED POST -->
  <section class="blog-feature">
    <div class="wrap">
      <a href="{featured['slug']}.html" class="bf-card" data-r>
        <div class="bf-media">
          <img src="{local_img(featured['featured'])}" alt="{esc(featured['featured_alt'] or clean_txt(featured['title']))}">
          <span class="bf-badge">Latest Post</span>
        </div>
        <div class="bf-body">
          <div class="bf-meta"><span>{esc((featured['categories'] or ['Dental Tips'])[0])}</span><span class="mdot"></span><span>{fmt_date(featured['date'])}</span></div>
          <h2>{esc(clean_txt(featured['title']))}</h2>
          <p>{esc(excerpt(featured['content'], 300))}</p>
          <span class="bf-more">Read More <span class="arr"><svg viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg></span></span>
        </div>
      </a>
    </div>
  </section>
'''
        heading = 'More from our <em>blog</em>'
    else:
        feat_block = ''
        heading = f'More from our <em>blog</em>'

    cards = '\n'.join(card(p, (i % 3) + 1) for i, p in enumerate(chunk))

    page = head + mobile_block + f'''
<main>

{hero}{feat_block}
  <!-- ALL ARTICLES -->
  <section class="blog-grid-sec">
    <div class="wrap">
      <div class="bg-head">
        <div data-r>
          <div class="chip"><span class="dot"></span>All Articles</div>
          <h2>{heading}</h2>
        </div>
        <div class="bg-count" data-r data-d="1">Page {pg} of {pages} &middot; {len(posts)} articles</div>
      </div>
      <div class="bg-grid">
{cards}
      </div>
{pager(pg)}
    </div>
  </section>

  <div class="sp-cta">
    <div class="wrap">
      <div class="sp-cta-inner">
        <div data-r>
          <h2>Ready to book <em>your visit?</em></h2>
          <p>Reading is a good start. If something here raised a question about your own teeth, our team is happy to talk it through.</p>
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
    open(os.path.join(BUILD, fname), 'w').write(page + foot)

print(f"index pages built: {pages} (blog.html + blog-2..{pages}.html)")
print(f"featured: {clean_txt(featured['title'])[:60]}")
print(f"cards across pages: {len(rest)} + 1 featured = {len(posts)}")
