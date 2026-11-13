# uuestrie.ca — static site

Bilingual static website for UUEstrie, migrated from WordPress (November 2026).

## Everyday use

Ask your AI assistant something like:

> Add next Sunday's service: Nov 22, Amy Panetta, "Finding Our Way". Here's the blurb: … Image is ~/Downloads/amy.jpg

It follows `CLAUDE.md` (also readable by other tools as `AGENTS.md`). Or do it by hand:
copy `templates/event.md` to `content/events/`, edit, then run:

```
python3 build.py          # build into public/
python3 build.py serve    # build + preview at http://localhost:8000
```

Requires only Python 3.9+ (preinstalled on macOS).

## Hosting options (pick one)

| Host | Cost | How |
|---|---|---|
| **GitHub Pages** | free | Push this folder to a GitHub repo, Settings → Pages → Source: GitHub Actions. `.github/workflows/deploy.yml` builds on each push and every Monday. `static/CNAME` sets the uuestrie.ca domain. |
| Cloudflare Pages / Netlify | free | Connect the repo; build command `python3 build.py`, output directory `public`. |
| Current web host | — | Run `python3 build.py` and upload the contents of `public/` by SFTP. |

Then point the uuestrie.ca DNS at the new host. Old WordPress URLs for pages, events and
news posts are preserved; `/calendar/`, `/accueil/`, `/sample-page/` (Loi 25) redirect.

## What was migrated

- All 17 WordPress pages (+ new Home, Plan your visit pages)
- 69 events (Aug 2025 → Nov 2026) as Markdown files in `content/events/`
- 37 news posts (2010–2024) as an archive at `/news/`
- Images, re-hosted locally and resized
- Mailchimp newsletter sign-up form, CanadaHelps donation links (Member Services page dropped Nov 2026)

Dropped on purpose: ticketing, WordPress search, cookie banner (no cookies are used any more),
the WordPress contact form (replaced by an email link).
