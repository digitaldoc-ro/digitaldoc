# Digitaldoc landing page

Public website: [www.digitaldoc.ro](https://www.digitaldoc.ro/). The signed-in
application is maintained separately in `../digitaldoc-ui` and runs at
[aplicatia.digitaldoc.ro](https://aplicatia.digitaldoc.ro/).

The landing page uses the same SEO and GEO principles documented in
`~/projects/ppw/proiectul-pagini-web/docs/SEO.md` and `docs/GEO.md`: useful visible
content, stable canonical URLs, truthful structured data, readable static HTML,
and generated discovery files that stay aligned with the page.

## Edit and preview

Python 3.12+ is sufficient; the build uses the standard library and requires no
dependency installation. The npm commands are convenient wrappers:

```sh
npm run build
npm test
npm run dev
```

Preview at [localhost:8000](http://localhost:8000/). The server defaults to the
deployable `dist/` directory and accepts `--directory`, `--host`, and `--port`:

```sh
python3 scripts/serve.py --port 8001
python3 scripts/check_site.py --root dist
```

Edit `src/index.html` and the dictionaries in `i18n/ro.json` and `i18n/en.json`,
then rebuild. Romanian is served at `/`; English is complete static HTML at
`/en/`. Language links work without JavaScript and do not change the language
according to a visitor's IP address. Keep product claims, pricing and module
limits consistent with the application.

The build generates the HTML pages, matching Markdown copies, `robots.txt`,
`sitemap.xml`, `llms.txt`, `llms-full.txt`, and `404.html`. Treat generated files as
outputs; keep changes in the source template or dictionaries. Publish the entire
`dist/` artifact together. It contains only public assets and excludes this
documentation, scripts, tests, and source templates.

The hero uses checked-in responsive WebP images with the original PNG as its
fallback and social preview. To regenerate the variants after replacing the
screenshot, install `cwebp` and run `python3 scripts/optimize_images.py`, then
rebuild. The original screenshot must remain at least 1024 pixels wide.
The optional Romanian font regeneration command and license details are in
`assets/fonts/README.md`; ordinary builds require neither image nor font tools.

## Publish

The GitHub Actions workflow builds and validates pull requests. Pushes to `main`
and manual runs on `main` also publish the `dist/` artifact through GitHub Pages.
In repository **Settings → Pages**, select **GitHub Actions** as the source and
retain the custom domain `www.digitaldoc.ro`. The repository's `CNAME` is included
in the artifact. No deployment or account configuration is performed merely by
editing these local files.

GitHub Pages cannot configure the custom canonical HTTP headers used by the
local server. Apply the production CDN rules in [docs/SEO-GEO.md](docs/SEO-GEO.md),
then verify their actual responses after publication. Local validation confirms
the artifact's consistency; it does not establish Google indexation, live Core
Web Vitals, or AI citations.
