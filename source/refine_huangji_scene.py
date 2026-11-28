"""Build, reopen and render the Huangji Hall and Ningshou Palace revision."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import struct
import time

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from huangji_interiors import CAISSON_Y, DAIS_FRONT, SOFFIT, build_interiors
from huangji_furnishings import CATALOGUE as ELEPHANT_SOURCE, ENVELOPE as ELEPHANT_ENVELOPE, POSITIONS as ELEPHANT_POSITIONS
from mesh_tools import collection
from ning_shou_halls import (CROSS_GATES, DECK, FLANKS, MAIN_ID, MAIN_SOURCE, MAIN_X, MAIN_Y, MAP_PATHS,
                            LANDING_Y, PLAN_SOURCE, REAR_ID, REAR_SOURCE, REAR_X, REAR_Y, ROAD_NORTH, ROAD_SOUTH, ROAD_Z, STAIR_X,
                            SECTION_SOURCE, STUDY, Envelope, build_shell)
from north_garden_walkthrough import bounds, visible
from osm_site import Site
from outer_court_walkthrough import configure_cycles, first_hit, route_geometry, smoothstep
from qinan_survey import Location
from refine_immersive import camera, use_existing_palette
from refine_ning_shou_scene import GROUP as SOUTH_GROUP, INNER_TOUR, TOUR as SOUTH_TOUR, sample_path
from refine_yude_tang_scene import area_light, geometry_trees


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'The_Forbidden_City_Ning_Shou_Detail.blend'
MASTER = ROOT / 'The_Forbidden_City_Huangji_and_Ningshou.blend'
REPORT = ROOT / 'huangji_ningshou_revision_report.json'
VALIDATION = ROOT / 'validation_huangji_ningshou_revision.json'
GROUP = '宁寿宫前朝 · 皇极殿、宁寿宫后殿和东西庑'
TOUR = '皇极殿 · 沿高台甬路至殿内御座'
FRAME_DIR = 'huangji_axial_walk_frames'
FPS, FRAMES, EYE = 24, 1080, 1.65
REPLACED_IDS = {MAIN_ID, REAR_ID, *FLANKS, *CROSS_GATES}
PROXY_COUNT = 2*len(REPLACED_IDS)+1
VIEWS = {
    '71': ('huangji_axial_approach','皇极殿 · 宁寿门望向九间重檐','main',(0.,-56.58,2.69),(0.,-9.,8.29),26.),
    '72': ('huangji_terrace_threequarter','皇极殿 · 青白石月台和正吻','main',(-25.6,-31.6,1.68),(.9,-2.,8.71),26.),
    '73': ('huangji_throne_stairs','皇极殿 · 七级御阶与仁德大隆','main',(0.04,-5.23,3.78),(0.,4.28,5.08),27.),
    '74': ('huangji_throne_detail','皇极殿 · 金漆宝座与围屏','main',(1.01,-.542,4.45),(-.03,4.21,5.24),30.),
    '75': ('huangji_octagonal_caisson','皇极殿 · 仰视八角盘龙藻井','main',(.10,1.80,3.76),(0.,CAISSON_Y,SOFFIT+.30),21.),
    '76': ('ningshou_glazed_parapet','宁寿宫后殿 · 檐廊和琉璃透风栏','rear',(23.3,-17.07,2.65),(4.35,-2.34,5.00),21.),
    '77': ('huangji_chiwen_and_tile','皇极殿 · 正吻、飞椽和上下垂脊','main',(-21.7,-29.2,12.4),(-11.4,-1.4,14.45),41.),
    '78': ('ningshou_shared_platform_overview','宁寿宫前朝 · 王字形台基和东西庑','main',(90.,-111.,88.),(0.,-8.,2.2),39.),
    '79': ('huangji_under_eaves','皇极殿 · 金龙雀替和槛窗','main',(-14.3,-12.45,3.75),(2.4,-7.08,5.47),30.),
    '80': ('ningshou_rear_interior_layout','宁寿宫后殿 · 西间木榻和祭祀空间','rear',(-10.72,-2.78,3.76),(-17.16,4.85,3.69),25.),
    '81': ('huangji_enamel_elephant','皇极殿 · 月白珐琅太平有象与御座','main',(8.19,-5.08,3.39),(5.52,-.94,2.97),39.),
    '82': ('huangji_dais_carved_fascia','皇极殿 · 地平束腰雕龙与三路朱栏','main',(6.79,-1.33,3.51),(2.35,4.40,2.93),31.),
}


def dump(path, value):
    pending=path.with_suffix('.pending.json')
    pending.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf-8')
    pending.replace(path)


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def png_size(path):
    with path.open('rb') as stream:
        header=stream.read(24)
    if len(header)!=24 or header[:8]!=b'\x89PNG\r\n\x1a\n' or header[12:16]!=b'IHDR':
        raise RuntimeError(f'Invalid PNG frame: {path}')
    return struct.unpack('>II',header[16:24])


def remove_proxies(scene):
    removed=[]
    for o in list(scene.objects):
        ref=str(o.get('source_osm_id',o.get('osm_id','')))
        if ref in REPLACED_IDS or o.name.startswith('宁寿门后 · 连至皇极殿前的高台甬路'):
            removed.append(o.name)
            data=o.data if o.type=='MESH' else None
            bpy.data.objects.remove(o,do_unlink=True)
            if data and not data.users:
                bpy.data.meshes.remove(data)
    if len(removed)!=PROXY_COUNT:
        raise RuntimeError(f'Expected {PROXY_COUNT} footprint, tile or elevated way proxies. Found {removed}')
    obj=bpy.data.objects['石板路 · mapped circulation']
    bm=bmesh.new()
    try:
        bm.from_mesh(obj.data)
        low=bm.faces.layers.int['osm_id_low']; high=bm.faces.layers.int.get('osm_id_high')
        faces=[f for f in bm.faces if f[low] in MAP_PATHS and (high is None or f[high]==0)]
        count=len(faces)
        if count==0:
            raise RuntimeError('Expected to replace old geometry of the inner paved courts.')
        bmesh.ops.delete(bm,geom=faces,context='FACES')
        bm.to_mesh(obj.data); obj.data.update()
    finally:
        bm.free()
    return removed,count


def setup_context(base,main,group):
    scene=bpy.data.scenes.new(TOUR)
    scene.world=bpy.data.worlds.get('宁寿宫 · 天空漫反射') or base.world
    scene.unit_settings.system='METRIC'
    scene.unit_settings.scale_length=1.
    scene.view_settings.view_transform=base.view_settings.view_transform
    scene.view_settings.look='AgX - Medium High Contrast'
    scene.view_settings.exposure=base.view_settings.exposure + .09
    scene.render.engine='CYCLES'
    scene.render.fps=FPS
    scene.render.resolution_x=1280; scene.render.resolution_y=720
    scene.render.resolution_percentage=100
    loc=main.loc
    for obj in base.objects:
        if not visible(obj):
            continue
        if obj.type=='MESH':
            lo,hi=bounds(obj)
            dx=max(lo[0]-loc.x,loc.x-hi[0],0.); dy=max(lo[1]-loc.y,loc.y-hi[1],0.)
            if dx*dx+dy*dy>126**2:
                continue
        elif (obj.type!='LIGHT' or obj.data.type!='SUN'):
            continue
        scene.collection.objects.link(obj)
    light=collection('两殿检视 · 可关闭的天光反照',group)
    area_light(light,'皇极殿 · 明间铺地返照',loc,(.02,-5.56,4.79),(.18,3.51,5.28),610.,4.71,(1.,.909,.794))
    area_light(light,'皇极殿 · 井口与北窗反照',loc,(2.10,6.67,4.46),(0.,CAISSON_Y,8.94),410.,3.93,(.80,.88,1.))
    area_light(light,'皇极殿 · 东侧窗格天光反照',loc,(8.76,-4.91,4.82),(3.06,2.90,3.19),520.,5.31,(.83,.91,1.))
    area_light(light,'皇极殿 · 西侧窗格天光反照',loc,(-8.76,-4.91,4.82),(-3.06,2.90,3.19),520.,5.31,(.83,.91,1.))
    for obj in light.objects:
        scene.collection.objects.link(obj)
    return scene


def path_and_poses(base,loc):
    plan=sample_path(((.48,-57.66),(.22,-54.89),(.10,-44.2),(-.14,-33.1),(1.01,-28.93),
                      (STAIR_X,-26.68),(STAIR_X,LANDING_Y+.12),(.53,-21.0),(.05,-13.14),
                      (.16,-8.64),(.04,-6.42),(0.,-4.38),(-.035,DAIS_FRONT-.93)))
    route=lambda t: plan.interpolate(min(plan.length,max(0.,t)))
    at=lambda d,h: Vector(loc.world(route(d).x,route(d).y,h))
    graph=bpy.context.evaluated_depsgraph_get()
    trees=route_geometry(base,graph,at(0,0),at(plan.length,0),2.6,4.45)
    floor_objects=[r for r in trees if r[0].startswith(('两殿 ·','皇极殿 · 逐块','宁寿门 · 石座'))]
    down=Vector((0,0,-1))
    def support(distance):
        hit=first_hit(floor_objects,at(distance,DECK+.31),down,DECK-.63)
        if not hit or not .95<=hit[1].z<=DECK+.021:
            raise RuntimeError(f'No supported walking level at path distance {distance:.4f}: {hit}')
        return hit[1].z
    directions=[Vector((math.cos(i*math.pi/4),math.sin(i*math.pi/4),0)) for i in range(8)]
    result,levels=[],[]
    previous=None
    for frame in range(1,FRAMES+1):
        t=(frame-1)/(FRAMES-1)
        d=plan.length*(.89*t+.11*smoothstep(t))
        level=support(d); levels.append(level)
        smoothed=sum(support(d+.071*j) for j in range(-4,5))/9
        z=smoothed+EYE+.013*math.sin(d*math.tau/.838)
        point=at(d,z)
        for dz in (0.,-.28,-.67,-.98):
            for direction in directions:
                hit=first_hit(trees,point+Vector((0,0,dz)),direction,.205)
                if hit:
                    raise RuntimeError(f'Tour overlaps {hit[0]} at {frame}, local y={route(d).y:.3f}')
        if (hit:=first_hit(trees,point,Vector((0,0,1)),.23)):
            raise RuntimeError(f'Tour has insufficient overhead clearance at {frame}: {hit[0]}')
        if previous is not None:
            diff=point-previous
            if (hit:=first_hit(trees,previous,diff.normalized(),diff.length)):
                raise RuntimeError(f'Tour crosses {hit[0]} between frames {frame-1} and {frame}')
        transition=smoothstep((d-36.5)/12.7)
        fade=smoothstep((d-25.4)/12.4)
        a=Vector(loc.world(.26,-5.71,8.05-1.58*fade))
        b=Vector(loc.world(.02,5.03,5.19))
        q=(a.lerp(b,transition)-point).to_track_quat('-Z','Y')
        if result and q.dot(result[-1][1])<0:
            q.negate()
        lens=25.9-3.9*smoothstep((d-27.6)/13.)+3.0*smoothstep((d-44.4)/8.4)
        result.append((point,q,lens))
        previous=point
    return result, {'scene':TOUR,'frames_checked':FRAMES,'fps':FPS,'frames_directory':FRAME_DIR,
                    'path_m':round(plan.length,4),'eye_height_m':EYE,'support_z_range_m':[min(levels),max(levels)],
                    'duration_seconds':FRAMES/FPS,'average_speed_m_per_s':round(plan.length/(FRAMES/FPS),4),
                    'checked_overhead_clearance_m':.23,
                    'bvh_objects':len(trees),'checked_radial_clearance_m':.205,
                    'origin_xy_m':[loc.x,loc.y],'origin_yaw_rad':loc.yaw}


def create_tour(scene,result):
    cam=bpy.data.objects.new(TOUR,bpy.data.cameras.new(TOUR))
    scene.collection.objects.link(cam); scene.camera=cam
    cam.rotation_mode='QUATERNION'
    cam.data.clip_start,cam.data.clip_end=.042,2200.
    for i,(pos,q,lens) in enumerate(result,1):
        cam.location,cam.rotation_quaternion,cam.data.lens=pos,q,lens
        cam.keyframe_insert('location',frame=i)
        cam.keyframe_insert('rotation_quaternion',frame=i)
        cam.data.keyframe_insert('lens',frame=i)
    scene.frame_start,scene.frame_end=1,FRAMES
    scene.render.filepath=f'//renders/{FRAME_DIR}/'
    scene.frame_set(1)


def update_previous_tours(group):
    for name in (SOUTH_TOUR,INNER_TOUR):
        scene=bpy.data.scenes.get(name)
        if not scene:
            continue
        for obj in group.all_objects:
            if obj.type=='MESH' and obj.name not in scene.objects:
                scene.collection.objects.link(obj)


def build():
    bpy.ops.wm.open_mainfile(filepath=str(BASE))
    scene=bpy.context.scene
    prior_scenes=sorted(bpy.data.scenes.keys())
    site=Site(); removed,faces=remove_proxies(scene)
    group=collection(GROUP,bpy.data.collections['紫禁城 · EDITABLE 3D MASTER'])
    main,rear,halls,p,metrics=build_shell(site,group,use_existing_palette())
    build_interiors(main,rear,halls,p)
    print('HUANGJI GEOMETRY READY',len(group.all_objects),flush=True)
    bpy.context.view_layer.update()
    keys,tour=path_and_poses(scene,main.loc)
    render_scene=setup_context(scene,main,group)
    # Mild rear-window bounce is present only in the local lighting collection.
    light=bpy.data.collections['两殿检视 · 可关闭的天光反照']
    area_light(light,'宁寿宫 · 直棂窗返照',rear.loc,(-14.,-3.48,4.15),(-15.78,3.81,3.95),560.,4.3,(.92,.89,.82))
    render_scene.collection.objects.link(bpy.data.objects['宁寿宫 · 直棂窗返照'])
    create_tour(render_scene,keys)
    update_previous_tours(group)
    cams=collection('两殿 · 实景对位与人眼相机',group)
    for index,(_,title,loc_key,eye,look,lens) in VIEWS.items():
        loc=main.loc if loc_key=='main' else rear.loc
        obj=camera(f'{index} · {title}',loc.world(*eye),loc.world(*look),lens)
        obj.data.clip_start,obj.data.clip_end=.043,2600.
        scene.collection.objects.unlink(obj); cams.objects.link(obj)
        if index=='72': scene.camera=obj
    scene.render.engine='CYCLES'
    scene.render.resolution_x=3840; scene.render.resolution_y=2160; scene.render.resolution_percentage=100
    scene.render.filepath='//renders/72_huangji_terrace_threequarter_huangji.png'
    scene['latest_revision']=GROUP
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_perspective='CAMERA'
    objs=[o for o in group.all_objects if o.type=='MESH']
    result={'native_blend':MASTER.name,'previous_master':BASE.name,'collection':GROUP,'preserved_scenes':prior_scenes,
            'blender_version':bpy.app.version_string,
            'build_sources_sha256':{name:digest(ROOT/'source'/name) for name in
                                    ('refine_huangji_scene.py','ning_shou_halls.py','huangji_interiors.py',
                                     'huangji_furnishings.py','huangji_caisson.py','paired_halls.py','prepare_huangji_details.py')},
            'detail_source_manifest_sha256':digest(ROOT/'source/references/ning_shou_court/huangji_detail_sources.json'),
            'sources':{'official_hall':MAIN_SOURCE,'official_rear':REAR_SOURCE,'study':STUDY,'published_plan':PLAN_SOURCE,
                       'published_section_and_ornaments':SECTION_SOURCE,'surface_registration':'source/references/ning_shou_court/huangji_surface_sources.json'},
            'documented_scale':{'ridge_top_m':19.0,'chiwen_height_m':2.60,'published_chiwen_segments':11,
                                'published_roof_guardians':9,'terrace_and_route':metrics},
            'map_footprint_reference':{'main_way':MAIN_ID,'main_m':[main.width,main.depth],
                                       'rear_way':REAR_ID,'rear_m':[rear.width,rear.depth]},
            'inferred_dimensions':{'main_column_x_m':MAIN_X,'main_column_y_m':MAIN_Y,'rear_column_x_m':REAR_X,
                                   'rear_column_y_m':REAR_Y,'dais_and_carving':'Visible floor plan and image proportions; no survey.'},
            'source_conflicts':{'four_gilt_posts_vs_six':'Adopted four per building page. Zhang and Li discuss six; photographs do not establish all obscured positions.',
                                'rear_seven_vs_nine_bays':'Adopted seven main bays per building page. Early article calls it nine, potentially counting differently.',
                                'front_three_vs_five_doors':'Museum page identifies principal three as doors. The archived article counts five. The model takes the current building page for operable bays.'},
            'display_state':'Restored exterior, photo-led Huangji ceremonial interior and separately identified historical room setup for the rear hall.',
            'enamel_elephant_pair':{'catalogue':ELEPHANT_SOURCE,'catalogue_xyz_envelope_m':ELEPHANT_ENVELOPE,
                                   'local_positions_m':ELEPHANT_POSITIONS,'catalogue_identity_confirmed':False,
                                   'scope':'Documented dimensions of a corresponding museum type; carving and photographed placements inferred.'},
            'old_objects_replaced': removed,'local_flat_paving_faces_replaced':faces,
            'editable_meshes':len(objs),'native_polygons':sum(len(o.data.polygons) for o in objs),'huangji_walkthrough':tour}
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(MASTER),compress=True)
    dump(REPORT,result)
    print('HUANGJI_BUILT',len(objs),result['native_polygons'],tour['path_m'],flush=True)


def verify(scene):
    data=json.loads(REPORT.read_text('utf-8'))
    site=Site(); main,rear=(Envelope.from_way(site,ref) for ref in (MAIN_ID,REAR_ID))
    loc=main.loc; group=bpy.data.collections[GROUP]; graph=bpy.context.evaluated_depsgraph_get()
    checks=[]
    def test(label,ok,evidence):
        checks.append({'check':label,'passed':bool(ok),'evidence':evidence})
    source_changes=[name for name,value in data['build_sources_sha256'].items() if digest(ROOT/'source'/name)!=value]
    test('reconstruction source inputs match the saved build report',not source_changes,
         {'changed_sources':source_changes,'blender_version':data['blender_version']})
    test('native scene is metric and previous tour scenes preserved',scene.unit_settings.system=='METRIC'
         and scene.unit_settings.scale_length==1. and set(data['preserved_scenes'])<set(bpy.data.scenes.keys()), sorted(bpy.data.scenes.keys()))
    test('old footprints and tile carriers removed',len(data['old_objects_replaced'])==PROXY_COUNT and
         not set(data['old_objects_replaced'])&set(bpy.data.objects.keys()),data['old_objects_replaced'])
    road=next(o for o in group.all_objects if o.get('role')=='measured_axial_walkway')
    lo=[min(v.co[i] for v in road.data.vertices) for i in range(3)]
    hi=[max(v.co[i] for v in road.data.vertices) for i in range(3)]
    road_size=[hi[1]-lo[1],hi[0]-lo[0],hi[2]]
    test('reopened stone walkway matches the 30 × 6 × 1.60 m published dimensions',
         max(abs(a-b) for a,b in zip(road_size,(30.,6.,ROAD_Z)))<.012,road_size)
    treads=next(o for o in group.all_objects if o.get('role')=='forecourt_stairs')
    tree=geometry_trees([treads],graph)
    levels=[]
    for side in (-1,1):
        row=[]
        for j in range(3):
            y=ROAD_NORTH+(j+.5)*(LANDING_Y-ROAD_NORTH)/3
            hit=first_hit(tree,Vector(loc.world(side*STAIR_X,y,DECK+.20)),Vector((0,0,-1)),DECK-ROAD_Z+.25)
            row.append(round(hit[1].z,5) if hit else None)
        levels.append(row)
    test('both three-tread stone routes beside the modeled danbi rise to the terrace',
         all(all(z is not None for z in row) and row[0]>ROAD_Z and row[0]<row[1]<row[2] and abs(row[2]-DECK)<.007
             for row in levels),levels)
    upper=bpy.data.collections['皇极殿 · 上檐庑殿四坡']
    native_ridge=next(o for o in upper.objects if 'sculpted ridge' in o.name)
    ridge=max(v.co.z for v in native_ridge.data.vertices)
    terminals=[c for c in upper.children if '正吻十一拼' in c.name]
    details=[]
    for c in terminals:
        zz=[v.co.z for o in c.objects for v in o.data.vertices]
        details.append([len(c.objects),max(zz)-min(zz)])
    test('upper roof main ridge and both eleven-part chiwen',abs(ridge-19.)<.021 and len(details)==2
         and all(n==11 and abs(h-2.60)<.0002 for n,h in details), {'ridge_z_m':ridge,'terminations':details})
    guards=[len(c.objects)-1 for c in upper.children if c.get('guardians_excluding_rider') is not None]
    test('nine individual upper roof guardians at each corner',sorted(guards)==[9]*4,guards)
    frame_rows=[]
    for prefix,desired in (('皇极殿',(9,5)),('宁寿宫',(7,3))):
        obj=bpy.data.objects[prefix+' · 檐柱、内柱与石柱础']
        n=(len(obj['width_axis_coordinates_m'])-1,len(obj['depth_axis_coordinates_m'])-1)
        frame_rows.append(list(n)); test(prefix+' bay structure',n==desired,n)
    test('independent native furniture and caisson meshes',
         sum(o.get('role')=='huangji_gilt_column' for o in group.all_objects)==4 and
         sum(o.get('role')=='huangji_screen_leaf' for o in group.all_objects)==7 and
         sum(o.get('role')=='huangji_dais_stair' for o in group.all_objects)==3 and
         all(any(o.get('role')==v for o in group.all_objects) for v in ('huangji_throne','water_clock','striking_clock','historical_rear_rooms')),
         {'gilt_posts':4,'screen_leaves':7,'stairs':3,'clock_models':2})
    door=bpy.data.collections['皇极殿 · 可编辑槅扇、槛墙及亮子']
    door_tree=geometry_trees(list(door.all_objects),graph)
    direction=Vector((-math.sin(loc.yaw),math.cos(loc.yaw),0))
    checks_open=[first_hit(door_tree,Vector(loc.world(x,-8.4,z)),direction,2.78) is None
                 for x,z in ((0.,3.22),(.36,3.3),(-.36,3.31),(0.,4.12))]
    test('central hall portal has a genuine walkable opening',all(checks_open),checks_open)
    ceiling_obj=bpy.data.objects['皇极殿 · 八角抹角藻井、盘龙与垂珠']
    top=geometry_trees([ceiling_obj],graph)
    h=first_hit(top,Vector(loc.world(.87,CAISSON_Y+.19,SOFFIT-.47)),Vector((0,0,1)),2.3)
    test('the caisson opens beyond the ceiling plane',h and h[1].z>SOFFIT+.32,round(h[1].z,5) if h else None)
    local_images={'huangji_eave_face.jpg','ning_shou_eave_face.jpg','renshou_inscription.jpg','huangji_screen_band.jpg'}
    test('rectified museum surfaces are packed',local_images<={im.name for im in bpy.data.images if im.packed_file},sorted(local_images))
    detail_images={f'huangji_screen_crest_{i}.jpg' for i in range(1,5)}|{
        f'huangji_ceiling_roundel_{i}.jpg' for i in range(1,5)}|{
        'huangji_gilt_column_detail.jpg','huangji_dais_upper_fascia.jpg','huangji_dais_lower_fascia.jpg'}
    detail_images|={'huangji_caisson_atlas.jpg','huangji_caisson_dragon_disk.jpg'}
    packed={im.name for im in bpy.data.images if im.packed_file}
    test('photographed crown, ceiling, column and dais fields are self contained',detail_images<=packed,
         {'required':sorted(detail_images),'missing':sorted(detail_images-packed)})
    sizes=[]
    for index in (1,2):
        pieces=[o for o in group.all_objects if o.get('role')=='huangji_enamel_elephant' and o.get('pair_index')==index]
        points=[v.co for obj in pieces for v in obj.data.vertices]
        size=[max(v[a] for v in points)-min(v[a] for v in points) for a in range(3)] if points else []
        sizes.append({'pair_index':index,'editable_parts':len(pieces),'size_xyz_m':size})
    test('both enamel elephant assemblies reproduce the selected catalogue envelope',
         all(row['editable_parts']==4 and len(row['size_xyz_m'])==3 and
             max(abs(a-b) for a,b in zip(row['size_xyz_m'],ELEPHANT_ENVELOPE))<.0001 for row in sizes),sizes)
    carving=[o for o in group.all_objects if o.get('role')=='huangji_dais_fascia']
    test('the photographed dais bands have native relief geometry',len(carving)==1 and
         len(carving[0].data.polygons)>40000,{'meshes':len(carving),'polygons':sum(len(o.data.polygons) for o in carving)})
    tour=bpy.data.scenes[TOUR]; cam=tour.camera
    active=bpy.context.window.scene; bpy.context.window.scene=tour
    try:
        inv=mathutils_inverse(loc)
        samples=[]
        for f in (1,180,360,600,FRAMES):
            tour.frame_set(f)
            xyz=inv(cam.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.translation)
            samples.append([round(x,4) for x in xyz])
    finally:
        tour.frame_set(1); bpy.context.window.scene=active
    test('saved camera walks from the stair to the interior',tour.frame_end==FRAMES and samples[0][1]<ROAD_SOUTH
         and samples[-1][1]>MAIN_Y[1] and samples[-1][1]<DAIS_FRONT and all(b[1]>a[1] for a,b in zip(samples,samples[1:])),samples)
    test('previous centimeter-detail Nine Dragons blocks remain intact',
         len([o for o in bpy.data.collections[SOUTH_GROUP].all_objects if o.get('assembly')=='nine_dragon_tile'])==270,270)
    data={'file':MASTER.name,'master_sha256':digest(MASTER),'validated_at':datetime.now(timezone.utc).isoformat(),
          'passed':all(c['passed'] for c in checks),'checks':checks,
          'scope':'Saved geometry, recognized architectural arrangement, specified features and camera path; not measured agreement of every surface.'}
    dump(VALIDATION,data)
    print('HUANGJI_VERIFIED',data['passed'],[(c['check'],c['evidence']) for c in checks if not c['passed']],flush=True)
    if not data['passed']:
        raise RuntimeError('One or more reopened architecture checks failed.')


def mathutils_inverse(loc):
    co,si=math.cos(loc.yaw),math.sin(loc.yaw)
    return lambda v:(co*(v.x-loc.x)+si*(v.y-loc.y),-si*(v.x-loc.x)+co*(v.y-loc.y),v.z)


def render(args):
    scene=bpy.data.scenes[TOUR]; base=bpy.context.scene
    bpy.context.window.scene=scene
    configure_cycles(scene)
    scene.render.resolution_x,scene.render.resolution_y=args.width,round(args.width*9/16)
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'; scene.render.image_settings.color_mode='RGB'
    scene.render.image_settings.compression=16
    scene.cycles.samples=args.samples; scene.cycles.use_denoising=True
    scene.render.use_persistent_data=True
    if scene.cycles.device=='GPU': scene.cycles.denoiser='OPTIX'
    job={'master_file':MASTER.name,'master_sha256':digest(MASTER),'engine':'CYCLES','device':scene.cycles.device,
         'samples':args.samples,'denoiser':'OPTIX' if scene.cycles.device=='GPU' else 'OPENIMAGEDENOISE',
         'width':args.width,'height':scene.render.resolution_y,'fps':FPS,'frames_total':FRAMES,
         'renderer_sha256':digest(Path(__file__))}
    print('HUANGJI_RENDER_DEVICE',scene.cycles.device,flush=True)
    if args.mode=='stills':
        for i in args.views.split(','):
            cam=next(o for o in base.objects if o.type=='CAMERA' and o.name.startswith(i+' · '))
            if cam.name not in scene.objects: scene.collection.objects.link(cam)
            scene.camera=cam
            scene.render.filepath=str(ROOT/'renders'/f'{i}_{VIEWS[i][0]}_{args.suffix}.png')
            started=time.monotonic()
            bpy.ops.render.render(write_still=True)
            path=Path(scene.render.filepath)
            dump(path.with_suffix('.render.json'),dict(job,camera=cam.name,view=i,
                 camera_matrix_world=[list(row) for row in cam.matrix_world],image_sha256=digest(path),
                 elapsed_seconds=round(time.monotonic()-started,3),completed_at=datetime.now(timezone.utc).isoformat()))
        return
    folder=ROOT/'renders'/(FRAME_DIR if args.suffix=='huangji' else FRAME_DIR+'_'+args.suffix)
    folder.mkdir(exist_ok=True)
    stamp=folder/'render_job.json'
    existing=json.loads(stamp.read_text('utf-8')) if stamp.is_file() else None
    if existing!=job:
        if any(folder.glob('[0-9][0-9][0-9][0-9].png')):
            raise RuntimeError('Existing camera frames belong to different settings or an unverified job. Choose a fresh --suffix.')
        dump(stamp,job)
    for frame in (range(1,FRAMES+1) if args.frames=='all' else (int(n) for n in args.frames.split(','))):
        path=folder/f'{frame:04d}.png'
        if (path.is_file() and path.stat().st_mtime_ns>=MASTER.stat().st_mtime_ns
                and png_size(path)==(args.width,scene.render.resolution_y)):
            continue
        pending=path.with_suffix('.pending.png')
        scene.frame_set(frame); scene.render.filepath=str(pending)
        bpy.ops.render.render(write_still=True)
        pending.replace(path)
        print('HUANGJI_FRAME',frame,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('build','verify','stills','tour'))
    parser.add_argument('--views',default=','.join(VIEWS))
    parser.add_argument('--frames',default='all')
    parser.add_argument('--suffix',default='huangji')
    parser.add_argument('--samples',type=int,default=36)
    parser.add_argument('--width',type=int,default=1280)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.mode=='build':
        build()
        return
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    verify(bpy.context.scene) if args.mode=='verify' else render(args)


if __name__=='__main__':
    main()
