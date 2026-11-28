"""Recheck v5 with all four pavements evaluated in their owning city scene.

The initial verifier evaluated three objects absent from the isolated walk
scene. Keep that original failed report and its rendered evidence unchanged;
recheck the actual saved file in the complete scene instead of altering it.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source'))
import gallery_fabric_v5 as fabric
import refine_cross_axis_fabric_v5 as original
from cross_axis_galleries_plan import RANGES, plan
from osm_site import Site


def evaluated_bevels(report):
    previous = bpy.context.window.scene
    city = bpy.data.scenes[original.CITY]
    bpy.context.window.scene = city
    city.frame_set(1)
    graph = bpy.context.evaluated_depsgraph_get()
    rows = []
    for record in report['change']['paving']:
        obj = bpy.data.objects[record['object']]
        if obj.name not in city.objects:
            raise RuntimeError('The tested paving is absent from the owning city scene: '+obj.name)
        modifier = obj.modifiers.get(fabric.BEVEL_NAME)
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        passed = bool(modifier and modifier.show_viewport and modifier.show_render
                      and abs(modifier.width-fabric.BEVEL_WIDTH)<1e-7
                      and modifier.segments == 3
                      and len(mesh.polygons)>len(obj.data.polygons))
        rows.append({'object':obj.name,'owning_scene':city.name,'present_in_evaluated_scene':True,
                     'base_faces':len(obj.data.polygons),'evaluated_faces':len(mesh.polygons),
                     'width_m':modifier.width if modifier else None,'passed':passed})
        evaluated.to_mesh_clear()
    bpy.context.window.scene = previous
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'validation_gallery_fabric_revision_v5_recheck.json')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if args.output.exists():
        parser.error('Preserve the previous recheck; choose another output report.')
    report=json.loads(original.REPORT.read_text(encoding='utf8'))
    first=json.loads(original.VALIDATION.read_text(encoding='utf8'))
    if original.digest(original.MASTER) != report['master_sha256'] or original.digest(original.BASE) != original.SHA_BASE:
        raise RuntimeError('A frozen model changed before the independent recheck.')
    bpy.ops.wm.open_mainfile(filepath=str(original.MASTER),load_ui=False)
    walk=bpy.data.scenes[original.WALK]
    bpy.context.window.scene=walk
    walk.frame_set(1)
    checks={
        'frozen_build_sources_retained':original.code_hashes()==report['code_hashes'],
        'original_object_transforms_retained':fabric.encoded_hash(original.object_rows(set(report['original_object_names'])))==report['original_transforms_hash'],
        'non_paving_raw_geometry_retained':fabric.encoded_hash(original.mesh_rows(report['change']['geometry_changed_objects']))==report['non_paving_geometry_hash'],
        'all_saved_raw_geometry_matches_built_v5':fabric.encoded_hash(original.mesh_rows())==report['post_mesh_hash'],
        'scene_membership_units_timings_retained':original.scene_rows()==report['post_scene_state'],
        'original_animation_keyframes_retained':original.action_hash()==report['original_action_hash'],
        'non_target_material_bindings_retained':original.bindings_hash(set(report['change']['target_objects']))==report['non_target_material_binding_hash'],
        'original_shader_graphs_retained':all(bpy.data.materials.get(n) and fabric.material_hash(bpy.data.materials[n])==h for n,h in report['original_material_graphs'].items()),
        'reviewed_shader_copies_saved_intact':all(fabric.material_hash(bpy.data.materials[n])==h for n,h in report['change']['material_hashes'].items()),
        'per_piece_material_values_saved_intact':all(fabric.seed_hash(bpy.data.objects[n].data)==h for n,h in report['change']['piece_attribute_hashes'].items()),
        'all_eight_previous_rendered_images_match_this_model':first['master_sha256']==report['master_sha256'] and len(first['renders'])==8 and all(original.digest(ROOT/r['file'])==r['sha256'] for r in first['renders']),
    }
    bevels=evaluated_bevels(report)
    checks['four_paving_bevels_evaluate_in_owning_scene']=len(bevels)==4 and all(r['passed'] for r in bevels)
    route=original.audit_route(walk,plan(Site(),RANGES[0]),report['route_poses'])
    checks['all_960_saved_route_frames_supported_and_clear']=route['passed']
    result={'passed':all(checks.values()),'verified_at':datetime.now().astimezone().isoformat(),
            'master_sha256':report['master_sha256'],'base_sha256':original.SHA_BASE,
            'script_sha256':original.digest(Path(__file__)),
            'initial_failed_report':original.VALIDATION.name,
            'initial_failed_report_sha256':original.digest(original.VALIDATION),
            'diagnosis':'Three non-walk pavements are absent from the isolated walk scene. Their modifiers are evaluated in the full owning city scene here. No model change was made to obtain a pass.',
            'checks':checks,'bevels':bevels,'route':route,'renders':first['renders'],
            'whole_city_pixel_perfect_reconstruction_proven':False,
            'all_dimensions_surveyed':False,'continuous_six_hour_refinement_verified':False}
    checks['frozen_master_unchanged_after_recheck']=original.digest(original.MASTER)==report['master_sha256']
    result['passed']=all(checks.values())
    original.dump(args.output,result)
    if not result['passed']:
        raise RuntimeError('v5 recheck failed: '+str([n for n,ok in checks.items() if not ok]))
    print('FABRIC_V5_OWNING_SCENE_RECHECK_PASSED',flush=True)


if __name__=='__main__':
    main()
