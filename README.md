# Maxim Kelly — director portfolio

Static site rebuilt from the Cargo export. All video is streamed from Vimeo, so
hosting costs stay at zero.

## How the site is built

Never hand-edit `site/*.html` — every page is generated.

```
rendered/<Project>.json   project pages (video, credits, awards)
final-data/portfolio.json portfolio grid + captions
final-data/contact.json   contact rows
final-data/selected-press.json  press rows
build_static_site_v3.py   the generator
optimize_images.py        shrinks portfolio stills
site/                     generated output — this is what gets deployed
```

Regenerate everything:

```sh
python3 build_static_site_v3.py
```

It rewrites `site/*.html`, `site/assets/style.css`, plus all the redirect
aliases and `404.html`. It also checks every internal link and fails if any
Cargo placeholder markup is left over.

## Adding content

| What | Edit | Then |
| --- | --- | --- |
| New portfolio piece | new `rendered/New-Project.json` + a tile in `final-data/portfolio.json` | `python3 build_static_site_v3.py` |
| Contact details | `final-data/contact.json` | `python3 build_static_site_v3.py` |
| Press item | `final-data/selected-press.json` | `python3 build_static_site_v3.py` |
| Look / typography | `SITE_CSS` in `build_static_site_v3.py` | `python3 build_static_site_v3.py` |

For a new project page, copy an existing file in `rendered/` and change
`"page"`, `"title"` and `"content_html"`. The Vimeo iframe goes straight in
`content_html`.

After adding images to `site/assets/cargo/`, run `python3 optimize_images.py`.

## Deploying

`.github/workflows/deploy.yml` publishes `site/` to GitHub Pages on every push
to `main`.

One-time setup:

1. Push this repo to GitHub.
2. Repo **Settings → Pages → Source: GitHub Actions**.

Live URL is `https://<username>.github.io/<repo>/`.

## Preview locally

```sh
python3 build_static_site_v3.py
cd site && python3 -m http.server 8000
```

Then open `http://localhost:8000/menu.html`.
