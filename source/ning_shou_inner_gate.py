"""Ningshou Gate: a five-bay gate hall, carved terrace and splayed glazed screens."""
import math
from types import SimpleNamespace

import bpy
from mathutils import Vector
from shapely.geometry import LineString, box

from architectural_roofs import swept_roof
from carved_ornament import cloud
from garden_bridge_pavilions import laid_pavers, transfer
from mesh_tools import Batch, collection
from ning_shou_gate import local_shape, pave
from osm_site import rectangle
from paired_halls import column, frame, lattice
from palace_architecture import dougong, stairs
from palace_materials import paint
from qinan_hall import marble_rail, painted_bay
from qinan_survey import Location


INNER_ID = '40592357'
INNER_SOURCE = 'https://www.dpm.org.cn/explore/building/236520.html'
INNER_FLOOR = 1.045
STAIR_TOE, TERRACE_EDGE = -11.05, -6.74
XS = (-13.18, -8.64, -3.06, 3.06, 8.64, 13.18)
YS = (-4.67, -2.18, 2.19, 4.61)
STAIRS = ((-5.72, 3.75), (0., 5.14), (5.72, 3.75))
EAVE = 6.58


def palette(base):
    p = SimpleNamespace(**base.__dict__)
    p.understone = p.stone
    p.stone = p.cleanstone
    p.fascia = p.door
    p.faded_teal = p.teal
    p.faded_blue = p.blue
    p.cream = p.giltpaint
    p.lion_gold = paint('宁寿门 · 鎏金铜狮与残存的金层', (.203, .100, .026),
                        second=(.671, .461, .117), scale=17.5, rough=.38, metal=.71, bump=.0025, coat=.09)
    p.window_gold = paint('宁寿门 · 棂窗和框口贴金', (.37, .181, .034),
                           second=(.70, .44, .116), scale=10.2, rough=.52, metal=.31, bump=.0017)
    return p


def gilt_guardian(loc, target, sign, p):
    x, y = sign * 3.58, STAIR_TOE - .54
    foot, body, carving = loc.batch(), loc.batch(), loc.batch()
    for z, w, d, h in ((.076, .943, .95, .10), (.150, .874, .893, .047), (.241, .755, .765, .144),
                       (.335, .858, .862, .047), (.385, .901, .903, .053)):
        foot.box((x, y, z), (w, d, h), p.understone if h > .10 else p.stone)
        for a in (-1, 1):
            for j in range(6):
                u = (j - 2.5) * w * .146
                if h > .08:
                    cloud(foot, (x + u, y + a * (d / 2 + .009), z), .095, p.stone, rotation=j * .64)
    foot.finish('宁寿门 · 铜狮须弥座' + ('东' if sign > 0 else '西'), target, bevel=.007)
    z = .414
    g = p.lion_gold
    # Overlapping solids form the carved breast, upright forelegs and crouched haunches.
    for u, v, h, sx, sy, sz in ((0, .068, .265, .209, .210, .266), (0, -.068, .414, .172, .141, .199),
                                (0, -.113, .559, .194, .157, .166), (.111, .113, .119, .117, .172, .133),
                                (-.111, .113, .119, .117, .172, .133), (0, -.225, .458, .141, .114, .077),
                                (0, -.250, .522, .118, .104, .060), (0, -.183, .365, .103, .094, .121)):
        body.ellipsoid((x+u, y+v, z+h), (sx, sy, sz), g, sides=26, rings=16)
    for a in (-1, 1):
        body.ellipsoid((x+a*.119, y-.126, z+.196), (.069, .094, .163), g, sides=22, rings=13)
        body.ellipsoid((x+a*.132, y-.226, z+.053), (.084, .123, .054), g, sides=22, rings=12)
        body.ellipsoid((x+a*.158, y-.085, z+.653), (.057, .047, .069), g, sides=20, rings=12)
        body.ellipsoid((x+a*.073, y-.259, z+.519), (.064, .063, .044), g, sides=22, rings=12)
    sculpture = body.finish('宁寿门 · 铜狮铸体 ' + ('东' if sign > 0 else '西'), target,
                            properties={'documented_subject': 'gilt bronze lion', 'sculpture_inferred': True})
    modifier = sculpture.modifiers.new('连续铸体表面', 'REMESH')
    modifier.mode, modifier.voxel_size, modifier.use_smooth_shade = 'VOXEL', .005, True
    bpy.context.view_layer.update()
    baked = bpy.data.meshes.new_from_object(sculpture.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    raw = sculpture.data
    sculpture.modifiers.clear()
    sculpture.data = baked
    bpy.data.meshes.remove(raw)
    for a in (-1, 1):
        for j in range(4):
            u = x + a * .13 + (j - 1.5) * .033
            carving.ellipsoid((u, y-.323, z+.049), (.021, .033, .025), g, sides=13, rings=8)
        xx = x + a * .098
        yy, zz = y - .238, z + .581
        carving.ellipsoid((xx, yy+.009, zz), (.042, .033, .033), p.inset, sides=18, rings=9)
        carving.ellipsoid((xx, yy-.018, zz), (.022, .013, .020), g, sides=17, rings=8)
        carving.path([(xx + i*.019, yy - .009 + .004*i*i, zz+.036 - .009*i*i) for i in range(-2, 3)],
                     .011, g, sides=9)
        carving.path([(x+a*(.12+.022*i), y-.288+.015*i, z+.501-.032*i) for i in range(5)], .013, g, sides=9)
        for dx in (-.049, .049):
            a0 = math.pi * (.09 if dx > 0 else .91)
            carving.rod((x+dx, y-.309, z+.485), (x+dx+.009*math.cos(a0), y-.315, z+.457),
                        .0105, g, r1=.0038, sides=9)
    carving.ellipsoid((x, y-.311, z+.522), (.057, .031, .032), g, sides=22, rings=11)
    carving.path([(x + i*.024, y-.291+.004*i*i, z+.466 + .002*i*i) for i in range(-4, 5)],
                 .008, p.inset, sides=10)
    for row in range(4):
        zz = z + .418 + row * .081
        for j in range(9):
            t = .42 + (j + .45 * (row % 2)) * 2.28 / 9
            xx = x + .218 * math.cos(t)
            yy = y - .069 + .154 * math.sin(t)
            if row >= 2:
                xx = x + (xx - x) * (.94 if row == 2 else .72)
            carving.ellipsoid((xx, yy, zz), (.042, .041, .045), g, sides=14, rings=9)
            q = [(xx+.036*(1-.89*i/22)*math.cos(i*.34+t), yy+.034,
                  zz+.036*(1-.89*i/22)*math.sin(i*.34+t)) for i in range(23)]
            carving.path(q, .0065, g, sides=7)
    for a in (-1, 1):
        for j in range(7):
            zz = z + .311 + .034 * j
            carving.path([(x+a*(.137+i*.015), y-.162+i*.018, zz-.0033*i*i) for i in range(6)], .0068, g, sides=7)
    tail = [(x+sign*u, y+v, z+h) for u, v, h in ((.12,.195,.09),(.21,.23,.14),(.277,.16,.221),(.28,.10,.32),
                                                      (.251,.068,.427),(.211,.09,.472),(.184,.14,.464))]
    carving.path(tail, .023, g, sides=12)
    for i in range(5):
        carving.path([(x+sign*(.213+.014*i-.019*t), y+.116+.038*t, z+.462+.065*math.sin(t*2.1))
                      for t in (k/11 for k in range(12))], .011, g, sides=8)
    carving.finish('宁寿门 · 铜狮眉眼、牙爪、卷鬃与尾' + ('东' if sign > 0 else '西'), target)


def terrace(loc, target, p):
    group = collection('宁寿门 · 汉白玉台基、三出阶及中央丹陛', target)
    stone, rail, ramp = loc.batch(), loc.batch(), loc.batch()
    outline = box(-15.10, TERRACE_EDGE, 15.10, 5.62)
    for lo, hi, margin, mat in ((-.075, .164, .12, p.understone), (.164, .285, .064, p.stone),
                                (.285, .745, -.087, p.understone), (.745, .829, -.018, p.stone),
                                (.829, INNER_FLOOR - .046, .041, p.stone)):
        stone.solid_xy(outline.buffer(margin, join_style=2), lo, hi, mat, bottom=False)
    laid_pavers(stone, outline, INNER_FLOOR, p, course=.66, width=1.32)
    for x, w in STAIRS:
        for offset, run in (((-w * .325, w * .343), (w * .325, w * .343)) if x == 0 else ((0., w),)):
            stairs(stone, (x + offset, STAIR_TOE), (x + offset, TERRACE_EDGE + .08), run,
                   .025, INNER_FLOOR, p, handrails=False)
        for side in (-1, 1):
            lean = x + side * (w / 2 + .14)
            rail.beam((lean, STAIR_TOE + .30, .20), (lean, TERRACE_EDGE + .14, INNER_FLOOR + .28), .222, .197, p.stone)
            rail.beam((lean, STAIR_TOE + .30, .91), (lean, TERRACE_EDGE + .14, INNER_FLOOR + .86), .139, .116, p.stone)
            for j in range(4):
                t = j / 3
                y = STAIR_TOE + .30 + (TERRACE_EDGE - STAIR_TOE - .16) * t
                z = .055 + (INNER_FLOOR - .055) * t
                rail.box((lean, y, z + .44), (.19, .212, .79), p.stone)
                rail.lathe(lean, y, ((.118, z + .797), (.126, z + .821), (.101, z + .91), (.069, z + .982)), p.stone, sides=14)
    gap = 1.28
    face = [(-gap, STAIR_TOE + .03, .059), (gap, STAIR_TOE + .03, .059),
            (gap, TERRACE_EDGE - .03, INNER_FLOOR - .01), (-gap, TERRACE_EDGE - .03, INNER_FLOOR - .01)]
    ramp.face(face, p.stone)
    for side in (-1, 1):
        ramp.path([(side * gap, STAIR_TOE + .032, .064), (side * gap, TERRACE_EDGE - .03, INNER_FLOOR + .009)],
                  .050, p.stone, sides=8)
    for i in range(22):
        u = ((i * 7) % 13) / 15 - .39
        t = .04 + .91 * i / 22
        y = STAIR_TOE + t * (TERRACE_EDGE - STAIR_TOE)
        z = .073 + t * (INNER_FLOOR - .06)
        # Scrolls are built along the slope, rather than suspended above the stone.
        panel = Batch()
        cloud(panel, (u * 2.27, y, z), .42, p.stone, facing='down', rotation=i * .79)
        ramp.add([(x, yy, zz + (yy - y) * .228) for x, yy, zz in panel.v], panel.f, p.stone, smooth=True)
    stone.finish('宁寿门 · 石座和六级台阶', group, bevel=.006, properties={'floor_z_m': INNER_FLOOR, 'stair_runs': 3})
    ramp.finish('宁寿门 · 丹陛石与浮起卷云', group)
    ends = [-14.87]
    for x, w in STAIRS:
        ends.extend((x - w / 2 - .23, x + w / 2 + .23))
    ends.append(14.87)
    for a, b in zip(ends[::2], ends[1::2]):
        if b - a > .41:
            marble_rail(rail, ((a, TERRACE_EDGE + .16), (b, TERRACE_EDGE + .16)), INNER_FLOOR, p, step=1.55)
    for sign in (-1, 1):
        marble_rail(rail, ((sign * 14.87, TERRACE_EDGE + .16), (sign * 14.87, 5.43)), INNER_FLOOR, p)
        marble_rail(rail, ((sign * 14.87, 5.43), (sign * 4.04, 5.43)), INNER_FLOOR, p)
    rail.finish('宁寿门 · 透雕栏板与阶道望柱', group, bevel=.004)
    for sign in (-1, 1):
        gilt_guardian(loc, group, sign, p)


def shutters(loc, group, p):
    doors, windows, endwalls = loc.batch(), loc.batch(), loc.batch()
    glazing = SimpleNamespace(red=p.door)
    for side in (-1, 1):
        x = side * (XS[-1] + XS[-2]) * .5
        w = XS[-1] - XS[-2] - .46
        windows.box((x, YS[0], INNER_FLOOR + .484), (w, .342, .957), p.vermilion)
        windows.box((x, YS[0], INNER_FLOOR + .959), (w + .034, .385, .116), p.door)
        for i in range(4):
            tx, bw = x + (i - 1.5) * w / 4, w / 4
            frame(windows, tx, YS[0] - .047, 2.69, bw, 1.38, .049, p.window_gold)
            windows.box((tx, YS[0] + .061, 2.69), (bw - .071, .037, 1.27), p.inset)
            lattice(windows, tx, YS[0] - .074, 2.044, bw - .071, 1.286, glazing)
            frame(windows, tx, YS[0] - .053, 3.63, bw, .429, .043, p.window_gold)
            for j in range(1, 9):
                xx = tx + ((j / 9) - .5) * bw
                windows.box((xx, YS[0] - .043, 3.63), (.023, .046, .337), p.door)
            for off in (-.073, .073):
                windows.box((tx, YS[0] - .044, 3.63 + off), (bw - .067, .038, .022), p.door)
        for y in (YS[-1], YS[2]):
            endwalls.box((x, y, (INNER_FLOOR + 5.68) / 2), (w + .071, .211, 5.68 - INNER_FLOOR), p.vermilion)
            frame(endwalls, x, y - .112, (INNER_FLOOR + 5.68) / 2, w + .055, 5.68 - INNER_FLOOR - .025,
                  .103, p.faded_teal)
        for lo, hi in zip(YS, YS[1:]):
            endwalls.box((side * XS[-1], (lo + hi) / 2, (INNER_FLOOR + 5.89) / 2),
                         (.381, hi - lo - .081, 5.89 - INNER_FLOOR), p.vermilion)
    for i, (left, right) in enumerate(zip(XS[1:-2], XS[2:-1])):
        w = right - left - .55
        mid, y = (left + right) / 2, YS[2]
        # Three rear gate bays; the principal pair is open in the tour scene.
        for side in (-1, 1):
            t = Batch()
            hinge = mid + side * w / 2
            tx, h = -side * w / 4, 3.21
            t.box((tx, 0, INNER_FLOOR + .10 + h / 2), (w / 2 - .027, .144, h), p.door)
            frame(t, tx, -.084, INNER_FLOOR + .11 + h * .52, w * .45, h * .93, .043, p.window_gold)
            for r in range(9):
                for c in range(6):
                    t.ellipsoid((tx + (c - 2.5) * w * .068, -.078, INNER_FLOOR + .35 + r * .33),
                                (.031, .022, .032), p.bronze, sides=8, rings=4)
            transfer(doors, t, hinge, y, -side * math.radians(86.5) if i == 1 else 0.)
        doors.box((mid, y, 4.485), (w + .07, .259, .437), p.door)
        frame(doors, mid, y - .134, 4.485, w - .063, .319, .025, p.window_gold)
        endwalls.box((mid, y, 5.07), (right - left - .31, .26, .755), p.fascia)
        painted_bay(endwalls, mid, y - .154, 5.08, right - left - .38, p, height=.37)
    for y in (*YS[1:], YS[0]):
        for j, (lo, hi) in enumerate(zip(XS, XS[1:])):
            if y == YS[0] and j in (1, 2, 3):
                windows.box(((lo + hi) / 2, y, 4.78), (hi - lo - .34, .331, .256), p.fascia)
    windows.finish('宁寿门 · 两梢间四扇菱花槛窗和方格风窗', group,
                   properties={'front_open_bays': 3, 'lattice_leaves': 8})
    doors.finish('宁寿门 · 后金柱明间开启及次间门扇', group, properties={'rear_door_bays': 3})
    endwalls.finish('宁寿门 · 梢间墙与山墙', group)


def splayed_screen(loc, target, p, sign):
    start = Vector((sign * 13.79, -3.56))
    middle = Vector((sign * 17.83, -3.56))
    tip = Vector((sign * 26.61, -8.56))
    group = collection(('东' if sign > 0 else '西') + '八字琉璃影壁', target)
    group['screen_side'] = sign
    group['plan_shape'] = 'splayed'
    for n, (a, b) in enumerate(((start, middle), (middle, tip))):
        point = (a + b) * .5
        length = (b - a).length
        direction = math.atan2((b - a).y, (b - a).x)
        if sign < 0:
            direction -= math.pi
        h = 3.34 if n == 0 else 4.07
        block = Batch(loc.world(point.x, point.y), loc.yaw + direction)
        block.box((0, 0, h / 2), (length + .059, .693, h), p.vermilion)
        for z, step, height in ((.144, .25, .288), (.319, .172, .063), (.487, .099, .284), (.653, .18, .047)):
            block.box((0, 0, z), (length + .1 + step, .693 + step, height), p.stone)
        block.box((0, -.341, h - .379), (length - .14, .072, .302), p.glaze_green)
        block.box((0, -.364, h - .552), (length - .14, .068, .051), p.glaze_yellow)
        for py in (-1, 1):
            for x in (-length / 2 + .17, length / 2 - .17):
                block.box((x, py * .369, (h - .16) / 2), (.162, .064, h - .81), p.glaze_yellow)
            centers = [(-length * .23, .65), (length * .23, .76)] if n else [(0., .58)]
            for x, r in centers:
                y = py * .364
                z = 1.84 if n == 0 else 2.05
                block.rod((x, y - py * .026, z), (x, y + py * .041, z), r, p.glaze_green, sides=44)
                rim = [(x + r * math.cos(t), y + py * .050, z + r * math.sin(t)) for t in (i * math.tau / 60 for i in range(61))]
                block.path(rim, .029, p.glaze_yellow, sides=7)
                for i in range(14):
                    a0 = i * math.tau / 14
                    rr = r * (.45 + .21 * (i % 2))
                    cloud(block, (x + rr * math.cos(a0), y + py * .067 + .015, z + rr * math.sin(a0)),
                          .30 * r, p.glaze_yellow if i % 3 == 0 else p.glaze_blue, rotation=a0 + .7)
                for i in range(8):
                    a0 = i * math.tau / 8
                    block.ellipsoid((x + .21 * r * math.cos(a0), y + py * .064, z + .21 * r * math.sin(a0)),
                                    (.14 * r, .058, .10 * r), p.glaze_green, sides=10, rings=5)
        block.finish('影壁 · 砖身、石座、釉面额枋与圆光', group, bevel=.005)
        swept_roof('影壁瓦帽', group, p, origin=loc.world(point.x, point.y), yaw=loc.yaw + direction,
                   width=length + .42, depth=1.22, eave=h + .014, rise=.39, kind='gable', tiles=True,
                   pitch=.184, beasts=0, ridge_terminals=False, detail=1, soffit=False)


def axial_approach(site, loc, target, p):
    group = collection('宁寿门前后 · 御路与两院衔接', target)
    yard, raised = loc.batch(), loc.batch()
    footprint = local_shape(site.geom('42310573'), loc)
    footprint = footprint.difference(box(-15.22, TERRACE_EDGE - .02, 15.22, 5.68))
    pave(yard, footprint, p, road_width=4.27)
    approach = box(-3.95, 5.40, 3.95, 49.20)
    raised.solid_xy(approach, .001, INNER_FLOOR - .054, p.understone, bottom=False)
    laid_pavers(raised, approach, INNER_FLOOR, p, course=.78, width=1.02)
    for side in (-1, 1):
        marble_rail(raised, ((side * 3.82, 5.39), (side * 3.82, 49.13)), INNER_FLOOR, p, step=1.86)
    yard.finish('宁寿门前 · 砖墁、石芯路与砖缝', group, bevel=.002)
    raised.finish('宁寿门后 · 连至皇极殿前的高台甬路', group, properties={'floor_z_m': INNER_FLOOR, 'shape_inferred': True})


def build_inner_gate(site, target, base):
    x, y, width, depth, yaw = rectangle(site.geom(INNER_ID))
    loc = Location(x, y, yaw)
    p = palette(base)
    group = collection('宁寿门 · 五间歇山和白石丹陛', target)
    group['museum_source'] = INNER_SOURCE
    group['source_osm_id'] = INNER_ID
    terrace(loc, group, p)
    timber, brackets = loc.batch(), loc.batch()
    for xi in XS:
        for yi in YS:
            column(timber, xi, yi, INNER_FLOOR, EAVE - (.58 if yi in (YS[0], YS[-1]) else .37),
                   .318 if abs(xi) < 8.7 else .288, p)
    for yi, sign in ((YS[0], -1), (YS[-1], 1)):
        for a, b in zip(XS, XS[1:]):
            painted_bay(brackets, (a + b) / 2, yi, EAVE - 1.062, b - a - .11, p, height=.47)
            for j in range(4):
                xx = a + (j + .38) * (b - a) / 4
                dougong(brackets, xx, yi, EAVE - .856, p, scale=.65, direction=(0, sign))
    for side in (-1, 1):
        for a, b in zip(YS, YS[1:]):
            painted_bay(brackets, side * XS[-1], (a + b) / 2, EAVE - 1.055, b - a - .04, p, yaw=math.pi / 2, height=.48)
    for x in XS:
        timber.beam((x, YS[0], 5.47), (x, YS[-1], 5.47), .355, .447, p.door)
    for x0, x1 in zip(XS, XS[1:]):
        for yy in (YS[1], YS[2]):
            timber.beam((x0, yy, 5.75), (x1, yy, 5.75), .322, .41, p.faded_teal)
    timber.finish('宁寿门 · 六缝四列减缩柱头及穿梁', group, bevel=.007,
                  properties={'column_rows': 4, 'column_lines': 6, 'columns': 24, 'surveyed': False})
    brackets.finish('宁寿门 · 重作和玺彩画题材、斗栱与额枋', group, bevel=.004)
    shutters(loc, group, p)
    swept_roof('宁寿门 · 单檐黄瓦歇山', group, p, origin=loc.world(), yaw=loc.yaw,
               width=width, depth=depth, eave=EAVE, rise=3.04, kind='xieshan', tiles=True,
               pitch=.236, beasts=5, detail=2, eave_lift=.43, terminal_height=1.22, ridge_length=width * .74)
    for sign in (-1, 1):
        splayed_screen(loc, group, p, sign)
    axial_approach(site, loc, target, p)
    return loc, {'source': INNER_SOURCE, 'map_way': INNER_ID, 'map_envelope_m': [width, depth],
                 'documented_form': {'width_bays': 5, 'depth_bays': 3, 'front_open_bays': 3,
                                     'roof': 'xieshan', 'stair_runs': 3, 'side_screens': 2, 'gilt_lions': 2},
                 'estimated_sections': {'terrace_z_m': INNER_FLOOR, 'eave_z_m': EAVE, 'column_lines_m': XS,
                                        'column_rows_m': YS, 'stair_toe_y_m': STAIR_TOE}}
