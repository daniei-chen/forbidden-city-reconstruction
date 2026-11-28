"""Build self-contained README SVGs. Requires fonttools and a local CJK font.

Only the lettering's glyph outlines are exported; no font file is distributed.
The roof illustration is decorative, not a measured elevation.
"""
import argparse
from html import escape
import os
from pathlib import Path
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
RED, GOLD, PAPER = '#721F28', '#D5B57B', '#F5EBDD'


class Lettering:
    def __init__(self, path):
        self.font = TTFont(path, fontNumber=0)
        self.glyphs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.upem = self.font['head'].unitsPerEm

    def text(self, text, x, baseline, size, color=PAPER, tracking=0):
        scale, fragments = size / self.upem, []
        for char in text:
            if char == ' ':
                x += size * .45 + tracking
                continue
            name = self.cmap.get(ord(char))
            if name is None:
                raise ValueError(f'Missing glyph: {char!r}')
            pen = SVGPathPen(self.glyphs)
            self.glyphs[name].draw(pen)
            fragments.append(f'<path fill="{color}" d="{pen.getCommands()}" '
                             f'transform="translate({x:.3f} {baseline:.3f}) scale({scale:.7f} {-scale:.7f})"/>')
            x += self.font['hmtx'].metrics[name][0] * scale + tracking
        return '\n'.join(fragments)


def svg(width, height, title, content, description=''):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">\n'
            f'<title id="title">{escape(title)}</title>\n'
            f'<desc id="desc">{escape(description or title)}</desc>\n'
            + '\n'.join(content) + '\n</svg>\n')


def cover(lettering):
    parts = [
        '<defs><linearGradient id="red" x2="1" y2="1"><stop stop-color="#721F28"/>'
        '<stop offset="1" stop-color="#45161D"/></linearGradient></defs>',
        '<rect width="1600" height="484" fill="url(#red)"/>',
        f'<rect x="24" y="24" width="1552" height="436" fill="none" stroke="{GOLD}" stroke-opacity=".5"/>',
        f'<path d="M24 70V24H70 M1530 24H1576V70 M24 414V460H70 M1530 460H1576V414" '
        f'fill="none" stroke="{GOLD}" stroke-width="3"/>',
        f'<path d="M920 90V394 M940 90V394" stroke="{GOLD}" stroke-opacity=".18"/>',
        f'<rect x="106" y="84" width="112" height="33" fill="none" stroke="{GOLD}" stroke-opacity=".7"/>',
        lettering.text('数字营造', 119, 108, 20, GOLD, 2),
        lettering.text('紫禁城', 101, 264, 126, PAPER, 21),
        lettering.text('三维复原与建筑考据', 112, 329, 33, GOLD, 5),
        '<text x="114" y="380" fill="#D3BBA3" font-family="Georgia,serif" '
        'font-size="17" letter-spacing="4.2">THE FORBIDDEN CITY · DIGITAL RECONSTRUCTION</text>',
        f'<g stroke="{GOLD}" fill="none" stroke-linejoin="round" stroke-linecap="round">',
        '<path d="M1020 342H1478 M1032 350H1466 M1045 359H1453" stroke-width="1.2" opacity=".65"/>',
        '<path d="M1080 335V272 M1114 335V272 M1150 335V272 M1184 335V272 M1221 335V272 '
        'M1257 335V272 M1293 335V272 M1328 335V272 M1363 335V272 M1398 335V272" opacity=".55"/>',
        '<path d="M1058 267H1420 M1068 277H1410" stroke-width="2" opacity=".8"/>',
        '<path d="M1011 253Q1060 257 1097 232L1144 204H1334L1381 232Q1420 257 1467 253 '
        'Q1428 266 1380 263H1098Q1050 266 1011 253Z" stroke-width="1.8"/>',
        '<path d="M1102 239H1376 M1112 231H1366 M1124 222H1354" opacity=".35"/>',
        '<path d="M1124 217V183 M1155 217V183 M1190 217V183 M1225 217V183 '
        'M1260 217V183 M1295 217V183 M1330 217V183 M1360 217V183" opacity=".5"/>',
        '<path d="M1075 175Q1126 176 1165 145L1195 119H1287L1318 145Q1356 176 1409 175 '
        'Q1374 189 1328 185H1156Q1110 189 1075 175Z" stroke-width="2"/>',
        '<path d="M1150 166H1334 M1160 157H1324 M1172 147H1312" opacity=".35"/>',
        '<path d="M1193 119H1289 M1201 113H1281 M1184 119L1178 110 M1298 119L1304 110" stroke-width="2"/>',
        '<path d="M1230 334V295H1252V334 M1190 334V295H1212V334 M1270 334V295H1292V334" opacity=".65"/>',
        '</g>',
        lettering.text('一砖一瓦，循据而造', 1090, 405, 23, '#D3BBA3', 2),
    ]
    return svg(1600, 484, '紫禁城 · 三维复原与建筑考据', parts,
               '宫墙红与琉璃金配色，楷体题字和宫阙线稿装饰。线稿为版式意象，不是模型截图或测绘图。')


def button(lettering, label, primary=False, width=276):
    background, foreground = (RED, PAPER) if primary else (PAPER, RED)
    border = GOLD if primary else '#C7AA80'
    return svg(width, 58, label, [
        f'<rect x=".75" y=".75" width="{width-1.5}" height="56.5" rx="3" '
        f'fill="{background}" stroke="{border}" stroke-width="1.5"/>',
        lettering.text(label, 23, 38, 24, foreground, 1),
        f'<path d="M{width-41} 29H{width-24}M{width-30} 23L{width-24} 29L{width-30} 35" '
        f'fill="none" stroke="{foreground}" stroke-width="1.6"/>',
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', type=Path,
                        default=Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts/simkai.ttf')
    args = parser.parse_args()
    if not args.font.is_file():
        parser.error('Provide an available CJK font with --font.')
    lettering = Lettering(args.font)
    ASSETS.mkdir(parents=True, exist_ok=True)
    artwork = {
        'forbidden-city-cover.svg': cover(lettering),
        'download-model.svg': button(lettering, '下载可编辑工程', primary=True),
        'view-release.svg': button(lettering, '查看版本与预览'),
        'read-verification.svg': button(lettering, '阅读校核记录'),
    }
    for name, content in artwork.items():
        (ASSETS/name).write_text(content, encoding='utf8')
        print(name)


if __name__ == '__main__':
    main()
