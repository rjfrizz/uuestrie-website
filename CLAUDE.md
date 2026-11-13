# UUEstrie website — instructions for AI assistants

This is the static website for UUEstrie (Unitarian Universalist Church of North
Hatley, Québec). It's bilingual (English / French). The most common job is
**adding next Sunday's service** and occasionally a concert or other event.

## How the site works

- `python3 build.py` builds everything into `public/` (standard library only, nothing to install).
- `python3 build.py serve` builds and previews at http://localhost:8000.
- Never edit `public/` — it is regenerated on every build.
- The build prints `PROBLEMS:` and exits non-zero if an event file is malformed or an image is missing. Fix every problem before finishing.

```
content/events/   one Markdown file per service/event   ← weekly updates go here
content/pages/    one HTML file per page (about, ceremonies, visit, contact…)
content/news/     old blog posts (archive, rarely touched)
static/images/events/   images for new events
static/uploads/   images migrated from the old WordPress site
site.json         site settings: navigation, address, "Coming soon" list, redirects
templates/event.md   copy this to start a new event
```

## Adding a weekly service (the usual task)

1. Copy `templates/event.md` to `content/events/YYYY-MM-DD-short-name.md`
   (e.g. `content/events/2026-11-22-amy-panetta.md`). Lower-case, hyphens, no accents.
   The file name becomes the web address: `/event/2026-11-22-amy-panetta/`.
2. Fill in the front matter:
   - `title:` English title. Put the speaker in it, e.g. `Saved by Grace with Rev. Nicoline Guerrier`.
   - `title_fr:` French title (optional but strongly preferred — it powers the French view).
   - `date:` `YYYY-MM-DD`. `start:` / `end:` as `"HH:MM"` 24-hour, in quotes. Sunday services are `"10:30"` to `"12:00"`.
   - `category:` one of `service`, `concert`, `away` (outing elsewhere), `event`.
   - `location:` only if NOT at the church (default is 201 Main Street). Optionally
     `UUEstrie, Sanctuary (Upstairs), 201 Main Street, North Hatley` or
     `UUEstrie, Stoddard Hall (Downstairs), 201 Main Street, North Hatley`
     (sanctuary April to mid-November, Stoddard Hall over the winter; in 2026 the move downstairs is after Nov 15).
   - `image:` path inside `static/`, e.g. `images/events/2026-11-22.jpg`. Copy the image file there.
     Resize big photos first: `sips -Z 1600 path/to/photo.jpg` (macOS). Omit `image:` if there is none.
   - `cancelled: yes` to mark a cancellation (keep the file; the site shows a "Cancelled / Annulé" badge).
   - Values containing a colon `:` must be wrapped in double quotes.
3. Body: English paragraphs first, then a line containing only `---`, then the French paragraphs.
   Separate paragraphs with a blank line. Supported formatting: `**bold**`, `*italic*`,
   `[link text](https://…)`, `- bullet` lists, `## heading`. Email addresses become links automatically.
   End both languages with the coffee-hour sentence (see the template).
4. If the person gave text in only one language, write a natural translation for the other
   (Québec French: “courriel”, “10 h 30”, « guillemets », espace before `: ; ! ?`),
   and tell the user it was machine-translated so someone can review it.
5. Remove that date from `coming_soon` in `site.json` if it's listed there; add newly
   announced speakers to `coming_soon` as `{ "date": "YYYY-MM-DD", "text": "Name" }`
   (add `"text_fr"` when the French wording differs, e.g. for an extra activity).
6. Run `python3 build.py`, confirm no `PROBLEMS:` and that "Next up" shows the right event.
7. If the project is a git repository with a remote, commit with a message like
   `Add Nov 22 service: <title>` and push only when the user asks — pushing publishes the site.

### Drafts from the presenter form

New services submitted through the presenter Google Form are turned into drafts in
`content/drafts/` by the `check-services` skill (`.claude/skills/check-services/SKILL.md`).
The build ignores that folder. A draft goes live only when the user approves it and it is
moved into `content/events/` (the skill describes the steps).

### How the language switcher works (don't break it)

Visitors choose English or Français (default: the browser's language, else English). Each paragraph is auto-detected as English or
French at build time and hidden in the other mode. If a paragraph mixes both languages it's
shown in every mode. To force a language on a block, wrap it:

```
:::fr
Texte en français.
:::
```

In page HTML, use `lang="en"` / `lang="fr"` attributes on elements, and
`<span lang="en">…</span><span class="sep"> / </span><span lang="fr">…</span>` for short bilingual labels.

## Editing pages

Pages are plain HTML fragments in `content/pages/` with a small header (`title:`, `title_fr:`).
`content/pages/about/history.html` → `/about/history/`; `index.html` in a folder → that folder's URL.
Keep English and French blocks next to each other. To add a page to the menu, edit `nav` in `site.json`.
The page title is the only `<h1>`: start in-page headings at `<h2>` (the build turns any stray
`<h1>` into `<h2>` and strips old WordPress `align=` attributes). Pages listed as `children` of a
`nav` item automatically get a row of section links at the top.
The page title is the only `<h1>`: start in-page headings at `<h2>` (the build turns any stray
`<h1>` into `<h2>` and strips old WordPress `align=` attributes). Pages listed as `children` of a
`nav` item automatically get a row of section links at the top.

## Don'ts

- Don't add JavaScript frameworks, build tools or packages; keep the build stdlib-only.
- Don't rename existing event files or change their `slug:` — old links on Facebook point to them.
- Don't delete past events; they form the "Past services" archive.
- Don't put anyone's personal phone number or home address on the site.
