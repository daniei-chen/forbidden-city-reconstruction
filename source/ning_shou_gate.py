"""Huangji Gate's three vaulted openings and seven glazed rooflets."""
import math
from mathutils import Vector
from shapely.affinity import affine_transform
from shapely.geometry import box

from architectural_roofs import swept_roof, terminal
from carved_ornament import cloud
from garden_bridge_pavilions import transfer
from garden_context import old_cypress
from garden_cross_roofs import roof_panels, tile
from mesh_tools import Batch, collection, line_boxes
from ning_shou_screen import glazed_bracket
from osm_site import rectangle
from palace_architecture import arch_mesh, arch_section
from palace_materials import paint
from qinan_survey import Location


GATE_ID = '41661998'
GATE_SOURCE = 'https://www.dpm.org.cn/explore/building/236451.html'
GLAZED_GATES = 'https://img.dpm.org.cn/Uploads/pdf/2205/T00030_00.pdf'
ARCHIVES = 'https://img.dpm.org.cn/Uploads/File/2019/12/15/u5df60cf540978.pdf'
ARCHES = ((-7.12, 2.56, 3.53, 1.03), (0., 3.06, 4.01, 1.19), (7.12, 2.56, 3.53, 1.03))
WALL_TOP = 6.65
SILL = .087
EAST_WALL = '41657461'
BACK_RANGES = ('40591186', '40591187', '40591188')
COURT_REPLACEMENTS = {EAST_WALL, *BACK_RANGES, '41662000', '41662003'}


def arch_trim(loc, group, x, width, top, rise, depth, p):
    b = loc.batch()
    radius = width / 2
    spring = top - rise
    for side in (-1, 1):
        y = side * (depth / 2 + .016)
        for index in range(21):
            a, c = index * math.pi / 21 + .0035, (index + 1) * math.pi / 21 - .0035
            def ring(angle, delta):
                return (x + (radius + delta) * math.cos(angle), y,
                        spring + (rise + delta) * math.sin(angle))
            quad = [ring(a, 0.), ring(a, .118), ring(c, .118), ring(c, 0.)]
            b.face(quad if side < 0 else quad[::-1], p.vermilion)
        for sign in (-1, 1):
            b.box((x + sign * (radius + .058), y - side * .006, spring / 2 + .032),
                  (.115, .039, spring - .064), p.vermilion)
    b.finish('皇极门 · 券脸和拱脚', group, properties={'clear_width_m': width, 'crown_z_m': top})


def leaves(loc, target, index, x, w, h, rise, depth, p):
    radius = w / 2 - .058
    arch = arch_section(x, 2 * radius, h - .047, bottom=SILL + .022, rise=rise - .028)
    for sign in (-1, 1):
        pivot = x + sign * (radius - .061)
        bottom = SILL + .018
        half = arch.intersection(box(x + .013 if sign > 0 else x - radius - .02, bottom,
                                     x + radius + .02 if sign > 0 else x - .013, h + .01))
        panels, hardware = Batch(), Batch()
        arch_mesh(panels, half, .104, p.door)
        for row in range(9):
            z = bottom + .236 + row * ((h - bottom - .47) / 8)
            for column in range(8 if index == 1 else 7):
                dx = x + sign * (column + .52) * radius / (8 if index == 1 else 7)
                from shapely.geometry import Point
                if half.covers(Point(dx, z)):
                    hardware.ellipsoid((dx, -.062, z), (.025, .015, .024), p.bronze, sides=9, rings=5)
        for z in (.32, 1.41, 2.42):
            if z < h - rise - .035:
                panels.box((x + sign * radius / 2, .042, z), (radius - .064, .087, .069), p.door)
                hardware.rod((pivot, .050, z - .057), (pivot, .050, z + .057), .056, p.bronze, sides=12)
        pull = x + sign * .153
        hardware.ellipsoid((pull, -.062, 1.12), (.067, .024, .078), p.bronze, sides=12, rings=6)
        hardware.path([(pull + .056 * math.cos(a), -.088 - .020 * math.sin(a), 1.061 + .066 * math.sin(a))
                       for a in (i * math.tau / 24 for i in range(25))], .011, p.bronze, sides=7)
        hinge_y = depth * .08
        angle = -sign * math.radians(89.4) if index == 1 else 0
        posed = loc.batch()
        for piece in (panels, hardware):
            piece.v = [(xx - pivot, yy, zz) for xx, yy, zz in piece.v]
            transfer(posed, piece, pivot, hinge_y, angle)
        posed.finish(f'皇极门 · 第 {index + 1} 券门扇 {"东" if sign > 0 else "西"}', target, bevel=.009,
                     properties={'open_angle_deg': round(math.degrees(angle), 1), 'hinge_xy_m': [pivot, hinge_y]})


def lotus_post(b, x, y, z, scale, p):
    b.lathe(x, y, tuple((r * scale, z + h * scale) for r, h in (
        (.035, -.34), (.073, -.315), (.093, -.246), (.085, -.198), (.051, -.163),
        (.057, -.116), (.084, -.102), (.089, -.053), (.073, 0), (.065, .13))), p.glaze_yellow, sides=16)
    for j in range(8):
        a = j * math.tau / 8
        v = Vector((math.cos(a), math.sin(a), 0))
        c = Vector((x, y, z))
        b.path([c + v * (.045 * scale) + Vector((0, 0, -.315 * scale)),
                c + v * (.096 * scale) + Vector((0, 0, -.247 * scale)),
                c + v * (.052 * scale) + Vector((0, 0, -.174 * scale))], .0085 * scale, p.glaze[1], sides=6)


def hybrid_roof(loc, target, p, x, y, width, depth, eave, rise, outer):
    """A rooflet with a hanging gable toward the center and a hip outside."""
    shell, tiling, ridge = loc.batch(), loc.batch(), loc.batch()
    hx, hy, inset = width / 2, depth / 2, .59
    def position(u, t, side):
        left = -hx + (inset * t if outer < 0 else 0.)
        right = hx - (inset * t if outer > 0 else 0.)
        a = u if side else (1. if outer > 0 else 0.)
        yy = side if side else 2 * u - 1
        return Vector((x + left + (right - left) * a, y + yy * hy * (1 - t), eave + rise * (.16 * t + .84 * t**1.62)))
    for side in (-1, 1, 0):
        def surface(u, t):
            return position(u, t, side)
        end = .998 if not side else 1.
        roof_panels(shell, lambda u, t: surface(u, end * t), 14, 12, p.roof, p.clay)
        count = max(6, round((width if side else depth) / .19))
        for col in range(count):
            for cap in (True, False):
                u = (col + (.48 if cap else .96)) / count
                for j in range(4):
                    t0, t1 = j * end / 4, min(end, (j + 1.12) * end / 4)
                    def pitch(t):
                        return (width - inset * t) / count if side else depth * (1 - t) / count
                    tile(tiling, surface, u, t0, t1, end, pitch, p.glaze[(col + j) % 5], cap)
                if cap:
                    c = surface(u, 0) + Vector((0, 0, .031))
                    outward = Vector((0, side, 0)) if side else Vector((outer, 0, 0))
                    tiling.rod(c - outward * .012, c + outward * .053, pitch(0) * .337, p.glaze[1], sides=13)
        for border in (0., 1.):
            ridge.path([tuple(surface(border, t) + Vector((0, 0, .046))) for t in (i / 18 for i in range(19))],
                       .055, p.glaze_yellow, sides=8)
    gable = x - outer * hx
    outer_tip = x + outer * (hx - inset)
    shell.face([(gable, y - hy, eave), (gable, y, eave + rise), (gable, y + hy, eave)][::outer], p.glaze_green)
    ridge.beam((gable, y, eave + rise + .052), (outer_tip, y, eave + rise + .052), .178, .126, p.glaze_yellow)
    terminal(ridge, (outer_tip, y, eave + rise + .065), outer, .237, p.glaze_yellow, p)
    shell.finish('边楼 · 外侧庑殿、内侧悬山', target, properties={'roof_type': 'outer_hip_inner_gable'})
    tiling.finish('边楼 · 独立琉璃瓦和瓦当', target)
    ridge.finish('边楼 · 戗脊与正吻', target)


def rooflets(loc, target, depth, p):
    spec = ((-10.79, 1.97, 4.04, .433, '边楼'), (-7.12, 5.56, 4.39, .658, '次楼'),
            (-3.57, 1.77, 4.01, .391, '夹楼'), (0., 5.48, 4.85, .688, '正楼'),
            (3.57, 1.77, 4.01, .391, '夹楼'), (7.12, 5.56, 4.39, .658, '次楼'),
            (10.79, 1.97, 4.04, .433, '边楼'))
    for index, (x, width, eave, rise, label) in enumerate(spec):
        group = collection(f'皇极门 · {index + 1:02d} {label}', target)
        group['rooflet_index'] = index + 1
        group['role'] = label
        group['inferred_eave_z_m'] = eave
        b = loc.batch()
        front = -depth / 2 - .232
        for z, height, mat in ((eave - .672, .141, p.glaze_green), (eave - .495, .198, p.glaze_blue),
                               (eave - .154, .116, p.glaze_green)):
            b.box((x, front, z), (width * .87, .407, height), mat)
            for sign in (-1, 1):
                b.box((x, front - .205, z + sign * height * .424), (width * .87, .014, .018), p.glaze_yellow)
        num = round(width / .66)
        for j in range(num):
            dx = x + ((j + .5) / num - .5) * width * .83
            glazed_bracket(b, dx, front - .049, eave - .391, p, scale=.765 if width > 3 else .591,
                           steps=5 if label in ('次楼', '正楼') else 3)
            cloud(b, (dx, front - .213, eave - .501), .17, p.glaze_yellow, rotation=j * .26)
        for sign in (-1, 1):
            xx = x + width * .409 * sign
            lotus_post(b, xx, front - .073, eave - .594, .98 if width > 3 else .74, p)
            for j in range(3):
                cloud(b, (xx - sign * (.129 + .07 * j), front - .239, eave - .690 + j * .054),
                      .156, p.glaze_yellow, rotation=j * .85)
        b.finish('仿木琉璃枋、垂莲柱、斗栱和雀替', group, bevel=.003)
        roof_y = -depth / 2 - .198
        if label == '边楼':
            hybrid_roof(loc, group, p, x, roof_y, width, 1.49, eave, rise, -1 if x < 0 else 1)
        else:
            swept_roof(label, group, p, origin=loc.world(x, roof_y), yaw=loc.yaw, width=width,
                       depth=2.04 if width > 3 else 1.46, eave=eave, rise=rise,
                       kind='gable' if label == '夹楼' else 'hip', tiles=True, pitch=.20, beasts=0,
                       detail=2, terminal_height=.475, eave_lift=.119 if width > 3 else .039)
    return spec


def build_gate(site, target, p):
    x, y, width, depth, yaw = rectangle(site.geom(GATE_ID))
    loc = Location(x, y, yaw)
    group = collection('皇极门 · 三间七楼与砖券', target)
    group['museum_source'] = GATE_SOURCE
    group['osm_id'] = GATE_ID
    depth = min(3.21, depth)
    openings = [arch_section(cx, w, h, bottom=-.4, rise=r) for cx, w, h, r in ARCHES]
    outline = box(-width / 2, -.078, width / 2, WALL_TOP)
    for opening in openings:
        outline = outline.difference(opening)
    body = loc.batch()
    arch_mesh(body, outline, depth, p.vermilion)
    body.finish('皇极门 · 厚墙与贯通的三座砖券', group,
                properties={'map_width_m': width, 'solid_depth_m': depth, 'gate_openings': 3, 'source_osm_id': GATE_ID})
    stone = loc.batch()
    for lo, hi, size, material in ((-.06, .091, .59, p.brick), (.094, .189, .49, p.stone),
                                   (.19, .356, .32, p.cleanstone), (.356, .401, .39, p.stone)):
        plinth = box(-width / 2, lo, width / 2, hi)
        for opening in openings:
            plinth = plinth.difference(opening.buffer(.022))
        arch_mesh(stone, plinth, depth + size, material)
    for cx, w, _, _ in ARCHES:
        stone.box((cx, .026, SILL / 2), (w - .028, depth + 1.0, SILL), p.stone)
        for j in range(3):
            stone.box((cx, (j - 1) * 1.19, .036), (w - .057, 1.173, .078), p.cleanstone)
    stone.finish('皇极门 · 须弥座、门槛和甬路接石', group, bevel=.007)
    doors = collection('皇极门 · 门扇与铜件', group)
    for i, (cx, w, h, rise) in enumerate(ARCHES):
        arch_trim(loc, group, cx, w, h, rise, depth, p)
        leaves(loc, doors, i, cx, w, h, rise, depth, p)
    spec = rooflets(loc, collection('皇极门 · 七座琉璃门楼', group), depth, p)
    return loc, width, depth, spec


def court_edges(site, screen, gate, width, depth, target, p):
    group = collection('宁寿宫南端 · 夹墙、铺地与琉璃瓦口', target)
    wall, footing, cap = Batch(), Batch(), Batch()
    path = site.points('41662003')[::-1]
    ztop, gauge = 2.72, .63
    line_boxes(wall, path, .464, ztop, gauge, p.vermilion)
    line_boxes(footing, path, -.02, .463, gauge + .072, p.brick)
    line_boxes(cap, path, ztop - .082, ztop + .015, gauge + .32, p.glaze_green)
    for a, b in zip(path, path[1:]):
        delta = Vector(b) - Vector(a)
        length, yaw = delta.length, math.atan2(delta.y, delta.x)
        if length < .12:
            continue
        mid = tuple((Vector(a) + Vector(b)) / 2)
        swept_roof('九龙壁背墙 · 墙帽逐片瓦', group, p, origin=(*mid, 0.), yaw=yaw, width=length + .032,
                   depth=gauge + .43, kind='gable', eave=ztop, rise=.243, tiles=True, pitch=.195,
                   beasts=0, detail=1, ridge_terminals=False, gable_ends=False, soffit=False)
    wing_walls(site, gate, width, depth, group, p)
    wall.finish('院墙 · 九龙壁背墙', group)
    footing.finish('院墙 · 青砖下碱及散水石', group)
    cap.finish('院墙 · 檐下绿琉璃线', group)
    courtyard = gate.batch()
    outline = local_shape(site.geom('42310572'), gate).intersection(box(-65., -38., 65., -1.62))
    pave(courtyard, outline, p, road_width=3.91)
    courtyard.finish('皇极门前 · 石御路、立砖边带与错缝墁地', group, bevel=.002)
    bronze_vats(gate, group, p)
    backing_ranges(site, group, p)


def local_shape(shape, location):
    c, s = math.cos(location.yaw), math.sin(location.yaw)
    x, y = location.x, location.y
    return affine_transform(shape, (c, s, -s, c, -c*x - s*y, s*x - c*y))


def pave(batch, outline, p, *, road_width):
    """Named court polygons have real setts, two soldier courses and larger axial slabs."""
    xmin, ymin, xmax, ymax = outline.bounds
    edge = road_width / 2
    core = box(-edge, ymin - .1, edge, ymax + .1)
    full_road = box(-edge - .40, ymin - .1, edge + .40, ymax + .1)
    periphery = outline.difference(full_road)
    for j in range(math.ceil((ymax - ymin) / .295)):
        y = ymin + .295 * j
        for i in range(math.ceil((xmax - xmin) / .577) + 1):
            x = xmin + (i - .5 * (j % 2)) * .577
            if abs(x + .29) < edge - .53:
                continue
            piece = periphery.intersection(box(x + .0027, y + .0026, x + .574, y + .292))
            top = .019 + .0022 * math.sin((j * 221 + i * 97) * .172)
            batch.solid_xy(piece, -.028, top, p.court_paver, bottom=False)
    center = outline.intersection(core)
    for i in range(4):
        x = -edge + i * road_width / 4
        y = ymin - (i % 2) * .37
        for j in range(math.ceil((ymax - y) / 1.14)):
            yy = y + j * 1.14 + .13 * math.sin(j * 1.61 + i * .6)
            next_y = y + (j + 1) * 1.14 + .13 * math.sin((j + 1) * 1.61 + i * .6)
            piece = center.intersection(box(x + .0035, yy + .003, x + road_width/4 - .0035, next_y - .003))
            batch.solid_xy(piece, -.026, .023, p.path_stones[(i * 13 + j * 7) % len(p.path_stones)], bottom=False)
    for sign in (-1, 1):
        a, b = sorted((sign * edge, sign * (edge + .40)))
        for j in range(math.ceil((ymax - ymin) / .21)):
            yy = ymin + j * .21
            piece = outline.intersection(box(a + .003, yy + .003, b - .003, yy + .207))
            batch.solid_xy(piece, -.026, .021, p.court_paver, bottom=False)


def bronze_vats(gate, group, p):
    metal = paint('皇极门 · 铜水缸的黑褐表层与斑驳氧化', (.046, .035, .023),
                  second=(.137, .105, .062), scale=10.8, rough=.44, metal=.67, grain=162, bump=.0037)
    for side in (-1, 1):
        x, y = side * 3.76, -4.56
        cylinder, vessel = gate.batch(), gate.batch()
        cylinder.lathe(x, y, ((.65, .018), (.65, .065), (.58, .21), (.55, .241)), p.stone, sides=48)
        vessel.lathe(x, y, ((.303, .232), (.347, .259), (.417, .405), (.527, .620),
                            (.592, .857), (.615, 1.030), (.640, 1.052), (.644, 1.090),
                            (.626, 1.119), (.589, 1.119), (.570, 1.089), (.570, 1.010),
                            (.545, .827), (.492, .641), (.384, .429), (.297, .310)), metal, sides=80)
        for sign in (-1, 1):
            cx = x + sign * .588
            vessel.ellipsoid((cx, y, .863), (.046, .115, .122), metal, sides=18, rings=8)
            vessel.path([(cx + sign * (.033 + .045 * math.sin(a)), y + .098 * math.cos(a), .809 + .113 * math.sin(a))
                         for a in (i * math.tau / 32 for i in range(33))], .017, metal, sides=9)
        name = '东' if side > 0 else '西'
        cylinder.finish(f'皇极门 · {name}缸石墩', group)
        vessel.finish(f'皇极门 · {name}铜缸和耳环', group,
                      properties={'source': GATE_SOURCE, 'dimensions_inferred_from_photo': True, 'hollow_vessel': True})


def wing_walls(site, gate, width, depth, group, p):
    west_ref = '41662000'
    west = local_shape(site.geom(west_ref), gate)
    start, end = west.bounds[0], -width / 2
    west_outline = box(start, -depth / 2, end + .007, depth / 2)
    west_wall = gate.batch()
    west_wall.solid_xy(west_outline.buffer(.024, join_style=2), -.018, .463, p.brick, way=int(west_ref))
    west_wall.solid_xy(west_outline, .462, WALL_TOP, p.vermilion, way=int(west_ref))
    west_wall.finish('皇极门 · 西翼接墙', group,
                     properties={'reconstructed_osm_way': west_ref, 'section_dimensions_estimated': True})
    map_shape = local_shape(site.geom(EAST_WALL), gate)
    face = map_shape.intersection(box(0., -10., 67., 2.9))
    returning = map_shape.difference(face)
    stone, plaster = gate.batch(), gate.batch()
    for shape, h in ((face, WALL_TOP), (returning, 4.10)):
        stone.solid_xy(shape.buffer(.024, join_style=2), -.018, .463, p.brick, way=int(EAST_WALL))
        plaster.solid_xy(shape, .462, h, p.vermilion, way=int(EAST_WALL))
    data = {'reconstructed_osm_way': EAST_WALL, 'map_footprint_area_m2': map_shape.area,
            'return_y_max_m': map_shape.bounds[3], 'section_heights_estimated': True}
    stone.finish('东翼墙 · 青砖下碱及向北折返段', group, properties=data)
    plaster.finish('东翼墙 · 朱墙整条平面', group, properties=data)
    east_end = 60.72
    harmonized = gate.batch()
    harmonized.box(((start + east_end) / 2, 0., WALL_TOP - .041), (east_end - start, depth + .29, .091), p.glaze_green)
    harmonized.box(((start + east_end) / 2, 0., WALL_TOP - .171), (east_end - start, depth + .095, .026), p.glaze_yellow)
    harmonized.finish('皇极门 · 通长墙帽下的老绿釉线脚', group)
    swept_roof('皇极门 · 整面连续的黄琉璃顶', group, p,
               origin=gate.world((start + east_end)/2, .05), yaw=gate.yaw,
               width=east_end-start+.08, depth=depth+.59, kind='gable', eave=WALL_TOP, rise=.55,
               tiles=True, pitch=.205, beasts=0, detail=1, ridge_terminals=False, soffit=False)
    point = (60.48, 1.96)
    tip = (59.34, map_shape.bounds[3])
    yaw = gate.yaw + math.atan2(tip[1]-point[1], tip[0]-point[0])
    swept_roof('东翼墙 · 北返段院墙灰背', group, p,
               origin=gate.world((point[0]+tip[0])/2, (point[1]+tip[1])/2), yaw=yaw,
               width=math.dist(point, tip), depth=2.92, kind='gable', eave=4.10, rise=.38, tiles=False,
               pitch=.20, beasts=0, detail=1, ridge_terminals=False, soffit=False)


def backing_ranges(site, group, p):
    target = collection('九龙壁背后 · 缎衣库三段灰瓦屋面', group)
    for ref, eave, rise in zip(BACK_RANGES, (2.51, 2.51, 2.39), (1.14, 1.14, 1.02)):
        x, y, w, d, yaw = rectangle(site.geom(ref))
        loc = Location(x, y, yaw)
        shape = local_shape(site.geom(ref), loc)
        b = loc.batch()
        b.solid_xy(shape.buffer(-.30, join_style=2), -.015, eave, p.vermilion, way=int(ref))
        b.solid_xy(shape.buffer(-.23, join_style=2), -.018, .408, p.brick, way=int(ref))
        b.finish('缎衣库 · 依地图落位的矮墙', target,
                 properties={'reconstructed_osm_way': ref, 'estimated_eave_z_m': eave})
        swept_roof('缎衣库 · 灰瓦', target, p, origin=loc.world(), yaw=yaw, width=w, depth=d,
                   kind='gable', eave=eave, rise=rise, grey=True, tiles=True, pitch=.235,
                   beasts=0, detail=1, ridge_terminals=False)


def courtyard_trees(target, screen, gate, p):
    group = collection('宁寿宫前 · 实拍中的树冠与庭荫', target)
    p.bark = paint('宁寿宫 · 柏干裂皮', (.068, .048, .035), second=(.227, .181, .132),
                   scale=6.1, rough=.94, grain=95, bump=.013)
    p.cypress = [paint(f'宁寿宫 · 柏叶 {i+1}', color, rough=.68, grain=90, bump=.0015)
                 for i, color in enumerate(((.028, .057, .018), (.062, .101, .033), (.092, .126, .040), (.124, .142, .053)))]
    soil = paint('宁寿宫 · 植穴内的黄褐旧土', (.105, .075, .043), second=(.214, .173, .111),
                 scale=5.6, rough=.93, grain=62, bump=.009)
    specs = ((screen, -17.89, -2.80, 7.62, 4773, '九龙壁左侧庭柏'),
             (screen, 17.73, -2.43, 6.91, 4774, '九龙壁右侧庭柏'),
             (gate, -16.65, -4.46, 8.15, 4510, '皇极门西翼庭柏'),
             (gate, 16.92, -2.96, 8.24, 4511, '皇极门东翼庭柏'))
    for loc, x, y, h, seed, name in specs:
        old_cypress(group, loc, p, name, x, y, h, seed, branch_start=2)
        b = loc.batch()
        b.lathe(x, y, ((.62, .021), (.59, .060), (.39, .063)), soil, sides=32)
        b.finish(name+' · 植穴', group,
                 properties={'evidence': 'Canopies visible in the Palace Museum photos; positions and heights inferred.'})
    return [dict(name=name, xy_m=loc.world(x, y)[:2], height_model_m=h) for loc, x, y, h, _, name in specs]
