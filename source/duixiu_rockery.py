"""Dui Xiu rockery, separated stone flights, grotto, fountains and summit pavilion."""
import math
import random
from types import SimpleNamespace

import bpy
import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from architectural_roofs import swept_roof
from carved_ornament import cloud, dragon
from duixiu_vegetation import creepers, pine
from garden_bridge_pavilions import flower, laid_pavers, ring_outline, transfer
from mesh_tools import Batch, collection, polygons
from osm_site import rectangle
from palace_architecture import arch_mesh, arch_section
from palace_materials import paint
from qinan_hall import bracket, marble_rail, painted_bay, plaque, text_mesh
from qinan_survey import (DUIXIU, GARDEN_SOURCE, PAVILION_SOURCE, ROCK_ARTICLE, ROCK_SOURCE, SUMMIT_Z, YUJING, Location)
from taihu_stone import limestone, mesh_field, waves

SUMMIT=(-4.45,-1.72,4.62,6.07)
PAVILION_Z=SUMMIT_Z+.276
CAVE_X=.13
CAVE_Y=-3.33
CAVE_RX,CAVE_RY=1.56,1.63
CAVE_Z=.153
CAVE_SPRING=1.87
CAVE_RISE=1.32
PORTAL=-6.68
PORTAL_W=1.81
PORTAL_H=2.531
FOUNTAIN_Y=-7.37
WEST=((-8.55,-7.55,.031),(-8.26,-3.37,1.94),(-8.07,.58,3.97),(-7.80,4.03,5.68),
      (-6.37,5.21,6.57),(-5.42,3.51,7.70),(-5.28,1.38,8.86),(-4.31,.62,SUMMIT_Z))
EAST=((8.62,-7.21,.031),(8.37,-3.73,1.79),(8.52,.26,3.80),(8.11,3.75,5.61),
      (6.76,5.61,6.74),(5.73,4.89,7.49),(5.45,2.78,8.68),(4.52,1.55,SUMMIT_Z))


def rock_materials(base):
    p=SimpleNamespace(**base.__dict__)
    p.limestone=paint('堆秀山 · 错落青灰太湖石',(.092,.098,.101),second=(.391,.377,.342),scale=3.8,
                      rough=.88,grain=56,bump=.049)
    p.pocket=paint('堆秀山 · 暗灰孔蚀与湿纹',(.072,.076,.069),second=(.285,.264,.209),scale=5.9,
                   rough=.89,grain=64,bump=.034)
    p.mortar=paint('堆秀山 · 洞内深灰砖缝',(.061,.054,.043),second=(.172,.145,.109),scale=4.5,
                   rough=.96,grain=124,bump=.006)
    p.vault=[paint(f'堆秀山 · 穹隆旧砖 {i+1}',(r*.69,g*.69,b*.69),second=(r,g,b),scale=13.,rough=.88,
                   grain=107,bump=.0042) for i,(r,g,b) in enumerate(((.336,.277,.201),(.268,.231,.173),
                                                                       (.366,.324,.248),(.307,.259,.181)))]
    p.creeper=[paint(f'堆秀山 · 地锦叶 {i+1}',rgb,rough=.76,bump=.002,coat=.09) for i,rgb in enumerate(
        ((.043,.081,.020),(.072,.112,.026),(.129,.156,.048),(.101,.123,.032)))]
    bsdf=p.limestone.node_tree.nodes.get('Principled BSDF')
    nodes=p.limestone.node_tree.nodes;links=p.limestone.node_tree.links
    geometry=nodes.new('ShaderNodeNewGeometry')
    coarse=nodes.new('ShaderNodeTexNoise');coarse.inputs['Scale'].default_value=1.79;coarse.inputs['Detail'].default_value=5.3
    links.new(geometry.outputs['Position'],coarse.inputs['Vector'])
    color=next(n for n in nodes if n.type=='VALTORGB')
    links.new(coarse.outputs['Fac'],color.inputs[0])
    stops=color.color_ramp.elements
    stops[0].position=.216;stops[1].position=.788
    stops.new(.455).color=(.199,.213,.218,1)
    stops.new(.621).color=(.346,.319,.263,1)
    deposits=nodes.new('ShaderNodeTexNoise');deposits.inputs['Scale'].default_value=.79
    deposits.inputs['Detail'].default_value=5.1;deposits.inputs['Roughness'].default_value=.72
    links.new(geometry.outputs['Position'],deposits.inputs['Vector'])
    ochre=nodes.new('ShaderNodeValToRGB')
    ochre.color_ramp.elements[0].position=.515;ochre.color_ramp.elements[0].color=(0,0,0,1)
    ochre.color_ramp.elements[1].position=.717;ochre.color_ramp.elements[1].color=(.79,.79,.79,1)
    links.new(deposits.outputs['Fac'],ochre.inputs[0])
    blend=nodes.new('ShaderNodeMixRGB');blend.inputs[2].default_value=(.45,.368,.245,1)
    links.new(ochre.outputs['Color'],blend.inputs[0]);links.new(color.outputs['Color'],blend.inputs[1])
    links.new(blend.outputs[0],bsdf.inputs['Base Color'])
    cracks=nodes.new('ShaderNodeTexNoise');cracks.inputs['Scale'].default_value=12.55;cracks.inputs['Detail'].default_value=6.8
    links.new(geometry.outputs['Position'],cracks.inputs['Vector'])
    bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.54;bump.inputs['Distance'].default_value=.047
    links.new(cracks.outputs['Fac'],bump.inputs['Height'])
    links.new(next(n for n in nodes if n.type=='BUMP' and n!=bump).outputs['Normal'],bump.inputs['Normal'])
    links.new(bump.outputs['Normal'],bsdf.inputs['Normal'])
    return p


def segment_metrics(x,y,a,c):
    vx,vy=c[0]-a[0],c[1]-a[1]
    t=np.clip(((x-a[0])*vx+(y-a[1])*vy)/(vx*vx+vy*vy),0,1)
    gap=np.hypot(x-a[0]-vx*t,y-a[1]-vy*t)
    return gap,a[2]+(c[2]-a[2])*t


def core(loc,site,target,p):
    ax=np.arange(-10.6,10.72,.146)
    ay=np.arange(-8.01,7.87,.146)
    az=np.arange(-.40,SUMMIT_Z+.454,.146)
    x,y,z=np.meshgrid(ax,ay,az,indexing='ij',sparse=True)
    xy=shapely.points(*np.meshgrid(ax,ay,indexing='ij'))
    bottom=loc.local(site.geom(DUIXIU)).buffer(-.23,quad_segs=3)
    top=box(-4.59,-1.86,4.77,6.15).buffer(.17,quad_segs=5)

    def distance(shape):
        return (shapely.distance(xy,shape.boundary)*np.where(shapely.contains(shape,xy),-1.,1.))[:,:,None]

    t=np.clip(z/SUMMIT_Z,0,1)**.712
    f=(1-t)*distance(bottom)+t*distance(top)
    variation=waves(x*.55,y*.50,z*.77,1.81)
    f+=.63*variation+.104*np.cos(x*3.34-z*2.79)
    f=np.maximum(f,np.maximum(-z-.107,z-(SUMMIT_Z-.045)))
    # Fill the retaining slopes underneath exposed stair runs before excavating headroom.
    for path in (WEST,EAST):
        for a,b in zip(path,path[1:]):
            gap,h=segment_metrics(x,y,a,b)
            shoulder=1.205+.30*variation+.15*np.sin(z*3.4+x*1.6)
            f=np.minimum(f,np.maximum.reduce(np.broadcast_arrays(gap-shoulder,z-h+.126,-z-.062)))
    # The void is the union of the barrel entry and an oval chamber under a brick dome.
    x0=x-CAVE_X;y0=y-CAVE_Y
    ell=np.sqrt((x0/(CAVE_RX+.045))**2+(y0/(CAVE_RY+.048))**2+np.maximum(0,(z-CAVE_SPRING)/(CAVE_RISE+.106))**2)
    room=np.maximum(ell-1,CAVE_Z-.14-z)
    mouth=np.maximum(np.sqrt((x0/(PORTAL_W/2+.069))**2+np.maximum(0,(z-1.64)/1.002)**2)-1,
                     np.maximum(y+3.64,CAVE_Z-.14-z))
    f=np.maximum(f,-np.minimum(room,mouth))
    for path in (WEST,EAST):
        for a,b in zip(path,path[1:]):
            gap,h=segment_metrics(x,y,a,b)
            f=np.maximum(f,-np.maximum(gap-.618,h-z-.073))
    limestone_core=mesh_field('堆秀山 · 有洞室和磴道凹槽的连续山芯', (ax,ay,az),f,p.pocket)
    obj=bpy.data.objects.new('堆秀山 · 叠石内芯和承托壳',limestone_core)
    target.objects.link(obj);obj.location=loc.world();obj.rotation_euler.z=loc.yaw
    obj['source_osm_id']=DUIXIU
    obj['representation']='Closed editable surface. Outline from OSM; sectional rock form is interpreted.'
    return obj


def terrain_blocked(x,y,z,rx,ry,rz):
    rad=min(rx,ry)*.87
    if z-rz<3.31:
        if abs(x-CAVE_X)<PORTAL_W/2+rad+.10 and -9.22<y<-3.81:
            return True
        if ((x-CAVE_X)/(CAVE_RX+rx*.86))**2+((y-CAVE_Y)/(CAVE_RY+ry*.85))**2<1:
            return True
    for path in (WEST,EAST):
        for a,c in zip(path,path[1:]):
            distance,h=segment_metrics(x,y,a,c)
            if distance<.68+rad and z+rz>h-.11:
                return True
    if z+rz>SUMMIT_Z-.12 and box(*SUMMIT).buffer(.20).distance(Point(x,y))<rad:
        return True
    return False


def slope_surface(theta,t):
    """Squarish, asymmetrical terrace silhouette, with steeper southern face."""
    c,s=math.cos(theta),math.sin(theta)
    cx=(math.copysign(abs(c)**.66,c))*(9.13-(9.13-4.27)*t)
    cy=(math.copysign(abs(s)**.72,s))*(6.70-(6.70-3.91)*t)+2.08*t
    return cx+.26*math.sin(theta*3.0+t*3.1),cy+.37*math.cos(theta*3.0-t*4.1)


def rock_objects(loc,target,p):
    library=[limestone(f'太湖石 · 孔蚀母形 {i+1:02}',i,p.limestone,p.pocket) for i in range(11)]
    rng=random.Random(42424158)
    objects=[]
    coords=[]

    def add(x,y,z,rx,ry,rz,angle,idx=None,tilt=(0.,0.)):
        if terrain_blocked(x,y,z,rx,ry,rz):
            return
        model=library[rng.randrange(len(library)) if idx is None else idx]
        obj=bpy.data.objects.new(f'堆秀山 · 叠石 {len(objects)+1:03}',model)
        target.objects.link(obj)
        obj.location=loc.world(x,y,z);obj.rotation_euler=(tilt[0],tilt[1],loc.yaw+angle)
        obj.scale=(rx,ry,rz)
        obj['fidelity']='Limestone morphology from the reference photographs; not a scanned specimen.'
        objects.append(obj.name);coords.append((x,y,z,rx,ry,rz))

    for j,z in enumerate((.37,1.16,2.06,3.03,4.18,5.12,6.07,7.05,8.04,8.95,9.53)):
        level=(z/SUMMIT_Z)**.712
        count=round(43-level*15)
        for i in range(count):
            a=(i+.39*(j%3)+rng.uniform(-.25,.25))*math.tau/count
            x,y=slope_surface(a,level)
            x+=rng.uniform(-.39,.47);y+=rng.uniform(-.37,.42)
            radius=rng.uniform(.43,1.05)
            size=1.1-.31*level
            rx=radius*size;ry=rng.uniform(.42,.91)*size;rz=rng.uniform(.46,1.04)*size
            if rng.random()<.2:
                rz*=1.28;rx*=.82
            ang=a+math.pi/2+rng.uniform(-.7,.7)
            add(x,y,z+rng.uniform(-.23,.32),rx,ry,rz,ang,tilt=(rng.uniform(-.29,.28),rng.uniform(-.35,.32)))
    # Irregular stones beside the east and west stairs cover the visible retaining slopes.
    for side,path in ((-1,WEST),(1,EAST)):
        for a,c in zip(path,path[1:]):
            if a[2]>7.9:
                continue
            dx,dy=c[0]-a[0],c[1]-a[1]
            span=math.hypot(dx,dy)
            inward=side*-1
            for j in range(round(span/.64)):
                t=(j+.46)/round(span/.64)
                x,y,z=(a[k]+(c[k]-a[k])*t for k in range(3))
                for bank in (-1,1):
                    s=inward*bank
                    u=.98+rng.uniform(-.13,.29)
                    xx=x+s*u*dy/span;yy=y-s*u*dx/span
                    rz=rng.uniform(.32,.66)
                    add(xx,yy,max(.30,z-rz*.89+rng.uniform(-.04,.14)),rng.uniform(.38,.59),rng.uniform(.39,.58),rz,
                        rng.uniform(0,math.tau),tilt=(rng.uniform(-.23,.23),rng.uniform(-.24,.24)))
    # Projecting large reef-like columns and the stone with the Yun Gen inscription.
    for pos in ((-2.78,-6.08,1.83,.62,.78,1.59,.11),(-5.11,-5.92,2.91,1.12,.83,1.31,-.46),
                (-6.76,-4.86,4.16,.86,.62,1.52,-.32),(-1.97,-4.53,4.18,.63,1.05,1.69,.92),
                (3.58,-5.49,3.06,.63,.70,1.47,-.85),(5.19,-5.85,1.77,.84,.79,1.83,-.075),
                (6.69,-5.37,1.46,1.01,.64,1.42,.125),(4.18,-3.73,5.48,.78,.76,1.06,-.36),
                (.56,-3.52,5.91,.64,.66,1.39,.37),(-3.07,-2.91,7.35,.61,.60,1.19,-.21),
                (-.92,-2.26,8.03,.57,.71,1.45,-.13),(1.52,-2.47,8.61,.62,.63,.88,1.2),
                (3.34,-2.26,9.21,.395,.438,1.03,.60)):
        add(*pos,tilt=(rng.uniform(-.28,.28),rng.uniform(-.32,.36)))
    return objects,coords


def flight_settings(path):
    rows=[]
    for i,(a,c) in enumerate(zip(path,path[1:])):
        d=math.dist(a[:2],c[:2])
        start=min(.40,d*.213) if i else .0
        end=min(.40,d*.213) if i<len(path)-2 else .0
        run=d-start-end
        count=max(1,min(round((c[2]-a[2])/.171),int(run/.212)))
        rows.append((d,start,end,count,run/count))
    return rows


def make_flight(loc,target,p,path,side):
    group=collection(f'堆秀山 · {side}磴道',target)
    b=loc.batch();risers=0
    width=1.12
    labels=[]
    settings=flight_settings(path)
    for i,((a,c),(distance,start,end,count,run)) in enumerate(zip(zip(path,path[1:]),settings)):
        dx=(c[0]-a[0])/distance;dy=(c[1]-a[1])/distance
        angle=math.atan2(dy,dx)
        z0,z1=a[2],c[2]
        local=Batch()
        if start:
            local.box((start*.5,0,z0-.073),(start+.018,width+.036,.146),p.stone)
        if end:
            local.box((distance-end*.5,0,z1-.073),(end+.018,width+.036,.146),p.stone)
        for j in range(count):
            z=z0+(z1-z0)*(j+1)/count
            if run<.20:
                raise RuntimeError(f'Rock stair tread is too short: {side} {i+1}: {run:.3f} m')
            u=start+(j+.5)*run
            local.box((u,0,z-.218),(run+.014,width,.435),p.understone)
            local.box((u-.003,0,z-.029),(run+.015,width+.016,.058),p.stone)
            if j%3==1:
                v=.174*math.sin(i*3+j*1.14)
                local.box((u,v,z-.007),(run*.95,.005,.004),p.understone)
        transfer(b,local,a[0],a[1],angle)
        if i<len(path)-2:
            b.solid_xy(Point(*c[:2]).buffer(.537,quad_segs=8),c[2]-.138,c[2]-.002,p.stone)
        risers+=count
        labels.append({'treads':count,'riser_m':(z1-z0)/count,'tread_m':run,
                       'start_landing_m':start,'end_landing_m':end})
    b.finish(f'堆秀山 · {side}磴道踏面与转折石',group,properties={'treads':risers,'narrow_width_m_in_model':width})
    # Repeated topological junctions must be explicit in the modeled base path.
    x,y,_=path[0]
    leaf=loc.batch()
    for sign in (-1,1):
        u=x+sign*.737
        leaf.box((u,y+.04,1.01),(.19,.215,2.06),p.limestone)
    leaf.box((x,y+.045,2.067),(1.66,.231,.223),p.limestone)
    leaf.box((x+(1 if side=='东' else -1)*.68,y+.52,1.01),(.081,.943,1.89),p.fascia,yaw=.075)
    leaf.finish(f'堆秀山 · {side}侧磴道入口及开启木门',group)
    return labels


def shell_tile(b,vertices,material,thickness=.038):
    """Four-point facing wedge with a thin closed mortar bed on its back."""
    back=[(x,y,z+thickness) for x,y,z in vertices]
    b.add([*vertices,*back],((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)),material)


def grotto(loc,target,p):
    group=collection('堆秀山 · 南券、砖砌穹隆与石雕蟠龙藻井',target)
    wall,bricks,relief,floor=(loc.batch() for _ in range(4))
    entry=arch_section(CAVE_X,PORTAL_W,PORTAL_H,bottom=CAVE_Z-.13,rise=.94)
    portal=Batch()
    arch_mesh(portal,box(CAVE_X-1.30,.019,CAVE_X+1.30,2.748).difference(entry),.53,p.understone)
    transfer(wall,portal,0,PORTAL,0)
    for i in range(17):
        lo,hi=(i+.009)*math.pi/17,(i+.991)*math.pi/17
        coords=[(CAVE_X+r*math.cos(a),PORTAL-.273,PORTAL_H-.94+h*math.sin(a))
                for r,h,angles in ((PORTAL_W/2,.94,(lo,hi)),(PORTAL_W/2+.24,.94+.208,(hi,lo))) for a in angles]
        wall.face(coords,p.stone if i%3 else p.understone)
    for side in (-1,1):
        for j in range(8):
            h=(PORTAL_H-.94-CAVE_Z)/8
            wall.box((CAVE_X+side*(PORTAL_W/2+.098),PORTAL-.285,CAVE_Z+(j+.50)*h),(.194,.231,h-.004),p.understone)
    base=Point(CAVE_X,CAVE_Y).buffer(1.,quad_segs=34)
    from shapely.affinity import scale as scale_shape
    bed=scale_shape(base,CAVE_RX,CAVE_RY,origin=(CAVE_X,CAVE_Y)).union(box(CAVE_X-PORTAL_W/2,PORTAL-.79,CAVE_X+PORTAL_W/2,-3.82))
    floor.solid_xy(bed,CAVE_Z-.094,CAVE_Z-.051,p.mortar)
    laid_pavers(floor,bed,CAVE_Z,p,course=.294,width=.442)
    for j in range(13):
        z=CAVE_Z+j*(CAVE_SPRING-CAVE_Z)/13
        for i in range(39):
            a=(i+j*.5)*math.tau/39
            cc=a+math.pi/39
            if math.sin(cc)<-.30 and abs(CAVE_RX*math.cos(cc))<.916:
                continue
            v=[]
            for h in (z+.004,z+(CAVE_SPRING-CAVE_Z)/13-.003):
                for t in (a+.003,a+math.tau/39-.003):
                    v.append((CAVE_X+CAVE_RX*math.cos(t),CAVE_Y+CAVE_RY*math.sin(t),h))
            bricks.face((v[0],v[2],v[3],v[1]),p.vault[(i+3*j)%len(p.vault)])
    for j in range(15):
        lo=j*math.pi/2/15;hi=(j+1)*math.pi/2/15
        n=max(8,round(39*math.cos((lo+hi)*.5)))
        edge=(j%2)*.5*math.tau/n
        for i in range(n):
            t0=edge+(i+.019)*math.tau/n;t1=edge+(i+.981)*math.tau/n
            def at(t,lat):
                return (CAVE_X+CAVE_RX*math.cos(t)*math.cos(lat),CAVE_Y+CAVE_RY*math.sin(t)*math.cos(lat),
                        CAVE_SPRING+CAVE_RISE*math.sin(lat))
            m=at((t0+t1)/2,(lo+hi)/2)
            if m[1]<-4.43 and abs(m[0]-CAVE_X)<.90 and m[2]<PORTAL_H-.08:
                continue
            shell_tile(bricks,[at(t0,lo+.003),at(t1,lo+.003),at(t1,hi-.003),at(t0,hi-.003)],p.vault[(i*7+j)%4])
    # Separate longitudinal barrel from the dome. The intrados remains visible through the aperture.
    y0,y1=PORTAL+.08,-4.47
    for col in range(12):
        ya=y0+col*(y1-y0)/12+.004;yb=ya+(y1-y0)/12-.008
        for k in range(25):
            a=(k+.014)*math.pi/25;c=(k+.986)*math.pi/25
            shell_tile(bricks,[(CAVE_X+(PORTAL_W/2+.011)*math.cos(t),v,PORTAL_H-.94+.94*math.sin(t))
                               for t,v in ((a,ya),(a,yb),(c,yb),(c,ya))],p.vault[(col+k)%4])
        for sign in (-1,1):
            for j in range(11):
                z=CAVE_Z+(j+.5)*(PORTAL_H-.94-CAVE_Z)/11
                bricks.box((CAVE_X+sign*(PORTAL_W/2+.047),(ya+yb)/2,z),(.079,yb-ya,(PORTAL_H-.94-CAVE_Z)/11-.004),p.vault[(col+j)%4])
    crown=CAVE_SPRING+CAVE_RISE-.121
    relief.rod((CAVE_X,CAVE_Y,crown+.136),(CAVE_X,CAVE_Y,crown),.642,p.understone,sides=64)
    relief.rod((CAVE_X,CAVE_Y,crown+.062),(CAVE_X,CAVE_Y,crown-.012),.562,p.stone,sides=64)
    dragon(relief,(CAVE_X,CAVE_Y,crown-.009),.88,.96,SimpleNamespace(gold=p.understone,giltpaint=p.stone,door=p.mortar),
           facing='ceiling',z_relief=.037)
    for i in range(10):
        angle=i*math.tau/10
        cloud(relief,(CAVE_X+.482*math.cos(angle),CAVE_Y+.49*math.sin(angle),crown-.027),.119,p.understone,
              facing='ceiling',rotation=angle*1.3)
    wall.box((CAVE_X,PORTAL-.299,2.69),(1.164,.134,.278),p.understone)
    wall.box((CAVE_X,PORTAL-.374,2.694),(1.04,.033,.21),p.stone)
    wall.finish('堆秀山 · 石券口、砌石券脸与匾石',group)
    text_mesh(group,loc,'堆秀 · 洞门题字','堆 秀',CAVE_X-.02,PORTAL-.397,2.698,.139,p.mortar)
    bricks.finish('堆秀山 · 纵向券筒、穹隆砖瓣和砖缝',group)
    floor.finish('堆秀山 · 洞内脚下铺砖与门坎',group)
    relief.finish('堆秀山 · 实体蟠龙石雕和圆井',group)
    return group


def reclining_lion(b,dx,dy,z,p,scale,turn):
    t=Batch();s=scale
    a,c=p.stone,p.understone
    def C(x,y,h):
        return x*s,y*s,z+h*s
    t.ellipsoid(C(0,.093,.29),(.405*s,.563*s,.277*s),c,sides=26,rings=16)
    t.ellipsoid(C(.08,-.321,.339),(.296*s,.275*s,.272*s),a,sides=25,rings=16)
    t.ellipsoid(C(.193,-.507,.310),(.195*s,.127*s,.112*s),a,sides=24,rings=14)
    for side in (-1,1):
        t.ellipsoid(C(.116+side*.222,-.410,.152),(.157*s,.274*s,.090*s),c,sides=19,rings=12)
        t.ellipsoid(C(side*.25,.31,.176),(.166*s,.266*s,.131*s),a,sides=18,rings=12)
        for k in range(4):
            t.ellipsoid(C(.035+k*.061+side*.224,-.586,.127),(.032*s,.064*s,.038*s),a,sides=10,rings=7)
        t.ellipsoid(C(.126+side*.147,-.491,.424),(.047*s,.024*s,.038*s),c,sides=14,rings=9)
        t.ellipsoid(C(.092+side*.19,-.242,.491),(.077*s,.061*s,.105*s),a,sides=15,rings=9)
        for k in range(8):
            t.path([C(.10+side*(.15+.091*math.sin(t*math.pi*1.22)),-.299+k*.025-.045*math.sin(t*math.tau),
                      .332+k*.029+.082*math.cos(t*math.pi*1.3)) for t in (j/24 for j in range(25))],.024*s,a,sides=7)
    t.path([C(.065,.538,.203),C(.303,.596,.276),C(.408,.444,.354),C(.372,.286,.434),C(.295,.333,.49)],.051*s,a,sides=10)
    transfer(b,t,dx,dy,turn)


def stone_fountain(loc,target,p,side):
    group=collection('堆秀山 · '+('东' if side>0 else '西')+'侧石蟠龙水法',target)
    x=side*4.07+CAVE_X;y=FOUNTAIN_Y+.15*(side>0)
    b=loc.batch();d=loc.batch()
    b.solid_xy(box(x-.714,y-.597,x+.714,y+.597),.035,.186,p.understone)
    reclining_lion(b,x,y,.184,p,1.06,.334*side)
    for sign in (-1,1):
        reclining_lion(b,x+sign*.241,y+.042,.738,p,.44,sign*.94)
    b.lathe(x,y,((.287,.761),(.296,.905),(.351,.969),(.469,1.024),(.578,1.145),
                  (.613,1.295),(.616,1.49),(.581,1.54),(.518,1.527),(.504,1.431),(.463,1.281),(.285,1.196)),
            p.stone,sides=64)
    for i in range(15):
        a=i*math.tau/15
        b.ellipsoid((x+.591*math.cos(a),y+.590*math.sin(a),1.301),(.063,.049,.065),p.understone,
                    sides=11,rings=7,yaw=a)
        for side_a in (-1,1):
            aa=a+side_a*.121
            b.path([(x+(r+.58)*math.cos(aa),y+(r+.58)*math.sin(aa),h) for r,h in
                    ((0,1.28),(.036,1.258),(.035,1.356),(.012,1.393))],.014,p.stone,sides=6)
    coil=[(x+(.314-.18*t)*math.cos(1.48*math.tau*t),y+(.317-.197*t)*math.sin(1.48*math.tau*t),1.322+.495*t**1.51)
          for t in (i/117 for i in range(118))]
    d.path(coil,.073,p.understone,sides=15)
    for i in range(3,len(coil)-9,2):
        xx,yy,zz=coil[i]
        d.path([(xx+.058*math.cos(a),yy+.058*math.sin(a),zz+.055+.026*math.cos(a)) for a in (j*math.pi/8 for j in range(9))],
               .0067,p.stone,sides=5)
    u,v,h=coil[-1]
    d.ellipsoid((u,v-.013,h+.05),(.136,.112,.131),p.stone,sides=24,rings=15)
    d.ellipsoid((u,v-.053,h+.153),(.096,.072,.113),p.stone,sides=19,rings=13)
    d.rod((u,v-.077,h+.258),(u,v-.077,h+.274),.036,p.mortar,sides=18)
    for sign in (-1,1):
        d.ellipsoid((u+sign*.090,v-.093,h+.092),(.039,.029,.027),p.understone,sides=12,rings=8)
        d.path([(u+sign*.061,v+.050,h+.077),(u+sign*.109,v+.085,h+.204),
                (u+sign*.094,v+.117,h+.248)],.018,p.stone,sides=8)
        d.path([(u+sign*.064,v-.112,h+.153),(u+sign*.175,v-.047,h+.124),
                (u+sign*.219,v+.033,h+.178)],.016,p.understone,sides=8)
    b.finish('堆秀山 · 伏狮、双幼狮与浮雕石钵',group)
    d.finish('堆秀山 · 盘身、龙口与水道孔',group,properties={
        'source':'https://yllhj.beijing.gov.cn/ztxx/lhysh/sh/202308/t20230814_3221918.shtml',
        'state':'No running water portrayed. The carved outlet and basin remain visible.'})


def diamond_panel(b,x,y,z,w,h,p,yaw):
    t=Batch()
    for side in (-1,1):
        t.box((side*(w/2-.043),0,z+h/2),(.078,.129,h),p.fascia)
        t.box((0,0,z+h*(.019 if side<0 else .981)),(w,.118,.082),p.red)
    t.box((0,.002,z+h*.154),(w-.119,.101,h*.263),p.fascia)
    void=box(-w/2+.051,z+h*.292,w/2-.051,z+h-.038)
    for sign in (-1,1):
        for j in range(-30,31):
            v=j*.12
            ln=LineString(((-w/2,v+z), (w/2,v+z+w*sign))).intersection(void)
            if ln.geom_type=='LineString' and ln.length>.018:
                a,c=ln.coords[0],ln.coords[-1]
                t.rod((a[0],-.023+sign*.008,a[1]),(c[0],-.023+sign*.008,c[1]),.016,p.red,sides=6)
    transfer(b,t,x,y,yaw)


def summit_room(loc,target,p,z):
    room=collection('御景亭 · 井口天花与南向宝座',target)
    room['museum_source']=PAVILION_SOURCE
    room['evidence']='Caisson and south-facing throne are documented; their geometry and paint are typological estimates.'
    frame,patterns,seat=(loc.batch() for _ in range(3))
    top=z+3.18
    center=Polygon(ring_outline(1.045))
    for i in range(7):
        for j in range(7):
            u,v=(i-3)*.72,(j-3)*.687
            panel=box(u-.353,v-.336,u+.353,v+.336).difference(center)
            for shape in polygons(panel):
                frame.solid_xy(shape,top,top+.057,p.faded_teal)
                if shape.area>.37:
                    flower(patterns,u,v,top-.006,.157,p.cream,p.giltpaint)
    for i in range(8):
        for is_x,length,step in ((True,4.846,.72),(False,5.07,.687)):
            u=(i-3.5)*step
            span=LineString(((u,-length/2),(u,length/2)) if is_x else ((-length/2,u),(length/2,u)))
            for part in getattr(span.difference(center),'geoms',(span.difference(center),)):
                if not part.is_empty:
                    a,c=part.coords[0],part.coords[-1]
                    frame.beam((*a,top-.021),(*c,top-.021),.07,.067,p.fascia)
    levels=((1.045,top),(.943,top+.12),(.809,top+.29),(.667,top+.445))
    for (a,h),(b,m) in zip(levels,levels[1:]):
        outline,inner=ring_outline(a),ring_outline(b)
        for i in range(8):
            j=(i+1)%8
            frame.face([(*outline[i],h),(*inner[i],m),(*inner[j],m),(*outline[j],h)],p.faded_blue)
            patterns.rod((*outline[i],h-.008),(*outline[j],h-.008),.019,p.giltpaint,sides=9)
            u=(outline[i][0]+outline[j][0]+inner[i][0]+inner[j][0])/4
            v=(outline[i][1]+outline[j][1]+inner[i][1]+inner[j][1])/4
            cloud(patterns,(u,v,(h+m)/2-.019),.15,p.giltpaint,facing='ceiling',rotation=i*math.pi/4)
    radius,crown=levels[-1]
    frame.solid_xy(Polygon(ring_outline(radius)),crown,crown+.075,p.faded_blue)
    flower(patterns,0,0,crown-.02,.405,p.old_gold,p.cream)
    frame.finish('御景亭 · 方格天花和四级八方井壁',room)
    patterns.finish('御景亭 · 天花彩纹与花心',room)

    y=.80
    seat.box((0,y-.04,z+.065),(2.28,1.67,.13),p.door)
    seat.box((0,y,z+.464),(1.19,.848,.16),p.lacquer)
    seat.box((0,y-.042,z+.562),(1.10,.753,.068),p.faded_blue)
    for k in (-1,1):
        x=k*.501
        for u in (-.29,.31):
            seat.path([(x,y+u,z+.152),(x*.94,y+u,z+.278),(x,y+u,z+.449)],.061,p.lacquer,sides=11)
        seat.rod((x,y-.33,z+.554),(x*.98,y-.33,z+.793),.028,p.old_gold,sides=12)
        seat.path([(x,y-.37,z+.768),(x*1.04,y-.16,z+.805),(x,y+.34,z+.923)],.044,p.old_gold,sides=13)
        seat.box((x,y+.336,z+.94),(.067,.081,.73),p.old_gold)
    for k in range(11):
        u=(k-5)*.089
        v=z+1.265+.201*(1-(abs(u)/.51)**1.6)
        seat.rod((u,y+.338,z+.625),(u,y+.338,v),.027,p.lacquer,sides=10)
        if k%2==0:
            cloud(seat,(u,y+.299,z+.925),.156,p.old_gold,rotation=k*.63)
    seat.path([(.51*t,y+.338,z+1.263+.216*(1-abs(t)**1.6)) for t in (i/12 for i in range(-12,13))],
              .038,p.old_gold,sides=12)
    seat.box((0,y-.405,z+.418),(1.126,.040,.103),p.old_gold)
    seat.finish('御景亭 · 南向宝座、台座及靠背',room,properties={'model_type':'Typological form; no survey of this object.'})
    return room


def summit_pavilion(site,loc,target,p):
    group=collection('御景亭 · 山顶石台、四柱槅扇和攒尖顶',target)
    group['source_osm_id']=YUJING;group['museum_source']=PAVILION_SOURCE
    b,railing=(loc.batch() for _ in range(2))
    x0,y0,x1,y1=SUMMIT
    outline=box(x0,y0,x1,y1)
    b.solid_xy(outline,SUMMIT_Z-.27,SUMMIT_Z-.058,p.understone)
    laid_pavers(b,outline,SUMMIT_Z,p,course=.544,width=.907)
    for a,c in (((x0+.145,y0+.135),(x1-.145,y0+.135)),((x0+.145,y1-.135),(x1-.145,y1-.135)),
                ((x0+.145,y0+.135),(x0+.145,-.25)),((x0+.145,1.29),(x0+.145,y1-.135)),
                ((x1-.145,y0+.135),(x1-.145,.73)),((x1-.145,2.29),(x1-.145,y1-.135))):
        marble_rail(railing,(a,c),SUMMIT_Z,p,step=1.57)
    loc2=Location.from_map(site,YUJING)
    _,_,w,d,_=rectangle(site.geom(YUJING))
    z=PAVILION_Z
    sat,panels,beam=(loc2.batch() for _ in range(3))
    sat.solid_xy(box(-3.074,-2.974,3.074,2.974),SUMMIT_Z-.003,z-.055,p.stone)
    laid_pavers(sat,box(-3.074,-2.974,3.074,2.974),z,p,course=.552,width=.769)
    sat.box((3.186,0,SUMMIT_Z+.067),(.262,1.71,.134),p.stone)
    halfw,halfd=2.66,2.55
    for x in (-halfw,halfw):
        for y in (-halfd,halfd):
            post=loc2.batch()
            post.box((x,y,z+.143),(.58,.57,.286),p.stone)
            post.box((x,y,z+1.561),(.404,.407,2.57),p.red)
            post.box((x,y,z+2.86),(.462,.464,.218),p.faded_blue)
            post.finish('御景亭 · 方檐柱 %.2f %.2f'%(x,y),group,properties={'post_component':1})
    for side in (-1,1):
        for across in (False,True):
            a=halfw if across else halfd
            dist=halfd if across else halfw
            yaw=(0 if side<0 else math.pi) if across else side*math.pi/2
            x,y=(0,dist*side) if across else (dist*side,0)
            painted_bay(beam,x,y,z+2.757,a*2-.307,p,yaw=yaw,height=.427)
            for i in range(7):
                u=(i-3)*a/3
                bracket(beam,x+math.cos(yaw)*u,y+math.sin(yaw)*u,z+3.015,yaw,p)
            if not across and side>0:
                dw=(a*2-.32)/4
                for i in range(4):
                    u=(i-1.5)*dw
                    if i not in (1,2):
                        diamond_panel(panels,x,y+u,z+.05,dw-.016,2.49,p,yaw)
                        continue
                    sign=1 if i==1 else -1
                    hinge=u-sign*(dw-.016)*.5
                    leaf=Batch(loc2.world(x,y+hinge),loc2.yaw+yaw+sign*1.48)
                    diamond_panel(leaf,sign*(dw-.016)*.5,0,z+.05,dw-.016,2.49,p,0)
                    leaf.finish(f'御景亭 · 东面可开启槅扇 {i}',group,properties={
                        'closed_world_yaw_rad':loc2.yaw+yaw,'open_for_viewing':True})
                continue
            for i in range(4):
                u=(i-1.5)*(a*2-.32)/4
                diamond_panel(panels,x+math.cos(yaw)*u,y+math.sin(yaw)*u,z+.05,(a*2-.37)/4,2.49,p,yaw)
    b.finish('御景亭 · 山顶白石台盘和外圈墁地',group)
    railing.finish('御景亭 · 可编辑的峰顶白石栏板',group)
    sat.finish('御景亭 · 独立小台基',group)
    panels.finish('御景亭 · 四面红漆菱花槅扇',group)
    beam.finish('御景亭 · 檐枋、石青地与麻叶斗栱',group)
    swept_roof('御景亭 绿琉璃黄剪边',group,p,origin=loc2.world(),yaw=loc2.yaw,width=w,depth=d,eave=z+3.698,rise=1.601,
               kind='pyramid',tiles=True,pitch=.195,beasts=3,green=True,border_glaze=p.tiles[1],detail=2,pyramid_finial=False,eave_lift=.427)
    roof_top=z+5.299
    finial=loc2.batch()
    finial.lathe(0,0,((.374,roof_top-.046),(.353,roof_top+.08),(.334,roof_top+.141),(.261,roof_top+.20),
                      (.255,roof_top+.282),(.289,roof_top+.322),(.244,roof_top+.367),(.237,roof_top+.443),
                      (.299,roof_top+.511),(.328,roof_top+.663),(.297,roof_top+.807),(.223,roof_top+.895),
                      (.111,roof_top+.936),(.005,roof_top+.951)),p.old_gold,sides=60)
    finial.finish('御景亭 · 旋制鎏金宝顶',group)
    plaque(loc2,group,'御景亭',0,-halfd-.34,z+2.815,.408,.683,p,
           ('north_yujing_plaque.jpg','https://img.dpm.org.cn/Uploads/Picture/2020/04/17/s5e998c8cb3f9d.jpg'),gilded=True)
    summit_room(loc2,group,p,z)
    return group


def build_rockery(site,loc,target,base):
    p=rock_materials(base)
    group=collection('堆秀山与御景亭 · 叠石、双磴道及山顶亭',target)
    group['museum_source']=ROCK_SOURCE
    rocks=collection('堆秀山 · 可编辑的逐件叠石',group)
    core(loc,site,rocks,p)
    pieces,coords=rock_objects(loc,rocks,p)
    pine(loc,group)
    creepers(loc,group,rocks,p)
    west=make_flight(loc,group,p,WEST,'西')
    east=make_flight(loc,group,p,EAST,'东')
    interior=grotto(loc,group,p)
    for side in (-1,1):
        stone_fountain(loc,group,p,side)
    summit=summit_pavilion(site,loc,group,p)
    porch=loc.batch();border=loc.batch()
    ground=box(-9.76,-11.31,9.62,-7.45)
    laid_pavers(porch,ground,.043,p,course=.49,width=.95)
    marble_rail(border,((-9.48,-8.503),(-1.21,-8.503)),.045,p,step=1.37)
    marble_rail(border,((1.35,-8.503),(9.51,-8.503)),.045,p,step=1.36)
    porch.finish('堆秀山 · 山脚南面青石行道',group)
    border.finish('堆秀山 · 山下白石短栏',group)
    report={'collection':group.name,'sources':{'rockery':ROCK_SOURCE,'pavilion':PAVILION_SOURCE,
           'rockery_archival_article':ROCK_ARTICLE,'garden_situation_plan':GARDEN_SOURCE},
            'mapped_osm_rockery':DUIXIU,'mapped_osm_pavilion':YUJING,'documented_summit_height_approx_m':10.,
            'model_summit_platform_z_m':SUMMIT_Z,'individual_limestone_objects':len(pieces),
            'reusable_closed_rock_forms':11,'west_flights':west,'east_flights':east,'grotto':interior.name,
            'summit_pavilion':summit.name,'form_confidence':'Mapped outline and recorded features; individual stones, cave section and paths are interpreted from references.'}
    return group,report
