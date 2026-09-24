# GYA Site CMS

The client dashboard framework for static GYA sites. First implemented on
Coastal Dental. Log in at `/admin/`.

## What the practice can do

- Edit wording on any page by clicking the text in a live preview
- Replace images by clicking them, with alt text
- Edit the page title, meta description and social share image per page
- Write, publish and unpublish blog posts, and edit existing articles in place
- Update phone, email, address, opening hours, booking link and health funds,
  which change everywhere on the site at once
- Reorder sections on a page by drag and drop (the top banner stays first)

## How it fits together

```
/admin/index.html   Dashboard. Login, page editor, blog, practice details.
/cms/adapter.js     STORAGE ADAPTER. The only file that knows about storage.
/cms/cms.js         Runtime on every page. Applies saved edits. Backend-agnostic.
/cms/site.js        Generated. The built-in practice details (the defaults).
/cms/pages.json     Generated. The page list shown in the dashboard.
/post.html          Template for posts written in the dashboard.
/_tools/            Build step and browser tests. Never deployed.
```

Nothing is saved into the HTML. Pages ship as built. `cms.js` reads saved
edits through the adapter and applies them in the browser. If nothing has
been saved, the page is untouched.

## Demo mode (current)

`cms/adapter.js` is the demo adapter. Login is `demo@coastaldental.com.au`
with password `demo1234`, shown on the login screen.

Everything is stored in the browser doing the editing (IndexedDB). Nothing is
published and nobody else sees the changes. That also makes the dummy login
harmless: there is nothing behind it to protect. Settings has a button to
wipe all demo changes.

## Swapping to Supabase: one file

Replace `cms/adapter.js` with a Supabase adapter implementing the same
contract. Nothing in the dashboard, the runtime or the pages changes.

```
mode                          'supabase'
auth.signIn(email, password)  -> { email }, throws on failure
auth.signOut()
auth.getUser()                -> { email } | null
get(key) / set(key, value) / remove(key) / list(prefix)
uploadImage(blob, filename)   -> public URL usable in <img src>
```

Keys used: `page:<slug>`, `site:practice`, `site:posts`. The full shape of
each is documented at the top of `cms/adapter.js`.

Suggested schema:

```sql
create table content (
  key        text primary key,
  value      jsonb not null,
  updated_at timestamptz default now(),
  updated_by uuid references auth.users
);
alter table content enable row level security;
create policy "public read"  on content for select using (true);
create policy "staff write"  on content for all
  using (exists (select 1 from profiles where id = auth.uid() and role = 'admin'))
  with check (exists (select 1 from profiles where id = auth.uid() and role = 'admin'));
-- plus a public-read Storage bucket "site-media", admin-only upload
```

The anon key can sit in the adapter. The service role key must never be in
the front end. Staff accounts are created by us, no self sign-up.

## Before going live with a real backend

These do not matter in demo mode, and they do matter in production:

1. **Social share previews.** Facebook, LinkedIn and WhatsApp do not run
   JavaScript, so a changed share image or title will not show in link
   previews. Google does run JavaScript and will pick up title, description
   and wording changes, but reading them from the HTML is more reliable.
   Recommended: a Publish button that triggers a Vercel deploy hook, whose
   build pulls saved content and bakes it into the static pages.
2. **Dashboard blog posts and SEO.** New posts render at
   `post.html?slug=...`, and that template is marked noindex so an empty
   template never gets indexed. Posts written in the dashboard therefore
   need the same publish step to become real, indexable pages at `/slug/`
   with sitemap entries. The existing articles are real pages already.
3. **Editable text IDs are positional.** Each editable block is numbered in
   page order by the build step. If a developer restructures a page's HTML,
   saved text for that page can land on the wrong block. After any
   structural change, open that page in the dashboard and check it.

## Build step

Run after regenerating any page:

```
python3 _tools/cms_build.py .
```

It marks editable text, images and sections, creates `post.html`, and
regenerates `cms/site.js` and `cms/pages.json`. It only ever adds attributes,
so stripping them gives back the original page byte for byte, and running it
twice produces identical files.

If the practice details in the built HTML change, re-run it so the dashboard
defaults match.

## Using it on a new site

1. Copy `cms/`, `admin/` and `_tools/` into the site.
2. Edit the settings block at the top of `_tools/cms_build.py`: site name
   and service page slugs.
3. Adjust `load_defaults()` in the same file to read that site's footer:
   phone, email, address, hours, booking link, fund logos. This is the only
   per-site code.
4. Run the build step, then `python3 _tools/test_dashboard.py` against a
   local server (`python3 -m http.server 8765`).

Test on a local server or a Vercel preview, not by double-clicking the
files: the editor needs a real web address for the preview to talk to the
dashboard.
