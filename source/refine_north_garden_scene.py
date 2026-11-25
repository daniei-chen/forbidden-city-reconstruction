"""Install the measured Hall of Imperial Peace and its garden neighbours in the city master."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from duixiu_rockery import (CAVE_X, CAVE_Y, CAVE_Z, EAST, PAVILION_Z, PORTAL, SUMMIT_Z, WEST, build_rockery, flight_settings)
from export_wenyuan_revision import export_selected
from garden_bridge_pavilions import garden_materials
from mesh_tools import collection
from osm_site import Site
from outer_court_walkthrough import configure_cycles, first_hit
from qinan_furnishings import build_furnishings
from qinan_hall import build_qinan, materials
from qinan_survey import (CEILING, DATUM, DUIXIU, EAVE_COLUMN, FLOOR, GOLD_COLUMN, LOW_FOOT_X,
                          LOW_FOOT_Y, QIN, TIANYI, TOP_BOARD, YUJING, Location, replacements)
from refine_immersive import camera, use_existing_palette
from refine_yude_tang_scene import area_light, geometry_trees
from tianyi_court import GATE_CROWN, GATE_FLOOR, build_tianyi, court_landscape, court_walls

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'The_Forbidden_City_Imperial_Garden_Revision.blend'
MASTER=ROOT/'The_Forbidden_City_North_Garden_Revision.blend'
REPORT=ROOT/'north_garden_revision_report.json'
VALIDATION=ROOT/'validation_north_garden_revision.json'
GROUP='御花园 · 钦安殿、天一门与堆秀山'
GLB='North_Imperial_Garden_Geometry.glb'
VIEWS={
    '46':('46_qinan_front_court','钦安殿月台与重檐',QIN,(11.37,-23.25,2.44),(-.82,-4.37,6.53),25.2,.11),
    '47':('47_qinan_flat_roof','钦安殿盝顶与四脊',QIN,(17.8,-22.7,19.2),(0,-1.82,8.13),33,.04),
    '48':('48_tianyi_arch','天一门、铜獬豸与左右影壁',TIANYI,(.04,-12.9,1.82),(0,0,2.76),35.3,.055),
    '49':('49_qinan_interior','钦安殿内减柱与正龛',QIN,(-.37,-2.97,3.29),(.02,3.2,4.08),23.2,.49),
    '50':('50_duixiu_from_below','堆秀山、洞口及峰顶御景亭',DUIXIU,(-5.68,-25.0,2.26),(.08,-2.61,7.78),31.0,.07),
    '51':('51_duixiu_cave','堆秀山洞室与蟠龙石雕',DUIXIU,(.11,-5.67,1.32),(.16,-3.00,2.51),15.9,.46),
    '52':('52_yujing_peak','从东磴道望御景亭',DUIXIU,(8.68,1.38,13.15),(.12,2.57,12.56),21.4,.10),
    '53':('53_duixiu_stone_fountain','堆秀山东侧石蟠龙水法',DUIXIU,(5.8,-11.93,1.66),(3.9,-6.35,1.99),53,.09),
    '54':('54_qinan_ceiling','钦安殿天花与藻井',QIN,(-.61,-1.73,5.89),(0,.3,DATUM+CEILING+.45),19.3,.41),
    '55':('55_yujing_inside','御景亭内南向宝座与藻井',YUJING,(1.42,-1.99,PAVILION_Z+1.46),(0,.20,PAVILION_Z+1.95),16.2,.35),
    '56':('56_yujing_rock_and_pine','古松与叠石间仰望御景亭',DUIXIU,(-8.94,-16.02,2.10),(.02,-1.45,9.38),26.5,.07),
}


def fill(target,loc,name,eye,aim,power,radius,tone=(1.,.91,.78)):
    area_light(target,name,loc,eye,aim,power,radius,tone)


def build():
    bpy.ops.wm.open_mainfile(filepath=str(BASE))
    scene=bpy.context.scene
    site=Site()
    root=bpy.data.collections['紫禁城 · EDITABLE 3D MASTER']
    main=collection(GROUP,root)
    locs={ref:Location.from_map(site,ref) for ref in (QIN,TIANYI,DUIXIU,YUJING)}
    refs=replacements(site)
    removed={}
    for obj in list(scene.objects):
        hit=next((str(obj[k]) for k in ('osm_id','source_osm_id') if k in obj and str(obj[k]) in refs),None)
        if hit is not None:
            removed.setdefault(hit,[]).append(obj.name)
            bpy.data.objects.remove(obj,do_unlink=True)
    if not all(ref in removed for ref in (TIANYI,YUJING,'685600280','685600276','685600259')):
        raise RuntimeError(f'Old proxy assemblies are missing or changed: {sorted(removed)}')
    print('NORTH_GARDEN_REMOVED',sum(map(len,removed.values())),flush=True)
    p=materials(garden_materials(use_existing_palette()))
    hall,qinan=build_qinan(site,locs[QIN],main,p)
    qinan['interior_furnishings']=build_furnishings(locs[QIN],hall,p)
    print('QINAN_MESHES',len(hall.all_objects),flush=True)
    gate,tianyi=build_tianyi(site,locs[TIANYI],main,p)
    court_walls(site,main,p)
    court_landscape(site,main,p)
    print('TIANYI_MESHES',len(gate.all_objects),flush=True)
    rockery,duixiu=build_rockery(site,locs[DUIXIU],main,p)
    print('DUIXIU_MESHES',len(rockery.all_objects),flush=True)
    lights=collection('御花园北部 · 可关闭的渲染检视补光',main)
    fill(lights,locs[QIN],'钦安殿 · 南檐返照',(-.25,-4.61,4.1),(.2,1.7,4.0),235,3.9)
    fill(lights,locs[QIN],'钦安殿 · 天花漫射补光',(.12,-1.74,5.08),(0,.03,9.72),162,2.9)
    fill(lights,locs[QIN],'钦安殿 · 后部石地反射',(-4.84,.23,3.04),(0,3.63,4.19),171,2.5,(.94,.94,1.))
    fill(lights,locs[DUIXIU],'堆秀山 · 券洞反照',(.12,-4.63,.65),(.12,-2.77,2.33),14,.76)
    fill(lights,locs[YUJING],'御景亭 · 地面天光反照',(1.81,-1.13,PAVILION_Z+.76),(.05,.38,PAVILION_Z+2.53),42,2.14)
    for prefix,(_,label,ref,eye,aim,lens,_) in VIEWS.items():
        loc=locs[ref]
        obj=camera(f'{prefix} · {label}',loc.world(*eye),loc.world(*aim),lens)
        obj.data.clip_start=.032
        obj.data.clip_end=1550
    scene.camera=next(o for o in scene.objects if o.type=='CAMERA' and o.name.startswith('50 '))
    scene['latest_revision']='钦安殿实测柱网与盝顶、天一门青砖券门、堆秀山叠石和御景亭'
    scene['whole_city_every_detail_1to1_proven']=False
    meshes=[o for o in main.all_objects if o.type=='MESH']
    report={'native_blend':MASTER.name,'base_blend':BASE.name,'collection':GROUP,
            'qinan':qinan,'tianyi':tianyi,'duixiu':duixiu,'removed_generic_proxy_objects':removed,
            'new_mesh_objects':len(meshes),'new_mesh_datablocks':len({o.data.as_pointer() for o in meshes}),
            'fidelity_limit':'Actual metres with individually classified evidence. Unpublished surfaces are interpreted; full-city pixel matching remains unverified.'}
    bpy.context.preferences.filepaths.save_version=0
    bpy.context.view_layer.update()
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(MASTER),compress=True)
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print('NORTH_GARDEN_MASTER',MASTER.name,len(meshes),flush=True)


def verify(scene):
    data=json.loads(REPORT.read_text('utf-8'))
    deps=bpy.context.evaluated_depsgraph_get()
    site=Site()
    tests=[]
    def check(name,passed,detail):
        tests.append({'check':name,'passed':bool(passed),'evidence':detail})
    def trace(loc,objects):
        trees=geometry_trees(objects,deps)
        def cast(a,c):
            start=Vector(loc.world(*a));end=Vector(loc.world(*c));d=end-start
            hit=first_hit(trees,start,d.normalized(),d.length)
            return (hit[0],round(hit[1].z,5)) if hit else None
        return cast

    check('Metric units',scene.unit_settings.system=='METRIC' and scene.unit_settings.scale_length==1.,
          scene.unit_settings.scale_length)
    missing=[name for rows in data['removed_generic_proxy_objects'].values() for name in rows if name in scene.objects]
    check('Old target proxy shells and tile carriers removed',not missing,missing)
    check('Earlier three native tours preserved',all(bpy.data.scenes.get(n) for n in
          ('澄瑞亭 · 过桥仰看双龙藻井','浴德堂 · 穿过券道看穹顶','文华殿 · 海棠甬路至檐下')),len(bpy.data.scenes))

    grove=bpy.data.collections[data['qinan']['collection']]
    qin=Location.from_map(site,QIN)
    posts=[obj for obj in grove.all_objects if obj.get('post_role')=='eave']
    gold=[obj for obj in grove.all_objects if obj.get('post_role')=='gold']
    low=[list(o['foot_centre_m']) for o in posts]
    xs=sorted({p[0] for p in low});ys=sorted({p[1] for p in low})
    xspan=[round(b-a,4) for a,b in zip(xs,xs[1:])];yspan=[round(b-a,4) for a,b in zip(ys,ys[1:])]
    check('Qinan five and three axes use surveyed column bases',xspan==list(LOW_FOOT_X) and yspan==list(LOW_FOOT_Y),
          {'x_bays_m':xspan,'y_bays_m':yspan})
    check('Sixteen eave posts and four retained inner posts at measured heights',len(posts)==16 and len(gold)==4
          and all(math.isclose(float(obj['timber_height_m']),EAVE_COLUMN,abs_tol=1e-6) for obj in posts)
          and all(math.isclose(float(obj['timber_height_m']),GOLD_COLUMN,abs_tol=1e-6) for obj in gold),
          {'eave_posts':len(posts),'gold_posts':len(gold),'eave_height_m':EAVE_COLUMN,'gold_height_m':GOLD_COLUMN})
    check('No inner posts at the four omitted central junctions',all(abs(o['foot_centre_m'][0])>5.9 for o in gold),
          [list(o['foot_centre_m']) for o in gold])
    beams=[obj for obj in grove.all_objects if 'section_height_m' in obj]
    section=[(round(o.dimensions.z,3),round(o['section_width_m'],3)) for o in beams]
    check('Two original-type huataifang sections use 920 x 540 mm',section==[(.92,.54),(.92,.54)],section)
    boards=[o for o in grove.all_objects if 'board_levels_from_base_m' in o]
    levels=[(round(min(v[2] for v in o.bound_box)-DATUM,3),round(max(v[2] for v in o.bound_box)-DATUM,3)) for o in boards]
    check('Flat roof boards are at measured lower and upper faces',levels==[TOP_BOARD],levels)
    ceiling=trace(qin,[o for o in grove.all_objects if '井口板' in o.name])
    main_ceil=ceiling((2.68,.47,7.59),(2.68,.47,12))
    inset=ceiling((.07,0,7.59),(.07,0,12.2))
    check('Qinan main ceiling stays at the surveyed plane and opens into the caisson',
          main_ceil and abs(main_ceil[1]-DATUM-CEILING)<.009 and inset and inset[1]-main_ceil[1]>.55,
          {'main_plane':main_ceil,'recess':inset})
    interiors=data['qinan']['interior_furnishings']
    names=[o.name for o in bpy.data.collections[interiors['collection']].all_objects if o.get('reconstruction_role')]
    check('The central shrine and ten catalogue side shrines are individually editable',
          interiors['shrine_assemblies']==11 and sorted(names)==sorted(interiors['modelled_sequence']),names)
    room_trace=trace(qin,grove.all_objects)
    closed_eaves=[room_trace((0,0,5.85),end) for end in ((0,9,7.52),(0,-10,7.47),(14,0,7.52),(-14,0,7.52))]
    clear_shrine=room_trace((0,-2.96,3.54),(0,2.71,4.16))
    check('Qinan camera has an unblocked sightline up to the shrine and a closed roof perimeter',
          clear_shrine is None and all(closed_eaves),{'sightline':clear_shrine,'walls':closed_eaves})

    gate=trace(Location.from_map(site,TIANYI),bpy.data.collections[data['tianyi']['collection']].all_objects)
    inlet=gate((0,-2.48,1.79),(0,2.22,1.79))
    jamb=gate((1.23,-2.32,1.72),(1.23,2.16,1.72))
    crown=gate((0,-.09,GATE_FLOOR+.11),(0,-.09,4.12))
    check('Tianyi gate is a real through arch with open doors',not inlet and jamb and crown
          and abs(crown[1]-GATE_CROWN)<.035,{'through':inlet,'jamb':jamb,'intrados':crown})
    leaves=[o for o in bpy.data.collections[data['tianyi']['collection']].all_objects if 'bronze_stud_count' in o]
    check('The two individually hinged doors each have nine by nine modeled studs',
          len(leaves)==2 and all(o['bronze_stud_count']==81 and 'closed_world_yaw_rad' in o for o in leaves),
          [int(o['bronze_stud_count']) for o in leaves])

    rock=Location.from_map(site,DUIXIU)
    rock_group=bpy.data.collections[data['duixiu']['collection']]
    cave=trace(rock,[o for o in rock_group.all_objects if '叠石 ' not in o.name])
    floor=cave((CAVE_X+.07,CAVE_Y,1.22),(CAVE_X+.07,CAVE_Y,-.34))
    crown=cave((CAVE_X+.07,CAVE_Y,1.22),(CAVE_X+.07,CAVE_Y,4))
    inner=cave((CAVE_X,PORTAL-.70,1.49),(CAVE_X,CAVE_Y+.26,1.49))
    check('Rockery entry is void and leaves a brick chamber below carved ceiling',not inner and floor
          and abs(floor[1]-CAVE_Z)<.014 and crown and 2.79<crown[1]<3.18,
          {'through':inner,'supported_floor':floor,'vault':crown})
    stair_cast=trace(rock,[o for o in rock_group.all_objects if '磴道踏面' in o.name or '山顶白石台盘' in o.name])
    for side,route in (('west',WEST),('east',EAST)):
        bad=[];sample=0
        for (a,c),(distance,start,end,count,run) in zip(zip(route,route[1:]),flight_settings(route)):
            for j in range(count):
                along=start+(j+.55)*run
                t=along/distance
                u=[a[0]*(1-t)+c[0]*t,a[1]*(1-t)+c[1]*t,a[2]+(c[2]-a[2])*(j+1)/count]
                found=stair_cast((u[0],u[1],u[2]+.35),(u[0],u[1],u[2]-.20))
                if not found or abs(found[1]-u[2])>.035:
                    bad.append([u,found])
                sample+=1
        check(f'{side} rock stair treads rise to summit',not bad,{'tread_samples':sample,'failures':bad[:6]})
    t=[stair_cast((x,y,SUMMIT_Z+.15),(x,y,SUMMIT_Z-.21)) for x,y in ((-.57,-.64),(.23,-.38),(1.37,-.91))]
    check('Summit paving is close to the museum’s approximate 10 m',sum(bool(v and abs(v[1]-SUMMIT_Z)<.012) for v in t)>=2,t)
    pv=bpy.data.collections[data['duixiu']['summit_pavilion']]
    check('Four freestanding summit pavilion columns and native yellow-border green tiles',
          sum(int(o.get('post_component',0)) for o in pv.all_objects)==4 and any('individually curved' in o.name for o in pv.all_objects),
          len(pv.all_objects))
    pavilion=Location.from_map(site,YUJING)
    room=trace(pavilion,pv.all_objects)
    threshold=room((4.,0,PAVILION_Z+1.42),(1.76,0,PAVILION_Z+1.42))
    ceiling_surface=trace(pavilion,[o for o in pv.all_objects if '八方井壁' in o.name])
    tray=ceiling_surface((.01,.04,PAVILION_Z+1.73),(.01,.04,PAVILION_Z+3.94))
    apron=ceiling_surface((1.44,.69,PAVILION_Z+1.73),(1.44,.69,PAVILION_Z+3.94))
    check('Summit pavilion has a physical east opening and an inset ceiling over the throne',
          not threshold and tray and apron and abs((tray[1]-apron[1])-.445)<.018
          and any('南向宝座、台座及靠背' in o.name for o in pv.all_objects),
          {'east_opening':threshold,'ceiling_crown':tray,'surrounding_ceiling':apron})
    tour=data.get('duixiu_walkthrough')
    if tour:
        walk=bpy.data.scenes.get(tour['scene'])
        check('Native ascent timeline and validated frame count are present after reopen',
              walk and walk.camera and walk.camera.animation_data and walk.frame_end==tour['frames_checked']==480,
              {'frame_end':walk.frame_end if walk else None,'fps':walk.render.fps if walk else None})
    report={'file':MASTER.name,'passed':all(t['passed'] for t in tests),'tests':tests,
            'scope':'Saved geometry, documentary dimensions and physical openings. Not a field scan comparison.'}
    VALIDATION.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print('NORTH_GARDEN_VERIFIED',report['passed'],len(tests),flush=True)
    if not report['passed']:
        raise RuntimeError([v for v in tests if not v['passed']])


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
    if scene.cycles.device=='GPU':
        scene.cycles.denoiser='OPTIX'
    for prefix in args.views.split(','):
        stem,*_,exposure=VIEWS[prefix]
        scene.camera=next(o for o in scene.objects if o.type=='CAMERA' and o.name.startswith(prefix+' '))
        scene.view_settings.exposure=exposure
        scene.render.filepath=str(ROOT/'renders'/f'{stem}_{args.suffix}.png')
        door_pose=[(o,o.rotation_euler.z) for o in scene.objects if o.name.startswith('天一门') and 'closed_world_yaw_rad' in o] if prefix=='48' else []
        for obj,_ in door_pose:
            obj.rotation_euler.z=obj['closed_world_yaw_rad']
        bpy.context.view_layer.update()
        print('NORTH_GARDEN_RENDER',prefix,scene.cycles.device,flush=True)
        try:
            bpy.ops.render.render(write_still=True)
        finally:
            for obj,angle in door_pose:
                obj.rotation_euler.z=angle


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('build','verify','render','export'))
    parser.add_argument('--width',type=int,default=2304)
    parser.add_argument('--samples',type=int,default=80)
    parser.add_argument('--views',default=','.join(VIEWS))
    parser.add_argument('--suffix',default='north_verified')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if args.mode=='build':
        build();return
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    scene=bpy.context.scene
    if args.mode=='verify':
        verify(scene)
    elif args.mode=='render':
        render(scene,args)
    else:
        meshes=[o for o in bpy.data.collections[GROUP].all_objects if o.type=='MESH' and o.data.polygons]
        print(export_selected(ROOT/'exports'/GLB,meshes),flush=True)


if __name__=='__main__':
    main()
