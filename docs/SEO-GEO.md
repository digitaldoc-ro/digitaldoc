# Digitaldoc SEO and GEO

Implemented locally on 14 November 2026, following the principles in
`~/projects/ppw/proiectul-pagini-web/docs/SEO.md` and `docs/GEO.md`. Publication and
production CDN/Search Console configuration have not been established by these
repository changes.

## What the site provides

- Romanian static HTML at `https://www.digitaldoc.ro/` and English static HTML at
  `https://www.digitaldoc.ro/en/`, each with a self canonical and reciprocal
  `ro`, `en`, and `x-default` language annotations.
- Complete descriptions and product answers in the HTML response. Language
  selection is an ordinary link; no IP-based translation is needed to read either
  page.
- Consistent title, description, social previews and JSON-LD describing the
  product and its verified operator. Structured data reflects visible content;
  it does not invent ratings, testimonials, dates or product claims.
- A sitemap containing only canonical HTML pages. Build times are not presented
  as editorial update dates.
- Markdown copies and optional LLM discovery files generated from the same
  visible content, with absolute links and UTF-8 text.
- Automated checks for metadata, schema, links, translations, and export parity,
  applied to the repository output and the deployment artifact.
- Self-hosted Source Sans 3 fonts with `font-display: swap`, explicit image
  dimensions, a high-priority hero image, and deferred loading of the existing
  analytics library. The font license is included with the public assets.

Local verification passed on 14 November 2026: the build and both artifact
checks, 14 regression tests, HTTP checks for compression/UTF-8/redirects/404s and
discovery headers, and browser checks for both languages with JavaScript enabled
and disabled at 390, 768, 1000 and 1440 pixels. Language navigation, mobile menu
and pricing selection passed, with no horizontal overflow or page JavaScript
errors. A repeated build produced identical bytes for all 26 public files.
The deterministic page checker also reported no HTML findings for either
language; production response headers and field performance were not measured.

## Lighthouse follow-up — 14 November 2026

Lighthouse 13.5.0 measured the built Romanian homepage using its default mobile
and desktop presets against the local preview. Google Analytics was enabled and
its library was present in both reports. These are local lab measurements,
not deployed-site or field measurements.

| Category | Mobile before | Mobile after | Desktop before | Desktop after |
| --- | --- | --- | --- | --- |
| Performance | 97 | 100 | 100 | 100 |
| Accessibility | 97 | 100 | 97 | 100 |
| Best Practices | 100 | 100 | 100 | 100 |
| SEO | 100 | 100 | 100 | 100 |

The contrast and image-delivery audits now pass. Theme-aware control text and
language-link colors fix the original contrast failures. Browser contrast checks
also passed for both languages in light and dark themes.
Responsive WebP screenshots weigh 8,448–25,326 bytes instead of the 143,415-byte
PNG; the PNG remains the fallback and social image. HTML and social metadata now
use its actual 1024×558 dimensions. Romanian font downloads fell from 88,828 to
31,664 bytes, retaining the original character coverage and verified glyphs.

Mobile LCP improved from 2.6 to 1.5 seconds, with FCP 0.8 seconds, TBT 40 ms and
CLS 0. Desktop LCP was 0.4 seconds, FCP 0.2 seconds, TBT 0 ms and CLS 0.
Lighthouse still identifies unused code inside the external analytics library;
analytics remains enabled. The reported category scores do not imply that every
informational opportunity is absent or that scores will be identical in every run.

GEO here means clear, useful and accessible source material for systems that
retrieve information. Google says existing SEO best practices apply to its AI
features; there is no special schema or mandatory AI text file that guarantees
inclusion. `llms.txt` is a supplementary index for systems that choose to use it,
with no promised ranking or citation benefit. See [Google's AI features
guidance](https://developers.google.com/search/docs/appearance/ai-features).

## Production HTTP rules

The former runtime translator and the current pricing script initially shared
`/i18n/landing.js`. A returning browser could combine current static HTML with
cached translator code and older dictionaries, then replace the Romanian H1 with
an older English heading after first paint. This combination was reproduced in
Chromium on 14 November 2026. Both generated pages now reference the pricing-only
script under a content-hashed URL in `assets/`, and a regression check rejects
the historical script URL. With the old language preference and cached assets
simulated, the corrected pages made no translation/dictionary requests and their
H1 and language remained stable. The H1 and page-title wording is now parallel in
Romanian and English. Publish the generated script together with the HTML; an
already-cached HTML response can require a refresh or expiry before using it.

Keep one preferred origin, `https://www.digitaldoc.ro`, using permanent redirects
from HTTP and the apex domain. Preserve the path and query string. Also redirect
`/index.html` to `/`, `/en/index.html` to `/en/`, and `/en` to `/en/`.

Apply these response-header rules at Cloudflare or the actual production server:

| Exact request path | Response header |
| --- | --- |
| `/index.md` | `Link: <https://www.digitaldoc.ro/>; rel="canonical"` |
| `/en/index.md` | `Link: <https://www.digitaldoc.ro/en/>; rel="canonical"` |
| `/llms.txt`, `/llms-full.txt` | `X-Robots-Tag: noindex` |

Do not add `noindex` to canonical HTML or the Markdown copies. Keep Markdown
accessible so crawlers can read the canonical header. The optional LLM files
remain readable even with `noindex`; that directive controls search indexing,
not access. [Google documents HTTP canonical headers for non-HTML
files](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls).

Serve Markdown as `text/markdown; charset=utf-8`, other text with UTF-8, and unknown
paths with a true HTTP 404. The local preview server demonstrates these behaviors;
GitHub Pages does not support arbitrary custom response headers, so production
headers require CDN/server configuration. Do not copy private project files or
documentation into the public deployment.

## Crawler access and training preferences

`robots.txt` permits crawling and names the canonical sitemap. This preserves
open access without adding crawler-specific licensing or training directives.
Search access and model training are different controls: `OAI-SearchBot` is
distinct from `GPTBot`, and `Claude-SearchBot` from `ClaudeBot`. An allow rule
does not establish that CDN challenges or firewalls permit a crawler's real
requests. Keep existing account/CDN training preferences and check verified
crawler traffic if an actual access problem appears.

## Verification and upkeep

```sh
npm run build
npm test
python3 scripts/check_site.py --root dist
npm run dev
```

After deployment, verify the two HTML URLs, reciprocal language annotations,
Markdown canonical headers, auxiliary `noindex` headers, sitemap, and a nonexistent
URL. Check mobile layout and the language, menu, theme, pricing and contact flows.
Use Search Console URL Inspection and sitemap reports for live Google access and
indexation; use measured user data for Core Web Vitals. Record any AI citation
observations with the date, question, service and cited URL. Local checks and a
crawler User-Agent smoke test do not prove indexation or citation improvements.

Update the source template and locale dictionaries together when functionality,
prices or storage limits change, then rebuild and publish the complete artifact.
Keep the visible FAQ, metadata, schema and exports consistent with the product.
