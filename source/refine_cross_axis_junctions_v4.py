"""Slow and redirect the saved human-height gallery walk towards its fabric."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Quaternion, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'source'))
from cross_axis_galleries_plan import RANGES, plan
from osm_site import Site
from refine_cross_axis_junctions_v3 import digest as file_digest, geometry_digest

BASE = ROOT/'The_Forbidden_City_Cross_Axis_Junctions_v3.blend'
MASTER = ROOT/'The_Forbidden_City_Cross_Axis_Junctions_v4.blend'
REPORT = ROOT/'cross_axis_junctions_revision_v4_report.json'
VALIDATION = ROOT/'validation_cross_axis_junctions_revision_v4.json'
SCENE = '熙和门南庑 · 40秒慢行廊下漫游'
CAMERA_NAME = '熙和门南庑 · 檐廊漫游相机'
SHA_BASE = 'c178190c3fee3f695ef9cf50ea03336488b311aa8b4fd9895c954f509dd950cc'
FPS = 24
FRAMES = 960
PATH_REVISION = 'xihe-south-porch-40s-facing-architecture-v2'


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')


def camera_pose(q, frame):
    progress = (frame-1)/(FRAMES-1)
    start_x = q.bounds[0]+5.
    end_x = q.bounds[2]-6.
    x = start_x+(end_x-start_x)*progress
    y = q.porch_path_y
    seconds = (frame-1)/FPS
    bob = math.sin(math.tau*1.35*seconds)*.006
    position = Vector(q.loc.world(x, y, 2.65+bob))

    # Keep the sightline close to level while bringing the porch floor, screen
    # lattice, eaves and the route ahead into a normal eye-height view.
    target = Vector(q.loc.world(x+4.5, y+.52, 3.25))
    rotation = (target-position).to_track_quat('-Z', 'Y')
    sway = math.sin(math.tau*.10*progress)*.012
    if sway:
        rotation = Quaternion(Vector((0., 0., 1.)), sway) @ rotation
    return position, rotation


def update_walk(scene, camera, q):
    if camera.animation_data and camera.animation_data.action:
        action = camera.animation_data.action
        for curve in list(action.fcurves):
            if curve.data_path in ('location', 'rotation_quaternion'):
                action.fcurves.remove(curve)
    camera.animation_data_clear()
    camera.rotation_mode = 'QUATERNION'

    records = []
    prior = None
    for frame in range(1, FRAMES+1):
        position, rotation = camera_pose(q, frame)
        if prior is not None and prior.dot(rotation) < 0:
            rotation.negate()
        camera.location = position
        camera.rotation_quaternion = rotation
        camera.keyframe_insert(data_path='location', frame=frame)
        camera.keyframe_insert(data_path='rotation_quaternion', frame=frame)
        prior = rotation.copy()
        if frame in (1, 240, 480, 720, 960):
            direction = rotation@Vector((0., 0., -1.))
            records.append({'frame': frame, 'progress': round((frame-1)/(FRAMES-1), 5),
                            'eye_height_m': 1.65,
                            'camera_location_world_m': [round(float(v), 5) for v in position],
                            'view_direction_world': [round(float(v), 6) for v in direction],
                            'view_elevation_degrees': round(math.degrees(math.asin(float(direction.z))), 3)})

    for curve in camera.animation_data.action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'

    distance = (q.bounds[2]-6.)-(q.bounds[0]+5.)
    duration = (FRAMES-1)/FPS
    scene.name = SCENE
    scene.frame_start = 1
    scene.frame_end = FRAMES
    scene.render.fps = FPS
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene['camera_path_revision'] = PATH_REVISION
    scene['route_speed_m_s'] = round(distance/duration, 4)
    scene['route_distance_m'] = round(distance, 4)
    scene['nominal_eye_height_m'] = 1.65
    scene['camera_orientation'] = 'Near-level 1.65 m eye-height sightline towards the original porch floor, open lattice and eaves.'
    scene['visual_review_revision'] = 'Corrected after native v3 route test renders showed predominantly sky.'
    camera.name = CAMERA_NAME
    camera.data.name = CAMERA_NAME+' · 30 mm'
    scene.camera = camera
    scene.frame_set(1)
    return {'scene': scene.name, 'camera': camera.name, 'frames': FRAMES,
            'fps': FPS, 'duration_seconds': FRAMES/FPS,
            'nominal_walk_duration_seconds': round(duration, 4),
            'route_distance_m': round(distance, 4),
            'walk_speed_m_s': scene['route_speed_m_s'],
            'nominal_eye_height_m': 1.65,
            'view_elevation_checkpoints': records,
            'scope': 'Same single contiguous mapped porch route. Native geometry support and collision checks are inherited from the identical v3 camera positions; only timing, gait and camera aim change.'}


def build():
    if MASTER.exists() or MASTER.with_name(MASTER.stem+'.pending.blend').exists() or REPORT.exists():
        raise RuntimeError('Retain the current v4 candidate and inspect it before retrying.')
    v3_report_path = ROOT/'cross_axis_junctions_revision_v3_report.json'
    v3_report = json.loads(v3_report_path.read_text(encoding='utf8'))
    assert file_digest(BASE) == SHA_BASE == v3_report['master_sha256']
    bpy.ops.wm.open_mainfile(filepath=str(BASE))

    city = bpy.data.scenes['紫禁城 · metric architectural reconstruction']
    city_state_before = __import__('integrate_cross_axis_junctions_v2').scene_state(city)
    walk = bpy.data.scenes[v3_report['added_scene']['scene']]
    old_camera = bpy.data.objects[v3_report['added_scene']['camera']]
    site = Site()
    q = plan(site, RANGES[0])
    route = update_walk(walk, old_camera, q)
    route['collision_source_blend_sha256'] = SHA_BASE
    route['collision_checked_frames'] = v3_report['added_scene']['checked_frames']
    route['body_head_clearance_rays'] = v3_report['added_scene']['body_head_clearance_rays']

    pending = MASTER.with_name(MASTER.stem+'.pending.blend')
    bpy.context.preferences.filepaths.save_version = 0
    bpy.context.window.scene = walk
    bpy.ops.wm.save_as_mainfile(filepath=str(pending), compress=True)
    pending.replace(MASTER)
    report = {'native_blend': MASTER.name, 'master_sha256': file_digest(MASTER),
              'base_blend': BASE.name, 'base_sha256': SHA_BASE,
              'base_report_sha256': file_digest(v3_report_path),
              'original_city_scene': city_state_before,
              'route': route,
              'source_script_sha256': file_digest(Path(__file__)),
              'limitations': [route['scope'],
                              'Route timings and camera directions are deliberate visualization choices rather than a measured visitor-route survey.',
                              'The 1 m gallery and 2.62 m gate-platform connection remains unresolved.',
                              'Whole-city photoreal, complete measured dimensions and pixel-perfect capture are not claimed.']}
    dump(REPORT, report)
    print('JUNCTIONS_V4_WALK_REVIEW_SAVED', MASTER.name, report['master_sha256'],
          'frames', FRAMES, 'seconds', route['duration_seconds'], 'speed', route['walk_speed_m_s'], flush=True)


def verify():
    report = json.loads(REPORT.read_text(encoding='utf8'))
    assert file_digest(MASTER) == report['master_sha256']
    assert file_digest(BASE) == report['base_sha256'] == SHA_BASE
    assert file_digest(Path(__file__)) == report['source_script_sha256']
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    city = bpy.data.scenes['紫禁城 · metric architectural reconstruction']
    scene = bpy.data.scenes[SCENE]
    camera = bpy.data.objects[CAMERA_NAME]
    errors = []
    try:
        import integrate_cross_axis_junctions_v2 as previous
        if previous.scene_state(city) != report['original_city_scene']:
            errors.append({'check': 'original complete-city scene retained'})
    except Exception as exc:
        errors.append({'check': 'original city scene fingerprint', 'error': repr(exc)})
    if scene.camera != camera or scene.render.fps != FPS or scene.frame_end != FRAMES:
        errors.append({'check': 'forty-second route settings'})
    positions = []
    prior_quaternion = None
    sightline = []
    for frame in (1, 240, 480, 720, 960):
        scene.frame_set(frame)
        world = camera.matrix_world
        values = [float(value) for value in world.translation]
        quaternion = world.to_quaternion()
        direction = quaternion@Vector((0., 0., -1.))
        if not all(math.isfinite(value) for value in values):
            errors.append({'check': 'finite camera transform', 'frame': frame})
        if prior_quaternion is not None and prior_quaternion.dot(quaternion) < .95:
            errors.append({'check': 'continuous camera rotation', 'frame': frame,
                           'rotation_dot': float(prior_quaternion.dot(quaternion))})
        if direction.z > .25:
            errors.append({'check': 'camera looks towards the architectural scene, not mostly sky',
                           'frame': frame, 'direction_z': round(float(direction.z), 4)})
        prior_quaternion = quaternion
        positions.append(values)
        sightline.append(round(math.degrees(math.asin(float(direction.z))), 3))
    if report['route']['walk_speed_m_s'] > 1.6:
        errors.append({'check': 'human walking pace', 'speed_m_s': report['route']['walk_speed_m_s']})
    result = {'passed': not errors,
              'verified_at': __import__('datetime').datetime.now().astimezone().isoformat(),
              'master_sha256': report['master_sha256'], 'base_sha256': report['base_sha256'],
              'original_city_scene_retained': previous.scene_state(city) == report['original_city_scene'],
              'reopened_scene_count': len(bpy.data.scenes),
              'route_frames': FRAMES, 'route_duration_seconds': FRAMES/FPS,
              'route_walk_speed_m_s': report['route']['walk_speed_m_s'],
              'native_floor_collision_frames_inherited': report['route']['collision_checked_frames'],
              'native_body_head_clearance_rays': report['route']['body_head_clearance_rays'],
              'reopened_camera_positions_m': positions,
              'reopened_camera_elevation_degrees': sightline,
              'errors': errors, 'whole_city_pixel_perfect_reconstruction_proven': False,
              'all_dimensions_surveyed': False,
              'continuous_six_hour_refinement_verified': False}
    dump(VALIDATION, result)
    if errors:
        raise RuntimeError(json.dumps(errors, ensure_ascii=True))
    print('JUNCTIONS_V4_WALK_REOPENED_CHECKS_PASSED', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('build', 'verify'))
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    build() if args.action == 'build' else verify()
