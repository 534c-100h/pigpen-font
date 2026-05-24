"""
Generate Pigpen Cipher TTF font.

Pigpen cipher mapping (all right-angle line segments):
  Grid 1 (3x3, no dot): A-I   — "missing side" convention
  Grid 2 (3x3, with dot): J-R — same as A-I + dot
  Grid 3 (X, no dot): S-V     — right-angle wedges
  Grid 4 (X, with dot): W-Z   — same as S-V + dot

Consistent line width, baseline-aligned. Clean 90° corners.
"""

import math
import time
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

UPM = 1000
LINE_W = 56
HL = LINE_W / 2

ADVANCE = 800
CELL = 500       # 3×3 grid cell edge
DOT_R = 32

# X-grid: XW = XH/2 for 90° between diagonals. Slightly taller than CELL/2
XH = 560
XW = XH // 2



# ── Draw primitives (each call = 1 contour / rectangle) ───────────

def draw_rect(pen, x1, y1, x2, y2):
    pen.moveTo((x1, y1))
    pen.lineTo((x2, y1))
    pen.lineTo((x2, y2))
    pen.lineTo((x1, y2))
    pen.closePath()


def draw_h(pen, x1, x2, y):
    """Horizontal stroke rectangle centered at y, from x1 to x2."""
    draw_rect(pen, x1, y - HL, x2, y + HL)


def draw_v(pen, y1, y2, x):
    """Vertical stroke rectangle centered at x, from y1 to y2."""
    draw_rect(pen, x - HL, y1, x + HL, y2)


def draw_dot(pen, cx, cy):
    r = DOT_R
    n = 16
    pen.moveTo((cx + r, cy))
    for i in range(1, n + 1):
        a = 2 * math.pi * i / n
        pen.lineTo((cx + r * math.cos(a), cy + r * math.sin(a)))
    pen.closePath()


# ── Grid symbols (A-R, 3×3) ───────────────────────────────────────

def draw_grid(pen, row, col, dotted):
    """Draw a 3×3 grid cell symbol as individual stroke rectangles.
    Segments extended past joints by HL for clean 90° outer corners.
    Uses "missing side" convention: cell (r,c) draws edges for (2-r,2-c).
    """
    lb, rt = 0, CELL

    hs = set()  # y-positions of horizontals
    vs = set()  # x-positions of verticals

    is_t, is_b = row == 0, row == 2
    is_l, is_r = col == 0, col == 2
    outer = is_t + is_b + is_l + is_r

    # Collect edges
    if outer == 2:  # Corner: 2 edges
        if is_t:
            hs.add(rt)
        if is_b:
            hs.add(lb)
        if is_l:
            vs.add(lb)
        if is_r:
            vs.add(rt)
    elif outer == 1:  # Edge: 1 outer + 2 internal = 3 edges
        if is_t:
            hs.add(rt)
            vs.update([lb, rt])
        elif is_b:
            hs.add(lb)
            vs.update([lb, rt])
        elif is_l:
            vs.add(lb)
            hs.update([lb, rt])
        elif is_r:
            vs.add(rt)
            hs.update([lb, rt])
    else:  # Center: 4 edges
        hs.update([lb, rt])
        vs.update([lb, rt])

    # Draw horizontals: extend past ends where verticals exist
    for y in sorted(hs):
        el = HL if lb in vs else 0
        er = HL if rt in vs else 0
        draw_h(pen, lb - el, rt + er, y)

    # Draw verticals: extend past ends where horizontals exist
    for x in sorted(vs):
        eb = HL if lb in hs else 0
        et = HL if rt in hs else 0
        draw_v(pen, lb - eb, rt + et, x)

    if dotted:
        draw_dot(pen, CELL / 2, CELL / 2)


# ── Clipped diagonal stroke (mitered at angle bisector) ────────────

def clip_rect_to_bisector(verts, cx, cy, bx, by):
    """Clip a polygon to the half-plane (x-cx)*bx + (y-cy)*by >= 0.
    bx, by = bisector direction at the convergence (cx, cy).
    Returns clipped polygon vertices (may be 3-5 points)."""
    kept = []
    n = len(verts)
    for i in range(n):
        p1 = verts[i]
        p2 = verts[(i + 1) % n]
        d1 = (p1[0] - cx) * bx + (p1[1] - cy) * by
        d2 = (p2[0] - cx) * bx + (p2[1] - cy) * by
        if d1 >= -1e-6:
            kept.append(p1)
        if (d1 > 1e-6 and d2 < -1e-6) or (d1 < -1e-6 and d2 > 1e-6):
            t = d1 / (d1 - d2)
            ix = p1[0] + t * (p2[0] - p1[0])
            iy = p1[1] + t * (p2[1] - p1[1])
            kept.append((ix, iy))
    return kept


def draw_clipped_diag(pen, x1, y1, x2, y2, cx, cy, bx, by):
    """Draw a diagonal stroke, clipped to one side of the angle bisector."""
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    if L < 1:
        return
    ux, uy = dx / L, dy / L
    nx, ny = -uy * HL, ux * HL
    sx, sy = x1 - ux * HL * 2, y1 - uy * HL * 2
    rect = [
        (sx + nx, sy + ny),
        (x2 + nx, y2 + ny),
        (x2 - nx, y2 - ny),
        (sx - nx, sy - ny),
    ]
    clipped = clip_rect_to_bisector(rect, cx, cy, bx, by)
    if len(clipped) >= 3:
        pen.moveTo(clipped[0])
        for p in clipped[1:]:
            pen.lineTo(p)
        pen.closePath()


# ── X-grid wedge symbols (S-Z): miter-clipped diagonals ───────────

def draw_wedge(pen, pos):
    """Draw two diagonal strokes clipped at the angle bisector.
    Produces a clean, sharp V with no protruding corners."""
    CY = XH / 2
    if pos == 'top':      # S: \/  converge at (0,0), bisector = (0,1)
        draw_clipped_diag(pen, 0, 0, -XW, XH, 0, 0, -1, 0)
        draw_clipped_diag(pen, 0, 0, XW, XH, 0, 0, 1, 0)
    elif pos == 'left':   # T: <  converge at (XW,CY), bisector = (-1,0)
        draw_clipped_diag(pen, XW, CY, -XW, XH, XW, CY, 0, 1)
        draw_clipped_diag(pen, XW, CY, -XW, 0, XW, CY, 0, -1)
    elif pos == 'right':  # U: >  converge at (-XW,CY), bisector = (1,0)
        draw_clipped_diag(pen, -XW, CY, XW, XH, -XW, CY, 0, 1)
        draw_clipped_diag(pen, -XW, CY, XW, 0, -XW, CY, 0, -1)
    else:                 # V: /\ converge at (0,XH), bisector = (0,-1)
        draw_clipped_diag(pen, 0, XH, -XW, 0, 0, XH, -1, 0)
        draw_clipped_diag(pen, 0, XH, XW, 0, 0, XH, 1, 0)


# ── RecordingPen replay helpers ───────────────────────────────────

def _replay(rec, out_pen, ox, oy):
    for cmd, args in rec.value:
        if cmd == 'moveTo':
            out_pen.moveTo((args[0][0] + ox, args[0][1] + oy))
        elif cmd == 'lineTo':
            out_pen.lineTo((args[0][0] + ox, args[0][1] + oy))
        elif cmd == 'closePath':
            out_pen.closePath()


def _ymin(rec):
    y = float('inf')
    for cmd, args in rec.value:
        if cmd in ('moveTo', 'lineTo'):
            y = min(y, args[0][1])
    return y if y != float('inf') else 0


# ── Glyph drawer factories ────────────────────────────────────────

def make_grid_drawer(row, col, dotted):
    def draw(pen):
        from fontTools.pens.recordingPen import RecordingPen
        rec = RecordingPen()
        draw_grid(rec, row, col, dotted)
        ox = (ADVANCE - CELL) / 2
        oy = -_ymin(rec)
        _replay(rec, pen, ox, oy)
    return draw


def make_wedge_drawer(pos, dotted):
    def draw(pen):
        from fontTools.pens.recordingPen import RecordingPen
        rec = RecordingPen()
        draw_wedge(rec, pos)
        if dotted:
            xs, ys = [], []
            for cmd, args in rec.value:
                if cmd in ('moveTo', 'lineTo'):
                    xs.append(args[0][0])
                    ys.append(args[0][1])
            if xs:
                cx = (min(xs) + max(xs)) / 2
                cy = (min(ys) + max(ys)) / 2
                # Push dot away from convergence point toward wide opening
                bias = 0.15 * XH  # shift amount
                if pos == 'top':        # converge at bottom → push up
                    cy += bias
                elif pos == 'bottom':   # converge at top → push down
                    cy -= bias
                elif pos == 'left':     # converge at right → push left
                    cx -= bias
                else:                   # 'right': converge at left → push right
                    cx += bias
                draw_dot(rec, cx, cy)
            else:
                draw_dot(rec, 0, XH / 2)
        ox = ADVANCE / 2
        oy = -_ymin(rec)
        _replay(rec, pen, ox, oy)
    return draw


def period_drawer(pen):
    r = 50
    cx = ADVANCE / 2
    cy = r
    n = 16
    pen.moveTo((cx + r, cy))
    for i in range(1, n + 1):
        a = 2 * math.pi * i / n
        pen.lineTo((cx + r * math.cos(a), cy + r * math.sin(a)))
    pen.closePath()


def notdef_drawer(pen):
    draw_rect(pen, 50, 50, ADVANCE - 50, UPM - 50)


def space_drawer(pen):
    pass


# ── Letter mappings ───────────────────────────────────────────────

# 3×3 grid, "missing side" convention:
#   A(top-left)=┘  B(top-centre)=⊔  C(top-right)=└
#   D(mid-left)=┤  E(centre)=□      F(mid-right)=├
#   G(bot-left)=┐  H(bot-centre)=⊓  I(bot-right)=┌
#   J-R: same + dot
GRID = [
    ('A', 2, 2), ('B', 2, 1), ('C', 2, 0),
    ('D', 1, 2), ('E', 1, 1), ('F', 1, 0),
    ('G', 0, 2), ('H', 0, 1), ('I', 0, 0),
]

# X-grid right-angle wedges:
#   S=\/  T=>  U=<  V=/\
#   W-Z: same + dot
CROSS = [
    ('S', 'top'),  ('T', 'left'),  ('U', 'right'), ('V', 'bottom'),
    ('W', 'top'),  ('X', 'left'),  ('Y', 'right'), ('Z', 'bottom'),
]


def build_font():
    glyph_order = ['.notdef', 'space']
    for i in range(26):
        glyph_order.append(chr(65 + i))
    for i in range(26):
        glyph_order.append(chr(97 + i))
    glyph_order.append('period')

    drawers = {
        '.notdef': notdef_drawer,
        'space': space_drawer,
        'period': period_drawer,
    }

    for l, r, c in GRID:
        drawers[l] = make_grid_drawer(r, c, False)
        drawers[l.lower()] = make_grid_drawer(r, c, False)
        dl = chr(ord(l) + 9)
        drawers[dl] = make_grid_drawer(r, c, True)
        drawers[dl.lower()] = make_grid_drawer(r, c, True)

    for l, pos in CROSS:
        dotted = l in ('W', 'X', 'Y', 'Z')
        drawers[l] = make_wedge_drawer(pos, dotted)
        drawers[l.lower()] = make_wedge_drawer(pos, dotted)

    cmap = {0: '.notdef', 32: 'space'}
    for i in range(26):
        cmap[65 + i] = chr(65 + i)
        cmap[97 + i] = chr(97 + i)
    cmap[0x3002] = 'period'
    cmap[0x002E] = 'period'

    metrics = {n: (300, 0) if n == 'space' else (ADVANCE, 0)
               for n in glyph_order}

    class _GS:
        def __getitem__(self, k):
            return None
    gs = _GS()

    glyph_objects = {}
    for name in glyph_order:
        pen = TTGlyphPen(gs)
        drawers[name](pen)
        glyph_objects[name] = pen.glyph()

    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyph_objects)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    import datetime as _dt
    _build = _dt.datetime.now().strftime('%H%M')
    fb.setupNameTable({
        'familyName': f'Pigpen Cipher b{_build}',
        'styleName': 'Regular',
        'uniqueFontIdentifier': f'PigpenCipher-b{_build}-Regular',
        'fullName': f'Pigpen Cipher b{_build} Regular',
        'version': f'Version 2.{_build}',
        'psName': f'PigpenCipher-b{_build}-Regular',
    })
    fb.setupOS2(
        sTypoAscender=800, sTypoDescender=-200,
        usWinAscent=900, usWinDescent=300,
        fsType=0,
        fsSelection=0x0040,  # bit 6: REGULAR
        ulUnicodeRange1=0x00000001,
        ulCodePageRange1=0x00000001,
        achVendID='WHIM',
    )
    fb.setupPost()
    mac_now = int(time.time()) + 2082844800
    fb.setupHead(unitsPerEm=UPM, created=mac_now, modified=mac_now)

    output = 'PigpenCipher.ttf'
    # Force post table to format 3.0 (no glyph names) for maximum software compatibility
    old_post = fb.font['post']
    old_post.formatType = 3.0
    fb.save(output)

    font = TTFont(output)
    print(f'Font: {output}  |  LINE_W={LINE_W}  HL={HL}')
    glyf = font['glyf']
    for name in ['.notdef', 'A', 'B', 'D', 'E', 'G', 'J',
                 'S', 'T', 'U', 'V', 'W', 'period']:
        g = glyf[name]
        n = g.numberOfContours if hasattr(g, 'numberOfContours') else 0
        bb = f'({g.xMin},{g.yMin},{g.xMax},{g.yMax})' if n > 0 else 'empty'
        print(f'  {name}: {n} contours, bbox={bb}')

    print('Mapping:')
    print('  A-I: 3x3 grid, missing-side convention')
    print('  J-R: same + dot')
    print('  S-V: right-angle wedges: S=\\/ T=> U=< V=/\\')
    print('  W-Z: same + dot')
    print('Done.')


if __name__ == '__main__':
    build_font()
