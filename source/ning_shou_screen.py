"""Nine Dragons Screen: photo-registered color over solid, editable glazed blocks."""
import json
import math
from pathlib import Path
from types import SimpleNamespace

import bpy
import numpy as np
from mathutils import Vector
from shapely.geometry import Polygon

from carved_ornament import cloud
from mesh_tools import Batch, collection
from palace_architecture import arch_mesh
from palace_materials import paint
from qinan_survey import Location


REFS = Path(__file__).resolve().parent / 'references' / 'ning_shou_court'
SCREEN_SOURCE = 'https://www.dpm.org.cn/explore/building/236477.html'
SCREEN_ID = '41661995'
LENGTH, HEIGHT, BODY, RELIEF = 29.4, 3.5, .45, .20
FIELD_W, FIELD_LOW, FIELD_HIGH = 28.83, .463, 2.695
FIELD_H = FIELD_HIGH - FIELD_LOW
GRID_PITCH = .00895
FACE_Y = -BODY / 2
RAIL_Y = -1.24


def location(site):
    points = site.points(SCREEN_ID)
    a, b = points[0], points[-1]
    # Looking south from the court, the viewer's left is geographic east.
    return Location((a[0] + b[0]) / 2, (a[1] + b[1]) / 2,
                    math.atan2(a[1] - b[1], a[0] - b[0]))


def palette(base):
    p = SimpleNamespace(**base.__dict__)
    p.vermilion = paint('宁寿宫 · 风化朱砂灰泥', (.215, .032, .020),
                        second=(.405, .068, .042), scale=.34, rough=.83, grain=73, bump=.010)
    p.brick = paint('宁寿宫 · 青砖下碱', (.19, .174, .151),
                    second=(.34, .316, .273), scale=1.4, rough=.86, bump=.007,
                    brick=(.45, .133, .005, True))
    p.stone = paint('宁寿宫 · 磨蚀青白石', (.34, .312, .267),
                    second=(.59, .556, .49), scale=3.8, rough=.78, grain=159, bump=.004)
    p.cleanstone = paint('九龙壁 · 石栏冷白与石英纹', (.423, .413, .39),
                         second=(.71, .70, .656), scale=4.6, rough=.77, grain=182, bump=.0032)
    p.glaze_green = paint('宁寿宫 · 老绿釉', (.025, .100, .061),
                          second=(.086, .249, .156), scale=8, rough=.42, coat=.19, bump=.003)
    p.glaze_blue = paint('宁寿宫 · 青蓝釉', (.024, .074, .092),
                         second=(.081, .190, .219), scale=6.7, rough=.43, coat=.17, bump=.003)
    p.glaze_yellow = paint('宁寿宫 · 风化黄釉', (.31, .128, .023),
                           second=(.61, .331, .069), scale=9.8, rough=.37, coat=.19, bump=.0023)
    p.clay = paint('宁寿宫 · 灰釉胎及缝内沉积', (.093, .061, .036),
                   second=(.176, .115, .068), scale=22, rough=.86, bump=.0032)
    p.glaze = [paint(f'宁寿宫 · 黄琉璃窑变 {j + 1}', color,
                     second=tuple(v * 1.35 for v in color), scale=13.7, rough=.29 + .031 * j,
                     coat=.23, grain=95, bump=.0018) for j, color in enumerate(
                         ((.366, .153, .029), (.49, .221, .048), (.40, .177, .031),
                          (.414, .200, .046), (.316, .131, .031)))]
    p.field = paint('九龙壁 · 老琉璃与残存釉面', (.062, .160, .194),
                    rough=.45, coat=.14, grain=245, bump=.0011)
    atlas = REFS / 'nine_dragons_calibrated.jpg'
    im = bpy.data.images.load(str(atlas), check_existing=True)
    im['source_url'] = SCREEN_SOURCE
    im['local_reference_method'] = 'Nine oblique photographs registered to the panel plane; retained for local visual comparison.'
    im.pack()
    nodes = p.field.node_tree.nodes
    links = p.field.node_tree.links
    uv = nodes.new('ShaderNodeUVMap'); uv.uv_map = 'Roof UV'
    texture = nodes.new('ShaderNodeTexImage'); texture.image = im; texture.extension = 'EXTEND'
    links.new(uv.outputs['UV'], texture.inputs['Vector'])
    surface = nodes.get('Principled BSDF')
    links.new(texture.outputs['Color'], surface.inputs['Base Color'])
    glaze = nodes.new('ShaderNodeMapRange')
    glaze.inputs['From Min'].default_value = .035
    glaze.inputs['From Max'].default_value = .62
    glaze.inputs['To Min'].default_value = .61
    glaze.inputs['To Max'].default_value = .31
    links.new(texture.outputs['Color'], glaze.inputs['Value'])
    links.new(glaze.outputs['Result'], surface.inputs['Roughness'])
    p.court_paver = paint('宁寿宫 · 院砖颗粒、风化和水痕', (.177, .165, .144),
                          second=(.301, .286, .257), scale=3.9, rough=.91, grain=160, bump=.0039)
    p.path_stones = [paint(f'宁寿宫 · 石御路 {i + 1}', colors[0], second=colors[1],
                           scale=2.5 + i * .69, rough=.85, grain=147, bump=.0031)
                     for i, colors in enumerate((((.255, .233, .207), (.471, .445, .397)),
                                                 ((.239, .217, .185), (.405, .379, .337)),
                                                 ((.272, .258, .227), (.416, .388, .333)),
                                                 ((.197, .182, .164), (.396, .364, .324))))]
    return p


def ceramic_blocks(loc, target, p, registration):
    with np.load(REFS / 'nine_dragons_height.npz', allow_pickle=False) as fixture:
        heights = fixture['relief']
    rows, cols = heights.shape
    joints = [.0, .196, .399, .603, .801, 1.]
    head = registration['central_face_joint_controls']
    for row, (bottom, top) in enumerate(zip(joints, joints[1:])):
        group = collection(f'第 {row + 1} 层 · 单独可编辑的琉璃塑块', target)
        edges = np.linspace(0., 1., 55)
        edges[1:-1] += np.sin(np.arange(1, 54) * 1.74 + row * .96) * .0017
        head_index = None
        if row + 1 == head['course_from_bottom']:
            a, b = head['atlas_u']
            head_index = round((a + b) / 2 * 54 - .5)
            i = head_index
            edges[i-2:i+4] = np.interp(np.arange(i-2, i+4), (i-3, i, i+1, i+4),
                                       (edges[i-3], a, b, edges[i+4]))
        for col, (left, right) in enumerate(zip(edges, edges[1:])):
            gap = .0010
            nx = math.ceil(((right - left) * FIELD_W - 2 * gap) / GRID_PITCH) + 1
            nz = math.ceil(((top - bottom) * FIELD_H - 2 * gap) / GRID_PITCH) + 1
            us = np.linspace(left + gap / FIELD_W, right - gap / FIELD_W, nx)
            vs = np.linspace(bottom + gap / FIELD_H, top - gap / FIELD_H, nz)
            u, v = np.meshgrid(us, vs)
            sx, sz = u * (cols - 1), (1 - v) * (rows - 1)
            ix, iz = np.floor(sx).astype(int), np.floor(sz).astype(int)
            dx, dz = sx - ix, sz - iz
            depth = ((1 - dz) * ((1 - dx) * heights[iz, ix] + dx * heights[iz, ix + 1])
                     + dz * ((1 - dx) * heights[iz + 1, ix] + dx * heights[iz + 1, ix + 1]))
            taper = np.minimum(np.minimum((u - us[0]) * FIELD_W, (us[-1] - u) * FIELD_W),
                               np.minimum((v - vs[0]) * FIELD_H, (vs[-1] - v) * FIELD_H))
            depth *= .975 + .025 * np.minimum(taper / .008, 1)
            points = list(zip(((u.ravel() - .5) * FIELD_W).tolist(), (FACE_Y - depth.ravel()).tolist(),
                              (FIELD_LOW + v.ravel() * FIELD_H).tolist()))
            uv = list(zip(u.ravel().tolist(), v.ravel().tolist()))
            width, height = len(us), len(vs)
            faces = [(i, i + 1, i + width + 1, i + width) for r in range(height - 1)
                     for c in range(width - 1) for i in (r * width + c,)]
            perimeter = (list(range(width)) + [r * width + width - 1 for r in range(1, height)]
                         + [(height - 1) * width + c for c in range(width - 2, -1, -1)]
                         + [r * width for r in range(height - 2, 0, -1)])
            batch = loc.batch()
            batch.add(points, faces, p.field, uv=uv, smooth=True)
            back_start = len(batch.v)
            count = len(perimeter)
            back = [(points[i][0], FACE_Y + .046, points[i][2]) for i in perimeter]
            batch.add(back, [tuple(reversed(range(count)))], p.clay)
            for j, k in enumerate(perimeter):
                nxt = (j + 1) % count
                batch.f.append((perimeter[nxt], k, back_start + j, back_start + nxt))
                batch.mi.append(batch.slots[p.clay]); batch.sm.append(False); batch.ids.append(0); batch.uv.append(None)
            batch.finish(f'九龙壁 · 琉璃塑块 {row + 1:02d}-{col + 1:02d}', group, properties={
                'assembly': 'nine_dragon_tile', 'row': row + 1, 'course_position': col + 1,
                'source_osm_id': SCREEN_ID, 'relief_max_m': float(depth.max()),
                'front_grid_shape': [nz, nx], 'front_grid_pitch_target_m': GRID_PITCH,
                'joint_evidence': 'central head boundaries registered from screen_06' if col == head_index else 'inferred course grid'})


def glazed_bracket(batch, x, y, z, p, *, scale=1., steps=3):
    def point(u, v):
        return (x + u * scale, z + v * scale)
    for level in range(steps):
        w = .092 + .064 * level
        h = .066 * level
        depth = (.135 + .042 * level) * scale
        profile = Polygon([point(-w * .62, h - .029), point(w * .62, h - .029),
                           point(w * .83, h - .018), point(w, h + .015), point(w, h + .043), point(-w, h + .043),
                           point(-w, h + .015), point(-w * .83, h - .018)])
        part = Batch()
        arch_mesh(part, profile, depth, p.glaze_green if level != 1 else p.glaze_blue)
        batch.add([(u, v + y - .018 * level * scale, zt) for u, v, zt in part.v], part.f, part.mats[0])
        batch.box((x, y - depth / 2 - (.018 * level + .005) * scale, z + (h + .024) * scale),
                  (2 * w * scale, .012 * scale, .012 * scale), p.glaze_yellow)
    batch.box((x, y - .112 * scale, z + .137 * scale), (.046 * scale, .062 * scale, .171 * scale), p.glaze_green)


def carving_rails(loc, target, p):
    base, rail = loc.batch(), loc.batch()
    for z, w, d, h in ((.047, 29.55, .69, .103), (.135, 29.47, .63, .071), (.224, 29.35, .54, .115),
                      (.324, 29.44, .62, .090), (.407, 29.46, .67, .078)):
        base.box((0, .007, z), (w, d, h), p.stone)
    for j in range(196):
        x = -14.61 + j * .1495
        base.ellipsoid((x, -.293, .229), (.067, .047, .061), p.cleanstone, sides=10, rings=6)
        if j % 2 == 0:
            cloud(base, (x, -.308, .335), .128, p.stone, rotation=(j % 3) * .47)
    base.finish('九龙壁 · 须弥座、石英质石料与莲瓣浅刻', target, bevel=.008)
    n, span = 21, 31.32
    for j in range(n + 1):
        x = -span / 2 + j * span / n
        rail.box((x, RAIL_Y, .065), (.325, .32, .104), p.stone)
        rail.box((x, RAIL_Y, .359), (.209, .185, .590), p.cleanstone)
        rail.box((x, RAIL_Y, .665), (.215, .186, .157), p.cleanstone)
        rail.ellipsoid((x, RAIL_Y, .735), (.11, .097, .048), p.cleanstone, sides=14, rings=6)
        for k in range(4):
            cloud(rail, (x + (.038 if k % 2 else -.038), RAIL_Y - .090, .631 + k * .028),
                  .084, p.cleanstone, rotation=k * 1.25)
        if j == n:
            continue
        width = span / n
        center = x + width / 2
        rail.box((center, RAIL_Y, .045), (width - .17, .257, .088), p.stone)
        rail.box((center, RAIL_Y, .215), (width - .195, .13, .291), p.cleanstone)
        rail.box((center, RAIL_Y, .375), (width - .195, .155, .052), p.cleanstone)
        rail.box((center, RAIL_Y, .572), (width - .173, .152, .068), p.cleanstone)
        for delta in (-.43, 0., .43):
            xx = center + delta
            rail.ellipsoid((xx, RAIL_Y, .473), (.137, .070, .078), p.cleanstone, sides=13, rings=7)
            rail.lathe(xx, RAIL_Y, ((.081, .371), (.063, .403), (.046, .441), (.070, .467)), p.cleanstone, sides=12)
            cloud(rail, (xx, RAIL_Y - .075, .475), .159, p.cleanstone, rotation=1.5)
        for z in (.120, .306):
            rail.rod((center - .541, RAIL_Y - .066, z), (center + .541, RAIL_Y - .066, z), .010, p.cleanstone, sides=5)
    rail.finish('九龙壁 · 透空栏板、团花望柱与地栿', target, bevel=.005,
                properties={'rail_bays': n, 'spacing_source': 'photograph estimate'})


def dragon_crest(loc, target, p):
    band, design = loc.batch(), loc.batch()
    centers = [(i - 4) * 2.91 for i in range(9)]
    for sign in (-1, 1):
        for i in range(53):
            x = -13.32 + i * .512
            band.box((x, sign * .089, 3.381), (.508, .112, .176), p.glaze_yellow)
            cloud(design, (x, sign * .156, 3.399), .159, p.glaze_yellow, rotation=i * 1.66)
    for i, x in enumerate(centers):
        pose = -1 if i > 4 else 1
        y = -.181
        if i == 4:
            pts = [(x + .56 * math.sin(a), y, 3.392 + .044 * math.cos(a * 2)) for a in np.linspace(-1.54, 1.54, 23)]
        else:
            pts = [(x + pose * (.84 * t - .42), y, 3.392 + .049 * math.sin(t * math.tau * 1.23)) for t in np.linspace(0, 1, 28)]
        design.path(pts, .024, p.glaze_green, sides=9)
        head = (x, y - .021, 3.451) if i == 4 else pts[-1]
        design.ellipsoid(head, (.053, .029, .044), p.glaze_green, sides=12, rings=7)
        for j, point in enumerate(pts[3::4]):
            xx, yy, zz = point
            k = -1 if j % 2 else 1
            design.path([(xx, yy, zz), (xx - pose * .073, yy - .012, zz + k * .026),
                         (xx - pose * .115, yy, zz + k * .055)], .012, p.glaze_green, sides=6)
        for k in (-1, 1):
            xx, yy, zz = head
            design.path([(xx + k * .024, yy, zz), (xx + k * .050, yy, zz + .023),
                         (xx + k * .060, yy, min(3.49, zz + .038))], .008, p.glaze_green, sides=6)
    band.finish('九龙壁 · 黄釉正脊底板', target)
    design.finish('九龙壁 · 正脊中坐龙与两侧八行龙', target, properties={'crest_dragons': 9, 'relief_inferred': True})


def eaves(loc, target, p):
    group = collection('九龙壁 · 仿木琉璃斗栱与庑殿顶', target)
    brackets, edging, roof = loc.batch(), loc.batch(), loc.batch()
    for z, h, material in ((.445, .051, p.glaze_yellow), (2.703, .041, p.glaze_yellow),
                           (2.774, .102, p.glaze_green), (2.838, .021, p.glaze_yellow),
                           (3.011, .052, p.glaze_green)):
        edging.box((0, -.004, z), (29.43, .60, h), material)
    for side in (-1, 1):
        edging.box((side * (FIELD_W / 2 + .129), -.019, (FIELD_LOW + FIELD_HIGH) / 2),
                   (.243, .494, FIELD_HIGH - FIELD_LOW), p.glaze_yellow)
    for i in range(46):
        x = (i - 22.5) * .628
        glazed_bracket(brackets, x, -.276, 2.874, p, scale=.71, steps=3)
        if i < 45:
            mid = x + .314
            roof.box((mid, -.280, 2.922), (.354, .070, .139), p.glaze_green)
            cloud(roof, (mid, -.326, 2.910), .118, p.glaze_yellow, rotation=i * .13)
            cloud(roof, (mid + .050, -.328, 2.94), .083, p.glaze_green, rotation=1.3)
    edging.finish('九龙壁 · 黄釉边框、檐枋和隔层', group)
    brackets.finish('九龙壁 · 仿木琉璃构件逐组分层', group)
    roof.finish('九龙壁 · 45 块垫栱板及浮起纹样', group, properties={'frieze_blocks': 45})

    # At this small scale the ridge has its own nine-dragon crest, so the shell
    # and ceramic courses end below the documented 3.50 m envelope.
    shell, tiles = loc.batch(), loc.batch()
    half_w, half_d, trunc = 14.93, .708, .63
    def point(x, t, side):
        return Vector((x, side * half_d * (1 - t), 3.014 + .268 * t**1.47 + .047 * (abs(x) / half_w)**18 * (1 - t)**2))
    for side in (-1, 1):
        for i in range(11):
            a, b = i / 11, (i + 1) / 11
            left, right = half_w - trunc * a, half_w - trunc * b
            quad = [point(-left, a, side), point(left, a, side), point(right, b, side), point(-right, b, side)]
            shell.face(quad if side < 0 else quad[::-1], p.clay)
        for k in range(192):
            x = -half_w + (k + .5) * 2 * half_w / 192
            end = min(.997, (half_w - abs(x)) / trunc)
            if end < .10:
                continue
            for j in range(3):
                t0, t1 = j * end / 3, min(end, (j + 1.08) * end / 3)
                rows = []
                for t in (t0, (t0 + t1) / 2, t1):
                    center = point(x, t, side)
                    rows += [tuple(center + Vector((.052 * math.cos(a), 0., .018 + .054 * math.sin(a))))
                             for a in (m * math.pi / 8 for m in range(9))]
                faces = [(r * 9 + m, r * 9 + m + 1, (r + 1) * 9 + m + 1, (r + 1) * 9 + m)
                         for r in range(2) for m in range(8)]
                tiles.add(rows, faces if side > 0 else [f[::-1] for f in faces], p.glaze[(k * 7 + j * 3) % 5], smooth=True)
                pan = [tuple(point(x + u, t, side) + Vector((0, 0, z))) for t in (t0, t1)
                       for u, z in ((.032, .024), (.077, .008), (.124, .022))]
                faces = [(0, 1, 4, 3), (1, 2, 5, 4)]
                tiles.add(pan, faces if side < 0 else [f[::-1] for f in faces], p.glaze[(k + j + 1) % 5], smooth=True)
            c = point(x, 0, side)
            axis = Vector((0, side, 0))
            c.z += .032
            tiles.rod(c - axis * .018, c + axis * .047, .045, p.glaze[k % 5], sides=16)
            for j in range(5):
                a = j * math.tau / 5
                tiles.ellipsoid(c + axis * .05 + Vector((.022 * math.cos(a), 0, .022 * math.sin(a))),
                                (.008, .005, .009), p.clay, sides=6, rings=4)
            z = c.z - .114
            tiles.box((x, side * .531, z), (.060, .278, .057), p.glaze_green)
    for sign in (-1, 1):
        shell.face([(sign * half_w, -.708, 3.06), (sign * half_w, .708, 3.06),
                    (sign * (half_w - trunc), 0, 3.282)][::sign], p.glaze[2])
        for side in (-1, 1):
            pts = [point(sign * (half_w - trunc * t), t, side) + Vector((0, 0, .065)) for t in np.linspace(0, 1, 21)]
            shell.path(pts, .048, p.glaze_yellow, sides=10)
    shell.finish('九龙壁 · 窄庑殿灰背和戗脊', group)
    tiles.finish('九龙壁 · 檐端瓦当、筒瓦、板瓦及仿木椽', group, properties={'roof_coverage': 'individual cap and pan tiles'})
    dragon_crest(loc, group, p)


def build_screen(site, target, base):
    loc = location(site)
    p = palette(base)
    group = collection('九龙壁 · 九龙琉璃与白石围栏', target)
    group['museum_source'] = SCREEN_SOURCE
    group['map_way'] = SCREEN_ID
    group['field_geometry'] = 'photo-constrained inference; 270 independent blocks'
    registration = json.loads((REFS / 'registration.json').read_text(encoding='utf-8'))
    body = loc.batch()
    body.box((0, 0, 1.505), (LENGTH, BODY, 3.01), p.clay)
    body.finish('九龙壁 · 29.4 米墙芯与灰缝', group,
                properties={'published_length_m': LENGTH, 'published_wall_height_m': HEIGHT, 'published_thickness_m': BODY})
    ceramic_blocks(loc, collection('九龙壁 · 五层 270 个独立琉璃塑块', group), p, registration)
    carving_rails(loc, group, p)
    eaves(loc, group, p)
    return loc, p, registration
