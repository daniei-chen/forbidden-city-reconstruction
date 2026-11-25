"""Camera path over the native Wenhua paving and stairs, with a local render scene."""

import argparse
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
SCENE = '文华殿 · 海棠甬路至檐下'
FRAMES = ROOT/'renders'/'wenhua_approach_frames'
FPS = 24
FRAME_COUNT = 240
PATH_REVISION = 'doorway-v2'


def frame_folder(suffix=''):
    return FRAMES.with_name(f'{FRAMES.name}_{PATH_REVISION}{suffix}')


def smoothstep(value):
    value = min(1.,max(0.,value))
    return value*value*(3-2*value)


def configure_cycles(scene):
    scene.render.engine='CYCLES'
    scene.cycles.device='CPU'
    prefs=bpy.context.preferences.addons['cycles'].preferences
    try:
        prefs.compute_device_type='OPTIX'
        prefs.get_devices()
        for device in prefs.devices:
            device.use=device.type=='OPTIX'
        if any(device.use for device in prefs.devices):
            scene.cycles.device='GPU'
    except (RuntimeError,TypeError) as err:
        print('OptiX unavailable:',err,flush=True)


def route_geometry(scene, graph, start, finish, lateral_margin, top):
    low=Vector((min(start[0],finish[0])-lateral_margin,min(start[1],finish[1])-.35,-.55))
    high=Vector((max(start[0],finish[0])+lateral_margin,max(start[1],finish[1])+.35,top))
    trees=[]
    for obj in scene.objects:
        if obj.type!='MESH' or obj.hide_render or any(c.hide_render for c in obj.users_collection):
            continue
        corners=[obj.matrix_world@Vector(p) for p in obj.bound_box]
        if any(max(v[axis] for v in corners)<low[axis] or min(v[axis] for v in corners)>high[axis]
               for axis in range(3)):
            continue
        if not obj.data.polygons:
            continue
        matrix=obj.matrix_world.copy()
        inverse=matrix.inverted_safe()
        trees.append((obj.name,BVHTree.FromObject(obj,graph),matrix,inverse,inverse.to_3x3()))
    return trees


def first_hit(trees, point, direction, maximum):
    nearest=maximum
    found=None
    for name,tree,matrix,inverse,axes in trees:
        local_ray=axes@direction
        scale=local_ray.length
        hit, _, _, distance=tree.ray_cast(inverse@point,local_ray/scale,nearest*scale)
        if hit is not None and distance/scale < nearest:
            nearest=distance/scale
            found=(name,matrix@hit)
    return found


def add_walkthrough(base, group, plan, pair, *, width=1280, samples=24):
    graph=bpy.context.evaluated_depsgraph_get()
    origin_x,origin_y=plan.origin
    axis_x=plan.front.centre[0]
    start=plan.front.y0-17.70
    finish=plan.front.y0-.82
    stairs_bottom=plan.front.y0-5.21
    trees=route_geometry(base,graph,plan.world(axis_x,start),plan.world(axis_x,finish),2.1,3.60)
    frames=[]
    levels=[]
    shallowest=float('inf')
    for number in range(FRAME_COUNT):
        t=number/(FRAME_COUNT-1)
        distance=t+.32*t*t*(1-t)
        y=start+(finish-start)*distance
        x=axis_x-1.36*smoothstep((y-start)/5.)+.84*smoothstep((y-stairs_bottom-3.35)/2.)
        heights=[]
        for j in range(-5,6):
            p=Vector(plan.world(x,y+j*.041,3.30))
            hit=first_hit(trees,p,Vector((0,0,-1)),3.80)
            if hit is None:
                raise RuntimeError(f'Missing walking surface at frame {number+1}')
            heights.append(hit[1].z)
        floor=sum(heights)/len(heights)
        if floor < -.11 or floor > pair.floor+.12:
            raise RuntimeError(f'Unexpected walking surface at frame {number+1}: {floor:.3f}m')
        pos=Vector(plan.world(x,y,floor+1.65))
        eave_turn=smoothstep((t-.56)/.44)
        aim_y=max(plan.front.y0+2.0,y+7.5)
        aim=Vector(plan.world(axis_x+3.65*eave_turn,aim_y,5.10-1.15*eave_turn))
        frames.append((pos,(aim-pos).to_track_quat('-Z','Y')))
        levels.append(floor)
        if number:
            travel=pos-frames[number-1][0]
            hit=first_hit(trees,frames[number-1][0],travel.normalized(),travel.length+.24)
            if hit:
                raise RuntimeError(f'Camera hits {hit[0]} at frame {number+1}')
        for offset in ((1,0,0),(-1,0,0),(0,0,1)):
            hit=first_hit(trees,pos,Vector(offset),.23)
            if hit:
                shallowest=min(shallowest,(hit[1]-pos).length)
    if shallowest < .23:
        raise RuntimeError('Camera fails lateral or overhead clearance checks')

    walk=bpy.data.scenes.new(SCENE)
    walk.world=base.world
    walk.unit_settings.system='METRIC'
    walk.unit_settings.scale_length=1.
    chosen=set(group.all_objects)
    for obj in base.objects:
        if obj.type=='LIGHT' and obj.data.type=='SUN':
            chosen.add(obj)
        if obj.type!='MESH' or obj.hide_render or any(c.hide_render for c in obj.users_collection):
            continue
        if obj.name.startswith(('场地与城内铺地','石板路 ·','内金水河与池塘','城外地表延伸')):
            chosen.add(obj)
            continue
        corners=[obj.matrix_world@Vector(p) for p in obj.bound_box]
        x0,x1=min(v.x for v in corners),max(v.x for v in corners)
        y0,y1=min(v.y for v in corners),max(v.y for v in corners)
        dx=max(x0-origin_x,0,origin_x-x1)
        dy=max(y0-origin_y,0,origin_y-y1)
        if dx*dx+dy*dy < 105**2:
            chosen.add(obj)
    for obj in sorted(chosen,key=lambda item:item.name):
        walk.collection.objects.link(obj)

    fill_targets=bpy.data.collections.new('文华殿 · 漫游檐下补光对象')
    for mesh in group.all_objects:
        if mesh.type=='MESH' and not any(word in mesh.name for word in ('黄琉璃','海棠','花圃','穿廊')):
            fill_targets.objects.link(mesh)
    fill_data=bpy.data.lights.new('文华殿 · 漫游檐下柔光','AREA')
    fill_data.energy=610.
    fill_data.shape='RECTANGLE'
    fill_data.size=8.
    fill_data.size_y=3.0
    fill_data.color=(.95,.97,1.)
    fill_data.specular_factor=.25
    fill=bpy.data.objects.new(fill_data.name,fill_data)
    walk.collection.objects.link(fill)
    fill.location=plan.world(axis_x-1.1,plan.front.y0-4.6,4.05)
    fill.rotation_euler=(Vector(plan.world(axis_x+1.5,plan.front.y0+1.6,4.5))-fill.location).to_track_quat('-Z','Y').to_euler()
    fill.light_linking.receiver_collection=fill_targets

    data=bpy.data.cameras.new(SCENE)
    data.lens=22.5
    data.clip_start=.065
    data.clip_end=1800
    obj=bpy.data.objects.new(SCENE,data)
    walk.collection.objects.link(obj)
    obj.rotation_mode='QUATERNION'
    previous=None
    for frame,(location,rotation) in enumerate(frames,1):
        if previous and previous.dot(rotation)<0:
            rotation.negate()
        obj.location=location
        obj.rotation_quaternion=rotation
        obj.keyframe_insert(data_path='location',frame=frame)
        obj.keyframe_insert(data_path='rotation_quaternion',frame=frame)
        previous=rotation.copy()
    walk.camera=obj
    walk.frame_start,walk.frame_end=1,FRAME_COUNT
    walk.frame_set(1)
    walk.render.resolution_x=width
    walk.render.resolution_y=width*9//16
    walk.render.resolution_percentage=100
    walk.render.fps=FPS
    walk.render.film_transparent=False
    walk.render.use_persistent_data=True
    walk.render.image_settings.file_format='PNG'
    walk.render.image_settings.color_mode='RGB'
    walk.render.filepath=f'//renders/{frame_folder().name}/'
    walk.view_settings.view_transform=base.view_settings.view_transform
    walk.view_settings.look=base.view_settings.look
    walk.view_settings.exposure=.24
    configure_cycles(walk)
    walk.cycles.samples=samples
    walk.cycles.use_denoising=True
    walk.cycles.max_bounces=5
    walk.cycles.diffuse_bounces=3
    walk.cycles.glossy_bounces=2
    walk['camera_path_revision']=PATH_REVISION
    walk['motion_note']='Eye height 1.65m over smoothed, ray-sampled paving and steps. Native shared meshes within the local shot.'
    return {'scene':SCENE,'frames_checked':FRAME_COUNT,'fps':FPS,'shared_native_objects':len(chosen),
            'route_intersection_meshes':len(trees),
            'eye_height_m':1.65,'floor_minimum_z_m':min(levels),'floor_maximum_z_m':max(levels),
            'ray_clearance_m':.23,'start_m':list(frames[0][0]),'end_m':list(frames[-1][0]),
            'frames_directory':frame_folder().name,'camera_path_revision':PATH_REVISION,
            'lighting':'Walkthrough-only fill, linked to nearby masonry and wood. Roof glaze uses scene daylight.'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--frames',default='all')
    parser.add_argument('--suffix',default='')
    parser.add_argument('--blend',default='The_Forbidden_City_Yude_Tang_Revision.blend')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/args.blend))
    scene=bpy.data.scenes[SCENE]
    bpy.context.window.scene=scene
    configure_cycles(scene)
    if scene.get('camera_path_revision')!=PATH_REVISION:
        raise RuntimeError('Saved scene does not contain the current camera path')
    folder=frame_folder(args.suffix)
    folder.mkdir(exist_ok=True)
    wanted=range(1,FRAME_COUNT+1) if args.frames=='all' else [int(value) for value in args.frames.split(',')]
    for frame in wanted:
        target=folder/f'{frame:04d}.png'
        if target.is_file():
            continue
        scene.frame_set(frame)
        scene.render.filepath=str(target)
        print('WENHUA_FRAME',frame,flush=True)
        bpy.ops.render.render(write_still=True)


if __name__=='__main__':
    main()
