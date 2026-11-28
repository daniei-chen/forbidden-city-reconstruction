"""Install, reopen and render the Ning Shou south court in the native palace model."""
import argparse
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from shapely.geometry import LineString

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mesh_tools import collection
from ning_shou_gate import ARCHES, ARCHIVES, COURT_REPLACEMENTS, EAST_WALL, GATE_ID, GATE_SOURCE, GLAZED_GATES, build_gate, court_edges, courtyard_trees
from ning_shou_inner_gate import INNER_ID, INNER_FLOOR, build_inner_gate
from ning_shou_screen import BODY, FACE_Y, FIELD_HIGH, FIELD_LOW, FIELD_W, GRID_PITCH, HEIGHT, LENGTH, RELIEF, SCREEN_ID, SCREEN_SOURCE
from ning_shou_screen import build_screen, location as screen_location
from north_garden_walkthrough import bounds, visible
from osm_site import Site, rectangle
from outer_court_walkthrough import configure_cycles, first_hit, route_geometry, smoothstep
from qinan_survey import Location
from refine_immersive import camera, use_existing_palette
from refine_yude_tang_scene import geometry_trees


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'The_Forbidden_City_Imperial_Garden_Twins.blend'
MASTER = ROOT / 'The_Forbidden_City_Ning_Shou_Detail.blend'
REPORT = ROOT / 'ning_shou_detail_revision_report.json'
CHECKS = ROOT / 'validation_ning_shou_detail_revision.json'
GROUP = '宁寿宫 · 九龙壁、皇极门与宁寿门'
TOUR = '宁寿宫 · 从九龙壁穿过皇极门'
INNER_TOUR = '宁寿宫 · 登宁寿门至高台甬路'
FRAMES_FOLDER = 'ning_shou_detail_frames'
INNER_FRAMES_FOLDER = 'ning_shou_inner_gate_frames'
FPS, FRAMES, EYE = 24, 480, 1.65
COURT_PATHS = {42310572, 42310573, 146020933, 146020934, 41661996}
VIEWS = {
    '63': ('nine_dragons_front', '九龙壁 · 正面全幅', 'screen', (0., -25.6, 1.65), (0., 0., 2.33), 26.),
    '64': ('nine_dragons_yellow_relief', '九龙壁 · 正龙琉璃浮雕', 'screen', (1.76, -5.23, 1.65), (.64, -.17, 1.70), 38.),
    '65': ('huangji_south_court', '皇极门 · 正楼、次楼和边楼', 'gate', (-6.7, -23.3, 1.65), (.15, -1.07, 3.29), 28.),
    '66': ('huangji_through_arch', '皇极门 · 从门槛望入前院', 'gate', (.13, -3.46, 1.74), (.06, 1.6, 2.26), 24.),
    '67': ('nine_dragons_low_rake', '九龙壁 · 望柱、瓦当与掠视浮雕', 'screen', (-13.8, -4.74, 1.68), (-5.9, -.15, 1.83), 32.),
    '68': ('ning_shou_gate_front', '宁寿门 · 五间敞厅和丹陛', 'inner', (-2.5, -30.2, 1.65), (0., -.5, 4.55), 27.),
    '69': ('ning_shou_gate_stair', '宁寿门 · 白石栏阶与铜狮', 'inner', (8.36, -13.85, 1.64), (.44, -5.43, 2.18), 29.),
    '70': ('ning_shou_gate_from_eaves', '宁寿门 · 敞间、额枋与高台甬路', 'inner', (1.74, -4.17, 2.69), (-.46, 9.76, 3.54), 26.),
}


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def remove_old_court_paving():
    obj = bpy.data.objects['石板路 · mapped circulation']
    mesh = obj.data
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        low = bm.faces.layers.int['osm_id_low']
        high = bm.faces.layers.int.get('osm_id_high')
        doomed = [f for f in bm.faces if f[low] in COURT_PATHS and (high is None or f[high] == 0)]
        if not doomed:
            raise RuntimeError('No previous paving faces found for the two Ning Shou courtyards.')
        count = len(doomed)
        bmesh.ops.delete(bm, geom=doomed, context='FACES')
        bm.to_mesh(mesh)
        mesh.update()
        return count
    finally:
        bm.free()


def share_court(base, scene, gate, inner=None):
    count = 0
    for obj in base.objects:
        if not visible(obj):
            continue
        if obj.type == 'LIGHT':
            if obj.data.type != 'SUN':
                continue
        elif obj.type == 'MESH':
            lo, hi = bounds(obj)
            dx = max(lo[0] - gate.x, gate.x - hi[0], 0.)
            dy = max(lo[1] - gate.y, gate.y - hi[1], 0.)
            far = (dx * dx + dy * dy > 103**2)
            if inner:
                dx = max(lo[0] - inner.x, inner.x - hi[0], 0.)
                dy = max(lo[1] - inner.y, inner.y - hi[1], 0.)
                far = far and dx * dx + dy * dy > 84**2
            if far:
                continue
        else:
            continue
        scene.collection.objects.link(obj)
        count += 1
    world = bpy.data.worlds.get('宁寿宫 · 天空漫反射')
    if not world:
        world = base.world.copy()
        world.name = '宁寿宫 · 天空漫反射'
        nodes, links = world.node_tree.nodes, world.node_tree.links
        sky = nodes.get('Background')
        render_sky = nodes.new('ShaderNodeBackground')
        render_sky.inputs['Strength'].default_value = sky.inputs['Strength'].default_value * 1.7
        links.new(sky.inputs['Color'].links[0].from_socket, render_sky.inputs['Color'])
        mix = nodes.new('ShaderNodeMixShader')
        light_path = nodes.new('ShaderNodeLightPath')
        links.new(light_path.outputs['Is Camera Ray'], mix.inputs[0])
        links.new(render_sky.outputs[0], mix.inputs[1])
        links.new(sky.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], nodes.get('World Output').inputs['Surface'])
    scene.world = world
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.
    scene.render.engine = 'CYCLES'
    scene.render.fps = FPS
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = base.view_settings.view_transform
    scene.view_settings.look = base.view_settings.look
    scene.view_settings.exposure = base.view_settings.exposure
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    return count


def sample_path(anchors):
    anchors = [Vector(v) for v in anchors]
    points = []
    for i, (p, q) in enumerate(zip(anchors, anchors[1:])):
        a = (q - anchors[max(0, i - 1)]) * .38
        b = (anchors[min(i + 2, len(anchors) - 1)] - p) * .38
        for j in range(25):
            t = j / 25
            points.append(tuple(p * (2*t**3 - 3*t*t + 1) + a * (t**3 - 2*t*t + t)
                                + q * (-2*t**3 + 3*t*t) + b * (t**3 - t*t)))
    return LineString([*points, tuple(anchors[-1])])


def prepare_tour(base, gate, screen, *, inner=None):
    if inner:
        path = sample_path(((.24, -21.85), (1.85, -15.5), (1.94, -10.63), (1.94, -6.59),
                            (1.73, -4.75), (.56, -1.62), (.16, 3.09), (.25, 9.55)))
        place, name, folder, max_floor = inner, INNER_TOUR, INNER_FRAMES_FOLDER, 1.17
    else:
        path = sample_path(((-7.7, -24.9), (-2.85, -23.7), (-.37, -17.5), (.0, -8.1), (.0, 1.5), (.63, 5.17)))
        place, name, folder, max_floor = gate, TOUR, FRAMES_FOLDER, .45
    graph = bpy.context.evaluated_depsgraph_get()
    loc = lambda p, z: Vector(place.world(p.x, p.y, z))
    start, finish = (path.interpolate(x * path.length) for x in (0., 1.))
    trees = route_geometry(base, graph, loc(start, 0), loc(finish, 0), 2.25, 4.05)
    down = Vector((0, 0, -1))
    stationary = tuple(Vector((math.cos(i * math.pi / 4), math.sin(i * math.pi / 4), 0.)) for i in range(8))

    def floor(point):
        hit = first_hit(trees, loc(point, max_floor + .29), down, max_floor + .53)
        if hit is None or not -.08 <= hit[1].z < max_floor:
            raise RuntimeError(f'No walking surface at {point}: {hit}')
        return hit[1].z

    keys, feet = [], []
    last = None
    for frame in range(FRAMES):
        t = frame / (FRAMES - 1)
        d = path.length * (.10 * smoothstep(t) + .90 * t)
        point = path.interpolate(d)
        level = floor(point)
        feet.append(level)
        support = sum(floor(path.interpolate(min(path.length, max(0., d + .096 * i)))) for i in range(-3, 4)) / 7
        z = EYE + support + .010 * math.sin(d * math.tau / .81)
        pos = loc(point, z)
        for offset in (0., -.35, -.77):
            for direction in stationary:
                hit = first_hit(trees, pos + Vector((0, 0, offset)), direction, .193)
                if hit:
                    raise RuntimeError(f'Human-eye camera overlap at frame {frame + 1}: {hit[0]}')
        if last is not None:
            diff = pos - last
            if diff.length > .0001 and (hit := first_hit(trees, last, diff.normalized(), diff.length)):
                raise RuntimeError(f'Camera crosses {hit[0]} between frames {frame} and {frame + 1}')
        last = pos
        if inner:
            facade = Vector(inner.world(.01, -2.22, 4.37))
            court = Vector(inner.world(-.13, 56.2, 4.16))
            q = (facade.lerp(court, smoothstep((d - 11.4) / 7.1)) - pos).to_track_quat('-Z', 'Y')
            lens = 24.8 - 2.3 * smoothstep(d / 17.)
        else:
            mural = Vector(screen.world(1.24 - 3.3 * smoothstep(d / 8.1), -.25, 1.89))
            portal = Vector(gate.world(.07, 1.9, 2.50))
            court = Vector(gate.world(.42, 69.8, 4.21))
            approach = smoothstep((d - 16.) / 12.5)
            look_a = (mural - pos).to_track_quat('-Z', 'Y')
            look_b = (portal.lerp(court, approach) - pos).to_track_quat('-Z', 'Y')
            turn = smoothstep((d - 4.25) / 10.75)
            q = look_a.slerp(look_b, turn)
            lens = 24.6 - 1.8 * turn + 1.3 * smoothstep((d - 24.) / 6.)
        if keys and q.dot(keys[-1][1]) < 0:
            q.negate()
        keys.append((pos, q, lens))

    scene = bpy.data.scenes.new(name)
    shared = share_court(base, scene, gate, inner=inner)
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    scene.collection.objects.link(cam)
    cam.rotation_mode = 'QUATERNION'
    cam.data.clip_start, cam.data.clip_end = .035, 2000
    for i, (pos, q, lens) in enumerate(keys, 1):
        cam.location, cam.rotation_quaternion, cam.data.lens = pos, q, lens
        for key in ('location', 'rotation_quaternion'):
            cam.keyframe_insert(data_path=key, frame=i)
        cam.data.keyframe_insert(data_path='lens', frame=i)
    scene.frame_start, scene.frame_end = 1, FRAMES
    scene.camera = cam
    scene.render.filepath = f'//renders/{folder}/'
    scene.frame_set(1)
    return {'scene': name, 'fps': FPS, 'frames_checked': FRAMES, 'frames_directory': folder,
            'path_m': round(path.length, 3), 'eye_height_m': EYE, 'clearance_radius_m': .193,
            'support_range_m': [min(feet), max(feet)], 'geometry_objects_checked': len(trees),
            'shared_render_objects': shared, 'terminal_gate_local_xy_m': list(finish.coords)[0],
            'origin_xy_m': [place.x, place.y], 'origin_yaw_rad': place.yaw,
            'scope': 'Per-frame footing, head and torso sample and segment continuity checked against the mesh.'}


def build():
    bpy.ops.wm.open_mainfile(filepath=str(BASE))
    scene = bpy.context.scene
    site = Site()
    group = collection(GROUP, bpy.data.collections['紫禁城 · EDITABLE 3D MASTER'])
    prior = {s.name for s in bpy.data.scenes}
    removed = []
    for obj in list(scene.objects):
        ref = str(obj.get('source_osm_id', obj.get('osm_id', '')))
        if ref in {GATE_ID, SCREEN_ID, INNER_ID, *COURT_REPLACEMENTS}:
            removed.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)
    if not any(name.startswith('皇极门') for name in removed):
        raise RuntimeError('Expected existing gate proxy before replacement.')
    removed_paving_faces = remove_old_court_paving()
    screen, p, registration = build_screen(site, group, use_existing_palette())
    gate, width, depth, roofs = build_gate(site, group, p)
    court_edges(site, screen, gate, width, depth, group, p)
    inner, inner_report = build_inner_gate(site, group, p)
    trees = courtyard_trees(group, screen, gate, p)
    cameras = {}
    for index, (_, title, place, eye, look, lens) in VIEWS.items():
        loc = {'screen': screen, 'gate': gate, 'inner': inner}[place]
        cam = camera(index + ' · ' + title, loc.world(*eye), loc.world(*look), lens)
        cam.data.clip_start, cam.data.clip_end = .035, 2200
        cameras[index] = cam
    scene.camera = cameras['63']
    scene.render.resolution_x, scene.render.resolution_y = 2304, 1296
    scene.render.filepath = '//renders/63_nine_dragons_front_ningshou_detail.png'
    scene['latest_revision'] = GROUP
    bpy.context.view_layer.update()
    tour = prepare_tour(scene, gate, screen)
    inner_tour = prepare_tour(scene, gate, screen, inner=inner)
    objects = [o for o in group.all_objects if o.type == 'MESH']
    info = {'native_blend': MASTER.name, 'base_blend': BASE.name, 'collection': GROUP,
            'sources': {'screen': SCREEN_SOURCE, 'gate': GATE_SOURCE, 'glazed_gates_article': GLAZED_GATES,
                        'archive_plan_and_text_pdf': ARCHIVES, 'archive_plan_pdf_page': 4},
            'preserved_scenes': sorted(prior), 'replaced_objects': removed,
            'replaced_paving': {'map_ways': sorted(COURT_PATHS), 'old_faces_removed': removed_paving_faces},
            'courtyard_trees': {'source': [SCREEN_SOURCE, GATE_SOURCE], 'positions_and_sizes_inferred': True, 'objects': trees},
            'screen': {'map_way': SCREEN_ID, 'published_length_height_thickness_m': [LENGTH, HEIGHT, BODY],
                       'published_relief_limit_m': RELIEF, 'published_blocks': 270, 'published_bracket_panels': 45,
                       'published_ridge_dragons': 9, 'color_registration': registration,
                       'target_projected_mesh_pitch_m': GRID_PITCH,
                       'inferred_field_bounds_m': [-FIELD_W / 2, FIELD_LOW, FIELD_W / 2, FIELD_HIGH]},
            'gate': {'map_way': GATE_ID, 'mapped_width_m': width, 'body_depth_model_m': depth,
                     'documented_openings': 3, 'documented_rooflets': 7, 'estimated_arches': ARCHES,
                     'estimated_rooflets': roofs, 'door_pose': 'Central leaves open for the virtual visit; side leaves closed.'},
            'editable_meshes': len(objects), 'native_polygons': sum(len(o.data.polygons) for o in objects),
            'ning_shou_walkthrough': tour, 'inner_gate_walkthrough': inner_tour, 'inner_gate': inner_report,
            'limits': ['Dragon silhouettes and ceramic coloring are registered to the reference images; relief depth, block joints and profiles are modeled estimates.',
                       'Gate section heights, hardware and bracket curvature are photo estimates. Open doors are a tour pose.',
                       'No contemporary point cloud or calibrated depth photography was available.']}
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(MASTER), compress=True)
    dump(REPORT, info)
    print('NING_SHOU_BUILT', len(objects), info['native_polygons'], tour['path_m'], inner_tour['path_m'], flush=True)


def sample_audit(blocks):
    rows, axial, spatial = [], [], []
    cell_areas = []
    for block in sorted(blocks, key=lambda o: (o['row'], o['course_position'])):
        nz, nx = block['front_grid_shape']
        positions = np.empty(len(block.data.vertices) * 3, dtype=np.float32)
        block.data.vertices.foreach_get('co', positions)
        front = positions[:nz*nx*3].reshape(nz, nx, 3).astype(np.float64)
        dx, dz = np.diff(front, axis=1), np.diff(front, axis=0)
        dx_xz, dz_xz = dx[:, :, (0, 2)], dz[:, :, (0, 2)]
        intervals = np.concatenate([np.linalg.norm(d, axis=2).ravel() for d in (dx_xz, dz_xz)])
        distances = np.concatenate([np.linalg.norm(d, axis=2).ravel() for d in (dx, dz)])
        area = dx[:-1, :, 0] * dz[:, :-1, 2]
        cell_areas.append(area.ravel())
        axial.append(float(intervals.max()))
        spatial.append(distances)
        rows.append({'object': block.name, 'course': block['row'], 'position': block['course_position'],
                     'grid_z_x': list(block['front_grid_shape']),
                     'max_pitch_mm': round(float(intervals.max()) * 1000, 5),
                     'longest_front_edge_mm': round(float(distances.max()) * 1000, 5),
                     'face_coverage_m2': round(float(area.sum()), 7), 'joint_evidence': block['joint_evidence']})
    spatial = np.concatenate(spatial)
    cell_areas = np.concatenate(cell_areas)
    area = float(cell_areas.sum())
    return {'tiles_measured': len(rows), 'max_projected_pitch_mm': max(axial) * 1000,
            'max_projected_quad_area_cm2': float(cell_areas.max()) * 10000,
            'spatial_edge_p95_mm': float(np.percentile(spatial, 95)) * 1000,
            'max_spatial_edge_mm': float(spatial.max()) * 1000,
            'front_surface_quads': int(cell_areas.size), 'projected_face_coverage_m2': area,
            'projected_field_area_m2': FIELD_W * (FIELD_HIGH - FIELD_LOW),
            'scope': 'Measurements of serialized ceramic mesh in its front plane and along its edges. Does not measure deviation from the real relief.',
            'blocks': rows}


def verify_tour(info):
    scene = bpy.data.scenes[info['scene']]
    camera_ok = bool(scene.camera and scene.camera.animation_data and scene.camera.animation_data.action)
    first, final, turn_limit = None, None, None
    if camera_ok:
        yaw = info['origin_yaw_rad']
        travel = Vector((-math.sin(yaw), math.cos(yaw), 0.))
        origin = Vector((*info['origin_xy_m'], 0.))
        active = bpy.context.window.scene
        bpy.context.window.scene = scene
        try:
            angles, positions = [], []
            prev = None
            for frame in range(1, FRAMES + 1):
                scene.frame_set(frame)
                cam = scene.camera.evaluated_get(bpy.context.evaluated_depsgraph_get())
                pose = cam.matrix_world.copy()
                positions.append((pose.translation - origin).dot(travel))
                rotation = pose.to_quaternion()
                if prev is not None:
                    angles.append(math.degrees(2 * math.acos(min(1., abs(prev.dot(rotation))))))
                prev = rotation
            first, final, turn_limit = positions[0], positions[-1], max(angles)
        finally:
            scene.frame_set(1)
            bpy.context.window.scene = active
    return (first is not None and first < -20. and final > 4.5 and turn_limit < 4.
            and scene.frame_end == FRAMES and info['frames_checked'] == FRAMES), {
        'start_gate_local_y_m': first, 'end_gate_local_y_m': final, 'frames': FRAMES,
        'max_turn_deg_per_frame': turn_limit, 'support_z_range_m': info['support_range_m']}


def verify(scene):
    info = json.loads(REPORT.read_text(encoding='utf-8'))
    group = bpy.data.collections[GROUP]
    graph = bpy.context.evaluated_depsgraph_get()
    site = Site()
    gx, gy, _, _, yaw = rectangle(site.geom(GATE_ID))
    gate = Location(gx, gy, yaw)
    screen = screen_location(site)
    checks = []

    def check(label, ok, evidence):
        checks.append({'check': label, 'passed': bool(ok), 'evidence': evidence})

    check('metric; preserved all existing scenes', scene.unit_settings.system == 'METRIC'
          and scene.unit_settings.scale_length == 1. and set(info['preserved_scenes']) <= set(bpy.data.scenes.keys()),
          [scene.unit_settings.scale_length, sorted(bpy.data.scenes.keys())])
    check('prior screen and gate proxies removed', not set(info['replaced_objects']) & set(scene.objects.keys()), info['replaced_objects'])
    old = bpy.data.objects['石板路 · mapped circulation'].data
    old_low = np.empty(len(old.polygons), dtype=np.int32)
    old.attributes['osm_id_low'].data.foreach_get('value', old_low)
    if old.attributes.get('osm_id_high'):
        old_high = np.empty(len(old.polygons), dtype=np.int32)
        old.attributes['osm_id_high'].data.foreach_get('value', old_high)
        old_low = old_low[old_high == 0]
    check('old paving is removed only for the replaced mapped courts and paths',
          info['replaced_paving']['old_faces_removed'] > 0 and len(old_low) > 0 and not set(old_low) & COURT_PATHS,
          {'old_faces_removed': info['replaced_paving']['old_faces_removed'], 'remaining_global_paths': len(set(old_low))})
    body = bpy.data.objects['九龙壁 · 29.4 米墙芯与灰缝']
    size = [max(v.co[i] for v in body.data.vertices) - min(v.co[i] for v in body.data.vertices) for i in (0, 1)]
    crest = max(v.co.z for v in bpy.data.objects['九龙壁 · 正脊中坐龙与两侧八行龙'].data.vertices)
    check('published screen body and crest envelope', abs(size[0] - LENGTH) < .0001 and abs(size[1] - BODY) < .0001
          and abs(crest - HEIGHT) < .014, [round(v, 5) for v in [*size, crest]])
    blocks = [o for o in group.all_objects if o.get('assembly') == 'nine_dragon_tile']
    counts = [sum(o['row'] == row for o in blocks) for row in range(1, 6)]
    relief = FACE_Y - min(v.co.y for o in blocks for v in o.data.vertices)
    check('270 independent shaped ceramic blocks with bounded relief', counts == [54]*5 and .189 < relief <= RELIEF + .0001
          and all(len(o.data.polygons) > 1500 for o in blocks), {'course_tile_counts': counts, 'geometry_max_relief_m': relief})
    sampling = sample_audit(blocks)
    dump(ROOT / 'nine_dragons_tile_sampling_audit.json', sampling)
    check('all ceramic blocks measured below 1 cm projected pitch',
          sampling['max_projected_pitch_mm'] <= 10. and sampling['max_projected_quad_area_cm2'] <= 1.
          and sampling['front_surface_quads'] > 700000 and sampling['projected_face_coverage_m2'] > 63.,
          {k: v for k, v in sampling.items() if k != 'blocks'})
    atlas = bpy.data.images.get('nine_dragons_calibrated.jpg')
    check('packed calibration atlas and nine identifiable figure positions', atlas and atlas.packed_file
          and len(info['screen']['color_registration']['figure_centers_u']) == 9, list(atlas.size) if atlas else None)
    frieze = bpy.data.objects['九龙壁 · 45 块垫栱板及浮起纹样']
    check('ceramic frieze and nine ridge figures', frieze['frieze_blocks'] == 45
          and bpy.data.objects['九龙壁 · 正脊中坐龙与两侧八行龙']['crest_dragons'] == 9, [45, 9])
    direction = Vector((-math.sin(gate.yaw), math.cos(gate.yaw), 0))
    gate_body = bpy.data.objects['皇极门 · 厚墙与贯通的三座砖券']
    wall_tree = geometry_trees([gate_body], graph)
    open_result = []
    for x, width, top, _ in ARCHES:
        clear = [first_hit(wall_tree, Vector(gate.world(x + c, -3., z)), direction, 6.)
                 for c, z in ((0, 1.65), (0, top - .11), (.40 * width, 1.55), (-.40 * width, 1.55))]
        crown = first_hit(wall_tree, Vector(gate.world(x, -3., top + .055)), direction, 6.)
        open_result.append([all(hit is None for hit in clear), bool(crown)])
    check('three actual arch voids with solid wall above', all(a and b for a, b in open_result), open_result)
    rooflets = bpy.data.collections['皇极门 · 七座琉璃门楼']
    roof_types = [c['role'] for c in sorted(rooflets.children, key=lambda c: c['rooflet_index'])]
    check('seven roof silhouettes including two outer-hip inner-gable roofs',
          roof_types == ['边楼', '次楼', '夹楼', '正楼', '夹楼', '次楼', '边楼']
          and sum(o.get('roof_type') == 'outer_hip_inner_gable' for o in rooflets.all_objects) == 2, roof_types)
    upper_wall = bpy.data.objects['东翼墙 · 朱墙整条平面']
    return_tip = max(v.co.y for v in upper_wall.data.vertices)
    check('eastern wing retains mapped north return', upper_wall['reconstructed_osm_way'] == EAST_WALL
          and abs(upper_wall['return_y_max_m'] - return_tip) < .0001 and return_tip > 177, return_tip)
    x, y, width, depth, yaw = rectangle(site.geom(INNER_ID))
    inner = Location(x, y, yaw)
    inner_group = bpy.data.collections['宁寿门 · 五间歇山和白石丹陛']
    direction = Vector((-math.sin(yaw), math.cos(yaw), 0.))
    structure = [o for o in inner_group.all_objects if o.type == 'MESH']
    tree = geometry_trees(structure, graph)
    front_bays = [-10.91, -5.85, 0., 5.85, 10.91]
    bays_clear = [first_hit(tree, Vector(inner.world(xx, -6.22, 2.74)), direction, 6.18) is None
                  for xx in front_bays]
    central_clear = first_hit(tree, Vector(inner.world(.09, -.18, 2.74)), direction, 6.25) is None
    check('Ningshou Gate has three real open bays, two front windows and an open central threshold',
          bays_clear == [False, True, True, True, False] and central_clear,
          {'clear_front_bays': bays_clear, 'clear_rear_central_bay': central_clear, 'mapped_roof_dimensions_m': [width, depth]})
    check('two wing screens, lion pedestals and raised axial approach exist as native geometry',
          sum(c.get('plan_shape') == 'splayed' for c in inner_group.children) == 2
          and sum(o.get('documented_subject') == 'gilt bronze lion' for o in structure) == 2
          and bpy.data.objects['宁寿门后 · 连至皇极殿前的高台甬路']['floor_z_m'] == INNER_FLOOR,
          {'screen_count': 2, 'lion_count': 2, 'approach_floor_z_m': INNER_FLOOR})
    passed, evidence = verify_tour(info['ning_shou_walkthrough'])
    check('saved camera trajectory enters the north courtyard', passed, evidence)
    passed, evidence = verify_tour(info['inner_gate_walkthrough'])
    check('saved camera trajectory climbs the physical stairs and enters the upper passage',
          passed and evidence['support_z_range_m'][1] >= INNER_FLOOR - .001, evidence)
    data = {'file': MASTER.name, 'passed': all(c['passed'] for c in checks), 'checks': checks,
            'scope': 'Reopened geometry and published envelope. No survey equivalence or full-city pixel equivalence implied.'}
    dump(CHECKS, data)
    print('NING_SHOU_VERIFY', data['passed'], [(r['check'], r['evidence']) for r in checks if not r['passed']], flush=True)
    if not data['passed']:
        raise RuntimeError('Ning Shou geometry failed verification.')


def render(args):
    base = bpy.context.scene
    scene = bpy.data.scenes[INNER_TOUR if args.mode == 'inner-tour' else TOUR]
    if args.mode == 'stills' and any(VIEWS[index][2] == 'inner' for index in args.views.split(',')):
        scene = bpy.data.scenes[INNER_TOUR]
    bpy.context.window.scene = scene
    configure_cycles(scene)
    scene.render.resolution_x = args.width
    scene.render.resolution_y = round(args.width * 9 / 16)
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.compression = 16
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.use_persistent_data = True
    if scene.cycles.device == 'GPU':
        scene.cycles.denoiser = 'OPTIX'
    if args.mode == 'stills':
        for index in args.views.split(','):
            label = VIEWS[index][0]
            cam = next(o for o in base.objects if o.type == 'CAMERA' and o.name.startswith(index + ' '))
            scene.collection.objects.link(cam)
            scene.camera = cam
            scene.render.filepath = str(ROOT / 'renders' / f'{index}_{label}_{args.suffix}.png')
            print('NING_SHOU_STILL', index, scene.cycles.device, flush=True)
            bpy.ops.render.render(write_still=True)
    else:
        name = INNER_FRAMES_FOLDER if args.mode == 'inner-tour' else FRAMES_FOLDER
        folder = ROOT / 'renders' / (name if args.suffix == 'ningshou_detail' else f'{name}_{args.suffix}')
        folder.mkdir(exist_ok=True)
        frames = range(1, FRAMES + 1) if args.frames == 'all' else [int(x) for x in args.frames.split(',')]
        for number in frames:
            path = folder / f'{number:04d}.png'
            if path.is_file() and path.stat().st_mtime_ns >= MASTER.stat().st_mtime_ns:
                continue
            scene.frame_set(number)
            pending = path.with_suffix('.pending.png')
            scene.render.filepath = str(pending)
            print('NING_SHOU_FRAME', number, scene.cycles.device, flush=True)
            bpy.ops.render.render(write_still=True)
            pending.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('build', 'verify', 'stills', 'tour', 'inner-tour'))
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--samples', type=int, default=32)
    parser.add_argument('--views', default=','.join(VIEWS))
    parser.add_argument('--frames', default='all')
    parser.add_argument('--suffix', default='ningshou_detail')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if args.mode == 'build':
        build()
        return
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    if args.mode == 'verify':
        verify(bpy.context.scene)
    else:
        render(args)


if __name__ == '__main__':
    main()
