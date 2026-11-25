"""Create a human-scale, walkable camera animation and temper roof reflections.

The path stays on the mapped southern court, climbs the mapped centre stair,
crosses the real Taihe doorway, and ends at floor level inside the hall.  The
visitor animation is derived from the editable native Blender reconstruction;
it is not a 3D scan claim.
"""
from pathlib import Path
import argparse
import json
import math
import sys

import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'The_Forbidden_City_Immersive_Refined.blend'
OUTPUT=ROOT/'The_Forbidden_City_Cinematic.blend'
RENDERS=ROOT/'renders'


def tune_finish_and_sun():
    scene=bpy.context.scene
    scene.view_settings.exposure=-0.16
    scene.view_settings.look='AgX - Medium High Contrast'
    changed=[]
    for material in bpy.data.materials:
        if not material.use_nodes:
            continue
        surface=material.node_tree.nodes.get('Principled BSDF')
        if surface is None:
            continue
        if any(token in material.name for token in ('黄琉璃','琉璃筒瓦','板瓦')):
            surface.inputs['Roughness'].default_value=max(.64,surface.inputs['Roughness'].default_value)
            if 'Coat Weight' in surface.inputs:
                surface.inputs['Coat Weight'].default_value=0.0
            if 'IOR Level' in surface.inputs:
                surface.inputs['IOR Level'].default_value=.24
            changed.append(material.name)
        elif any(token in material.name for token in ('深红漆木','格扇暗红')):
            surface.inputs['Roughness'].default_value=max(.55,surface.inputs['Roughness'].default_value)
            if 'Coat Weight' in surface.inputs:
                surface.inputs['Coat Weight'].default_value=min(.08,surface.inputs['Coat Weight'].default_value)
    sun_object=next((o for o in bpy.context.scene.objects
                     if o.type=='LIGHT' and o.name=='日光 · south west'),None)
    if sun_object is not None:
        sun=sun_object.data
        sun.energy=1.30
        sun.angle=math.radians(5.5)
        elevation=math.radians(47)
        azimuth=math.radians(310)
        direction=Vector((math.cos(elevation)*math.cos(azimuth),
                          math.cos(elevation)*math.sin(azimuth),math.sin(elevation)))
        sun_object.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler()
        if bpy.context.scene.world is not None and bpy.context.scene.world.use_nodes:
            for node in bpy.context.scene.world.node_tree.nodes:
                if node.type=='TEX_SKY' and hasattr(node,'sun_rotation'):
                    node.sun_elevation=elevation
                    node.sun_rotation=azimuth
    for name,power,size in (
        ('太和殿室内天光 · soft skylight',12500.,27.),
        ('太和殿御座面光 · bounced daylight',2800.,15.),
        ('太和殿内殿漫射反光 · bounced diffuse fill',2300.,14.),
    ):
        light=bpy.data.lights.get(name)
        if light is not None:
            light.energy=power
            light.shape='DISK'
            light.size=size
    return changed


def make_camera():
    scene=bpy.context.scene
    old=bpy.data.collections.get('沉浸动线 · 人眼高度摄影机')
    if old is not None:
        for obj in list(old.objects):
            bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.collections.remove(old)
    rig=bpy.data.collections.new('沉浸动线 · 人眼高度摄影机')
    scene.collection.children.link(rig)
    camera_data=bpy.data.cameras.new('故宫中轴步行镜头 · 36 mm')
    camera_data.lens=36
    camera_data.sensor_width=36
    camera_data.clip_start=.08
    camera_data.clip_end=1800
    camera=bpy.data.objects.new('12 · 御道实地步行 · 一镜到底',camera_data)
    rig.objects.link(camera)
    target=bpy.data.objects.new('12 · 运镜注视目标',None)
    rig.objects.link(target)
    target.empty_display_type='SPHERE'
    target.empty_display_size=.22
    # Time-coded positions trace the real northbound route from the southern
    # Taihe courtyard, over measured centre steps and up to the interior.
    points=[
        (1,   (-1.7,-205,1.672), (-1.7,-151,14.2)),
        (72,  (-1.7,-199,1.672), (-1.7,-151,13.7)),
        (144, (-1.7,-190,1.672), (-1.7,-149,13.2)),
        (216, (-1.7,-180,2.158), (-1.7,-143,12.6)),
        (288, (-1.7,-170,4.699), (-1.7,-135,12.1)),
        (360, (-1.7,-160,7.239), (-1.7,-124,11.7)),
        (432, (-1.7,-150,9.800), (-1.7,-115,11.9)),
        (504, (-1.7,-138,9.780), (-1.7,-104,12.5)),
        (576, (-1.7,-126,9.780), (-1.7,-97,13.0)),
        (648, (-1.7,-114,9.780), (-1.7,-91,13.1)),
        (720, (-1.7,-106,10.005), (-1.7,-79,13.0)),
        (792, (-1.7,-99,10.005), (-1.7,-80,12.5)),
        (864, (-1.7,-94,10.005), (-1.7,-81,11.8)),
    ]
    for frame,position,look_at in points:
        camera.location=position
        camera.keyframe_insert(data_path='location',frame=frame,group='走过三大殿的御道')
        target.location=look_at
        target.keyframe_insert(data_path='location',frame=frame,group='走过三大殿的御道')
    for obj in (camera,target):
        for curve in obj.animation_data.action.fcurves:
            for key in curve.keyframe_points:
                key.interpolation='BEZIER'
                key.handle_left_type='AUTO_CLAMPED'
                key.handle_right_type='AUTO_CLAMPED'
    track=camera.constraints.new('TRACK_TO')
    track.target=target
    track.track_axis='TRACK_NEGATIVE_Z'
    track.up_axis='UP_Y'
    scene.camera=camera
    scene.frame_start=1
    scene.frame_end=864
    scene.render.fps=24
    # Simulate a visitor's gradual adaptation while moving from the bright
    # white-marble court into the naturally dimmer, deep timber interior.
    for frame,exposure in ((1,-.16),(648,-.16),(690,.05),(720,.43),(756,.68),(864,.68)):
        scene.view_settings.exposure=exposure
        scene.keyframe_insert(data_path='view_settings.exposure',frame=frame,group='Human-eye exposure adaptation')
    if scene.animation_data is not None:
        for curve in scene.animation_data.action.fcurves:
            for point in curve.keyframe_points:
                point.interpolation='BEZIER'
                point.handle_left_type='AUTO_CLAMPED'
                point.handle_right_type='AUTO_CLAMPED'
    scene.frame_set(1)
    return camera


def configure_render(width,samples):
    scene=bpy.context.scene
    scene.render.engine='CYCLES'
    scene.cycles.samples=samples
    scene.cycles.use_denoising=True
    scene.cycles.max_bounces=6
    scene.render.resolution_x=width
    scene.render.resolution_y=round(width*9/16)
    scene.render.resolution_percentage=100
    try:
        prefs=bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type='OPTIX'
        prefs.get_devices()
        for device in prefs.devices:
            device.use=device.type=='OPTIX'
        if any(device.use for device in prefs.devices):
            scene.cycles.device='GPU'
    except Exception as exc:
        print('GPU setup warning:',exc,flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--animation',action='store_true')
    parser.add_argument('--width',type=int,default=1280)
    parser.add_argument('--samples',type=int,default=20)
    parser.add_argument('--blend',default=str(OUTPUT))
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if args.preview or args.animation:
        blend=Path(args.blend)
        if not blend.is_absolute():
            blend=ROOT/blend
        bpy.ops.wm.open_mainfile(filepath=str(blend))
    else:
        bpy.ops.wm.open_mainfile(filepath=str(INPUT))
        changed=tune_finish_and_sun()
        camera=make_camera()
        scene=bpy.context.scene
        scene['visitor_walkthrough']='Continuous 36-second visitor route: southern Three Great Halls court → central white-marble steps → Taihe Hall open portal → throne-facing interior.'
        scene['visitor_walkthrough_path']='Centreline follows the mapped palace north–south axis; eye clearance is 1.65 m above the modeled stair and terrace surfaces; this is not an on-site route survey.'
        scene['roof_reflection_refinement']='Reduced solar glare and softened the yellow-glazed tile highlight while preserving specular ceramic response.'
        scene.render.filepath=str(RENDERS/'Forbidden_City_Walkthrough')
        bpy.ops.file.pack_all()
        bpy.context.preferences.filepaths.save_version=2
        bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT),compress=True)
        print('SAVED',OUTPUT,'roof_materials',len(changed),'camera',camera.name,flush=True)
        report={'source':INPUT.name,'new_master':OUTPUT.name,'roof_materials_tuned':changed,
                'camera':camera.name,'animation_seconds':36,'fps':24,'frames':864,
                'world_units':'metres','camera_height':'1.65 m above walking surface'}
        (ROOT/'cinematic_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
        if not args.preview:
            return
    scene=bpy.context.scene
    configure_render(args.width,args.samples)
    if args.animation:
        scene.render.image_settings.file_format='FFMPEG'
        scene.render.ffmpeg.format='MPEG4'
        scene.render.ffmpeg.codec='H264'
        scene.render.ffmpeg.constant_rate_factor='HIGH'
        scene.render.filepath=str(ROOT/'renders'/'故宫中轴沉浸漫游')
        scene.frame_start=1;scene.frame_end=864
        print('ANIMATION_START',scene.render.filepath,flush=True)
        bpy.ops.render.render(animation=True)
        print('ANIMATION_DONE',scene.render.filepath,flush=True)
    else:
        scene.render.image_settings.file_format='PNG'
        frames=(1,144,288,432,576,720,864)
        scene.render.resolution_x=min(args.width,960)
        scene.render.resolution_y=round(scene.render.resolution_x*9/16)
        scene.cycles.samples=min(args.samples,12)
        for frame in frames:
            scene.frame_set(frame)
            path=RENDERS/('walkthrough_storyboard_%03d.png'%frame)
            scene.render.filepath=str(path)
            print('PREVIEW_START',frame,path,flush=True)
            bpy.ops.render.render(write_still=True)
            print('PREVIEW_DONE',frame,flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT),compress=True)


if __name__=='__main__':
    main()
