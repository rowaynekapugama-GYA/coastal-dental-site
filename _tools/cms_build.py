#!/usr/bin/env python3
"""
GYA Site CMS | build step
Run after any page regeneration. Idempotent: strips previous CMS markup
before re-annotating, and only ever inserts attributes, so the rest of
each page's HTML is left byte for byte as it was.
"""
import glob, html as H, json, os, re, sys
from html.parser import HTMLParser

ROOT = sys.argv[1] if len(sys.argv) > 1 else '.'
os.chdir(ROOT)

# ---- per-site settings (the only lines to change on a new site) ----
SITE_NAME = 'Coastal Dental'
SERVICE_SLUGS = {'restorative', 'cosmetic', 'children', 'preventative', 'crowns', 'rootcanal',
                 'orthodontics', 'hygiene', 'mouthguards', 'cerec', 'sleep-dentistry', 'emergency',
                 'teeth-whitening', 'dental-implants', 'clear-aligners', 'braces'}
# ---------------------------------------------------------------------
# Blog posts are recognised from the page itself (og:type article with a
# published date), so this works on any site without extra data files.
posts_meta = {}
for _f in glob.glob('*.html'):
    _c = open(_f, encoding='utf-8').read()
    _c = _c[:_c.find('</head>')]
    if 'og:type" content="article"' in _c:
        _m = re.search(r'article:published_time" content="([^"]+)"', _c)
        posts_meta[_f[:-5]] = _m.group(1) if _m else ''

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param',
        'source', 'track', 'wbr'}
BLOCKY = {'div', 'p', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'section', 'article',
          'table', 'img', 'svg', 'video', 'iframe', 'form', 'input', 'button', 'picture', 'header',
          'footer', 'aside', 'figure', 'blockquote', 'textarea', 'select'}
NO_ANCESTOR_TAGS = {'form', 'svg', 'nav', 'button', 'script', 'style', 'noscript', 'iframe',
                    'select', 'label', 'time', 'textarea'}
NO_ANCESTOR_CLASSES = {'bp-card', 'bf-card', 'post-rel', 'bg-pager', 'marquee', 'funds', 'crumb',
                       'map-wrap', 'cms-skip', 'bg-count', 'post-share'}


def load_defaults():
    c = open('index.html', encoding='utf-8').read()
    foot = c[c.find('<!-- FOOTER -->'):]
    tel = re.search(r'href="tel:(\d+)"', foot).group(1)
    phone = re.search(r'href="tel:\d+">([^<]+)</a>', foot).group(1).strip()
    email = re.search(r'href="mailto:([^"]+)"', foot).group(1)
    addr = re.search(r'Location:\s*([^<]+)<br>\s*([^<]+)</span>', foot)
    hours = [{'day': d.strip(), 'time': H.unescape(t).strip()} for d, t in
             re.findall(r'<div class="fh"><span>([^<]+)</span><span>([^<]+)</span></div>', foot)]
    track = c[c.find('<div class="funds-track">'):]
    track = track[:track.find('</div>')]
    funds_raw = re.findall(r'<img class="fund-logo" src="([^"]+)" alt="([^"]+)"', track)
    seen, funds = set(), []
    for src, alt in funds_raw:
        if src in seen:
            continue
        seen.add(src)
        funds.append({'name': H.unescape(alt), 'logo': src})
    bk = open('book-now.html', encoding='utf-8').read()
    booking = H.unescape(re.search(r'<iframe[^>]*src="([^"]*centaur[^"]*)"', bk).group(1))
    return {
        'phone': phone, 'tel': tel, 'email': email,
        'address1': addr.group(1).strip(), 'address2': addr.group(2).strip(),
        'hours': hours, 'bookingUrl': booking,
        'funds': funds, 'fundsCount': len(funds),
    }


DEFAULTS = load_defaults()


# ------------------------------------------------------------- strip old
def strip_cms(src):
    src = re.sub(r'<span class="cms-q"[^>]*>(.*?)</span>', r'\1', src, flags=re.S)
    src = re.sub(r'\s+data-cms(?:-page|-img|-section|-label|-pinned)?(?:="[^"]*")?(?=[\s>/])', '', src)
    src = re.sub(r'\n?<!-- GYA-CMS -->.*?<!-- /GYA-CMS -->\n?', '\n', src, flags=re.S)
    return src


# ------------------------------------------------------------ tree build
class Tree(HTMLParser):
    def __init__(self, src):
        super().__init__(convert_charrefs=False)
        self.src = src
        self.line_starts = [0]
        for m in re.finditer('\n', src):
            self.line_starts.append(m.end())
        self.nodes, self.stack = [], []
        self.feed(src)

    def off(self):
        ln, col = self.getpos()
        return self.line_starts[ln - 1] + col

    def _open(self, tag, attrs, void):
        start = self.off()
        raw = self.get_starttag_text() or ''
        node = {'tag': tag, 'attrs': dict(attrs), 'start': start, 'tag_end': start + len(raw),
                'end': start + len(raw), 'parent': self.stack[-1] if self.stack else None,
                'children': [], 'direct_text': False, 'raw': raw}
        idx = len(self.nodes)
        self.nodes.append(node)
        if node['parent'] is not None:
            self.nodes[node['parent']]['children'].append(idx)
        if not void:
            self.stack.append(idx)

    def handle_starttag(self, tag, attrs):
        self._open(tag, attrs, tag in VOID)

    def handle_startendtag(self, tag, attrs):
        self._open(tag, attrs, True)

    def handle_endtag(self, tag):
        pos = self.off()
        for i in range(len(self.stack) - 1, -1, -1):
            if self.nodes[self.stack[i]]['tag'] == tag:
                for j in self.stack[i:]:
                    self.nodes[j]['end'] = pos + len(f'</{tag}>')
                del self.stack[i:]
                return

    def handle_data(self, data):
        if self.stack and data.strip():
            self.nodes[self.stack[-1]]['direct_text'] = True

    def handle_entityref(self, name):
        if self.stack:
            self.nodes[self.stack[-1]]['direct_text'] = True

    def handle_charref(self, name):
        if self.stack:
            self.nodes[self.stack[-1]]['direct_text'] = True


def classes(n):
    return set((n['attrs'].get('class') or '').split())


def plain(src, n):
    t = re.sub(r'<[^>]+>', ' ', src[n['tag_end']:n['end']])
    return re.sub(r'\s+', ' ', H.unescape(t)).strip()


def annotate(path):
    slug = os.path.basename(path)[:-5]
    src = strip_cms(open(path, encoding='utf-8').read())

    # FAQ questions sit inside <button>; wrap their text so it can be edited
    def wrap_faq(m):
        return f'{m.group(1)}<span class="cms-q" data-cmswrap>{m.group(2)}</span>{m.group(3)}'
    src = re.sub(r'(<button class="faq-q">)([^<]+?)(\s*<div class="faq-toggle">)', wrap_faq, src)

    t = Tree(src)
    nodes = t.nodes
    main = next((i for i, n in enumerate(nodes) if n['tag'] == 'main'), None)
    inserts = []  # (offset, text)

    htag = next((n for n in nodes if n['tag'] == 'html'), None)
    if htag:
        inserts.append((htag['tag_end'] - 1, f' data-cms-page="{slug}"'))

    def ancestors(i):
        p = nodes[i]['parent']
        while p is not None:
            yield p
            p = nodes[p]['parent']

    def in_main(i):
        return main is not None and any(a == main for a in ancestors(i))

    def excluded(i):
        for a in ancestors(i):
            if nodes[a]['tag'] in NO_ANCESTOR_TAGS:
                return True
            if classes(nodes[a]) & NO_ANCESTOR_CLASSES:
                return True
        return bool(classes(nodes[i]) & NO_ANCESTOR_CLASSES)

    def has_blocky(i):
        for c in nodes[i]['children']:
            if nodes[c]['tag'] in BLOCKY or has_blocky(c):
                return True
        return False

    tn = im = sn = 0
    chosen = set()

    if main is not None and 'cms-skip' not in classes(nodes[main]):
        # sections: direct children of <main>
        kids = [c for c in nodes[main]['children']]
        for k, c in enumerate(kids):
            n = nodes[c]
            if n['tag'] in ('script', 'style'):
                continue
            sn += 1
            label = ''
            stack = [c]
            order = []
            while stack:
                x = stack.pop(0)
                order.append(x)
                stack = nodes[x]['children'] + stack
            for x in order:
                if nodes[x]['tag'] in ('h1', 'h2'):
                    label = plain(src, nodes[x])
                    break
            if not label:
                for x in order:
                    if 'chip' in classes(nodes[x]):
                        label = plain(src, nodes[x])
                        break
            if not label:
                label = (n['attrs'].get('class') or n['tag']).split()[0].replace('-', ' ').title()
            label = label[:70]
            extra = f' data-cms-section="s{sn}" data-cms-label="{H.escape(label, quote=True)}"'
            if k == 0:
                extra += ' data-cms-pinned'
            inserts.append((n['tag_end'] - (2 if n['raw'].endswith('/>') else 1), extra))

        # text + images
        for i, n in enumerate(nodes):
            if not in_main(i):
                continue
            wrapped = 'data-cmswrap' in n['attrs']
            if not wrapped and excluded(i):
                continue
            tag = n['tag']

            if tag == 'img':
                im += 1
                inserts.append((n['tag_end'] - (2 if n['raw'].endswith('/>') else 1), f' data-cms-img="i{im}"'))
                continue
            if tag == 'div' and n['attrs'].get('role') == 'img':
                if any(nodes[c]['tag'] == 'video' for c in n['children']):
                    continue
                im += 1
                inserts.append((n['tag_end'] - 1, f' data-cms-img="i{im}"'))
                continue

            if not (n['direct_text'] or wrapped):
                continue
            if has_blocky(i):
                continue
            if any(a in chosen for a in ancestors(i)):
                continue
            txt = plain(src, n)
            if not txt or re.fullmatch(r'[\d\s.,:/()&#;+-]{1,4}', txt):
                continue
            if DEFAULTS['phone'] in txt or DEFAULTS['email'] in txt:
                continue
            tn += 1
            chosen.add(i)
            if wrapped:
                # replace the marker attribute with the real one
                s, e = n['start'], n['tag_end']
                inserts.append(('REPLACE', s, e, f'<span class="cms-q" data-cms="t{tn}">'))
            else:
                inserts.append((n['tag_end'] - 1, f' data-cms="t{tn}"'))

    # apply edits from the end so offsets stay valid
    def key(x):
        return x[1] if x[0] == 'REPLACE' else x[0]
    for ins in sorted(inserts, key=key, reverse=True):
        if ins[0] == 'REPLACE':
            _, s, e, txt = ins
            src = src[:s] + txt + src[e:]
        else:
            off, txt = ins
            src = src[:off] + txt + src[off:]

    tags = ('<!-- GYA-CMS -->\n<script src="cms/site.js"></script>\n'
            '<script src="cms/adapter.js"></script>\n<script src="cms/cms.js"></script>\n'
            '<!-- /GYA-CMS -->\n')
    src = src.replace('</body>', tags + '</body>', 1)
    open(path, 'w', encoding='utf-8').write(src)
    title = re.search(r'<title>(.*?)</title>', src, re.S)
    return slug, H.unescape(title.group(1)).strip() if title else slug, tn, im, sn


# ------------------------------------------------------ post template
def make_post_template():
    base = open('blog.html', encoding='utf-8').read()
    base = strip_cms(base)
    head_end = base.find('<main>')
    head = base[:head_end]
    head = re.sub(r'<title>.*?</title>', f'<title>Blog | {SITE_NAME}</title>', head, count=1, flags=re.S)
    head = re.sub(r'<link rel="canonical"[^>]*>\n?', '', head)
    head = head.replace('</head>', '<meta name="robots" content="noindex, follow">\n</head>', 1)
    ref = open('invisalign-or-braces-how-to-choose.html', encoding='utf-8').read()
    css = re.search(r'<style>\s*\.post-hero.*?</style>', ref, re.S).group(0)
    head = head.replace('</head>', css + '\n</head>', 1)
    foot = base[base.find('<!-- FOOTER -->'):]
    body = '''<main class="cms-skip">
  <article data-cms-post>
  <section class="post-hero">
    <div class="ph-bg"><img data-post-image src="" alt=""></div>
    <div class="ph-inner">
      <nav class="crumb" aria-label="Breadcrumb"><a href="index.html">Home</a><span class="sep">&rsaquo;</span><a href="blog.html">Blog</a><span class="sep">&rsaquo;</span><span data-post-crumb>Article</span></nav>
      <span class="ph-cat" data-post-cat>Blog</span>
      <h1 data-post-title>Loading article</h1>
      <div class="ph-meta"><time data-post-date></time><span class="mdot"></span><span>''' + SITE_NAME + '''</span></div>
    </div>
  </section>
  <div class="post-wrap"><div class="post-body" data-post-body></div></div>
  </article>
</main>

'''
    open('post.html', 'w', encoding='utf-8').write(head + body + foot)


# --------------------------------------------------------------- run
make_post_template()
pages = [p for p in sorted(glob.glob('*.html')) if not re.match(r'blog-\d+\.html$', p)]
report, catalogue = [], []
for p in sorted(glob.glob('*.html')):
    slug, title, tn, im, sn = annotate(p)
    report.append((slug, tn, im, sn))
    if re.match(r'blog-\d+$', slug) or slug == 'post':
        continue
    if slug in posts_meta:
        group = 'Blog posts'
    elif slug in SERVICE_SLUGS:
        group = 'Services'
    else:
        group = 'Main pages'
    entry = {'slug': slug, 'file': p, 'title': re.sub(r'\s*[|\-]\s*Coastal Dental.*$', '', title), 'group': group}
    if slug in posts_meta:
        entry['date'] = posts_meta[slug][:10]
    catalogue.append(entry)

os.makedirs('cms', exist_ok=True)
json.dump(catalogue, open('cms/pages.json', 'w'), indent=1)
open('cms/site.js', 'w').write(
    '/* Generated by the CMS build step. The built-in practice details the\n'
    '   runtime swaps out when the practice saves new ones in the dashboard. */\n'
    'window.CMS_SITE = ' + json.dumps({'name': SITE_NAME, 'defaults': DEFAULTS}, indent=1) + ';\n')

tot = [sum(r[i] for r in report) for i in (1, 2, 3)]
print(f'pages annotated: {len(report)}')
print(f'editable text blocks: {tot[0]} | images: {tot[1]} | sections: {tot[2]}')
print(f'catalogue entries: {len(catalogue)}')
print('defaults:', {k: v for k, v in DEFAULTS.items() if k not in ('hours', 'funds')})
print(f'hours rows: {len(DEFAULTS["hours"])} | funds: {len(DEFAULTS["funds"])}')
