# Treatments — authoring guide

Private presentation pages at `maximkelly.com/t/<slug>/`. No site navigation,
no links to the rest of the site, not indexed, not in the sitemap.

## Make one

1. Write `content/treatments/<slug>.md`
2. Drop assets in `site/assets/treatments/<slug>/`
3. `python3 optimize_images.py`
4. `python3 build_static_site_v3.py`
5. Share `https://maximkelly.com/t/<slug>/`

`<slug>` becomes the URL. Use something readable but not guessable where
confidentiality matters — e.g. `nbt-baby-kool` rather than `test`.

## File format

Markdown with a YAML front matter block. The YAML is only the header — everything
below it is plain writing.

```markdown
---
client: Nothing But Thieves
track: Baby Kool (Evelyn)
production: Somesuch
director: Maxim Kelly
date: November 2025
version: Treatment v2
hero: assets/treatments/nbt-baby-kool/hero.jpg
---

Just write normally. Blank line between paragraphs.

## Opening

Subheadings become section titles.

![](assets/treatments/nbt-baby-kool/01.jpg)
*Reference — Under the Skin, 2013*

![](wide: assets/treatments/nbt-baby-kool/02.jpg)
*Wide frame, breaks out of the reading column*

![](full: assets/treatments/nbt-baby-kool/03.jpg)
*Full bleed*

{{video: https://vimeo.com/1217571722}}

> A pull quote sits large in the column.

---

## Second section

A line of `---` is a section break.
```

## Front matter

| Field | Required | Appears as |
| --- | --- | --- |
| `client` | no | kicker above the title |
| `track` | yes | main title |
| `production` | no | hero meta + credits |
| `director` | no | hero meta + credits |
| `date` | no | hero meta + credits |
| `version` | no | hero meta + credits |
| `hero` | no | full-bleed hero image |

The hero meta renders as `Directed by Maxim Kelly · Somesuch · November 2025`.
Credits sit at the bottom of the page, right-aligned.

## Blocks

| Syntax | Renders as | Width |
| --- | --- | --- |
| plain paragraph | body text | reading column (~72ch) |
| `## Heading` | section title | reading column |
| `### Heading` | subheading | reading column |
| `![](path)` | image | **inline** — reading column |
| `![](wide: path)` | image | **wide** — ~1180px |
| `![](full: path)` | image | **full** — 94vw, edge to edge |
| `*text` on the line below an image | caption | under the image |
| `{{video: URL}}` | Vimeo embed | wide |
| `> text` | pull quote | reading column, large |
| `---` | section break | full-width rule |
| `**bold**` / `*italic*` | inline emphasis | — |
| `- item` | list | reading column |
| `{{wide}}` on its own line | next block uses the wide width | — |
| `{{columns: 2}}` on its own line | next block splits into 2 columns | — |
| `{{split` … `}}` | two side-by-side panes | wide |

### Side-by-side blocks

```
{{split
left:
Text on the left. Markdown works here.

right:
![](assets/treatments/x/01.jpg)
*Caption on the right*
}}
```

Either side can hold text, images, lists or quotes.

## Images and GIFs — what the build does

Put originals in `site/assets/treatments/<slug>/`, then run
`python3 optimize_images.py`. It handles them automatically:

| You drop in | Build produces | Why |
| --- | --- | --- |
| photo (jpg/webp, or PNG > 1MB) | JPEG, max 2000px, q82 | a 12MB frame becomes ~300KB |
| screenshot (PNG ≤ 1MB) | PNG, downscaled | JPEG artefacts destroy small type |
| **animated GIF** | **silent looping MP4**, GIF removed | ~10x smaller, much better quality |

A GIF written as `![](full: assets/.../transition.gif)` becomes a looping
`<video>` on the page automatically. The build finds the MP4 by name.

Re-running is safe — anything already small is left alone.

## Motion

Deliberately restrained — the ideas are the product, not the animation.

- every block fades up once as it enters the viewport
- a brief dark curtain on first open — the page lifts once it is ready (max five seconds, instant on revisit)
- `full:` images get a subtle (~5%) parallax drift
- the hero title fades in on load

All disabled under `prefers-reduced-motion`.

## Print

`Cmd + P` gives a designed PDF: light background, no motion, images sized to
the page. Clients will always PDF it.

## Analytics and alerts

Treatment pages report anonymous, cookieless events to GoatCounter:
`treatment_open`, `treatment_revisit`, `scroll_depth_25/50/75/100`,
`section_<name>` with dwell time, `video_click`, `treatment_print`.

A single Telegram message is pushed whenever a treatment is opened. Nothing
else alerts — the rest stays in the dashboard. Configure in
`content/config.yml`.

## Privacy

- pages are marked `noindex, nofollow`
- `robots.txt` disallows `/t/`
- treatments are never linked from the main site
- URLs are not in `sitemap.xml`

This is **unlisted, not private**. Anyone with the URL can open it and read the
source. Treat it like an unlisted Vimeo link — fine for normal treatments, not
for anything that genuinely cannot leak.

## Things to avoid

- Don't use a guessable slug where confidentiality matters
- Don't link a treatment from the main site, the press page or social
- Don't put client-identifiable names in image filenames if that's a concern
