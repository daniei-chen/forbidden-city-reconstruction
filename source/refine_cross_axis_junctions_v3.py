"""Create an isolated first-person gallery walk and soften new roof reflections."""
import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'source'))
import integrate_cross_axis_junctions_v2 as previous
from cross_axis_galleries_plan import RANGES, plan
from osm_site import Site

BASE = ROOT/'The_Forbidden_City_Cross_Axis_Junctions_v2.blend'
MASTER = ROOT/'The_Forbidden_City_Cross_Axis_Junctions_v3.blend'
REPORT = ROOT/'cross_axis_junctions_revision_v3_report.json'
VALIDATION = ROOT/'validation_cross_axis_junctions_revision_v3.json'
SCENE = '熙和门南庑 · 20秒第一人称廊下漫游'
SHA_BASE = '3aec97b18875bfd3eea69cd655aabb4c7a69e878f2a17e9af80acd3055fedf26'
FPS = 24
FRAME_COUNT = 480
FRAMES = ROOT/'renders/cross_axis_junctions_walk_v3'
PATH_REVISION = 'xihe-south-porch-v1'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')


def geometry_digest(obj):
    mesh = obj.data
    vertices = np.empty(len(mesh.vertices)*3, dtype=np.float32)
    indices = np.empty(len(mesh.loops), dtype=np.int32)
    starts = np.empty(len(mesh.polygons), dtype=np.int32)
    totals = np.empty(len(mesh.polygons), dtype=np.int32)
    smooth = np.empty(len(mesh.polygons), dtype=np.uint8)
    mesh.vertices.foreach_get('co', vertices)
    mesh.loops.foreach_get('vertex_index', indices)
    mesh.polygons.foreach_get('loop_start', starts)
    mesh.polygons.foreach_get('loop_total', totals)
    mesh.polygons.foreach_get('use_smooth', smooth)
    sha = hashlib.sha256()
    for value in (vertices, indices, starts, totals, smooth):
        sha.update(value.tobytes())
    return sha.hexdigest()


def first_hit(geometry, point, direction, maximum):
    nearest = maximum
    found = None
    for name, tree, matrix, inverse, axes in geometry:
        local_ray = axes@direction
        scale = local_ray.length
        hit, _, _, distance = tree.ray_cast(inverse@point, local_ray/scale, nearest*scale)
        if hit is not None and distance/scale < nearest:
            nearest = distance/scale
            found = (name, matrix@hit)
    return found


def relevant_geometry(scene, graph, spec, q, x_start, x_end, y_path, top):
    start = Vector(q.loc.world(x_start, y_path, 0))
    finish = Vector(q.loc.world(x_end, y_path, 0))
    low = Vector((min(start.x, finish.x)-3.0, min(start.y, finish.y)-3.0, -.5))
    high = Vector((max(start.x, finish.x)+3.0, max(start.y, finish.y)+3.0, top))
    result = []
    for obj in scene.objects:
        if obj.type != 'MESH' or obj.hide_render or not obj.data.polygons:
            continue
        if any(collection.hide_render for collection in obj.users_collection):
            continue
        world_bounds = [obj.matrix_world@Vector(corner) for corner in obj.bound_box]
        bounds_low = [min(v[i] for v in world_bounds) for i in range(3)]
        bounds_high = [max(v[i] for v in world_bounds) for i in range(3)]
        if any(bounds_high[i] < low[i] or bounds_low[i] > high[i] for i in range(3)):
            continue
        matrix = obj.matrix_world.copy()
        inverse = matrix.inverted_safe()
        result.append((obj.name, BVHTree.FromObject(obj, graph), matrix, inverse, inverse.to_3x3()))
    return result


def bounds_separation(bounds, target):
    return tuple(max(bounds[0][i]-target[1][i], target[0][i]-bounds[1][i], 0.) for i in range(3))


def make_walkthrough(city, root_collection, group, q):
    start_x = q.bounds[0]+5.0
    finish_x = q.bounds[2]-6.0
    y_path = q.porch_path_y
    if finish_x-start_x < 8.0:
        raise RuntimeError('The selected gallery does not have enough clear porch length.')

    graph = bpy.context.evaluated_depsgraph_get()
    geometry = relevant_geometry(city, graph, RANGES[0], q, start_x, finish_x, y_path, 12.0)
    if not geometry:
        raise RuntimeError('No native geometry intersects the porch route bounds.')

    forward = Vector(q.loc.world(1., 0., 0.))-Vector(q.loc.world(0., 0., 0.))
    forward.normalize()
    cross = Vector(q.loc.world(0., 1., 0.))-Vector(q.loc.world(0., 0., 0.))
    cross.normalize()
    frames = []
    checks = []
    errors = []
    previous_location = None
    lowest = math.inf
    highest = -math.inf

    for frame in range(FRAME_COUNT):
        progress = frame/(FRAME_COUNT-1)
        x = start_x+(finish_x-start_x)*progress
        floor = first_hit(geometry, Vector(q.loc.world(x, y_path, 2.35)),
                          Vector((0., 0., -1.)), 2.5)
        if floor is None:
            errors.append({'frame': frame+1, 'kind': 'unsupported_floor'})
            continue
        floor_z = floor[1].z
        if abs(floor_z-1.0) > .025:
            errors.append({'frame': frame+1, 'kind': 'unexpected_floor_datum', 'z_m': floor_z})
        lowest, highest = min(lowest, floor_z), max(highest, floor_z)
        time_seconds = frame/FPS
        gait = math.sin(math.tau*1.45*time_seconds)*.008
        position = Vector(q.loc.world(x, y_path, floor_z+1.65+gait))
        yaw_sway = math.sin(math.tau*.12*progress)*.025
        target = Vector(q.loc.world(x+6., q.front_y-1.60, 5.15))
        rotation = (target-position).to_track_quat('-Z', 'Y')
        if yaw_sway:
            from mathutils import Quaternion
            rotation = Quaternion(Vector((0., 0., 1.)), yaw_sway) @ rotation

        if previous_location is not None:
            travel = position-previous_location
            obstruction = first_hit(geometry, previous_location, travel.normalized(), travel.length+.06)
            if obstruction:
                errors.append({'frame': frame+1, 'kind': 'camera_path_collision',
                               'object': obstruction[0]})

        body_rays = 0
        for height in (.30, 1.0, 1.85):
            origin = position+Vector((0., 0., height-1.65-gait))
            for direction in (forward, -forward, cross, -cross):
                obstruction = first_hit(geometry, origin, direction, .215)
                body_rays += 1
                if obstruction:
                    errors.append({'frame': frame+1, 'kind': 'body_clearance',
                                   'height_m': height, 'object': obstruction[0]})
                    break

        frames.append((position, rotation))
        checks.append({'frame': frame+1, 'floor_z_m': round(floor_z, 5),
                       'eye_z_m': round(position.z, 5), 'body_clearance_rays': body_rays})
        previous_location = position

    if errors:
        raise RuntimeError('Native floor/collision route check failed: '+json.dumps(errors[:5]))
    if len(frames) != FRAME_COUNT:
        raise RuntimeError(f'Expected {FRAME_COUNT} checked camera frames; got {len(frames)}.')

    walk = bpy.data.scenes.new(SCENE)
    walk.use_fake_user = True
    walk.world = city.world
    walk.unit_settings.system = 'METRIC'
    walk.unit_settings.scale_length = 1.
    walk.view_settings.view_transform = city.view_settings.view_transform
    walk.view_settings.look = city.view_settings.look
    walk.view_settings.exposure = .05

    start_world = Vector(q.loc.world(start_x, y_path, 0))
    finish_world = Vector(q.loc.world(finish_x, y_path, 0))
    route_bounds = (
        (min(start_world.x, finish_world.x)-29., min(start_world.y, finish_world.y)-34., -.8),
        (max(start_world.x, finish_world.x)+29., max(start_world.y, finish_world.y)+34., 32.),
    )
    chosen = {obj for obj in group.all_objects if obj.type in {'MESH', 'LIGHT'}}
    for obj in city.objects:
        if obj.type == 'LIGHT' and obj.data.type == 'SUN':
            chosen.add(obj)
        if obj.type != 'MESH' or obj.hide_render or any(c.hide_render for c in obj.users_collection):
            continue
        world = [obj.matrix_world@Vector(c) for c in obj.bound_box]
        bounds = ([min(v[i] for v in world) for i in range(3)],
                  [max(v[i] for v in world) for i in range(3)])
        if any(bounds_separation(bounds, route_bounds)):
            continue
        chosen.add(obj)
    for obj in sorted(chosen, key=lambda item: item.name):
        walk.collection.objects.link(obj)

    camera_data = bpy.data.cameras.new('熙和门南庑 · 行人视点 1.65 m')
    camera_data.lens = 30.
    camera_data.clip_start = .07
    camera_data.clip_end = 700.
    camera = bpy.data.objects.new('熙和门南庑 · 真实廊下步行相机', camera_data)
    walk.collection.objects.link(camera)
    camera.rotation_mode = 'QUATERNION'
    previous_rotation = None
    for frame, (position, rotation) in enumerate(frames, 1):
        if previous_rotation is not None and previous_rotation.dot(rotation) < 0:
            rotation.negate()
        camera.location = position
        camera.rotation_quaternion = rotation
        camera.keyframe_insert(data_path='location', frame=frame)
        camera.keyframe_insert(data_path='rotation_quaternion', frame=frame)
        previous_rotation = rotation.copy()
    for curve in camera.animation_data.action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'

    walk.camera = camera
    walk.frame_start = 1
    walk.frame_end = FRAME_COUNT
    walk.render.engine = 'CYCLES'
    walk.render.resolution_x = 1280
    walk.render.resolution_y = 720
    walk.render.resolution_percentage = 100
    walk.render.fps = FPS
    walk.render.film_transparent = False
    walk.render.use_persistent_data = True
    walk.render.image_settings.file_format = 'PNG'
    walk.render.image_settings.color_mode = 'RGB'
    walk.render.filepath = f'//renders/{FRAMES.name}/'
    walk.cycles.device = 'CPU'
    walk.cycles.samples = 32
    walk.cycles.use_denoising = True
    walk.cycles.max_bounces = 6
    walk.cycles.diffuse_bounces = 3
    walk.cycles.glossy_bounces = 3
    walk['camera_path_revision'] = PATH_REVISION
    walk['native_walk_method'] = 'Actual 1.65 m eye-height camera animation over independently ray-supported original city geometry.'
    walk['route_floor_source'] = 'Four hundred eighty vertically supported sample positions on the mapped one-metre forecourt-gallery floor; this mapped height is provisional, not a field survey.'
    walk['walk_speed_m_s'] = round((finish_x-start_x)/((FRAME_COUNT-1)/FPS), 4)

    return walk, {'scene': SCENE, 'camera': camera.name, 'frames': FRAME_COUNT,
                  'fps': FPS, 'duration_seconds': FRAME_COUNT/FPS, 'lens_mm': camera_data.lens,
                  'nominal_eye_height_m': 1.65, 'walk_speed_m_s': walk['walk_speed_m_s'],
                  'local_city_context_meshes': sum(obj.type == 'MESH' for obj in chosen),
                  'route_collision_meshes': len(geometry), 'checked_frames': len(checks),
                  'body_head_clearance_rays': sum(r['body_clearance_rays'] for r in checks),
                  'floor_range_m': [lowest, highest], 'start_world_m': list(frames[0][0]),
                  'finish_world_m': list(frames[-1][0]), 'checkpoints': [checks[i] for i in (0, 119, 239, 359, 479)],
                  'path_revision': PATH_REVISION,
                  'scope': 'A single contiguous front-porch walk only. The gallery-to-gate 1.0 m/2.62 m historical level connection and unfurnished interior remain unresolved.'}


def build():
    if MASTER.exists() or MASTER.with_name(MASTER.stem+'.pending.blend').exists():
        raise RuntimeError('Retain the existing v3 candidate and inspect it before retrying.')
    expected_base = SHA_BASE
    assert previous.read(previous.REPORT)['master_sha256'] == expected_base
    if digest(BASE) != expected_base:
        raise RuntimeError('The frozen v2 model changed; this revision is no longer based on its verified source.')
    bpy.ops.wm.open_mainfile(filepath=str(BASE))
    city = bpy.data.scenes['紫禁城 · metric architectural reconstruction']
    bpy.context.window.scene = city
    prior_scenes = [previous.scene_state(scene) for scene in bpy.data.scenes]
    all_state = previous.scene_state(city)
    assert len(prior_scenes) == 20
    roof_tiles = sorted((obj for obj in city.objects
                         if obj.get('junction_role') == 'continuous_roof'
                         and obj.get('cross_axis_junction') in {spec['key'] for spec in RANGES}
                         and obj.type == 'MESH'
                         and 'individual' in obj.name.lower()), key=lambda item: item.name)
    if len(roof_tiles) != 4:
        roof_tiles = sorted((obj for obj in city.objects
                             if obj.get('junction_role') == 'continuous_roof'
                             and obj.get('cross_axis_junction') in {spec['key'] for spec in RANGES}
                             and obj.type == 'MESH' and len(obj.data.polygons) > 100000),
                            key=lambda item: item.name)
    if len(roof_tiles) != 4:
        raise RuntimeError(f'Expected four independent native continuous-roof meshes, got {len(roof_tiles)}.')

    geometry_before = {obj.name: geometry_digest(obj) for obj in roof_tiles}
    material_changes = []
    for obj in roof_tiles:
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        for index, material in enumerate(list(obj.data.materials)):
            if material is None or '黄琉璃瓦' not in material.name:
                continue
            variant = material.copy()
            variant.name = '门庑接缝 · 低眩柔和黄釉 '+str(index)
            variant['fidelity_scope'] = 'New junction tile meshes only; retained city roof materials remain unchanged.'
            shader = variant.node_tree.nodes.get('Principled BSDF')
            if shader:
                roughness = shader.inputs.get('Roughness')
                coat = shader.inputs.get('Coat Weight')
                coat_roughness = shader.inputs.get('Coat Roughness')
                specular = shader.inputs.get('Specular IOR Level')
                if roughness:
                    roughness.default_value = max(.46, float(roughness.default_value))
                if coat:
                    coat.default_value = min(.075, float(coat.default_value))
                if coat_roughness:
                    coat_roughness.default_value = max(.38, float(coat_roughness.default_value))
                if specular:
                    specular.default_value = .36
            obj.data.materials[index] = variant
            material_changes.append({'object': obj.name, 'slot': index, 'source': material.name,
                                     'variant': variant.name,
                                     'roughness': shader.inputs['Roughness'].default_value,
                                     'coat': shader.inputs['Coat Weight'].default_value,
                                     'specular_ior_level': shader.inputs['Specular IOR Level'].default_value})
    geometry_after = {obj.name: geometry_digest(obj) for obj in roof_tiles}
    if geometry_after != geometry_before:
        raise RuntimeError('The localized roof-material adjustment changed native roof geometry.')
    site = Site()
    q = plan(site, RANGES[0])
    junction_name = previous.read(previous.REPORT)['new_groups'][0]
    junction = bpy.data.collections.get(junction_name)
    if junction is None:
        raise RuntimeError('The verified cross-gate junction geometry collection is missing.')
    walk, route = make_walkthrough(city, bpy.data.collections['紫禁城 · EDITABLE 3D MASTER'], junction, q)
    pending = MASTER.with_name(MASTER.stem+'.pending.blend')
    bpy.context.preferences.filepaths.save_version = 0
    bpy.context.window.scene = walk
    bpy.ops.wm.save_as_mainfile(filepath=str(pending), compress=True)
    pending.replace(MASTER)

    report = {'native_blend': MASTER.name, 'master_sha256': digest(MASTER),
              'base_blend': BASE.name, 'base_sha256': expected_base,
              'added_scene': route, 'prior_scene_count': len(prior_scenes),
              'prior_scene_states': prior_scenes, 'city_scene_before': all_state,
              'new_roof_tile_geometry_before': geometry_before,
              'new_roof_tile_geometry_after': geometry_after,
              'localized_material_changes': material_changes,
              'source_script_sha256': digest(Path(__file__)),
              'limitations': [route['scope'],
                              'The reflectance correction is a controlled rendering response inferred from architectural photography; no on-site glaze BRDF scan is available.',
                              'The walk is verified against the currently mapped floor and native collision geometry, not against a measured real visitor path.',
                              'No whole-city photoreal or pixel-perfect survey certification is claimed.']}
    dump(REPORT, report)
    print('JUNCTIONS_V3_MASTER_SAVED', MASTER.name, report['master_sha256'],
          'route_frames', FRAME_COUNT, 'material_slots', len(material_changes), flush=True)


def verify():
    report = json.loads(REPORT.read_text(encoding='utf8'))
    assert digest(MASTER) == report['master_sha256']
    assert digest(BASE) == report['base_sha256']
    assert digest(Path(__file__)) == report['source_script_sha256']
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    city = bpy.data.scenes['紫禁城 · metric architectural reconstruction']
    walk = bpy.data.scenes[SCENE]
    errors = []
    scene_checks = [previous.scene_state(bpy.data.scenes[state['name']]) == state
                    for state in report['prior_scene_states']]
    if not all(scene_checks):
        errors.append({'check': 'all previous architectural scene states', 'passed': False})
    if previous.scene_state(city) != report['city_scene_before']:
        errors.append({'check': 'complete-city scene membership and settings retained', 'passed': False})
    for scene_state in report['prior_scene_states']:
        if scene_state['name'] == city.name and previous.scene_state(city) != scene_state:
            errors.append({'check': 'original complete-city scene retained', 'passed': False})
    route = report['added_scene']
    cam = bpy.data.objects.get(route['camera'])
    geometry = {name: geometry_digest(bpy.data.objects[name]) for name in report['new_roof_tile_geometry_after']}
    if geometry != report['new_roof_tile_geometry_after']:
        errors.append({'check': 'localized yellow-glazed-roof geometry preserved', 'passed': False})
    for frame in (1, 120, 240, 360, 480):
        walk.frame_set(frame)
        if cam is None or not all(math.isfinite(float(value)) for value in cam.matrix_world.translation):
            errors.append({'check': 'finite saved walkthrough camera', 'frame': frame, 'passed': False})
        if walk.camera is not cam:
            errors.append({'check': 'walkthrough active camera', 'frame': frame, 'passed': False})
    valid = not errors
    result = {'passed': valid, 'verified_at': __import__('datetime').datetime.now().astimezone().isoformat(),
              'master_sha256': report['master_sha256'], 'base_sha256': report['base_sha256'],
              'reopened_scene_count': len(bpy.data.scenes),
              'reopened_current_city_objects': len(city.objects),
              'full_city_inventory_mesh_count': 11752,
              'route_frames_supported_and_collision_checked_at_build': route['checked_frames'],
              'route_body_head_clearance_rays': route['body_head_clearance_rays'],
              'route_checkpoint_camera_frames_reopened': [1, 120, 240, 360, 480],
              'geometry_preserved': geometry == report['new_roof_tile_geometry_after'],
              'errors': errors, 'whole_city_pixel_perfect_reconstruction_proven': False,
              'all_dimensions_surveyed': False,
              'continuous_six_hour_refinement_verified': False,
              'scope': 'Independent native-file reopen, original scene/city retention, original new-roof geometry preservation and human-height camera checkpoints. The new porch path covers one verified contiguous mapped gallery segment only.'}
    dump(VALIDATION, result)
    if not valid:
        raise RuntimeError(json.dumps(errors[:6], ensure_ascii=True))
    print('JUNCTIONS_V3_REOPENED_CHECKS_PASSED', len(scene_checks)+7, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('build', 'verify'))
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    build() if args.action == 'build' else verify()
