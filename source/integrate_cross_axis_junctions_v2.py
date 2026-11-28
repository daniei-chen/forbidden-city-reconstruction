"""Integrate the reviewed junction study into a new, separately named city file."""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
import numpy as np
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'source'))
from cross_axis_galleries_plan import RANGES, plan
from refine_wumen_scene import fingerprint, scene_state
from study_cross_axis_galleries_v1 import ray, trees
from osm_site import Site


BASE = ROOT/'The_Forbidden_City_Cross_Axis_Galleries.blend'
STUDY = ROOT/'studies/Cross_Axis_Junctions_Study_v4.blend'
CITY = ROOT/'The_Forbidden_City_Cross_Axis_Junctions_v2.blend'
REPORT = ROOT/'cross_axis_junctions_revision_v2_report.json'
VALIDATION = ROOT/'validation_cross_axis_junctions_revision_v2.json'
STUDY_REPORT = ROOT/'studies/cross_axis_junctions_study_v4_report.json'
STUDY_QA = ROOT/'studies/validation_cross_axis_junctions_study_v4.json'
OLD_GALLERIES = ROOT/'cross_axis_galleries_revision_report_v1.json'
OLD_GATE = ROOT/'cross_axis_gates_revision_report.json'
CANDIDATES = ROOT/'cross_axis_gallery_junction_candidates_v2.json'
REVIEW_SCENE = '協和熙和門 · 四段短接實際全城環境'
SHA_CITY = '0c5a515e391feae09bdf32c673f5ecde93b41f011cddd4ca8bb2e2d91e28e449'
SHA_STUDY = '168598283c3f685271c80e06a71cd51fbf487105eb6a123b220a8b6d40ee16ea'
CAMERA_LABELS = ('熙和门南接段', '熙和门北接段', '协和门北接段', '协和门南接段')


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_text('utf8'))


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf8')


def add_actual_context_clearance(scene, site, plans, old_names):
    bpy.context.window.scene = scene
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    by_spec = []
    failures = []
    for spec, record in zip(RANGES, plans):
        q = plan(site, spec)
        x0, x1 = record['short_masonry_x_limits_m']
        corners = [q.loc.world(x, y, z) for x in (x0-1., x1+1.)
                   for y in (q.front_y-1., q.rear_y+1.) for z in (-.5, 13.)]
        lo = [min(p[k] for p in corners)-.5 for k in range(3)]
        hi = [max(p[k] for p in corners)+.5 for k in range(3)]
        candidates = []
        for obj in scene.objects:
            if obj.type != 'MESH' or obj.name in old_names or obj.hide_render or not len(obj.data.polygons):
                continue
            if any(c.hide_render for c in obj.users_collection):
                continue
            evaluated = obj.evaluated_get(graph)
            matrix = evaluated.matrix_world
            points = [matrix@Vector(c) for c in obj.bound_box]
            bounds = ([min(p[k] for p in points) for k in range(3)],
                      [max(p[k] for p in points) for k in range(3)])
            if any(bounds[1][k] < lo[k] or bounds[0][k] > hi[k] for k in range(3)):
                continue
            candidates.append(obj)
        geometry = trees(candidates, graph)
        gate_spec = next(g for g in RANGES if g['gate_body'] == spec['gate_body'])
        deck_id = '638218843' if gate_spec['gate'] == '熙和门' else '638238326'
        deck = q.loc.local(site.geom(deck_id))
        errors = []
        checked = 0
        body_rays = 0
        positions = 41
        for i in range(positions):
            x = x0+.47+(x1-x0-.94)*i/(positions-1)
            y = q.porch_path_y
            datum = 2.62 if deck.contains(Point(x, y)) else 1.0
            checked += 1
            foot = ray(geometry, q.loc.world(x, y, datum+.12), (0, 0, -1), .25)
            if foot is None or not datum-.0041 < foot[1][2] < datum+.001:
                errors.append({'kind': 'no_actual_city_floor_support', 'index': i,
                               'expected_floor_m': datum, 'hit': foot})
            for height in (.30, 1.20, 1.85):
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    direction = Vector(q.loc.world(dx, dy))-Vector(q.loc.world())
                    hit = ray(geometry, q.loc.world(x, y, datum+height), direction, .27)
                    body_rays += 1
                    if hit:
                        errors.append({'kind': 'actual_city_path_obstruction', 'index': i,
                                       'height_m': height, 'hit': hit})
        row = {'range': spec['key'], 'gate': spec['gate'], 'neighbour_meshes_tested': len(candidates),
               'positions': checked, 'actual_gate_or_gallery_floor_support_rays': checked,
               'body_head_clearance_rays': body_rays, 'passed': not errors, 'errors': errors[:12],
               'scope': 'Actual surrounding city objects and retained gate terrace; it tests the short side corridor only. It does not claim that gallery-to-gate interior access or the floor-height transition is historically resolved.'}
        by_spec.append(row)
        failures.extend({'range': spec['key'], **e} for e in errors)
        print('ACTUAL_CITY_SHORT_PATH_CHECKED', spec['key'], len(candidates), checked, body_rays, flush=True)
    return {'passed': not failures, 'ranges': by_spec, 'errors': failures,
            'scope': 'Actual complete-city neighbours, original gate platforms, and replaced short-porch meshes; unknown historical interior access remains explicitly outside the check.'}


def build():
    if CITY.exists() or CITY.with_name(CITY.stem+'.pending.blend').exists() or REPORT.exists() or VALIDATION.exists():
        raise RuntimeError('Candidate destination or report exists. Inspect it before retrying.')
    old = read(OLD_GALLERIES)
    gates = read(OLD_GATE)
    study = read(STUDY_REPORT)
    qa = read(STUDY_QA)
    candidates = read(CANDIDATES)
    assert digest(BASE) == SHA_CITY == old['master_sha256']
    assert digest(STUDY) == SHA_STUDY == study['native_sha256'] == qa['native_sha256']
    assert qa['passed'] and len(qa['checks']) == 23
    assert candidates['native_sha256'] == SHA_CITY
    assert not any((o.get('replacement_approved') for g in candidates['gates']
                    for p in g['retained_relation_parts'] for o in [p]))
    bpy.ops.wm.open_mainfile(filepath=str(BASE))
    city = bpy.data.scenes['紫禁城 · metric architectural reconstruction']
    bpy.context.window.scene = city
    bpy.context.view_layer.update()
    baseline_states = [scene_state(s) for s in bpy.data.scenes]
    assert len(baseline_states) == 19
    original_state = {s['name']: s for s in baseline_states}

    short_by_gate = {g['gate']: sorted({o['object'] for p in g['retained_relation_parts']
                                      for o in p['actual_saved_native_objects']})
                     for g in candidates['gates']}
    assert all(len(v) == 18 for v in short_by_gate.values())
    range_roofs = {spec['key']: sorted(o.name for o in bpy.data.objects
                    if o.get('cross_axis_gallery') == spec['key'] and o.get('cross_axis_gallery_role') == 'roof')
                   for spec in RANGES}
    assert all(len(v) == 3 for v in range_roofs.values()), range_roofs
    replaced_by_spec = {}
    for spec in RANGES:
        replaced_by_spec[spec['key']] = set(range_roofs[spec['key']]) | set(short_by_gate[spec['gate']])
    old_names = set().union(*replaced_by_spec.values())
    assert len(old_names) == 48 and all(bpy.data.objects.get(n) for n in old_names)
    old_fp = fingerprint(sorted(old_names))
    preserved = sorted(o.name for o in bpy.data.objects if o.name not in old_names)
    preserved_fp = fingerprint(preserved)
    prior_scene_states = [scene_state(s) for s in bpy.data.scenes]

    with bpy.data.libraries.load(str(STUDY), link=False) as (source, target):
        group_name = study['root_group']
        assert group_name in source.collections
        source_cam_names = [v['camera'] for v in study['views']]
        assert all(n in source.objects for n in source_cam_names)
        target.collections = [group_name]
        target.objects = list(source_cam_names)
    groups = list(target.collections)
    imported_cameras = list(target.objects)
    assert len(groups) == 1 and len(imported_cameras) == 4
    new_by_spec = {}
    new_names = set()
    for record in study['plans']:
        spec_names = sorted(o.name for o in groups[0].all_objects
                            if o.get('cross_axis_junction') == record['key'])
        assert len(spec_names) >= 6, (record['key'], len(spec_names))
        new_by_spec[record['key']] = set(spec_names)
        new_names.update(spec_names)
    assert len(new_names) == 30
    for i, obj in enumerate(imported_cameras):
        wanted = '交接检查相机 · %03d · %s' % (208+i, CAMERA_LABELS[i])
        assert bpy.data.objects.get(wanted) is None
        obj.name = wanted
        obj.data.name = wanted+' · 镜头'
        obj['study_camera_key'] = 208+i
    camera_names = [o.name for o in imported_cameras]

    for name in sorted(old_names):
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    root = bpy.data.collections.get('紫禁城 · EDITABLE 3D MASTER')
    assert root is not None
    root.children.link(groups[0])

    expected_states = []
    for state in prior_scene_states:
        scene = bpy.data.scenes[state['name']]
        previous_names = set(state['objects'])
        removed_here = previous_names & old_names
        wanted = previous_names-old_names
        for key, oldset in replaced_by_spec.items():
            if oldset & removed_here:
                wanted.update(new_by_spec[key])
                for obj_name in new_by_spec[key]:
                    obj = bpy.data.objects[obj_name]
                    if obj.name not in scene.objects:
                        scene.collection.objects.link(obj)
        expected = {**state, 'objects': sorted(wanted)}
        expected_states.append(expected)
        assert scene_state(scene) == expected, scene.name
    assert fingerprint(preserved) == preserved_fp
    assert fingerprint(sorted(old_names))['missing'] == sorted(old_names)
    assert not any(bpy.data.objects.get(n) for n in old_names)

    review_scene = bpy.data.scenes.new(REVIEW_SCENE)
    review_scene.use_fake_user = True
    review_scene.world = city.world
    review_scene.unit_settings.system = 'METRIC'
    review_scene.unit_settings.scale_length = 1.
    review_scene.view_settings.view_transform = city.view_settings.view_transform
    review_scene.view_settings.look = city.view_settings.look
    review_scene.view_settings.exposure = .30
    for obj in city.objects:
        review_scene.collection.objects.link(obj)
    for obj in groups[0].all_objects:
        if obj.name not in review_scene.objects:
            review_scene.collection.objects.link(obj)
    for obj in imported_cameras:
        review_scene.collection.objects.link(obj)
    review_scene.camera = imported_cameras[0]
    site = Site()
    clearance = add_actual_context_clearance(city, site, study['plans'], old_names)
    if not clearance['passed']:
        dump(ROOT/'cross_axis_junctions_failed_actual_city_context_v2.json', clearance)
        raise RuntimeError('Actual city short path or gate platform failed; formal file not replaced.')
    assert fingerprint(preserved) == preserved_fp

    bpy.context.window.scene = city
    bpy.context.preferences.filepaths.save_version = 0
    pending = CITY.with_name(CITY.stem+'.pending.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(pending), compress=True)
    pending.replace(CITY)
    source_files = ('cross_axis_junction_architecture_v2.py', 'study_cross_axis_junctions_v2.py',
                    'study_cross_axis_junctions_study_v4.py', 'integrate_cross_axis_junctions_v2.py')
    report = {'built_at': bpy.app.version_string,
              'generated_at': __import__('datetime').datetime.now().astimezone().isoformat(),
              'native_blend': CITY.name, 'master_sha256': digest(CITY),
              'base_blend': BASE.name, 'base_sha256': SHA_CITY,
              'study': str(STUDY.relative_to(ROOT)), 'study_sha256': SHA_STUDY,
              'study_report_sha256': digest(STUDY_REPORT), 'study_validation_sha256': digest(STUDY_QA),
              'removed_names': sorted(old_names), 'removed_fingerprint': old_fp,
              'replaced_by_range': {k: sorted(v) for k, v in replaced_by_spec.items()},
              'new_names': sorted(new_names), 'new_fingerprint': fingerprint(sorted(new_names)),
              'new_groups': [groups[0].name], 'preserved_names': preserved,
              'preserved_fingerprint': preserved_fp, 'prior_scene_states': prior_scene_states,
              'expected_inherited_scene_states': expected_states, 'review_scene': REVIEW_SCENE,
              'review_cameras': camera_names, 'plans': study['plans'],
              'actual_city_context_clearance': clearance,
              'source_sha256': {n: digest(ROOT/'source'/n) for n in source_files},
              'input_sha256': {n: digest(ROOT/n) for n in
                   ('cross_axis_galleries_revision_report_v1.json', 'cross_axis_gates_revision_report.json',
                    'cross_axis_gallery_junction_candidates_v2.json',
                    'studies/cross_axis_junctions_study_v4_report.json',
                    'studies/validation_cross_axis_junctions_study_v4.json')},
              'limitations': [
                  'This is a versioned improvement to four short gate/gallery roof returns, not whole-city completion.',
                  'The map roof orientation is translated correctly in the replaced junction geometry; source map footprints remain estimates, not field survey.',
                  'The 1 m long-range and 2.62 m gate platform datums remain separate. A verified physical floor-level connection/ramp is not asserted.',
                  'The visual joints, support sections, roof tile profile and plaster returns are still inferred; all hidden spaces are not historically measured.',
                  'No photoreal, all-dimensions-surveyed or pixel-perfect acceptance is claimed.',
                  'The new local environment scene uses the actual complete-city meshes; visual review and aerial are pending independent reopen.'
              ], 'whole_city_pixel_perfect_reconstruction_proven': False,
              'all_dimensions_surveyed': False, 'continuous_six_hour_refinement_verified': False}
    dump(REPORT, report)
    print('JUNCTIONS_COMPLETE_CITY_CANDIDATE_SAVED', CITY.name, report['master_sha256'], flush=True)


def verify():
    report = read(REPORT)
    assert digest(CITY) == report['master_sha256']
    assert digest(BASE) == SHA_CITY == report['base_sha256']
    assert digest(STUDY) == SHA_STUDY == report['study_sha256']
    assert read(STUDY_QA)['passed']
    for name, sha in report['source_sha256'].items():
        assert digest(ROOT/'source'/name) == sha, name
    for name, sha in report['input_sha256'].items():
        assert digest(ROOT/name) == sha, name
    bpy.ops.wm.open_mainfile(filepath=str(CITY))
    city = bpy.data.scenes['紫禁城 · metric architectural reconstruction']
    checks = []
    errors = []
    def test(label, passed, evidence):
        row = {'check': label, 'passed': bool(passed), 'evidence': evidence}
        checks.append(row)
        if not passed:
            errors.append(row)
    test('All prior architectural scenes and settings retained',
         all(scene_state(bpy.data.scenes[s['name']]) == s for s in report['expected_inherited_scene_states']),
         len(report['expected_inherited_scene_states']))
    test('All unrelated native objects retained',
         fingerprint(report['preserved_names']) == report['preserved_fingerprint'],
         len(report['preserved_names']))
    test('Exact native junction geometry and carriers retained',
         fingerprint(report['new_names']) == report['new_fingerprint'],
         report['new_fingerprint'])
    test('Only 48 intended junction and obsolete range-roof objects replaced',
         all(bpy.data.objects.get(n) is None for n in report['removed_names']), len(report['removed_names']))
    ridge_checks = []
    for spec, saved in zip(RANGES, report['plans']):
        q = plan(Site(), spec)
        points = []
        for name in report['new_names']:
            obj = bpy.data.objects[name]
            if obj.get('cross_axis_junction') != spec['key'] or obj.get('junction_role') != 'continuous_roof':
                continue
            for index, vertex in enumerate(obj.data.vertices):
                if index % 7:
                    continue
                world = obj.matrix_world@vertex.co
                if world.z <= 10.7:
                    continue
                dx, dy = world.x-q.loc.x, world.y-q.loc.y
                c, s = math.cos(q.loc.yaw), math.sin(q.loc.yaw)
                points.append((c*dx+s*dy, -s*dx+c*dy))
        values = np.asarray(points)
        _, axes = np.linalg.eigh(np.cov(values.T))
        a = axes[:, -1]
        degrees = math.degrees(math.atan2(a[1], a[0])) % 180
        deviation = min(degrees, 180-degrees)
        ridge_checks.append({'range': spec['key'], 'ridge_axis_deg_from_map_local_x': degrees,
                             'deviation_from_longitudinal': deviation,
                             'terminates_at_gate_wall': saved['roof_terminates_at_gate_wall'],
                             'high_vertices_sampled': len(points)})
    test('Four continuous gallery ridges follow map axis and meet gate wall',
         all(r['deviation_from_longitudinal'] < .15 and r['terminates_at_gate_wall'] for r in ridge_checks),
         ridge_checks)
    test('Review scene contains actual current-city context',
         REVIEW_SCENE in bpy.data.scenes and
         all(n in bpy.data.scenes[REVIEW_SCENE].objects for n in report['review_cameras']),
         len(bpy.data.scenes[REVIEW_SCENE].objects) if REVIEW_SCENE in bpy.data.scenes else None)
    site = Site()
    context = add_actual_context_clearance(city, site, report['plans'], set())
    test('Actual city porch floors and body/head clearance', context['passed'], context)
    result = {'passed': not errors, 'verified_at': __import__('datetime').datetime.now().astimezone().isoformat(),
              'master_sha256': report['master_sha256'], 'base_sha256': report['base_sha256'],
              'checks': checks, 'actual_city_context_clearance': context,
              'scope': 'Independently reopened new full-city model; preserves the full pre-existing city and 18 scenes, and verifies four short gate/gallery returns with actual neighbors. No field-survey, photoreal or whole-city pixel-perfect certification.',
              'whole_city_pixel_perfect_reconstruction_proven': False,
              'all_dimensions_surveyed': False, 'continuous_six_hour_refinement_verified': False,
              'visual_inspection_complete': False, 'same_version_aerial_rendered': False}
    dump(VALIDATION, result)
    if errors:
        raise RuntimeError(json.dumps(errors[:4], ensure_ascii=True))
    print('JUNCTIONS_COMPLETE_CITY_REOPENED_CHECKS_PASSED', len(checks), flush=True)


if __name__ == '__main__':
    if '--' not in sys.argv:
        build()
    elif sys.argv[sys.argv.index('--')+1:] == ['verify']:
        verify()
    else:
        raise SystemExit('usage: -- verify (omit -- to build)')
