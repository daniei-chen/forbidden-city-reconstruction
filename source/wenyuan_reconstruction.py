"""Wenyuan Ge: documented column grid, a real mezzanine, and two roof levels.

Geometry uses metres and the 1988 survey as printed in Palace Museum Journal,
1993, pp.35-44. OSM supplies placement only. Missing heights, ornament depths,
individual book sizes and cabinet positions remain explicitly interpreted.
"""
from pathlib import Path
from types import SimpleNamespace
import json
import math

import bpy
from mathutils import Vector
from shapely.geometry import Polygon, box

from mesh_tools import Batch, collection
from palace_materials import paint, roof_shader
from architectural_roofs import swept_roof
from palace_architecture import dougong,arch_block,stairs
from shapely.geometry import LineString,Point
from osm_site import Site, rectangle

ROOT=Path(__file__).resolve().parents[1]
REF='40478704'
SPANS=(2.10,5.68,5.66,8.22,5.69,5.66)
WIDTH=sum(SPANS)
DEPTH=14.77
XS=[-WIDTH/2]
for span in SPANS:
    XS.append(XS[-1]+span)
YS=(-7.385,-5.235,-3.115,3.115,5.235,7.385)
MAIN=(XS[3]+XS[4])/2
FLOOR=.68  # Site elevation/terrace height is not measured in the cited paper.
MEZZ=FLOOR+4.97
UPPER=FLOOR+8.05  # Published floor underside 7.83 + interpreted 0.22 floor thickness.
UPPER_EAVE=FLOOR+12.85
RISE=4.45
LOW_EAVE=FLOOR+6.28
LOW_RISE=7.6
LOW_STOP=.42
ROOF_WIDTH=36.75
ROOF_DEPTH=13.15
PAPER='刘榕, 从实测谈文渊阁结构与艺术特点, 故宫博物院院刊1993年第3期, printed pp.35-44; survey 1988'


def materials(base):
    p=SimpleNamespace(**base.__dict__)
    p.lacquer=paint('文渊阁 · 沉绿漆柱与抱框',(.018,.085,.045),second=(.042,.141,.076),rough=.55,bump=.0015,grain=95,coat=.08)
    p.wood=paint('文渊阁 · 褐黑槅扇',(.027,.020,.012),second=(.070,.052,.027),rough=.60,bump=.001,grain=80)
    p.cream=paint('文渊阁 · 栏杆白花与白椽',(.60,.57,.44),second=(.76,.73,.59),rough=.76,bump=.0005,grain=100)
    p.green_clay=bpy.data.materials.get('新校核 · 绿色琉璃瓦') or base.green_clay
    p.green=bpy.data.materials.get('新校核 · 绿瓦屋面') or base.green
    p.brick=paint('文渊阁 · 水磨澄泥青砖',(.115,.126,.123),second=(.195,.205,.188),rough=.83,bump=.0015,grain=135,brick=(.43,.095,.002,True))
    p.purple=paint('文渊阁 · 紫釉游龙',(.12,.032,.068),second=(.245,.077,.126),rough=.40,bump=.001,coat=.14)
    p.paper=paint('文渊阁 · 书函纸页',(.52,.43,.26),second=(.75,.65,.44),rough=.86,bump=.0002,grain=120)
    p.glass=bpy.data.materials.new('文渊阁 · 书橱护尘面板 / interpreted glazing')
    p.glass.use_nodes=True;p.glass.diffuse_color=(.12,.10,.07,.24)
    shader=p.glass.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value=(.72,.68,.58,1)
    shader.inputs['Transmission Weight'].default_value=1.
    shader.inputs['Roughness'].default_value=.19;shader.inputs['IOR'].default_value=1.48
    p.books=[paint('文渊阁 · 书函 '+str(i),c,rough=.82,bump=.0005,grain=100) for i,c in enumerate(((.075,.105,.095),(.085,.10,.15),(.19,.13,.07),(.11,.105,.075)))]
    p.floorwood=paint('文渊阁 · 楼板杉木',(.077,.047,.022),second=(.16,.108,.053),rough=.71,bump=.002,grain=85)
    p.wall=paint('文渊阁 · 室内浅色墙面',(.51,.47,.36),second=(.69,.65,.53),rough=.88,bump=.001,grain=110)
    p.bank=bpy.data.materials['17 · 石驳岸 / cut-stone revetment']
    p.roof=bpy.data.materials.get('新校核 · 黑瓦屋面') or roof_shader(
        '文渊阁 · 黑瓦屋面',(.016,.020,.019),(.044,.048,.042),(.009,.012,.010))
    p.tiles=[paint('文渊阁 · 黑釉筒板瓦 '+str(i),(.019+i*.004,.024+i*.004,.023+i*.003),second=(.040+i*.005,.047+i*.005,.041+i*.005),rough=.49,bump=.001,grain=110,coat=.10) for i in range(4)]
    p.door=p.wood
    p.red=p.lacquer
    p.blue=p.lacquer
    p.teal=p.lacquer
    p.giltpaint=p.cream
    p.darktile=p.tiles[0]
    return p


def hip_underside(x,y):
    """Clearance envelope at side framing; the end frames sit under the hip."""
    hw=ROOF_WIDTH/2;hd=ROOF_DEPTH/2
    t=1-abs(y)/hd
    if abs(x)>14.7:
        t=min(t,.38*(hw-abs(x))/(hw-14.7))
    t=max(0.,min(1.,t))
    return UPPER_EAVE+RISE*(.10*t+.90*t**1.71)-.26


def ring_rect(b,x,y,z,w,h,mat,thick=.035):
    for sign in (-1,1):
        b.box((x+sign*w/2,y,z),(thick,.055,h),mat)
        b.box((x,y,z+sign*h/2),(w,.055,thick),mat)


def lantern_panel(b,x,y,z,w,h,p,*,blind=False):
    """Open wooden lantern-pattern lattice; no photo used as a room backdrop."""
    b.box((x,y+.045,z+h*.22),(w,.10,h*.44),p.wood)
    if blind:
        b.box((x,y+.08,z+h*.70),(w,.075,h*.56),p.wood)
    ring_rect(b,x,y,z+h/2,w,h,p.wood,.055)
    for zz in (h*.41,h*.94):
        b.box((x,y-.015,z+zz),(w,.075,.055),p.wood)
    bottom=z+h*.45
    field_h=h*.46
    # Each lantern loop has a real opening and clipped connection bars.
    rows=max(1,round(field_h/.45));step=field_h/rows
    for i in range(rows):
        c=bottom+(i+.5)*step
        ring_rect(b,x,y-.025,c,w*.56,step*.70,p.wood,.026)
        for sign in (-1,1):
            b.box((x+sign*w*.37,y-.025,c),(w*.18,.04,.026),p.wood)
        if i<rows-1:
            for sign in (-1,1):
                b.box((x+sign*w*.14,y-.025,c+step*.5),(.024,.04,step*.34),p.wood)
    # Recessed panel mouldings below the open lattice.
    for j in range(2):
        ring_rect(b,x,y-.016,z+h*(.12+.16*j),w*.73,h*.12,p.lacquer,.019)


def balustrade(b,a,c,y,z,p,*,h=1.3):
    if c-a<.20:
        return
    for dz,hh in ((.10,.19),(.36,.10),(h-.05,.10)):
        b.box(((a+c)/2,y,z+dz),(c-a,.13,hh),p.lacquer)
    n=max(1,round((c-a)/.90));s=(c-a)/n
    for i in range(n):
        x=a+(i+.5)*s
        b.box((a+i*s,y,z+h/2),(.055,.12,h),p.lacquer)
        ring_rect(b,x,y-.077,z+.78,s*.81,.61,p.lacquer,.051)
        ring_rect(b,x,y-.086,z+.78,s*.43,.34,p.cream,.035)
        for sign in (-1,1):
            b.box((x+sign*s*.31,y-.085,z+.78),(s*.18,.045,.035),p.cream)
            b.box((x,y-.085,z+.78+sign*.25),(.035,.045,.16),p.cream)
    b.box((c,y,z+h/2),(.055,.12,h),p.lacquer)


def painted_strip_material():
    """Map an archival photo onto the actual beam, not across the whole building."""
    path=ROOT/'source/textures/wenyuan_actual_painted_beam.jpg'
    if not path.is_file():
        return None
    image=bpy.data.images.load(str(path),check_existing=True)
    image.pack()
    m=bpy.data.materials.new('文渊阁 · 2025院刊实拍额枋彩画')
    m.use_nodes=True
    m.diffuse_color=(.16,.16,.075,1)
    tex=m.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image
    uv=m.node_tree.nodes.new('ShaderNodeUVMap');uv.uv_map='Roof UV'
    m.node_tree.links.new(uv.outputs['UV'],tex.inputs['Vector'])
    bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.79
    m.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
    m['source']='Palace Museum Journal 2025 no.4, p.88, figure 1; cropped full beam photograph'
    return m


def add_beams(b,p,painted):
    for sign in (-1,1):
        for yy,zz in ((sign*7.385,FLOOR+5.48),(sign*5.235,FLOOR+11.95)):
            b.box((0,yy,zz-.20),(WIDTH,.34,.54),p.lacquer)
            for i,(a,c) in enumerate(zip(XS,XS[1:])):
                w=c-a-.25;z=zz-.20;y=yy+sign*.179
                if painted and i:
                    face=[(a+.125,y,z-.26),(c-.125,y,z-.26),(c-.125,y,z+.26),(a+.125,y,z+.26)]
                    if sign>0:
                        face.reverse()
                    b.face(face,painted,uv=[(0,0),(1,0),(1,1),(0,1)])
                # Hanging meizi: green framework with actual white-flower voids.
                n=max(1,round(w/.62));s=w/n
                for j in range(n):
                    x=a+.125+(j+.5)*s
                    ring_rect(b,x,y,z-.60,s*.88,.34,p.lacquer,.032)
                    ring_rect(b,x,y+sign*.012,z-.60,s*.46,.18,p.cream,.023)
                for edge in (a+.33,c-.33):
                    pts=[(edge,y,z-.40),(edge,y,z-.85),(edge+(.34 if edge<a+1 else -.34),y,z-.40)]
                    b.path(pts,.042,p.lacquer,sides=6)
            # Intermediate bracket sets reflect the unusually dense survey layout.
            for a,c in zip(XS,XS[1:]):
                n=max(1,round((c-a)/.82))
                for j in range(n):
                    x=a+(j+.5)*(c-a)/n
                    dougong(b,x,yy,zz+.14,p,scale=.52 if abs(yy)>6 else .60,direction=(0,sign))
        for z0 in (MEZZ,UPPER):
            b.box((0,sign*5.235,z0-.23),(WIDTH,.30,.40),p.lacquer)
    for x in XS:
        for yy in (-5.235,5.235):
            b.beam((x,yy,FLOOR+5.48),(x,math.copysign(7.385,yy),FLOOR+5.48),.27,.30,p.lacquer)
        b.box((x,0,UPPER-.18),(.32,10.47,.36),p.floorwood)
        level=min(FLOOR+13.65,hip_underside(x,3.115)-.43)
        b.box((x,0,level),(.61,6.23,.75),p.floorwood)
        # The two end bays support a hipped end, not a complete centre truss.
        if abs(x)<14.7:
            b.box((x,0,FLOOR+15.15),(.46,3.10,.56),p.floorwood)


def grey_endwalls(target,origin,yaw,p):
    b=Batch(origin,yaw)
    # Stone-framed true arch, in the front corridor of both side walls.
    door_y=-6.30;r=.56;spring=FLOOR+2.30-r
    notch=[(door_y-r,FLOOR-.10),(door_y+r,FLOOR-.10),(door_y+r,spring)]
    notch.extend((door_y+r*math.cos(t),spring+r*math.sin(t)) for t in [math.pi*j/24 for j in range(25)])
    cut=Polygon(notch)
    profile=Polygon([(-7.385,FLOOR),(-7.385,LOW_EAVE+.32),(-5.235,FLOOR+8.23),
                     (-5.235,UPPER_EAVE+.28),(5.235,UPPER_EAVE+.28),(5.235,FLOOR+8.23),
                     (7.385,LOW_EAVE+.32),(7.385,FLOOR)])
    for sign in (-1,1):
        # Extrusion temporarily uses XY=(depth,height), then maps to (X,Y,Z).
        wall=Batch();wall.solid_xy(profile.difference(cut),sign*WIDTH/2-.29,sign*WIDTH/2+.29,p.brick)
        b.add([(x,y,z) for y,z,x in wall.v],wall.f,p.brick)
        x=sign*(WIDTH/2+.315)
        for side in (-1,1):
            b.box((x,door_y+side*.63,FLOOR+.87),(.18,.16,1.74),p.marble)
        outer=.71
        for j in range(32):
            a=math.pi*j/32;c=math.pi*(j+1)/32
            b.face([(x,door_y+v*math.cos(t),spring+v*math.sin(t)) for v,t in ((r,a),(r,c),(outer,c),(outer,a))],p.marble)
        for yy in (-5.235,5.235):
            b.box((x,yy,FLOOR+10.1),(.14,.24,4.3),p.brick)
    return b.finish('文渊阁 · 两山澄泥砖墙与1.12×2.30m通透券门',target,properties={'documented_arch_opening_m':[1.12,2.30],'source':PAPER})


def roof_colour(group,p,*,lower):
    for obj in group.objects:
        if obj.type!='MESH':
            continue
        slots={m.name:i for i,m in enumerate(obj.data.materials)}
        if p.green_clay.name not in slots:
            obj.data.materials.append(p.green_clay)
        idx=obj.data.materials.find(p.green_clay.name)
        if 'sculpted ridge' in obj.name:
            for i,m in enumerate(list(obj.data.materials)):
                if m in p.tiles or m==p.gold:
                    obj.data.materials[i]=p.green_clay
        else:
            hw=ROOF_WIDTH/2 if not lower else 18.15
            hd=ROOF_DEPTH/2 if not lower else 8.60
            for poly in obj.data.polygons:
                c=poly.center
                mat=obj.data.materials[poly.material_index]
                if mat in p.tiles and (abs(c.y)>hd-.78 or abs(c.x)>hw-.65):
                    poly.material_index=idx


def nine_dragon_ridge(target,origin,yaw,p,z,*,waist=False):
    b=Batch(origin,yaw)
    h=.20 if waist else .42
    ys=(-5.06,5.06) if waist else (0.,)
    for y0 in ys:
        b.box((0,y0,z+h/2),(29.40,.33,h),p.green_clay)
        for j in range(43):
            x=-14.7+(j+.5)*29.4/43
            # Real 43-piece mortar joints, rather than a single uninterrupted bar.
            for sy in (-1,1):
                b.box((x-29.4/86,y0+sy*.172,z+h/2),(.008,.01,h*.93),p.darktile)
        for sy in (-1,1):
            intervals=[(-14.7+i*(MAIN+14.7)/5,-14.7+(i+1)*(MAIN+14.7)/5,1) for i in range(5)]
            intervals += [(MAIN+i*(14.7-MAIN)/4,MAIN+(i+1)*(14.7-MAIN)/4,-1) for i in range(4)]
            for a,c,d in intervals:
                length=(c-a)*.89;mid=(c+a)/2
                pts=[(mid+length*(i/40-.5),y0+sy*(.18+.014*math.sin(i*.6)),z+h*(.50+.19*math.sin(i/40*math.tau*1.65))) for i in range(41)]
                b.path(pts,.047 if not waist else .023,p.purple,sides=7)
                hx=mid+d*length*.41
                b.ellipsoid((hx,y0+sy*.21,z+h*.61),(.11,.055,h*.23),p.purple,sides=9,rings=5)
                for side in (-1,1):
                    b.path([(hx,y0+sy*.214,z+h*.72),(hx-d*.10,y0+sy*.22,z+h*.96),
                            (hx-d*.17,y0+sy*.22,z+h*.90)],.014 if not waist else .008,p.purple,sides=5)
                for t in (.27,.59,.76):
                    x=a+(c-a)*t
                    b.path([(x,y0+sy*.19,z+h*.48),(x-d*.10,y0+sy*.214,z+h*.15),
                            (x+d*.14,y0+sy*.222,z+h*.13)],.016 if not waist else .009,p.purple,sides=5)
                for k in range(4):
                    x=a+(c-a)*(k+.5)/4
                    b.path([(x-.13,y0+sy*.183,z+h*.13),(x-.06,y0+sy*.195,z+h*.26),
                            (x+.04,y0+sy*.198,z+h*.26),(x+.10,y0+sy*.19,z+h*.16)],.011 if not waist else .006,p.cream,sides=5)
            b.ellipsoid((MAIN,y0+sy*.22,z+h*.55),(.13,.055,.13) if not waist else (.07,.03,.07),p.cream,sides=12,rings=6)
    return b.finish('文渊阁 · '+('腰檐20cm九龙博脊' if waist else '29.4m四十三节九龙正脊'),target,properties={
        'ridge_length_m':29.4,'ridge_height_m':h,'ridge_thickness_m':.33,
        'segmented_ridge_sections':43,'west_dragons':5,'east_dragons':4,
        'source':PAPER,'carving_note':'Counts, colours, ordering and ridge dimensions documented; individual sculptural relief is an interpretation.'})


def add_roofs(target,origin,yaw,p):
    lower=swept_roof('文渊阁 · 腰檐双坡',target,p,origin=origin,yaw=yaw,width=36.30,depth=17.20,
                     eave=LOW_EAVE,rise=LOW_RISE,kind='gable',stop=LOW_STOP,tiles=True,pitch=.27,detail=2)
    upper=swept_roof('文渊阁 · 上檐歇山',target,p,origin=origin,yaw=yaw,width=ROOF_WIDTH,depth=ROOF_DEPTH,
                     eave=UPPER_EAVE,rise=RISE,kind='xieshan',tiles=True,pitch=.27,detail=2,beasts=5,
                     terminal_height=1.25,ridge_length=29.4)
    roof_colour(lower,p,lower=True);roof_colour(upper,p,lower=False)
    # Replace only the upper roof's plain central ridge with the documented one.
    # Retain hip ridges and terminals; the central bar is buried by the new facing.
    nine_dragon_ridge(target,origin,yaw,p,UPPER_EAVE+RISE+.10)
    nine_dragon_ridge(target,origin,yaw,p,UPPER-.05,waist=True)
    # Small green-glazed hanging canopies over the two side archways.
    co,si=math.cos(yaw),math.sin(yaw)
    for sign in (-1,1):
        x,y=sign*(WIDTH/2+.33),-6.30
        wo=(origin[0]+co*x-si*y,origin[1]+si*x+co*y,origin[2])
        cp=SimpleNamespace(**p.__dict__);cp.roof=p.green;cp.tiles=[p.green_clay]*4
        canopy=swept_roof('文渊阁 · '+('东' if sign>0 else '西')+'券门绿琉璃垂花罩',target,cp,
                          origin=wo,yaw=yaw+math.pi/2,width=2.02,depth=.70,eave=FLOOR+2.88,rise=.42,
                          kind='hip',tiles=True,pitch=.12,detail=2,terminal_height=.19)
        canopy['source']=PAPER
        canopy['projection_note']='Wall-facing half embedded; visible projection approximately 0.24m.'
    return lower,upper


def add_stairs(b,p):
    # West end bay: two flights and an actual landing, no virtual camera tunnel.
    x=(XS[0]+XS[1])/2
    width=1.15
    y0=-3.8;run=4.60
    for i in range(20):
        hh=(MEZZ-FLOOR)*(i+1)/20
        b.box((x,y0+(i+.5)*run/20,FLOOR+hh/2),(width,run/20+.01,hh),p.floorwood)
    b.box((x,y0+run+.58,MEZZ-.10),(1.62,1.15,.20),p.floorwood)
    # Further ascent returns along the same narrow staircase bay.
    for i in range(14):
        hh=(UPPER-MEZZ)*(i+1)/14
        b.box((x,y0+run-(i+.5)*run/14,MEZZ+hh/2),(width,run/14+.01,hh),p.floorwood)
    for side in (-1,1):
        b.beam((x+side*.61,y0,FLOOR+.82),(x+side*.61,y0+run,MEZZ+.82),.07,.07,p.wood)
        b.beam((x+side*.61,y0+run,MEZZ+.82),(x+side*.61,y0,UPPER+.82),.07,.07,p.wood)


def bookcase(target,origin,yaw,p,index,position,width=1.43,height=3.1,rotation=0.):
    x,y,z=position;co,si=math.cos(rotation),math.sin(rotation)
    world=(origin[0]+math.cos(yaw)*x-math.sin(yaw)*y,origin[1]+math.sin(yaw)*x+math.cos(yaw)*y,origin[2]+z)
    b=Batch(world,yaw+rotation);depth=.46
    b.box((0,depth*.43,height/2),(width,.055,height),p.wood)
    for side in (-1,1):
        b.box((side*(width/2-.035),0,height/2),(.07,depth,height),p.wood)
    for j in range(6):
        zz=.11+j*(height-.20)/5
        b.box((0,0,zz),(width,depth+.025,.065),p.wood)
        if j==5:
            continue
        for k in range(4):
            xx=-width*.37+k*width*.245
            pack=.20+(index+k+j)%3*.025
            b.box((xx,-.025,zz+pack/2+.04),(width*.212,.34,pack),p.books[index%4])
            # Bound Chinese books live inside cloth-covered slipcases. Their
            # front is dark cloth with a narrow title label, not an exposed
            # white page block resembling a modern bookcase.
            b.box((xx+width*.102,-.010,zz+pack/2+.04),(.008,.29,pack*.68),p.paper)
            b.box((xx-width*.047,-.201,zz+pack/2+.04),(.028,.011,pack*.58),p.paper)
            for side in (-1,1):
                b.box((xx+side*width*.063,-.211,zz+pack/2+.04),(.017,.01,pack*.85),p.books[index%4])
    for x in (-width/2+.04,0,width/2-.04):
        b.box((x,-.257,height/2),(.045,.052,height-.13),p.wood)
    for j in range(6):
        zz=.11+j*(height-.20)/5
        b.box((0,-.263,zz),(width,.055,.047),p.wood)
    for side in (-1,1):
        b.box((side*width*.25,-.245,height/2),(width*.5-.065,.008,height-.22),p.glass)
    obj=b.finish('文渊阁 · 藏书橱 %03d'%index,target,bevel=.002)
    obj['placement_accuracy']='Interpreted furniture layout; not an item-by-item inventory or measured cabinet.'
    obj['reference_note']='Framed dark-front cabinets and cloth slipcases interpreted from Palace Museum archival interior photographs. Glazing and individual labels not measured.'
    return obj


def books(target,origin,yaw,p):
    g=collection('文渊阁 · 115架解释性藏书空间',target)
    count=0
    # 32 lower-floor cases (including 12 for Gujin Tushu Jicheng), 33 history
    # cases in mezzanine, and 50 on upper floor, following the 1993 survey.
    lower=[]
    for x in (-13.48,-9.40,11.55,15.55):
        for y in (-2.3,-.75,.80,2.35):
            lower.append((x,y,FLOOR))
    for y in (4.65,):
        for i in range(16):
            lower.append((-13.70+i*1.82,y,FLOOR))
    mezz=[]
    for i in range(21):
        mezz.append((-13.8+i*1.40,4.65,MEZZ))
    for x in (-13.0,13.0):
        for i in range(6):
            mezz.append((x,-2.6+i*1.25,MEZZ))
    upper=[]
    for row,y in enumerate((-4.55,-1.45,1.45,4.55)):
        n=13 if row<2 else 12
        for i in range(n):
            upper.append((-13.6+i*2.32,y,UPPER))
    for floor,items in (('下层',lower),('暗层',mezz),('上层',upper)):
        for pos in items:
            count+=1
            obj=bookcase(g,origin,yaw,p,count,pos,width=1.22 if floor=='暗层' else 1.43,height=2.32 if floor=='暗层' else 3.05)
            obj['storey']=floor
    return count


def pond_and_bridge(site,target,p):
    """The mapped front pond crossing was absent in the earlier whole-city mesh."""
    line=site.geom('685378540')
    a=Vector(line.coords[0]);c=Vector(line.coords[-1]);mid=(a+c)/2
    length=(c-a).length;yaw=math.atan2(c.y-a.y,c.x-a.x)
    g=collection('文渊阁 · 方池石桥与水生纹石栏',target)
    arch_block('文渊阁池桥 · 地图原始跨水位置',g,p,origin=(mid.x,mid.y,-1.2),yaw=yaw,
               width=length,depth=2.80,height=1.85,openings=[(0,length*.72,1.60)],rise=.95,stone=True)
    b=Batch((mid.x,mid.y,0),yaw)
    b.box((0,0,.72),(length+.20,3.05,.18),p.marble)
    for sign in (-1,1):
        stairs(b,(sign*(length/2+1.25),0),(sign*length/2,0),2.85,.022,.81,p,handrails=False)
    b.finish('文渊阁池桥 · 石板桥面及两端踏步',g)
    rails=Batch()
    pond=site.geom('41657452')
    cut=line.buffer(2.05,cap_style=2)
    border=pond.exterior.difference(cut)
    paths=list(border.geoms) if hasattr(border,'geoms') else [border]
    paths += [LineString([tuple(Vector((mid.x,mid.y))+Vector((math.cos(yaw)*x-math.sin(yaw)*sy*1.39,math.sin(yaw)*x+math.cos(yaw)*sy*1.39))) for x in (-length/2,length/2)]) for sy in (-1,1)]
    for k,line0 in enumerate(paths):
        z=.81 if k>=len(paths)-2 else .15
        n=max(1,round(line0.length/1.85));last=None
        for j in range(n+1):
            q=line0.interpolate(j*line0.length/n)
            x,y=q.x,q.y
            rails.lathe(x,y,((.15,z),(.15,z+.12),(.105,z+.16),(.10,z+.84),(.14,z+.88),(.11,z+.96)),p.marble,sides=12)
            if last:
                xx,yy=last
                d=math.dist((xx,yy),(x,y))
                if d>.05:
                    ux,uy=(x-xx)/d,(y-yy)/d
                    nx,ny=-uy,ux
                    for zz,h in ((.19,.14),(.78,.13)):
                        rails.beam((xx,yy,z+zz),(x,y,z+zz),.14,h,p.marble)
                    rails.beam((xx+ux*.12,yy+uy*.12,z+.47),(x-ux*.12,y-uy*.12,z+.47),.075,.45,p.marble)
                    # Water-animal subject is documented. Shape and placement here
                    # are an interpreted low relief, deliberately not called a scan.
                    for side in (-1,1):
                        def pt(u,h):
                            return ((x+xx)/2+ux*u+nx*.052*side,(y+yy)/2+uy*u+ny*.052*side,z+.48+h)
                        body=[pt(.24*math.cos(t),.095*math.sin(t)) for t in [j*math.tau/28 for j in range(29)]]
                        rails.path(body,.014,p.marble,sides=5)
                        rails.path([pt(-.21,0),pt(-.34,.10),pt(-.32,-.10),pt(-.21,0)],.013,p.marble,sides=5)
                        for off in (-.09,.045):
                            rails.path([pt(off-.13,.07),pt(off-.05,.115),pt(off+.05,.10),pt(off+.13,.04)],.011,p.marble,sides=5)
            last=(x,y)
    obj=rails.finish('文渊阁 · 池周石栏及解释性水生动物浅浮雕',g)
    obj['source_osm_pond']='41657452';obj['source_osm_bridge']='685378540'
    obj['accuracy']='Pond outline and crossing position from source map. Width, elevations, parapets and animal relief interpreted from architectural descriptions; not measured carvings.'
    return {'pond_osm':'41657452','bridge_osm':'685378540','mapped_span_m':length,
            'bridge_width_m_inferred':2.80,'carving_accuracy':'Interpretation of documented aquatic-animal subject, not exact copied carvings.'}


def build_wenyuan(root,palette):
    site=Site();shape=site.geom(REF)
    cx,cy,_,_,yaw=rectangle(shape);origin=(cx,cy,0)
    group=collection('文渊阁 · 实测柱网与三层藏书楼',root)
    group['source_osm_id']=REF
    group['dimension_source']=PAPER
    group['documented_spans_west_to_east_m']=SPANS
    group['documented_column_depth_m']=DEPTH
    group['unverified']='Roof heights and curve, terrace elevation, missing furniture dimensions, cabinet locations, carving shapes and weathering remain interpreted.'
    p=materials(palette)
    floor=Batch(origin,yaw)
    floor.box((0,0,FLOOR/2),(WIDTH+1.25,DEPTH+.82,FLOOR),p.marble_dark)
    floor.box((0,0,FLOOR-.055),(WIDTH+1.45,DEPTH+1.0,.11),p.marble)
    for i in range(4):
        h=FLOOR*(i+1)/4
        floor.box((MAIN,-8.68+(i+.5)*.30,h/2),(3.55,.31,h),p.marble)
    floor.finish('文渊阁 · 台明与前阶',group)
    columns=collection('文渊阁 · 42根米制柱网',group)
    for i,x in enumerate(XS):
        for j,y in enumerate(YS):
            outer=j in (0,5)
            top=5.48 if outer else 11.95 if j in (1,4) else 13.65
            if not outer:
                top=min(top,hip_underside(x,y)-FLOOR-.47)
            dia=.56 if outer else .68
            b=Batch(origin,yaw)
            b.lathe(x,y,((dia*.65,FLOOR-.02),(dia*.65,FLOOR+.11),(dia*.48,FLOOR+.17)),p.marble_dark,sides=24)
            # Published 2cm inward lean and 5cm head diameter reduction for eave columns.
            lean=-math.copysign(.02,y) if outer else 0.
            b.rod((x,y,FLOOR+.13),(x,y+lean,FLOOR+top),dia/2,p.lacquer,r1=(dia-.05)/2 if outer else dia*.48,sides=24)
            obj=b.finish('文渊阁 · 柱 %02d-%02d'%(i+1,j+1),columns)
            obj['grid_centre_local_m']=[x,y]
            obj['documented_diameter_m']=dia
            obj['height_m']=top
            obj['height_source']='Survey p43' if outer or (j in (2,3) and abs(x)<14.7) else 'Interpreted end/tong column under roof clearance'
    grey_endwalls(group,origin,yaw,p)
    timber=Batch(origin,yaw)
    # A real U-shaped mezzanine leaves the central hall double height.
    slab=box(XS[1],-5.235,WIDTH/2,5.235).difference(box(XS[2],-5.3,XS[5],3.115))
    timber.solid_xy(slab,MEZZ-.20,MEZZ,p.floorwood)
    # Upper floor has a staircase opening rather than a solid inaccessible slab.
    upper=box(-WIDTH/2,-5.235,WIDTH/2,5.235).difference(box(XS[0]+.30,-4.05,XS[1]-.24,1.65))
    timber.solid_xy(upper,UPPER-.22,UPPER,p.floorwood)
    add_stairs(timber,p)
    painted=painted_strip_material()
    add_beams(timber,p,painted)
    for sign in (-1,1):
        yy=sign*7.385
        for a,c in zip(XS,XS[1:]):
            if a<MAIN<c:
                balustrade(timber,a+.28,MAIN-1.04,yy,FLOOR,p)
                balustrade(timber,MAIN+1.04,c-.28,yy,FLOOR,p)
            else:
                balustrade(timber,a+.28,c-.28,yy,FLOOR,p)
        for level,h in ((FLOOR,4.70),(UPPER,3.25)):
            for i,(a,c) in enumerate(zip(XS,XS[1:])):
                y=sign*(3.115 if level==FLOOR and i in (2,3,4) and sign<0 else 5.235)
                n=12 if i==3 and level==FLOOR else 10 if i in (2,4) and level==FLOOR else max(3,round((c-a)/.66))
                width=(c-a-.36)/n
                for j in range(n):
                    # Keep the two middle leaves genuinely open at the central entrance.
                    if i==3 and level==FLOOR and j in (n//2-1,n//2):
                        continue
                    x=a+.18+(j+.5)*width
                    lantern_panel(timber,x,y,level+.06,width-.025,h,p)
                    if level==FLOOR:
                        # Only the rear transoms are blind, as described in p38.
                        lantern_panel(timber,x,y,FLOOR+5.08,width-.025,2.42,p,blind=sign>0)
        # Intermediate front balustrade on the tong-column line.
        if sign<0:
            for i in (2,3,4):
                a,c=XS[i:i+2]
                if i==3:
                    balustrade(timber,a+.22,MAIN-1.04,-5.235,FLOOR,p)
                    balustrade(timber,MAIN+1.04,c-.22,-5.235,FLOOR,p)
                else:
                    balustrade(timber,a+.22,c-.22,-5.235,FLOOR,p)
    # Plank partition makes the west stair bay an actual separate room.
    for a,c in ((-5.235,-3.5),(-2.25,5.235)):
        timber.box((XS[1],(a+c)/2,(FLOOR+UPPER)/2),(.18,c-a,UPPER-FLOOR),p.wood)
    obj=timber.finish('文渊阁 · 梁枋回纹栏杆槅扇及真实夹层楼梯',group)
    obj['railing_height_m']=1.30
    obj['central_railing_gate_width_m']=2.08
    obj['upper_floor_underside_from_ground_floor_m']=7.83
    obj['mezzanine_clear_height_m']=2.86
    add_roofs(group,origin,yaw,p)
    cabinets=books(group,origin,yaw,p)
    pond=pond_and_bridge(site,group,p)
    return group,{
        'placement_osm_id':REF,'placement_metres':[cx,cy], 'yaw_radians':yaw,
        'column_grid_spans_m':list(SPANS),'column_grid_width_m':WIDTH,'column_grid_depth_m':DEPTH,
        'column_count':42,'eave_column_height_m':5.48,'eave_column_diameter_m':.56,
        'inner_column_diameter_m':.68,'gold_column_height_m':13.65,
        'railing_height_m':1.30,'central_railing_gate_m':2.08,
        'arch_clear_width_height_m':[1.12,2.30],
        'cabinet_counts_by_level':[32,33,50],'total_cabinets':cabinets,
        'ridge_length_height_thickness_m':[29.4,.42,.33],'ridge_sections':43,
        'front_pond_and_bridge':pond,
        'source':PAPER,
        'modelled_derived_levels_m':{'ground_floor':FLOOR,'mezzanine':MEZZ,'upper_floor':UPPER,'upper_roof_eave':UPPER_EAVE},
        'precision_limits':[
            'Map placement is contributed cartography, not a certified survey.',
            'Bay widths transcribed from printed plan to 0.01m; sum33.01m versus rounded33m in the text.',
            'Upper floor underside7.83m and mezzanine2.86m are documented; slab thickness and site elevation inferred.',
            'Unpublished roof heights, curves, framing details, precise cabinet positions and sculptural relief inferred.',
            'The paper documents115 shelves; individual cabinets and books are interpreted, not inventories of surviving objects.',
            '1988 survey and2025 paint photos describe different observation dates; no all-surface present-day identity is claimed.'
        ]}
