"""Replace two garden roof proxies in the editable city with documented bridge pavilions."""
import argparse
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector
from shapely.geometry import Point
from shapely.prepared import prep

sys.path.insert(0,str(Path(__file__).resolve().parent))
from export_wenyuan_revision import export_selected
from garden_bridge_pavilions import (CAISSON_EDGE, CEILING_PHOTO, DECK, STUDIES, WATER, WIDTH,
                                    build_pavilion, garden_materials, plan_from_map)
from garden_context import HALLS, garden_context
from garden_walkthrough import WALK_SCENE as GARDEN_WALK_SCENE
from mesh_tools import collection
from osm_site import Site, rectangle
from outer_court_walkthrough import configure_cycles, first_hit
from refine_immersive import camera, use_existing_palette
from refine_yude_tang_scene import area_light, geometry_trees

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'The_Forbidden_City_Yude_Tang_Revision.blend'
MASTER=ROOT/'The_Forbidden_City_Imperial_Garden_Revision.blend'
REPORT=ROOT/'imperial_garden_revision_report.json'
VALIDATION=ROOT/'validation_imperial_garden_revision.json'
GROUP='御花园 · 浮碧亭与澄瑞亭'
VIEWS={
    '40':('40_fubi_pool_and_pavilion','浮碧亭与方池',0,(13.98,-10.02,2.17),(0,-.74,3.64),26.2,.16),
    '41':('41_chengrui_south_approach','澄瑞亭南面',1,(.43,-17.70,1.68),(0,-.73,2.95),34,.09),
    '42':('42_chengrui_double_dragon_caisson','澄瑞亭双龙藻井',1,(.03,3.11,2.20),(0,3.67,5.09),20.5,.42),
    '43':('43_fubi_bridge_water_level','浮碧亭券桥水面',0,(-12.63,-3.02,1.82),(-1.22,.70,2.20),25.5,.18),
    '44':('44_garden_bridge_pavilion_from_east','澄瑞亭屋面与池岸',1,(14.8,-9.92,7.40),(0,.18,3.65),28,.09),
    '45':('45_fubi_painted_soffit','浮碧亭百花天花',0,(-.82,2.14,2.34),(0,3.87,5.05),21.5,.47),
}


def clear_generic_pool(obj,site):
    mesh=bmesh.new()
    mesh.from_mesh(obj.data)
    matrix=obj.matrix_world.copy()
    zones={study.pond:prep(site.geom(study.pond).buffer(.285,join_style=2)) for study in STUDIES}
    counts={key:0 for key in zones}
    removed=[]
    for face in mesh.faces:
        points=[matrix@v.co for v in face.verts]
        centre=Point(sum(p.x for p in points)/len(points),sum(p.y for p in points)/len(points))
        for key,zone in zones.items():
            if zone.covers(centre) and all(zone.covers(Point(p.x,p.y)) for p in points):
                removed.append(face)
                counts[key]+=1
                break
    if not all(counts.values()):
        mesh.free()
        raise RuntimeError(f'Expected both separated old pools in the terrain mesh: {counts}')
    bmesh.ops.delete(mesh,geom=removed,context='FACES')
    mesh.to_mesh(obj.data)
    mesh.free()
    obj.data.update()
    return counts


def build():
    bpy.ops.wm.open_mainfile(filepath=str(BASE))
    scene=bpy.context.scene
    site=Site()
    root=bpy.data.collections['紫禁城 · EDITABLE 3D MASTER']
    p=garden_materials(use_existing_palette())
    target=collection(GROUP,root)
    refs={s.way for s in STUDIES}|{hall[1] for hall in HALLS}
    removed={ref:[] for ref in refs}
    for obj in list(scene.objects):
        for key in ('osm_id','source_osm_id'):
            ref=str(obj.get(key,''))
            if ref in refs:
                removed[ref].append(obj.name)
                bpy.data.objects.remove(obj,do_unlink=True)
                break
    if any(len(removed[s.way])!=3 for s in STUDIES) or any(not removed[hall[1]] for hall in HALLS):
        raise RuntimeError(f'Expected each roof proxy and both field and border tile carriers: {removed}')
    streams=next(obj for obj in scene.objects if obj.name.startswith('内金水河与池塘 ·'))
    old_water=clear_generic_pool(streams,site)
    plans=[plan_from_map(site,study) for study in STUDIES]
    report={'source_blend':BASE.name,'native_blend':MASTER.name,'collection':GROUP,'pavilions':[],
            'whole_city_every_detail_1to1_proven':False,
            'study_limits':['Museum records specify about 8 m across the column grid, shape and subjects.',
                            'Pond plan and pavilion position come from mapped outlines.',
                            'Bridge elevation, timber sizes, tile curves and ornament are reconstructed from reference views.',
                            'Plant placement and lighting are interpretations of garden conditions.']}
    for study,plan in zip(STUDIES,plans):
        group=build_pavilion(study,plan,target,p)
        lighting=collection(study.name+' · 渲染检视补光',group)
        area_light(lighting,study.name+' · 青白石反射补光',plan,(.18,plan.main_y-.96,2.72),
                   (0,plan.main_y,4.96),87,2.46,(1.,.95,.85))
        area_light(lighting,study.name+' · 抱厦石台反射补光',plan,(.40,plan.front_y+1.9,1.75),
                   (0,plan.front_y+.66,4.2),63,2.18,(.89,.95,1.))
        _,_,pond_length,pond_width,_=rectangle(site.geom(study.pond))
        metrics={'name':study.name,'collection':group.name,'museum':study.museum,'photographs':study.photographs,
                 'caisson_reference':CEILING_PHOTO if study.caisson=='dragons' else study.museum,
                 'documented_approx_width_m':WIDTH,'documented_main_bays':3,'documented_arch_count':1,
                 'osm_building_way':study.way,'osm_pond_way':study.pond,'mapped_origin_m':plan.world(),
                 'mapped_yaw_rad':plan.yaw,'mapped_pond_rect_m':[pond_length,pond_width],'mapped_pond_area_m2':plan.pond.area,
                 'modelled_deck_z_m':DECK,'modelled_water_z_m':WATER,'modelled_caisson_edge_z_m':CAISSON_EDGE,
                 'removed_proxy_objects':removed[study.way],'trimmed_generic_pool_faces':old_water[study.pond],
                 'mesh_objects':sum(obj.type=='MESH' for obj in group.all_objects),
                 'native_polygons':sum(len(obj.data.polygons) for obj in group.all_objects if obj.type=='MESH')}
        report['pavilions'].append(metrics)
        print('GARDEN_PAVILION',study.name,metrics['mesh_objects'],metrics['native_polygons'],flush=True)
    report['context']=garden_context(site,plans,target,p)
    for hall in report['context']['halls']:
        hall['removed_proxy_objects']=removed[hall['osm_id']]
    for prefix,(_,title,i,eye,aim,lens,_) in VIEWS.items():
        obj=camera(f'{prefix} · {title}',plans[i].world(*eye),plans[i].world(*aim),lens)
        obj.data.clip_start=.035
        obj.data.clip_end=1600
    scene.camera=next(obj for obj in scene.objects if obj.type=='CAMERA' and obj.name.startswith('40 '))
    scene['latest_revision']='御花园 · 浮碧亭和澄瑞亭的独立桥券、庑作与八方藻井'
    scene['whole_city_every_detail_1to1_proven']=False
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(MASTER),compress=True)
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')


def verify(scene):
    report=json.loads(REPORT.read_text('utf-8'))
    graph=bpy.context.evaluated_depsgraph_get()
    site=Site()
    tests=[]

    def check(label,passed,evidence):
        tests.append(dict(check=label,passed=bool(passed),evidence=evidence))

    check('Metric units',scene.unit_settings.system=='METRIC' and scene.unit_settings.scale_length==1.,
          scene.unit_settings.scale_length)
    for name in ('浴德堂 · 穿过券道看穹顶','文华殿 · 海棠甬路至檐下'):
        walk=bpy.data.scenes.get(name)
        check(f'Prior native walkthrough retained: {name}',walk is not None and walk.camera.animation_data,
              walk.frame_end if walk else None)
    route=report.get('chengrui_walkthrough')
    if route:
        walk=bpy.data.scenes.get(GARDEN_WALK_SCENE)
        check('Saved Chengrui camera preserves the checked native path',
              walk is not None and walk.frame_end==route['checked_frames']==route['frames']
              and walk.camera.animation_data and walk.camera.data.animation_data,
              {'frames':walk.frame_end if walk else None,'distance_m':route['walk_distance_m']})
    for hall in report['context']['halls']:
        group=bpy.data.collections.get(hall['collection'])
        check(hall['name']+' north backdrop is a separate timber and roof assembly',
              group is not None and len(group.all_objects)>=5 and not any(name in scene.objects for name in hall['removed_proxy_objects']),
              {'mesh_objects':len(group.all_objects) if group else 0,'removed':hall['removed_proxy_objects']})
    for study,data in zip(STUDIES,report['pavilions']):
        plan=plan_from_map(site,study)
        group=bpy.data.collections[data['collection']]
        objects=[obj for obj in group.all_objects if obj.type=='MESH']
        trees=geometry_trees(objects,graph)

        def ray(a,b):
            p,q=Vector(plan.world(*a)),Vector(plan.world(*b))
            delta=q-p
            hit=first_hit(trees,p,delta.normalized(),delta.length)
            return (hit[0],round(hit[1].z,5)) if hit else None

        missing=[obj for obj in data['removed_proxy_objects'] if obj in scene.objects]
        check(study.name+' generic geometry superseded',not missing,missing)
        posts=[obj for obj in objects if obj.get('component')=='square_column' and '亭身' in obj.name]
        xvals=sorted({float(obj['post_x_local_m']) for obj in posts})
        check(study.name+' documented three bays between square posts',len(posts)==12 and len(xvals)==4
              and math.isclose(xvals[-1]-xvals[0],WIDTH),xvals)
        y0,y1=plan.bank_y
        yc=(y0+y1)/2
        gap=ray((-5.1,yc,-.28),(5.1,yc,-.28))
        crown=ray((0,yc,-.32),(0,yc,.75))
        check(study.name+' bridge void connects across both stone faces',not gap and crown and .25<crown[1]<.36,
              {'side_to_side_ray':gap,'crown_hit':crown})
        deck=ray((.11,plan.main_y-.52,2.3),(.11,plan.main_y-.52,-.9))
        pond=ray((10.3,yc,1.38),(10.3,yc,-1.08))
        site_water=scene.ray_cast(graph,Vector(plan.world(10.3,yc,1.38)),Vector((0,0,-1)),distance=2.7)
        check(study.name+' dry deck above recessed water',deck and abs(deck[1]-DECK)<.018
              and pond and abs(pond[1]-WATER)<.015 and site_water[0] and site_water[4].name==pond[0],
              {'floor':deck,'water':pond,'world_hit':site_water[4].name if site_water[0] else None})
        loft=ray((.062,plan.main_y+.063,2.91),(.062,plan.main_y+.063,5.80))
        rim=ray((1.63,plan.main_y,2.91),(1.63,plan.main_y,5.80))
        check(study.name+' octagonal well is vertically recessed above its surrounding ceiling',
              loft and rim and loft[1]-rim[1]>.29,{'medallion':loft,'ceiling':rim})
        passage=ray((.11,plan.front_y+.53,2.21),(.11,plan.main_y+4.4,2.21))
        check(study.name+' south porch and bridge centre are open at eye level',not passage,passage)
        tile_meshes=[obj for obj in objects if 'individually curved' in obj.name]
        colors=[[m.name for m in obj.data.materials] for obj in tile_meshes]
        check(study.name+' actual green tile meshes and separate yellow borders',len(colors)==2 and all(
            any('蓝绿色' in n for n in names) and any('琉璃筒瓦' in n for n in names) for names in colors),colors)
        check(study.name+' saved mesh count',len(objects)==data['mesh_objects'],len(objects))
    result={'file':MASTER.name,'passed':all(t['passed'] for t in tests),'tests':tests,
            'scope':'Checks native geometry, not accuracy against a site scan.'}
    VALIDATION.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    print('GARDEN_VERIFIED',result['passed'],len(tests),flush=True)
    if not result['passed']:
        raise RuntimeError([test for test in tests if not test['passed']])


def render(scene,args):
    configure_cycles(scene)
    scene.render.resolution_x=args.width
    scene.render.resolution_y=round(args.width*.684)
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGB'
    scene.render.use_persistent_data=True
    scene.cycles.samples=args.samples
    scene.cycles.use_denoising=True
    for prefix in args.views.split(','):
        stem,*_,exposure=VIEWS[prefix]
        scene.camera=next(obj for obj in scene.objects if obj.type=='CAMERA' and obj.name.startswith(prefix+' '))
        scene.view_settings.exposure=exposure
        scene.render.filepath=str(ROOT/'renders'/f'{stem}_{args.suffix}.png')
        print('GARDEN_RENDER',prefix,scene.cycles.device,flush=True)
        bpy.ops.render.render(write_still=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('build','verify','render','export'))
    parser.add_argument('--width',type=int,default=2304)
    parser.add_argument('--samples',type=int,default=80)
    parser.add_argument('--views',default=','.join(VIEWS))
    parser.add_argument('--suffix',default='garden')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if args.mode=='build':
        build()
        return
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    scene=bpy.context.scene
    if args.mode=='verify':
        verify(scene)
    elif args.mode=='render':
        render(scene,args)
    else:
        group=bpy.data.collections[GROUP]
        meshes=[obj for obj in group.all_objects if obj.type=='MESH' and obj.data.polygons]
        print(export_selected(ROOT/'exports'/'Imperial_Garden_Bridge_Pavilions.glb',meshes),flush=True)


if __name__=='__main__':
    main()
