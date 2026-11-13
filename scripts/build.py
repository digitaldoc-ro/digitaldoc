"""Generate both languages and discovery files from one authored template."""
from html import escape
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import struct
import unicodedata

from site_content import parse_html, render_markdown, serialize

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://www.digitaldoc.ro/'
PAGES = {'ro': '', 'en': 'en/'}


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(unicodedata.normalize('NFC', text), encoding='utf-8')


def value_at(dictionary, key):
    value = dictionary
    for part in key.split('.'):
        value = value[part]
    if not isinstance(value, str):
        raise ValueError(f'Translation must be text: {key}')
    return value


def translate(tree, dictionary, language):
    for node in tree.all(lambda n: bool(n.tag)):
        for marker, target in (('data-i18n-placeholder', 'placeholder'),
                               ('data-i18n-aria-label', 'aria-label'),
                               ('data-i18n-alt', 'alt')):
            if marker in node.attrs:
                node.attrs[target] = value_at(dictionary, node.attrs[marker])
        if 'data-i18n' in node.attrs:
            node.children = [value_at(dictionary, node.attrs['data-i18n'])]
        if 'data-i18n-html' in node.attrs:
            node.children = parse_html(value_at(dictionary, node.attrs['data-i18n-html'])).children
        if node.tag == 'html':
            node.attrs['lang'] = language
        if 'lang-switch__btn' in node.attrs.get('class', '').split():
            active = node.attrs['data-lang'] == language
            node.attrs['class'] = 'lang-switch__btn' + (' is-active' if active else '')
            node.attrs.pop('aria-pressed', None)
            node.attrs.pop('aria-current', None)
            if active:
                node.attrs['aria-current'] = 'page'
        if 'logo-link' in node.attrs.get('class', '').split():
            node.attrs['href'] = '/' + PAGES[language]


def metadata(tree, dictionary, language, url):
    title, description = dictionary['meta']['title'], dictionary['meta']['description']
    image = SITE + 'demo-document-1.png'
    image_width, image_height = struct.unpack('>II', (ROOT / 'demo-document-1.png').read_bytes()[16:24])
    organization = {'@type': 'Organization', '@id': SITE + '#organization',
                    'name': 'Digitaldoc', 'legalName': 'ACS ONE MEGA VISION SRL',
                    'url': SITE, 'logo': SITE + 'digitaldoc.svg',
                    'email': 'contact@mg.digitaldoc.ro'}
    website = {'@type': 'WebSite', '@id': SITE + '#website', 'url': SITE,
               'name': 'Digitaldoc', 'inLanguage': ['ro', 'en'],
               'publisher': {'@id': organization['@id']}}
    main = tree.first(lambda n: n.tag == 'main')
    features = main.first(lambda n: n.attrs.get('id') == 'features')
    software = {'@type': 'SoftwareApplication', '@id': SITE + '#software',
                'name': 'Digitaldoc', 'url': 'https://aplicatia.digitaldoc.ro/',
                'description': dictionary['hero']['lead'],
                'applicationCategory': 'BusinessApplication', 'operatingSystem': 'Web',
                'inLanguage': ['ro', 'en'], 'screenshot': image,
                'featureList': [n.text_content() for n in features.all(lambda n: n.tag == 'h3')],
                'publisher': {'@id': organization['@id']}}
    webpage = {'@type': 'WebPage', '@id': url + '#webpage', 'url': url,
               'name': title, 'description': description, 'inLanguage': language,
               'isPartOf': {'@id': website['@id']},
               'mainEntity': {'@id': software['@id']},
               'publisher': {'@id': organization['@id']}}
    graph = json.dumps({'@context': 'https://schema.org',
                        '@graph': [organization, website, webpage, software]},
                       ensure_ascii=False, indent=2).replace('</', '<\\/')
    lines = [f'<title>{escape(title)}</title>',
             f'<meta name="description" content="{escape(description, quote=True)}">',
             '<meta name="robots" content="index, follow, max-image-preview:large">',
             f'<link rel="canonical" href="{url}">']
    for lang, route in PAGES.items():
        lines.append(f'<link rel="alternate" hreflang="{lang}" href="{SITE}{route}">')
    lines.extend([f'<link rel="alternate" hreflang="x-default" href="{SITE}">',
                  f'<link rel="alternate" type="text/markdown" href="{url}index.md" title="Markdown">',
                  f'<link rel="sitemap" type="application/xml" href="{SITE}sitemap.xml">',
                  f'<link rel="describedby" type="text/plain" href="{SITE}llms.txt">'])
    fonts = ['source-sans-3-latin-wght-normal.woff2']
    if language == 'ro':
        fonts.append('digitaldoc-romanian-sans-wght-normal.woff2')
    lines.extend(f'<link rel="preload" href="/assets/fonts/{font}" as="font" type="font/woff2" crossorigin="anonymous">'
                 for font in fonts)
    properties = {'og:type': 'website', 'og:site_name': 'Digitaldoc',
                  'og:title': title, 'og:description': description, 'og:url': url,
                  'og:locale': 'ro_RO' if language == 'ro' else 'en_US',
                  'og:locale:alternate': 'en_US' if language == 'ro' else 'ro_RO',
                  'og:image': image, 'og:image:type': 'image/png',
                  'og:image:width': str(image_width), 'og:image:height': str(image_height),
                  'og:image:alt': dictionary['a11y']['heroImage']}
    lines.extend(f'<meta property="{key}" content="{escape(val, quote=True)}">'
                 for key, val in properties.items())
    twitter = {'card': 'summary_large_image', 'title': title, 'description': description,
               'image': image, 'image:alt': dictionary['a11y']['heroImage']}
    lines.extend(f'<meta name="twitter:{key}" content="{escape(val, quote=True)}">'
                 for key, val in twitter.items())
    lines.append('<script type="application/ld+json">' + graph + '</script>')
    return '\n  '.join(lines)


def optimize(source, landing_script):
    # No external font stylesheet or font-origin connection in the critical path.
    source = re.sub(r'\s*<link[^>]+href="https://fonts\.(?:googleapis|gstatic)\.com[^>]*>', '', source)
    fonts = (ROOT / 'assets/fonts.css').read_text(encoding='utf-8')
    source = source.replace('</head>', '<style>\n' + fonts + '\n</style>\n</head>')
    # A returning visitor may still have the old runtime translator cached at
    # /i18n/landing.js. New HTML must never execute that historical URL again.
    source = source.replace('src="/i18n/landing.js"', f'src="/{landing_script}"')
    # Preserve the existing analytics configuration, loading the library after paint.
    source = source.replace('<script async src="https://www.googletagmanager.com/gtag/js?id=G-J18L89H7RC"></script>', '''<script>
    window.addEventListener('load', function () {
      function loadAnalytics() {
        var script = document.createElement('script');
        script.async = true;
        script.src = 'https://www.googletagmanager.com/gtag/js?id=G-J18L89H7RC';
        document.head.appendChild(script);
      }
      if ('requestIdleCallback' in window) window.requestIdleCallback(loadAnalytics, {timeout: 2000});
      else window.setTimeout(loadAnalytics, 0);
    }, {once: true});
  </script>''')
    return source


def build():
    source = (ROOT / 'src/index.html').read_text(encoding='utf-8')
    script = (ROOT / 'i18n/landing.js').read_bytes()
    landing_script = f'assets/landing.{sha256(script).hexdigest()[:12]}.js'
    # Retain previous versions for visitors whose cached HTML still names them.
    (ROOT / landing_script).write_bytes(script)
    exports, entries = [], []
    for language, route in PAGES.items():
        dictionary = json.loads((ROOT / f'i18n/{language}.json').read_text(encoding='utf-8'))
        url = SITE + route
        tree = parse_html(source)
        translate(tree, dictionary, language)
        html = serialize(tree).replace('<!-- SEO_METADATA -->', metadata(tree, dictionary, language, url))
        if '<!-- SEO_METADATA -->' in html or '<link rel="canonical"' not in html:
            raise ValueError('Missing SEO metadata template marker')
        write(ROOT / route / 'index.html', optimize(html, landing_script))
        main = tree.first(lambda n: n.tag == 'main')
        footer = tree.first(lambda n: n.tag == 'footer')
        markdown = ('<!-- Generated from the visible HTML; edit src/index.html and i18n/*.json. -->\n\n'
                    + ('Sursa canonică: ' if language == 'ro' else 'Canonical source: ')
                    + url + '\n\n' + render_markdown(main, url) + '\n'
                    + render_markdown(footer, url))
        write(ROOT / route / 'index.md', markdown)
        exports.append(markdown)
        entries.append(f'- [{dictionary["meta"]["title"]}]({url}): {dictionary["meta"]["description"]}\n'
                       f'  - [Markdown]({url}index.md)')
    write(ROOT / 'robots.txt', 'User-agent: *\nAllow: /\n\nSitemap: ' + SITE + 'sitemap.xml\n')
    write(ROOT / 'sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + ''.join(f'  <url><loc>{SITE}{route}</loc></url>\n' for route in PAGES.values())
          + '</urlset>\n')
    write(ROOT / 'llms.txt', '# Digitaldoc\n\n'
          '> Official public pages for Digitaldoc, a web application for organizing and sharing documents.\n\n'
          '## Pages / Pagini\n\n' + '\n'.join(entries) + '\n\n'
          '## Product sections / Secțiuni\n\n'
          + '\n'.join(f'- [{label}]({SITE}#{anchor})' for label, anchor in
                      [('Despre Digitaldoc', 'about-digitaldoc'), ('Funcționalități', 'features'),
                       ('Prețuri și limite', 'pricing'), ('Întrebări frecvente', 'faq'), ('Contact', 'contact')])
          + '\n\n## Additional resources\n\n'
          f'- [Complete text]({SITE}llms-full.txt): generated copies of both visible HTML pages.\n'
          '- [Application](https://aplicatia.digitaldoc.ro/): account required for personal documents.\n'
          '- [Terms](https://aplicatia.digitaldoc.ro/terms)\n'
          '- [Privacy](https://aplicatia.digitaldoc.ro/privacy)\n\n'
          'This supplementary index does not replace the canonical HTML pages.\n')
    write(ROOT / 'llms-full.txt', '\n\n---\n\n'.join(exports))
    write(ROOT / '404.html', '''<!doctype html>
<html lang="ro"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>Pagina nu a fost găsită | Digitaldoc</title>
<link rel="icon" href="/favicon.svg"><style>body{font:1.2rem system-ui;margin:10vh auto;padding:2rem;max-width:40rem;color:#1a1d26}a{color:#002b7f}</style>
</head><body><main><h1>Pagina nu a fost găsită / Page not found</h1>
<p>Verifică adresa sau revino la pagina principală.</p><p><a href="/">Digitaldoc în română</a> · <a href="/en/" lang="en">Digitaldoc in English</a></p>
</main></body></html>
''')
    # Publish only the website, keeping source, internal docs and validation out.
    dist = ROOT / 'dist'
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir()
    for name in ('index.html', 'index.md', 'en', 'assets', 'robots.txt',
                 'sitemap.xml', 'llms.txt', 'llms-full.txt', '404.html', 'CNAME',
                 'digitaldoc.svg', 'favicon.svg', 'demo-document-1.png', 'google83152e7ab05f6d9b.html'):
        origin, target = ROOT / name, dist / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if origin.is_dir():
            shutil.copytree(origin, target)
        else:
            shutil.copy2(origin, target)
    write(dist / '.nojekyll', '')
    print('Built Romanian and English HTML, metadata, Markdown, discovery files and dist/.')


if __name__ == '__main__':
    build()
