"""Fubi and Chengrui pavilions: open timber frames built over mapped ponds."""

from dataclasses import dataclass
import math
import os
from pathlib import Path
import random
from types import SimpleNamespace

import bpy
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from architectural_roofs import swept_roof
from carved_ornament import cloud
from mesh_tools import Batch, collection, object_to_mesh
from osm_site import rectangle
from palace_architecture import arch_mesh, arch_section
from palace_materials import paint, water


@dataclass(frozen=True)
class Study:
    name: str
    way: str
    pond: str
    museum: str
    caisson: str
    photographs: tuple[str, ...]


STUDIES=(
    Study('浮碧亭','40795241','42353096','https://www.dpm.org.cn/explore/building/236498.html','flowers',
          ('https://img.dpm.org.cn/Uploads/Picture/2020/04/17/s5e998d952596d.jpg',
           'https://img.dpm.org.cn/Uploads/Picture/dc/1944[1024].jpg',
           'https://img.dpm.org.cn/Uploads/Picture/dc/8020.jpg')),
    Study('澄瑞亭','40795243','42353097','https://www.dpm.org.cn/explore/building/236443.html','dragons',
          ('https://img.dpm.org.cn/Uploads/Picture/2020/04/16/s5e98108dd6faa.jpg',
           'https://img.dpm.org.cn/Uploads/Picture/2020/04/16/s5e98108dd0c88.jpg',
           'https://img.dpm.org.cn/Uploads/Picture/2020/04/16/s5e98108dce16c.jpg')),
)

WIDTH=8.0
DECK=.79
PORCH=.35
WATER=-.68
POSTS=(-4.,-1.56,1.56,4.)
MAIN_EAVE=5.50
MAIN_RISE=2.74
ANNEX_EAVE=4.76
ANNEX_RISE=1.84
CAISSON_EDGE=4.73
CAISSON_CROWN=5.29
CEILING_PHOTO='https://img.dpm.org.cn/Uploads/Picture/dc/7906.jpg'


@dataclass(frozen=True)
class Plan:
    x: float
    y: float
    yaw: float
    roof_width: float
    front_y: float
    main_y: float
    annex_y: float
    annex_depth: float
    pond: Polygon
    bank_y: tuple[float,float]

    def world(self,x=0.,y=0.,z=0.):
        c,s=math.cos(self.yaw),math.sin(self.yaw)
        return self.x+c*x-s*y,self.y+s*x+c*y,z

    def batch(self):
        return Batch(self.world(),self.yaw)


def plan_from_map(site,study):
    x,y,length,width,long_yaw=rectangle(site.geom(study.way))
    yaw=(long_yaw+math.pi/2+math.pi/2)%math.pi-math.pi/2
    pond=affinity.rotate(affinity.translate(site.geom(study.pond),-x,-y),-yaw,
                         origin=(0,0),use_radians=True)
    crossing=pond.intersection(LineString(((0,-35),(0,35))))
    south,north=crossing.bounds[1],crossing.bounds[3]
    main_y=(length-width)*.5
    front=-length*.5
    annex_depth=length-width+.42
    return Plan(x,y,yaw,width,front,main_y,front+annex_depth/2,annex_depth,pond,(south,north))


def garden_materials(base):
    p=SimpleNamespace(**base.__dict__)
    p.green_clay=paint('御花园 · 旧蓝绿色琉璃',(.020,.165,.152),second=(.070,.338,.283),
                       scale=11.,rough=.38,bump=.004,grain=74,coat=.18)
    p.green=paint('御花园 · 瓦下青绿釉面',(.016,.112,.100),second=(.046,.244,.199),
                  scale=6.8,rough=.45,bump=.008)
    p.stone=paint('御花园 · 风化青白石与暗纹',(.30,.310,.292),second=(.615,.599,.533),
                  scale=2.1,rough=.79,grain=105,bump=.0067)
    p.understone=paint('御花园 · 湿润石券砌体',(.167,.159,.136),second=(.36,.344,.284),
                       scale=4.1,rough=.87,bump=.005,brick=(.61,.22,.0048,True))
    p.fascia=paint('御花园 · 暗朱红博风与梁背',(.118,.018,.010),second=(.246,.048,.030),
                   scale=8.1,rough=.66,grain=96,bump=.0032)
    p.faded_teal=paint('御花园 · 石绿彩画褪色底',(.031,.108,.080),second=(.139,.247,.156),
                       scale=5.5,rough=.79,grain=114,bump=.005)
    p.faded_blue=paint('御花园 · 石青彩画褪色底',(.019,.046,.126),second=(.064,.138,.246),
                       scale=7.2,rough=.78,grain=117,bump=.004)
    p.cream=paint('御花园 · 旧白粉线与华板',(.265,.261,.198),second=(.483,.457,.334),rough=.82,bump=.004)
    p.ochre_wood=paint('御花园 · 藻井旧金地',(.144,.071,.034),second=(.442,.272,.102),
                       scale=12.1,rough=.58,grain=132,bump=.0022)
    p.caisson_gilt=paint('御花园 · 残存金箔与朱底',(.117,.052,.020),second=(.448,.276,.105),
                         scale=24.6,rough=.54,metal=.27,grain=131,bump=.0084)
    p.caisson_shade=paint('御花园 · 深褐托底与尘积',(.062,.027,.012),second=(.260,.156,.077),
                          scale=18.4,rough=.82,grain=156,bump=.0051)
    p.water=water('御花园 · 池面微波与暗反射',(.037,.074,.049),25.)
    p.lotus_green=[paint(f'御花园 · 荷叶 {i+1}',col,rough=.48,bump=.0012,coat=.16)
                   for i,col in enumerate(((.031,.096,.028),(.055,.167,.047),(.094,.197,.043)))]
    p.lotus_pink=paint('御花园 · 荷花淡胭脂',(.49,.12,.18),second=(.89,.464,.51),
                       scale=3.6,rough=.61,bump=.0011)
    return p


def laid_pavers(b, footprint, z, p, *, course=.68, width=.91):
    x0,y0,x1,y1=footprint.bounds
    count=math.ceil((x1-x0)/width)
    for row in range(math.ceil((y1-y0)/course)):
        y=y0+row*course
        for i in range(-1,count+1):
            x=x0+(i+.5*(row%2))*width
            piece=footprint.intersection(box(x+.007,y+.009,x+width-.006,y+course-.006))
            b.solid_xy(piece,z-.058,z,p.terrace_floor,bottom=False)


def raised_stair(b,y0,y1,x,w,z0,z1,count,p):
    for j in range(count):
        a=y0+(y1-y0)*j/count
        c=y0+(y1-y0)*(j+1)/count
        h=z0+(z1-z0)*(j+1)/count
        b.box((x,(a+c)/2,(z0+h)/2),(w,abs(a-c)+.012,h-z0),p.stone)
        b.box((x,(a+c)/2,h-.024),(w+.05,abs(a-c)+.033,.051),p.stone)
    length=abs(y1-y0)
    direction=1 if y1>y0 else -1
    for side in (-1,1):
        outline=Polygon([(0,z0-.02),(length,z0-.02),(length,z1+.29),
                         (length*.79,z1+.24),(length*.64,(z0+z1)/2+.18),
                         (length*.37,z0+.23),(length*.14,z0+.14),(0,z0+.08)])
        block=Batch((x+side*(w/2+.13),y0,0.),math.pi/2 if direction>0 else -math.pi/2)
        arch_mesh(block,outline,.19,p.stone)
        b.add([(u*math.cos(block.yaw)-v*math.sin(block.yaw)+block.origin.x,
                u*math.sin(block.yaw)+v*math.cos(block.yaw)+block.origin.y,z) for u,v,z in block.v],
              block.f,p.stone)


def stone_rail(b,line,z,p,*,banana_leaf=False,interval=1.36):
    points=list(line.coords)
    used=set()
    for start,end in zip(points,points[1:]):
        length=math.dist(start,end)
        if length<.30:
            continue
        dx,dy=(end[0]-start[0])/length,(end[1]-start[1])/length
        yaw=math.atan2(dy,dx)
        count=max(1,round(length/interval))
        span=length/count
        for j in range(count+1):
            x,y=start[0]+dx*j*span,start[1]+dy*j*span
            key=round(x,4),round(y,4)
            if key not in used:
                used.add(key)
                b.box((x,y,z+.084),(.275,.28,.17),p.stone,yaw=yaw)
                b.box((x,y,z+.425),(.208,.215,.65),p.stone,yaw=yaw)
                b.box((x,y,z+.756),(.255,.262,.115),p.stone,yaw=yaw)
                b.box((x,y,z+.815),(.224,.235,.053),p.stone,yaw=yaw)
                b.lathe(x,y,((.139,z+.837),(.129,z+.867),(.132,z+.894),(.106,z+.939),(.053,z+.955)),
                        p.stone,sides=12)
                if banana_leaf:
                    for a in range(4):
                        u=a*math.pi/2+yaw
                        b.path([(x+math.cos(u)*r,y+math.sin(u)*r,z+h) for r,h in
                                ((.079,.793),(.126,.837),(.128,.886),(.065,1.016))],.014,p.stone,sides=6)
            if j==count or span<.57:
                continue
            x,y=x+dx*span/2,y+dy*span/2
            w=span-.225
            frame=box(-w/2,z+.097,w/2,z+.728)
            airy=Polygon([(-.40*w,z+.589),(-.35*w,z+.604),(.35*w,z+.604),(.40*w,z+.589),
                          (.40*w,z+.507),(.35*w,z+.476),(.27*w,z+.482),(.21*w,z+.435),
                          (.20*w,z+.415),(-.20*w,z+.415),(-.21*w,z+.435),(-.27*w,z+.482),
                          (-.35*w,z+.476),(-.40*w,z+.507)]).buffer(.016,quad_segs=5)
            b.box((x,y,z+.774),(span+.010,.171,.085),p.stone,yaw=yaw)
            section=Batch()
            arch_mesh(section,frame.difference(airy),.142,p.stone)
            b.add([(x+u*dx-v*dy,y+u*dy+v*dx,q) for u,v,q in section.v],section.f,p.stone)
            for i in range(3):
                off=(i-1)*w*.21
                for side in (-1,1):
                    for scale in (1.,.66):
                        petals=[(x+dx*(off+scale*(.087+.014*math.cos(5*t))*math.cos(t))+side*dy*.075,
                                 y+dy*(off+scale*(.087+.014*math.cos(5*t))*math.cos(t))-side*dx*.075,
                                 z+.239+scale*(.074+.010*math.cos(5*t))*math.sin(t))
                                for t in (j*math.tau/40 for j in range(41))]
                        b.path(petals,.006 if scale==1 else .0041,p.stone,sides=5)


def build_bridge(study,plan,target,p):
    group=collection(study.name+' · 单券石桥与踏步',target)
    y0,y1=plan.bank_y
    middle=(y0+y1)/2
    arch_span=y1-y0-1.42
    crown=.31
    width=WIDTH+.39
    # Section coordinates run along the crossing. Rotate the extrusion east-west.
    section=Polygon([(y0-.50,-2.1),(y1+.53,-2.1),(y1+.53,DECK-.06),
                     (y0+1.22,DECK-.06),(y0+.22,PORCH-.063),(y0-.50,PORCH-.063)])
    arch=arch_section(middle,arch_span,crown,bottom=-2.2,rise=1.19)
    b=Batch(plan.world(),plan.yaw+math.pi/2)
    arch_mesh(b,section.difference(arch),width,p.understone)
    b.finish(study.name+' · 单个贯通石拱券',group,properties={
        'mapped_bank_span_m':y1-y0,'arch_clear_span_m_estimated':arch_span,'openings':1})
    b=plan.batch()
    a_end=plan.front_y+1.15
    start=y0+.39
    end=y0+1.28
    far=max(y1+.43,plan.main_y+4.46)
    b.solid_xy(box(-width/2,a_end,width/2,y0+.20),-.25,PORCH-.036,p.stone)
    laid_pavers(b,box(-width/2+.015,a_end+.01,width/2-.015,start),PORCH,p)
    b.solid_xy(box(-width/2,end-0.014,width/2,far),DECK-.21,DECK-.058,p.stone)
    laid_pavers(b,box(-width/2+.015,end,width/2-.015,far),DECK,p)
    if far>y1+.43:
        b.solid_xy(box(-width/2,y1+.43,width/2,far),0,DECK-.055,p.understone)
    raised_stair(b,start,end,0,3.12,PORCH,DECK,2,p)
    raised_stair(b,far+.86,far,0,3.20,PORCH,DECK,2,p)
    b.solid_xy(box(-2.28,far+.856,2.28,far+1.73),.022,PORCH-.058,p.stone)
    laid_pavers(b,box(-2.28,far+.86,2.28,far+1.73),PORCH,p)
    raised_stair(b,far+2.51,far+1.73,0,3.20,.034,PORCH,2,p)
    # Short end railings leave only the centre bays open at the two stairs.
    for yy in (end+.015,far-.06):
        for side in (-1,1):
            stone_rail(b,LineString(((side*(width/2-.203),yy),(side*1.765,yy))),DECK,p,
                       banana_leaf=study.caisson=='dragons')
    b.solid_xy(box(-width/2,a_end-.40,width/2,a_end),.028,PORCH-.040,p.stone)
    raised_stair(b,a_end-.97,a_end,0,3.2,.031,PORCH,2,p)
    for x in (-width/2+.13,width/2-.13):
        stone_rail(b,LineString(((x,end),(x,far-.06))),DECK,p,banana_leaf=study.caisson=='dragons')
    # Wedge voussoirs frame the same physical opening on both spandrels.
    for x in (-width/2-.011,width/2+.011):
        for i in range(31):
            a,c=math.pi*(i+.024)/31,math.pi*(i+.976)/31
            line=[(x,middle+(arch_span/2+v)*math.cos(t),crown-1.19+(1.19+v)*math.sin(t))
                  for v,t in ((.006,a),(.006,c),(.276,c),(.276,a))]
            b.add(line,[tuple(range(4)) if x<0 else (3,2,1,0)],p.stone)
    b.finish(study.name+' · 青白石面砖、两步台阶与透雕栏板',group)
    return group


def pond_landscape(study,plan,target,p):
    group=collection(study.name+' · 方池、池壁及岸栏',target)
    pond=plan.pond
    stone,wet=plan.batch(),plan.batch()
    wet.solid_xy(pond.buffer(-.10,join_style=2),WATER-.047,WATER,p.water,bottom=False)
    wet.finish(study.name+' · 地图池口与独立水面',group,properties={
        'source_osm_way':study.pond,'mapped_water_surface_area_m2':pond.area})
    rim=pond.buffer(.25,join_style=2).difference(pond.buffer(-.10,join_style=2))
    stone.solid_xy(rim,-1.27,.10,p.understone)
    stone.solid_xy(pond,-1.39,-1.258,p.understone)
    stone.solid_xy(pond.buffer(.34,join_style=2).difference(pond.buffer(-.13,join_style=2)),.10,.224,p.stone)
    avoid=box(-4.04,plan.bank_y[0]-.68,4.04,plan.bank_y[1]+.68)
    edge=pond.buffer(.125,join_style=2).exterior.difference(avoid)
    for line in edge.geoms if hasattr(edge,'geoms') else (edge,):
        if line.geom_type=='LineString':
            stone_rail(stone,line,.222,p,banana_leaf=study.caisson=='dragons',interval=1.66)
    # Discrete coping joint blocks are visible from the footpath.
    line=pond.exterior
    count=math.ceil(line.length/.73)
    for j in range(count):
        a,c=line.interpolate(j*line.length/count),line.interpolate((j+.985)*line.length/count)
        if a.distance(c)<.04:
            continue
        dx,dy=c.x-a.x,c.y-a.y
        stone.box(((a.x+c.x)/2,(a.y+c.y)/2,.231),(a.distance(c),.286,.047),p.stone,yaw=math.atan2(dy,dx))
    if study.caisson=='flowers':
        for x in (-8.05,6.62):
            cut=pond.intersection(LineString(((x,-35),(x,35))))
            y=cut.bounds[1]+.078
            stone.ellipsoid((x,y,-.265),(.183,.19,.199),p.stone,sides=16,rings=9)
            stone.ellipsoid((x,y+.128,-.328),(.107,.115,.088),p.stone,sides=13,rings=7)
            for side in (-1,1):
                cloud(stone,(x+side*.096,y+.14,-.241),.107,p.understone,facing='front')
                stone.ellipsoid((x+side*.073,y+.155,-.231),(.03,.026,.024),p.stone,sides=8,rings=5)
            stone.ellipsoid((x,y+.223,-.35),(.056,.009,.025),p.black,sides=10,rings=6)
    stone.finish(study.name+' · 沿原始池岸的压顶石与望柱',group)
    if study.caisson=='flowers':
        lotus(plan,group,p)
    return group


def lotus(plan,target,p):
    b=plan.batch()
    rng=random.Random(42353096)
    positions=[(-8.4,-2.0),(-7.4,1.6),(-5.7,-.58),(5.9,1.15),(7.5,-1.55),(9.12,1.76)]
    for i,(x,y) in enumerate(positions):
        for j in range(8):
            xx=x+rng.uniform(-.79,.79)
            yy=y+rng.uniform(-.79,.79)
            if not plan.pond.buffer(-.36).contains(Point(xx,yy)):
                continue
            z=WATER+rng.uniform(.041,.65)
            r=rng.uniform(.145,.335)
            b.rod((xx,yy,WATER-.23),(xx,yy,z),.009,p.lotus_green[0],sides=6)
            verts=[(xx,yy,z-.06)]
            verts.extend((xx+r*math.cos(a),yy+r*math.sin(a),z+.025+r*.16*math.sin(a*3))
                         for a in (q*math.tau/22 for q in range(22)))
            b.add(verts,[(0,k+1,(k+1)%22+1) for k in range(22)],p.lotus_green[(j+i)%3],smooth=True)
            if j in (2,6):
                top=z+.24
                b.rod((xx,yy,z-.17),(xx+.04,yy+.048,top),.013,p.lotus_green[1],sides=8)
                for k in range(11):
                    a=k*math.tau/11
                    b.ellipsoid((xx+.04+.069*math.cos(a),yy+.048+.069*math.sin(a),top+.055),
                                (.092,.025,.069),p.lotus_pink,sides=8,rings=6,yaw=a)
    b.finish('浮碧亭 · 夏季荷叶与花瓣',target,properties={'season':'Documented summer lotus; placement and biological forms interpreted.'})


def transfer(out,part,x,y,yaw):
    c,s=math.cos(yaw),math.sin(yaw)
    verts=[(x+u*c-v*s,y+u*s+v*c,z) for u,v,z in part.v]
    groups={}
    for face,slot,smooth in zip(part.f,part.mi,part.sm):
        groups.setdefault((slot,smooth),[]).append(face)
    for (slot,smooth),faces in groups.items():
        indices=list(dict.fromkeys(i for face in faces for i in face))
        index={old:i for i,old in enumerate(indices)}
        out.add([verts[i] for i in indices],[(tuple(index[i] for i in face)) for face in faces],
                part.mats[slot],smooth=smooth)


def flower(b,x,y,z,r,material,centre):
    for j in range(8):
        a=j*math.tau/8
        b.ellipsoid((x+.63*r*math.cos(a),y+.63*r*math.sin(a),z),
                    (.42*r,.184*r,.071*r),material,sides=8,rings=4,yaw=a)
    b.ellipsoid((x,y,z-.026*r),(.212*r,.212*r,.118*r),centre,sides=10,rings=4)


def panel_motif(b,x,y,z,w,h,p,style):
    # Fine, weathered paint details sit slightly proud of the timber substrate.
    edge=[(-.48,0),(-.37,-.41),(.37,-.41),(.48,0),(.37,.41),(-.37,.41),(-.48,0)]
    for scale,material in ((1.,p.cream),(.87,p.faded_teal),(.73,p.giltpaint)):
        b.path([(x+i*w*scale,y,z+j*h*scale) for i,j in edge],.0056,material,sides=5)
    for side in (-1,1):
        for q in range(4):
            off=side*(w*.18+q*.066*w)
            cloud(b,(x+off,y+.010,z+(.058*h if q%2==0 else -.058*h)),
                  h*.39,p.cream,rotation=side*q*.86)
    if style=='flowers':
        coords=[(x+.15*h*math.cos(t),y-.008,z+.15*h*math.sin(t)) for t in
                (i*math.tau/31 for i in range(32))]
        b.path(coords,.0065,p.giltpaint,sides=5)


def painted_span(frame,painted,a,c,z,p,style):
    x,y=(a[0]+c[0])*.5,(a[1]+c[1])*.5
    w=math.dist(a,c)
    yaw=math.atan2(c[1]-a[1],c[0]-a[0])
    work=Batch()
    work.box((0,0,z+.20),(w,.34,.34),p.faded_teal)
    work.box((0,0,z+.511),(w,.286,.25),p.fascia)
    work.box((0,0,z+.925),(w,.374,.40),p.faded_blue)
    for yface in (-.189,.189):
        direction=-1 if yface<0 else 1
        for h in (.065,.332,.589,.770,1.075):
            work.box((0,yface,z+h),(w-.071,.021,.026),p.faded_teal)
        motif=Batch()
        for n in (-1,0,1):
            panel_motif(motif,n*w*.30,-.177,z+.21,w*.28,.246,p,style)
            panel_motif(motif,n*w*.30,-.203,z+.935,w*.28,.33,p,style)
        if direction>0:
            for face,slot,smooth in zip(motif.f,motif.mi,motif.sm):
                work.face([(-motif.v[i][0],-motif.v[i][1],motif.v[i][2]) for i in face],
                          motif.mats[slot],smooth=smooth)
        else:
            transfer(work,motif,0,0,0)
    count=3 if w>2.8 else 2
    for i in range(count):
        u=w*(i+.5)/count-w/2
        span=w/count-.12
        # Each hua board has genuine pierced areas in its cloud scrolls.
        shape=box(u-span/2,z+.620,u+span/2,z+.763)
        for k in range(3):
            o=u+(k-1)*span*.27
            hole=Point(o,z+.695).buffer(.041,quad_segs=6)
            shape=shape.difference(affinity.scale(hole,1.56,.8,origin=(o,z+.695)))
            cloud(work,(o,-.070,z+.700),.16,p.cream)
        arch_mesh(work,shape,.119,p.faded_teal)
        work.box((u,-.089,z+.625),(span,.053,.026),p.fascia)
        work.box((u,-.089,z+.763),(span,.053,.028),p.fascia)
    transfer(painted,work,x,y,yaw)
    for i in range(2):
        u=(i-.5)*w*.48
        cx,cy=x+u*math.cos(yaw),y+u*math.sin(yaw)
        frame.box((cx,cy,z+1.127),(.232,.214,.092),p.faded_blue,yaw=yaw)
        frame.box((cx,cy,z+1.212),(.504,.235,.122),p.faded_teal,yaw=yaw)
        for off in (-.174,.174):
            frame.box((cx+off*math.cos(yaw),cy+off*math.sin(yaw),z+1.295),
                      (.137,.224,.069),p.fascia,yaw=yaw)
    frame.box((x,y,z+1.411),(w,.264,.269),p.door,yaw=yaw)


def post_base(b,x,y,z,p):
    b.box((x,y,z+.041),(.57,.56,.087),p.stone)
    b.lathe(x,y,((.274,z+.076),(.263,z+.094),(.24,z+.128),(.223,z+.157),(.226,z+.19)),p.stone,sides=28)


def seat(b,a,c,z,p,backrest):
    length=math.dist(a,c)
    yaw=math.atan2(c[1]-a[1],c[0]-a[0])
    x,y=(a[0]+c[0])/2,(a[1]+c[1])/2
    work=Batch()
    for u in (-length*.32,length*.32):
        for zh,w,h in ((.069,.265,.135),(.172,.212,.107),(.28,.286,.123),(.369,.30,.071)):
            work.box((u,0,z+zh),(w,.315,h),p.stone)
    work.box((0,0,z+.429),(length,.392,.070),p.fascia)
    if backrest:
        work.box((0,.152,z+.849),(length,.081,.072),p.fascia)
        for j in range(1,13):
            u=length*(j/13-.5)
            work.path([(u,.117,z+.454),(u,.139,z+.568),(u,.192,z+.705),(u,.158,z+.821)],
                      .027,p.fascia,sides=8)
    transfer(b,work,x,y,yaw)


def build_frame(study,plan,target,p):
    group=collection(study.name+' · 方柱、梁枋和坐凳',target)
    main_s,main_n=plan.main_y-4,plan.main_y+4
    porch_front=plan.front_y+1.49
    main=[(x,plan.main_y+y) for x in POSTS for y in POSTS if abs(x)==4 or abs(y)==4]
    porch=[(x,porch_front) for x in POSTS]
    frame,painted,seatwork=plan.batch(),plan.batch(),plan.batch()
    for layout,z,eave in ((main,DECK,MAIN_EAVE),(porch,PORCH,ANNEX_EAVE)):
        for idx,(x,y) in enumerate(layout,1):
            col=plan.batch()
            post_base(col,x,y,z,p)
            col.box((x,y,(z+.16+eave-1.36)*.5),(.395,.405,eave-1.36-z-.16),p.red)
            col.box((x,y,eave-1.275),(.427,.436,.22),p.faded_teal)
            col.box((x,y,eave-1.127),(.457,.460,.076),p.faded_blue)
            col.finish(f'{study.name} · {"亭身" if layout is main else "抱厦"}方柱 {idx:02d}',group,
                       properties={'component':'square_column','post_x_local_m':x,'post_y_local_m':y,
                                   'dimension_basis':'Photo interpretation; 8 m pavilion span is published.'})
    for a,c in zip(POSTS,POSTS[1:]):
        for y in (main_s,main_n):
            painted_span(frame,painted,(a,y),(c,y),MAIN_EAVE-1.65,p,study.caisson)
        for x in (-4,4):
            painted_span(frame,painted,(x,plan.main_y+a),(x,plan.main_y+c),MAIN_EAVE-1.65,p,study.caisson)
        painted_span(frame,painted,(a,porch_front),(c,porch_front),ANNEX_EAVE-1.52,p,study.caisson)
    for x in (-4,4):
        painted_span(frame,painted,(x,porch_front),(x,main_s),ANNEX_EAVE-1.52,p,study.caisson)
        for a,c in zip(POSTS,POSTS[1:]):
            seat(seatwork,(x*.934,plan.main_y+a+.23),(x*.934,plan.main_y+c-.23),DECK,p,True)
    for side in (-1,1):
        seat(seatwork,(side*1.80,porch_front+.16),(side*3.77,porch_front+.16),PORCH,p,False)
    frame.finish(study.name+' · 麻叶形斗栱与檐枋承托',group)
    painted.finish(study.name+' · 彩画梁枋、透雕华板',group)
    seatwork.finish(study.name+' · 抱厦石脚坐凳与桥侧靠背',group)
    return porch_front


def enamel_plaque(study,plan,y,target,p):
    key='fubi' if study.caisson=='flowers' else 'chengrui'
    texture=Path(__file__).parent/'textures'/f'garden_plaque_{key}.jpg'
    z=3.714
    width,height=.447,.832
    b=plan.batch()
    # Lobe shape of the freestanding red lacquer frame, with flared lower feet.
    half=[(0,.615),(.128,.608),(.209,.564),(.267,.516),(.313,.511),(.378,.572),
          (.456,.598),(.549,.573),(.616,.530),(.658,.467),(.620,.398),(.514,.370),
          (.430,.399),(.400,.342),(.411,.280),(.363,.221),(.409,.103),(.435,-.044),
          (.427,-.180),(.389,-.278),(.377,-.357),(.439,-.463),(.460,-.546),
          (.411,-.664),(.353,-.692),(.279,-.579),(.239,-.505),(.158,-.525),(0,-.550)]
    outline=[(u*.88,z+v) for u,v in half]
    outline.extend((-u*.88,z+v) for u,v in reversed(half[1:-1]))
    solid=Batch()
    arch_mesh(solid,Polygon(outline),.095,p.fascia)
    transfer(b,solid,0,y,0)
    def front(u,v):
        return u,y-.058-(v-z)*.185,v
    # Tilt the solid back to the photographed mounting angle.
    b.v=[(u,v-(w-z)*.185,w) for u,v,w in b.v]
    b.path([front(*q) for q in (*outline,outline[0])],.0103,p.giltpaint,sides=7)
    for side in (-1,1):
        for zz in (-1,1):
            b.path([front(side*u,z+zz*v) for u,v in ((.224,.416),(.327,.520),(.368,.430),(.335,.344),(.294,.358))],
                   .0105,p.giltpaint,sides=7)
    uv=[(0,0),(1,0),(1,1),(0,1)]
    coords=[front(u,z+v) for u,v in ((-width/2,-height/2),(width/2,-height/2),(width/2,height/2),(-width/2,height/2))]
    material=p.cobalt
    if texture.is_file():
        material=bpy.data.materials.new(study.name+' · 实拍满汉匾心');material.use_nodes=True
        material.diffuse_color=p.cobalt.diffuse_color
        node=material.node_tree.nodes.new('ShaderNodeTexImage')
        node.image=bpy.data.images.load(str(texture),check_existing=True)
        node.image['source_reference']=study.photographs[2 if key=='fubi' else 1]
        bsdf=material.node_tree.nodes.get('Principled BSDF')
        material.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value=.50
    b.face(coords,material,uv=uv)
    b.path([(x,d-.005,w) for x,d,w in (*coords,coords[0])],.016,p.giltpaint,sides=8)
    b.finish(study.name+' · 漆木挂匾与满汉匾心',target,
             properties={'photo_panel':texture.is_file(),'photo_source':study.photographs[2 if key=='fubi' else 1]})
    if not texture.is_file():
        font=Path(os.environ.get('PALACE_CJK_FONT','C:/Windows/Fonts/simkai.ttf'))
        if font.is_file():
            glyphs=bpy.data.fonts.load(str(font),check_existing=True)
            for i,char in enumerate(study.name):
                curve=bpy.data.curves.new('匾字 '+char,'FONT')
                curve.body=char;curve.font=glyphs;curve.size=.235
                curve.align_x='CENTER';curve.align_y='CENTER';curve.extrude=.006
                obj=bpy.data.objects.new(study.name+' · '+char,curve)
                target.objects.link(obj)
                x,dy,height_z=front(0,z+.24-i*.242)
                obj.location=plan.world(x,dy-.010,height_z)
                obj.rotation_euler=(math.pi/2+.183,0,plan.yaw)
                curve.materials.append(p.giltpaint)
                bpy.context.view_layer.update()
                object_to_mesh(obj)


def ring_outline(radius,n=8):
    return [(radius*math.cos(math.pi/8+math.tau*i/n),radius*math.sin(math.pi/8+math.tau*i/n)) for i in range(n)]


def ceiling_tile(b,x,y,z,w,d,p,style,index):
    b.box((x,y,z+.042),(w+.021,d+.021,.085),p.faded_teal)
    for delta,material in ((.048,p.faded_blue),(.079,p.fascia),(.112,p.faded_teal)):
        b.box((x,y,z-.002-(delta-.048)*.07),(w-2*delta,d-2*delta,.020),material)
    radius=min(w,d)
    if style=='flowers':
        flower(b,x,y,z-.023,radius*.231,(p.cream,p.fascia,p.giltpaint)[index%3],p.giltpaint)
        for side in (-1,1):
            b.path([(x,y,z-.023),(x+side*w*.18,y+d*.116,z-.023),(x+side*w*.235,y-d*.10,z-.023)],
                   .007,p.faded_teal,sides=5)
    else:
        rr=[(x+.26*w*math.cos(a),y+.245*d*math.sin(a),z-.025) for a in (i*math.tau/40 for i in range(41))]
        b.path(rr,.0065,p.giltpaint,sides=5)
        # The motif is sized as a painted roundel; the main relief is separate.
        for k in (-1,1):
            cloud(b,(x+k*.063,y+k*.041,z-.023),radius*.19,p.giltpaint,facing='ceiling',rotation=k*1.4)
        b.path([(x-.13*w+u*.26*w,y+.052*math.sin(u*math.tau*1.15),z-.027) for u in (i/22 for i in range(23))],
               .0093,p.giltpaint,sides=6)


def dragon_relief(b,y,z,side,p):
    """A carved coiled body, with joints and raised scales visible from below."""
    from mathutils import Vector
    from mathutils.geometry import interpolate_bezier
    control=[(-.095,-.738),(-.48,-.629),(-.61,-.422),(-.44,-.29),(-.253,-.414),
             (-.151,-.34),(-.279,-.111),(-.56,-.047),(-.593,.227),(-.46,.475),
             (-.262,.432),(-.221,.195)]
    points=[Vector((x*side,y+v*side,z-.084)) for x,v in control]
    pp=[]
    for i,(a,c) in enumerate(zip(points,points[1:])):
        pre=points[max(0,i-1)]
        post=points[min(len(points)-1,i+2)]
        pp+=interpolate_bezier(a,a+(c-pre)/6,c-(post-a)/6,c,9)[:-1]
    pp.append(points[-1])
    radii=[];sides=12;verts=[];faces=[]
    for i,q in enumerate(pp):
        tangent=(pp[min(len(pp)-1,i+1)]-pp[max(0,i-1)]).normalized()
        normal=Vector((-tangent.y,tangent.x,0))
        r=.012+.063*math.sin(min(1.,i/(len(pp)*.68))*math.pi/2)
        radii.append((r,normal,tangent))
        for j in range(sides):
            a=j*math.tau/sides
            verts.append(tuple(q+normal*(r*math.cos(a))-Vector((0,0,r*.66*math.sin(a)))))
        if i:
            faces.extend(((i-1)*sides+j,(i-1)*sides+(j+1)%sides,i*sides+(j+1)%sides,i*sides+j) for j in range(sides))
    b.add(verts,faces,p.caisson_shade,smooth=True)
    for i in range(5,len(pp)-4,2):
        r,n,t=radii[i]
        q=pp[i]
        for j in (-1,0,1):
            tip=q+n*(r*j*.53)-Vector((0,0,r*(.608-.17*abs(j))))
            b.path([tip+n*(r*.32*math.cos(k*math.pi/8))+t*(r*.29*math.sin(k*math.pi/8))
                    for k in range(9)],.0041,p.caisson_gilt,sides=5)
        b.path([q+n*(r*.61*math.sin(k*math.pi/12))+t*(r*.72*math.cos(k*math.pi/12))-
                Vector((0,0,r*.165)) for k in range(13)],.0036,p.caisson_gilt,sides=5)
    for i,s in ((24,1),(42,-1),(58,1),(75,-1)):
        n=radii[i][1]*s;t=radii[i][2]
        start=pp[i]
        elbow=start+n*.101-t*.041
        wrist=elbow+n*.055+t*.062
        b.path([start,elbow,wrist],.026,p.caisson_shade,sides=10)
        for k in (-1,0,1,2):
            b.path([wrist,wrist+n*.037+t*k*.023,wrist+n*.062+t*(k*.034-.014)],.011,p.caisson_gilt,sides=7)
    x,x_y=points[-1].x,points[-1].y
    def v(u,v,h):
        return (x+u*side,x_y+v*side,z-h)
    b.ellipsoid(v(0,.012,.11),(.120,.094,.079),p.caisson_shade,sides=24,rings=11)
    b.ellipsoid(v(.069,-.045,.143),(.108,.053,.044),p.caisson_gilt,sides=20,rings=11,yaw=-.42)
    b.ellipsoid(v(.052,-.103,.105),(.078,.030,.023),p.caisson_shade,sides=18,rings=8)
    for k in (0,1,2):
        b.ellipsoid(v(.083+k*.020,-.092-k*.008,.128),(.011,.012,.021),p.cream,sides=10,rings=6)
    for s in (-1,1):
        b.ellipsoid(v(s*.061,.016,.171),(.035,.022,.025),p.caisson_gilt,sides=15,rings=8,yaw=s*.48)
        b.ellipsoid(v(s*.057,.008,.188),(.009,.010,.008),p.caisson_shade,sides=13,rings=7)
        b.path([v(s*.034,.024,.182),v(s*.054,.044,.199),v(s*.093,.027,.176)],.012,p.caisson_gilt,sides=7)
        b.path([v(s*.037,.068,.14),v(s*.091,.144,.136),v(s*.092,.179,.105),v(s*.142,.217,.082)],
               .017,p.caisson_gilt,sides=8)
        b.path([v(.103,-.050,.164),v(.134,-.013,.174),v(.162,.055*s,.158),v(.201,.077*s,.13)],
               .009,p.caisson_gilt,sides=6)
        for i in range(5):
            k=i*.019
            b.path([v(s*(.064+k),.045-k,.133),v(s*(.116+k),.083,.098),v(s*(.149+k),.101,.057)],
                   .014,p.caisson_gilt,sides=7)
        for i in range(4):
            b.path([v(s*.079,.035-i*.016,.132),v(s*.132,.021-i*.021,.162),v(s*.144,-.038-i*.017,.140)],
                   .008,p.caisson_gilt,sides=6)


def caisson_photo():
    file=Path(__file__).parent/'references'/'nov21_exterior_photos'/'chengrui_caisson.jpg'
    if not file.is_file():
        return None
    material=bpy.data.materials.new('澄瑞亭 · 故宫仰拍对位的八方井壁')
    material.use_nodes=True
    nodes=material.node_tree.nodes; links=material.node_tree.links
    node=nodes.new('ShaderNodeTexImage')
    node.image=bpy.data.images.load(str(file),check_existing=True)
    node.image['source_reference']=CEILING_PHOTO
    surface=nodes.get('Principled BSDF')
    links.new(node.outputs['Color'],surface.inputs['Base Color'])
    bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.31;bump.inputs['Distance'].default_value=.025
    links.new(node.outputs['Color'],bump.inputs['Height']);links.new(bump.outputs['Normal'],surface.inputs['Normal'])
    surface.inputs['Roughness'].default_value=.68
    material.diffuse_color=(.30,.163,.079,1)
    return material


def build_caisson(study,plan,porch_front,target,p):
    group=collection(study.name+' · 八方双龙藻井与井口天花',target)
    tiles=plan.batch();trim=plan.batch();relief=plan.batch()
    y=plan.main_y
    step=.807
    z=CAISSON_EDGE
    # A central clear opening with separate corner panels and an octagonal well.
    for i in range(-4,5):
        for j in range(-4,5):
            if abs(i)<=1 and abs(j)<=1:
                continue
            ceiling_tile(tiles,i*step,y+j*step,z,step-.038,step-.038,p,study.caisson,i+j*3)
    for i in range(-5,5):
        u=(i+.5)*step
        for q in (-1,1):
            trim.box((q*step*4.50,y+u,z-.047),(.227,step+.010,.108),p.fascia)
            trim.box((u,y+q*step*4.50,z-.047),(step+.010,.227,.108),p.fascia)
    well=Polygon(ring_outline(1.305))
    patch=box(-step*1.5,-step*1.5,step*1.5,step*1.5).difference(well)
    tiles.solid_xy(affinity.translate(patch,0,y),z,z+.109,p.faded_blue)
    for a in (math.pi/4,math.pi*3/4,math.pi*5/4,math.pi*7/4):
        flower(trim,1.465*math.cos(a),y+1.465*math.sin(a),z-.018,.125,p.giltpaint,p.cream)

    photo=caisson_photo() if study.caisson=='dragons' else None
    sections=((1.305,z),(1.258,z+.101),(1.153,z+.242),(1.096,z+.304),(1.015,z+.477),(.995,CAISSON_CROWN))
    for idx,((outer,a),(inner,c)) in enumerate(zip(sections,sections[1:])):
        low=ring_outline(outer); high=ring_outline(inner)
        for k in range(8):
            n=(k+1)%8
            u,v=low[k],low[n]
            tx,ty=v[0]-u[0],v[1]-u[1]
            corners=(u,high[k],high[n],v)
            tiles.face([(x,y+v0,h) for (x,v0),h in zip(corners,(a,c,c,a))],
                       (photo or p.ochre_wood) if idx>0 else p.faded_teal,
                       uv=[(.50+x*.295,.506+v0*.391) for x,v0 in corners] if photo else None)
            trim.rod((u[0],y+u[1],a-.01),(v[0],y+v[1],a-.01),.026 if idx==0 else .017,
                     p.giltpaint,sides=8)
            for spot in ((.24,.75) if photo else (.17,.37,.58,.79)):
                x0=u[0]+tx*spot; y0=u[1]+ty*spot
                q=inner/outer
                cloud(relief,(x0*(1+q)/2,y+y0*(1+q)/2,(a+c)/2-.021),.105,p.ochre_wood,
                      facing='ceiling',rotation=math.atan2(ty,tx)+idx*.4)
    for r,h,mat in ((.974,CAISSON_CROWN-.026,p.faded_blue),(.924,CAISSON_CROWN-.037,p.caisson_gilt),
                    (.789,CAISSON_CROWN-.043,p.caisson_shade)):
        trim.rod((0,y,h+.036),(0,y,h),r,mat,sides=96)
    for side in (-1,1):
        dragon_relief(relief,y,CAISSON_CROWN-.051,side,p)
    relief.ellipsoid((0,y,CAISSON_CROWN-.123),(.074,.073,.043),p.caisson_gilt,sides=24,rings=11)
    for i in range(40):
        a=i*math.tau/40
        r=(.166,.594,.714)[i%3]
        cloud(relief,(r*math.cos(a),y+r*math.sin(a),CAISSON_CROWN-.069),.119 if i%3 else .107,p.caisson_gilt,
              facing='ceiling',rotation=a*1.24)
    # The lower porch has its own square grid and ends at the main front beam.
    y0,y1=porch_front+.23,plan.main_y-4.15
    rows=max(2,round((y1-y0)/.66));d=(y1-y0)/rows
    for row in range(rows):
        for i in range(-5,6):
            ceiling_tile(tiles,i*.684,y0+(row+.5)*d,4.181,.656,d-.026,p,study.caisson,row+i)
    tiles.finish(study.name+' · 井口天花、罩面与斜升井壁',group)
    trim.finish(study.name+' · 八方层叠缘枋与圆井',group)
    relief.finish(study.name+' · 两条独立蟠龙、宝珠和彩画小纹',group,properties={
        'reference':CEILING_PHOTO if study.caisson=='dragons' else study.museum,
        'dimension_basis':'Octagonal form and subjects documented; relief and paint dimensions interpreted.'})


def build_roof(study,plan,target,p):
    group=collection(study.name+' · 绿瓦黄剪边、卷棚和宝顶',target)
    width=max(9.83,plan.roof_width+.38)
    depth=9.77
    yellow=p.tiles[2]
    swept_roof(study.name+' 攒尖',group,p,origin=plan.world(0,plan.main_y),yaw=plan.yaw,
               width=width,depth=depth,eave=MAIN_EAVE,rise=MAIN_RISE,kind='pyramid',pitch=.234,tiles=True,
               green=True,detail=2,beasts=3,border_glaze=yellow,pyramid_finial=False,eave_lift=.42)
    y0=plan.front_y-.035
    y1=plan.main_y-3.39
    d=y1-y0;y=(y1+y0)/2
    swept_roof(study.name+' 抱厦卷棚',group,p,origin=plan.world(0,y),yaw=plan.yaw,
               width=width+.016,depth=d,eave=ANNEX_EAVE,rise=ANNEX_RISE,kind='juanpeng',pitch=.231,
               eave_lift=.14,green=True,detail=2,tiles=True,gable_ends=False,border_glaze=yellow)
    b=plan.batch()
    for side in (-1,1):
        x=side*width*.5
        profile=[]
        for i in range(53):
            v=d*(i/52-.5)
            t=1-abs(v)*2/d
            f=.10*t+.90*t**1.71
            if t>.72:
                m=(t-.72)/.28
                f=(2*m**3-3*m*m+1)*(.072+.90*.72**1.71)+(m**3-2*m*m+m)*(.1+.9*1.71*.72**.71)*.28-2*m**3+3*m*m
            h=ANNEX_EAVE+ANNEX_RISE*f+.14*(1-t)**2+.07*(1-t)**14
            profile.append((y+v,h))
        board=Batch()
        shape=Polygon([*profile,*[(u,z-.475-.12*abs((u-y)*2/d)) for u,z in reversed(profile)]])
        arch_mesh(board,shape,.115,p.fascia)
        transfer(b,board,x,0,math.pi/2)
        # These independent ceramic edge courses sit directly on the bargeboard.
        for off,r,mat in ((0,.066,p.giltpaint),(.077,.093,yellow),(.16,.055,p.ochre_wood)):
            b.path([(x,u,z+off) for u,z in profile],r,mat,sides=10)
        for j,(u,z) in enumerate(profile[1:-1:2]):
            b.rod((x-side*.074,u,z+.018),(x+side*.083,u,z+.018),.079,yellow,sides=12)
        for sign in (-1,1):
            for j in range(4):
                idx=3+j*3 if sign<0 else 49-j*3
                u,z=profile[idx]
                from architectural_roofs import ridge_guardian
                ridge_guardian(b,(x,u,z+.165),0,sign,.26,yellow,kind=j)
        # Recessed dark gable structure does not close the open space below it.
        x0=side*3.98
        b.box((x0,y,4.626),(.27,max(.1,d-2.12),.27),p.faded_teal)
        for i in range(-3,4):
            u=y+i*d*.098
            h=profile[min(52,max(0,round(52*(.5+(u-y)/d))))][1]
            if h>4.99:
                b.box((x0,u,(4.73+h-.25)/2),(.142,.139,h-4.98),p.door)
    b.finish(study.name+' · 朱红曲线博风、边瓦和脊兽',group)
    finial=plan.batch()
    z=MAIN_EAVE+MAIN_RISE
    finial.lathe(0,plan.main_y,((.42,z-.055),(.40,z+.065),(.354,z+.122),(.391,z+.175),(.359,z+.246),
                 (.269,z+.269),(.284,z+.325),(.323,z+.416),(.353,z+.54),(.357,z+.689),
                 (.321,z+.799),(.253,z+.879),(.129,z+.914),(.004,z+.933)),yellow,sides=48)
    for j in range(24):
        a=j*math.tau/24
        finial.ellipsoid((.378*math.cos(a),plan.main_y+.378*math.sin(a),z+.173),
                          (.038,.023,.032),p.ochre_wood,sides=9,rings=5,yaw=a)
    finial.finish(study.name+' · 琉璃葫芦式宝顶',group)


def build_pavilion(study,plan,target,p):
    group=collection(study.name+' · 石桥、木作与藻井',target)
    group['museum_source']=study.museum
    group['source_osm_building_way']=study.way
    group['source_osm_water_way']=study.pond
    group['documented_nominal_bay_span_m']=WIDTH
    build_bridge(study,plan,group,p)
    pond_landscape(study,plan,group,p)
    porch_front=build_frame(study,plan,group,p)
    build_roof(study,plan,group,p)
    build_caisson(study,plan,porch_front,group,p)
    enamel_plaque(study,plan,porch_front-.37,group,p)
    return group
