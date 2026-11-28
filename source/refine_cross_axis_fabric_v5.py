"""Study, save and independently reopen the v5 gallery fabric revision."""
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'source'))
import gallery_fabric_v5 as fabric
from cross_axis_galleries_plan import RANGES, plan
from osm_site import Site
from outer_court_walkthrough import configure_cycles
from refine_cross_axis_junctions_v3 import first_hit, relevant_geometry

BASE = ROOT/'The_Forbidden_City_Cross_Axis_Junctions_v4.blend'
MASTER = ROOT/'The_Forbidden_City_Gallery_Fabric_v5.blend'
REPORT = ROOT/'gallery_fabric_revision_v5_report.json'
VALIDATION = ROOT/'validation_gallery_fabric_revision_v5.json'
STUDY = ROOT/'renders/gallery_fabric_v5_study_r2'
REVIEW = STUDY/'visual_review.json'
SHA_BASE = '71dea99bc8b0f8449a186f0414b0c3bb0acf38d3ddfb4eb64a89957211541ef3'
CITY = '紫禁城 · metric architectural reconstruction'
WALK = '熙和门南庑 · 40秒慢行廊下漫游'
CAMERA = '熙和门南庑 · 檐廊漫游相机'
FLOOR_CAMERA = '209 · 熙和门南庑 · 铺砖细棱与柱脚'
FINISH_CAMERA = '210 · 熙和门南庑 · 槅扇朱漆近观'
ROOF_CAMERA = '交接检查相机 · 208 · 熙和门南接段'
CHECKPOINTS = (1, 240, 480, 720, 960)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def code_hashes():
    return {name: digest(ROOT/'source'/name) for name in
            ('gallery_fabric_v5.py', 'refine_cross_axis_fabric_v5.py')}


def object_rows(names=None):
    return [[o.name, o.type, o.parent.name if o.parent else None,
             [fabric.serial(row) for row in o.matrix_basis]]
            for o in sorted(bpy.data.objects, key=lambda o: o.name)
            if names is None or o.name in names]


def mesh_rows(exclude=()):
    cache, rows = {}, []
    for obj in sorted(bpy.data.objects, key=lambda o: o.name):
        if obj.type != 'MESH' or obj.name in exclude:
            continue
        if obj.data.name not in cache:
            cache[obj.data.name] = fabric.mesh_hash(obj.data)
        rows.append([obj.name, obj.data.name, cache[obj.data.name]])
    return rows


def scene_rows():
    return [[s.name, fabric.encoded_hash(sorted(o.name for o in s.objects)),
             s.unit_settings.system, s.unit_settings.scale_length,
             s.frame_start, s.frame_end, s.render.fps]
            for s in sorted(bpy.data.scenes, key=lambda s: s.name)]


def action_hash():
    rows = []
    for action in sorted(bpy.data.actions, key=lambda a: a.name):
        rows.append([action.name, [[curve.data_path, curve.array_index,
                     [[fabric.serial(p.co), p.interpolation] for p in curve.keyframe_points]]
                    for curve in action.fcurves]])
    return fabric.encoded_hash(rows)


def bindings_hash(exclude):
    return fabric.encoded_hash([[o.name, [m.name if m else None for m in o.data.materials]]
                               for o in sorted(bpy.data.objects, key=lambda o: o.name)
                               if o.type == 'MESH' and o.name not in exclude])


def sample_route(scene):
    rows = []
    camera = bpy.data.objects[CAMERA]
    for frame in range(1, 961):
        scene.frame_set(frame)
        rows.append([frame, list(camera.matrix_world.translation),
                     list(camera.matrix_world.to_quaternion())])
    scene.frame_set(1)
    return rows


def create_views(walk, q):
    x = (q.bounds[0]+q.bounds[2])/2
    definitions = (
        (FLOOR_CAMERA, (x, q.porch_path_y, 1.72), (x+1.75, q.front_y+.46, 1.10), 38.),
        (FINISH_CAMERA, (x, q.porch_path_y-.15, 2.75), (x+.45, q.wall_y, 3.02), 42.),
    )
    for name, position, aim, lens in definitions:
        if bpy.data.objects.get(name):
            raise RuntimeError('A comparison camera already exists: '+name)
        data = bpy.data.cameras.new(name)
        data.lens, data.clip_start, data.clip_end = lens, .025, 700.
        camera = bpy.data.objects.new(name, data)
        walk.collection.objects.link(camera)
        camera.location = q.loc.world(*position)
        camera.rotation_euler = (Vector(q.loc.world(*aim))-camera.location).to_track_quat('-Z','Y').to_euler()
        camera['purpose'] = 'Close fabric inspection, not a claimed standing eye-height survey.'
    roof = bpy.data.objects.get(ROOF_CAMERA)
    if roof is None:
        raise RuntimeError('The original matched roof inspection camera is missing.')
    if roof.name not in walk.objects:
        walk.collection.objects.link(roof)


def render(scene, camera, path, frame=480, width=1600, samples=64):
    if path.exists():
        raise RuntimeError('Preserve render evidence: '+str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    scene.frame_set(frame)
    scene.camera = camera
    configure_cycles(scene)
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = 'OPTIX' if scene.cycles.device == 'GPU' else 'OPENIMAGEDENOISE'
    scene.cycles.max_bounces = 8
    scene.cycles.diffuse_bounces = 5
    scene.cycles.glossy_bounces = 3
    scene.render.resolution_x, scene.render.resolution_y = width, round(width*9/16)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.film_transparent = False
    scene.render.use_persistent_data = True
    scene.render.filepath = str(path)
    print('FABRIC_RENDER', path.name, flush=True)
    bpy.ops.render.render(write_still=True, scene=scene.name)
    return {'file': str(path.relative_to(ROOT)), 'sha256': digest(path),
            'camera': camera.name, 'frame': frame, 'width': width,
            'height': scene.render.resolution_y, 'samples': samples,
            'world': scene.world.name, 'exposure': scene.view_settings.exposure}


def open_base():
    if digest(BASE) != SHA_BASE:
        raise RuntimeError('The frozen v4 input no longer matches its verified hash.')
    bpy.ops.wm.open_mainfile(filepath=str(BASE), load_ui=False)
    walk = bpy.data.scenes[WALK]
    bpy.context.window.scene = walk
    walk.frame_set(1)
    return bpy.data.scenes[CITY], walk, plan(Site(), RANGES[0])


def study():
    if (STUDY/'study_report.json').exists():
        raise RuntimeError('Inspect the existing fabric study instead of overwriting it.')
    city, walk, q = open_base()
    create_views(walk, q)
    before = [render(walk, bpy.data.objects[name], STUDY/(label+'_before.png'))
              for name, label in ((CAMERA,'walk_0480'), (FLOOR_CAMERA,'paving'),
                                  (FINISH_CAMERA,'lacquer'), (ROOF_CAMERA,'glaze'))]
    change = fabric.apply(city, {s['key'] for s in RANGES})
    after = [render(walk, bpy.data.objects[name], STUDY/(label+'_after.png'))
             for name, label in ((CAMERA,'walk_0480'), (FLOOR_CAMERA,'paving'),
                                 (FINISH_CAMERA,'lacquer'), (ROOF_CAMERA,'glaze'))]
    dump(STUDY/'study_report.json', {'base_sha256': SHA_BASE, 'code_hashes': code_hashes(),
                                    'change': change, 'before': before, 'after': after,
                                    'model_saved': False,
                                    'lighting_and_camera_equal_in_each_pair': True})
    print('FABRIC_STUDY_COMPLETE', flush=True)


def build():
    pending = MASTER.with_name(MASTER.stem+'.pending.blend')
    if MASTER.exists() or pending.exists() or REPORT.exists():
        raise RuntimeError('Inspect the existing v5 candidate before attempting another build.')
    review = json.loads(REVIEW.read_text(encoding='utf8'))
    study_report = json.loads((STUDY/'study_report.json').read_text(encoding='utf8'))
    if not review.get('passed') or study_report['code_hashes'] != code_hashes():
        raise RuntimeError('The current source needs a completed, matching visual study.')
    city, walk, q = open_base()
    original_names = sorted(o.name for o in bpy.data.objects)
    original_transforms = fabric.encoded_hash(object_rows())
    original_scene_state = scene_rows()
    original_actions = action_hash()
    poses = sample_route(walk)
    original_materials = {m.name: fabric.material_hash(m) for m in bpy.data.materials}
    keys = {s['key'] for s in RANGES}
    target_names = {o.name for o in city.objects if o.type == 'MESH' and
                    (o.get('cross_axis_gallery') in keys or o.get('cross_axis_junction') in keys)}
    paving_names = {o.name for o in city.objects if o.get('cross_axis_gallery_role') == 'paving'}
    original_geometry = fabric.encoded_hash(mesh_rows(paving_names))
    original_bindings = bindings_hash(target_names)
    create_views(walk, q)
    change = fabric.apply(city, keys)
    if change['material_hashes'] != study_report['change']['material_hashes']:
        raise RuntimeError('Built material graphs differ from the visually reviewed study.')
    if original_geometry != fabric.encoded_hash(mesh_rows(paving_names)):
        raise RuntimeError('Native geometry outside the four pavement meshes changed.')
    if original_bindings != bindings_hash(target_names):
        raise RuntimeError('A material binding outside the gallery scope changed.')
    if any(fabric.material_hash(bpy.data.materials[name]) != value for name,value in original_materials.items()):
        raise RuntimeError('An original material graph was changed instead of independently copied.')
    walk.camera = bpy.data.objects[CAMERA]
    walk.frame_set(1)
    walk.render.resolution_x, walk.render.resolution_y = 1280, 720
    walk['fabric_revision'] = 'gallery-fabric-v5'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(pending), compress=True)
    pending.replace(MASTER)
    dump(REPORT, {'native_blend': MASTER.name, 'master_sha256': digest(MASTER),
                  'base_blend': BASE.name, 'base_sha256': SHA_BASE, 'code_hashes': code_hashes(),
                  'original_object_names': original_names, 'original_transforms_hash': original_transforms,
                  'original_scene_state': original_scene_state, 'original_action_hash': original_actions,
                  'original_material_graphs': original_materials,
                  'non_paving_geometry_hash': original_geometry,
                  'non_target_material_binding_hash': original_bindings,
                  'post_mesh_hash': fabric.encoded_hash(mesh_rows()),
                  'post_scene_state': scene_rows(), 'route_poses': poses,
                  'change': change, 'visual_review_sha256': digest(REVIEW),
                  'limitations': ['Gallery plan, bay-count boundary and heights remain provisional as documented in v4.',
                                 'The 1 m gallery / 2.62 m gate platform transition remains unresolved.',
                                 'Edge dressing, lacquer, stone and glaze response are inferred, not measured surface properties.',
                                 'The walk covers one gallery; room interiors remain unfurnished.',
                                 'Whole-city pixel-perfect and complete measured 1:1 reproduction are not proven.']})
    print('FABRIC_V5_SAVED', MASTER.name, flush=True)


def audit_route(walk, q, expected):
    graph = bpy.context.evaluated_depsgraph_get()
    geometry = relevant_geometry(walk, graph, RANGES[0], q,
                                 q.bounds[0]+5., q.bounds[2]-6., q.porch_path_y, 12.)
    forward = Vector(q.loc.world(1.,0.,0.))-Vector(q.loc.world(0.,0.,0.))
    cross = Vector(q.loc.world(0.,1.,0.))-Vector(q.loc.world(0.,0.,0.))
    forward.normalize(); cross.normalize()
    failures, floors, cameras = [], [], []
    body_rays = head_rays = floor_rays = motion_rays = 0
    camera = bpy.data.objects[CAMERA]
    previous = None
    for frame, position, quaternion in expected:
        walk.frame_set(frame)
        current = camera.matrix_world.translation.copy()
        rotation = camera.matrix_world.to_quaternion()
        if (current-Vector(position)).length > 2e-5 or abs(sum(a*b for a,b in zip(rotation, quaternion))) < .999999:
            failures.append({'frame':frame, 'reason':'saved route pose drift'})
        levels = []
        for offset in (Vector(), forward*.08, -forward*.08, cross*.08, -cross*.08):
            floor_rays += 1
            start = current+offset; start.z = 2.35
            hit = first_hit(geometry, start, Vector((0.,0.,-1.)), 2.5)
            if hit is None or abs(hit[1].z-1.) > .006:
                failures.append({'frame':frame, 'reason':'foot support', 'hit':hit[0] if hit else None})
            else:
                levels.append(hit[1].z)
        if not levels:
            continue
        floor = max(levels); floors.extend(levels)
        for height in (.30, 1., 1.85):
            origin = Vector((current.x,current.y,floor+height))
            for direction in (forward,-forward,cross,-cross):
                body_rays += 1
                hit = first_hit(geometry,origin,direction,.215)
                if hit:
                    failures.append({'frame':frame,'reason':'body clearance','object':hit[0]})
        head_rays += 1
        if first_hit(geometry,current,Vector((0.,0.,1.)),.22):
            failures.append({'frame':frame,'reason':'head clearance'})
        if previous is not None:
            motion_rays += 1
            delta = current-previous
            if first_hit(geometry,previous,delta.normalized(),delta.length+.06):
                failures.append({'frame':frame,'reason':'continuous camera motion'})
        previous = current
        if frame in CHECKPOINTS:
            cameras.append([frame,list(current),round(current.z-floor,6)])
    return {'passed':not failures, 'frames':len(expected), 'native_collision_meshes':len(geometry),
            'floor_rays':floor_rays, 'body_rays':body_rays, 'head_rays':head_rays,
            'continuous_motion_rays':motion_rays, 'floor_z_range_m':[min(floors),max(floors)],
            'camera_checkpoints':cameras, 'failures':failures,
            'scope':'Ray-sampled support and clearance against the saved evaluated meshes, including paving bevels; not a complete human-volume or site-route certification.'}


def verify():
    report = json.loads(REPORT.read_text(encoding='utf8'))
    if digest(MASTER) != report['master_sha256'] or digest(BASE) != SHA_BASE:
        raise RuntimeError('The native files do not match their recorded hashes.')
    bpy.ops.wm.open_mainfile(filepath=str(MASTER), load_ui=False)
    walk = bpy.data.scenes[WALK]
    bpy.context.window.scene = walk
    walk.frame_set(1)
    checks = {}
    def check(label, ok):
        checks[label] = bool(ok)
    check('original object transforms retained', fabric.encoded_hash(object_rows(set(report['original_object_names']))) == report['original_transforms_hash'])
    check('non-paving raw geometry retained', fabric.encoded_hash(mesh_rows(report['change']['geometry_changed_objects'])) == report['non_paving_geometry_hash'])
    check('all saved raw geometry matches built v5', fabric.encoded_hash(mesh_rows()) == report['post_mesh_hash'])
    check('scene membership units and timings retained', scene_rows() == report['post_scene_state'])
    check('all original animation keyframes retained', action_hash() == report['original_action_hash'])
    check('non-target material bindings retained', bindings_hash(set(report['change']['target_objects'])) == report['non_target_material_binding_hash'])
    check('original shader graphs retained', all(bpy.data.materials.get(n) and fabric.material_hash(bpy.data.materials[n]) == h for n,h in report['original_material_graphs'].items()))
    check('reviewed shader copies saved intact', all(fabric.material_hash(bpy.data.materials[n]) == h for n,h in report['change']['material_hashes'].items()))
    check('per-piece material values saved intact', all(fabric.seed_hash(bpy.data.objects[n].data) == h for n,h in report['change']['piece_attribute_hashes'].items()))
    bevels = []
    for row in report['change']['paving']:
        obj = bpy.data.objects[row['object']]
        modifier = obj.modifiers.get(fabric.BEVEL_NAME)
        graph = bpy.context.evaluated_depsgraph_get()
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        bevels.append({'object':obj.name, 'evaluated_faces':len(mesh.polygons),
                       'base_faces':len(obj.data.polygons),
                       'width_m':modifier.width if modifier else None})
        check(obj.name+' evaluated bevel', modifier is not None and abs(modifier.width-fabric.BEVEL_WIDTH)<1e-7
              and len(mesh.polygons)>len(obj.data.polygons))
        evaluated.to_mesh_clear()
    route = audit_route(walk, plan(Site(),RANGES[0]), report['route_poses'])
    check('960 saved route frames supported and clear', route['passed'])
    output = ROOT/'renders/gallery_fabric_v5_verified'
    renders = [render(walk,bpy.data.objects[CAMERA],output/f'walk_{f:04d}.png',f,1600,64)
               for f in CHECKPOINTS]
    renders += [render(walk,bpy.data.objects[name],output/(label+'.png'))
                for name,label in ((FLOOR_CAMERA,'paving'),(FINISH_CAMERA,'lacquer'),(ROOF_CAMERA,'glaze'))]
    result = {'passed':all(checks.values()),'verified_at':datetime.now().astimezone().isoformat(),
              'master_sha256':report['master_sha256'], 'base_sha256':SHA_BASE,
              'checks':checks,'bevels':bevels,'route':route,'renders':renders,
              'scene_count':len(bpy.data.scenes),'whole_city_pixel_perfect_reconstruction_proven':False,
              'all_dimensions_surveyed':False,'continuous_six_hour_refinement_verified':False}
    dump(VALIDATION,result)
    if not result['passed']:
        raise RuntimeError('Native v5 checks failed: '+str([n for n,ok in checks.items() if not ok]))
    print('FABRIC_V5_REOPENED_VERIFIED', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('study','build','verify'))
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    {'study':study,'build':build,'verify':verify}[args.action]()
