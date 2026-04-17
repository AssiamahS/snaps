# snaps web

Static landing page. Deploy to Cloudflare Pages:

```bash
npx wrangler pages deploy web --project-name snaps-web
```

Or drop the `web/` folder onto any static host (Netlify, Vercel, GitHub Pages).

The only things that need editing before going live:
- `action="https://formspree.io/f/REPLACE_ME"` — replace with a real Formspree
  endpoint (or swap for a ConvertKit / Buttondown form).
- `https://api.snaps.dev/...` — replace with whatever the actual API hostname
  is once we decide (snaps.dev is illustrative).

No build step, no framework, no npm install. Tailwind is loaded via CDN, which
is fine for a landing; swap to a compiled build when we add more pages.
