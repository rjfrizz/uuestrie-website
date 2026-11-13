---
name: check-services
description: Check UUEstrie's presenter-form spreadsheet (and the "Service details" sheet) for new Sunday services and turn each new one into a bilingual draft event in content/drafts/ for review. Use when asked to "check for new services", "check the sheet", or run on a schedule. Also covers publishing a reviewed draft.
---

# Check for new services

Turn new rows in the Google Sheets into **draft** service postings (English + French).
Drafts live in `content/drafts/`, which `build.py` never reads, so nothing goes live
until the user approves and the draft is moved into `content/events/`.

## Sources (read with the Google Drive connector)

1. **Presenter form responses** (main source) — file id `1jBQcFGVwq_xz0YHbeXjvFGs8zPx1bf_TaZOHqB0LRw4`.
   Download as CSV (`download_file_content`, `exportMimeType: text/csv`), because
   `read_file_content` only returns a sample of rows. Columns by position:
   0 Timestamp · 1 Email · 2 Song requests · 3 Name and title · 4 Service title ·
   5 Phone · 6 Description · 7 Bio · 8 Photo permission · 9 Set-up needs ·
   10 Questions / notes · 11 Will send image (Yes/No).
   Some rows are shifted by a column (e.g. the 10/24/2026 "Awestruck" row) — if column 4
   looks like a phone number or column 3 is not a name, re-read the row by content.
2. **Service details** (rarely used) — file id `1UOYF-oWVP3x3FBgxkgRY4OLEKuJRxMU1fokwknxOH-4`.
   Has headers: `submittedAt, date, serviceTime, serviceTitle, speaker, speakerBio, reflectionTopic, …`.
3. **Weekly "This Sunday" emails** (Gmail connector) — Mailchimp e-blasts from
   `communications@uuestrie.ca`, usually sent Thursday/Friday, subject like
   "This Sunday at UU Estrie: …" or "This Sunday: …" (a Sunday-morning "Today: …" resend
   also exists — treat it as the same service). Search
   `from:communications@uuestrie.ca newer_than:21d`; each send arrives as several copies in
   one thread, so read one message per thread (`get_thread`, `PLAIN_TEXT`).
   Each email contains:
   - the date line, e.g. `November 8th, 2026, 10:30am | 8 novembre 2026, 10h30`;
   - the English title, description, coffee-hour line and bio, then the **French
     version written by the team** (prefer it over machine translation);
   - an **"Upcoming Services & Activities"** list (date → presenter) for the next weeks.
   - The service image: fetch the thread with `FULL_CONTENT` and take the main `<img>` in
     the service section (usually on `mcusercontent.com`); a plain link right under the
     date line (e.g. fineartamerica.com) is the image's credit/source, not the image.
   Ignore the boilerplate sections (Children's Program, Leadership Circle, "Powered by
   Community", unsubscribe links).

## Steps

1. Read `content/drafts/.seen.json`. A row is **new** if its Timestamp (form),
   `submittedAt` (Service details) or Gmail thread id (`weekly_email`) is not listed there.
2. For each new item, check it isn't already on the site (same speaker + similar title in
   `content/events/` or `content/drafts/`).
   - Already published, and a new weekly email has **different** wording, date, title or
     image → don't edit the live file; report the differences so the user can decide.
   - Already a draft → update the draft from the weekly email (its text and French win
     over the form), and say so in the report.
   - Otherwise just record it in `.seen.json`.
3. **Find the date.** The form has no date column. In order:
   - the weekly email's date line, if there is an email for this service;
   - the "Upcoming Services" list in the most recent weekly email;
   - the Service details `date` column, if the row came from there;
   - a matching name in `coming_soon` in `site.json`;
   - a date written in the description/notes.
   If none, still write the draft with `date: 2099-01-01` and say "DATE NEEDED" in
   `draft_notes` and in the report. Never guess a date.
4. **Write the draft** to `content/drafts/YYYY-MM-DD-short-name.md`, following
   `templates/event.md` and the rules in `CLAUDE.md`:
   - `title:` "<Service title> with <Name>" (keep "Rev." etc.; drop long job titles).
   - `title_fr:` French title. `start: "10:30"`, `end: "12:00"`, `category: service`.
   - `location:` Sanctuary (Upstairs) from April to mid-November, otherwise
     Stoddard Hall (Downstairs) — exact strings are in `CLAUDE.md`.
   - Body: description paragraph(s), then a bio paragraph, then the coffee-hour line;
     `---`; the same in French. If the presenter wrote in one language, translate into
     the other (Québec French conventions in `CLAUDE.md`). If they wrote both, use theirs.
     The two languages don't have to be word-for-word identical.
   - Light copy-editing only (typos, spacing). Don't invent content.
   - `image:` only if a file is actually in `static/images/events/`. If column 11 says
     "Yes", note in `draft_notes` that an image is expected at communications@uuestrie.ca.
   - Add `draft_source:` (which sheet + timestamp) and `draft_notes:` (anything the
     reviewer must check, including "French is machine-translated").
5. **Coming soon list.** Compare the latest email's "Upcoming Services" list with
   `coming_soon` in `site.json` and propose additions/changes (e.g. full names, extra
   activities like a potluck). Only edit `site.json` if the user agrees.
6. Add each handled item to `.seen.json` with a short note. Store **only the
   timestamp/thread id and the outcome** there.
7. Run `python3 build.py` to make sure nothing else broke, then report: one line per new
   or updated draft (date, title, file, what needs checking), suggested "Coming soon"
   changes, and differences found for already-published services — or "No new services."

## Privacy — never put these on the site or in drafts

Email address, phone number, song requests, set-up needs, photo permission, and private
notes to the team (column 10 often contains logistics and cancellation arrangements).
Only the title, name/title, description and bio are public. If column 10 holds something
attendees should know (e.g. "the service will be bilingual"), it may go in the body —
mention it in `draft_notes` so the reviewer can confirm.

## Publishing a draft (only when the user says so)

1. Remove the `draft_source:` and `draft_notes:` lines; make sure `date:` is real.
2. Move the file from `content/drafts/` to `content/events/` (same file name).
3. Remove that date from `coming_soon` in `site.json`.
4. Run `python3 build.py`, confirm no `PROBLEMS:` and the right "Next up".
5. Don't push or deploy unless the user asks — that publishes the site.
