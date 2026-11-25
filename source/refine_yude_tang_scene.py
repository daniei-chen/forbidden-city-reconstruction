"""Install Yude Tang in the full metric city, then verify and render the saved meshes."""

import argparse
import json
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

sys.path.insert(0,str(Path(__file__).resolve().parent))
from export_wenyuan_revision import export_selected
from mesh_tools import collection, polygons
from osm_site import Site
from outer_court_walkthrough import SCENE as WALK_SCENE, add_walkthrough, configure_cycles, first_hit
from paired_hall_plans import PAIRS, split_plan
from refine_immersive import camera, use_existing_palette
from yude_bath import (BATH_X, BATH_Y, DOOR_X, FIRE_EXCAVATION, FIRE_FLOOR, FIRE_X1,
                       FIRE_Y0, FIRE_Y1, HALL_FLOOR, HALL_REF, PASSAGE_POINTS, WELL_REF, build_yude, place)
from yude_tang_walkthrough import WALK_SCENE as YUDE_WALK_SCENE, keyframe_camera

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'The_Forbidden_City_Outer_Court_Revision.blend'
MASTER=ROOT/'The_Forbidden_City_Yude_Tang_Revision.blend'
REPORT=ROOT/'yude_tang_revision_report.json'
VALIDATION=ROOT/'validation_yude_tang_revision.json'
GROUND='场地与城内铺地 · 地面按水域开口'
VIEWS={
    '33':('33_yude_front_hall','浴德堂前殿',(-4.4,-14.4,1.68),(1.1,-.22,3.35),27,.08),
    '34':('34_yude_bath_oculus','浴德堂穹顶、天窗与券门',(BATH_X+.91,BATH_Y+1.77,2.64),
          (BATH_X+.32,BATH_Y-1.35,3.66),14.2,.16),
    '35':('35_yude_dogleg_vault','浴德堂曲尺券道',(4.51,3.70,2.52),(3.66,5.57,2.71),15.5,.30),
    '36':('36_yude_boiler_room','烧水灶间与铜锅',(5.35,FIRE_Y0+2.91,3.24),
          (3.47,FIRE_Y0+.89,2.44),20,.36),
    '37':('37_yude_complex','浴德堂浴室与井亭',(-25.75,30.50,24.70),(-4.55,8.95,3.92),39,-.10),
    '38':('38_yude_sunken_stairs','下沉灶间入口',(-2.24,FIRE_Y1+5.68,2.49),
          (1.68,FIRE_Y1-.72,1.20),25,.24),
    '39':('39_yude_well_pavilion','浴德堂井亭与引水石槽',(-7.10,17.02,5.46),
          (-13.44,11.25,3.45),22,.16),
}


def open_ground(obj, excavation):
    """Retain the saved site geometry and subtract the local opening from horizontal paving."""
    mesh=bmesh.new()
    mesh.from_mesh(obj.data)
    local=obj.matrix_world.inverted_safe()
    cut=Polygon([(local@Vector((x,y,0)))[:2] for x,y in excavation.exterior.coords])
    layers=list(mesh.faces.layers.int.values())
    affected=0
    for face in list(mesh.faces):
        z=face.verts[0].co.z
        if not -.02 < z < .105 or any(abs(v.co.z-z)>.0001 for v in face.verts):
            continue
        shape=Polygon([(v.co.x,v.co.y) for v in face.verts])
        if not shape.is_valid or not shape.intersects(cut) or shape.intersection(cut).area<1e-8:
            continue
        material=face.material_index
        up=face.normal.z>0
        attributes=[face[layer] for layer in layers]
        mesh.faces.remove(face)
        for part in polygons(shape.difference(cut)):
            for triangle in constrained_delaunay_triangles(part).geoms:
                if triangle.area < 1e-9:
                    continue
                points=list(orient(triangle,1 if up else -1).exterior.coords)[:-1]
                new=mesh.faces.new([mesh.verts.new((x,y,z)) for x,y in points])
                new.material_index=material
                for layer,value in zip(layers,attributes):
                    new[layer]=value
        affected+=1
    mesh.normal_update()
    mesh.to_mesh(obj.data)
    mesh.free()
    obj.data.update()
    return affected


def area_light(target,name,placement,eye,aim,power,size,tone):
    data=bpy.data.lights.new(name,'AREA')
    data.energy=power
    data.shape='DISK'
    data.size=size
    data.color=tone
    data.specular_factor=.25
    obj=bpy.data.objects.new(name,data)
    target.objects.link(obj)
    obj.location=placement.world(*eye)
    obj.rotation_euler=(Vector(placement.world(*aim))-obj.location).to_track_quat('-Z','Y').to_euler()


def build():
    bpy.ops.wm.open_mainfile(filepath=str(BASE))
    scene=bpy.context.scene
    root=bpy.data.collections['紫禁城 · EDITABLE 3D MASTER']
    site=Site()
    previous_walk=bpy.data.scenes.get(WALK_SCENE)
    if previous_walk:
        old_camera=previous_walk.camera
        bpy.data.scenes.remove(previous_walk)
        if old_camera and not old_camera.users_collection:
            bpy.data.objects.remove(old_camera,do_unlink=True)
    removed=[]
    for obj in list(scene.objects):
        if any(str(obj.get(key,'')) in {HALL_REF,WELL_REF} for key in ('osm_id','source_osm_id')):
            removed.append(obj.name)
            bpy.data.objects.remove(obj,do_unlink=True)
    if len(removed)!=4:
        raise RuntimeError(f'Expected two generic roof shells and their tile carriers, found {removed}')
    group,placement,data=build_yude(site,root,use_existing_palette())
    data['removed_superseded_objects']=removed
    bpy.context.view_layer.update()
    excavation=Polygon([placement.world(x,y)[:2] for x,y in FIRE_EXCAVATION.exterior.coords])
    data['paving_faces_trimmed']={obj.name:open_ground(obj,excavation) for obj in scene.objects
                                  if obj.type=='MESH' and obj.name.startswith((GROUND,'石板路 ·'))}
    if not data['paving_faces_trimmed'].get(GROUND):
        raise RuntimeError('No site ground was cut at the sunken stair')
    for prefix,(_,name,eye,aim,lens,_) in VIEWS.items():
        obj=camera(f'{prefix} · {name}',placement.world(*eye),placement.world(*aim),lens)
        obj.data.clip_start=.032
    # Small photographic fill sources live in a clearly named collection.
    # They reveal preserved brick fabric without adding physical fixtures.
    lights=collection('浴德堂 · 渲染检视补光',group)
    area_light(lights,'浴德堂 · 券口反射补光',placement,(4.22,8.04,2.85),(2.72,10.6,3.53),
               31,.56,(1.,.94,.82))
    area_light(lights,'浴德堂 · 圆窗漫射补光',placement,(BATH_X,BATH_Y,5.36),(BATH_X-.7,BATH_Y+.4,2.61),
               83,.39,(.94,.97,1.))
    area_light(lights,'浴德堂 · 券道窗下反射补光',placement,(3.56,4.96,3.23),(4.03,3.86,2.21),
               26,.42,(1.,.96,.84))
    area_light(lights,'浴德堂 · 券道入口反射补光',placement,(4.65,2.87,2.76),(3.64,4.48,2.43),
               22,.39,(1.,.96,.87))
    area_light(lights,'浴德堂 · 灶间门口反射补光',placement,(5.41,FIRE_Y0+3.02,2.86),
               (3.52,FIRE_Y0+.68,2.18),54,.66,(1.,.95,.87))
    bpy.context.view_layer.update()
    pair=PAIRS[0]
    plan=split_plan(site.geom(pair.ref))
    prior=json.loads((ROOT/'outer_court_revision_report.json').read_text('utf-8'))
    wenhua=bpy.data.collections[prior['pairs'][0]['collection']]
    route=add_walkthrough(scene,wenhua,plan,pair)
    yude_route=keyframe_camera(scene,group,placement)
    print('YUDE_WALK_ROUTE',yude_route,flush=True)
    scene.camera=next(obj for obj in scene.objects if obj.name.startswith('37 ') and obj.type=='CAMERA')
    scene['latest_revision']='浴德堂前殿、白釉砖穹顶、曲尺券道、铜锅、下沉灶间与井亭'
    scene['whole_city_every_detail_1to1_proven']=False
    data['meshes']=sum(obj.type=='MESH' for obj in group.all_objects)
    data['native_polygons']=sum(len(obj.data.polygons) for obj in group.all_objects if obj.type=='MESH')
    data['render_lighting']='Adjustable inspection fill in scenes. Not fixtures in the surveyed building.'
    report={'source_blend':BASE.name,'native_blend':MASTER.name,'yude_tang':data,'wenhua_walkthrough':route,
            'yude_walkthrough':yude_route}
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(MASTER),compress=True)
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print('YUDE_MASTER_SAVED',MASTER.name,data['meshes'],data['native_polygons'],route['frames_checked'],flush=True)


def geometry_trees(objects,graph):
    trees=[]
    for obj in objects:
        if obj.type=='MESH' and obj.data.polygons:
            matrix=obj.matrix_world.copy()
            inverse=matrix.inverted_safe()
            trees.append((obj.name,BVHTree.FromObject(obj,graph),matrix,inverse,inverse.to_3x3()))
    return trees


def verify(scene):
    report=json.loads(REPORT.read_text('utf-8'))
    data=report['yude_tang']
    group=bpy.data.collections[data['collection']]
    graph=bpy.context.evaluated_depsgraph_get()
    placement=place(Site(),HALL_REF)
    trees=geometry_trees(group.all_objects,graph)
    tests=[]

    def check(name,passed,value):
        tests.append({'check':name,'passed':bool(passed),'evidence':value})

    def ray(a,b):
        p,q=Vector(placement.world(*a)),Vector(placement.world(*b))
        direction=q-p
        hit=first_hit(trees,p,direction.normalized(),direction.length)
        return (hit[0], (hit[1]-p).length) if hit else None

    check('Metric scene',scene.unit_settings.system=='METRIC' and scene.unit_settings.scale_length==1.0,
          scene.unit_settings.scale_length)
    missing=[name for name in data['removed_superseded_objects'] if name in scene.objects]
    check('Superseded mapped roof meshes removed',not missing,missing)
    floor=ray((BATH_X,BATH_Y,2.3),(BATH_X,BATH_Y,.3))
    check('Bath floor at modelled section level',floor and abs(floor[1]-(2.3-HALL_FLOOR))<.025,floor)
    walls=[ray((BATH_X,BATH_Y,2.34),(BATH_X+dx,BATH_Y+dy,2.34))
           for dx,dy in ((3.,0.),(-3.,0.),(0.,3.),(0.,-3.))]
    check('Four clear bath walls approximately two metres from centre',
          all(hit and 1.98<hit[1]<2.02 for hit in walls),walls)
    bends=[(x,y,HALL_FLOOR+1.12) for x,y in PASSAGE_POINTS[1:-1]]
    segments=[(PASSAGE_POINTS[0][0],2.91,HALL_FLOOR+1.12),*bends,
              (DOOR_X,BATH_Y-.79,HALL_FLOOR+1.12)]
    overlaps=[hit for a,b in zip(segments,segments[1:]) if (hit:=ray(a,b))]
    check('Curve through both arches has no intersecting wall',not overlaps,overlaps)
    low=FIRE_Y1+.57
    world=Vector(placement.world(.28,low,1.20))
    found=scene.ray_cast(graph,world,Vector((0,0,-1)),distance=2.3)
    actual_z=found[1].z if found[0] else None
    check('Sunken stair is open through saved city paving',found[0] and actual_z<-.15,
          {'z':actual_z,'surface':found[4].name if found[0] else None})
    fire_y=FIRE_Y0+1.05
    feed=ray((FIRE_X1-.42,fire_y,FIRE_FLOOR+.20),(FIRE_X1+.58,fire_y,FIRE_FLOOR+.20))
    jamb=ray((FIRE_X1-.42,fire_y+.29,FIRE_FLOOR+.20),(FIRE_X1+.42,fire_y+.29,FIRE_FLOOR+.20))
    check('Firebox feed is empty across the masonry surround',not feed and jamb,{'opening':feed,'jamb':jamb})
    cap=ray((BATH_X,BATH_Y,4.40),(BATH_X,BATH_Y,7.))
    adjacent=ray((BATH_X+.39,BATH_Y,4.40),(BATH_X+.39,BATH_Y,7.))
    check('Oculus has depth before glass, with masonry at the side',cap and adjacent and cap[1]>adjacent[1]+.3,
          {'centre':cap,'side':adjacent})
    walk=bpy.data.scenes.get(WALK_SCENE)
    check('Saved walkthrough camera animation',walk and walk.frame_end==240 and walk.camera.animation_data and
          walk.get('camera_path_revision')==report['wenhua_walkthrough']['camera_path_revision'],
          report['wenhua_walkthrough']['camera_path_revision'])
    yude_walk=bpy.data.scenes.get(YUDE_WALK_SCENE)
    yude_route=report['yude_walkthrough']
    check('Saved Yude bath walkthrough uses the validated path',
          yude_walk and yude_walk.frame_end==yude_route['frames']==yude_route['floor_and_clearance_checks']
          and yude_walk.camera.animation_data and yude_walk.camera.data.animation_data,yude_route)
    result={'file':MASTER.name,'passed':all(t['passed'] for t in tests),'tests':tests,
            'scope':'Scene geometry and apertures. Field scan accuracy and current condition are not asserted.'}
    VALIDATION.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    print('YUDE_VERIFIED',result['passed'],len(tests),flush=True)
    if not result['passed']:
        raise RuntimeError([t for t in tests if not t['passed']])


def render(scene,args):
    configure_cycles(scene)
    scene.render.resolution_x=args.width
    scene.render.resolution_y=round(args.width*.68)
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGB'
    scene.cycles.samples=args.samples
    scene.cycles.use_denoising=True
    for prefix in args.views.split(','):
        stem,*_,exposure=VIEWS[prefix]
        scene.camera=next(obj for obj in scene.objects if obj.type=='CAMERA' and obj.name.startswith(prefix+' '))
        scene.render.filepath=str(ROOT/'renders'/f'{stem}_{args.suffix}.png')
        scene.view_settings.exposure=exposure
        print('YUDE_CAMERA',prefix,flush=True)
        bpy.ops.render.render(write_still=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('build','verify','render','export'))
    parser.add_argument('--width',type=int,default=2000)
    parser.add_argument('--samples',type=int,default=64)
    parser.add_argument('--views',default=','.join(VIEWS))
    parser.add_argument('--suffix',default='yude')
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
        report=json.loads(REPORT.read_text('utf-8'))
        group=bpy.data.collections[report['yude_tang']['collection']]
        meshes=[obj for obj in group.all_objects if obj.type=='MESH' and obj.data.polygons]
        print(export_selected(ROOT/'exports'/'Yude_Tang_Architectural_Mesh.glb',meshes),flush=True)


if __name__=='__main__':
    main()
