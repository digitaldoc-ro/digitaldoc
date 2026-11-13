#!/usr/bin/env python3
"""Regenerate and verify the Romanian variable WOFF2; optional build tooling.

Run with:
uv run --no-project --with 'fonttools[woff]==4.68.0' python scripts/subset_fonts.py

The normal site build uses the checked-in font and does not need fontTools.
The original Latin/Latin-ext files and their complete coverage remain unchanged.
"""
from pathlib import Path

from fontTools import subset
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / 'assets/fonts'
ROMANIAN = (set(range(0x0102, 0x0104)) | set(range(0x015E, 0x0160)) |
            set(range(0x0162, 0x0164)) | set(range(0x0218, 0x021C)))


def verify(original, optimized):
    """Compare coverage, variable axes, metrics, attribution and glyph geometry."""
    assert set(optimized.getBestCmap()) == ROMANIAN, 'Unexpected subset coverage'
    axes = [(axis.axisTag, axis.minValue, axis.defaultValue, axis.maxValue)
            for axis in original['fvar'].axes]
    assert axes == [(axis.axisTag, axis.minValue, axis.defaultValue, axis.maxValue)
                    for axis in optimized['fvar'].axes], 'Variable axes changed'
    assert original['head'].unitsPerEm == optimized['head'].unitsPerEm
    for table, fields in {
        'hhea': ('ascent', 'descent', 'lineGap'),
        'OS/2': ('sTypoAscender', 'sTypoDescender', 'sTypoLineGap',
                 'usWinAscent', 'usWinDescent', 'sxHeight', 'sCapHeight'),
    }.items():
        for field in fields:
            assert getattr(original[table], field) == getattr(optimized[table], field), f'{table}.{field} changed'
    for name_id in (0, 13, 14):
        assert original['name'].getDebugName(name_id) == optimized['name'].getDebugName(name_id), 'Attribution/license changed'
    assert 'Source' not in optimized['name'].getDebugName(1), 'Subset must not retain the Reserved Font Name'
    weight_axis = next(axis for axis in original['fvar'].axes if axis.axisTag == 'wght')
    weights = {weight_axis.minValue, weight_axis.defaultValue, weight_axis.maxValue,
               300, 400, 500, 600, 650, 700, 750, 800}
    for weight in sorted(weights):
        if not weight_axis.minValue <= weight <= weight_axis.maxValue:
            continue
        original_glyphs = original.getGlyphSet(location={'wght': weight})
        optimized_glyphs = optimized.getGlyphSet(location={'wght': weight})
        for codepoint in sorted(ROMANIAN):
            names = (original.getBestCmap()[codepoint], optimized.getBestCmap()[codepoint])
            recordings, widths = [], []
            for glyphs, name in zip((original_glyphs, optimized_glyphs), names):
                pen = DecomposingRecordingPen(glyphs)
                glyphs[name].draw(pen)
                recordings.append(pen.value)
                widths.append(glyphs[name].width)
            assert widths[0] == widths[1], f'Advance changed: U+{codepoint:04X}, {weight}'
            assert recordings[0] == recordings[1], f'Outline changed: U+{codepoint:04X}, {weight}'


def main():
    source = FONT_DIR / 'source-sans-3-latin-ext-wght-normal.woff2'
    destination = FONT_DIR / 'digitaldoc-romanian-sans-wght-normal.woff2'
    font = TTFont(source, recalcTimestamp=False)
    options = subset.Options()
    options.flavor = 'woff2'
    options.name_IDs = ['*']
    options.name_languages = ['*']
    options.name_legacy = True
    options.layout_features = ['*']
    options.notdef_outline = True
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=ROMANIAN)
    subsetter.subset(font)
    # The original copyright identifies “Source” as a Reserved Font Name.
    # Rename this derivative while retaining the copyright and OFL metadata.
    for record in font['name'].names:
        if record.nameID in {1, 3, 4, 6, 16, 18, 21, 25}:
            renamed = record.toUnicode().replace('Source Sans 3', 'Digitaldoc Romanian Sans')
            renamed = renamed.replace('SourceSans3', 'DigitaldocRomanianSans')
            record.string = renamed.encode(record.getEncoding())
    font.save(destination)
    with TTFont(source) as original, TTFont(destination) as optimized:
        verify(original, optimized)
    print(f'{source.name}: {source.stat().st_size:,} → {destination.stat().st_size:,} bytes; '
          'coverage, axes, metrics, outlines and license metadata verified')


if __name__ == '__main__':
    main()
