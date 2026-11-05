# Treatments — authoring guide

Private presentation pages at `maximkelly.com/t/<slug>/`. No site navigation,
no links to the rest of the site, not indexed, not in the sitemap.

## Make one

1. Write `content/treatments/<slug>.md`
2. Drop assets in `site/assets/treatments/<slug>/`
3. `python3 build_static_site_v3.py`
4. Share `https://maximkelly.com/t/<slug>/`

`<slug>` becomes the URL. Use something readable but not guessable where
confidentiality matters — e.g. `nbt-baby-kool` rather than `test`.

## File format

Markdown with a YAML front matter block:

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

The opening section starts right here. Just write normally.

## Opening

Subheadings become sticky section titles.

![](assets/treatments/nbt-baby-kool/01.jpg)
*Reference — Under the Skin, 2013*

![](wide: assets/treatments/nbt-baby-kool/02.jpg)
*Wide frame, breaks out of the reading column*

![](full: assets/treatments/nbt-baby-kool/03.jpg)
*Full bleed, own section*

{{video: https://vimeo.com/1217571722}}

> A pull quote sits large in the centre of the column.

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

## Blocks

| Syntax | Renders as | Width |
| --- | --- | --- |
| plain paragraph | body text | reading column (~65ch) |
| `## Heading` | sticky section title | reading column |
| `### Heading` | subheading | reading column |
| `![](path)` | image | **inline** — reading column |
| `![](wide: path)` | image | **wide** — ~1200px |
| `![](full: path)` | image | **full** — edge to edge |
| `*text` on the line below an image | caption | under the image |
| `{{video: URL}}` | Vimeo embed | wide |
| `> text` | pull quote | reading column, large |
| `---` | section break | full-width rule |
| `**bold**` / `*italic*` | inline emphasis | — |
| `- item` | list | reading column |

Default image width is `inline`. Use `wide:` or `full:` only when an image
earns the room.

## Images and GIFs — what the build does

Assets in `site/assets/treatments/<slug>/` are handled automatically:

- **Still images** (jpg/png) — resized to max 2000px, re-encoded to JPEG q82.
  A 12MB reference frame becomes roughly 300KB.
- **Animated GIFs** — converted to silent looping MP4 (roughly 10x smaller at
  better quality) and rendered as a looping video. Drop the `.gif` in as normal.
- **Screenshots / text-heavy images** — kept as PNG and downscaled, because JPEG
  artefacts destroy small type.

Drop the original files in and run the build. No preparation needed.

## Motion

Deliberately restrained — the ideas are the product, not the animation.

- every block fades up once as it enters the viewport
- `##` section titles stick near the top while their section scrolls
- `full:` images get a subtle (~5%) parallax drift
- the hero title fades in on load

All of it is disabled under `prefers-reduced-motion`.

## Print

`Cmd + P` gives a designed PDF: light background, no motion, no sticky titles,
images sized to the page. Clients will always PDF it.

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
