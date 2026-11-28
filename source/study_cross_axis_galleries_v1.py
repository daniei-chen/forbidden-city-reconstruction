"""Build, independently reopen, sample and render the four gallery ranges."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source'))
import cross_axis_galleries_architecture as architecture
from cross_axis_galleries_plan import BAY_COUNT, FLOOR, POST_TOP, RANGES, STATUS, plan
from mesh_tools import collection
from osm_site import Site
from outer_court_walkthrough import configure_cycles
from palace_materials import palette
from refine_immersive import camera

BASE = ROOT/'studies/Xiehe_Xihe_Gates_Study_v6.blend'
BASE_SHA = 'd985a626d577e28a638fcb2f159cc4ae778ca91361f49852bd41cd7dd432b86d'
OUT = ROOT/'studies/Cross_Axis_Galleries_Study_v1.blend'
REPORT = ROOT/'studies/cross_axis_galleries_study_v1_report.json'
VALIDATION = ROOT/'studies/validation_cross_axis_galleries_study_v1.json'


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),'utf8')


def now():
    return datetime.now().astimezone().isoformat()


def build():
    if OUT.exists() or REPORT.exists():
        raise RuntimeError('New study destination already exists; inspect before any retry.')
    assert digest(BASE)==BASE_SHA
    audit = json.loads((ROOT/'cross_axis_galleries_source_and_plan_audit_v1.json').read_text('utf8'))
    assert len(audit['official_text_matches'])==2
    bpy.ops.wm.open_mainfile(filepath=str(BASE))
    scene = bpy.context.scene
    scene.name = '太和门广场东西庑 · 前廊退窗局部研究'
    original_objects = sorted(o.name for o in scene.objects)
    root = collection('太和门广场四段长庑 · 可通行前廊研究')
    site = Site()
    p = architecture.materials(palette())
    records = []
    views = []
    for index,spec in enumerate(RANGES):
        print('BUILDING_GALLERY',spec['key'],flush=True)
        records.append(architecture.build_range(site,spec,root,p))
        q=plan(site,spec)
        cx,cy=q.centre
        key=201+index
        eye=(cx-18,q.front_y-25,9.0)
        target=(cx,q.wall_y,4.2)
        cam=camera(f'{key} · {spec["name"]} · 柱廊外观',q.loc.world(*eye),q.loc.world(*target),40)
        cam.data.clip_start=.025
        views.append({'key':key,'camera':cam.name,'range':spec['key'],'kind':'exterior','exposure':.30})
        if index in (0,2):
            key=205+index//2
            eye=(q.xs[2]+.30,q.porch_path_y,FLOOR+1.65)
            target=(q.xs[9],q.porch_path_y,FLOOR+2.0)
            cam=camera(f'{key} · {spec["name"]} · 人眼沿廊',q.loc.world(*eye),q.loc.world(*target),28)
            cam.data.clip_start=.025
            views.append({'key':key,'camera':cam.name,'range':spec['key'],'kind':'porch','exposure':1.0})
    scene.camera=bpy.data.objects[views[0]['camera']]
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT),compress=True)
    sources=['cross_axis_galleries_plan.py','cross_axis_galleries_architecture.py',
             'audit_cross_axis_gallery_sources.py','study_cross_axis_galleries_v1.py']
    dump(REPORT,{'built_at':now(),'native_file':str(OUT.relative_to(ROOT)),'native_sha256':digest(OUT),
                 'base_study_sha256':BASE_SHA,'preserved_base_objects':original_objects,
                 'plans':records,'views':views,
                 'sources':{n:digest(ROOT/'source'/n) for n in sources},
                 'source_audit_sha256':digest(ROOT/'cross_axis_galleries_source_and_plan_audit_v1.json'),
                 'source_manifest_sha256':digest(ROOT/'source/references/cross_axis_galleries/sources.json'),
                 'short_gate_junctions_present_in_local_study':False,
                 'complete_city_modified':False,'status':STATUS})
    print('GALLERY_STUDY_SAVED',OUT,flush=True)


def trees(objects, graph):
    result=[]
    for o in objects:
        evaluated=o.evaluated_get(graph)
        matrix=evaluated.matrix_world.copy()
        result.append((o.name,matrix,matrix.inverted_safe(),BVHTree.FromObject(o,graph)))
    return result


def ray(items, origin, direction, maximum):
    start=Vector(origin); d=Vector(direction)
    nearest=None
    for name,m,inv,tree in items:
        a=inv@start; c=inv@(start+d*maximum); dd=c-a
        hit,normal,face,dist=tree.ray_cast(a,dd.normalized(),dd.length)
        if hit is None:continue
        world=m@hit; distance=(world-start).length
        if nearest is None or distance<nearest[0]:nearest=(distance,list(world),name)
    return nearest


def verify():
    report=json.loads(REPORT.read_text('utf8'))
    assert digest(OUT)==report['native_sha256']
    for n,sha in report['sources'].items():assert digest(ROOT/'source'/n)==sha,n
    bpy.ops.wm.open_mainfile(filepath=str(OUT))
    bpy.context.view_layer.update()
    scene=bpy.context.scene
    graph=bpy.context.evaluated_depsgraph_get()
    site=Site(); errors=[]; checks=[]
    preserved=all(n in scene.objects for n in report['preserved_base_objects'])
    if not preserved:errors.append({'kind':'missing_base_objects'})
    for spec,saved in zip(RANGES,report['plans']):
        q=plan(site,spec)
        objects=[o for o in scene.objects if o.get('cross_axis_gallery')==spec['key']]
        meshes=[o for o in objects if o.type=='MESH']
        role=lambda names:[o for o in meshes if o.get('cross_axis_gallery_role') in names]
        support=trees(role(('plinth','paving','mortar')),graph)
        obstacle=trees(meshes,graph)
        post_trees=trees(role(('posts',)),graph)
        roof_trees=trees(role(('roof',)),graph)
        support_rays=0; clearance_rays=0; surface_samples=0
        # Longitudinal human route across all eleven bays, independently
        # checking side/body/head rays, overhead and foot support.
        start=q.xs[0]+.38; end=q.xs[-1]-.38
        path=[]
        for i in range(241):
            x=start+(end-start)*i/240; y=q.porch_path_y
            path.append((x,y))
        for i,(x,y) in enumerate(path):
            hit=ray(support,q.loc.world(x,y,FLOOR+.12),(0,0,-1),.25)
            support_rays+=1
            if hit is None or not FLOOR-.0041<hit[1][2]<FLOOR+.001:
                errors.append({'range':spec['key'],'kind':'porch_floor_support','index':i,'hit':hit})
            for height in (.30,1.20,1.85):
                for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    direction=Vector(q.loc.world(dx,dy))-Vector(q.loc.world())
                    hit=ray(obstacle,q.loc.world(x,y,FLOOR+height),direction,.27)
                    clearance_rays+=1
                    if hit:errors.append({'range':spec['key'],'kind':'body_clearance','index':i,'hit':hit})
            ceiling=ray(obstacle,q.loc.world(x,y,FLOOR+1.85),(0,0,1),.35)
            clearance_rays+=1
            if ceiling:errors.append({'range':spec['key'],'kind':'head_clearance','index':i,'hit':ceiling})
        # Deliberately sample exact mortar joint axes, not just paver centres.
        deck=q.loc.local(site.geom(spec['deck'])); dx0,dy0,dx1,dy1=deck.bounds
        for j in range(1,int((dy1-dy0)/.58)):
            for i in range(1,int((dx1-dx0)/.86),3):
                x=dx0+(i+.5*(j%2))*.86; y=dy0+j*.58
                if not deck.buffer(-.02).contains(Point(x,y)):continue
                hit=ray(support,q.loc.world(x,y,FLOOR+.10),(0,0,-1),.22)
                surface_samples+=1
                if hit is None or abs(hit[1][2]-(FLOOR-.003))>.001:
                    errors.append({'range':spec['key'],'kind':'recessed_mortar_support','x':x,'y':y,'hit':hit})
        # An actual opening must separate front posts and the setback facade.
        for a,c in zip(q.xs,q.xs[1:]):
            x=(a+c)/2
            direction=Vector(q.loc.world(0,1))-Vector(q.loc.world())
            hit=ray(obstacle,q.loc.world(x,q.front_y-.40,FLOOR+1.5),direction,q.wall_y-q.front_y-.02)
            clearance_rays+=1
            if hit:errors.append({'range':spec['key'],'kind':'solid_front_wall_survives','hit':hit})
        for x in q.xs:
            direction=Vector(q.loc.world(1,0))-Vector(q.loc.world())
            hit=ray(post_trees,q.loc.world(x,q.front_y,FLOOR+1),direction,.24)
            if hit is None:errors.append({'range':spec['key'],'kind':'missing_native_porch_post','x':x})
        # Roof frame must stay under the actual evaluated roof shell.
        frame_vertices=0; max_excess=-1e9
        for obj in role(('roof_frame',)):
            eo=obj.evaluated_get(graph); em=eo.to_mesh()
            try:
                for i,v in enumerate(em.vertices):
                    if i%13:continue
                    world=eo.matrix_world@v.co
                    if world.z<POST_TOP+.8:continue
                    hit=ray(roof_trees,(world.x,world.y,14),(0,0,-1),10)
                    if hit:
                        excess=world.z-(hit[1][2]-.17)
                        max_excess=max(max_excess,excess);frame_vertices+=1
                        if excess>.025:errors.append({'range':spec['key'],'kind':'frame_above_roof','excess_m':excess})
            finally:eo.to_mesh_clear()
        area=saved['paving']
        if abs(area['paver_area_m2']+area['joint_area_m2']-area['footprint_area_m2'])>1e-5:
            errors.append({'range':spec['key'],'kind':'paving_area_mismatch'})
        checks.append({'range':spec['key'],'native_meshes':len(meshes),
                       'provisional_long_range_bays':BAY_COUNT,'native_front_post_positions':len(q.xs),
                       'path_positions':len(path),'support_rays':support_rays,
                       'body_head_front_clearance_rays':clearance_rays,'mortar_joint_samples':surface_samples,
                       'sampled_high_frame_vertices':frame_vertices,'max_frame_excess_m':max_excess})
    result={'passed':not errors,'verified_at':now(),'native_sha256':report['native_sha256'],
            'preserved_gate_study_objects':preserved,'ranges':checks,'errors':errors,
            'scope':'Actual reopened local model; no current-city junction/level or field-accuracy certification.',
            'dimension_status':STATUS,'complete_city_modified':False}
    dump(VALIDATION,result)
    if errors:raise RuntimeError('Gallery study checks failed: '+str(errors[:6]))
    print('GALLERY_STUDY_REOPENED_CHECKS_PASSED',json.dumps(checks),flush=True)


def render(args):
    report=json.loads(REPORT.read_text('utf8'))
    validation=json.loads(VALIDATION.read_text('utf8'))
    assert validation['passed'] and digest(OUT)==validation['native_sha256']==report['native_sha256']
    bpy.ops.wm.open_mainfile(filepath=str(OUT))
    scene=bpy.context.scene
    configure_cycles(scene)
    scene.cycles.samples=args.samples
    scene.cycles.use_denoising=True
    scene.cycles.max_bounces=8
    scene.render.resolution_x=args.width
    scene.render.resolution_y=round(args.width*9/16)
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGB'
    for view in sorted(report['views'],key=lambda v:v['key']):
        if str(view['key']) not in args.views.split(','):continue
        out=ROOT/'renders'/f'{view["key"]}_cross_axis_galleries_study_v1.png'
        if out.exists():raise RuntimeError('Refusing to overwrite an existing study render: '+out.name)
        scene.camera=bpy.data.objects[view['camera']]
        scene.view_settings.exposure=view['exposure']
        scene.render.filepath=str(out)
        bpy.ops.render.render(write_still=True)
        dump(out.with_suffix('.render.json'),{'native_file':str(OUT.relative_to(ROOT)),
             'native_sha256':report['native_sha256'],'image_sha256':digest(out),
             'camera':view['camera'],'rendered_at':now(),'width':scene.render.resolution_x,
             'height':scene.render.resolution_y,'samples':args.samples,
             'exposure':view['exposure'],'device':scene.cycles.device,'complete_city_render':False})
        print('GALLERY_STUDY_IMAGE_SAVED',out.name,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('build','verify','render'))
    parser.add_argument('--views',default='201,202,203,204,205,206')
    parser.add_argument('--width',type=int,default=1440)
    parser.add_argument('--samples',type=int,default=32)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.mode=='build':build()
    elif args.mode=='verify':verify()
    else:render(args)
