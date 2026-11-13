#!/usr/bin/env python3
"""Preview the built site with canonical URLs, UTF-8 and real 404 responses."""
import argparse
from functools import partial
import gzip
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
SITE = 'https://www.digitaldoc.ro/'
CANONICAL_MARKDOWN = {
    '/index.md': SITE,
    '/en/index.md': SITE + 'en/',
}


class SiteHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.md': 'text/markdown'}

    def accepts_gzip(self):
        preferences = {}
        for item in self.headers.get('Accept-Encoding', '').split(','):
            name, *parameters = item.strip().lower().split(';')
            quality = 1.0
            for parameter in parameters:
                if parameter.strip().startswith('q='):
                    try:
                        quality = float(parameter.strip()[2:])
                    except ValueError:
                        quality = 0.0
            preferences[name.strip()] = quality if 0 <= quality <= 1 else 0.0
        return preferences.get('gzip', preferences.get('*', 0)) > 0

    def send_response(self, code, message=None):
        self._response_code = code
        super().send_response(code, message)

    def guess_type(self, path):
        content_type = super().guess_type(path)
        if self.is_text(content_type):
            return content_type + '; charset=utf-8'
        return content_type

    @staticmethod
    def is_text(content_type):
        return content_type.startswith('text/') or content_type in {
            'application/javascript', 'application/json', 'application/xml', 'image/svg+xml'
        }

    def send_head(self):
        request = urlsplit(self.path)
        request_path = unquote(request.path)
        redirects = {'/index.html': '/', '/en/index.html': '/en/', '/en': '/en/'}
        if request_path in redirects:
            location = redirects[request_path]
            if request.query:
                location += '?' + request.query
            self.send_response(301)
            self.send_header('Location', location)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return None

        root = Path(self.directory).resolve()
        target = Path(self.translate_path(request.path)).resolve()
        if not target.is_relative_to(root):
            self.send_error(404)
            return None
        if target.is_dir():
            target = target / 'index.html'
        if not target.is_file():
            self.send_error(404)
            return None
        if request_path == '/404.html':
            self.send_error(404)
            return None
        try:
            data = target.read_bytes()
        except OSError:
            self.send_error(404)
            return None

        content_type = self.guess_type(str(target))
        compressible = self.is_text(content_type.split(';')[0])
        encoded = gzip.compress(data, mtime=0) if compressible and self.accepts_gzip() else data
        compressed = len(encoded) < len(data)
        body = encoded if compressed else data
        etag = '"' + sha256(body).hexdigest() + '"'
        candidates = [value.strip().removeprefix('W/') for value in
                      self.headers.get('If-None-Match', '').split(',')]
        unchanged = etag in candidates or '*' in candidates
        self.send_response(304 if unchanged else 200)
        self.send_header('ETag', etag)
        if compressible:
            self.send_header('Vary', 'Accept-Encoding')
        if not unchanged:
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            if compressed:
                self.send_header('Content-Encoding', 'gzip')
        self.end_headers()
        return None if unchanged else BytesIO(body)

    def send_error(self, code, message=None, explain=None):
        if code == 404:
            error_page = Path(self.directory) / '404.html'
            if error_page.is_file():
                data = error_page.read_bytes()
                encoded = gzip.compress(data, mtime=0) if self.accepts_gzip() else data
                compressed = len(encoded) < len(data)
                body = encoded if compressed else data
                self.send_response(404, 'Not Found')
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Vary', 'Accept-Encoding')
                self.send_header('X-Robots-Tag', 'noindex')
                if compressed:
                    self.send_header('Content-Encoding', 'gzip')
                self.end_headers()
                if self.command != 'HEAD':
                    self.wfile.write(body)
                return
        super().send_error(code, message, explain)

    def end_headers(self):
        # All served asset names are stable; revalidate them after deployments.
        self.send_header('Cache-Control', 'no-cache')
        request_path = unquote(urlsplit(self.path).path)
        if getattr(self, '_response_code', None) in {200, 304}:
            if request_path in CANONICAL_MARKDOWN:
                self.send_header('Link', '<' + CANONICAL_MARKDOWN[request_path] + '>; rel="canonical"')
            if request_path in {'/llms.txt', '/llms-full.txt'}:
                self.send_header('X-Robots-Tag', 'noindex')
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT / 'dist')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    directory = args.directory.resolve()
    if not (directory / 'index.html').is_file():
        parser.error('Build the site first with npm run build (missing index.html).')
    handler = partial(SiteHandler, directory=str(directory))
    with ThreadingHTTPServer((args.host, args.port), handler) as server:
        print(f'Serving Digitaldoc at http://{args.host}:{server.server_port} from {directory}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
