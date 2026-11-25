"""Generate and render a checked walk up Dui Xiu's eastern stone stairway."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from shapely.geometry import LineString, Point

sys.path.insert(0,str(Path(__file__).resolve().parent))
from duixiu_rockery import EAST, PAVILION_Z, SUMMIT_Z
from osm_site import Site
from outer_court_walkthrough import configure_cycles, first_hit, smoothstep
from qinan_survey import DUIXIU, YUJING, Location

ROOT=Path(__file__).resolve().parents[1]
MASTER=ROOT/'The_Forbidden_City_North_Garden_Revision.blend'
REPORT=ROOT/'north_garden_revision_report.json'
TITLE='堆秀山 · 东磴道登御景亭'
FRAME_DIRECTORY='duixiu_ascent_frames_v3'
FRAMES,FPS=480,24
EYE=1.64


def rounded_line(vertices):
    points=[Vector(p) for p in vertices]
    result=[points[0]]
    for a,b,c in zip(points,points[1:],points[2:]):
        r=min(.228,(b-a).length*.238,(c-b).length*.238)
        first=b+(a-b).normalized()*r
        last=b+(c-b).normalized()*r
        result.extend((1-t)**2*first+2*t*(1-t)*b+t*t*last for t in (j/12 for j in range(13)))
    result.append(points[-1])
    return LineString([tuple(v) for v in result])


def visible(obj):
    return not obj.hide_render and not any(c.hide_render for c in obj.users_collection)


def bounds(obj):
    vectors=[obj.matrix_world@Vector(p) for p in obj.bound_box]
    return [min(p[k] for p in vectors) for k in range(3)],[max(p[k] for p in vectors) for k in range(3)]


def collision_geometry(base,line,loc):
    xmin,ymin,xmax,ymax=line.bounds
    corners=[loc.world(x,y) for x in (xmin,xmax) for y in (ymin,ymax)]
    left,right=min(v[0] for v in corners)-1.1,max(v[0] for v in corners)+1.1
    front,back=min(v[1] for v in corners)-1.1,max(v[1] for v in corners)+1.1
    graph=bpy.context.evaluated_depsgraph_get()
    cache={};trees=[];floors=[]
    for obj in base.objects:
        if obj.type!='MESH' or not obj.data.polygons or not visible(obj):
            continue
        lo,hi=bounds(obj)
        if hi[0]<left or lo[0]>right or hi[1]<front or lo[1]>back or hi[2]<-.07 or lo[2]>PAVILION_Z+EYE+.30:
            continue
        key=obj.data.as_pointer()
        if obj.modifiers:
            tree=BVHTree.FromObject(obj,graph)
        else:
            if key not in cache:
                cache[key]=BVHTree.FromObject(obj,graph)
            tree=cache[key]
        transform=obj.matrix_world.copy()
        inverse=transform.inverted_safe()
        entry=(obj.name,tree,transform,inverse,inverse.to_3x3())
        trees.append(entry)
        if obj.name.startswith(('堆秀山 · 东磴道踏面','御景亭 · 山顶白石台盘','堆秀山 · 山脚南面青石行道',
                                '御景亭 · 独立小台基','场地与城内铺地','石板路 ·')):
            floors.append(entry)
    return trees,floors


def plan_camera(base,loc,pavilion):
    def rock_xy(x,y):
        q=loc.local(Point(pavilion.world(x,y)[:2]))
        return q.x,q.y

    way=[(10.70,-12.08),(10.32,-9.05),(10.27,-7.84),(9.70,-7.58),(8.69,-7.63),
         *[v[:2] for v in EAST],(3.87,1.70),
         *[rock_xy(x,y) for x,y in ((3.27,-.24),(2.77,-.24),(1.72,-.28),(1.11,-.91),(.92,-1.46))]]
    path=rounded_line(way)
    rock_line=LineString([v[:2] for v in EAST])
    threshold=path.project(Point(rock_xy(2.66,-.24)))
    levels=[0.]
    for a,c in zip(EAST,EAST[1:]):
        levels.append(levels[-1]+math.dist(a[:2],c[:2]))
    trees,floors=collision_geometry(base,path,loc)
    all_clear=[];all_support=[];keyframes=[];last_floor=None
    previous=None
    ray_down=Vector((0,0,-1))
    cardinal=[Vector((math.cos(a*math.tau/8),math.sin(a*math.tau/8),0)) for a in range(8)]
    cardinal.extend((Vector((0,0,1)),ray_down))

    def sample(d):
        pt=path.interpolate(min(path.length,max(0.,d)))
        s=rock_line.project(pt)
        idx=min(len(levels)-2,max(i for i,value in enumerate(levels) if value<=s+.0001))
        f=(s-levels[idx])/(levels[idx+1]-levels[idx])
        z=(1-f)*EAST[idx][2]+f*EAST[idx+1][2]
        origin=Vector(loc.world(pt.x,pt.y,z+.57))
        hit=first_hit(floors,origin,ray_down,.95)
        if hit is None or abs(hit[1].z-z)>.39:
            raise RuntimeError(f'Dui Xiu path leaves its built tread: station {d:.2f}, x={pt.x:.2f}, y={pt.y:.2f}: {hit}')
        return pt,hit

    for i in range(FRAMES):
        t=i/(FRAMES-1)
        moving=min(1.,t/.925)
        transition=max(0.,(moving-.90)/.10)
        d=path.length*(min(moving,.90)+.10*(transition+.5*transition**2-.5*transition**4))
        pt,hit=sample(d)
        all_support.append(hit[1].z)
        weighted_offsets=((-3,1),(-2,3),(-1,5),(0,7),(1,5),(2,3),(3,1))
        height=sum(sample(d+off*.105)[1][1].z*w for off,w in weighted_offsets)/25.
        nod=.013*math.sin(d*math.tau/.98)*(1-smoothstep((t-.87)/.071))
        # Lower the head briefly under the stone lintel as the treads start to rise.
        duck=.165*(1-smoothstep((abs(pt.y-EAST[0][1]-.046)-.21)/.61))
        position=Vector(loc.world(pt.x,pt.y,height+EYE+nod-duck))
        for delta in (0.,-.39,-.79):
            for ray in cardinal:
                obstacle=first_hit(trees,position+Vector((0,0,delta)),ray,.177)
                if obstacle:
                    raise RuntimeError(f'Dui Xiu clearance at frame {i+1}: {obstacle[0]}; '
                                       f'camera local=({pt.x:.3f}, {pt.y:.3f}, {position.z:.3f}), '
                                       f'body offset={delta:.2f}, direction={tuple(round(v,2) for v in ray)}')
        if previous is not None:
            diff=position-previous
            if diff.length>.001 and (overlap:=first_hit(trees,previous,diff.normalized(),diff.length)):
                raise RuntimeError(f'Camera crosses {overlap[0]} between frames {i} and {i+1}')
        previous=position
        all_clear.append(height+nod-hit[1].z)
        last_floor=hit[0]
        ahead=path.interpolate(min(path.length,d+2.05))
        forward=Vector(loc.world(ahead.x,ahead.y,height+EYE+.48))
        mountain=Vector(loc.world(.18,-.69,7.86))
        entrance=Vector(pavilion.world(1.38,-.24,PAVILION_Z+1.56))
        chair=Vector(pavilion.world(.0,.64,PAVILION_Z+1.34))
        ceiling=Vector(pavilion.world(.0,.16,PAVILION_Z+2.76))
        start=(1-smoothstep((t-.02)/.213))*.92
        arrival=smoothstep((d-threshold+3.4)/2.64)
        inside=smoothstep((d-threshold+.17)/1.67)
        up=smoothstep((t-.904)/.096)
        look=forward.lerp(mountain,start).lerp(entrance,arrival).lerp(chair,inside).lerp(ceiling,up)-Vector((0,0,duck*2.5))
        rotation=(look-position).to_track_quat('-Z','Y')
        lens=22.0+1.7*(1-start)-6.4*max(inside,up)
        keyframes.append((position,rotation,lens))
    if not last_floor.startswith('御景亭 · 独立小台基') or abs(all_support[-1]-PAVILION_Z)>.012:
        raise RuntimeError(f'The final camera has not entered the pavilion: {last_floor}, {all_support[-1]}')
    audit={'walk_length_m':round(path.length,3),'frames_checked':len(keyframes),'fps':FPS,'eye_height_nominal_m':EYE,
           'minimum_checked_head_torso_radius_m':.177,'head_dip_beneath_entry_lintel_max_m':.165,
           'supported_floor_range_m':[min(all_support),max(all_support)],
           'floor_smoothing_error_m':[min(all_clear),max(all_clear)],'mesh_objects_raycast':len(trees),
           'terminal_support':last_floor,'final_subject':'South-facing throne and inset ceiling inside Yujing Pavilion',
           'scope':'Per-frame vertical tread and head/torso sample from editable meshes. Path alignment and tread dimensions inferred.'}
    return keyframes,audit


def prepare(base,loc,pavilion):
    keys,audit=plan_camera(base,loc,pavilion)
    prior=bpy.data.scenes.get(TITLE)
    if prior:
        old_camera=prior.camera
        bpy.data.scenes.remove(prior)
        if old_camera and not old_camera.users_collection:
            bpy.data.objects.remove(old_camera,do_unlink=True)
    scene=bpy.data.scenes.new(TITLE)
    scene.world=base.world
    scene.unit_settings.system='METRIC'
    scene.unit_settings.scale_length=1.
    shared=0
    for obj in base.objects:
        if not visible(obj):
            continue
        if obj.type=='LIGHT':
            if obj.data.type!='SUN' and not obj.name.startswith(('堆秀山 ·','御景亭 ·')):
                continue
        elif obj.type=='MESH':
            lo,hi=bounds(obj)
            dx=max(0.,lo[0]-loc.x,loc.x-hi[0]);dy=max(0.,lo[1]-loc.y,loc.y-hi[1])
            if dx*dx+dy*dy>78**2:
                continue
        else:
            continue
        scene.collection.objects.link(obj)
        shared+=1
    camera=bpy.data.objects.new(TITLE,bpy.data.cameras.new(TITLE))
    scene.collection.objects.link(camera)
    camera.rotation_mode='QUATERNION'
    camera.data.clip_start=.039
    camera.data.clip_end=1800
    last=None
    for frame,(position,q,focal) in enumerate(keys,1):
        if last is not None and last.dot(q)<0:
            q.negate()
        camera.location=position
        camera.rotation_quaternion=q
        camera.data.lens=focal
        camera.keyframe_insert(data_path='location',frame=frame)
        camera.keyframe_insert(data_path='rotation_quaternion',frame=frame)
        camera.data.keyframe_insert(data_path='lens',frame=frame)
        last=q.copy()
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
    scene.cycles.samples=24
    scene.cycles.use_denoising=True
    scene.cycles.max_bounces=5
    scene.cycles.diffuse_bounces=3
    scene.cycles.glossy_bounces=2
    scene.view_settings.view_transform=base.view_settings.view_transform
    scene.view_settings.look=base.view_settings.look
    scene.view_settings.exposure=.11
    for frame,exposure in ((1,.11),(448,.11),(470,.46),(FRAMES,.55)):
        scene.view_settings.exposure=exposure
        scene.keyframe_insert(data_path='view_settings.exposure',frame=frame)
    scene.frame_set(1)
    audit.update(scene=scene.name,frames=FRAMES,frames_directory=FRAME_DIRECTORY,shared_objects=shared)
    return audit


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('prepare','render'))
    parser.add_argument('--frames',default='all')
    parser.add_argument('--samples',type=int,default=24)
    parser.add_argument('--width',type=int,default=1280)
    parser.add_argument('--suffix',default='')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if args.width!=1280 and not args.suffix:
        parser.error('Use a separate --suffix for preview sizes.')
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    if args.mode=='prepare':
        site=Site()
        result=prepare(bpy.context.scene,Location.from_map(site,DUIXIU),Location.from_map(site,YUJING))
        report=json.loads(REPORT.read_text('utf8'))
        report['duixiu_walkthrough']=result
        bpy.context.preferences.filepaths.save_version=0
        bpy.ops.wm.save_as_mainfile(filepath=str(MASTER),compress=True)
        REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
        print('DUIXIU_WALK_CHECKED',json.dumps(result,ensure_ascii=False),flush=True)
        return
    scene=bpy.data.scenes[TITLE]
    bpy.context.window.scene=scene
    configure_cycles(scene)
    if scene.cycles.device=='GPU':
        scene.cycles.denoiser='OPTIX'
    scene.cycles.samples=args.samples
    scene.render.resolution_x=args.width
    scene.render.resolution_y=round(args.width*9/16)
    folder=ROOT/'renders'/(FRAME_DIRECTORY+args.suffix)
    folder.mkdir(exist_ok=True)
    frames=range(1,FRAMES+1) if args.frames=='all' else map(int,args.frames.split(','))
    for frame in frames:
        filename=folder/f'{frame:04d}.png'
        if filename.is_file():
            continue
        scene.frame_set(frame)
        scene.render.filepath=str(filename)
        print('DUIXIU_WALK_FRAME',frame,flush=True)
        bpy.ops.render.render(write_still=True)


if __name__=='__main__':
    main()
