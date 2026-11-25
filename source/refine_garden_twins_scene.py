"""Install, inspect and render the Wanchun and Qianqiu pavilion meshes."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from export_wenyuan_revision import export_selected
from garden_bridge_pavilions import garden_materials
from garden_cross_pavilions import build_twin, in_world_side
from garden_cross_plan import FLOOR, MUSEUM, PLAN_PAPER, TWINS, map_plan
from garden_cross_room import CEILING_Z, RECESS
from mesh_tools import collection
from osm_site import Site
from outer_court_walkthrough import configure_cycles, first_hit
from qinan_hall import materials
from refine_immersive import camera, use_existing_palette
from refine_yude_tang_scene import area_light, geometry_trees

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'The_Forbidden_City_North_Garden_Revision.blend'
MASTER=ROOT/'The_Forbidden_City_Imperial_Garden_Twins.blend'
REPORT=ROOT/'garden_twins_revision_report.json'
VERIFY=ROOT/'validation_garden_twins_revision.json'
GROUP='御花园 · 万春亭、千秋亭'
GLB='Wanchun_and_Qianqiu_Pavilions.glb'
VIEWS={
    '57':('qianqiu_at_stair','千秋亭 · 从踏道仰望重檐',1,(10.7,-16.8,1.83),(0,-.15,6.62),33.,.06),
    '58':('wanchun_at_stair','万春亭 · 南向抱厦与白石栏板',0,(-10.5,-18.4,1.76),(0,-.84,6.57),33.,.09),
    '59':('wanchun_round_roof','万春亭 · 竹节瓦与琉璃华盖',0,(10.5,-13.6,14.42),(0,0,8.16),31.,.05),
    '60':('wanchun_inside','万春亭 · 双凤天花与盘龙衔珠',0,(1.19,-2.34,3.21),(0,.40,5.62),16.9,.44),
    '61':('qianqiu_inside','千秋亭 · 井口与四内柱',1,(-1.27,-2.16,3.19),(0,.22,5.69),16.5,.43),
    '62':('wanchun_glaze_and_plaque','万春亭 · 满汉匾额与瓦当',0,(.19,-8.67,9.16),(0,-3.10,9.56),49.,.09),
}


def build():
    bpy.ops.wm.open_mainfile(filepath=str(BASE))
    scene=bpy.context.scene
    site=Site()
    group=collection(GROUP,bpy.data.collections['紫禁城 · EDITABLE 3D MASTER'])
    refs=set().union(*(site.members(twin.relation) for twin in TWINS))
    deleted={}
    for obj in list(scene.objects):
        match=next((str(obj[k]) for k in ('osm_id','source_osm_id') if k in obj and str(obj[k]) in refs),None)
        if match is not None:
            deleted.setdefault(match,[]).append(obj.name)
            bpy.data.objects.remove(obj,do_unlink=True)
    # The base represents these relations by their member parts. Their outline
    # ways are plan references and need not have generated proxy objects.
    expected={ref for twin in TWINS for ref in (twin.terrace,twin.timber,twin.drum,twin.top,*twin.stairs)}
    if missing:=expected-deleted.keys():
        raise RuntimeError(f'Missing mapped twin pavilion proxy parts: {sorted(missing)}')
    gardens=materials(garden_materials(use_existing_palette()))
    outputs=[build_twin(site,twin,group,gardens) for twin in TWINS]
    lights=collection('万春千秋 · 可关闭的检视反照',group)
    for twin,(loc,_,_) in zip(TWINS,outputs):
        area_light(lights,twin.name+' · 门口天光返照',loc,(.06,-2.90,3.2),(0,.83,5.4),133,3.2,(1.,.92,.83))
        area_light(lights,twin.name+' · 槛窗地面漫反射',loc,(-2.68,.95,3.15),(0,.40,5.97),105,2.56,(.88,.94,1.))
    cams={}
    for n,(_,label,i,pos,aim,lens,_) in VIEWS.items():
        pose=outputs[i][0]
        cams[n]=camera(n+' · '+label,pose.world(*pos),pose.world(*aim),lens)
        cams[n].data.clip_end=1550
        cams[n].data.clip_start=.034
    scene.camera=cams['57']
    scene['latest_revision']='御花园北部与亚字平面的万春亭、千秋亭'
    scene['whole_city_every_detail_1to1_proven']=False
    scene.render.filepath='//renders/57_qianqiu_at_stair_twins_verified.png'
    scene.render.resolution_x,scene.render.resolution_y=2304,1584
    meshes=[o for o in group.all_objects if o.type=='MESH']
    report={'native_blend':MASTER.name,'base_blend':BASE.name,'collection':GROUP,
            'first_hand_sources':{'palace_museum':MUSEUM,'figure_14_and_site_plan':PLAN_PAPER},
            'pavilions':[row[2] for row in outputs],'replaced_map_objects':deleted,
            'new_editable_meshes':len(meshes),'new_native_polygons':sum(len(o.data.polygons) for o in meshes),
            'limits':['Map topology and drawn relative positions constrain the plan.',
                      'Original tile widths, section heights, wood carving and coating state are estimates.',
                      'Wall orientation, tile joints, and the physical openings are checked against the saved model.']}
    bpy.context.preferences.filepaths.save_version=0
    bpy.context.view_layer.update()
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(MASTER),compress=True)
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print('TWINS_MASTER',MASTER.name,len(meshes),flush=True)


def verify(scene):
    site=Site();data=json.loads(REPORT.read_text('utf-8'))
    graph=bpy.context.evaluated_depsgraph_get()
    tests=[]

    def check(name,ok,value):
        tests.append({'check':name,'passed':bool(ok),'evidence':value})

    check('metric scale',scene.unit_settings.system=='METRIC' and scene.unit_settings.scale_length==1.,scene.unit_settings.scale_length)
    walk=bpy.data.scenes.get('堆秀山 · 东磴道登御景亭')
    check('checked Dui Xiu native tour remains available',walk and walk.camera and walk.frame_end==480,
          sorted(s.name for s in bpy.data.scenes))
    missing=[name for names in data['replaced_map_objects'].values() for name in names if name in scene.objects]
    check('superseded map proxy objects are absent',not missing,missing)

    for twin,info in zip(TWINS,data['pavilions']):
        loc,deck,_,metrics=map_plan(site,twin)
        objects=bpy.data.collections[info['collection']].all_objects
        all_tree=geometry_trees(objects,graph)
        stairs_tree=geometry_trees([o for o in objects if '踏面与垂带' in o.name],graph)
        ceiling_tree=geometry_trees([o for o in objects if '真凹藻井' in o.name],graph)
        feet=[];openings=[]
        for stair in info['model_estimates']['stairs']:
            side=stair['side'];x=stair['local_centre_xy'][0]
            a,b=stair['start_end_y']
            heights=[]
            for j in range(stair['treads']):
                q=Vector(in_world_side(loc,side,x,a+(j+.53)*(b-a)/stair['treads'],FLOOR+.56))
                hit=first_hit(stairs_tree,q,Vector((0,0,-1)),2.0)
                heights.append(round(hit[1].z,4) if hit else None)
            feet.append(heights)
            q=Vector(in_world_side(loc,side,0,-6.24,FLOOR+1.56))
            end=Vector(in_world_side(loc,side,0,-2.75,FLOOR+1.56))
            d=end-q
            hit=first_hit(all_tree,q,d.normalized(),d.length)
            openings.append(hit[0] if hit else None)
        check(twin.name+' four independently rising staircases',all(
              None not in levels and abs(levels[-1]-FLOOR)<.004 and all(b-a>.13 for a,b in zip(levels,levels[1:]))
              for levels in feet),feet)
        check(twin.name+' genuine passage through both doors in each annex',all(x is None for x in openings),openings)
        posts=sum(o.get('post_role')=='outer_eave' for o in objects)
        inner=sum(o.get('post_role')=='four_main_corners' for o in objects)
        check(twin.name+' 12 outer and four separate inner posts',posts==12 and inner==4,[posts,inner])
        circle=next(o for o in objects if 'outer_radius_m' in o)
        geometric_radius=max(math.hypot(v.co.x,v.co.y) for v in circle.data.vertices)
        hip=next(o for o in objects if 'hip_tips' in o)
        tiles=next(o for o in objects if 'radial_tile_courses' in o)
        check(twin.name+' lower annex edge and circular, individually tiled upper roof',
              hip['hip_tips']==12 and hip['reentrant_eaves']==8 and
              abs(geometric_radius-metrics['upper_eave_radius_m'])<.0002 and tiles['radial_tile_courses']>95,
              {'radius_m':geometric_radius,'mapped_radius_m':metrics['upper_eave_radius_m'],
               'lower_projecting_hips':hip['hip_tips'],'cap_tile_courses':tiles['radial_tile_courses']})
        trace=lambda x,y:first_hit(ceiling_tree,Vector(loc.world(x,y,4.65)),Vector((0,0,1)),3.6)
        crown=trace(.041,.058);near=trace(2.48,1.63)
        check(twin.name+' recessed caisson exists above the main ceiling plane',crown and near and
              abs(crown[1].z-CEILING_Z-RECESS)<.012 and abs(near[1].z-CEILING_Z)<.012,
              [crown[1].z if crown else None,near[1].z if near else None])
    evidence={'file':MASTER.name,'passed':all(row['passed'] for row in tests),'tests':tests,
              'scope':'Reopened scene and physical geometry; no field height or pixel-level proof.'}
    VERIFY.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),'utf-8')
    print('TWINS_VERIFY',evidence['passed'],len(tests),flush=True)
    if not evidence['passed']:
        raise RuntimeError([t for t in tests if not t['passed']])


def render(scene,args):
    configure_cycles(scene)
    scene.render.resolution_percentage=100
    scene.render.resolution_x=args.width
    scene.render.resolution_y=round(args.width*.6875)
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGB'
    scene.render.use_persistent_data=True
    scene.cycles.samples=args.samples
    scene.cycles.use_denoising=True
    if scene.cycles.device=='GPU':scene.cycles.denoiser='OPTIX'
    for n in args.views.split(','):
        stem,*_,exposure=VIEWS[n]
        scene.camera=next(o for o in scene.objects if o.type=='CAMERA' and o.name.startswith(n+' '))
        scene.view_settings.exposure=exposure
        scene.render.filepath=str(ROOT/'renders'/f'{n}_{stem}_{args.suffix}.png')
        print('TWINS_RENDER',n,scene.cycles.device,flush=True)
        bpy.ops.render.render(write_still=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=('build','verify','render','export'))
    p.add_argument('--width',type=int,default=2304)
    p.add_argument('--samples',type=int,default=88)
    p.add_argument('--views',default=','.join(VIEWS))
    p.add_argument('--suffix',default='twins_verified')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if args.mode=='build':build();return
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    scene=bpy.context.scene
    if args.mode=='verify':verify(scene)
    elif args.mode=='render':render(scene,args)
    else:
        meshes=[o for o in bpy.data.collections[GROUP].all_objects if o.type=='MESH' and o.data.polygons]
        print(export_selected(ROOT/'exports'/GLB,meshes),flush=True)


if __name__=='__main__':main()
