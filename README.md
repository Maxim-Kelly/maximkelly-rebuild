# Maxim Kelly — director portfolio

Static site rebuilt from the Cargo export. All video streams from Vimeo, so hosting
costs stay at zero.

## Updating the site

Everything you'll ever edit lives in `content/`. It's plain YAML — no HTML, no JSON.

| I want to… | Edit | 
| --- | --- |
| Change a video page | `content/projects/<Slug>.yml` |
| Add a new video | new `content/projects/<Slug>.yml` + a tile in `content/portfolio.yml` |
| Reorder / remove a portfolio tile | `content/portfolio.yml` |
| Add a press item | `content/press.yml` |
| Change contact details | `content/contact.yml` |
| Change the look | `SITE_CSS` in `build_static_site_v3.py` |

Then rebuild and push:

```sh
python3 build_static_site_v3.py
```

Commit and push in GitHub Desktop. The site redeploys automatically.

### A video page

```yaml
slug: BCNR                 # becomes BCNR.html
title: CONCORDE
artist: BLACK COUNTRY, NEW ROAD
vimeo: https://player.vimeo.com/video/662986910?h=dbd8ce30b8
credits:
  - label: SHARK AWARDS 2022
    value: NOMINATED: BEST DIRECTION, INTERNATIONAL
```

`vimeo` is the `src` of the embed iframe — copy it from Vimeo's *Share → Embed*.
`credits` is optional.

### A portfolio tile

```yaml
- slug: BCNR               # must match a project slug
  image: BCNR_C_MASTER_2K_2.00_04_07_22.Still001.jpeg   # file in site/assets/cargo/
  caption: CONCORDE | BLACK COUNTRY, NEW ROAD
  width: 1526
  height: 858
```

Order in this file is the order on the page. Drop the image into `site/assets/cargo/`
first, then run `python3 optimize_images.py` to shrink it.

### A press item

```yaml
- outlet: PROMONEWS
  groups:
    - label: INTERVIEW
      items:
        - "2024: [MOLCHAT DOMA & PREFUSE 73](https://www.promonews.tv/...)"
        - "2022: [BLACK COUNTRY, NEW ROAD](https://www.promonews.tv/...)"
```

`[text](url)` makes a link. Plain text works too. Stars and ratings are just text.

### A contact row

```yaml
- region: UK
  org: Friend
  org_url: http://www.friendlondon.tv
  person: Luke Jacobs
  email: luke@friendlondon.tv
```

`org` / `org_url` are optional.

## Previewing locally

```sh
python3 build_static_site_v3.py
cd site && python3 -m http.server 8000
```

Then open `http://localhost:8000/menu.html`.

## Deploying

`.github/workflows/deploy.yml` publishes `site/` to GitHub Pages on every push to
`main`. One-time setup: repo **Settings → Pages → Source: GitHub Actions**.

Live URL: `https://maxim-kelly.github.io/maximkelly-rebuild/`

Stylesheet links carry a content hash (`assets/style.css?v=...`) so a CSS change
always takes effect on reload.

## How it fits together

```
content/                    ← you edit this
  projects/*.yml
  portfolio.yml
  press.yml
  contact.yml
build_static_site_v3.py     ← generates site/ from content/
optimize_images.py          ← shrinks portfolio stills
import_content.py           ← one-time migration from the old JSON; not needed again
site/                       ← generated output, this is what deploys
```

`rendered/` and `final-data/` are the original Cargo export. The generator falls back
to them if a `content/` file is missing, but `content/` is the source of truth.
