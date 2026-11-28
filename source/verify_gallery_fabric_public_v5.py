"""Compare the actual v5 research master and its self-contained public copy.

The public edition deliberately removes photographic surfaces and the hidden
reference layer. Architectural meshes, transforms, animations, the eight
per-piece attributes and all reviewed v5 material graphs must survive intact.
This is a file-integrity and sampled-navigation audit, not a site survey.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'source'))
import gallery_fabric_v5 as fabric
from cross_axis_galleries_plan import RANGES, plan
from osm_site import Site
from reverify_gallery_fabric_v5 import evaluated_bevels
from refine_cross_axis_fabric_v5 import (
    WALK, CAMERA, FLOOR_CAMERA, action_hash, audit_route, render,
)

REFERENCE_LAYER = '90 · 参考图层 / hidden georeferenced aerial'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def architectural_fingerprint():
    cache, rows = {}, []
    for obj in sorted(bpy.data.objects, key=lambda obj: obj.name):
        if obj.get('public_inscription') or any(c.name == REFERENCE_LAYER for c in obj.users_collection):
            continue
        geometry = None
        if obj.type == 'MESH':
            if obj.data.name not in cache:
                cache[obj.data.name] = fabric.mesh_hash(obj.data)
            geometry = [obj.data.name, cache[obj.data.name]]
        rows.append([obj.name, obj.type, obj.parent.name if obj.parent else None,
                     [fabric.serial(row) for row in obj.matrix_basis], geometry])
    return {'objects':len(rows), 'unique_meshes':len(cache), 'sha256':fabric.encoded_hash(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('master', type=Path)
    parser.add_argument('public', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--build-report', type=Path, default=ROOT/'gallery_fabric_revision_v5_report.json')
    parser.add_argument('--render-previews', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    master, public, output = args.master.resolve(), args.public.resolve(), args.output.resolve()
    if output.exists():
        parser.error('Preserve the previous audit report; choose a new output path.')
    report = json.loads(args.build_report.read_text(encoding='utf8'))
    master_hash, public_hash = digest(master), digest(public)
    if master_hash != report['master_sha256']:
        raise RuntimeError('Research master does not match the v5 build record.')
    bpy.ops.wm.open_mainfile(filepath=str(master), load_ui=False)
    bpy.context.window.scene = bpy.data.scenes[WALK]
    bpy.context.scene.frame_set(1)
    before = architectural_fingerprint()
    before_actions = action_hash()
    print('PUBLIC_V5_SOURCE_FINGERPRINT', before['objects'], before['unique_meshes'], flush=True)

    bpy.ops.wm.open_mainfile(filepath=str(public), load_ui=False)
    scene = bpy.data.scenes[WALK]
    bpy.context.window.scene = scene
    scene.frame_set(1)
    after = architectural_fingerprint()
    checks = {'architectural_geometry_and_transforms_retained':before == after,
              'native_animation_retained':before_actions == action_hash(),
              'no_linked_libraries':not bpy.data.libraries,
              'no_packed_or_external_source_images':not any(i.source != 'VIEWER' or i.packed_file for i in bpy.data.images),
              'no_external_file_dependencies':not any(bpy.utils.blend_paths()+bpy.utils.blend_paths(packed=True)),
              'all_eight_per_piece_attributes_retained':all(
                  bpy.data.objects.get(n) and fabric.seed_hash(bpy.data.objects[n].data) == h
                  for n,h in report['change']['piece_attribute_hashes'].items()),
              'reviewed_v5_material_graphs_retained':all(
                  bpy.data.materials.get(n) and fabric.material_hash(bpy.data.materials[n]) == h
                  for n,h in report['change']['material_hashes'].items()),
              'reviewed_v5_material_bindings_retained':all(
                  bpy.data.objects[n].data.materials[index].name == copied
                  for n,index,original,copied in report['change']['material_bindings'])}
    bevels = evaluated_bevels(report)
    checks['four_paving_bevels_evaluate'] = len(bevels) == 4 and all(row['passed'] for row in bevels)
    route = audit_route(scene, plan(Site(), RANGES[0]), report['route_poses'])
    checks['all_960_native_route_frames_supported_and_clear'] = route['passed']
    result = {'passed':all(checks.values()),'verified_at':datetime.now().astimezone().isoformat(),
              'master':master.name,'master_sha256':master_hash,
              'public':public.name,'public_sha256':public_hash,
              'script_sha256':digest(Path(__file__)),
              'build_report_sha256':digest(args.build_report),
              'before_architecture':before,'after_architecture':after,
              'checks':checks,'bevels':bevels,'route':route,'renders':[],
              'whole_city_pixel_perfect_reconstruction_proven':False,
              'all_dimensions_surveyed':False,
              'scope':'Saved-file integrity, reviewed local fabric retention and ray-sampled single-gallery navigation; not complete human-volume collision or site certification.'}
    dump(output,result)
    if not result['passed']:
        raise RuntimeError('Public v5 validation failed: '+str([n for n,ok in checks.items() if not ok]))
    if args.render_previews:
        folder = output.parent/'previews'
        for camera,label in ((CAMERA,'gallery-walk-v0.2.1'),(FLOOR_CAMERA,'gallery-paving-v0.2.1')):
            result['renders'].append(render(scene,bpy.data.objects[camera],folder/(label+'.png'),480,1920,128))
            dump(output,result)
    if digest(public) != public_hash or digest(master) != master_hash:
        raise RuntimeError('An input model changed during validation.')
    result['input_files_unchanged'] = True
    dump(output,result)
    print('PUBLIC_V5_REOPENED_VERIFIED',public.name,flush=True)


if __name__ == '__main__':
    main()
