"""Outer court hall pairs, assembled from editable timber, stone and ceramic meshes."""

from dataclasses import asdict
import math
import random

import bpy
from mathutils import Vector
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

from architectural_roofs import swept_roof
from mesh_tools import Batch, collection
from paired_hall_plans import split_plan
from palace_architecture import dougong, frieze, railing, stairs
from palace_materials import paint


def column(batch, x, y, floor, top, radius, pal):
    batch.lathe(x, y, ((radius*1.32, floor-.025), (radius*1.32, floor+.084),
                      (radius*1.07, floor+.23)), pal.marble, sides=20)
    batch.lathe(x, y, ((radius, floor+.19), (radius*.99, floor+.85),
                      (radius*.93, top-.40), (radius*.88, top)), pal.red, sides=24)


def frame(batch, x, y, z, width, height, thickness, material):
    for sign in (-1, 1):
        batch.box((x+sign*(width-thickness)*.5, y, z), (thickness, .043, height), material)
        batch.box((x, y, z+sign*(height-thickness)*.5), (width, .043, thickness), material)


def lattice(batch, x, y, z, width, height, pal):
    """Three intersecting directions of wooden bars and six-lobed nail covers."""
    limits = box(-width/2, 0, width/2, height)
    pitch = .177
    for index, angle in enumerate((0., math.pi/3, -math.pi/3)):
        u, v = math.cos(angle), math.sin(angle)
        reach = math.hypot(width, height)+.18
        for j in range(-math.ceil(reach/pitch), math.ceil(reach/pitch)+1):
            d = j*pitch
            a = (-v*d-u*reach, height*.5+u*d-v*reach)
            b = (-v*d+u*reach, height*.5+u*d+v*reach)
            segment = LineString((a, b)).intersection(limits)
            if segment.geom_type == 'LineString' and segment.length > .022:
                a, b = segment.coords[0], segment.coords[-1]
                batch.rod((x+a[0], y-index*.006, z+a[1]),
                          (x+b[0], y-index*.006, z+b[1]), .016, pal.red, sides=5)
    for row in range(1, int(height/pitch)):
        zz = row*pitch
        for i in range(-math.ceil(width/pitch), math.ceil(width/pitch)+1):
            xx = (i+(row%2)*.5)*pitch*2/math.sqrt(3)
            if abs(xx) >= width*.5-.035:
                continue
            point = (x+xx, y-.018, z+zz)
            petals = []
            for j in range(25):
                a = j*math.tau/24
                r = .021+.006*math.cos(6*a)
                petals.append((point[0]+r*math.cos(a), point[1], point[2]+r*math.sin(a)))
            batch.path(petals, .0047, pal.red, sides=4)


def leaf(batch, x, y, z, width, height, pal, *, handle=False):
    stile = .075
    frame(batch, x, y, z+height/2, width, height, stile, pal.red)
    panel_h = height*.27
    batch.box((x, y+.028, z+panel_h*.50), (width-.12, .078, panel_h), pal.door)
    frame(batch, x, y-.021, z+panel_h*.54, width-.19, panel_h*.71, .017, pal.giltpaint)
    batch.box((x, y, z+panel_h), (width, .074, .105), pal.red)
    batch.box((x, y+.060, z+(panel_h+height)*.5),
              (width-.135, .04, height-panel_h-.12), pal.inset)
    lattice(batch, x, y-.032, z+panel_h+.055, width-2*stile, height-panel_h-.13, pal)
    if handle:
        batch.ellipsoid((x+width*.26,y-.066,z+panel_h*.96),(.064,.020,.071),pal.bronze,sides=12,rings=6)
        ring = [(x+width*.26+.041*math.cos(j*math.tau/16), y-.093,
                 z+panel_h*.91+.054*math.sin(j*math.tau/16)) for j in range(17)]
        batch.path(ring, .008, pal.bronze, sides=6)


def open_leaf(target, plan, x, y, floor, width, height, side, pal):
    # Rotate about the outer hinge, preserving the door furniture on the leaf.
    angle = side*math.radians(68)
    hinge = x-side*width/2
    batch = Batch(plan.world(hinge, y), plan.yaw+angle)
    leaf(batch, side*width/2, 0, floor, width, height, pal, handle=True)
    batch.finish('明间开启槅扇 · 独立门扇', target, properties={'hinge_angle_deg':math.degrees(angle)})


def bay_line(width):
    weights = (.155, .202, .286, .202, .155)
    return [-width*.5+width*sum(weights[:i]) for i in range(6)]


def courtyard_materials(pal):
    pal.plinth = paint('外朝东西路 · 夯灰砖与石灰灰缝', (.21,.195,.153),
                       second=(.33,.309,.251), scale=.39, rough=.88, bump=.005,
                       grain=85, brick=(.71,.20,.008,True))
    pal.panelling = paint('外朝东西路 · 槛墙灰砖', (.151,.149,.128),
                          second=(.235,.221,.179), rough=.89, bump=.005,
                          grain=110, brick=(.45,.11,.006,True))
    pal.rafters = paint('外朝东西路 · 椽尾深绿地', (.020,.065,.047),
                        second=(.038,.111,.084), rough=.76, bump=.003, grain=62)
    pal.path_edge = paint('外朝东西路 · 旧青石牙', (.209,.204,.184),
                          second=(.35,.329,.284), scale=.82, rough=.89, bump=.008)


def eave_carpentry(batch, env, eave, rise, pal):
    cx, cy=env.centre
    hw, hd=env.width/2, env.depth/2
    ridge=hw*.76
    for end_wall, halfspan in ((False,hw),(True,hd)):
        columns=math.ceil(2*halfspan/.265)
        for index in range(columns):
            offset=-halfspan+(index+.5)*2*halfspan/columns
            # Hip edges converge as the roof rises. Finish the exposed rafter
            # just inside its intersection with the hip so it never sticks out.
            max_t=(1-(abs(offset)+.065)/hd) if end_wall else .38*(hw-abs(offset)-.065)/(hw-ridge)
            stop=min(max_t,.22 if end_wall else .25)
            if stop < .012:
                continue
            for sign in (-1,1):
                points=[]
                for step in range(7):
                    t=stop*step/6
                    ww=hw+(ridge-hw)*min(t/.38,1)
                    dd=hd*(1-t)
                    u=abs(offset)/(dd if end_wall else ww)
                    z=eave+rise*(.10*t+.90*t**1.71)+.55*u**8*(1-t)**2+.07*(1-t)**14-.263
                    point=(cx+sign*ww,cy+offset,z) if end_wall else (cx+offset,cy+sign*dd,z)
                    points.append(point)
                batch.path(points,.059,pal.rafters,sides=6)
                tail=points[0]
                direction=(Vector(points[0])-Vector(points[1])).normalized()
                batch.rod(Vector(tail)+direction*.006,Vector(tail)+direction*.019,.044,
                          pal.giltpaint if index%4==0 else pal.teal,sides=7)


def facade_framing(plan, env, floor, eave, rise, target, pal, prefix, front=True):
    cx, cy = env.centre
    width, depth = env.width-4.15, env.depth-4.15
    xs = [cx+x for x in bay_line(width)]
    ys = [cy+depth*f for f in (-.5, -.235, .235, .5)]
    top = eave-1.24
    post_radius = .325 if front else .30
    body = Batch(plan.world(0,0),plan.yaw)
    wood = Batch(plan.world(0,0),plan.yaw)
    doors = Batch(plan.world(0,0),plan.yaw)
    floorplan = box(xs[0]-.55,ys[0]-.63,xs[-1]+.55,ys[-1]+.63)
    for row, y in enumerate(ys):
        for i, x in enumerate(xs):
            # Inner bay positions leave a clear central path through both doors.
            column(body,x,y,floor,top,post_radius*(1.06 if row in (1,2) else 1),pal)
            if row in (0,3):
                dougong(wood,x,y,top+.26,pal,scale=.64,direction=(0,-1 if row==0 else 1))
            elif i in (0,5):
                dougong(wood,x,y,top+.26,pal,scale=.56,direction=(-1 if i==0 else 1,0))
    for y in ys:
        wood.box((cx,y,top+.025),(width+.58,.42,.36),pal.red)
    for x in xs:
        wood.box((x,cy,top+.13),(.31,depth+.48,.44),pal.red)
        for y in (ys[0],ys[-1]):
            end = env.y0+.045 if y==ys[0] else env.y1-.045
            wood.beam((x,y,top+.36),(x,end,eave-.28),.23,.30,pal.rafters)
    for side, y in ((-1,ys[0]),(1,ys[-1])):
        outset = side*.11
        for index,(a,b) in enumerate(zip(xs,xs[1:])):
            centre=(a+b)/2
            opening=b-a-.67
            for fraction in (.22,.50,.78):
                dougong(wood,a+(b-a)*fraction,y,top+.24,pal,scale=.58,direction=(0,side))
            door_h=top-floor-.28
            if side==1 and index==2 and front:
                body.box((centre,y,floor+.07),(opening+.32,.50,.14),pal.marble)
                continue
            door_count=6 if index==2 else 4
            door_width=opening/door_count
            bottom=floor+.15 if index==2 else floor+.88
            height=door_h-(bottom-floor)+.08
            if index!=2:
                body.box((centre,y,floor+.46),(opening,.46,.83),pal.panelling)
                body.box((centre,y,floor+.87),(opening+.05,.55,.115),pal.marble_dark)
            if side==1 and index==2 and not front:
                body.box((centre,y,floor+.075),(opening+.22,.47,.15),pal.marble)
            for j in range(door_count):
                x=centre-opening/2+(j+.5)*door_width
                centre_leaf=j in (2,3) and index==2
                if side==-1 and centre_leaf:
                    open_leaf(target,plan,x,y,bottom,door_width-.029,height,1 if j==2 else -1,pal)
                elif side==1 and index==2:
                    # Exterior rear bay of the north hall reads as a closed panel.
                    doors.box((x,y,bottom+height*.5),(door_width-.031,.13,height),pal.door)
                    frame(doors,x,y+outset,bottom+height*.5,door_width-.103,height-.24,.029,pal.red)
                elif side==-1:
                    leaf(doors,x,y,bottom,door_width-.029,height,pal,handle=index==2)
                else:
                    doors.box((x,y,bottom+height*.5),(door_width-.023,.11,height),pal.door)
                    frame(doors,x,y+outset,bottom+height*.5,door_width-.101,height-.18,.024,pal.red)
            body.box((centre,y,top-.075),(opening+.28,.41,.26),pal.red)
    for sign,x in ((-1,xs[0]),(1,xs[-1])):
        # Leave an actual opening in the masonry on both end walls.
        wall_y = cy+(ys[1]-cy)*.12
        aperture = 1.30
        for a,b in ((ys[0],wall_y-aperture/2),(wall_y+aperture/2,ys[-1])):
            body.box((x,(a+b)/2,(top+floor)/2),(.34,b-a,top-floor),pal.paint)
        for lo,hi in ((floor,floor+1.54),(floor+2.84,top)):
            body.box((x,wall_y,(lo+hi)/2),(.34,aperture,hi-lo),pal.paint)
        side=Batch(plan.world(x,wall_y),plan.yaw+sign*math.pi/2)
        leaf(side,0,-.188,floor+1.54,aperture,1.30,pal)
        side.finish(prefix+' · 山墙方窗',target)
        for y in ys[1:3]:
            dougong(wood,x,y,top+.26,pal,scale=.58,direction=(sign,0))
    body.finish(prefix+' · 檐柱金柱、门槛与山墙',target,properties={
        'column_grid_count':24,'column_grid_x_m':xs,'column_grid_y_m':ys,
        'dimension_status':'Bay count documented; actual spans and heights interpreted.'})
    doors.finish(prefix+' · 槅扇、槛窗及三向木格心',target,properties={
        'front_lattice_leaves_by_bay':[4,4,6,4,4], 'central_open_leaves':2})
    frieze_batch=Batch(plan.world(cx,cy),plan.yaw)
    frieze(frieze_batch,width+.35,depth+.35,top+.19,pal,bay=width/5,height=.43)
    frieze(frieze_batch,width+.83,depth+.80,eave-.29,pal,bay=width/5,height=.32,ornate=False)
    eave_carpentry(wood,env,eave,rise,pal)
    wood.finish(prefix+' · 梁枋、额枋、斗栱及椽尾',target)
    frieze_batch.finish(prefix+' · 石青石绿彩画及金线',target,properties={
        'source_quality':'Colour and visual rhythm only; no exact conservation paint tracing available.'})
    return floorplan


def shared_terrace(pair, plan, hall_floors, parent, pal):
    floor = pair.floor
    front, rear = plan.front, plan.rear
    cx = front.centre[0]
    south_edge = front.y0-2.05
    north_edge = front.y1-1.04
    terrace_w = front.width-1.75
    front_plinth=box(cx-terrace_w/2,south_edge,cx+terrace_w/2,north_edge)
    neck_w=plan.link.width-2.24
    link_plinth=box(plan.link.centre[0]-neck_w/2,north_edge,plan.link.centre[0]+neck_w/2,rear.y0+1.29)
    footprint=unary_union([front_plinth, link_plinth, hall_floors[1].buffer(.92, join_style=2)])
    b=Batch(plan.world(0,0),plan.yaw)
    profile=((0.,.20,.19,pal.marble_dark),(.20,.38,.075,pal.marble),
             (.38,floor-.32,-.08,pal.plinth),(floor-.32,floor-.16,.04,pal.marble_dark),
             (floor-.16,floor,.15,pal.marble))
    for lo,hi,overhang,mat in profile:
        b.solid_xy(footprint.buffer(overhang,join_style=2),lo,hi,mat,
                   top=pal.terrace_floor if hi==floor else None)
    # Surface stones sit flush across the moon terrace, with narrow actual joints.
    end=hall_floors[0].bounds[1]+.04
    for row in range(math.ceil((end-south_edge)/.68)):
        y0=south_edge+row*.68
        y1=min(y0+.667,end)
        for i in range(math.ceil(terrace_w/.84)+1):
            x0=max(cx-terrace_w/2,cx-terrace_w/2+(i-.5*(row%2))*.84)
            x1=min(cx+terrace_w/2,cx-terrace_w/2+(i+1-.5*(row%2))*.84-.010)
            if x1>x0+.04 and y1>y0+.02:
                b.box(((x0+x1)/2,(y0+y1)/2,floor+.008),(x1-x0,y1-y0,.023),pal.terrace_floor)
    stair_start=south_edge-3.16
    stairs(b,(cx-1.36,stair_start),(cx-1.36,south_edge+.11),1.51,.04,floor,pal,handrails=False)
    stairs(b,(cx+1.36,stair_start),(cx+1.36,south_edge+.11),1.51,.04,floor,pal,handrails=False)
    b.beam((cx,stair_start,.13),(cx,south_edge+.12,floor+.08),1.10,.26,pal.marble)
    for offset in (-.40,.40):
        b.rod((cx+offset,stair_start,.19),(cx+offset,south_edge+.12,floor+.20),.035,pal.marble_dark,sides=8)
    for sign in (-1,1):
        x=cx+sign*(terrace_w*.36)
        stairs(b,(x,stair_start+.06),(x,south_edge+.12),2.95,.04,floor,pal,handrails=pair.marble_railing)
        if pair.marble_railing:
            for a,c in ((2.28,abs(x-cx)-1.72),(abs(x-cx)+1.72,terrace_w/2)):
                railing(b,LineString([(cx+sign*a,south_edge+.16),(cx+sign*c,south_edge+.16)]),floor,pal,spacing=1.84)
            edge=cx+sign*(terrace_w/2-.14)
            railing(b,LineString([(edge,south_edge+.18),(edge,hall_floors[0].bounds[1])]),floor,pal,spacing=1.84)
    b.finish(pair.front+' · 须弥座或月台、铺石及三路石阶',parent,properties={
        'estimated_floor_z_m':floor,'front_step_approaches':3,
        'masonry_basis':'Museum reports Wuying Sumeru pedestal and marble railings. Step counts and stone profiles are interpreted.'})
    return stair_start


def connecting_gallery(pair, plan, parent, pal):
    group=collection(pair.front+' · 前后殿穿廊',parent)
    link=plan.link
    x,y=link.centre
    eave=min(pair.front_eave,pair.rear_eave)-.72
    rise=2.57
    # Longitudinal ridge is embedded beneath the two neighbouring roof slopes.
    overlap=5.60
    swept_roof('穿廊低屋面',group,pal,origin=plan.world(x,y),yaw=plan.yaw+math.pi/2,
               width=link.depth+2*overlap,depth=link.width,eave=eave,rise=rise,
               kind='gable',tiles=True,pitch=.33,detail=1,soffit=False,
               ridge_terminals=False,gable_ends=False)
    b=Batch(plan.world(0,0),plan.yaw)
    for sign in (-1,1):
        xx=x+sign*(link.width*.5-1.44)
        for i in range(4):
            yy=link.y0-.82+i*(link.depth+1.64)/3
            column(b,xx,yy,pair.floor,eave-.70,.242,pal)
            dougong(b,xx,yy,eave-.57,pal,scale=.44,direction=(sign,0))
            b.box((x,yy,eave-.79),(link.width-2.37,.31,.31),pal.red)
        b.box((xx,y,eave-.70),(.27,link.depth+1.64,.31),pal.rafters)
    b.box((x,y,pair.floor+.023),(link.width-2.45,link.depth+5.42,.047),pal.terrace_floor)
    b.finish('穿廊 · 柱列与真实通行地面',group)
    group['dimension_status']='Width and free span inferred from the mapped narrowing; roof and framing heights interpreted.'
    return group


def approach(site, pair, plan, stairs_y, target, pal):
    c=plan.world(plan.front.centre[0],stairs_y)
    gate=site.geom(pair.gate)
    north_y=gate.bounds[3]
    # Map describes the gate position. The paving module and weathering are visual estimates.
    walkway=Batch()
    length=c[1]-north_y
    n=math.ceil(length/.79)
    for i in range(n):
        y=north_y+(i+.5)*length/n
        for x,w in ((c[0]-1.62,1.48),(c[0],1.73),(c[0]+1.62,1.48)):
            walkway.box((x,y,.052),(w-.012,length/n-.010,.058),pal.path if w>1.6 else pal.path_edge)
    walkway.finish(pair.front+' · 通向宫门的石板甬路',target)


def wenhua_garden(site, target, pal):
    """Place the photo-referenced spring canopies at the contributed map points."""
    garden=collection('文华殿 · 海棠春景与两侧花圃',target)
    turf=paint('文华殿 · 草叶与潮润泥面',(.036,.056,.017),second=(.091,.123,.035),
               scale=1.8,rough=.94,bump=.013,grain=93)
    blossoms=[paint('文华殿 · 海棠花瓣 '+str(i),c,rough=.69,bump=0) for i,c in enumerate(
        ((.65,.36,.42),(.77,.57,.61),(.86,.73,.68),(.60,.28,.33),(.78,.69,.62)))]
    group_nodes=[]
    surface=Batch()
    for ref in ('655912175','655912176'):
        bed=site.geom(ref)
        surface.solid_xy(bed,.023,.061,turf,way=int(ref),bottom=False)
        surface.solid_xy(bed.buffer(.10).difference(bed.buffer(-.11)),.029,.104,pal.path_edge,bottom=False)
        group_nodes.extend((key,position) for key,position in site.nodes.items()
                           if site.node_tags.get(key,{}).get('natural')=='tree' and bed.buffer(.60).covers(Point(position)))
    surface.finish('文华殿 · 花圃地形与青石压边',garden)
    tree_ids={key for key,_ in group_nodes}
    # Replace each tree's old branch and needle variants at this same position.
    for obj in list(bpy.context.scene.objects):
        if str(obj.get('osm_node','')) in tree_ids:
            bpy.data.objects.remove(obj,do_unlink=True)
    for i,(ref,position) in enumerate(sorted(group_nodes)):
        rng=random.Random(int(ref))
        b=Batch((*position,.061))
        center=(position[0],position[1],.061)
        height=5.0+rng.uniform(.1,1.45)

        def branch(start, direction, length, radius, level):
            direction=direction.normalized()
            elbow=start+direction*(length*.64)+Vector((rng.uniform(-.1,.1),rng.uniform(-.1,.1),.095))
            end=start+direction*length
            b.rod(start,elbow,radius,pal.trunk,r1=radius*.66,sides=8)
            b.rod(elbow,end,radius*.66,pal.trunk,r1=radius*.43,sides=7)
            if level:
                for j in range(3 if level>1 else 2):
                    angle=rng.uniform(0,math.tau)
                    base=elbow.lerp(end,j/(3 if level>1 else 2))
                    growth=direction.lerp(Vector((math.cos(angle),math.sin(angle),rng.uniform(.2,.85))),.48)
                    branch(base,growth,length*rng.uniform(.52,.73),radius*.48,level-1)
                return
            for k in range(11):
                pos=elbow.lerp(end,(k+.35)/11)
                angle=rng.uniform(0,math.tau)
                pos+=Vector((.12*math.cos(angle),.12*math.sin(angle),rng.uniform(-.05,.10)))
                color=blossoms[rng.randrange(len(blossoms))]
                basis=Vector((math.cos(angle),math.sin(angle),.15))
                across=Vector((-basis.y,basis.x,.4))
                centre_radius=rng.uniform(.034,.058)
                for petal in range(5):
                    a=petal*math.tau/5
                    d=basis*math.cos(a)+across*math.sin(a)
                    q=pos+d*(centre_radius*.72)
                    tangent=-basis*math.sin(a)+across*math.cos(a)
                    b.face([tuple(pos),tuple(q+tangent*.025),tuple(q+d*.035),tuple(q-tangent*.025)],color)
                if k%4==0:
                    leaf=pos+direction*.10+Vector((0,0,-.046))
                    b.face([tuple(pos),tuple(pos.lerp(leaf,.49)+across*.035),tuple(leaf),
                            tuple(pos.lerp(leaf,.49)-across*.035)],pal.leaves[(k+i)%len(pal.leaves)])

        for stem in range(5):
            angle=stem*2.399+rng.uniform(-.30,.30)
            start=Vector((.095*math.cos(angle),.095*math.sin(angle),0))
            axis=Vector((.35*math.cos(angle),.35*math.sin(angle),1.)).normalized()
            curve=start+axis*height*.38
            b.rod(start,curve,.13,pal.trunk,r1=.063,sides=11)
            for j in range(5):
                a=angle+(j-2)*.56
                direction=Vector((math.cos(a),math.sin(a),.74+j*.25))
                branch(curve.lerp(start,.12*j),direction,height*(.41-.045*j),.069-.008*j,3)
        b.finish('文华殿 · 海棠 '+ref,garden,properties={
            'osm_node':ref,'position_m':center,'season':'Spring blossom selected from site photographs.',
            'accuracy':'Cartographic root point; authored tree shape, flowers and height.'})
    return sorted(tree_ids)


def build_pair(site, pair, parent, pal):
    plan=split_plan(site.geom(pair.ref))
    root=collection(pair.front+'与'+pair.rear+' · 工字形殿群',parent)
    root['source_osm_way']=pair.ref
    root['shape_source_url']=pair.museum_url
    root['plan_overlap']=plan.source_fit
    root['scope']='Measured in model metres. Mapped roof plan, documented building type, estimated elevations and features.'
    floor_plans=[]
    for name,env,eave,rise,front in ((pair.front,plan.front,pair.front_eave,pair.front_rise,True),
                                    (pair.rear,plan.rear,pair.rear_eave,pair.rear_rise,False)):
        group=collection(name+' · 单檐歇山',root)
        group['hall_name']=name
        group['roof_envelope_width_depth_m']=[env.width,env.depth]
        group['eave_and_ridge_z_m']=[eave,eave+rise]
        group['bay_count_wide_depth']=[5,3]
        roof=swept_roof('黄琉璃瓦单檐歇山',group,pal,origin=plan.world(*env.centre),yaw=plan.yaw,
                        width=env.width,depth=env.depth,eave=eave,rise=rise,
                        kind='xieshan',tiles=True,pitch=.33,beasts=5 if front else 3,detail=1,
                        eave_lift=.55,terminal_height=1.12 if front else .92,soffit=False,
                        ridge_length=env.width*.76)
        roof['source_osm_way']=pair.ref
        floor_plans.append(facade_framing(plan,env,pair.floor,eave,rise,group,pal,name,front=front))
    terrace=collection(pair.front+' · 月台与前庭',root)
    bottom=shared_terrace(pair,plan,floor_plans,terrace,pal)
    approach(site,pair,plan,bottom,terrace,pal)
    garden_nodes=wenhua_garden(site,terrace,pal) if pair.ref=='43519304' else []
    connecting_gallery(pair,plan,root,pal)
    report={
        'building':pair.front,'rear_hall':pair.rear,'museum_source':pair.museum_url,
        'osm_way':pair.ref,'gate_osm_way':pair.gate,'origin':list(plan.origin),'yaw_rad':plan.yaw,
        'spring_garden_tree_nodes':garden_nodes,
        'plan_iou_against_contributed_map':round(plan.source_fit,6),
        'roof_envelopes_local_m':{part:asdict(getattr(plan,part)) for part in ('front','rear','link')},
        'model_elevations_m_estimated':{'floor':pair.floor,'front_eave':pair.front_eave,
            'front_ridge':pair.front_eave+pair.front_rise,'rear_eave':pair.rear_eave,
            'rear_ridge':pair.rear_eave+pair.rear_rise},
        'photo_validation_limits':'Actual conservation elevations, exact ornament inventories, interior exhibition fittings and repair-era dimensions unavailable here.'}
    return root, plan, report
