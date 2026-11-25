"""Render the checked path through both arches in the bathhouse model."""

import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from shapely.geometry import LineString

sys.path.insert(0,str(Path(__file__).resolve().parent))
from outer_court_walkthrough import configure_cycles, first_hit, route_geometry, smoothstep
from yude_bath import BATH_X, BATH_Y, DOOR_X, HALL_FLOOR, PASSAGE_POINTS


ROOT=Path(__file__).resolve().parents[1]
WALK_SCENE='浴德堂 · 穿过券道看穹顶'
FRAME_DIRECTORY='yude_tang_walkthrough_frames'
FPS=24
FRAME_COUNT=288


def round_route(points):
    vectors=[Vector(p) for p in points]
    route=[vectors[0]]
    for a,b,c in zip(vectors,vectors[1:],vectors[2:]):
        radius=min(.30,(b-a).length*.39,(c-b).length*.39)
        start=b+(a-b).normalized()*radius
        end=b+(c-b).normalized()*radius
        for index in range(17):
            t=index/16
            route.append((1-t)**2*start+2*t*(1-t)*b+t*t*end)
    route.append(vectors[-1])
    return LineString([tuple(p) for p in route])


def keyframe_camera(base,group,placement):
    graph=bpy.context.evaluated_depsgraph_get()
    route=round_route([(PASSAGE_POINTS[0][0],.32),*PASSAGE_POINTS,
                       (DOOR_X,8.31),(BATH_X-.56,BATH_Y-.41)])
    top=HALL_FLOOR+1.96
    start=placement.world(*route.coords[0])
    end=placement.world(*route.coords[-1])
    trees=route_geometry(base,graph,start,end,2.35,top+.20)
    eye=1.63
    radius=.155
    floor_height=[]
    transforms=[]
    last_position=None
    for index in range(FRAME_COUNT):
        t=index/(FRAME_COUNT-1)
        normal=min(1.,t/.91)
        distance=route.length*(normal+.52*normal**5*(1-normal))
        sample=route.interpolate(distance)
        x,y=sample.x,sample.y
        floor_probe=Vector(placement.world(x,y,HALL_FLOOR+.26))
        floor_hit=first_hit(trees,floor_probe,Vector((0,0,-1)),.38)
        if floor_hit is None:
            raise RuntimeError(f'Walkthrough leaves the supported floor at frame {index+1}: {x:.2f}, {y:.2f}')
        z=floor_hit[1].z
        floor_height.append(z)
        stride=.011*math.sin(distance*math.tau/1.04)*(1-smoothstep((t-.78)/.13))
        position=Vector(placement.world(x,y,HALL_FLOOR+eye+stride))
        probes=[Vector((math.cos(a*math.tau/8),math.sin(a*math.tau/8),0)) for a in range(8)]
        probes.extend((Vector((0,0,1)),Vector((0,0,-1))))
        for level in (0.,-.41):
            for direction in probes:
                obstacle=first_hit(trees,position+Vector((0,0,level)),direction,radius)
                if obstacle:
                    raise RuntimeError(f'Walkthrough clearance at frame {index+1}: {obstacle[0]}')
        if last_position is not None:
            travel=position-last_position
            if travel.length>1e-6:
                overlap=first_hit(trees,last_position,travel.normalized(),travel.length)
                if overlap:
                    raise RuntimeError(f'Camera intersects {overlap[0]} between frames {index} and {index+1}')
        last_position=position

        ahead=route.interpolate(min(route.length,distance+.92))
        look_ahead=Vector(placement.world(ahead.x,ahead.y,HALL_FLOOR+eye+.06))
        upper=Vector(placement.world(BATH_X+.08,BATH_Y+.72,4.91))
        tilt=smoothstep((t-.76)/.24)
        target=look_ahead.lerp(upper,tilt)
        rotation=(target-position).to_track_quat('-Z','Y')
        lens=21.5-3.4*smoothstep(t/.31)-1.1*tilt
        transforms.append((position,rotation,lens))

    scene=bpy.data.scenes.new(WALK_SCENE)
    scene.world=base.world
    scene.unit_settings.system='METRIC'
    scene.unit_settings.scale_length=1.
    chosen=set(group.all_objects)
    for obj in base.objects:
        if obj.type=='LIGHT' and obj.data.type=='SUN':
            chosen.add(obj)
        if obj.type!='MESH' or obj.hide_render or any(c.hide_render for c in obj.users_collection):
            continue
        corners=[obj.matrix_world@Vector(v) for v in obj.bound_box]
        dx=max(min(v.x for v in corners)-start[0],start[0]-max(v.x for v in corners),0)
        dy=max(min(v.y for v in corners)-start[1],start[1]-max(v.y for v in corners),0)
        if dx*dx+dy*dy<=55**2:
            chosen.add(obj)
    for obj in sorted(chosen,key=lambda item:item.name):
        scene.collection.objects.link(obj)
    data=bpy.data.cameras.new(WALK_SCENE)
    data.clip_start=.042
    data.clip_end=1500
    camera=bpy.data.objects.new(WALK_SCENE,data)
    scene.collection.objects.link(camera)
    camera.rotation_mode='QUATERNION'
    previous=None
    for frame,(position,rotation,lens) in enumerate(transforms,1):
        if previous is not None and previous.dot(rotation)<0:
            rotation.negate()
        camera.location=position
        camera.rotation_quaternion=rotation
        data.lens=lens
        camera.keyframe_insert(data_path='location',frame=frame)
        camera.keyframe_insert(data_path='rotation_quaternion',frame=frame)
        data.keyframe_insert(data_path='lens',frame=frame)
        previous=rotation.copy()
    scene.camera=camera
    scene.frame_start,scene.frame_end=1,FRAME_COUNT
    scene.render.engine='CYCLES'
    scene.render.fps=FPS
    scene.render.resolution_x,scene.render.resolution_y=1280,720
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGB'
    scene.render.filepath=f'//renders/{FRAME_DIRECTORY}/'
    scene.render.use_persistent_data=True
    scene.cycles.samples=32
    scene.cycles.use_denoising=True
    scene.cycles.max_bounces=6
    scene.cycles.diffuse_bounces=4
    scene.cycles.glossy_bounces=2
    scene.view_settings.view_transform=base.view_settings.view_transform
    scene.view_settings.look=base.view_settings.look
    scene.view_settings.exposure=.36
    scene.frame_set(1)
    return {'scene':scene.name,'frames':FRAME_COUNT,'fps':FPS,'frames_directory':FRAME_DIRECTORY,
            'walk_distance_m':round(route.length,3),'eye_height_m':eye,'clearance_radius_m':radius,
            'floor_range_m':[min(floor_height),max(floor_height)],'floor_and_clearance_checks':FRAME_COUNT,
            'checked_meshes':len(trees),'shared_objects':len(chosen),
            'scope':'Sampled floor, torso and head clearance within the saved model. Not a human gait simulation.'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--frames',default='all')
    parser.add_argument('--suffix',default='')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'The_Forbidden_City_Yude_Tang_Revision.blend'))
    scene=bpy.data.scenes[WALK_SCENE]
    bpy.context.window.scene=scene
    configure_cycles(scene)
    directory=ROOT/'renders'/f'{FRAME_DIRECTORY}{args.suffix}'
    directory.mkdir(exist_ok=True)
    frames=range(1,FRAME_COUNT+1) if args.frames=='all' else [int(v) for v in args.frames.split(',')]
    for frame in frames:
        path=directory/f'{frame:04d}.png'
        if path.is_file():
            continue
        scene.frame_set(frame)
        scene.render.filepath=str(path)
        print('YUDE_WALK_FRAME',frame,flush=True)
        bpy.ops.render.render(write_still=True)


if __name__=='__main__':
    main()
