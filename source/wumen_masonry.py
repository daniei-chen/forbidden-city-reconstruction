"""Editable gate masonry, reversible virtual door poses, and missing galleries.

Documented: 12 m platform, 60.05 x 25 m hall, 61.97 x 27.97 m exposed
hall plinth, nine/five hall bays, thirteen-bay wings and three-bay connectors.
The inherited mapped platform and five gate routes are retained. Individual
brick modules, portal sections, hinges, wear and component heights are inferred.
"""
import math
from types import SimpleNamespace

import bpy
from shapely import affinity
from shapely.geometry import LineString, box

from mesh_tools import Batch, collection, polygons
from palace_architecture import arch_mesh, arch_section, hall

MAIN = (-1.94, -470.29)
PLATFORM = '638157005'
COURSES = ((-16.58, -470., 5.1, 6.65, 34., 0.),
           (-3.75, -470., 6.0, 7.45, 34., 0.),
           (9.96, -470., 5.1, 6.65, 34., 0.),
           (-53.5, -476., 5.0, 6.0, 42., 0.),
           (-46.6, -492.6, 4.9, 5.7, 18.2, math.pi / 2),
           (48.5, -476., 5.0, 6.0, 42., 0.),
           (41.6, -492.6, 4.9, 5.7, 18.2, math.pi / 2))
SOURCE = 'https://www.dpm.org.cn/explore/building/236454.html'
PLAN_SOURCE = 'https://img.dpm.org.cn/Uploads/pdf/2196/T00006_00.pdf'


def part(batch, name, target, role, **properties):
    return batch.finish('午门修订 · ' + name, target,
                        properties=dict(role=role, architectural_source=SOURCE,
                                        section_status='Photograph-led, unmeasured individual sections.',
                                        **properties))


def section_at(shape, x):
    section = shape.intersection(LineString(((x, -650.), (x, -400.))))
    if section.geom_type != 'LineString':
        raise RuntimeError('Unexpected platform section at ' + str(x))
    return min(y for _, y in section.coords), max(y for _, y in section.coords)


def wedge(batch, x, y, spring, radius, thickness, a, c, depth, material):
    """One independently editable, closed radial vault brick."""
    vv = [(x + r * math.cos(t), y + dy, spring + r * math.sin(t))
          for dy in (-depth / 2, depth / 2)
          for r, t in ((radius, a), (radius, c),
                       (radius + thickness, c), (radius + thickness, a))]
    batch.add(vv, ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                   (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)), material)


def barrel(batch, x, y0, y1, width, height, p, index):
    """Brick intrados within the inherited arched opening, not a solid cap."""
    radius = width / 2 - .035
    spring = height - width / 2
    rows = max(1, round((y1 - y0) / .31))
    pitch = (y1 - y0) / rows
    count = math.ceil(math.pi * radius / .32)
    brick_count = 0
    # Lime beds sit 3 mm behind the brick faces. An empty 35 mm-deep crack
    # would create unrealistically black joints under the vaulted daylight.
    for j in range(96):
        wedge(batch, x, (y0 + y1) / 2, spring, radius + .003, .035,
              j * math.pi / 96, (j + 1) * math.pi / 96, y1 - y0, p.mortar)
    for row in range(rows):
        y = y0 + (row + .5) * pitch
        # Alternate half bricks around the arch; leave physical lime joints.
        offset = .5 * (row % 2)
        for j in range(-1, count + 1):
            a = max(.002, (j + offset) * math.pi / count + .0016)
            c = min(math.pi - .002, (j + 1 + offset) * math.pi / count - .0016)
            if c - a < .004:
                continue
            wedge(batch, x, y, spring, radius, .070, a, c, pitch - .007,
                  p.vault_bricks[(row * 7 + j * 3 + index) % len(p.vault_bricks)])
            brick_count += 1
    # Side walls have staggered bed joints and genuinely modelled stone footings.
    vertical = max(1, math.ceil((spring - .38) / .225))
    horizontal = max(1, math.ceil((y1 - y0) / .47))
    for side in (-1, 1):
        batch.box((x + side * (width / 2 - .036), (y0 + y1) / 2, (.38 + spring) / 2),
                  (.024, y1 - y0, spring - .38), p.mortar)
        for row in range(vertical):
            z0 = .38 + row * (spring - .38) / vertical
            z1 = .38 + (row + 1) * (spring - .38) / vertical
            for j in range(-1, horizontal + 1):
                a = max(y0, y0 + (j + (row % 2) * .5) * (y1 - y0) / horizontal)
                c = min(y1, y0 + (j + 1 + (row % 2) * .5) * (y1 - y0) / horizontal)
                if c - a < .015:
                    continue
                batch.box((x + side * (width / 2 - .022), (a + c) / 2, (z0 + z1) / 2),
                          (.058, c - a - .006, z1 - z0 - .005),
                          p.vault_bricks[(row * 3 + j + index) % len(p.vault_bricks)])
                brick_count += 1
        batch.box((x + side * (width / 2 - .026), (y0 + y1) / 2, .23),
                  (.073, y1 - y0, .31), p.marble_dark)
    return dict(bricks=brick_count, axial_bays=rows, radial_bricks_per_full_row=count,
                inferred_brick_module_m=[.31, .32, .07],
                clear_width_before_lining_m=width, inherited_crown_z_m=height,
                intrados_radius_m=radius, inherited_spring_z_m=spring)


def door_leaf(group, p, x, y, width, height, sign, label):
    """Door coordinates pivot at the hinge; both leaves open into the tunnel."""
    b = Batch((x, y, .065), sign * math.radians(88.0))
    center = sign * width / 2
    b.box((center, 0, height / 2), (width, .174, height), p.door)
    boards = max(3, round(width / .25))
    for j in range(boards):
        b.box((sign * (j + .5) * width / boards, -.091, height / 2),
              (width / boards - .0022, .015, height - .026), p.gate_red)
    for z in (.19, height * .35, height * .67, height - .19):
        b.box((center, .118, z), (width - .045, .075, .102), p.door)
    for row in range(9):
        for col in range(9):
            xx = sign * (.16 + col * (width - .32) / 8)
            zz = .22 + row * (height - .44) / 8
            b.ellipsoid((xx, -.124, zz), (.043, .025, .043), p.old_gold, sides=12, rings=8)
    for zz in (.42, height / 2, height - .42):
        b.rod((0, .015, zz - .115), (0, .015, zz + .115), .047,
              p.iron, sides=14)
        b.box((sign * .18, .096, zz), (.36, .022, .070), p.iron)
    hx = sign * (width - .23)
    hz = height * .43
    b.ellipsoid((hx, -.146, hz), (.112, .036, .139), p.old_gold, sides=24, rings=12)
    b.path([(hx + .080 * math.cos(j * math.tau / 48), -.210,
             hz - .055 + .105 * math.sin(j * math.tau / 48)) for j in range(49)],
           .013, p.old_gold, sides=10)
    for side in (-1, 1):
        b.path([(hx + side * (.031 + .018 * math.sin(t)), -.178,
                 hz + .015 + .068 * math.cos(t)) for t in (j * math.pi / 20 for j in range(21))],
               .006, p.gold, sides=6)
    return part(b, label, group, 'wumen_hinged_gate_leaf',
                hinge_world_xy_m=[x, y], hinge_angle_degrees=sign * 88.,
                modeled_nail_grid=[9, 9],
                pose_status='Reversible virtual visit pose; exact door sections and hardware unmeasured.')


def entrances(site, group, p):
    shape = site.geom(PLATFORM)
    lining = Batch()
    masonry, threshold, floors = Batch(), Batch(), Batch()
    records, portals = [], []
    for index, (x, _, width, height, _, _) in enumerate(COURSES[:3]):
        south, north = section_at(shape, x)
        records.append(dict(index=index, x=x, south_y_m=south, north_y_m=north,
                            **barrel(lining, x, south + .24, north - .035, width, height, p, index)))
        # The south facade has a square-headed mouth, while its deep vault and
        # north exit remain arched. Fill only the old arch outside that mouth.
        clear_w = 5.16 if index == 1 else 4.27
        clear_h = 5.27 if index == 1 else 4.70
        opening = box(x - clear_w / 2, -.26, x + clear_w / 2, clear_h + .065)
        fill = arch_section(x, width, height).difference(opening)
        skin = Batch()
        for polygon in polygons(fill):
            arch_mesh(skin, polygon, .25, p.paint)
        skin.v = [(a, b + south + .08, c) for a, b, c in skin.v]
        masonry.add(skin.v, skin.f, p.paint)
        for sign in (-1, 1):
            masonry.box((x + sign * (clear_w / 2 + .11), south - .095, clear_h / 2 + .065),
                        (.22, .30, clear_h + .13), p.gate_red)
            threshold.box((x + sign * (clear_w / 2 + .12), south - .11, .37),
                          (.28, .37, .65), p.marble_dark)
        masonry.box((x, south - .13, clear_h + .16), (clear_w + .43, .34, .19), p.gate_red)
        masonry.box((x, south - .316, clear_h + .26), (clear_w + .50, .032, .055), p.giltpaint)
        masonry.box((x, south - .319, clear_h + .18), (clear_w + .35, .035, .031), p.gold)
        for sign in (-1, 1):
            hinge = x - sign * (clear_w / 2 - .025)
            door_leaf(group, p, hinge, south + .31, clear_w / 2 - .033,
                      clear_h - .095, sign, f'第{index + 1}门 · {"左" if sign > 0 else "右"}扇九路铜钉板门')
        nx = max(2, math.ceil((width - .12) / .74))
        ny = max(2, math.ceil((north - south + 2.0) / 1.10))
        for j in range(ny):
            a = south - 1.0 + j * (north - south + 2.0) / ny
            c = south - 1.0 + (j + 1) * (north - south + 2.0) / ny
            for k in range(nx):
                xx = x - (width - .12) / 2 + (k + .5) * (width - .12) / nx
                floors.box((xx, (a + c) / 2, .028),
                           ((width - .12) / nx - .005, c - a - .006, .035),
                           p.floor_stones[(j + k * 3) % len(p.floor_stones)])
        portals.append(dict(x=x, south_y_m=south, clear_width_m=clear_w,
                            clear_height_m=clear_h, leaves=2, opening_degrees=88.,
                            dimension_status='Photo-led mouth within the inherited mapped vault.'))
    part(lining, '三条直券逐块青砖内衬', group, 'wumen_native_vault_bricks',
         vault_count=3, intrados_status='Native wedge bricks and staggered masonry, not image planes.')
    part(masonry, '南向方口、门框和金色槛线', group, 'wumen_south_rectangular_portals')
    part(threshold, '门框下脚石与门枕', group, 'wumen_door_foot_stones')
    part(floors, '门洞踏面逐块石板', group, 'wumen_tunnel_flagstones', nominal_top_z_m=.0455)
    # Low stone courses follow the original U-shaped foundation and respect
    # every straight or turned opening instead of bridging any gate route.
    band = shape.buffer(.058, join_style=2).difference(shape.buffer(-.15, join_style=2))
    for x, y, width, _, length, yaw in COURSES:
        cutter = affinity.rotate(box(-width / 2 - .025, -length / 2 - .3,
                                     width / 2 + .025, length / 2 + .3),
                                 yaw, origin=(0, 0), use_radians=True)
        band = band.difference(affinity.translate(cutter, x, y))
    b = Batch()
    b.solid_xy(band, .018, .37, p.marble_dark)
    b.solid_xy(band.buffer(.013, join_style=2), .376, .71, p.masonry)
    part(b, '凹形墩台下碱石砌及七段门道留口', group, 'wumen_opening_safe_stone_courses')
    plinth = Batch((MAIN[0], MAIN[1], 0), -.010)
    plinth.box((0, 0, 12.025), (61.97, 27.97, .05), p.marble_dark)
    part(plinth, '正楼测绘露明台基', group, 'wumen_published_hall_plinth',
         published_plan_m=[61.97, 27.97], source=PLAN_SOURCE,
         vertical_datum_status='Inherited site datum; exposed plinth plan documented in the 1983 article.')
    return dict(straight_vault_linings=records, south_portals=portals,
                published_plinth_plan_m=[61.97, 27.97],
                retained_five_route_cutters=COURSES,
                limits=['Brick modules, joint widths, portal clear sections and door hardware are unmeasured.',
                        'The two bent gate routes retain inherited geometry; only their low stone courses are revised.'])


def connectors(site, group, p):
    records = []
    for side, ref in ((-1, '638156830'), (1, '638156677')):
        shape = site.geom(ref)
        tower_x, tower_y = shape.centroid.x, shape.centroid.y
        main_edge = MAIN[0] + side * (60.05 / 2 - .18)
        tower_edge = tower_x - side * 7.04
        start, end = (main_edge, MAIN[1]), (tower_edge, tower_y)
        distance = math.dist(start, end)
        center = tuple((a + c) / 2 for a, c in zip(start, end))
        yaw = math.atan2(end[1] - start[1], end[0] - start[0])
        if side < 0:
            yaw += math.pi
        name = '午门修订 · ' + ('西' if side < 0 else '东') + '三间明廊'
        before = set(bpy.data.objects)
        hall(name, group, p, origin=(*center, 0.), yaw=yaw, width=distance,
             depth=9.3, floor=12., eave=17.6, rise=3.8, bays=3, deep_bays=1,
             kind='gable', beasts=0, open_gate=True, roof_width=distance + .44,
             roof_depth=13.1, post_radius=.27)
        created = set(bpy.data.objects) - before
        for obj in created:
            obj['connector_bays'] = 3
            obj['form_source'] = SOURCE
            obj['layout_status'] = 'Three bays documented; spans fitted between mapped tower and existing main hall.'
        records.append(dict(side='west' if side < 0 else 'east', name=name,
                            bays=3, endpoints_m=[start, end], width_m=distance,
                            mesh_objects=sum(o.type == 'MESH' for o in created),
                            section_status='Photo-led inherited gallery sections, not individual timber measurements.'))
    return records
