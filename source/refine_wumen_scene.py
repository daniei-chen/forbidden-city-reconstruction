"""Increment, reopen, verify and actually render the retained Meridian Gate.

Run with Blender 4.5: --background --factory-startup --python-exit-code 1
--python source/refine_wumen_scene.py -- build|verify|baseline|stills|tour
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import bpy
from mathutils import Vector
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source'))
from mesh_tools import collection
from osm_site import Site
from outer_court_walkthrough import configure_cycles
from refine_huangji_scene import digest, dump
from refine_immersive import camera, use_existing_palette
from wumen_masonry import COURSES, MAIN, PLATFORM, connectors, entrances
from wumen_surfaces import ATTR, digest_geometry, materials, rematerialize, tile_attributes
from wumen_collision import foot as support_foot, ray as collision_ray, trees as collision_trees
from wumen_roof_detail import build as build_ridge_detail
from wumen_courtyard import COURTYARD_IDS, build as build_courtyard

BASE = ROOT / 'The_Forbidden_City_Inner_Court_Daylight.blend'
MASTER = ROOT / 'The_Forbidden_City_Wumen_Revision.blend'
REPORT = ROOT / 'wumen_revision_report.json'
VALIDATION = ROOT / 'validation_wumen_revision.json'
CITY = '紫禁城 · metric architectural reconstruction'
SCENE = '午门 · 穿过正门砖券看内金水河'
GROUP = '午门 · 连接明廊、门道及写实表层修订'
CAMERA = '午门修订 · 人眼穿门漫游相机'
FRAME_DIR = ROOT / 'renders/wumen_axial_walk_frames'
FRAMES, FPS, EYE = 960, 24, 1.65
VIEWS = {
 '103': ('wumen_south_front', '午门 · 正楼与双阙', (2., -592., 1.67), (-3., -478., 14.3), 25.),
 '104': ('wumen_north_front', '午门 · 北面五个券洞', (37., -391., 1.70), (-5., -470., 15.), 27.),
 '105': ('wumen_inner_courtyard', '午门 · 广庭内的人眼尺度', (-3.75, -532., 1.70), (-3.75, -476., 13.8), 23.),
 '106': ('wumen_south_door', '午门 · 方口门面和九路铜钉', (-9., -492., 1.70), (-3.75, -482.5, 3.), 25.),
 '107': ('wumen_brick_vault', '午门 · 砖券内看内金水河', (-3.75, -476., 1.6955), (-3.75, -441., 3.25), 25.),
 '108': ('wumen_west_wing', '午门 · 雁翅廊的柱列和重檐阙亭', (-53.6, -520., 13.70), (-52.4, -469., 18.2), 28.),
 '109': ('wumen_connecting_gallery', '午门 · 补回的三间明廊', (-38., -482., 13.70), (-43., -469., 16.3), 27.),
 '110': ('wumen_southwest_tower', '午门 · 西南阙亭与灰面墩台', (-18., -582., 1.68), (-54., -550., 16.), 25.),
 '111': ('wumen_overview', '午门 · 九座单体的凹形布局', (113., -626., 111.), (-2., -509., 12.5), 38.),
 '112': ('wumen_north_vault_mouth', '午门 · 北面券口的深度', (-12., -448., 1.72), (-3.75, -461., 3.0), 32.),
 '113': ('wumen_roof_detail', '午门 · 正楼瓦作与上下檐', (-24., -500., 38.), (-2., -470., 28.), 43.),
 '114': ('wumen_door_hardware', '午门 · 铜钉、门环和厚板门', (-5.65, -483.1, 2.3), (-6.1, -481., 2.4), 42.),
}


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def open_base(path):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    city = bpy.data.scenes[CITY]
    bpy.context.window.scene = city
    city.frame_set(city.frame_current)
    bpy.context.evaluated_depsgraph_get().update()
    return city


def target_objects():
    result = {o for o in bpy.data.objects if o.name.startswith('午门')}
    result.update(o for o in bpy.data.objects
                  if str(o.get('osm_id', o.get('source_osm_id', ''))) in COURTYARD_IDS
                  or any(o.name.endswith(' ' + ref) for ref in COURTYARD_IDS))
    for group in bpy.data.collections:
        if group.name.startswith('午门'):
            result.update(group.all_objects)
    return result


def mesh_signature(mesh):
    result = hashlib.sha256()
    for count, prop, collection_, dtype in (
            (len(mesh.vertices) * 3, 'co', mesh.vertices, np.float32),
            (len(mesh.loops), 'vertex_index', mesh.loops, np.int32),
            (len(mesh.polygons), 'material_index', mesh.polygons, np.int32)):
        values = np.empty(count, dtype=dtype)
        collection_.foreach_get(prop, values); result.update(values.tobytes())
    result.update(json.dumps([m.name if m else None for m in mesh.materials], ensure_ascii=False).encode())
    return result.hexdigest()


def fingerprint(names):
    combined = hashlib.sha256(); data_cache = {}; missing = []
    for name in sorted(names):
        obj = bpy.data.objects.get(name)
        if obj is None:
            missing.append(name); continue
        r = [name, obj.type, list(obj.location), list(obj.rotation_euler),
             list(obj.rotation_quaternion), list(obj.scale), obj.hide_render, obj.hide_viewport,
             obj.parent.name if obj.parent else None]
        if obj.type == 'MESH':
            key = obj.data.as_pointer()
            if key not in data_cache:
                data_cache[key] = mesh_signature(obj.data)
            r.extend((len(obj.data.vertices), len(obj.data.polygons), data_cache[key]))
        combined.update(json.dumps(r, ensure_ascii=False, separators=(',', ':')).encode())
    return dict(sha256=combined.hexdigest(), objects=len(names),
                distinct_meshes=len(data_cache), missing=missing)


def scene_state(scene):
    camera_ = scene.camera
    return dict(name=scene.name, objects=sorted(o.name for o in scene.objects),
                world=scene.world.name if scene.world else None,
                camera=camera_.name if camera_ else None, frames=[scene.frame_start, scene.frame_end],
                fps=scene.render.fps, units=[scene.unit_settings.system, scene.unit_settings.scale_length],
                view=[scene.view_settings.view_transform, scene.view_settings.look, scene.view_settings.exposure])


def local_scene(city, objects):
    scene = bpy.data.scenes.new(SCENE)
    template = bpy.data.scenes['内廷中路 · 乾清门至乾清宫']
    scene.world = template.world.copy(); scene.world.name = '午门修订 · 可调整的晴日天光'
    scene.unit_settings.system = 'METRIC'; scene.unit_settings.scale_length = 1.
    scene.view_settings.view_transform = 'AgX'; scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = .30
    sky = next((n for n in scene.world.node_tree.nodes if n.type == 'TEX_SKY'), None)
    background = next((n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND'), None)
    if sky:
        sky.sky_type = 'HOSEK_WILKIE'; sky.turbidity = 2.2; sky.ground_albedo = .18
    if background:
        background.inputs['Strength'].default_value = 3.0
    graph = bpy.context.evaluated_depsgraph_get()
    linked = []
    for obj in city.objects:
        if obj.hide_render or any(c.hide_render for c in obj.users_collection):
            continue
        if obj.type != 'MESH':
            continue
        if obj not in objects:
            evaluated = obj.evaluated_get(graph)
            # Evaluated matrices are required after switching scenes. The
            # original proxies can still report identity matrices in Blender.
            points = [evaluated.matrix_world @ Vector(p) for p in obj.bound_box]
            lo = [min(p[k] for p in points) for k in range(3)]
            hi = [max(p[k] for p in points) for k in range(3)]
            if hi[0] < -235 or lo[0] > 235 or hi[1] < -790 or lo[1] > -273:
                continue
        scene.collection.objects.link(obj); linked.append(obj.name)
    for src in city.objects:
        if src.type == 'LIGHT' and src.data.type == 'SUN':
            sunlight = src.copy(); sunlight.data = src.data.copy()
            sunlight.name = '午门修订 · 自然日光'
            sunlight.data.energy = 3.2; sunlight.data.angle = math.radians(.65)
            scene.collection.objects.link(sunlight)
            if sky:
                sky.sun_direction = sunlight.rotation_euler.to_matrix() @ Vector((0, 0, 1))
            break
    for key, (_, label, eye, aim, lens) in VIEWS.items():
        cam = camera(key + ' · ' + label, eye, aim, lens)
        # camera() links to the active city; a new local camera is not needed
        # in any inherited scene.
        for group in list(cam.users_collection):
            group.objects.unlink(cam)
        scene.collection.objects.link(cam)
        cam.data.clip_start = .025; cam.data.clip_end = 3000.
    scene.render.fps = FPS
    scene.frame_start = 1; scene.frame_end = FRAMES
    return scene, linked


def route(scene, store=True):
    bpy.context.window.scene = scene
    scene.frame_set(1)
    graph = bpy.context.evaluated_depsgraph_get()
    cached = collision_trees(scene, graph)
    print('WUMEN_ROUTE_COLLISION_MESHES', len(cached), flush=True)
    records = []; failed = []; positions = []
    x = -3.75
    for frame in range(1, FRAMES + 1):
        t = (frame - 1) / (FRAMES - 1)
        y = -506. + 60. * t
        foot = support_foot(cached, x, y)
        if not foot[0]:
            failed.append(dict(frame=frame, reason='No supporting mesh')); continue
        z = foot[1].z + EYE
        # Check centre, shoulders and a full view-height forward segment.
        obstructions = []
        for dx in (-.24, 0., .24):
            for zz in (.32, .92, EYE):
                origin = Vector((x + dx, y, foot[1].z + zz))
                hit = collision_ray(cached, origin, (0, 1, 0), .22)
                if hit[0]:
                    obstructions.append(hit[4].name)
        head = collision_ray(cached, (x, y, z), (0, 0, 1), .22)
        if head[0]:
            obstructions.append(head[4].name)
        # Transition from looking at the building to a level view through its
        # vault using a smooth gaze, while translation remains a steady walk.
        a = min(1., max(0., t / .30)); a = a * a * (3 - 2 * a)
        aim_z = (1 - a) * 11.5 + a * 2.25
        position = Vector((x, y, z))
        rotation = (Vector((x, y + 23., aim_z)) - position).to_track_quat('-Z', 'Y')
        positions.append((frame, position, rotation))
        records.append(dict(frame=frame, foot_z_m=round(foot[1].z, 6),
                            support=foot[4].name, eye_z_m=round(z, 6),
                            obstructions=obstructions))
        if obstructions:
            failed.append(dict(frame=frame, reason='Clearance obstruction', objects=sorted(set(obstructions))))
        if frame % 240 == 0:
            print('WUMEN_ROUTE_CHECKED', frame, '/', FRAMES, flush=True)
    if failed:
        dump(ROOT / 'wumen_failed_route_audit.json', dict(passed=False, failures=failed, frames=records))
        raise RuntimeError('The gate route is not clear: ' + str(failed[:3]))
    existing = bpy.data.objects.get(CAMERA)
    if store:
        if existing is not None:
            raise RuntimeError('A route camera already exists in this fresh revision.')
        data = bpy.data.cameras.new(CAMERA); data.lens = 27.; data.clip_start = .028; data.clip_end = 3000.
        obj = bpy.data.objects.new(CAMERA, data); scene.collection.objects.link(obj)
        obj.rotation_mode = 'QUATERNION'
        previous = None
        for frame, position, rotation in positions:
            if previous is not None and previous.dot(rotation) < 0:
                rotation.negate()
            obj.location = position; obj.rotation_quaternion = rotation
            obj.keyframe_insert(data_path='location', frame=frame)
            obj.keyframe_insert(data_path='rotation_quaternion', frame=frame)
            previous = rotation.copy()
        scene.camera = obj
        for frame, exposure in ((1, .30), (200, .30), (330, 2.4),
                                (650, 2.4), (800, .30), (FRAMES, .30)):
            scene.view_settings.exposure = exposure
            scene.keyframe_insert(data_path='view_settings.exposure', frame=frame)
        scene['photographic_adaptation'] = 'Smooth virtual exposure change from +0.30 to +2.40 stops inside the vault, selected from actual exposure-study renders; not a measurement of human vision.'
    else:
        if existing is None:
            raise RuntimeError('Saved gate animation is missing.')
        for frame, position, rotation in positions[::24] + positions[-1:]:
            scene.frame_set(frame)
            if (existing.location - position).length > .0001 or abs(existing.rotation_quaternion.dot(rotation)) < .99999:
                raise RuntimeError('Saved route differs from the geometry-audited route at frame ' + str(frame))
    scene.frame_set(1)
    audit = dict(passed=True, frames_checked=FRAMES, fps=FPS, seconds=FRAMES / FPS,
                  eye_height_m=EYE, path_length_m=60., shoulder_half_width_m=.24,
                  forward_probe_m=.22, head_clearance_m=.22,
                  support_footprint_m=[.16, .20], cached_collision_meshes=len(cached),
                  photographic_exposure_stops=[.30, 2.4],
                  support_z_range_m=[min(r['foot_z_m'] for r in records), max(r['foot_z_m'] for r in records)],
                  scope='Saved render-mesh support and sample clearances; not full human-body simulation or a surveyed public access route.',
                  frames=records)
    dump(ROOT / ('wumen_walkthrough_route_audit.json' if store else 'wumen_reopened_route_audit.json'), audit)
    return {k: v for k, v in audit.items() if k != 'frames'}


def build():
    started = time.monotonic(); city = open_base(BASE)
    initial = target_objects()
    initial_names = sorted(o.name for o in initial)
    protected_names = sorted(o.name for o in bpy.data.objects if o not in initial)
    print('WUMEN_PROTECTING', len(protected_names), flush=True)
    protected = fingerprint(protected_names)
    scenes = [scene_state(s) for s in bpy.data.scenes]
    old_palette = use_existing_palette(); p = materials(old_palette)
    changes = rematerialize(initial, old_palette, p)
    parent = bpy.data.collections['紫禁城 · EDITABLE 3D MASTER']
    group = collection(GROUP, parent)
    for obj in initial:
        if obj.name not in group.objects:
            group.objects.link(obj)
    site = Site()
    courtyard = build_courtyard(site, group, p)
    masonry = entrances(site, group, p)
    print('WUMEN_MASONRY_BUILT', flush=True)
    galleries = connectors(site, group, p)
    ridge_detail = build_ridge_detail(group, p, galleries)
    objects = set(group.all_objects)
    tones = tile_attributes(objects)
    print('WUMEN_GALLERIES_BUILT', len(objects), flush=True)
    bpy.context.view_layer.update()
    local, linked = local_scene(city, objects)
    animation = dict(route(local), frames_directory=FRAME_DIR.name)
    after = fingerprint(protected_names)
    if after != protected:
        raise RuntimeError('An object outside the Meridian Gate scope changed before saving.')
    meshes = [o for o in objects if o.type == 'MESH']
    report = dict(native_blend=MASTER.name, base_file=BASE.name, base_sha256=digest(BASE),
                  built_at=now(), inherited_scene_states=scenes,
                  protected_names=protected_names, protected_fingerprint=protected,
                  preserved_existing_wumen_objects=[name for name in initial_names if bpy.data.objects.get(name)],
                  rematerialized_objects=changes, masonry=masonry, connecting_galleries=galleries,
                  ridge_detail=ridge_detail, courtyard=courtyard,
                  ceramic_elements=tones, main_scene=CITY, walkthrough_scene=SCENE,
                  lighting=dict(sky_model='HOSEK_WILKIE', turbidity=2.2,
                                ground_albedo=.18, sky_strength=3.0, sun_energy=3.2,
                                exposure_stops=.30,
                                status='Virtual sunny-day interpretation, not dated site photometry.'),
                  walkthrough=animation, local_context_objects=len(linked),
                  wumen_meshes=len(meshes), native_polygons=sum(len(o.data.polygons) for o in meshes),
                  build_sources_sha256={name: digest(ROOT / 'source' / name)
                      for name in ('refine_wumen_scene.py', 'wumen_masonry.py', 'wumen_surfaces.py',
                                   'wumen_collision.py', 'wumen_roof_detail.py', 'wumen_courtyard.py',
                                   'city_roof_tiles.py')},
                  reference_manifest='source/references/wumen/sources.json',
                  reference_manifest_sha256=digest(ROOT / 'source/references/wumen/sources.json'),
                  whole_city_pixel_perfect_reconstruction_proven=False,
                  limits=['Published overall sizes are distinct from inferred members and photo-led surfaces.',
                          'The 1983 article gives a different total-height convention (37.95 m) from the current museum building page (35.6 m); no independent datum survey is available.',
                          'The existing nine-bay hall, four towers and thirteen-bay wing geometry are retained; this is an incremental revision, not a claim of complete measured timber reconstruction.',
                          'Square south mouths, bricks, doors, paint fissures and their exact sections remain interpretive.',
                          'Ridge ornaments use authored sculptural prototypes at inherited locations; the actual Wu Men carvings, dimensions and ceramic assembly joints have not been surveyed.',
                          'Outer eaves after the 2004 intervention and the older protected inner paint are not interchangeable; historic paint diagrams are retained as references, not indiscriminately pasted over the exterior.'])
    local.camera = bpy.data.objects[CAMERA]
    local.render.resolution_x = 1920; local.render.resolution_y = 1080
    configure_cycles(local); local.cycles.samples = 96; local.cycles.use_denoising = True
    local['reconstruction_status'] = 'Metric, reference-led incremental reconstruction; exact members and surface damage unmeasured.'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    pending = MASTER.with_name(MASTER.stem + '.pending.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(pending), compress=True)
    pending.replace(MASTER)
    report['master_sha256'] = digest(MASTER)
    report['build_elapsed_seconds'] = round(time.monotonic() - started, 3)
    dump(REPORT, report)
    print('WUMEN_BUILT', len(meshes), report['native_polygons'], MASTER.name, flush=True)


def verify():
    open_base(MASTER)
    report = json.loads(REPORT.read_text(encoding='utf-8')); checks = []
    def test(name, okay, evidence):
        checks.append(dict(check=name, passed=bool(okay), evidence=evidence))
    actual = fingerprint(report['protected_names'])
    test('Every pre-existing object outside the gate retains coordinates, topology, transforms and material slots',
         actual == report['protected_fingerprint'], actual)
    for prior in report['inherited_scene_states']:
        scene = bpy.data.scenes.get(prior['name'])
        state = scene_state(scene) if scene else None
        # The full city intentionally includes the newly built gate components.
        if state and prior['name'] == CITY:
            replaced = {n for r in report.get('ridge_detail', []) for n in r['replaced_ridge_objects']}
            replaced.update(r['object'] for r in report.get('courtyard', {}).get('removed_duplicate_proxies', []))
            prior = dict(prior, objects=[n for n in prior['objects'] if n not in replaced])
            retained = set(prior['objects'])
            state['objects'] = [n for n in state['objects'] if n in retained]
        test('Retained scene, camera, animation and lighting: ' + prior['name'], state == prior,
             dict(name=prior['name'], objects=len(scene.objects) if scene else None))
    group = bpy.data.collections[GROUP]
    for row in report['ceramic_elements']:
        mesh = bpy.data.objects[row['object']].data
        attr = mesh.attributes.get(ATTR)
        test('Intact editable roof geometry and element tone: ' + row['object'],
             digest_geometry(mesh) == row['vertex_geometry_sha256'] and attr is not None
             and attr.domain == 'FACE' and len(attr.data) == len(mesh.polygons),
             dict(faces=len(mesh.polygons), elements=row['native_ceramic_elements']))
    scene = bpy.data.scenes[SCENE]; bpy.context.window.scene = scene
    scene.frame_set(1); graph = bpy.context.evaluated_depsgraph_get()
    cached = collision_trees(scene, graph)
    pad = next(o for o in group.all_objects if o.get('role') == 'wumen_published_hall_plinth')
    vv = np.empty(len(pad.data.vertices) * 3, dtype=np.float32); pad.data.vertices.foreach_get('co', vv)
    extents = np.ptp(vv.reshape(-1, 3), axis=0)
    test('Published exposed plinth plan is 61.97 by 27.97 metres',
         abs(float(extents[0]) - 61.97) < .0001 and abs(float(extents[1]) - 27.97) < .0001,
         extents.tolist())
    door_count = sum(o.get('role') == 'wumen_hinged_gate_leaf' for o in group.all_objects)
    test('Three south mouths each retain two independently editable hinged leaves', door_count == 6, door_count)
    test('Both missing connectors have three documented bays',
         len(report['connecting_galleries']) == 2 and all(r['bays'] == 3 for r in report['connecting_galleries']),
         report['connecting_galleries'])
    test('Metric local scene', scene.unit_settings.system == 'METRIC' and scene.unit_settings.scale_length == 1.,
         scene.unit_settings.scale_length)
    courtyard = report.get('courtyard', {})
    test('Both duplicate forecourt context shells removed while original palace meshes remain',
         len(courtyard.get('removed_duplicate_proxies', [])) == 2
         and all(bpy.data.objects.get(r['object']) is None
                 and bpy.data.objects.get(r['retained_palace_object']) is not None
                 for r in courtyard.get('removed_duplicate_proxies', [])),
         courtyard.get('removed_duplicate_proxies', []))
    for row in courtyard.get('revised_annexes', []):
        annex = bpy.data.objects[row['object']]
        carrier = bpy.data.objects[row['tile_carrier']]
        test('Forecourt annex retains mapped envelope and native yellow-tile instances: ' + row['osm_id'],
             digest_geometry(annex.data) == row['geometry_sha256']
             and carrier.get('tile_module_count') == row['tile_modules'] > 0
             and not any('灰瓦屋面' in m.name or '城砖' in m.name for m in annex.data.materials if m),
             dict(geometry_sha256=digest_geometry(annex.data), modules=carrier.get('tile_module_count')))
    route_audit = route(scene, store=False)
    test('All 960 saved route positions have support and sampled body/head clearance', route_audit['passed'], route_audit)
    # Recheck all five historic paths, including each segment of both doglegs.
    segments = [((-16.58, -489., 1.3), (-16.58, -453., 1.3)),
                ((-3.75, -489., 1.3), (-3.75, -453., 1.3)),
                ((9.96, -489., 1.3), (9.96, -453., 1.3)),
                ((-41.8, -492.6, 1.3), (-53.5, -492.6, 1.3)),
                ((-53.5, -492.6, 1.3), (-53.5, -453., 1.3)),
                ((36.9, -492.6, 1.3), (48.5, -492.6, 1.3)),
                ((48.5, -492.6, 1.3), (48.5, -453., 1.3))]
    results = []
    for a, c in segments:
        origin, delta = Vector(a), Vector(c) - Vector(a)
        hit = collision_ray(cached, origin, delta.normalized(), delta.length)
        results.append(dict(start=a, end=c, clear=not hit[0], blocker=hit[4].name if hit[0] else None))
    test('Three straight routes and both turned routes remain unobstructed', all(r['clear'] for r in results), results)
    missing = [im.name for im in bpy.data.images if im.source == 'FILE' and im.type != 'RENDER_RESULT'
               and not im.packed_file and not Path(bpy.path.abspath(im.filepath)).is_file()]
    test('No missing external image dependencies', not missing, missing)
    changed = [name for name, value in report['build_sources_sha256'].items()
               if digest(ROOT / 'source' / name) != value]
    test('Model and saved revision scripts agree', not changed, changed)
    result = dict(file=MASTER.name, master_sha256=digest(MASTER), validated_at=now(),
                  passed=all(c['passed'] for c in checks), checks=checks)
    dump(VALIDATION, result)
    if not result['passed']:
        raise RuntimeError('Gate verification failed: ' + str([r['check'] for r in checks if not r['passed']]))
    print('WUMEN_VERIFIED', len(checks), flush=True)


def render_config(scene, args):
    bpy.context.window.scene = scene
    configure_cycles(scene)
    scene.cycles.samples = args.samples; scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 9; scene.cycles.diffuse_bounces = 5; scene.cycles.glossy_bounces = 4
    if scene.cycles.device == 'GPU':
        scene.cycles.denoiser = 'OPTIX'
    scene.render.resolution_x = args.width; scene.render.resolution_y = round(args.width * 9 / 16)
    scene.render.resolution_percentage = 100; scene.render.use_persistent_data = True
    scene.render.image_settings.file_format = 'PNG'; scene.render.image_settings.color_mode = 'RGB'


def render_views(args, baseline=False):
    if baseline:
        city = open_base(BASE); scene, _ = local_scene(city, target_objects())
    else:
        open_base(MASTER); scene = bpy.data.scenes[SCENE]
    render_config(scene, args)
    for key in args.views.split(','):
        scene.camera = next(o for o in scene.objects if o.type == 'CAMERA' and o.name.startswith(key + ' · '))
        scene.view_settings.exposure = 2.4 if key == '107' else 1.8 if key == '114' else .30
        path = ROOT / 'renders' / f'{key}_{VIEWS[key][0]}_{args.suffix}.png'
        pending = path.with_suffix('.pending.png'); scene.render.filepath = str(pending)
        started = time.monotonic(); bpy.ops.render.render(write_still=True); pending.replace(path)
        dump(path.with_suffix('.render.json'), dict(master_file=(BASE if baseline else MASTER).name,
             master_sha256=digest(BASE if baseline else MASTER), camera=scene.camera.name,
             width=args.width, height=scene.render.resolution_y, engine='CYCLES', device=scene.cycles.device,
             samples=args.samples, image_sha256=digest(path), completed_at=now(),
             exposure_stops=scene.view_settings.exposure,
             elapsed_seconds=round(time.monotonic() - started, 3)))
        print('WUMEN_STILL', path.name, flush=True)


def render_tour(args):
    open_base(MASTER); scene = bpy.data.scenes[SCENE]; render_config(scene, args)
    scene.camera = bpy.data.objects[CAMERA]
    frames = list(range(1, FRAMES + 1)) if args.frames == 'all' else [int(f) for f in args.frames.split(',')]
    folder = FRAME_DIR if args.frames == 'all' else FRAME_DIR.with_name(FRAME_DIR.name + '_' + args.suffix)
    folder.mkdir(parents=True, exist_ok=True)
    job = dict(master_file=MASTER.name, master_sha256=digest(MASTER), width=args.width,
                height=scene.render.resolution_y, samples=args.samples, fps=FPS,
                frames_total=FRAMES, engine='CYCLES', device=scene.cycles.device,
                route_audit_sha256=digest(ROOT / 'wumen_walkthrough_route_audit.json'))
    job_path = folder / 'render_job.json'
    if job_path.exists() and json.loads(job_path.read_text(encoding='utf-8')) != job:
        raise RuntimeError('The frame folder contains a different model or render configuration.')
    dump(job_path, job)
    for frame in frames:
        path = folder / f'{frame:04}.png'
        if path.exists() and path.stat().st_mtime >= MASTER.stat().st_mtime:
            continue
        scene.frame_set(frame)
        pending = path.with_suffix('.pending.png'); scene.render.filepath = str(pending)
        bpy.ops.render.render(write_still=True); pending.replace(path)
        print('WUMEN_FRAME', frame, '/', FRAMES, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('baseline', 'build', 'verify', 'stills', 'tour'))
    parser.add_argument('--views', default='103,104,105,106,107,108,109,110,111,112,113,114')
    parser.add_argument('--width', type=int, default=1600)
    parser.add_argument('--samples', type=int, default=40)
    parser.add_argument('--suffix', default='wumen_review_v1')
    parser.add_argument('--frames', default='1,180,360,480,600,780,960')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if args.mode == 'build': return build()
    if args.mode == 'verify': return verify()
    if args.mode in ('baseline', 'stills'): return render_views(args, args.mode == 'baseline')
    return render_tour(args)


if __name__ == '__main__':
    main()
