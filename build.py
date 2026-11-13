#!/usr/bin/env python3
"""
UUEstrie static site generator.

    python3 build.py            build the site into ./public
    python3 build.py serve      build, then preview at http://localhost:8000

No third-party packages needed (Python 3.9+ standard library only).
See CLAUDE.md for how content is organised and how to add events.
"""
import datetime as dt
import html
import json
import re
import shutil
import sys
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
STATIC = ROOT / "static"
OUT = ROOT / "public"
SITE = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
TZ = ZoneInfo(SITE.get("timezone", "America/Toronto"))
NOW = dt.datetime.now(TZ)

ERRORS = []


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def esc(s):
    return html.escape(str(s or ""), quote=True)


def t(en, fr):
    """A bilingual UI string. The language switcher shows one or both."""
    if en == fr:
        return esc(en)
    return (f'<span class="t"><span lang="en">{esc(en)}</span>'
            f'<span class="sep"> / </span><span lang="fr">{esc(fr)}</span></span>')


def read_front_matter(path):
    """Files may start with a block of `key: value` lines between --- lines."""
    text = path.read_text(encoding="utf-8")
    meta = {}
    if text.startswith("---"):
        parts = text.split("\n")
        end = None
        for i in range(1, len(parts)):
            if parts[i].strip() == "---":
                end = i
                break
        if end is None:
            raise ValueError(f"{path}: front matter starts with --- but never ends")
        for line in parts[1:end]:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if ":" not in line:
                raise ValueError(f"{path}: bad front-matter line: {line!r}")
            k, v = line.split(":", 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            meta[k.strip()] = v
        text = "\n".join(parts[end + 1:])
    return meta, text


def url_for(path_in_static):
    p = str(path_in_static or "").strip()
    if not p or p.startswith(("http://", "https://", "/")):
        return p
    return "/" + p


# --------------------------------------------------------------------------
# Tiny Markdown (enough for event write-ups)
# --------------------------------------------------------------------------

def md_inline(s):
    s = esc(s).replace("&#x27;", "'")
    s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)",
               lambda m: f'<img src="{url_for(m.group(2))}" alt="{m.group(1)}" loading="lazy">', s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"(?<![\w.:/\"'>@-])([\w.+-]+@[\w-]+\.[\w.]+\w)",
               r'<a href="mailto:\1">\1</a>', s)
    return s


def markdown(text):
    out = []
    lang_stack = []
    blocks = re.split(r"\n\s*\n", text.strip("\n"))
    # Expand ::: fences that share a block with content
    flat = []
    for b in blocks:
        lines = b.split("\n")
        cur = []
        for ln in lines:
            if re.match(r"^:::\s*(en|fr)?\s*$", ln.strip()):
                if cur:
                    flat.append("\n".join(cur))
                    cur = []
                flat.append(ln.strip())
            else:
                cur.append(ln)
        if cur:
            flat.append("\n".join(cur))
    for b in flat:
        s = b.strip()
        if not s:
            continue
        m = re.match(r"^:::\s*(en|fr)?$", s)
        if m:
            if m.group(1):
                out.append(f'<div lang="{m.group(1)}">')
                lang_stack.append(m.group(1))
            elif lang_stack:
                out.append("</div>")
                lang_stack.pop()
            continue
        if s.startswith("<"):
            out.append(s)
        elif re.match(r"^-{3,}$|^~{3,}$", s):
            out.append("<hr>")
        elif m := re.match(r"^(#{1,4})\s+(.*)", s):
            lvl = min(len(m.group(1)) + 1, 5)
            out.append(f"<h{lvl}>{md_inline(m.group(2))}</h{lvl}>")
        elif all(re.match(r"^\s*[-*]\s+", ln) for ln in s.split("\n")):
            items = [md_inline(re.sub(r"^\s*[-*]\s+", "", ln)) for ln in s.split("\n")]
            out.append("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
        elif all(re.match(r"^\s*\d+[.)]\s+", ln) for ln in s.split("\n")):
            items = [md_inline(re.sub(r"^\s*\d+[.)]\s+", "", ln)) for ln in s.split("\n")]
            out.append("<ol>" + "".join(f"<li>{i}</li>" for i in items) + "</ol>")
        elif all(ln.startswith(">") for ln in s.split("\n")):
            inner = "<br>".join(md_inline(ln.lstrip("> ").rstrip()) for ln in s.split("\n"))
            out.append(f"<blockquote><p>{inner}</p></blockquote>")
        elif re.match(r"^!\[[^\]]*\]\([^)]+\)$", s):
            out.append(f"<figure>{md_inline(s)}</figure>")
        else:
            out.append("<p>" + "<br>".join(md_inline(ln.strip()) for ln in s.split("\n")) + "</p>")
    out.extend("</div>" for _ in lang_stack)
    return "\n".join(out)


# --------------------------------------------------------------------------
# Language detection: tag each top-level block as English or French so the
# EN / FR / Both switcher can hide the other language.
# --------------------------------------------------------------------------

FR_WORDS = set("""le la les des du de et est nous notre nos vous votre vos une un dans pour
avec sur au aux qui que ce cette ces sont être été pas plus par se sa son ses leur leurs
ou où mais aussi comme tous toutes tout très entre chez elle il ils elles dimanche église
bienvenue rencontre semaine après avant ensemble venez joignez-vous l'église d'un d'une
qu'il c'est l'unitarisme café""".split())
EN_WORDS = set("""the and of to is we our you your a an in for with on at who that this these
are be been not more by its their or where but also as all very between he she they it
sunday church welcome join us after before together come please will from have has""".split())
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "source", "track", "wbr"}
CONTAINERS = {"div", "section", "article", "figure", "blockquote", "details"}


def detect_lang(text):
    words = re.findall(r"[a-zA-ZÀ-ÿ'’-]+", text.lower().replace("’", "'"))
    if not words:
        return None
    fr = sum(w in FR_WORDS for w in words)
    en = sum(w in EN_WORDS for w in words)
    fr += len(re.findall(r"[éèêàçùôîâ]", text.lower())) * 0.5
    if fr >= 2 and fr > en * 2:
        return "fr"
    if en >= 2 and en > fr * 2:
        return "en"
    if len(words) <= 6:
        if fr >= 1 and en == 0:
            return "fr"
        if en >= 1 and fr == 0:
            return "en"
    return None


class _Blocks(HTMLParser):
    """Find the character ranges of top-level elements in an HTML fragment."""

    def __init__(self, src):
        super().__init__(convert_charrefs=True)
        self.src = src
        self.line_starts = [0]
        for m in re.finditer("\n", src):
            self.line_starts.append(m.end())
        self.depth = 0
        self.blocks = []  # [start, end, tag, attrs, text]
        self.cur = None

    def off(self):
        ln, col = self.getpos()
        return self.line_starts[ln - 1] + col

    def handle_starttag(self, tag, attrs):
        if self.depth == 0:
            self.cur = [self.off(), None, tag, dict(attrs), []]
            if tag in VOID:
                self.cur[1] = self.off() + len(self.get_starttag_text())
                self.blocks.append(self.cur)
                self.cur = None
                return
        if tag not in VOID:
            self.depth += 1

    def handle_startendtag(self, tag, attrs):
        if self.depth == 0:
            s = self.off()
            self.blocks.append([s, s + len(self.get_starttag_text()), tag, dict(attrs), []])

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        self.depth = max(0, self.depth - 1)
        if self.depth == 0 and self.cur:
            end = self.src.find(">", self.off()) + 1
            self.cur[1] = end
            self.blocks.append(self.cur)
            self.cur = None

    def handle_data(self, data):
        if self.cur is not None:
            self.cur[4].append(data)


def tag_languages(fragment, depth=0):
    """Add lang="en"/"fr" to top-level blocks that don't declare a language."""
    p = _Blocks(fragment)
    p.feed(fragment)
    p.close()
    if p.cur is not None:  # unclosed tag at the end: leave as is
        p.blocks.append([p.cur[0], len(fragment), p.cur[2], p.cur[3], p.cur[4]])
    out, pos = [], 0
    for start, end, tag, attrs, text in p.blocks:
        out.append(fragment[pos:start])
        chunk = fragment[start:end]
        if "lang" not in attrs and tag not in VOID:
            if tag in CONTAINERS and depth < 2:
                # tag the children instead
                inner_start = chunk.find(">") + 1
                inner_end = chunk.rfind("<")
                if 0 < inner_start <= inner_end:
                    chunk = (chunk[:inner_start] +
                             tag_languages(chunk[inner_start:inner_end], depth + 1) +
                             chunk[inner_end:])
            elif re.search(r'\slang="', chunk[chunk.find(">") + 1:]):
                pass  # children already declare their languages (e.g. EN + FR buttons)
            else:
                lang = detect_lang("".join(text))
                if lang:
                    chunk = re.sub(r"^<(\w+)", rf'<\1 lang="{lang}"', chunk, count=1)
        out.append(chunk)
        pos = end
    out.append(fragment[pos:])
    return "".join(out)


class _LangCount(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.count = {"en": 0, "fr": 0}

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        a = dict(attrs)
        parent = self.stack[-1][1] if self.stack else None
        self.stack.append((tag, a.get("lang") or parent))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        lang = self.stack[-1][1] if self.stack else None
        if lang in self.count:
            self.count[lang] += len(data.strip())


def lang_balance(fragment):
    """How much English vs French text is in a tagged fragment."""
    p = _LangCount()
    p.feed(fragment)
    p.close()
    return p.count["en"], p.count["fr"]


def bilingual_scope(fragment):
    """'bi' when both languages are substantially present, else 'mono-en'/'mono-fr'/''."""
    en, fr = lang_balance(fragment)
    if en and fr and min(en, fr) / max(en, fr) >= 0.2:
        return "bi"
    if en > fr:
        return "mono-en"
    if fr > en:
        return "mono-fr"
    return ""


def first_paragraphs(fragment):
    """First English and first French paragraph text, for excerpts."""
    res = {}
    for m in re.finditer(r"<p([^>]*)>(.*?)</p>", fragment, re.S):
        txt = re.sub(r"<[^>]+>", " ", m.group(2))
        txt = html.unescape(re.sub(r"\s+", " ", txt)).strip()
        if len(txt) < 25:
            continue
        lm = re.search(r'lang="(en|fr)"', m.group(1))
        lang = lm.group(1) if lm else "any"
        res.setdefault(lang, txt)
    return res


def shorten(s, n=220):
    if len(s) <= n:
        return s
    return s[:n].rsplit(" ", 1)[0].rstrip(",.;:—–- ") + "…"


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------

EN_MONTHS = "January February March April May June July August September October November December".split()
FR_MONTHS = "janvier février mars avril mai juin juillet août septembre octobre novembre décembre".split()
EN_DAYS = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()
FR_DAYS = "lundi mardi mercredi jeudi vendredi samedi dimanche".split()


def time_en(d):
    h = d.hour % 12 or 12
    ap = "a.m." if d.hour < 12 else "p.m."
    return f"{h}:{d.minute:02d} {ap}" if d.minute else f"{h} {ap}"


def time_fr(d):
    return f"{d.hour} h {d.minute:02d}" if d.minute else f"{d.hour} h"


def date_en(d, weekday=True, year=False):
    s = f"{EN_MONTHS[d.month - 1]} {d.day}"
    if year:
        s += f", {d.year}"
    return (EN_DAYS[d.weekday()] + ", " + s) if weekday else s


def date_fr(d, weekday=True, year=False):
    day = "1er" if d.day == 1 else str(d.day)
    s = f"{day} {FR_MONTHS[d.month - 1]}"
    if year:
        s += f" {d.year}"
    return (FR_DAYS[d.weekday()] + " " + s) if weekday else s


# --------------------------------------------------------------------------
# Content loading
# --------------------------------------------------------------------------

CATEGORIES = {
    "service": ("Sunday service", "Service du dimanche"),
    "concert": ("Concert", "Concert"),
    "away": ("Outing", "Sortie"),
    "event": ("Event", "Événement"),
}


def load_events():
    events = []
    for f in sorted((CONTENT / "events").glob("*.md")):
        try:
            meta, body = read_front_matter(f)
            for req in ("title", "date"):
                if not meta.get(req):
                    raise ValueError(f"missing '{req}:'")
            date = dt.date.fromisoformat(meta["date"])
            st = meta.get("start", "10:30")
            hh, mm = (int(x) for x in st.split(":"))
            start = dt.datetime(date.year, date.month, date.day, hh, mm, tzinfo=TZ)
            if meta.get("end"):
                eh, em = (int(x) for x in meta["end"].split(":"))
                end = start.replace(hour=eh, minute=em)
                if end <= start:
                    end = start + dt.timedelta(hours=1, minutes=30)
            else:
                end = start + dt.timedelta(hours=1, minutes=30)
            cat = meta.get("category", "service").lower()
            if cat not in CATEGORIES:
                raise ValueError(f"category must be one of {', '.join(CATEGORIES)}")
            body_html = tag_languages(markdown(body))
            slug = meta.get("slug") or f.stem
            events.append({
                "file": f.name,
                "slug": slug,
                "url": f"/event/{slug}/",
                "title": meta["title"],
                "title_fr": meta.get("title_fr", ""),
                "start": start,
                "end": end,
                "category": cat,
                "location": meta.get("location", ""),
                "image": url_for(meta.get("image", "")),
                "image_alt": meta.get("image_alt", ""),
                "cancelled": meta.get("cancelled", "").lower() in ("yes", "true", "1"),
                "body": body_html,
                "scope": bilingual_scope(body_html),
                "excerpt": first_paragraphs(body_html),
            })
        except Exception as e:  # keep building, report at the end
            ERRORS.append(f"content/events/{f.name}: {e}")
    events.sort(key=lambda e: e["start"])
    return events


def tidy(body):
    """Normalize HTML left over from WordPress so every page shares one look:
    in-page <h1> become <h2> (the page title is the only <h1>), <header> wrappers,
    align= attributes, target="_top" and empty paragraphs are removed."""
    body = re.sub(r"<(/?)h1\b", r"<\1h2", body)
    body = re.sub(r"</?header\b[^>]*>", "", body)
    body = re.sub(r'\s+align="[^"]*"', "", body)
    body = re.sub(r'\s+target="_top"', "", body, flags=re.I)
    body = re.sub(r"<p>(\s|&nbsp;|\xa0|<br\s*/?>)*</p>", "", body)
    return body


def load_pages():
    pages = []
    for f in sorted((CONTENT / "pages").rglob("*.html")):
        meta, body = read_front_matter(f)
        rel = f.relative_to(CONTENT / "pages").with_suffix("")
        parts = list(rel.parts)
        if parts[-1] == "index":
            parts = parts[:-1]
        url = "/" + "/".join(parts) + ("/" if parts else "")
        body = tag_languages(tidy(body))
        pages.append({"url": url, "title": meta.get("title", rel.name),
                      "title_fr": meta.get("title_fr", ""), "description": meta.get("description", ""),
                      "body": body, "scope": bilingual_scope(body), "meta": meta})
    return pages


def load_news():
    posts = []
    for f in sorted((CONTENT / "news").glob("*.html"), reverse=True):
        meta, body = read_front_matter(f)
        d = dt.date.fromisoformat(meta["date"])
        body = tag_languages(body)
        posts.append({"url": meta.get("url") or f"/news/{f.stem}/", "title": meta["title"],
                      "date": d, "body": body, "scope": bilingual_scope(body),
                      "excerpt": first_paragraphs(body)})
    return posts


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------

def nav_html(current):
    items = []
    for item in SITE["nav"]:
        active = current == item["url"] or (item["url"] != "/" and current.startswith(item["url"]))
        for c in item.get("children", []):
            if current.startswith(c["url"]):
                active = True
        cls = ' class="active"' if active else ""
        sub = ""
        if item.get("children"):
            sub = '<ul class="sub">' + "".join(
                f'<li><a href="{c["url"]}">{t(c["en"], c["fr"])}</a></li>' for c in item["children"]) + "</ul>"
        items.append(f'<li{cls}><a href="{item["url"]}">{t(item["en"], item["fr"])}</a>{sub}</li>')
    return "".join(items)


def page_title(en, fr=""):
    if fr and fr != en:
        return (f'<h1 class="page-title"><span lang="en">{esc(en)}</span>'
                f'<span class="sep"> / </span><span lang="fr">{esc(fr)}</span></h1>')
    return f'<h1 class="page-title">{esc(en)}</h1>'


def mono_note(scope):
    if scope == "mono-en":
        return ('<p class="mono-note" lang="fr">Cette page est présentement disponible '
                'en anglais seulement.</p>')
    if scope == "mono-fr":
        return '<p class="mono-note" lang="en">This page is currently available in French only.</p>'
    return ""


def layout(url, title, main, description="", og_image=""):
    s = SITE
    full_title = f"{title} · {s['name']}" if url != "/" else f"{s['name']} · {s['tagline_en']}"
    desc = description or s["description"]
    og = f'<meta property="og:image" content="{esc(s["base_url"] + og_image)}">' if og_image else ""
    addr = s["address"]
    year = NOW.year
    return f"""<!doctype html>
<html lang="en" data-lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(s['base_url'] + url)}">
{og}
<link rel="canonical" href="{esc(s['base_url'] + url)}">
<link rel="icon" href="/images/favicon.svg" type="image/svg+xml">
<link rel="alternate" type="text/calendar" title="UUEstrie events" href="/events.ics">
<link rel="stylesheet" href="/css/style.css">
<script>(function(){{var l=null;try{{l=localStorage.getItem('uue-lang')}}catch(e){{}}if(l!=='en'&&l!=='fr')l=/^fr/i.test(navigator.language||'')?'fr':'en';document.documentElement.setAttribute('data-lang',l)}})()</script>
</head>
<body>
<a class="skip" href="#content">{t("Skip to content", "Aller au contenu")}</a>
<div class="stripes" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
<header class="site-header">
  <div class="wrap header-row">
    <a class="brand" href="/"><img src="/images/logo.jpg" alt="UUEstrie" width="240" height="91"></a>
    <div class="lang-switch" role="group" aria-label="Language / Langue">
      <button type="button" data-set-lang="en" lang="en">English</button>
      <button type="button" data-set-lang="fr" lang="fr">Français</button>
    </div>
    <button class="menu-toggle" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
  </div>
  <nav id="site-nav" class="site-nav" aria-label="Main">
    <ul class="wrap">{nav_html(url)}<li class="signup"><a href="#newsletter" data-signup>{t("Weekly email", "Courriel hebdo")}</a></li><li class="donate"><a href="/donate/">{t("Donate", "Faire un don")}</a></li></ul>
  </nav>
</header>
<main id="content">
{main}
</main>
<footer class="site-footer">
  <div class="wrap footer-grid">
    <div>
      <h2>UUEstrie</h2>
      <p>{esc(addr['street'])}<br>{esc(addr['city'])} QC {esc(addr['postal'])}<br>
      <a href="tel:{esc(s['phone_tel'])}">{esc(s['phone'])}</a><br>
      <a href="mailto:{esc(s['email'])}">{esc(s['email'])}</a></p>
      <p><a href="{esc(s['map_url'])}">{t("Map and directions", "Carte et itinéraire")}</a></p>
    </div>
    <div>
      <h2>{t("Sundays at 10:30", "Le dimanche à 10 h 30")}</h2>
      <p>{t("Everyone is welcome. Stay for coffee afterwards.", "Tout le monde est bienvenu. Restez pour le café après le service.")}</p>
      <p><a href="/events/">{t("Upcoming services and events", "Services et événements à venir")}</a></p>
    </div>
    <div>
      <h2>{t("Stay connected", "Restez en contact")}</h2>
      <form class="newsletter" id="newsletter" action="{esc(s['newsletter_action'])}" method="post" target="_blank">
        <label for="nl-email">{t("Weekly email", "Courriel hebdomadaire")}</label>
        <div class="nl-row">
          <input type="email" id="nl-email" name="EMAIL" required placeholder="Email / Courriel" autocomplete="email">
          <button type="submit">{t("Sign up", "S’inscrire")}</button>
        </div>
        <div aria-hidden="true" style="position:absolute;left:-5000px"><input type="text" name="{esc(s['newsletter_bot_field'])}" tabindex="-1" value=""></div>
      </form>
      <p><a href="{esc(s['facebook'])}">Facebook</a></p>
    </div>
  </div>
  <div class="wrap footer-small">
    <a href="/accueil/privacy-policy/">{t("Privacy (Law 25)", "Confidentialité (Loi 25)")}</a> ·
    <a href="/suggestions/">Suggestions</a> ·
    <a href="/accueil/links/">{t("UU links", "Liens UU")}</a> ·
    <span>© {year} {t("Unitarian Universalist Church of North Hatley", "Église unitarienne universaliste de North Hatley")}</span>
  </div>
</footer>
<script src="/js/site.js" defer></script>
</body>
</html>
"""


def event_when(e, weekday=True, year=False):
    s = e["start"]
    return t(f"{date_en(s, weekday, year)} · {time_en(s)}", f"{date_fr(s, weekday, year)} · {time_fr(s)}")


def event_title_html(e):
    if e["title_fr"]:
        return f'<span lang="en">{esc(e["title"])}</span><span class="sep"> / </span><span lang="fr">{esc(e["title_fr"])}</span>'
    return esc(e["title"])


def event_card(e, big=False):
    ex = e["excerpt"]
    if "en" in ex or "fr" in ex:
        exc = "".join(f'<p lang="{lg}">{esc(shorten(ex[lg]))}</p>' for lg in ("en", "fr") if lg in ex)
    else:
        exc = f'<p>{esc(shorten(ex.get("any", "")))}</p>' if ex.get("any") else ""
    scope = "bi" if ("en" in ex and "fr" in ex) else ""
    img = (f'<img src="{esc(e["image"])}" alt="" loading="lazy">' if e["image"]
           else '<div class="noimg" aria-hidden="true"></div>')
    cat_en, cat_fr = CATEGORIES[e["category"]]
    cancelled = f'<span class="badge cancel">{t("Cancelled", "Annulé")}</span>' if e["cancelled"] else ""
    return f"""<article class="card{' big' if big else ''} {scope}" data-end="{e['end'].isoformat()}">
  <a class="card-img" href="{e['url']}" tabindex="-1" aria-hidden="true">{img}</a>
  <div class="card-body">
    <p class="when">{event_when(e)}</p>
    <h3><a href="{e['url']}">{event_title_html(e)}</a></h3>
    <p class="meta"><span class="badge {e['category']}">{t(cat_en, cat_fr)}</span>{cancelled}</p>
    {exc}
  </div>
</article>"""


def render_event(e):
    cat_en, cat_fr = CATEGORIES[e["category"]]
    loc = esc(e["location"]) if e["location"] else t(SITE["default_location_en"], SITE["default_location_fr"])
    img = (f'<figure class="hero-img"><img src="{esc(e["image"])}" alt="{esc(e["image_alt"])}"></figure>'
           if e["image"] else "")
    cancelled = (f'<p class="cancel-banner">{t("This event has been cancelled.", "Cet événement est annulé.")}</p>'
                 if e["cancelled"] else "")
    title_h = (f'<h1 class="page-title"><span lang="en">{esc(e["title"])}</span><span class="sep"> / </span>'
               f'<span lang="fr">{esc(e["title_fr"])}</span></h1>' if e["title_fr"]
               else f'<h1 class="page-title">{esc(e["title"])}</h1>')
    main = f"""<article class="wrap narrow event-page">
  <p class="crumbs"><a href="/events/">← {t("All events", "Tous les événements")}</a></p>
  {title_h}
  {cancelled}
  <dl class="event-facts">
    <div><dt>{t("When", "Quand")}</dt><dd>{event_when(e, year=True)}</dd></div>
    <div><dt>{t("Where", "Où")}</dt><dd>{loc}</dd></div>
    <div><dt>{t("Type", "Type")}</dt><dd>{t(cat_en, cat_fr)}</dd></div>
  </dl>
  {img}
  <div class="prose {e['scope']}">{mono_note(e['scope'])}{e['body']}</div>
  <p class="actions"><a class="btn" href="{e['url']}event.ics">{t("Add to my calendar", "Ajouter à mon calendrier")}</a></p>
</article>"""
    title = e["title"]
    desc = shorten(e["excerpt"].get("en") or e["excerpt"].get("any") or e["excerpt"].get("fr") or "", 160)
    return layout(e["url"], title, main, desc, e["image"])


def coming_soon_html():
    rows = []
    for c in SITE.get("coming_soon", []):
        try:
            d = dt.date.fromisoformat(c["date"])
        except Exception:
            continue
        if d < NOW.date():
            continue
        rows.append(f'<li data-end="{d.isoformat()}T23:59:00"><span class="cs-date">{t(date_en(d, False), date_fr(d, False))}</span> {t(c["text"], c["text_fr"]) if c.get("text_fr") else esc(c["text"])}</li>')
    if not rows:
        return ""
    return f'<section class="coming-soon"><h2>{t("Coming soon", "Bientôt")}</h2><ul>{"".join(rows)}</ul></section>'


def render_home(page, events):
    upcoming = [e for e in events if e["end"] >= NOW]
    past = [e for e in events if e["end"] < NOW][::-1]
    nxt = "".join(event_card(e, big=(i == 0)) for i, e in enumerate(upcoming[:4]))
    if not nxt:
        nxt = f'<p>{t("New events will be posted soon.", "De nouveaux événements seront bientôt affichés.")}</p>'
    recent = "".join(event_card(e) for e in past[:3])
    main = f"""<section class="hero">
  <div class="wrap hero-grid">
    <div class="prose {page['scope']}">{page['body']}</div>
    <aside class="join-box">
      <h2>{t("Join us", "Rejoignez-nous")}</h2>
      <p class="big">{t("Sundays at 10:30 a.m.", "Le dimanche à 10 h 30")}</p>
      <p>{esc(SITE['address']['street'])}, {esc(SITE['address']['city'])}</p>
      <p><a class="btn" href="/visit/">{t("Plan your visit", "Planifier votre visite")}</a></p>
    </aside>
  </div>
</section>
<section class="wrap">
  <h2 class="section-title">{t("Upcoming services and events", "Services et événements à venir")}</h2>
  <div class="cards upcoming">{nxt}</div>
  {coming_soon_html()}
  <p class="more"><a href="/events/">{t("See all events", "Voir tous les événements")} →</a></p>
</section>
<section class="wrap">
  <h2 class="section-title">{t("Recent services", "Services récents")}</h2>
  <div class="cards">{recent}</div>
</section>"""
    return layout("/", "Home", main)


def render_events_index(events):
    upcoming = [e for e in events if e["end"] >= NOW]
    past = [e for e in events if e["end"] < NOW][::-1]
    up_html = "".join(event_card(e, big=(i == 0)) for i, e in enumerate(upcoming)) or \
        f'<p>{t("New events will be posted soon.", "De nouveaux événements seront bientôt affichés.")}</p>'
    years = {}
    for e in past:
        years.setdefault(e["start"].year, {}).setdefault(e["start"].month, []).append(e)
    past_html = ""
    for i, (y, months) in enumerate(years.items()):
        inner = ""
        for m, evs in months.items():
            rows = "".join(
                f'<li><span class="pdate">{t(date_en(e["start"], False), date_fr(e["start"], False))}</span>'
                f'<a href="{e["url"]}">{event_title_html(e)}</a>'
                f'{" <em>(" + t("cancelled", "annulé") + ")</em>" if e["cancelled"] else ""}</li>' for e in evs)
            inner += f'<h3>{t(f"{EN_MONTHS[m-1]} {y}", f"{FR_MONTHS[m-1]} {y}")}</h3><ul class="past-list">{rows}</ul>'
        n = sum(len(v) for v in months.values())
        past_html += (f'<details class="past-year"{" open" if i == 0 else ""}><summary>{y} '
                      f'<span class="count">({n})</span></summary>{inner}</details>')
    main = f"""<div class="wrap">
  {page_title("Services and Events", "Services et événements")}
  <p class="lede">{t("Sunday services are at 10:30 a.m. at 201 Main Street, North Hatley, and are open to everyone.",
                     "Les services du dimanche ont lieu à 10 h 30 au 201, rue Main, North Hatley, et sont ouverts à tous.")}
  <a href="#newsletter">{t("Get the weekly email", "Recevez le courriel hebdomadaire")}</a>.</p>
  <h2 class="section-title">{t("Coming up", "À venir")}</h2>
  <div class="cards upcoming">{up_html}</div>
  {coming_soon_html()}
  <h2 class="section-title">{t("Past services and events", "Services et événements passés")}</h2>
  <div class="past">{past_html}</div>
</div>"""
    return layout("/events/", "Events", main)


def section_nav(url):
    """A row of links to the other pages in the same menu section (About us, Ceremonies…)."""
    for item in SITE["nav"]:
        kids = item.get("children", [])
        if any(c["url"] == url for c in kids):
            cur = ' aria-current="page"'
            links = "".join(
                f'<li><a href="{c["url"]}"{cur if c["url"] == url else ""}>'
                f'{t(c["en"], c["fr"])}</a></li>' for c in kids)
            return (f'<nav class="section-nav" aria-label="{esc(item["en"])}">'
                    f'<ul>{links}</ul></nav>')
    return ""


def render_page(p):
    main = f"""<article class="wrap narrow">
  {section_nav(p['url'])}
  {page_title(p['title'], p['title_fr'])}
  <div class="prose {p['scope']}">{mono_note(p['scope'])}{p['body']}</div>
</article>"""
    return layout(p["url"], p["title"], main, p["description"])


def render_news_index(posts):
    rows = "".join(
        f'<li><span class="pdate">{t(date_en(p["date"], False, True), date_fr(p["date"], False, True))}</span>'
        f'<a href="{p["url"]}">{esc(p["title"])}</a></li>' for p in posts)
    main = f"""<div class="wrap narrow">
  {page_title("News archive", "Archives des nouvelles")}
  <p class="lede">{t("Stories and announcements from past years.", "Récits et annonces des années passées.")}</p>
  <ul class="past-list">{rows}</ul>
</div>"""
    return layout("/news/", "News", main)


def render_post(p):
    main = f"""<article class="wrap narrow">
  <p class="crumbs"><a href="/news/">← {t("News archive", "Archives des nouvelles")}</a></p>
  <h1 class="page-title">{esc(p['title'])}</h1>
  <p class="when">{t(date_en(p['date'], False, True), date_fr(p['date'], False, True))}</p>
  <div class="prose {p['scope']}">{p['body']}</div>
</article>"""
    return layout(p["url"], p["title"], main)


def redirect_html(target):
    return (f'<!doctype html><meta charset="utf-8"><title>Redirecting…</title>'
            f'<link rel="canonical" href="{target}"><meta http-equiv="refresh" content="0; url={target}">'
            f'<p><a href="{target}">{target}</a></p>')


# --------------------------------------------------------------------------
# iCalendar
# --------------------------------------------------------------------------

def ics_text(s):
    s = s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    return s


def ics_fold(line):
    out, b = [], line.encode("utf-8")
    while len(b) > 74:
        cut = 74
        while (b[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(b[:cut].decode())
        b = b[cut:]
    out.append(b.decode())
    return "\r\n ".join(out)


def ics(events):
    fmt = "%Y%m%dT%H%M%SZ"
    stamp = NOW.astimezone(dt.timezone.utc).strftime(fmt)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//UUEstrie//Website//EN",
             "CALSCALE:GREGORIAN", "X-WR-CALNAME:UUEstrie"]
    for e in events:
        desc = html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"</p>|<br>", "\n", e["body"]))).strip()
        loc = e["location"] or SITE["default_location_en"]
        title = ("CANCELLED: " if e["cancelled"] else "") + e["title"]
        lines += ["BEGIN:VEVENT",
                  f"UID:{e['slug']}@uuestrie.ca",
                  f"DTSTAMP:{stamp}",
                  f"DTSTART:{e['start'].astimezone(dt.timezone.utc).strftime(fmt)}",
                  f"DTEND:{e['end'].astimezone(dt.timezone.utc).strftime(fmt)}",
                  f"SUMMARY:{ics_text(title)}",
                  f"LOCATION:{ics_text(loc)}",
                  f"URL:{SITE['base_url']}{e['url']}",
                  f"DESCRIPTION:{ics_text(desc[:1500])}",
                  "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(ics_fold(l) for l in lines) + "\r\n"


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

def write(url_path, text):
    p = OUT / url_path.lstrip("/")
    if url_path.endswith("/"):
        p = p / "index.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(STATIC, OUT)
    events = load_events()
    pages = load_pages()
    posts = load_news()

    seen = {}
    for e in events:
        if e["slug"] in seen:
            ERRORS.append(f"content/events/{e['file']}: same slug as {seen[e['slug']]}")
        seen[e["slug"]] = e["file"]

    for p in pages:
        write(p["url"], render_home(p, events) if p["url"] == "/" else render_page(p))
    for e in events:
        write(e["url"], render_event(e))
        write(e["url"] + "event.ics", ics([e]))
    write("/events/", render_events_index(events))
    write("/events.ics", ics(events))
    write("/news/", render_news_index(posts))
    for p in posts:
        write(p["url"], render_post(p))
    for old, new in SITE.get("redirects", {}).items():
        write(old, redirect_html(new))
    write("/404.html", layout("/404.html", "Not found", f"""<div class="wrap narrow">
  {page_title("Page not found", "Page introuvable")}
  <p>{t("Sorry, that page doesn't exist. Try the home page or the events list.",
        "Désolé, cette page n’existe pas. Essayez la page d’accueil ou la liste des événements.")}</p>
  <p><a class="btn" href="/">{t("Home", "Accueil")}</a> <a class="btn" href="/events/">{t("Events", "Événements")}</a></p>
</div>"""))
    urls = [p["url"] for p in pages] + [e["url"] for e in events] + ["/events/", "/news/"] + [p["url"] for p in posts]
    write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "\n".join(f"<url><loc>{SITE['base_url']}{u}</loc></url>" for u in urls) + "\n</urlset>\n")
    write("/robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE['base_url']}/sitemap.xml\n")

    # Check that every local image referenced by an event exists
    for e in events:
        if e["image"].startswith("/") and not (STATIC / e["image"].lstrip("/")).exists():
            ERRORS.append(f"content/events/{e['file']}: image not found: static{e['image']}")

    up = [e for e in events if e["end"] >= NOW]
    print(f"Built {len(pages)} pages, {len(events)} events ({len(up)} upcoming), {len(posts)} news posts → {OUT}")
    if up:
        print("Next up:", up[0]["start"].strftime("%Y-%m-%d %H:%M"), "-", up[0]["title"])
    if ERRORS:
        print("\nPROBLEMS:")
        for err in ERRORS:
            print("  -", err)
        return 1
    return 0


if __name__ == "__main__":
    code = build()
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        import functools
        import http.server
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
        print(f"Preview at http://localhost:{port}  (Ctrl+C to stop)")
        http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()
    sys.exit(code)
