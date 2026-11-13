"""Small HTML tree and visible-content export for the static landing page."""
from html import escape
from html.parser import HTMLParser
import re
from urllib.parse import urljoin

VOID = set('area base br col embed hr img input link meta param source track wbr'.split())
IGNORE = {'script', 'style', 'svg', 'template', 'input', 'button', 'textarea', 'select', 'form'}


def clean(text):
    return re.sub(r'\s+', ' ', text).strip()


class Node:
    def __init__(self, tag='', attrs=None, children=None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.children = children or []

    def all(self, predicate):
        if predicate(self):
            yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.all(predicate)

    def first(self, predicate):
        return next(self.all(predicate))

    def text_content(self):
        return clean(''.join(c.text_content() if isinstance(c, Node) else c for c in self.children))


class Tree(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
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

    def handle_comment(self, text):
        self.stack[-1].children.append(Node('!comment', children=[text]))

    def handle_decl(self, decl):
        self.stack[-1].children.append(Node('!declaration', children=[decl]))


def parse_html(source):
    return Tree(source).root


def serialize(node):
    if isinstance(node, str):
        return escape(node, quote=False)
    if node.tag == '!comment':
        return '<!--' + ''.join(node.children) + '-->'
    if node.tag == '!declaration':
        return '<!' + ''.join(node.children) + '>'
    attrs = ''.join(' ' + key + ('' if value is None else '="' + escape(value, quote=True) + '"')
                    for key, value in node.attrs.items())
    if node.tag in {'script', 'style'}:
        content = ''.join(node.children)
    else:
        content = ''.join(serialize(child) for child in node.children)
    if not node.tag:
        return content
    return '<' + node.tag + attrs + '>' + ('' if node.tag in VOID else content + '</' + node.tag + '>')


def hidden(node):
    classes = node.attrs.get('class', '').split()
    return (node.tag in IGNORE or node.tag.startswith('!') or 'hidden' in node.attrs
            or node.attrs.get('aria-hidden') == 'true'
            or 'halloween-greeting' in classes or 'form-success' in classes)


def inline(node, base_url):
    if isinstance(node, str):
        return node
    if hidden(node):
        return ''
    content = ''.join(inline(child, base_url) for child in node.children)
    if node.tag == 'a':
        return '[' + clean(content) + '](' + urljoin(base_url, node.attrs['href']) + ')'
    if node.tag == 'img':
        return ('![' + node.attrs['alt'] + '](' + urljoin(base_url, node.attrs['src']) + ')'
                if node.attrs.get('alt') else '')
    if node.tag == 'br':
        return ' '
    if node.tag in {'strong', 'b', 'em', 'i'} and content.strip():
        marker = '**' if node.tag in {'strong', 'b'} else '*'
        return ' ' + marker + content.strip() + marker + ' '
    return content


def render_markdown(node, base_url):
    """Keep headings, answers, pricing labels, lists and absolute links."""
    block_tags = {'div', 'section', 'article', 'main', 'footer', 'figure', 'figcaption',
                  'p', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                  'details', 'summary', 'label', 'dl', 'dt', 'dd', 'table'}

    def blocks(current):
        if isinstance(current, str) or hidden(current):
            return []
        tag = current.tag
        if tag in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
            return ['#' * int(tag[1]) + ' ' + clean(inline(current, base_url))]
        if tag in {'p', 'summary', 'figcaption', 'label', 'dt', 'dd'}:
            text = clean(inline(current, base_url))
            return [('### ' if tag == 'summary' else '') + text] if text else []
        if tag in {'ul', 'ol'}:
            items = []
            for index, child in enumerate((c for c in current.children if isinstance(c, Node) and c.tag == 'li'), 1):
                text = '\n\n'.join(blocks(child))
                if text:
                    prefix = f'{index}. ' if tag == 'ol' else '- '
                    items.append(prefix + text.replace('\n', '\n' + ' ' * len(prefix)))
            return ['\n'.join(items)] if items else []
        parts, pending = [], []

        def flush():
            text = clean(''.join(pending))
            if text:
                parts.append(text)
            pending.clear()

        for child in current.children:
            if isinstance(child, Node) and child.tag in block_tags:
                flush()
                parts.extend(blocks(child))
            else:
                pending.append(inline(child, base_url))
        flush()
        return parts

    return '\n\n'.join(blocks(node)).rstrip() + '\n'
