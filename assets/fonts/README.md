# Local variable fonts

The original Source Sans 3 Latin and Latin-ext WOFF2 files are retained unchanged,
with the supplied SIL Open Font License in `OFL.txt`. Their embedded copyright is
“© 2023 Adobe (http://www.adobe.com/), with Reserved Font Name ‘Source’”.

`digitaldoc-romanian-sans-wght-normal.woff2` is a Romanian glyph subset derived
from the original Latin-ext font, under the same SIL Open Font License 1.1. Its
internal font names are changed to **Digitaldoc Romanian Sans** to respect the
reserved name. Copyright and license metadata are preserved. The CSS family name
groups the faces so the existing site can combine their character coverage.

The subset contains Ăă, Șș, Țț, and the legacy cedilla variants Şş/Ţţ:
`U+0102–0103, U+015E–015F, U+0162–0163, U+0218–021B`. Latin already contains Ââ
and Îî. The CSS Latin-ext range excludes these Romanian code points; all other
extended Latin coverage remains available through the original file.

All three faces use the original variable weight range 200–900 and
`font-display: swap`.

To regenerate the optional subset from the repository root:

```sh
uv run --no-project --with 'fonttools[woff]==4.68.0' python scripts/subset_fonts.py
```

The script verifies exact character coverage, variable axes, units per em,
vertical metrics, original attribution/license metadata, and glyph advance
widths/outlines at weights 200, 300, 400, 500, 600, 650, 700, 750, 800 and 900.
Normal builds use the committed WOFF2 and need no font tooling or installation.
