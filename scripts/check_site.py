#!/usr/bin/env python3
"""Validate the public bilingual site, its metadata and generated text copies."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
import argparse
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent.parent
SITE = 'https://www.digitaldoc.ro/'
PAGES = {'ro': ('index.html', SITE), 'en': ('en/index.html', SITE + 'en/')}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
EXCLUDED = {'script', 'style', 'template'}
CONTROLS = {'button', 'input', 'select', 'textarea', 'option', 'form'}
MARKDOWN_LINK = re.compile(r'!?\[([^\]]*)\]\(([^\s)]+)(?:\s+["\'][^)]*["\'])?\)')


def normal(value):
    return re.sub(r'\s+', ' ', value).strip()


def plain_markdown(value):
    value = MARKDOWN_LINK.sub(lambda match: match[1], value)
    value = value.replace('\\|', '|').replace('**', '').replace('`', '')
    return normal(value)


class Node:
    def __init__(self, tag='', attrs=None, parent=None):
        self.tag, self.attrs, self.parent = tag, attrs or {}, parent
        self.children = []

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self):
        return ''.join(child.text() if isinstance(child, Node) else child for child in self.children)

    def public_text(self):
        if not self.visible():
            return ''
        return ''.join(child.public_text() if isinstance(child, Node) else child for child in self.children)

    def ancestors(self):
        current = self
        while current:
            yield current
            current = current.parent

    def visible(self):
        for node in self.ancestors():
            style = re.sub(r'\s+', '', node.attrs.get('style', '').lower())
            if (node.tag in EXCLUDED or 'hidden' in node.attrs or
                    node.attrs.get('aria-hidden', '').lower() == 'true' or
                    set(node.attrs.get('class', '').split()).intersection({'halloween-greeting', 'form-success'}) or
                    'display:none' in style or 'visibility:hidden' in style or
                    (node.tag == 'input' and node.attrs.get('type') == 'hidden')):
                return False
        return True


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def lookup(dictionary, key):
    value = dictionary
    for part in key.split('.'):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def objects(value):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from objects(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from objects(nested)


class Audit:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.errors = []
        self.documents = {}

    def require(self, condition, path, message):
        if not condition:
            try:
                label = str(Path(path).relative_to(self.root))
            except ValueError:
                label = str(path)
            self.errors.append(f'{label}: {message}')
        return bool(condition)

    def read(self, path):
        try:
            text = path.read_text(encoding='utf-8', errors='strict')
        except (OSError, UnicodeError) as error:
            self.require(False, path, f'cannot read UTF-8 file ({error})')
            return ''
        self.require(text == unicodedata.normalize('NFC', text), path, 'text must be NFC-normalized')
        self.require('\ufffd' not in text, path, 'text contains a Unicode replacement character')
        return text

    def document(self, path):
        if path not in self.documents:
            self.documents[path] = Document(self.read(path)).root
        return self.documents[path]

    @staticmethod
    def metadata(nodes, key, attribute='name'):
        return [node.attrs.get('content', '') for node in nodes
                if node.tag == 'meta' and node.attrs.get(attribute) == key]

    def local_target(self, url):
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc != urlsplit(SITE).netloc:
            return None
        path = unquote(parsed.path).lstrip('/')
        target = self.root / path
        if parsed.path.endswith('/') or not path:
            target /= 'index.html'
        target = target.resolve()
        if not target.is_relative_to(self.root):
            return None
        return target

    def links(self, path, canonical, nodes):
        for node in nodes:
            if node.tag not in {'img', 'source'}:
                continue
            for candidate in node.attrs.get('srcset', '').split(','):
                reference = candidate.strip().split()[0] if candidate.strip() else ''
                if reference:
                    target = self.local_target(urljoin(canonical, reference))
                    self.require(target is not None and target.is_file(), path,
                                 f'responsive image asset is missing: {reference}')
        for node in nodes:
            attr = 'href' if node.tag in {'a', 'link'} else 'src' if node.tag in {'img', 'script', 'source'} else None
            reference = node.attrs.get(attr, '') if attr else ''
            if not reference or reference.startswith(('data:', 'mailto:', 'tel:')):
                continue
            self.require(not reference.startswith(('javascript:', 'http:')), path, f'unsafe or insecure URL: {reference}')
            target_url = urljoin(canonical, reference)
            target = self.local_target(target_url)
            if target is None:
                continue
            if not self.require(target.is_file(), path, f'local link or asset is missing: {reference}'):
                continue
            fragment = unquote(urlsplit(target_url).fragment)
            if fragment and target.suffix == '.html':
                ids = {item.attrs.get('id') for item in self.document(target).walk()}
                self.require(fragment in ids, path, f'local anchor is missing: {reference}')

    def translations(self, path, language, nodes):
        dictionary_path = self.root / 'i18n' / f'{language}.json'
        # Deployment packages need no runtime dictionaries. Validate them against
        # the authored dictionaries when the checker is run from the checkout.
        if not dictionary_path.exists():
            dictionary_path = ROOT / 'i18n' / f'{language}.json'
        try:
            dictionary = json.loads(self.read(dictionary_path))
        except json.JSONDecodeError:
            self.require(False, dictionary_path, 'invalid translation JSON')
            return
        titles = [normal(node.text()) for node in nodes if node.tag == 'title']
        self.require(titles == [lookup(dictionary, 'meta.title')], path, f'{language} metadata title differs from dictionary')
        self.require(self.metadata(nodes, 'description') == [lookup(dictionary, 'meta.description')],
                     path, f'{language} metadata description differs from dictionary')
        for node in nodes:
            for attr, key in node.attrs.items():
                if attr != 'data-i18n' and not attr.startswith('data-i18n-'):
                    continue
                expected = lookup(dictionary, key)
                self.require(isinstance(expected, str), path, f'missing {language} translation: {key}')
                if not isinstance(expected, str):
                    continue
                actual = (node.text() if attr in {'data-i18n', 'data-i18n-html'}
                          else node.attrs.get(attr[len('data-i18n-'):], ''))
                if attr == 'data-i18n-html':
                    expected = Document(expected).root.text()
                self.require(normal(actual) == normal(expected), path, f'{language} translation differs for {key}')

    def schema(self, path, canonical, language, nodes):
        graph = []
        for node in nodes:
            if node.tag == 'script' and node.attrs.get('type') == 'application/ld+json':
                try:
                    data = json.loads(node.text())
                    self.require(data.get('@context') == 'https://schema.org', path, 'JSON-LD must declare schema.org context')
                    graph.extend(data.get('@graph', [data]))
                except (json.JSONDecodeError, AttributeError):
                    self.require(False, path, 'invalid JSON-LD')
        types = {entry.get('@type') for entry in graph if isinstance(entry, dict) and isinstance(entry.get('@type'), str)}
        for kind in ('Organization', 'WebSite', 'WebPage', 'SoftwareApplication'):
            self.require(kind in types, path, f'missing {kind} structured data')
        ids = [entry.get('@id') for entry in graph if isinstance(entry, dict)]
        self.require(all(ids) and len(ids) == len(set(ids)), path, 'structured entities need unique @id values')
        visible = normal(' '.join(node.public_text() for node in nodes if node.visible() and node.tag in {'p', 'h1', 'h2', 'h3', 'span', 'a', 'summary'}))
        for entry in objects(graph):
            for forbidden in ('aggregateRating', 'review', 'ratingValue'):
                self.require(forbidden not in entry, path, f'unsupported rating/review property: {forbidden}')
            if '@id' in entry and set(entry) == {'@id'}:
                self.require(entry['@id'] in ids, path, f'undefined structured entity: {entry["@id"]}')
            if entry.get('@type') == 'WebPage':
                self.require(entry.get('url') == canonical, path, 'WebPage URL differs from canonical')
                self.require(entry.get('inLanguage') == language, path, 'WebPage language differs from HTML')
            if entry.get('@type') in {'Organization', 'WebSite', 'SoftwareApplication'}:
                self.require(bool(entry.get('name')) and entry['name'] in visible, path, 'entity name must occur in visible content')
            if entry.get('@type') == 'SoftwareApplication':
                self.require(bool(entry.get('description')) and normal(entry['description']) in visible,
                             path, 'software description must match visible product definition')
                features = entry.get('featureList', [])
                features = [features] if isinstance(features, str) else features
                for feature in features:
                    self.require(isinstance(feature, str) and normal(feature) in visible,
                                 path, f'software feature must match visible content: {feature}')
            if entry.get('email'):
                self.require(entry['email'].removeprefix('mailto:') in visible, path, 'structured email must be visible')
            if entry.get('legalName'):
                self.require(isinstance(entry['legalName'], str) and normal(entry['legalName']) in visible,
                             path, 'structured legalName must be visible')
            if entry.get('sameAs'):
                targets = entry['sameAs'] if isinstance(entry['sameAs'], list) else [entry['sameAs']]
                hrefs = {node.attrs.get('href') for node in nodes if node.tag == 'a' and node.visible()}
                self.require(all(target in hrefs for target in targets), path, 'sameAs links must have visible source links')

    def seo_page(self, path, canonical, language):
        source = self.read(path)
        document = self.document(path)
        nodes = list(document.walk())
        self.require(source.lstrip().lower().startswith('<!doctype html>'), path, 'HTML5 doctype is missing')
        html = [node for node in nodes if node.tag == 'html']
        self.require(len(html) == 1 and html[0].attrs.get('lang') == language, path, 'HTML language does not match URL')
        self.require(any(node.tag == 'meta' and node.attrs.get('charset', '').lower() == 'utf-8' for node in nodes), path, 'UTF-8 declaration is missing')
        self.require(len(self.metadata(nodes, 'viewport')) == 1, path, 'expected one viewport declaration')
        titles = [normal(node.text()) for node in nodes if node.tag == 'title']
        descriptions = self.metadata(nodes, 'description')
        self.require(len(titles) == 1 and bool(titles[0]), path, 'expected one descriptive title')
        self.require(len(descriptions) == 1 and bool(descriptions[0]), path, 'expected one meta description')
        canonicals = [node.attrs.get('href') for node in nodes if node.tag == 'link' and node.attrs.get('rel') == 'canonical']
        self.require(canonicals == [canonical], path, 'canonical URL differs from the expected production URL')
        robots = self.metadata(nodes, 'robots')
        self.require(len(robots) == 1 and not re.search(r'\b(noindex|nofollow|nosnippet)\b', ' '.join(robots), re.I), path, 'page must permit indexing, links and snippets')
        h1s = [node for node in nodes if node.tag == 'h1' and node.visible()]
        self.require(len(h1s) == 1 and bool(normal(h1s[0].text())), path, 'expected one visible H1')
        self.require(len([node for node in nodes if node.tag == 'main']) == 1, path, 'expected one main landmark')
        identifiers = [node.attrs['id'] for node in nodes if node.attrs.get('id')]
        self.require(len(identifiers) == len(set(identifiers)), path, 'duplicate HTML IDs')
        hreflang = [(node.attrs.get('hreflang'), node.attrs.get('href')) for node in nodes
                    if node.tag == 'link' and node.attrs.get('rel') == 'alternate' and node.attrs.get('hreflang')]
        self.require(Counter(hreflang) == Counter({'ro': SITE, 'en': SITE + 'en/', 'x-default': SITE}.items()), path, 'hreflang must reciprocate ro/en/x-default')
        for key, expected in [('og:title', titles[0] if titles else ''), ('og:description', descriptions[0] if descriptions else ''), ('og:url', canonical), ('og:type', 'website')]:
            self.require(self.metadata(nodes, key, 'property') == [expected], path, f'{key} differs from page metadata')
        for key in ('og:image', 'og:image:alt'):
            values = self.metadata(nodes, key, 'property')
            self.require(len(values) == 1 and bool(values[0]), path, f'{key} is missing')
        for key in ('twitter:card', 'twitter:title', 'twitter:description', 'twitter:image', 'twitter:image:alt'):
            values = self.metadata(nodes, key)
            self.require(len(values) == 1 and bool(values[0]), path, f'{key} is missing')
        for image in (node for node in nodes if node.tag == 'img'):
            decorative = (image.attrs.get('role') == 'presentation' or image.attrs.get('aria-hidden') == 'true'
                          or any(parent.tag == 'a' and parent.attrs.get('aria-label') for parent in image.ancestors()))
            self.require('alt' in image.attrs and (bool(image.attrs['alt']) or decorative),
                         path, 'content image is missing descriptive alt text')
            self.require(all(re.fullmatch(r'[1-9]\d*', image.attrs.get(key, '')) for key in ('width', 'height')), path, 'image needs explicit positive width and height')
        self.translations(path, language, nodes)
        self.schema(path, canonical, language, nodes)
        self.links(path, canonical, nodes)
        scripts = '\n'.join(node.text() for node in nodes if node.tag == 'script')
        for node in nodes:
            if node.tag == 'script' and node.attrs.get('src'):
                target = self.local_target(urljoin(canonical, node.attrs['src']))
                if target and target.is_file():
                    scripts += '\n' + self.read(target)
        self.require(not re.search(r'navigator\.(?:language|languages|geolocation)|ipapi|ipinfo|geojs', scripts), path, 'URL language must not depend on browser language or geolocation')
        self.require(not re.search(r'document\.title\s*=|fetch\([^\n]*(?:i18n|\.json)', scripts), path, 'translated content and metadata must be generated before delivery')
        return (titles[0] if titles else '', descriptions[0] if descriptions else '')

    def markdown(self, path):
        content = self.read(path)
        for match in MARKDOWN_LINK.finditer(content):
            parsed = urlsplit(match[2])
            valid = (parsed.scheme == 'https' and bool(parsed.netloc)) or (parsed.scheme == 'mailto' and '@' in parsed.path)
            self.require(valid, path, f'Markdown link must be absolute: {match[2]}')
            target = self.local_target(match[2])
            if target is None:
                continue
            if not self.require(target.is_file(), path, f'Markdown local target is missing: {match[2]}'):
                continue
            fragment = unquote(parsed.fragment)
            html_target = target.with_suffix('.html') if target.suffix == '.md' else target
            if fragment and html_target.suffix == '.html' and html_target.is_file():
                identifiers = {node.attrs.get('id') for node in self.document(html_target).walk()}
                self.require(fragment in identifiers, path, f'Markdown local anchor is missing: {match[2]}')
        return content

    def geo_page(self, path, canonical, language, aggregate):
        nodes = list(self.document(path).walk())
        markdown_path = path.with_suffix('.md')
        markdown = self.markdown(markdown_path)
        self.require(canonical in markdown, markdown_path, 'Markdown must identify its canonical HTML source')
        prose = plain_markdown(markdown)
        combined = plain_markdown(aggregate)
        content_nodes = []
        for node in nodes:
            ancestors = list(node.ancestors())
            in_content = any(parent.tag == 'main' or parent.attrs.get('id') == 'contact' for parent in ancestors)
            if not in_content or not node.visible() or any(parent.tag in CONTROLS for parent in ancestors):
                continue
            if node.tag in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'summary', 'figcaption'} or 'data-i18n' in node.attrs:
                content_nodes.append(node)
        self.require(bool(content_nodes), path, 'public page has no extractable content')
        for node in content_nodes:
            text = normal(node.public_text())
            if not text:
                continue
            for name, target in (('Markdown copy', prose), ('llms-full.txt', combined)):
                self.require(text in target, path, f'visible content missing from {name}: {text[:90]}')
        faq = [node for node in nodes if node.attrs.get('id') == 'faq']
        self.require(len(faq) == 1 and faq[0].visible(), path, 'expected one visible FAQ section')
        if faq:
            questions = [node for node in faq[0].walk() if node.tag in {'summary', 'h3'}]
            self.require(len(questions) >= 3, path, 'FAQ needs at least three visible questions')
            for question in questions:
                self.require(question.visible() and bool(normal(question.text())), path, 'FAQ question must be public and readable')
        # All translated FAQ/definition strings are editorial source material;
        # checking them independently catches missing entire generated sections.
        dictionary_path = self.root / 'i18n' / f'{language}.json'
        if not dictionary_path.exists():
            dictionary_path = ROOT / 'i18n' / f'{language}.json'
        try:
            dictionary = json.loads(self.read(dictionary_path))
            for group in ('faq', 'about'):
                for text in self.strings(dictionary.get(group, {})):
                    visible_text = normal(' '.join(node.public_text() for node in nodes if node.visible() and node.tag in {'p', 'h1', 'h2', 'h3', 'summary'}))
                    self.require(normal(text) in visible_text, path, f'{group} translation must remain visible: {text[:70]}')
                    self.require(normal(text) in prose, markdown_path, f'{group} translation missing from Markdown: {text[:70]}')
        except json.JSONDecodeError:
            self.require(False, dictionary_path, 'invalid translation JSON')

    @staticmethod
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for nested in value.values():
                yield from Audit.strings(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from Audit.strings(nested)

    def discovery(self):
        path = self.root / 'sitemap.xml'
        try:
            tree = ET.fromstring(self.read(path))
            urls = [node.text for node in tree.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
            self.require(Counter(urls) == Counter(url for _, url in PAGES.values()), path, 'sitemap must contain exactly the two canonical HTML URLs')
        except ET.ParseError:
            self.require(False, path, 'invalid sitemap XML')
        robots_path = self.root / 'robots.txt'
        robots = self.read(robots_path)
        self.require(re.search(r'^User-agent:\s*\*\s*$', robots, re.M | re.I) and re.search(r'^Allow:\s*/\s*$', robots, re.M | re.I), robots_path, 'public crawling must be permitted')
        self.require(not re.search(r'^\s*Disallow:\s*/\s*$', robots, re.M | re.I), robots_path, 'robots.txt blocks the site')
        self.require('Sitemap: ' + SITE + 'sitemap.xml' in robots, robots_path, 'canonical sitemap declaration is missing')

    def run(self, seo=True, geo=True):
        metadata = []
        aggregate = self.markdown(self.root / 'llms-full.txt') if geo else ''
        for language, (relative, canonical) in PAGES.items():
            path = self.root / relative
            if seo:
                metadata.append(self.seo_page(path, canonical, language))
            if geo:
                self.geo_page(path, canonical, language, aggregate)
        if seo:
            self.require(len(set(title for title, _ in metadata)) == 2, self.root, 'language pages must have distinct titles')
            self.require(len(set(description for _, description in metadata)) == 2, self.root, 'language pages must have distinct descriptions')
            self.discovery()
        if geo:
            directory_path = self.root / 'llms.txt'
            directory = self.markdown(directory_path)
            targets = [match[2] for match in MARKDOWN_LINK.finditer(directory)]
            for _, canonical in PAGES.values():
                self.require(targets.count(canonical) == 1, directory_path, f'canonical HTML page must occur once: {canonical}')
        # No source/tooling documents should leak into the deployment artifact.
        package = self.root if self.root.name == 'dist' else self.root / 'dist'
        if package.is_dir():
            for name in ('docs', 'scripts', 'src', 'tests', 'node_modules', '.git', '.github',
                         'README.md', 'package.json', 'i18n/ro.json', 'i18n/en.json'):
                self.require(not (package / name).exists(), package / name, 'internal file must not be included in deployment')
        return self.errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='site directory to verify')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--seo-only', action='store_true')
    group.add_argument('--geo-only', action='store_true')
    args = parser.parse_args()
    errors = Audit(args.root).run(seo=not args.geo_only, geo=not args.seo_only)
    if errors:
        print(f'Site validation failed ({len(errors)} issues):')
        for error in errors:
            print('- ' + error)
        return 1
    mode = 'GEO' if args.geo_only else 'SEO' if args.seo_only else 'SEO and GEO'
    print(f'{mode} checks passed for two language pages: content, metadata, entities and discovery files.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
