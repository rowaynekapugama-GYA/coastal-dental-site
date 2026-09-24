from playwright.sync_api import sync_playwright
import re, sys

BASE = 'http://localhost:8765'
results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print(('PASS ' if ok else 'FAIL ') + name + (('  | ' + str(detail)) if detail else ''))

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 1440, 'height': 900})
    errors = []
    ctx.on('weberror', lambda e: errors.append(str(e.error)))
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errors.append(str(e)))

    # ---------- 0. baseline: public page untouched when nothing saved
    pg.goto(BASE + '/cerec.html'); pg.wait_for_timeout(800)
    orig_h1 = pg.inner_text('main h1')
    orig_title = pg.title()
    orig_order = pg.eval_on_selector_all('main > [data-cms-section]', 'els=>els.map(e=>e.dataset.cmsSection)')
    check('baseline page renders with no saved edits', orig_h1 and len(orig_order) > 3, f'h1="{orig_h1[:40]}" sections={len(orig_order)}')

    # ---------- 1. direct ?cms-edit=1 visit must NOT enable editing
    pg.goto(BASE + '/cerec.html?cms-edit=1'); pg.wait_for_timeout(800)
    ce = pg.eval_on_selector_all('[contenteditable="true"]', 'e=>e.length')
    check('visitor adding ?cms-edit=1 cannot edit', ce == 0, f'{ce} editable elements')

    # ---------- 2. login
    pg.goto(BASE + '/admin/index.html'); pg.wait_for_timeout(600)
    check('login screen shown when signed out', pg.is_visible('#loginForm'))
    pg.fill('#lEmail', 'demo@coastaldental.com.au'); pg.fill('#lPass', 'wrong')
    pg.click('#loginForm button[type=submit]'); pg.wait_for_timeout(400)
    check('wrong password rejected', 'Incorrect' in pg.inner_text('#lErr'))
    pg.fill('#lPass', 'demo1234'); pg.click('#loginForm button[type=submit]')
    pg.wait_for_selector('.prow', timeout=8000)
    rows = pg.eval_on_selector_all('.prow', 'e=>e.length')
    check('correct login opens dashboard with page list', rows > 100, f'{rows} pages listed')

    # ---------- 3. page editor: inline text edit
    pg.goto(BASE + '/admin/index.html#edit/cerec')
    pg.wait_for_selector('.img-item', timeout=15000)
    frame = pg.frame_locator('#frame')
    h1 = frame.locator('main h1[data-cms]').first
    check('editor turns page text editable', h1.get_attribute('contenteditable') == 'true')
    h1.click()
    pg.keyboard.press('Control+A')
    pg.keyboard.type('Same-day crowns, tested in the dashboard')
    pg.wait_for_timeout(300)
    check('typing marks page as unsaved', 'Unsaved' in pg.inner_text('#saveState'))

    # ---------- 4. image replace via click on page image
    img = frame.locator('main img[data-cms-img]').first
    img_id = img.get_attribute('data-cms-img')
    with pg.expect_file_chooser() as fc:
        img.click()
    fc.value.set_files('/tmp/test-upload.jpg')
    pg.wait_for_timeout(1500)
    new_src = img.get_attribute('src') or ''
    check('clicking an image replaces it', new_src.startswith('data:image'), new_src[:30])

    # ---------- 5. SEO
    pg.click('#tabs button[data-t=seo]')
    pg.fill('#sTitle', 'CEREC Same-Day Crowns Gosford | Tested')
    pg.fill('#sDesc', 'Test description written in the dashboard for the CEREC page.')
    check('SEO character counter updates', pg.inner_text('#tc').strip() == str(len('CEREC Same-Day Crowns Gosford | Tested')))

    # ---------- 6. Sections: move second movable section down
    pg.click('#tabs button[data-t=sections]')
    items = pg.eval_on_selector_all('#secList li:not(.locked)', 'e=>e.map(x=>x.dataset.id)')
    pg.locator('#secList li:not(.locked)').nth(0).locator('[data-move=down]').click()
    pg.wait_for_timeout(300)
    items2 = pg.eval_on_selector_all('#secList li:not(.locked)', 'e=>e.map(x=>x.dataset.id)')
    live = frame.locator('main > [data-cms-section]').evaluate_all('e=>e.map(x=>x.dataset.cmsSection)')
    check('section reorder applies live in preview', items2[0] == items[1] and items2[1] == items[0] and live[1:3] == items2[:2], f'{items[:2]} -> {items2[:2]}')

    # ---------- 7. Save and verify on the PUBLIC page
    pg.click('#saveBtn'); pg.wait_for_timeout(800)
    check('save completes', 'saved' in pg.inner_text('#saveState').lower())

    pub = ctx.new_page()
    pub.goto(BASE + '/cerec.html'); pub.wait_for_timeout(1200)
    check('public page shows edited heading', pub.inner_text('main h1') == 'Same-day crowns, tested in the dashboard', pub.inner_text('main h1'))
    check('public page shows replaced image', (pub.get_attribute(f'[data-cms-img="{img_id}"]', 'src') or '').startswith('data:image'))
    check('public page has new SEO title', pub.title() == 'CEREC Same-Day Crowns Gosford | Tested', pub.title())
    desc = pub.get_attribute('meta[name=description]', 'content')
    check('public page has new meta description', desc and desc.startswith('Test description'))
    pub_order = pub.eval_on_selector_all('main > [data-cms-section]', 'e=>e.map(x=>x.dataset.cmsSection)')
    check('public page section order saved', pub_order[1:3] == items2[:2], f'{pub_order[:4]}')
    check('hero stays pinned first', pub_order[0] == orig_order[0])

    # ---------- 8. Practice details sitewide
    pg.goto(BASE + '/admin/index.html#practice'); pg.wait_for_selector('#cPhone')
    pg.fill('#cPhone', '(02) 4322 6617')
    check('tap-to-call digits auto-fill', pg.input_value('#cTel') == '0243226617')
    pg.fill('[data-h="5"]', '8.00am – 1.00pm')
    with pg.expect_file_chooser() as fc:
        pg.click('#addFund')
    fc.value.set_files('/tmp/test-logo.png'); pg.wait_for_timeout(1200)
    pg.click('#saveBtn'); pg.wait_for_timeout(700)

    for path in ['/index.html', '/contact.html', '/dental-implants.html']:
        pub.goto(BASE + path); pub.wait_for_timeout(1000)
        body = pub.inner_text('body')
        old_left = body.count('4306 7053')
        new_n = body.count('4322 6617')
        tels = pub.eval_on_selector_all('a[href^="tel:"]', 'e=>[...new Set(e.map(a=>a.getAttribute("href")))]')
        check(f'phone swapped sitewide on {path}', old_left == 0 and new_n > 0 and tels == ['tel:0243226617'], f'old={old_left} new={new_n} tel={tels}')
    sat = pub.eval_on_selector_all('.f-hours > div', 'rows=>rows.map(r=>r.innerText)')
    check('footer hours updated', any('8.00am – 1.00pm' in r for r in sat), [r for r in sat if 'Sat' in r])
    pub.goto(BASE + '/index.html'); pub.wait_for_timeout(1000)
    fund_n = pub.eval_on_selector_all('.funds-track .fund-box', 'e=>e.length')
    check('health fund strip rebuilt, loop kept', fund_n == 16, f'{fund_n} boxes (8 funds x2)')

    # ---------- 9. Blog: new post
    pg.goto(BASE + '/admin/index.html#post'); pg.wait_for_selector('#pTitle')
    pg.fill('#pTitle', 'Why Gosford Families Book Morning Appointments')
    check('web address auto-fills from title', pg.input_value('#pSlug') == 'why-gosford-families-book-morning-appointments')
    pg.click('#pSlug'); pg.keyboard.press('End'); pg.keyboard.type('-2026')
    check('hyphens can be typed in the web address', pg.input_value('#pSlug').endswith('-2026'))
    pg.click('#rte'); pg.keyboard.type('Morning visits suit school runs.')
    pg.click('#rteBar button[data-v=H2]'); pg.keyboard.press('End'); pg.keyboard.press('Enter')
    pg.keyboard.type('A heading test')
    pg.click('#rteBar button[data-v=H2]')
    with pg.expect_file_chooser() as fc:
        pg.click('#pImgUp')
    fc.value.set_files('/tmp/test-upload.jpg'); pg.wait_for_timeout(1200)
    pg.fill('#pAlt', 'A family arriving for a morning appointment')
    pg.click('#saveBtn'); pg.wait_for_timeout(900)
    slug = 'why-gosford-families-book-morning-appointments-2026'
    check('post publishes', 'post/' + slug in pg.url, pg.url)

    pub.goto(BASE + '/blog.html'); pub.wait_for_timeout(1200)
    first = pub.inner_text('.bg-grid .bp-card h3')
    check('new post appears first on blog page', first == 'Why Gosford Families Book Morning Appointments', first)
    pub.goto(BASE + '/post.html?slug=' + slug); pub.wait_for_timeout(1200)
    check('new post page renders', pub.inner_text('h1') == 'Why Gosford Families Book Morning Appointments')
    check('post body keeps heading structure', pub.eval_on_selector_all('[data-post-body] h2', 'e=>e.length') >= 1)
    check('post featured image shown', (pub.get_attribute('[data-post-image]', 'src') or '').startswith('data:image'))

    # draft must not be public
    pg.goto(BASE + '/admin/index.html#post'); pg.wait_for_selector('#pTitle')
    pg.fill('#pTitle', 'Draft Only Post'); pg.click('#rte'); pg.keyboard.type('Not ready yet.')
    pg.click('#saveDraft'); pg.wait_for_timeout(800)
    pub.goto(BASE + '/post.html?slug=draft-only-post'); pub.wait_for_timeout(1000)
    check('draft posts are not publicly visible', 'not found' in pub.inner_text('h2').lower())

    # ---------- 10. XSS: hostile stored content is neutralised
    pg.evaluate("""async()=>{await window.CMS_ADAPTER.set('page:faq',{text:{t1:'<img src=x onerror="window.__pwned=1">Hi<script>window.__pwned=1</script>'}})}""")
    pub.goto(BASE + '/faq.html'); pub.wait_for_timeout(1000)
    pwned = pub.evaluate('window.__pwned || 0')
    check('stored HTML is sanitised (no script, no onerror)', pwned == 0)

    # ---------- 11. unsaved-changes guard keeps editor wired after cancel
    pg.goto(BASE + '/admin/index.html#edit/about'); pg.wait_for_selector('.img-item', timeout=15000)
    fr = pg.frame_locator('#frame')
    fr.locator('main [data-cms]').first.click(); pg.keyboard.type(' X')
    pg.once('dialog', lambda d: d.dismiss())
    pg.evaluate("location.hash='#pages'"); pg.wait_for_timeout(500)
    fr.locator('main [data-cms]').first.click(); pg.keyboard.type('Y'); pg.wait_for_timeout(300)
    check('cancelling leave keeps editor working', 'Unsaved' in pg.inner_text('#saveState') and '#edit/about' in pg.url)
    pg.once('dialog', lambda d: d.accept())

    # ---------- 12. revert + reset
    pg.goto(BASE + '/admin/index.html#settings'); pg.wait_for_selector('#resetAll')
    pg.once('dialog', lambda d: d.accept()); pg.click('#resetAll'); pg.wait_for_timeout(800)
    pub.goto(BASE + '/cerec.html'); pub.wait_for_timeout(1000)
    check('reset restores original page', pub.inner_text('main h1') == orig_h1 and pub.title() == orig_title)
    pub.goto(BASE + '/index.html'); pub.wait_for_timeout(800)
    check('reset restores original phone', '4306 7053' in pub.inner_text('body') and '4322 6617' not in pub.inner_text('body'))

    # ---------- 13. screenshots
    pg.goto(BASE + '/admin/index.html#edit/cerec'); pg.wait_for_selector('.img-item', timeout=15000); pg.wait_for_timeout(800)
    pg.screenshot(path='/tmp/dash_editor.png')
    pg.click('#tabs button[data-t=sections]'); pg.wait_for_timeout(300)
    pg.screenshot(path='/tmp/dash_sections.png')
    pg.goto(BASE + '/admin/index.html#practice'); pg.wait_for_selector('#cPhone'); pg.wait_for_timeout(500)
    pg.screenshot(path='/tmp/dash_practice.png', full_page=True)
    mob = b.new_context(viewport={'width': 390, 'height': 844}).new_page()
    mob.goto(BASE + '/admin/index.html'); mob.wait_for_timeout(600)
    mob.screenshot(path='/tmp/dash_login_mobile.png')

    real_errors = [e for e in errors if 'favicon' not in e]
    check('no JavaScript errors during the whole run', not real_errors, real_errors[:3])
    b.close()

passed = sum(1 for r in results if r[1])
print(f'\n{passed}/{len(results)} checks passed')
sys.exit(0 if passed == len(results) else 1)
