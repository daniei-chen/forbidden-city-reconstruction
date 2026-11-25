"""Metric reconstruction of Yude Tang from Palace Museum survey drawings and observations."""

from dataclasses import dataclass
import math
import random
from types import SimpleNamespace

import bpy
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from architectural_roofs import swept_roof
from mesh_tools import Batch, collection, polygons
from osm_site import rectangle
from palace_architecture import arch_mesh, arch_section, frieze, plaque_object, railing, stairs
from palace_materials import paint
from paired_halls import column, leaf


HALL_REF = '40542457'
WELL_REF = '40542542'
SOURCES = {
    'museum': 'https://www.dpm.org.cn/explore/building/236482.html',
    'measured_plan_section': 'https://www.dpm.org.cn/Uploads/File/2021/11/08/u6188edf18abbd.pdf',
    'fabric_and_equipment': 'https://www.dpm.org.cn/Uploads/File/2019/07/17/u5d2e998b92f38.pdf',
    'passage_measurements': 'https://www.dpm.org.cn/Uploads/File/pdf/9c/76/2e/9c762e9760e2e9ec23a6da55fb668a45.pdf',
    'interior_photo': 'https://img.dpm.org.cn/Uploads/Picture/dc/7415.jpg',
}

HALL_FLOOR = 1.22
BATH_X, BATH_Y = 3.18, 9.84
INNER = 2.0
WALL = 1.105
BATH_WIDTH = INNER*2
SPRING = HALL_FLOOR+2.60
OCULUS_RADIUS = .30
DOOR_X = BATH_X+1.04
BOILER_FLOOR = 1.30
FIRE_FLOOR = -.70
FIRE_X0, FIRE_X1 = -.42, 1.08
FIRE_Y0, FIRE_Y1 = BATH_Y+INNER+WALL, BATH_Y+INNER+WALL+3.50
FIRE_EXCAVATION = box(FIRE_X0-.36, FIRE_Y0-.32, FIRE_X1+.37, FIRE_Y1+1.81)


@dataclass(frozen=True)
class Placement:
    x: float
    y: float
    yaw: float
    width: float
    depth: float

    def world(self, x=0., y=0., z=0.):
        c,s=math.cos(self.yaw),math.sin(self.yaw)
        return self.x+c*x-s*y, self.y+s*x+c*y, z

    def local(self, x,y,z=0.):
        c,s=math.cos(self.yaw),math.sin(self.yaw)
        dx,dy=x-self.x,y-self.y
        return c*dx+s*dy,-s*dx+c*dy,z

    def batch(self):
        return Batch(self.world(),self.yaw)


def place(site, ident):
    x,y,w,d,yaw=rectangle(site.geom(ident))
    return Placement(x,y,yaw,w,d)


def materials(base):
    p=SimpleNamespace(**base.__dict__)
    p.plaster=paint('浴德堂 · 暗灰石灰墁背',(.135,.131,.113),second=(.255,.239,.206),
                    rough=.87,scale=3.1,grain=48,bump=.013)
    p.mortar=paint('浴德堂 · 缝内石灰及旧色',(.184,.159,.121),second=(.264,.236,.181),
                   rough=.90,scale=4.1,grain=113,bump=.003)
    p.wall=paint('浴德堂 · 旧朱砂抹灰墙',(.238,.043,.030),second=(.401,.083,.056),
                 scale=2.1,rough=.86,grain=64,bump=.006)
    p.brick=paint('浴德堂 · 下碱青砖',(.105,.113,.108),second=(.230,.222,.191),
                  scale=2.3,rough=.88,grain=92,bump=.007,brick=(.38,.087,.008,True))
    p.iron=paint('浴德堂 · 氧化铸铁',(.033,.027,.020),second=(.153,.094,.046),
                  scale=17.,rough=.65,metal=.62,grain=110,bump=.003)
    p.copper=paint('浴德堂 · 烧水锅旧铜',(.108,.072,.037),second=(.252,.159,.079),
                    scale=6.3,rough=.51,metal=.70,bump=.002,grain=118)
    p.floor=paint('浴德堂 · 青砖地面及潮润旧色',(.085,.087,.083),second=(.193,.176,.149),
                   scale=7.1,rough=.73,bump=.006,grain=48)
    p.stone=paint('浴德堂 · 旧青白石门券',(.261,.263,.236),second=(.466,.440,.381),
                   scale=4.9,rough=.87,bump=.005,grain=85)
    p.glaze=[]
    for i,tone in enumerate((.38,.435,.465,.417,.478,.458,.355,.394)):
        glaze=paint(f'浴德堂 · 旧白釉面砖 {i+1}',(tone,tone*.90,tone*.735),
                    second=(tone*.49,tone*.40,tone*.26),scale=1.91,rough=.60+(i%3)*.045,
                    grain=126,bump=.0031,coat=.075)
        nodes,links=glaze.node_tree.nodes,glaze.node_tree.links
        streak=nodes.new('ShaderNodeVectorMath')
        streak.operation='MULTIPLY'
        streak.inputs[1].default_value=(1.16,1.16,.39)
        weather=next(node for node in nodes if node.type=='TEX_NOISE' and node.inputs['Scale'].default_value<2)
        links.new(nodes.get('Texture Coordinate').outputs['Object'],streak.inputs[0])
        links.new(streak.outputs['Vector'],weather.inputs['Vector'])
        ramp=next(node for node in nodes if node.type=='VALTORGB')
        ramp.color_ramp.elements[0].position=.28
        ramp.color_ramp.elements[1].position=.63
        ramp.color_ramp.elements[0].color=(*((tone*.49,tone*.40,tone*.26)),1)
        ramp.color_ramp.elements[1].color=(tone,tone*.90,tone*.735,1)
        speckle=nodes.new('ShaderNodeTexNoise')
        speckle.inputs['Scale'].default_value=41.
        speckle.inputs['Detail'].default_value=3.
        speckle.inputs['Roughness'].default_value=.69
        links.new(nodes.get('Texture Coordinate').outputs['Object'],speckle.inputs['Vector'])
        staining=nodes.new('ShaderNodeValToRGB')
        staining.color_ramp.elements[0].position=.56
        staining.color_ramp.elements[0].color=(1.,1.,1.,1.)
        staining.color_ramp.elements[1].position=.72
        staining.color_ramp.elements[1].color=(.40,.31,.25,1.)
        links.new(speckle.outputs['Fac'],staining.inputs['Fac'])
        multiply=nodes.new('ShaderNodeMixRGB')
        multiply.blend_type='MULTIPLY'
        multiply.inputs[0].default_value=.79
        links.new(ramp.outputs['Color'],multiply.inputs[1])
        links.new(staining.outputs['Color'],multiply.inputs[2])
        links.new(multiply.outputs['Color'],nodes.get('Principled BSDF').inputs['Base Color'])
        p.glaze.append(glaze)
    p.glass=bpy.data.materials.new('浴德堂 · 天窗透光玻璃')
    p.glass.use_nodes=True
    shader=p.glass.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value=(.91,.965,1.,1.)
    shader.inputs['Transmission Weight'].default_value=1.
    shader.inputs['Roughness'].default_value=.10
    p.glass.diffuse_color=(.55,.75,.82,.35)
    return p


def face_bricks(batch, start, end, bottom, top, p, rng, *, hole=None, course=.092):
    """Place individual staggered bricks facing the space on the left of the wall line."""
    ax,ay=start
    dx,dy=end[0]-ax,end[1]-ay
    length=math.hypot(dx,dy)
    ux,uy=dx/length,dy/length
    nx,ny=-uy,ux
    thickness=.014
    face=box(0,bottom,length,top)
    if hole is not None:
        face=face.difference(hole)
    n=math.ceil((top-bottom)/course)
    for row in range(n):
        z=bottom+row*course
        offset=.168 if row%2 else 0.
        for i in range(-1,math.ceil(length/.336)+1):
            u0=max(.006,i*.336+offset+.004)
            u1=min(length-.006,(i+1)*.336+offset-.004)
            z1=min(top-.003,z+course-.006)
            if u1-u0<.018 or z1-z<.009:
                continue
            segment=face.intersection(box(u0,z+.003,u1,z1))
            for piece in polygons(segment):
                profile=list(piece.exterior.coords)[:-1]
                off=.004+rng.random()*.004
                vv=[(ax+u*ux+d*nx,ay+u*uy+d*ny,v) for d in (off-thickness,off) for u,v in profile]
                nn=len(profile)
                material=p.glaze[rng.randrange(len(p.glaze))] if row>1 else p.glaze[(rng.randrange(3)+5)%len(p.glaze)]
                fs=[tuple(reversed(range(nn,2*nn))),tuple(range(nn))]
                fs.extend((i,(i+1)%nn,(i+1)%nn+nn,i+nn) for i in range(nn))
                batch.add(vv,fs,material)


def arch_wall(placement, parent, name, x0, x1, y0, y1, z0, z1, holes, material):
    """Extrude a Y-normal opening wall from its x/z cross-section."""
    section=box(x0,z0,x1,z1).difference(unary_union([hole for hole in holes]))
    b=Batch(placement.world(0,(y0+y1)*.5),placement.yaw)
    arch_mesh(b,section,y1-y0,material)
    return b.finish(name,parent)


def annulus(batch,x,y,inner,outer,z0,z1,material):
    ring=Point(x,y).buffer(outer,quad_segs=40).difference(Point(x,y).buffer(inner,quad_segs=40))
    batch.solid_xy(ring,z0,z1,material)


def round_tile_patch(batch, xyz, theta0, theta1, row0, row1, material):
    verts=[xyz(t,angle) for t in (row0,row1) for angle in
           (theta0,(3*theta0+theta1)/4,(theta0+theta1)/2,(theta0+3*theta1)/4,theta1)]
    batch.add(verts,[(i,i+1,i+6,i+5) for i in range(4)],material)


def dome_spring_outline():
    chamfer=.90
    short=INNER-chamfer
    coords=((-INNER,-short),(-short,-INNER),(short,-INNER),(INNER,-short),
            (INNER,short),(short,INNER),(-short,INNER),(-INNER,short))
    return Polygon([(BATH_X+x,BATH_Y+y) for x,y in coords])


def dome(placement, parent, p):
    cx,cy=BATH_X,BATH_Y
    rng=random.Random(264024)
    structure,finish,cap=placement.batch(),placement.batch(),placement.batch()
    outer_base=2.35
    inner_base=1.98
    rise=1.72
    last=math.acos(OCULUS_RADIUS/inner_base)

    def inside(t, angle, inset=0.):
        s=t/last
        ca,sa=math.cos(angle),math.sin(angle)
        octagonal=1.0/max(abs(ca),abs(sa), (abs(ca)+abs(sa))/1.55)
        radius=inner_base*math.cos(t)*(1+(octagonal-1)*(1-s)**4)-inset
        return cx+radius*ca,cy+radius*sa,SPRING+rise*math.sin(t)-inset*.52

    def outside(t,angle):
        r=OCULUS_RADIUS+.15+(outer_base-OCULUS_RADIUS-.15)*(math.cos(t)-math.cos(last))/(1-math.cos(last))
        return cx+r*math.cos(angle),cy+r*math.sin(angle),SPRING+.13+(rise+.12)*math.sin(t)

    # Tie the inside of the vault into the uppermost wall course with a solid ring.
    support_inner=Polygon([inside(0,i*math.tau/128)[:2] for i in range(128)]).buffer(-.006)
    support_outer=Point(cx,cy).buffer(outer_base+.08,quad_segs=64)
    structure.solid_xy(support_outer.difference(support_inner),SPRING-.055,SPRING+.132,p.mortar)

    for row in range(46):
        lo,hi=last*row/46,last*(row+1)/46
        for i in range(112):
            a,b=math.tau*i/112,math.tau*(i+1)/112
            structure.face([outside(lo,a),outside(lo,b),outside(hi,b),outside(hi,a)],p.plaster,smooth=True)
            structure.face([inside(lo,a,-.004),inside(hi,a,-.004),inside(hi,b,-.004),inside(lo,b,-.004)],
                           p.mortar,smooth=True)
    # The square room transitions to the vault through thirteen corbel courses.
    transition_bottom=HALL_FLOOR+1.55
    for row in range(13):
        a,b=row/13,(row+1)/13
        hi=transition_bottom+(SPRING-transition_bottom)*b
        lo=transition_bottom+(SPRING-transition_bottom)*a
        cut=.90*b
        octagon=Polygon([(-INNER,-INNER+cut),(-INNER+cut,-INNER),(INNER-cut,-INNER),(INNER,-INNER+cut),
                         (INNER,INNER-cut),(INNER-cut,INNER),(-INNER+cut,INNER),(-INNER,INNER-cut)])
        for corner in polygons(box(-INNER,-INNER,INNER,INNER).difference(octagon)):
            points=[(x+cx,y+cy) for x,y in corner.exterior.coords]
            structure.solid_xy(Polygon(points),lo,hi,p.mortar)
        for start,end in zip(octagon.exterior.coords,octagon.exterior.coords[1:]):
            start=(start[0]+cx,start[1]+cy)
            end=(end[0]+cx,end[1]+cy)
            # The rear passage breaks through the lower part of the south course.
            if abs(start[1]-(cy-INNER))<1e-6 and abs(end[1]-(cy-INNER))<1e-6:
                hole=arch_section(DOOR_X-start[0],1.16,HALL_FLOOR+2.13,bottom=HALL_FLOOR-.05)
            else:
                hole=None
            face_bricks(finish,start,end,lo,hi,p,rng,hole=hole,course=hi-lo)
    for row in range(36):
        t0,t1=last*row/36,last*(row+1)/36
        radius=inner_base*math.cos((t0+t1)/2)
        count=max(8,round(math.tau*radius/.235))
        shift=.5*(row%2)
        for i in range(count):
            a,b=math.tau*(i+shift+.019)/count,math.tau*(i+shift+.981)/count
            colour=p.glaze[rng.randrange(len(p.glaze))]
            round_tile_patch(finish,lambda t,angle:inside(t,angle,.013),a,b,
                             t0+.0018,t1-.0018,colour)
    eye=inside(last,0.)[2]
    annulus(cap,cx,cy,OCULUS_RADIUS,.50,eye-.035,eye+.225,p.stone)
    annulus(cap,cx,cy,.45,.56,eye+.208,eye+.257,p.iron)
    annulus(cap,cx,cy,.45,.56,eye+.54,eye+.596,p.iron)
    # Glass fills the lantern roof over the oculus. The masonry is open below it.
    cap.lathe(cx,cy,((.53,eye+.593),(.52,eye+.616),(.21,eye+.723),(.012,eye+.738)),p.glass,sides=96)
    for i in range(8):
        a=i*math.tau/8
        x,y=cx+.452*math.cos(a),cy+.452*math.sin(a)
        cap.rod((x,y,eye+.224),(x,y,eye+.61),.017,p.iron,sides=8)
    structure.finish('浴德堂 · 穹窿顶灰背与内拱泥底',parent,properties={'inner_crown_z_m':eye})
    finish.finish('浴德堂 · 叠涩与逐块白釉拱砖',parent)
    cap.finish('浴德堂 · 0.60 米采光口、石口与玻璃顶盖',parent,properties={
        'masonry_opening_diameter_m':.60,'source':SOURCES['passage_measurements'],
        'upper_lantern':'Interpretive upper joinery and glazing.'})
    return eye


def bath_floor(placement,parent,p):
    cx,cy=BATH_X,BATH_Y
    floor=placement.batch()
    drain_x,drain_y=cx+1.63,cy+1.62
    drain_shape=box(drain_x-.17,drain_y-.17,drain_x+.17,drain_y+.17)
    room=box(cx-INNER,cy-INNER,cx+INNER,cy+INNER)
    floor.solid_xy(room.difference(drain_shape),HALL_FLOOR-.13,HALL_FLOOR-.025,p.floor)
    for j in range(7):
        for i in range(7):
            x,y=cx+(i-3)*.64,cy+(j-3)*.64
            piece=box(x-.316,y-.316,x+.316,y+.316).intersection(room).difference(drain_shape)
            floor.solid_xy(piece,HALL_FLOOR-.025,HALL_FLOOR,p.floor,bottom=False)
    floor.finish('浴德堂 · 按 0.64 m 模数分块铺砖',parent,properties={
        'tile_module_m':.64,'source':SOURCES['fabric_and_equipment']})
    drain=placement.batch()
    coin=Point(drain_x,drain_y).buffer(.112,quad_segs=16)
    square=box(drain_x-.034,drain_y-.034,drain_x+.034,drain_y+.034)
    rays=[Point(drain_x+.106*math.cos(i*math.tau/4+math.pi/4),drain_y+.106*math.sin(i*math.tau/4+math.pi/4)).buffer(.025)
          for i in range(4)]
    drain.solid_xy(drain_shape.difference(unary_union([square]+rays)),HALL_FLOOR-.052,HALL_FLOOR+.001,p.stone)
    drain.path([(x,y,HALL_FLOOR+.004) for x,y in coin.exterior.coords],.008,p.mortar,sides=5)
    drain.solid_xy(drain_shape.buffer(.027).difference(drain_shape),HALL_FLOOR-.11,HALL_FLOOR+.003,p.floor)
    drain.box((drain_x,drain_y,HALL_FLOOR-.17),(.38,.38,.07),p.iron)
    drain.finish('浴德堂 · 东北隅古币式透雕地漏',parent)


def bath_room(placement,parent,p):
    group=collection('浴德堂 · 方室白瓷砖、穹窿与采光天窗',parent)
    cx,cy=BATH_X,BATH_Y
    x0,x1=cx-INNER,cx+INNER
    y0,y1=cy-INNER,cy+INNER
    b=placement.batch()
    b.box((x0-WALL/2,cy,(HALL_FLOOR+SPRING)/2),(WALL,BATH_WIDTH,SPRING-HALL_FLOOR),p.mortar)
    b.box((x1+WALL/2,cy,(HALL_FLOOR+SPRING)/2),(WALL,BATH_WIDTH,SPRING-HALL_FLOOR),p.mortar)
    b.box((cx,y1+WALL/2,(HALL_FLOOR+SPRING)/2),(BATH_WIDTH+2*WALL,WALL,SPRING-HALL_FLOOR),p.mortar)
    b.finish('浴德堂 · 逾一米厚的东、西、北墙体',group,properties={
        'selected_wall_thickness_m':WALL,'source_constraint':'2019 survey description: thickness greater than 1m.'})
    opening=arch_section(DOOR_X,1.16,HALL_FLOOR+2.13,bottom=HALL_FLOOR-.06)
    arch_wall(placement,group,'浴德堂 · 浴室南墙与真实券洞',x0-WALL,x1+WALL,y0-WALL,y0,
              HALL_FLOOR,SPRING,[opening],p.mortar)
    inner=placement.batch()
    rng=random.Random(27931)
    face_bricks(inner,(x0,y0),(x1,y0),HALL_FLOOR,HALL_FLOOR+1.56,p,rng,
                hole=arch_section(DOOR_X-x0,1.16,HALL_FLOOR+2.13,bottom=HALL_FLOOR-.06))
    for a,c in (((x1,y0),(x1,y1)),((x1,y1),(x0,y1)),((x0,y1),(x0,y0))):
        face_bricks(inner,a,c,HALL_FLOOR,HALL_FLOOR+1.56,p,rng)
    spring=HALL_FLOOR+2.13-1.16/2
    for i in range(18):
        a,c=(i+.06)*math.pi/18,(i+.94)*math.pi/18
        for j in range(5):
            yy=y0-WALL+WALL*j/5
            yb=yy+WALL/5-.008
            rr=.574
            inner.face([(DOOR_X+rr*math.cos(a),yy,spring+rr*math.sin(a)),
                        (DOOR_X+rr*math.cos(c),yy,spring+rr*math.sin(c)),
                        (DOOR_X+rr*math.cos(c),yb,spring+rr*math.sin(c)),
                        (DOOR_X+rr*math.cos(a),yb,spring+rr*math.sin(a))],p.glaze[i%len(p.glaze)])
        inner.face([(DOOR_X+r*math.cos(t),y0+.013,spring+r*math.sin(t))
                     for r,t in ((.582,a),(.739,a),(.739,c),(.582,c))],p.glaze[(i*3)%len(p.glaze)])
    for side in (-1,1):
        x=DOOR_X+side*.571
        inner.box((x,y0-.074,HALL_FLOOR+.58),(.023,.15,.17),p.copper)
        inner.box((x,y0-.074,HALL_FLOOR+1.42),(.023,.13,.10),p.copper)
    inner.finish('浴德堂 · 白釉砖错缝、券砖与原门轴痕迹',group,properties={
        'inner_length_width_m':[4.,4.],'door_width_m_modelled':1.16,
        'door_note':'Restored aperture and remaining hinge plates. Original timber leaf is absent in the 2019 account.'})
    outside=placement.batch()
    outline=box(x0-WALL-.05,y0-WALL-.05,x1+WALL+.05,y1+WALL+.05)
    rim=outline.difference(box(x0-WALL+.08,y0-WALL+.08,x1+WALL-.08,y1+WALL-.08))
    # Exterior red panels sit away from the south opening and northern equipment.
    for x in (x0-WALL-.051,x1+WALL+.051):
        outside.box((x,cy,HALL_FLOOR+1.53),(.10,BATH_WIDTH+2*WALL,2.12),p.wall)
        outside.box((x,cy,HALL_FLOOR+.22),(.11,BATH_WIDTH+2*WALL,.51),p.brick)
    outside.solid_xy(outline.difference(dome_spring_outline().buffer(.023,join_style=2)),
                     SPRING-.075,SPRING+.038,p.plaster)
    outside.solid_xy(rim,SPRING+.013,SPRING+.12,p.brick)
    outside.finish('浴德堂 · 外墙红灰、下碱及穹窿围护',group)
    bath_floor(placement,group,p)
    threshold=placement.batch()
    threshold.solid_xy(box(DOOR_X-.58,y0-WALL-.008,DOOR_X+.58,y0+.009),
                       HALL_FLOOR-.14,HALL_FLOOR-.025,p.floor)
    joints=math.ceil(WALL/.56)
    for i in range(joints):
        a=y0-WALL+i*WALL/joints+.002
        b=y0-WALL+(i+1)*WALL/joints-.002
        threshold.solid_xy(box(DOOR_X-.575,a,DOOR_X+.575,b),HALL_FLOOR-.114,HALL_FLOOR,p.floor)
    threshold.finish('浴德堂 · 浴室券门下连续方砖踏面',group)
    return group,dome(placement,group,p)


PASSAGE_POINTS = ((4.66,3.29),(4.66,4.01),(3.56,4.01),(3.56,5.68),(DOOR_X,5.68),
                  (DOOR_X,BATH_Y-INNER-WALL))


def vault_patch(batch, footprint, bounds, surface, material):
    """Tessellate the facing on a fine grid so bricks follow the arch and its bends."""
    if footprint.is_empty:
        return
    x0,y0,x1,y1=bounds
    nx,ny=math.ceil((x1-x0)/.031),math.ceil((y1-y0)/.031)
    dx,dy=(x1-x0)/nx,(y1-y0)/ny
    vertices,faces,index=[],[],{}
    for i in range(nx):
        for j in range(ny):
            cell=box(x0+i*dx,y0+j*dy,x0+(i+1)*dx,y0+(j+1)*dy)
            if footprint.covers(cell):
                triangles=[orient(cell,-1)]
            else:
                triangles=[orient(triangle,-1) for part in polygons(footprint.intersection(cell))
                           for triangle in constrained_delaunay_triangles(part).geoms]
            for triangle in triangles:
                face=[]
                for xy in list(triangle.exterior.coords)[:-1]:
                    if xy not in index:
                        index[xy]=len(vertices)
                        vertices.append(surface(*xy))
                    face.append(index[xy])
                if len(face)==4:
                    faces.extend((tuple(face[:3]),(face[0],face[2],face[3])))
                else:
                    faces.append(tuple(face))
    if faces:
        batch.add(vertices,faces,material,smooth=True)


def passage(placement,parent,p):
    group=collection('浴德堂 · 曲尺券道',parent)
    path=LineString(PASSAGE_POINTS)
    width=1.26
    half=width/2
    inner=path.buffer(half,cap_style=2,join_style=2)
    y0,y1=PASSAGE_POINTS[0][1],PASSAGE_POINTS[-1][1]
    outer=box(2.36,y0,6.26,y1)
    spring=HALL_FLOOR+1.58
    body=placement.batch()
    body.solid_xy(outer.difference(inner),HALL_FLOOR,spring,p.mortar)
    body.solid_xy(inner,HALL_FLOOR-.13,HALL_FLOOR,p.floor)
    body.solid_xy(outer.difference(inner),spring,SPRING+.04,p.mortar,top=p.plaster)
    body.solid_xy(outer.difference(outer.buffer(-.055)).difference(inner.buffer(.005)),
                  spring,SPRING+.035,p.wall,top=p.plaster)
    rng=random.Random(40542457)
    tile=placement.batch()
    boundary=list(inner.exterior.coords)
    for a,b in zip(boundary,boundary[1:]):
        if abs(a[1]-b[1])<1e-6 and (abs(a[1]-y0)<1e-6 or abs(a[1]-y1)<1e-6):
            continue
        # Reversed perimeter leaves the interior to the left of the vector.
        face_bricks(tile,b,a,HALL_FLOOR,spring,p,rng)
    shaft_x,shaft_y=3.56,4.96
    shaft=box(shaft_x-.25,shaft_y-.22,shaft_x+.25,shaft_y+.22)
    roof=outer.difference(shaft)
    covering=placement.batch()
    covering.solid_xy(roof,spring+width/2+.085,SPRING+.04,p.plaster)
    # The vault is a curved surface over the bent walkable polygon. Its roof
    # has a separate rectangular opening where the period section shows light.
    tile_plan=inner.difference(shaft)
    u0,v0,u1,v1=tile_plan.bounds
    step_x,step_y=.145,.23

    def point(x,y):
        s=min(1.,path.distance(Point(x,y))/half)
        # Keep the springing finite at the wall so tiny coordinate differences
        # at the intersection of barrels do not form spikes.
        rise=(math.sqrt(1.004-s*s)-math.sqrt(.004))/(math.sqrt(1.004)-math.sqrt(.004))
        return x,y,spring+half*rise

    shaft_top=SPRING+.201
    boundary=list(orient(shaft,1).exterior.coords)
    for a,b in zip(boundary,boundary[1:]):
        for j in range(12):
            ends=[tuple(x+(z-x)*i/12 for x,z in zip(a,b)) for i in (j,j+1)]
            low=[point(*q) for q in ends]
            high=[(*q,shaft_top) for q in ends]
            covering.face([low[0],high[0],high[1],low[1]],p.stone)
    covering.solid_xy(shaft.buffer(.062,join_style=2).difference(shaft),shaft_top-.045,shaft_top+.06,p.stone)
    covering.box((shaft_x,shaft_y,shaft_top+.035),(.517,.456,.018),p.glass)

    for i in range(math.ceil((u1-u0)/step_x)):
        for j in range(math.ceil((v1-v0)/step_y)+1):
            x=u0+i*step_x
            y=v0+(j-.50*(i%2))*step_y
            bounds=(x,y,x+step_x,y+step_y)
            cell=tile_plan.intersection(box(*bounds))
            if cell.area<1e-7:
                continue
            brick=cell.intersection(box(x+.0025,y+.0025,x+step_x-.0025,y+step_y-.0025))
            # The clay and grout share one surface, with no overlapping vault
            # skins to intersect around the tighter bends.
            vault_patch(tile,brick,bounds,point,p.glaze[rng.randrange(len(p.glaze))])
            vault_patch(tile,cell.difference(brick),bounds,point,p.mortar)
    for i in range(math.ceil((u1-u0)/.56)):
        for j in range(math.ceil((v1-v0)/.56)+1):
            x=u0+i*.56
            y=v0+j*.56
            tile.solid_xy(inner.intersection(box(x+.005,y+.005,x+.552,y+.552)),HALL_FLOOR-.017,
                          HALL_FLOOR+.006,p.floor,bottom=False)
    body.finish('浴德堂 · 券道屏风墙及地坪',group,properties={
        'nominal_first_opening_width_m':width,'laid_out_centreline_m':path.length,
        'published_approximate_length_m':5.2,'note':'Bend offsets scaled from survey plan; published length is approximate.'})
    tile.finish('浴德堂 · 券道白釉砖及曲面拱砖',group)
    covering.finish('浴德堂 · 券道天窗与外部收头',group)
    return group,path.length


def front_hall(placement,parent,p):
    group=collection('浴德堂 · 三间卷棚前殿',parent)
    half=placement.width/2
    depth=placement.depth/2
    xs=(-half+.70,-2.01,2.01,half-.70)
    back=PASSAGE_POINTS[0][1]
    front=-depth+.79
    top=HALL_FLOOR+2.88
    eave=HALL_FLOOR+3.04
    floor=placement.batch()
    floor.solid_xy(box(-half-.32,-depth-.34,half+.32,back+.015),0,HALL_FLOOR-.12,p.brick)
    floor.solid_xy(box(-half-.40,-depth-.43,half+.40,back+.023),HALL_FLOOR-.12,HALL_FLOOR,p.stone,top=p.floor)
    stairs(floor,(0,-depth-2.48),(0,-depth-.35),2.65,.025,HALL_FLOOR,p,handrails=False)
    floor.finish('浴德堂 · 前殿台基、石踏步与砖地',group)
    timber=placement.batch()
    for y in (front,back-.24):
        for x in xs:
            column(timber,x,y,HALL_FLOOR,top,.148,p)
        timber.box((0,y,top+.016),(placement.width-1,.27,.26),p.red)
    for x in xs:
        timber.beam((x,front,top),(x,back-.18,top),.18,.24,p.door)
    for x in (-half+.54,half-.54):
        timber.box((x,(front+back)/2,(HALL_FLOOR+top)/2),(.33,back-front,top-HALL_FLOOR),p.wall)
        yz=[]
        for i in range(41):
            y=-depth+2*depth*i/40
            t=1-abs(y)/depth
            profile=.10*t+.90*t**1.71
            if t>.72:
                a=.72
                s=(t-a)/(1-a)
                v=.10*a+.90*a**1.71
                d=(.10+.90*1.71*a**.71)*(1-a)
                profile=(2*s**3-3*s*s+1)*v+(s**3-2*s*s+s)*d-2*s**3+3*s*s
            yz.append((y,eave+2.22*profile-.15))
        end_wall=Polygon([(-depth,top),(depth,top),*reversed(yz)])
        side=Batch(placement.world(x,0),placement.yaw+math.pi/2)
        arch_mesh(side,end_wall,.32,p.wall)
        side.finish('浴德堂 · 贴合卷棚弧线的红灰山面',group)
    timber.finish('浴德堂 · 檐柱梁架与东西山墙',group)
    for index,(a,b) in enumerate(zip(xs,xs[1:])):
        width=(b-a-.23)/4
        panels=placement.batch()
        if index!=1:
            panels.box(((a+b)/2,front,HALL_FLOOR+.45),(b-a-.26,.24,.90),p.brick)
        for i in range(4):
            if index==1 and i in (1,2):
                continue
            x=a+.115+(i+.50)*width
            z=HALL_FLOOR+(.17 if index==1 else .92)
            leaf(panels,x,front-.028,z,width-.014,top-z-.12,p,handle=index==1)
        panels.finish('浴德堂 · 前檐四扇槅扇与槛窗 '+str(index+1),group)
    opening=arch_section(PASSAGE_POINTS[0][0],1.26,HALL_FLOOR+2.21,bottom=HALL_FLOOR-.06)
    arch_wall(placement,group,'浴德堂 · 东次间后檐券门',-half+.50,half-.50,back-.32,back+.05,
              HALL_FLOOR,top,[opening],p.brick)
    plaque_object('浴德堂',group,p,placement.world(),placement.yaw,(0,front-.20,top-.06),height=.70)
    roof=swept_roof('浴德堂 · 黄琉璃卷棚瓦',group,p,origin=placement.world(),yaw=placement.yaw,
                    width=placement.width,depth=placement.depth,eave=eave,rise=2.22,kind='juanpeng',
                    tiles=True,pitch=.245,detail=2,soffit=True,gable_ends=False)
    roof['source']='Palace Museum 2019 p.92, 2021 p.51 elevation and cross-section.'
    # Short foundation under the bath keeps the raised surface separate from the yard.
    platform=placement.batch()
    platform.solid_xy(box(-.08,back,6.34,FIRE_Y0),0,HALL_FLOOR-.139,p.brick)
    railing(platform,LineString([(half+.25,-depth+.27),(half+.25,back)]),HALL_FLOOR,p,spacing=1.62)
    platform.finish('浴德堂 · 后罩与浴室高台下部',group)
    return group


def vaulted_service_room(placement,parent,p,name,xa,xb,ya,yb,floor,spring,rise,*,feed_opening=None):
    group=collection(name,parent)
    width=xb-xa
    centre=(xa+xb)/2
    body=placement.batch()
    body.box((xa-.14,(ya+yb)/2,(floor+spring)/2),(.28,yb-ya,spring-floor),p.brick)
    if feed_opening:
        feed_y0,feed_y1,feed_z1=feed_opening
        east_wall=box(ya,floor,yb,spring).difference(box(feed_y0,floor-.02,feed_y1,feed_z1))
        feed=Batch(placement.world(xb+.14,0),placement.yaw+math.pi/2)
        arch_mesh(feed,east_wall,.28,p.brick)
        feed.finish(name+' · 东墙与贯通火口',group)
    else:
        body.box((xb+.14,(ya+yb)/2,(floor+spring)/2),(.28,yb-ya,spring-floor),p.brick)
    body.box((centre,(ya+yb)/2,floor-.085),(width+.51,yb-ya,.17),p.stone)
    rng=random.Random(43712)
    for row in range(26):
        a,b=math.pi*(row+.014)/26,math.pi*(row+.986)/26
        t0,t1=math.pi*row/26,math.pi*(row+1)/26
        body.face([(centre+(width*.5+.032)*math.cos(t),v,spring+(rise+.032)*math.sin(t))
                   for t,v in ((t0,ya),(t1,ya),(t1,yb),(t0,yb))],p.mortar)
        for j in range(math.ceil((yb-ya)/.24)):
            y=ya+j*.24
            end=min(y+.232,yb)
            body.face([(centre+width*.50*math.cos(t),v,spring+rise*math.sin(t))
                      for t,v in ((a,y),(b,y),(b,end),(a,end))],p.glaze[rng.randrange(len(p.glaze))])
    roof=box(xa-.34,ya-.22,xb+.34,yb+.30)
    body.solid_xy(roof,spring+rise,spring+rise+.145,p.plaster)
    body.finish(name+' · 墙面、拱券、灰背与地面',group)
    return group


def service_facade(placement,parent,p):
    group=collection('浴德堂 · 灶间与烧火间北立面',parent)
    y=FIRE_Y1
    wall_top=3.97
    openings=[arch_section(4.90,.90,BOILER_FLOOR+1.91,bottom=BOILER_FLOOR-.025,rise=.16),
              arch_section(.27,.92,FIRE_FLOOR+2.04,bottom=FIRE_FLOOR-.025,rise=.19),
              box(2.87,1.98,3.88,2.76),box(4.02,3.13,4.37,3.40)]
    arch_wall(placement,group,'浴德堂 · 北墙红灰、双门与铁窗洞',-.78,6.60,y,y+.31,
              FIRE_FLOOR,wall_top,openings,p.wall)
    arch_wall(placement,group,'浴德堂 · 灶间下碱青砖',1.38,6.60,y+.310,y+.365,
              -.08,1.72,openings,p.brick)
    arch_wall(placement,group,'浴德堂 · 低门两侧下碱青砖',-.78,1.38,y+.310,y+.365,
              FIRE_FLOOR,.48,openings,p.brick)
    b=placement.batch()
    face_y=y+.388
    for x,width,base,top in ((4.90,.90,BOILER_FLOOR,3.21),(.27,.92,FIRE_FLOOR,1.34),
                             (3.375,1.01,1.98,2.76),(4.195,.35,3.13,3.40)):
        stone_w=.134 if x==4.195 else .197
        for sign in (-1,1):
            b.box((x+sign*(width/2+stone_w*.5),face_y,(base+top)*.5),(stone_w,.19,top-base),p.stone)
        b.box((x,face_y,top+.09),(width+2*stone_w+.05,.22,.18),p.stone)
        b.box((x,face_y,base-.05),(width+2*stone_w,.24,.10),p.stone)
    # The photographed window has deep wooden framing and iron bars.
    for i in range(9):
        x=2.93+i*.11
        b.rod((x,y+.22,2.00),(x,y+.22,2.73),.015,p.iron,sides=7)
    for i in range(3):
        z=2.10+i*.24
        b.rod((2.89,y+.222,z),(3.87,y+.222,z),.012,p.iron,sides=7)
    for x,z in ((4.44,1.55),(5.36,2.35),(-.18,.16),(.73,.42)):
        b.box((x,face_y,z),(.046,.073,.21),p.iron)
    # Shallow eave tiles at the top of the photographed continuous elevation.
    length=7.62
    b.box((2.91,y+.26,wall_top-.09),(length,.83,.17),p.brick)
    n=math.ceil(length/.22)
    for i in range(n):
        x=2.91-length/2+(i+.5)*length/n
        mat=p.tiles[i%len(p.tiles)]
        b.rod((x,y-.44,wall_top+.14),(x,y+.66,wall_top+.015),.082,mat,sides=12)
        b.rod((x,y+.65,wall_top+.014),(x,y+.727,wall_top+.005),.093,mat,sides=15)
    for x in (-.74,6.55):
        b.path([(x,y-.48,wall_top+.23),(x,y+.16,wall_top+.14),(x,y+.59,wall_top+.095),
                (x,y+.76,wall_top+.157)],.119,p.tiles[1],sides=11)
    b.finish('浴德堂 · 北立面石券框、铁窗及连檐瓦',group,properties={'reference':'2019, p.94 fig.12'})
    return group


def stone_channel(batch, points, width, depth, material):
    """Build an open trough cross-section swept along the actual sloping alignment."""
    profile=((-width/2,0),(width/2,0),(width/2,depth),(width*.31,depth),
             (width*.29,depth*.31),(-width*.29,depth*.31),(-width*.31,depth),(-width/2,depth))
    sections=[]
    for i,(x,y,z) in enumerate(points):
        a,c=points[max(0,i-1)],points[min(len(points)-1,i+1)]
        dx,dy=c[0]-a[0],c[1]-a[1]
        length=math.hypot(dx,dy)
        sections.extend((x-u*dy/length,y+u*dx/length,z+h) for u,h in profile)
    n=len(profile)
    faces=[tuple(reversed(range(n))),tuple(range(len(sections)-n,len(sections)))]
    faces.extend((i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j)
                 for i in range(len(points)-1) for j in range(n))
    batch.add(sections,faces,material)


def iron_fire_and_boiler(placement,parent,p):
    ym=FIRE_Y0
    feed_y=ym+1.05
    boiler=vaulted_service_room(placement,parent,p,'浴德堂 · 烧水灶间',1.45,6.23,ym,FIRE_Y1,
                               BOILER_FLOOR,BOILER_FLOOR+1.51,.79)
    fire=vaulted_service_room(placement,parent,p,'浴德堂 · 下沉烧火间',FIRE_X0,FIRE_X1,ym,FIRE_Y1,
                             FIRE_FLOOR,FIRE_FLOOR+1.63,.61,
                             feed_opening=(feed_y-.195,feed_y+.195,FIRE_FLOOR+.50))
    service_facade(placement,parent,p)
    b=placement.batch()
    pot_x,pot_y=3.53,ym+.91
    z=BOILER_FLOOR+1.17
    c0=Point(pot_x,pot_y).buffer(.53,quad_segs=40)
    stand=box(1.75,ym+.08,5.74,ym+1.75)
    b.solid_xy(stand.difference(c0),BOILER_FLOOR,z-.052,p.brick)
    b.solid_xy(stand.buffer(.035).difference(c0),z-.052,z+.018,p.stone)
    # Hollow, closed section of the existing vessel retains the 0.92m depth.
    rings=[]
    for i in range(25):
        t=i/24
        radius=max(.002,.50*math.sin(t*math.pi/2))
        rings.append((radius,z-.920+.920*(1-math.cos(t*math.pi/2))))
    profile=rings+[(.515,z+.013),(.534,z+.015),(.536,z-.031)]+[(r+.026,h-.026) for r,h in reversed(rings)]
    b.lathe(pot_x,pot_y,profile,p.copper,sides=100)
    b.finish('浴德堂 · 直径 1.00 米、深 0.92 米的铜锅与锅台',boiler,properties={
        'vessel_internal_m':[1.,.92],'platform_height_m':1.17,'source':SOURCES['fabric_and_equipment']})
    water=placement.batch()
    water.rod((BATH_X-.10,ym+.055,BOILER_FLOOR+1.32),(BATH_X-.10,BATH_Y+INNER-.043,HALL_FLOOR+1.39),
              .039,p.copper,sides=18)
    stone_channel(water,[(4.195,FIRE_Y1+.37,3.23),(4.12,FIRE_Y1-.31,3.19),
                         (3.78,ym+2.32,3.065),(pot_x+.13,pot_y+.38,z+.24)],.19,.14,p.iron)
    water.finish('浴德堂 · 铜质给水管与 U 形导水槽',boiler)

    iron=placement.batch()
    kiln_xy=(1.84,ym+1.05)
    fire_h=1.45
    for row in range(18):
        z0=FIRE_FLOOR+row*fire_h/18
        for i in range(30):
            a,b=math.tau*(i+.015+.5*(row%2))/30,math.tau*(i+.985+.5*(row%2))/30
            mid=(a+b)*.5
            # West firebox feed and two south ducts interrupt the courses.
            if (row<6 and abs(mid-math.pi)<.37) or (abs(mid-1.5*math.pi-.23)<.17 or abs(mid-1.5*math.pi+.23)<.17):
                continue
            points=[(kiln_xy[0]+r*math.cos(angle),kiln_xy[1]+r*math.sin(angle),h)
                    for h in (z0,z0+fire_h/18-.004) for r,angle in ((.60,a),(.664,a),(.664,b),(.60,b))]
            iron.add(points,[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],p.iron)
    for j in range(5):
        y=kiln_xy[1]+(j-2)*.223
        iron.box((kiln_xy[0],y,FIRE_FLOOR+fire_h+.08),(1.18,.15,.16),p.iron)
    for sign in (-1,1):
        iron.box((FIRE_X1+.003,kiln_xy[1]+sign*.222,FIRE_FLOOR+.25),(.058,.054,.50),p.iron)
    iron.box((FIRE_X1+.004,kiln_xy[1],FIRE_FLOOR+.517),(.056,.452,.05),p.iron)
    for x in (1.56,1.83,2.10):
        iron.box((x,kiln_xy[1]-.57,FIRE_FLOOR+.69),(.07,.080,1.43),p.iron)
    iron.finish('浴德堂 · 十八层铸铁火膛、五梁、双火道口',fire,properties={
        'chamber_diameter_height_m':[1.20,1.45],'iron_courses':18,'beams':5,
        'feed_width_height_m':[.39,.50],'source':SOURCES['fabric_and_equipment']})
    ducts=placement.batch()
    for index,x in enumerate((1.695,1.966)):
        points=[(x,kiln_xy[1]-.55,FIRE_FLOOR+.20),(x-.09,ym-.72,-.146),
                (BATH_X+(-.58 if index==0 else -1.60),BATH_Y+.75,.565)]
        for a,c in zip(points,points[1:]):
            dx,dy=c[0]-a[0],c[1]-a[1]
            length=math.hypot(dx,dy)
            for sign in (-1,1):
                x0,y0=-sign*.159*dy/length,sign*.159*dx/length
                ducts.beam((a[0]+x0,a[1]+y0,a[2]),(c[0]+x0,c[1]+y0,c[2]),.102,.39,p.brick)
            ducts.beam(a,c,.38,.065,p.iron)
    ducts.box((BATH_X,BATH_Y,HALL_FLOOR-.265),(4.0,4.0,.102),p.iron)
    ducts.finish('浴德堂 · 算尺火炕道及浴室下铸铁板',fire,properties={
        'accuracy':'Continuity and arrangement follow the published account; hidden slopes and turns interpreted.'})
    access=placement.batch()
    access.solid_xy(box(FIRE_X0,FIRE_Y1,FIRE_X1,FIRE_Y1+.35),FIRE_FLOOR-.16,FIRE_FLOOR,p.stone)
    stairs(access,(.30,FIRE_Y1+.32),(.30,FIRE_Y1+1.82),1.37,FIRE_FLOOR,.025,p,handrails=False)
    # Retain the stair sides outside the room. The hearth throat occupies the east wall below grade.
    left,_,right,_=FIRE_EXCAVATION.bounds
    for x in (left-.05,right+.05):
        access.box((x,FIRE_Y1+1.075,-.4075),(.10,1.51,.885),p.stone)
    access.finish('浴德堂 · 烧火间下沉入口及挡土石阶',fire)
    boiler_access=placement.batch()
    boiler_access.box((4.90,FIRE_Y1+.52,BOILER_FLOOR*.5),(1.54,.72,BOILER_FLOOR),p.stone)
    stairs(boiler_access,(4.90,FIRE_Y1+3.02),(4.90,FIRE_Y1+.876),1.51,.021,BOILER_FLOOR,p,handrails=False)
    boiler_access.finish('浴德堂 · 高台灶间外阶',boiler)
    return boiler,fire


def well_pavilion(site,parent,p):
    loc=place(site,WELL_REF)
    group=collection('浴德堂 · 井亭、高台与石井栏',parent)
    wall,post=loc.batch(),loc.batch()
    hw,hd=loc.width*.5,loc.depth*.5
    floor=2.0
    hole=Point(0,0).buffer(.47,quad_segs=35)
    wall.solid_xy(box(-hw+.37,-hd+.34,hw-.37,hd-.30).difference(hole),0,floor-.15,p.brick)
    wall.solid_xy(box(-hw+.26,-hd+.23,hw-.26,hd-.19).difference(hole),floor-.15,floor,p.stone)
    stairs(wall,(0,-hd-1.94),(0,-hd+.22),2.13,0.,floor,p,handrails=False)
    for x in (-hw+.96,hw-.96):
        for y in (-hd+.82,hd-.82):
            column(post,x,y,floor,4.72,.152,p)
        post.box((x,0,4.53),(.20,loc.depth-1.27,.28),p.red)
    for y in (-hd+.82,hd-.82):
        post.box((0,y,4.55),(loc.width-1.31,.22,.29),p.teal)
    frieze(post,loc.width-1.55,loc.depth-1.35,4.62,p,bay=2.20,height=.38)
    for sign in (-1,1):
        x=sign*(hw-.81)
        post.box((x,0,floor+.63),(.10,loc.depth-1.32,.10),p.red)
        for i in range(18):
            y=-hd+.65+(i+.5)*(loc.depth-1.30)/18
            post.box((x,y,floor+.31),(.064,.059,.61),p.teal)
    # At the well head the photo shows a carved opening beside a shallow basin.
    rim=Point(0.,0.).buffer(.66,quad_segs=48).union(box(-.58,-.28,.58,1.15))
    bowl=Point(0.,0.).buffer(.39,quad_segs=48)
    basin=box(-.467,.46,.467,1.02).buffer(.035)
    joint=bowl.union(basin).union(box(-.13,.32,.13,.56))
    wall.solid_xy(rim.difference(bowl),floor-.008,floor+.16,p.stone)
    wall.solid_xy(rim.difference(joint),floor+.16,floor+.37,p.stone)
    wall.solid_xy(bowl.buffer(.08).difference(bowl),floor-.38,floor-.006,p.brick)
    wall.finish('浴德堂井亭 · 两米井台、井筒与石质井栏',group,bevel=.012,properties={
        'published_platform_height_m':2.0,'osm_way':WELL_REF,'reference':'2019 p.97 fig.27–28'})
    post.finish('浴德堂井亭 · 四柱与梁枋',group)
    swept_roof('浴德堂井亭 · 瓦顶',group,p,origin=loc.world(),yaw=loc.yaw,width=loc.width,
               depth=loc.depth,eave=4.76,rise=1.70,kind='gable',tiles=True,pitch=.254,grey=True,detail=1,
               ridge_terminals=False)
    return group,loc


def exterior_watercourse(placement,well,parent,p):
    group=collection('浴德堂 · 井亭至灶间架空石槽',parent)
    sx,sy,_=placement.local(*well.world(.10,1.08))
    route=[(sx,sy,3.87),(sx+3.30,sy+.12,3.80),(-8.95,FIRE_Y1+.77,3.67),
           (-.21,FIRE_Y1+.77,3.51),(3.69,FIRE_Y1+.77,3.32),(4.195,FIRE_Y1+.28,3.22)]
    b=placement.batch()
    # Leave hairline construction joints between the separate stone elements.
    for a,c in zip(route,route[1:]):
        length=math.dist(a,c)
        pieces=math.ceil(length/1.69)
        for i in range(pieces):
            t0=(i+.005)/pieces
            t1=(i+.995)/pieces
            points=[tuple(x+(y-x)*t for x,y in zip(a,c)) for t in (t0,t1)]
            stone_channel(b,points,.35,.188,p.stone)
    for a,c in zip(route[:3],route[1:4]):
        x,y,z=((x+y)*.5 for x,y in zip(a,c))
        porch=2.0 if x<sx+2.1 else .025
        h=z-porch
        b.lathe(x,y,((.19,porch),(.19,porch+.13),(.12,porch+.22),(.106,porch+h*.78),
                      (.15,z-.18),(.204,z-.12),(.204,z-.018)),p.stone,sides=12)
    for i in range(5):
        x= -.14 + i*.91
        y=FIRE_Y1+.48
        z=3.45-i*.051
        b.box((x,y,z-.11),(.24,.48,.18),p.stone)
    b.finish('浴德堂 · 分段开槽石梁与石支墩',group,bevel=.008,properties={
        'route':'Well to north wall following the described gravity-fed path. Intermediate stones and lengths inferred.',
        'source':SOURCES['fabric_and_equipment'],'source_figure':'2019 pp.94,97 figs.12,27,28'})
    return group


def build_yude(site,root,palette):
    group=collection('浴德堂 · 文献尺度与实景分构件',root)
    placement=place(site,HALL_REF)
    p=materials(palette)
    group['documented_sources']=list(SOURCES.values())
    group['metric_source_status']='Published dimensions where available. Survey-image ratios and inferred fabric elsewhere.'
    group['osm_way']=HALL_REF
    front_hall(placement,group,p)
    _,length=passage(placement,group,p)
    _,eye=bath_room(placement,group,p)
    iron_fire_and_boiler(placement,group,p)
    _,well=well_pavilion(site,group,p)
    exterior_watercourse(placement,well,group,p)
    data={'collection':group.name,'world_origin_m':list(placement.world()),'world_yaw_rad':placement.yaw,
          'sources':SOURCES,'documented_dimensions_m':{'bath_side_approximate':4.,'oculus_diameter':.60,
          'floor_tile_module':.64,'first_arch_width':1.26,'bent_corridor_approximate_length':5.2,
          'boiler_internal_diameter':1.,'boiler_internal_depth':.92,'well_platform_height':2.,
          'fire_room_width':1.50,'fire_room_depth_approximate':3.50,'fire_room_drop':.70,
          'fire_chamber_diameter':1.20,'fire_chamber_height':1.45},
          'adopted_model_values':{'wall_thickness_m':WALL,'schematic_corridor_centreline_m':length,
          'bath_floor_z_m':HALL_FLOOR,'masonry_crown_z_m':eye,'well_location_m':list(well.world())},
          'fidelity_limits':['Published plan/section are archival, and repair details vary by date.',
          'Mapped placement of front hall and well. Exact joints, paint, weathering and current object positions require a site scan.',
          'Hidden duct shape and positions reconstructed from the description and drawing ratios.']}
    return group,placement,data
