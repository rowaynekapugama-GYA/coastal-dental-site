/* =====================================================================
   GYA Site CMS  |  STORAGE ADAPTER  (DEMO MODE)
   ---------------------------------------------------------------------
   This is the ONLY file that changes when we connect a real backend.
   Replace it with cms/adapter.js from the Supabase build and nothing
   else in the site or the dashboard needs touching.

   DEMO MODE BEHAVIOUR
   - Everything is saved in THIS BROWSER ONLY (IndexedDB).
   - Nothing is published. Other people, and other browsers, still see
     the site exactly as deployed.
   - The login is a dummy check for testing the dashboard. It protects
     nothing, which is fine here because edits never leave this browser.

   ADAPTER CONTRACT  (every adapter must provide exactly this)
   ---------------------------------------------------------------------
     mode                          'demo' | 'supabase' | ...
     auth.signIn(email, password)  -> { email }     throws on failure
     auth.signOut()                -> void
     auth.getUser()                -> { email } | null
     get(key)                      -> value | null   (plain JSON)
     set(key, value)               -> void
     remove(key)                   -> void
     list(prefix)                  -> [{ key, value }]
     uploadImage(blob, filename)   -> url string, usable directly in
                                      <img src> on the public site

   All methods are async. Keys in use:
     page:<slug>      { text:{id:html}, img:{id:{src,alt}},
                        seo:{title,description,ogImage}, order:[ids] }
     site:practice    { phone, tel, email, address1, address2,
                        hours:[{day,time}], bookingUrl,
                        funds:[{name,logo}] }
     site:posts       [ { slug, title, date, category, excerpt, image,
                          imageAlt, body, seoTitle, seoDescription,
                          status:'draft'|'published', updated } ]
   ===================================================================== */

(function () {
  const DB_NAME = 'gya-cms-demo';
  const STORE = 'kv';
  const SESSION_KEY = 'gya-cms-demo-session';
  const DEMO_USER = { email: 'demo@coastaldental.com.au', password: 'demo1234' };

  let dbp = null;
  function db() {
    if (dbp) return dbp;
    dbp = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    return dbp;
  }

  function tx(mode, fn) {
    return db().then(d => new Promise((resolve, reject) => {
      const t = d.transaction(STORE, mode);
      const s = t.objectStore(STORE);
      const out = fn(s);
      t.oncomplete = () => resolve(out && 'result' in out ? out.result : undefined);
      t.onerror = () => reject(t.error);
    }));
  }

  function blobToDataUrl(blob) {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result);
      r.onerror = () => reject(r.error);
      r.readAsDataURL(blob);
    });
  }

  window.CMS_ADAPTER = {
    mode: 'demo',

    auth: {
      async signIn(email, password) {
        const e = String(email || '').trim().toLowerCase();
        if (e !== DEMO_USER.email || password !== DEMO_USER.password) {
          throw new Error('Incorrect email or password.');
        }
        localStorage.setItem(SESSION_KEY, JSON.stringify({ email: e, at: Date.now() }));
        return { email: e };
      },
      async signOut() { localStorage.removeItem(SESSION_KEY); },
      async getUser() {
        try {
          const s = JSON.parse(localStorage.getItem(SESSION_KEY) || 'null');
          return s ? { email: s.email } : null;
        } catch (e) { return null; }
      },
      demoCredentials: { email: DEMO_USER.email, password: DEMO_USER.password },
    },

    async get(key) {
      const v = await tx('readonly', s => s.get(key));
      return v === undefined ? null : v;
    },

    async set(key, value) {
      await tx('readwrite', s => s.put(JSON.parse(JSON.stringify(value)), key));
    },

    async remove(key) {
      await tx('readwrite', s => s.delete(key));
    },

    async list(prefix) {
      const d = await db();
      return new Promise((resolve, reject) => {
        const out = [];
        const req = d.transaction(STORE, 'readonly').objectStore(STORE).openCursor();
        req.onsuccess = () => {
          const c = req.result;
          if (!c) return resolve(out);
          if (!prefix || String(c.key).startsWith(prefix)) out.push({ key: c.key, value: c.value });
          c.continue();
        };
        req.onerror = () => reject(req.error);
      });
    },

    /* Demo: images are stored inline as data URLs, which work directly in
       <img src>. The Supabase adapter uploads to Storage and returns the
       public URL instead. Either way the caller just gets a usable URL. */
    async uploadImage(blob /*, filename */) {
      return blobToDataUrl(blob);
    },

    /* Demo only: wipe every change in this browser. */
    async resetAll() {
      await tx('readwrite', s => s.clear());
    },
  };
})();
