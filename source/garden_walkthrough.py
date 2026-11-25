"""Native foot-level approach from the stone paving into Chengrui's caisson."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from garden_bridge_pavilions import STUDIES, plan_from_map
from osm_site import Site
from outer_court_walkthrough import configure_cycles, first_hit, route_geometry, smoothstep

ROOT=Path(__file__).resolve().parents[1]
MASTER=ROOT/'The_Forbidden_City_Imperial_Garden_Revision.blend'
REPORT=ROOT/'imperial_garden_revision_report.json'
WALK_SCENE='澄瑞亭 · 过桥仰看双龙藻井'
FRAME_DIRECTORY='chengrui_bridge_walkthrough_frames'
FRAMES=216
FPS=24
EYE=1.64


def create_walkthrough(base,plan):
    graph=bpy.context.evaluated_depsgraph_get()
    start,finish=plan.front_y-4.56,plan.main_y-.21
    x=.16
    trees=route_geometry(base,graph,plan.world(x,start-1.1),plan.world(x,finish+1.1),1.72,4.05)

    def floor(y):
        h=first_hit(trees,Vector(plan.world(x,y,1.19)),Vector((0,0,-1)),1.33)
        if h is None or h[1].z<-.021:
            raise RuntimeError(f'Missing tread at Chengrui local y={y:.3f}: {h}')
        return h[1].z

    previous_position=None
    keys=[]
    levels=[]
    eye_deviation=[]
    rays=[Vector((math.cos(a*math.tau/8),math.sin(a*math.tau/8),0)) for a in range(8)]
    rays.extend((Vector((0,0,-1)),Vector((0,0,1))))
    for i in range(FRAMES):
        t=i/(FRAMES-1)
        u=min(1.,t/.87)
        distance=(finish-start)*(.89*u+.11*smoothstep(u))
        y=start+distance
        z=floor(y)
        levels.append(z)
        # Transition smoothly over the edge of a tread while keeping the
        # underlying walk surface and body clearances sampled at every frame.
        average=sum(floor(y+j*.089)*weight for j,weight in ((-3,1),(-2,3),(-1,5),(0,7),(1,5),(2,3),(3,1)))/25
        stride=.009*math.sin(distance*math.tau/.97)*(1-smoothstep((t-.78)/.10))
        eye_deviation.append(round(average-z+stride,5))
        position=Vector(plan.world(x,y,average+EYE+stride))
        for offset in (0,-.45,-.94):
            for direction in rays:
                hit=first_hit(trees,position+Vector((0,0,offset)),direction,.20)
                if hit:
                    raise RuntimeError(f'Chengrui path hits {hit[0]} at frame {i+1}')
        if previous_position is not None:
            delta=position-previous_position
            if delta.length>.001 and first_hit(trees,previous_position,delta.normalized(),delta.length):
                raise RuntimeError(f'Camera intersects architecture between frames {i} and {i+1}')
        previous_position=position
        glance=smoothstep((t-.67)/.33)
        ahead=Vector(plan.world(.03,y+3.15,average+EYE+.23+.16*(1-smoothstep(t/.27))))
        caisson=Vector(plan.world(-.044,plan.main_y+.29,5.03))
        look=ahead.lerp(caisson,glance)
        keys.append((position,(look-position).to_track_quat('-Z','Y'),23.5-2.65*glance))

    previous=bpy.data.scenes.get(WALK_SCENE)
    if previous:
        obj=previous.camera
        bpy.data.scenes.remove(previous)
        if obj and not obj.users_collection:
            bpy.data.objects.remove(obj,do_unlink=True)
    scene=bpy.data.scenes.new(WALK_SCENE)
    scene.world=base.world
    scene.unit_settings.system='METRIC'
    scene.unit_settings.scale_length=1.
    native=0
    for obj in base.objects:
        if obj.hide_render or any(c.hide_render for c in obj.users_collection):
            continue
        if obj.type=='LIGHT':
            if obj.data.type!='SUN' and not obj.name.startswith('澄瑞亭'):
                continue
        elif obj.type=='MESH':
            bounds=[obj.matrix_world@Vector(v) for v in obj.bound_box]
            dx=max(0.,min(v.x for v in bounds)-plan.x,plan.x-max(v.x for v in bounds))
            dy=max(0.,min(v.y for v in bounds)-plan.y,plan.y-max(v.y for v in bounds))
            if dx*dx+dy*dy>58**2:
                continue
        else:
            continue
        scene.collection.objects.link(obj)
        native+=1
    lens=bpy.data.cameras.new(WALK_SCENE)
    lens.clip_start=.042;lens.clip_end=1200
    camera=bpy.data.objects.new(WALK_SCENE,lens)
    scene.collection.objects.link(camera)
    camera.rotation_mode='QUATERNION'
    q0=None
    for frame,(loc,q,focal) in enumerate(keys,1):
        if q0 is not None and q.dot(q0)<0:
            q.negate()
        camera.location=loc;camera.rotation_quaternion=q;lens.lens=focal
        camera.keyframe_insert(data_path='location',frame=frame)
        camera.keyframe_insert(data_path='rotation_quaternion',frame=frame)
        lens.keyframe_insert(data_path='lens',frame=frame)
        q0=q.copy()
    scene.camera=camera
    scene.frame_start,scene.frame_end=1,FRAMES
    scene.render.engine='CYCLES'
    scene.render.fps=FPS
    scene.render.resolution_x,scene.render.resolution_y=1280,720
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGB'
    scene.render.filepath=f'//renders/{FRAME_DIRECTORY}/'
    scene.render.use_persistent_data=True
    scene.cycles.samples=32
    scene.cycles.max_bounces=6
    scene.cycles.diffuse_bounces=3
    scene.cycles.glossy_bounces=3
    scene.cycles.use_denoising=True
    scene.view_settings.view_transform=base.view_settings.view_transform
    scene.view_settings.look=base.view_settings.look
    scene.view_settings.exposure=.27
    scene.frame_set(1)
    return {'scene':scene.name,'frames':FRAMES,'fps':FPS,'frames_directory':FRAME_DIRECTORY,
            'walk_distance_m':round(finish-start,3),'eye_height_m':EYE,'sampled_head_body_clearance_m':.20,
            'floor_range_m':[min(levels),max(levels)],'checked_frames':len(levels),
            'eye_height_smoothing_deviation_m':[min(eye_deviation),max(eye_deviation)],
            'shared_render_objects':native,'scope':'Ray checks over the modelled paving, not a physical site survey.'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('prepare','render'))
    parser.add_argument('--frames',default='all')
    parser.add_argument('--samples',type=int,default=32)
    parser.add_argument('--width',type=int,default=1280)
    parser.add_argument('--suffix',default='')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    if args.mode=='prepare':
        result=create_walkthrough(bpy.context.scene,plan_from_map(Site(),STUDIES[1]))
        report=json.loads(REPORT.read_text('utf-8'))
        report['chengrui_walkthrough']=result
        bpy.context.preferences.filepaths.save_version=0
        bpy.ops.wm.save_as_mainfile(filepath=str(MASTER),compress=True)
        REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
        print('CHENGRUI_ROUTE_CHECKED',result,flush=True)
        return
    scene=bpy.data.scenes[WALK_SCENE]
    bpy.context.window.scene=scene
    configure_cycles(scene)
    if scene.cycles.device=='GPU':
        scene.cycles.denoiser='OPTIX'
    scene.cycles.samples=args.samples
    scene.render.resolution_x=args.width
    scene.render.resolution_y=round(args.width*9/16)
    directory=ROOT/'renders'/f'{FRAME_DIRECTORY}{args.suffix}'
    directory.mkdir(exist_ok=True)
    frames=range(1,FRAMES+1) if args.frames=='all' else [int(v) for v in args.frames.split(',')]
    for i in frames:
        path=directory/f'{i:04d}.png'
        if path.is_file():
            continue
        scene.frame_set(i)
        scene.render.filepath=str(path)
        print('CHENGRUI_WALK_FRAME',i,flush=True)
        bpy.ops.render.render(write_still=True)


if __name__=='__main__':
    main()
