"""Mutation tests prove that broken discovery or lost public content fails QA."""
from pathlib import Path
import importlib.util
import json
import re
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('check_site', ROOT / 'scripts/check_site.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


class SiteChecksTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'site'
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns('.git', 'node_modules', '__pycache__', 'dist'))
        self.assertTrue((self.root / 'en/index.html').is_file(), 'Generate the bilingual site with python3 scripts/build.py before testing.')

    def mutate(self, relative, before, after):
        path = self.root / relative
        source = path.read_text(encoding='utf-8')
        self.assertIn(before, source, f'Mutation target missing in {relative}')
        path.write_text(source.replace(before, after, 1), encoding='utf-8')

    def assert_issue(self, message, **options):
        errors = checks.Audit(self.root).run(**options)
        self.assertTrue(any(message in error for error in errors), '\n'.join(errors))

    def test_generated_pages_pass(self):
        self.assertEqual(checks.Audit(self.root).run(), [])

    def test_canonical_regression_is_rejected(self):
        self.mutate('index.html', '<link rel="canonical" href="https://www.digitaldoc.ro/">',
                    '<link rel="canonical" href="https://digitaldoc.ro/">')
        self.assert_issue('canonical URL differs', geo=False)

    def test_untranslated_english_content_is_rejected(self):
        english = json.loads((self.root / 'i18n/en.json').read_text(encoding='utf-8'))
        romanian = json.loads((self.root / 'i18n/ro.json').read_text(encoding='utf-8'))
        self.mutate('en/index.html', english['hero']['title'], romanian['hero']['title'])
        self.assert_issue('en translation differs for hero.title', geo=False)

    def test_hidden_faq_is_rejected(self):
        self.mutate('index.html', '<section id="faq"', '<section hidden id="faq"')
        self.assert_issue('expected one visible FAQ section', seo=False)

    def test_removed_faq_is_rejected(self):
        path = self.root / 'index.html'
        source, count = re.subn(r'<section id="faq"[^>]*>.*?</section>', '', path.read_text(encoding='utf-8'), count=1, flags=re.S)
        self.assertEqual(count, 1)
        path.write_text(source, encoding='utf-8')
        self.assert_issue('expected one visible FAQ section', seo=False)

    def test_markdown_lost_answer_is_rejected(self):
        dictionary = json.loads((self.root / 'i18n/ro.json').read_text(encoding='utf-8'))
        self.mutate('index.md', dictionary['faq']['free']['answer'], 'Answer accidentally omitted.')
        self.assert_issue('visible content missing from Markdown copy', seo=False)

    def test_relative_markdown_link_is_rejected(self):
        self.mutate('index.md', '(https://aplicatia.digitaldoc.ro', '(/application')
        self.assert_issue('Markdown link must be absolute', seo=False)

    def test_broken_llms_fragment_is_rejected(self):
        self.mutate('llms.txt', '(https://www.digitaldoc.ro/#about-digitaldoc)',
                    '(https://www.digitaldoc.ro/#missing-product-definition)')
        self.assert_issue('Markdown local anchor is missing', seo=False)

    def test_missing_markdown_target_is_rejected(self):
        self.mutate('llms.txt', '(https://www.digitaldoc.ro/en/index.md)',
                    '(https://www.digitaldoc.ro/en/missing-copy.md)')
        self.assert_issue('Markdown local target is missing', seo=False)

    def test_wrong_language_alternate_is_rejected(self):
        self.mutate('en/index.html', 'hreflang="ro" href="https://www.digitaldoc.ro/"',
                    'hreflang="ro" href="https://www.digitaldoc.ro/en/"')
        self.assert_issue('hreflang must reciprocate', geo=False)

    def test_broken_navigation_anchor_is_rejected(self):
        self.mutate('index.html', 'href="#features"', 'href="#missing-features"')
        self.assert_issue('local anchor is missing', geo=False)

    def test_fabricated_rating_is_rejected(self):
        self.mutate('index.html', '"legalName":', '"aggregateRating": {"ratingValue": "5"}, "legalName":')
        self.assert_issue('unsupported rating/review property', geo=False)

    def test_unsubstantiated_legal_name_is_rejected(self):
        self.mutate('index.html', '"legalName": "ACS ONE MEGA VISION SRL"',
                    '"legalName": "Unsubstantiated Operator SRL"')
        self.assert_issue('structured legalName must be visible', geo=False)

    def test_missing_sitemap_language_is_rejected(self):
        self.mutate('sitemap.xml', '  <url><loc>https://www.digitaldoc.ro/en/</loc></url>', '')
        self.assert_issue('sitemap must contain exactly', geo=False)


if __name__ == '__main__':
    unittest.main()
