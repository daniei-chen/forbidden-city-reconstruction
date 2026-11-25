"""Install, verify and render the two outer-court timber hall pairs."""

import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from osm_site import Site
from paired_hall_plans import PAIRS, split_plan
from paired_halls import build_pair, courtyard_materials
from refine_immersive import use_existing_palette, camera
from outer_court_walkthrough import add_walkthrough, SCENE as WALK_SCENE

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'The_Forbidden_City_Wenyuan_Architectural_Revision.blend'
OUTPUT = ROOT/'The_Forbidden_City_Outer_Court_Revision.blend'
REPORT = ROOT/'outer_court_revision_report.json'
CHECKS = ROOT/'validation_outer_court_revision.json'
VIEWS = {
    '27':'27_wenhua_courtyard', '28':'28_wenhua_connected_roofs',
    '29':'29_wuying_courtyard', '30':'30_wuying_connected_roofs',
    '31':'31_wenhua_eave_and_joinery', '32':'32_wuying_portico',
}


def add_cameras(pair, plan, index):
    roof_x = plan.front.centre[0]
    prefix = 27+2*index
    views = (
        (prefix, pair.front+'庭院', (roof_x,plan.front.y0-(23.5 if index==0 else 26.7),1.65),
         (roof_x,plan.front.y0+1.3,5.55), 20 if index==0 else 22),
        (prefix+1,pair.front+'前后殿及穿廊',(-39,-33,61), (0,-.25,1.7), 36),
        (31+index,pair.front+'前檐下', (roof_x-4.0,plan.front.y0-5.8,1.73),
         (roof_x+1.3,plan.front.y0+2.1,4.90), 26),
    )
    for number,name,eye,aim,lens in views:
        obj=camera(f'{number} · {name}',plan.world(*eye),plan.world(*aim),lens)
        obj.data.clip_end=6000


def build():
    bpy.ops.wm.open_mainfile(filepath=str(BASE))
    scene=bpy.context.scene
    root=bpy.data.collections['紫禁城 · EDITABLE 3D MASTER']
    site=Site()
    pal=use_existing_palette()
    courtyard_materials(pal)
    if scene.animation_data:
        scene.animation_data.action=None
    scene.frame_set(1)
    report={'source_blend':BASE.name,'native_blend':OUTPUT.name,'pairs':[]}
    for index,pair in enumerate(PAIRS):
        old=[o for o in scene.objects if any(str(o.get(k,''))==pair.ref for k in ('osm_id','source_osm_id'))]
        if len(old)!=2:
            raise RuntimeError(f'{pair.front} should have one old map envelope and one tile carrier, found {len(old)}')
        names=[o.name for o in old]
        for obj in old:
            data=obj.data
            bpy.data.objects.remove(obj,do_unlink=True)
            if data.users==0:
                bpy.data.meshes.remove(data)
        group,plan,entry=build_pair(site,pair,root,pal)
        add_cameras(pair,plan,index)
        entry['collection']=group.name
        entry['superseded']=names
        entry['mesh_objects']=len([o for o in group.all_objects if o.type=='MESH'])
        entry['polygons']=sum(len(o.data.polygons) for o in group.all_objects if o.type=='MESH')
        report['pairs'].append(entry)
        print('HALL_PAIR_BUILT',pair.front,entry['mesh_objects'],entry['polygons'],flush=True)
        if index==0:
            bpy.context.view_layer.update()
            report['wenhua_walkthrough']=add_walkthrough(scene,group,plan,pair)
            print('WENHUA_WALKTHROUGH_CHECKED',report['wenhua_walkthrough'],flush=True)
    scene.camera=next(o for o in scene.objects if o.type=='CAMERA' and o.name.startswith('29 '))
    scene['latest_outer_court_revision']='文华殿、主敬殿、武英殿、敬思殿和两条穿廊'
    scene['whole_city_every_detail_1to1_proven']=False
    scene.unit_settings.system='METRIC'
    scene.unit_settings.length_unit='METERS'
    scene.unit_settings.scale_length=1.
    bpy.context.view_layer.update()
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT),compress=True)
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')


def verify(scene):
    report=json.loads(REPORT.read_text('utf-8'))
    results={'file':OUTPUT.name,'checks':[]}

    def check(name, passed, evidence):
        results['checks'].append({'check':name,'passed':bool(passed),'evidence':evidence})

    check('Scene scale in metres',scene.unit_settings.system=='METRIC' and scene.unit_settings.scale_length==1,
          scene.unit_settings.scale_length)
    missing=[i.name for i in bpy.data.images if i.source=='FILE' and not i.packed_file and i.users]
    check('Referenced image assets packed',not missing,missing)
    walk=bpy.data.scenes.get(WALK_SCENE)
    check('Wenhua camera animation available in saved file',walk and walk.camera and walk.camera.animation_data
          and walk.frame_end==report['wenhua_walkthrough']['frames_checked'],report['wenhua_walkthrough'])
    site=Site()
    graph=bpy.context.evaluated_depsgraph_get()
    for pair, entry in zip(PAIRS,report['pairs']):
        group=bpy.data.collections[entry['collection']]
        plan=split_plan(site.geom(pair.ref))
        roofs=[o for o in group.all_objects if o.get('roof_type')]
        roof_types=sorted(o['roof_type'] for o in roofs)
        check(pair.front+' separated roof types',roof_types==['gable','xieshan','xieshan'],roof_types)
        old=[name for name in entry['superseded'] if name in scene.objects]
        check(pair.front+' superseded envelopes absent',not old,old)
        check(pair.front+' fit to mapped plan',plan.source_fit>=.97,plan.source_fit)
        openings=[]
        for offset in (-.27,0.,.27):
            x=plan.front.centre[0]+offset
            start=Vector(plan.world(x,plan.front.y0-1.,pair.floor+1.62))
            end=Vector(plan.world(x,plan.rear.centre[1],pair.floor+1.62))
            direction=end-start
            hit=scene.ray_cast(graph,start,direction.normalized(),distance=direction.length)
            if hit[0]:
                openings.append({'offset_m':offset,'hit':hit[4].name,'location':list(hit[1])})
        check(pair.front+' walkable line from terrace through both halls',not openings,openings)
        for name, env, z in ((pair.front,plan.front,pair.front_eave+pair.front_rise),
                             (pair.rear,plan.rear,pair.rear_eave+pair.rear_rise)):
            xy=env.centre
            hit=scene.ray_cast(graph,Vector(plan.world(*xy,z+4)),Vector((0,0,-1)))
            check(name+' expected ridge over mapped centre',hit[0] and abs(hit[1].z-z)<.65,
                  {'saved_z_m':hit[1].z,'specified_shell_z_m':z,'mesh':hit[4].name if hit[0] else None})
        count=sum(len(o.data.polygons) for o in group.all_objects if o.type=='MESH')
        check(pair.front+' mesh payload survived reload',count==entry['polygons'],count)
    results['passed']=all(item['passed'] for item in results['checks'])
    results['limits']='Geometry and map-fit checks. They do not establish exact survey agreement or photo identity.'
    CHECKS.write_text(json.dumps(results,ensure_ascii=False,indent=2),'utf-8')
    print('OUTER_COURT_CHECKS',results['passed'],len(results['checks']),flush=True)
    if not results['passed']:
        failed=[item for item in results['checks'] if not item['passed']]
        raise RuntimeError(f'Failed checks: {failed}')


def render(scene,args):
    scene.render.engine='CYCLES'
    prefs=bpy.context.preferences.addons['cycles'].preferences
    scene.cycles.device='CPU'
    try:
        prefs.compute_device_type='OPTIX'
        prefs.get_devices()
        for device in prefs.devices:
            device.use=device.type=='OPTIX'
        if any(device.use for device in prefs.devices):
            scene.cycles.device='GPU'
    except (RuntimeError,TypeError) as err:
        print('OptiX unavailable:',err,flush=True)
    scene.cycles.samples=args.samples
    scene.cycles.use_denoising=True
    scene.render.resolution_x=args.width
    scene.render.resolution_y=round(args.width*.68)
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGB'
    scene.frame_set(1)
    for prefix in args.views.split(','):
        scene.camera=next(o for o in scene.objects if o.type=='CAMERA' and o.name.startswith(prefix+' '))
        scene.view_settings.exposure=.10 if prefix in ('31','32') else -.12
        scene.render.filepath=str(ROOT/'renders'/(VIEWS[prefix]+'_'+args.suffix+'.png'))
        print('OUTER_COURT_VIEW_BEGIN',prefix,flush=True)
        bpy.ops.render.render(write_still=True)
        print('OUTER_COURT_VIEW_DONE',prefix,flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('build','verify','render'))
    parser.add_argument('--views',default='27,28,29,30,31,32')
    parser.add_argument('--width',type=int,default=1800)
    parser.add_argument('--samples',type=int,default=48)
    parser.add_argument('--suffix',default='outer_court')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.mode=='build':
        build()
        return
    bpy.ops.wm.open_mainfile(filepath=str(OUTPUT))
    scene=bpy.context.scene
    if args.mode=='verify':
        verify(scene)
    else:
        render(scene,args)


if __name__=='__main__':
    main()
