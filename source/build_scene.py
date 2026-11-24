"""Build, save, export and really render the editable Forbidden City scene.

Blender 4.5: --background --factory-startup --python-exit-code 1 --python
build_scene.py -- --preview
Use render_scene.py for subsequent views without rebuilding the meshes.
"""
from pathlib import Path
import argparse
import json
import math
import random
import sys
import time

import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from shapely import constrained_delaunay_triangles, make_valid
from shapely.geometry import Polygon, LineString, Point, box
from shapely.affinity import rotate, translate
from shapely.ops import unary_union
from pyproj import Transformer
from mesh_tools import Batch, collection, polygons, line_boxes
from palace_materials import palette
from palace_architecture import hall, railing, stairs, arch_block, bronze_lion, ritual_vessel, corner_tower, meridian_platform
from osm_site import Site, tags, number, rectangle, E0, N0, ANGLE, CA, SA
from wenyuan_reconstruction import REF as WENYUAN_OSM_ID, build_wenyuan
from garden_bridge_pavilions import STUDIES, build_pavilion, garden_materials, plan_from_map
from garden_context import HALLS, garden_context

ROOT=Path(__file__).resolve().parents[1]
RENDERS=ROOT/'renders';EXPORTS=ROOT/'exports'
BLEND=ROOT/'The_Forbidden_City_1to1.blend'
random.seed(20261119)
T0=time.time()


def log(message):
    print('[PALACE %6.1fs] %s'%(time.time()-T0,message),flush=True)


def to_local(g,x,y,yaw):
    return rotate(translate(g,-x,-y),-yaw,origin=(0,0),use_radians=True)


def local_roof(batch,geom,eave,rise,pal,*,kind='hip',grey=False,green=False,way=0,direction=None):
    """Clip curved roof facets to the actual footprint; preserve irregular outlines."""
    x,y,W,D,yaw=rectangle(geom)
    if min(W,D)<.15:
        return
    shape=to_local(geom,x,y,yaw)
    hw,hd=W/2,D/2;rh=max(0,hw-hd*.78)
    if kind=='pyramid':rh=0
    if kind=='gable':rh=hw
    color=pal.grey if grey else pal.green if green else pal.roof
    edge=pal.grey if grey else pal.green if green else pal.tiles[1]
    ct,st=math.cos(yaw),math.sin(yaw)
    def point(a,b,z):return (x+a*ct-b*st,y+a*st+b*ct,z)
    def value(a,b):
        if kind=='skillion':
            # OSM roof:direction is compass bearing of downslope, in true north.
            d=(math.radians(direction if direction is not None else 180)+ANGLE+yaw)
            vx,vy=math.sin(d),math.cos(d)
            span=abs(vx)*hw+abs(vy)*hd
            t=.5-(a*vx+b*vy)/(2*span or 1)
        elif kind=='gable':t=1-abs(b)/hd
        else:t=min(1-abs(b)/hd,(hw-abs(a))/(hw-rh or 1))
        t=max(0,min(1,t))
        return eave+rise*(.16*t+.84*t**1.82)
    if kind=='skillion':
        # Linear roof slabs in source staircases and lower eaves.
        if direction is None:direction=180
        facets=[shape]
        for tr in constrained_delaunay_triangles(shape).geoms:
            pp=list(tr.exterior.coords)[:3]
            batch.face([point(a,b,value(a,b)) for a,b in pp],color,way=way,uv=[(a,b) for a,b in pp])
    else:
        n=8 if min(W,D)>4 else 4
        for side in range(2 if kind=='gable' else 4):
            for i in range(n):
                t0,t1=i/n,(i+1)/n
                def span(t):return hw+(rh-hw)*t
                if side<2:
                    s=-1 if side==0 else 1
                    pts=[(-span(t0),s*hd*(1-t0)),(span(t0),s*hd*(1-t0)),
                         (span(t1),s*hd*(1-t1)),(-span(t1),s*hd*(1-t1))]
                else:
                    s=-1 if side==2 else 1
                    pts=[(s*span(t0),-hd*(1-t0)),(s*span(t0),hd*(1-t0)),
                         (s*span(t1),hd*(1-t1)),(s*span(t1),-hd*(1-t1))]
                facet=make_valid(Polygon(pts)).intersection(shape)
                for p in polygons(facet):
                    for tr in constrained_delaunay_triangles(p).geoms:
                        pp=list(tr.exterior.coords)[:3]
                        vv=[point(a,b,value(a,b)) for a,b in pp]
                        if (Vector(vv[1])-Vector(vv[0])).cross(Vector(vv[2])-Vector(vv[0])).z<0:vv.reverse();pp.reverse()
                        batch.face(vv,color,way=way,uv=[(a,b) for a,b in pp])
        # Principal ridge is a distinct solid; restrained ornament for distant roofs.
        if kind!='pyramid' and rh>.1:
            ridge=LineString([(-rh,0),(rh,0)]).intersection(shape)
            for line in (list(ridge.geoms) if hasattr(ridge,'geoms') else [ridge]):
                if line.geom_type=='LineString' and line.length>.15:
                    batch.rod(point(*line.coords[0],eave+rise+.07),point(*line.coords[-1],eave+rise+.07),.09,edge,sides=6)
        elif kind=='pyramid':
            batch.rod(point(0,0,eave+rise),point(0,0,eave+rise+.6),.14,pal.gold,r1=.02,sides=8)
    for p in polygons(shape):
        pp=list(p.exterior.coords)
        for a,b in zip(pp,pp[1:]):
            if kind=='gable' and a[1]*b[1]<-1e-6:
                cuts=[i/8 for i in range(9)]
                cuts=sorted(set(cuts+[-a[1]/(b[1]-a[1])]))
            else:cuts=[0.,1.]
            pts=[(a[0]+f*(b[0]-a[0]),a[1]+f*(b[1]-a[1])) for f in cuts]
            for start,end in zip(pts,pts[1:]):
                batch.face([point(*start,eave-.06),point(*end,eave-.06),point(*end,value(*end)+.015),point(*start,value(*start)+.015)],
                           pal.door if kind=='gable' else edge,way=way)


def terrain(site,pal,parent,*, detailed_pools=()):
    ground=collection('01 · 场地 / metric site and water',parent)
    moat=site.geom('4845030').difference(site.boundary.buffer(-.4))
    river_parts=[]
    for ref,w in site.ways.items():
        t=tags(w)
        if ref=='4845030' or t.get('natural')!='water':continue
        g=site.geom(ref)
        if g.geom_type in ('Polygon','MultiPolygon') and site.boundary.intersects(g):
            river_parts.append((ref,g.intersection(site.boundary)))
    river=unary_union([g for _,g in river_parts])
    extent=box(-499,-614,499,614)
    forecourt=box(-79,-607,77,-478).difference(moat)
    banks=extent.difference(unary_union([site.boundary,moat,forecourt]))
    b=Batch();b.box((0,0,-5.5),(1000,1230,4.0),pal.slab)
    b.solid_xy(banks,-3.5,-.15,pal.bank,top=pal.grass)
    b.solid_xy(site.boundary.difference(river),-3.5,0,pal.bank,top=pal.court)
    b.solid_xy(forecourt.difference(site.boundary),-3.5,0,pal.bank,top=pal.path)
    b.solid_xy(box(-5.7,-605,1.9,-456).difference(moat),.005,.032,pal.path,bottom=False)
    b.finish('场地与城内铺地 · 地面按水域开口',ground)
    water=Batch()
    water.solid_xy(moat,-3.0,-.72,pal.bank,top=pal.water)
    for p in polygons(moat):
        for line in [p.exterior,*p.interiors]:
            line_boxes(water,list(line.coords),-.34,-.11,.48,pal.bank)
    water.finish('筒子河 · 原始水面轮廓及石驳岸',ground,properties={'osm_way':'4845030'})
    paving=Batch();streams=Batch();parks=Batch()
    generic_water=unary_union([g for ref,g in river_parts if ref not in detailed_pools])
    streams.solid_xy(generic_water,-3.0,-.74,pal.bank,top=pal.stream)
    for p in polygons(generic_water):
        line_boxes(streams,list(p.exterior.coords),-1.2,.16,.45,pal.bank)
    rail=Batch()
    crossings=unary_union([site.geom(ref).buffer(3.8) for ref in ('41439019','41439020','41439021','41439022','41439023')])
    for p in polygons(site.geom('638204006')):
        railing(rail,LineString(p.exterior.coords),.14,pal,spacing=2.05,exclude=crossings)
    rail.finish('内金水河 · 石栏板、望柱和桥口',ground)
    counts={'paths':0,'water':len(river_parts),'river_surface_m2':round(river.area,2)}
    for ref,w in site.ways.items():
        t=tags(w)
        if not any(k in t for k in ('highway','waterway','natural','landuse','leisure')):continue
        g=site.geom(ref)
        if g.is_empty or not site.boundary.buffer(10).intersects(g):continue
        if t.get('highway') in ('footway','pedestrian','path','service','steps') and 'bridge' not in t and 'tunnel' not in t:
            width=number(t.get('width'),1.6 if t.get('highway')=='path' else 2.8)
            pp=g if t.get('area')=='yes' and g.geom_type in ('Polygon','MultiPolygon') else g.buffer(width/2,cap_style=2)
            paving.solid_xy(pp.intersection(site.boundary).difference(river),.006,.022,pal.path,way=int(ref),bottom=False)
            counts['paths']+=1
        elif t.get('landuse') in ('grass','forest') or t.get('natural') in ('wood','scrub'):
            if g.geom_type in ('Polygon','MultiPolygon'):
                parks.solid_xy(g.intersection(site.boundary),.025,.04,pal.grass,way=int(ref),bottom=False)
    paving.finish('石板路 · mapped circulation',ground)
    streams.finish('内金水河与池塘 · mapped water',ground)
    parks.finish('苑地 · mapped planted beds',ground)
    return counts


CUSTOM_RELS=['8854043','8854044','8854310','8854434','8854352','8854507',
             '8860936','8860927','8861202','8851737','8859415','8849989',
             '8858781','8858912','8858938','8858328','8858329','8858355','8858356']


def generic_buildings(site,pal,parent,*, detailed=()):
    group=collection('02 · 宫院群 / individual source footprints and roof parts',parent)
    skip={WENYUAN_OSM_ID,*detailed}
    for rid in CUSTOM_RELS:skip.update(site.members(rid))
    skip.update(('638156455','638156470','638156753','638156765','638206921','638206922','638206928','638206935'))
    # Corner tower footprints are superseded by the separate cross-plan assemblies.
    corners=[site.nodes[i] for i in ('273355449','273355450','273355451','273355452')]
    def in_site(g):
        return (g.geom_type in ('Polygon','MultiPolygon') and not g.is_empty and g.area>.12
                and site.boundary.buffer(6).contains(g.representative_point())
                and all(g.centroid.distance(Point(c))>15 for c in corners))
    outlines=set();ring_members=set()
    for rid,r in site.rels.items():
        t=tags(r)
        if t.get('type')=='building':
            for m in r.findall('member'):
                if m.get('role')=='outline':
                    if m.get('type')=='way':outlines.add(m.get('ref'))
                    elif m.get('type')=='relation':outlines.update(site.members(m.get('ref')))
        elif t.get('type')=='multipolygon' and ('building' in t or 'building:part' in t):
            ring_members.update(site.members(rid))
    entries=[]
    for ref,w in site.ways.items():
        t=tags(w)
        if ref in skip or ref in outlines or ref in ring_members or not ('building' in t or 'building:part' in t):continue
        g=site.geom(ref)
        if in_site(g):entries.append((ref,t,g))
    for rid,r in site.rels.items():
        t=tags(r)
        if t.get('type')!='multipolygon' or not ('building' in t or 'building:part' in t):continue
        if site.members(rid).intersection(skip):continue
        g=site.geom(rid,'relation')
        if in_site(g):entries.append((rid,t,g))
    count=0
    for ref,t,g in entries:
        b=Batch();is_part='building:part' in t
        material=t.get('building:material','')
        stone=material=='stone' or t.get('roof:material')=='stone'
        wall=t.get('building')=='wall'
        roof=t.get('roof:shape')
        mn=number(t.get('min_height'))
        _,_,W,D,_=rectangle(g)
        h=number(t.get('height'),max(4.2,min(10,D*.45+4)))
        grey=any(q in t.get('roof:colour','').lower() for q in ('gray','grey','#8080'))
        green='green' in t.get('roof:colour','').lower()
        if stone:
            b.solid_xy(g,mn,h,pal.marble_dark,top=pal.marble,way=int(ref))
        elif is_part and not roof:
            b.solid_xy(g,mn,h,pal.door if material=='wood' else pal.paint,way=int(ref))
        elif roof=='skillion' and is_part:
            rh=number(t.get('roof:height'),h-mn)
            local_roof(b,g,h-rh,rh,pal,kind='skillion',grey=grey,green=green,way=int(ref),direction=number(t.get('roof:direction'),180))
        else:
            kind={'gabled':'gable','hipped':'hip','pyramidal':'pyramid'}.get(roof,'hip' if D>8 and W/D<4 else 'gable')
            rh=number(t.get('roof:height'),min(5.5,max(.65,D*.36)))
            if wall:rh=min(rh,.6);h=min(h,5.2)
            eave=max(mn+.12,h-rh)
            if not is_part or eave>mn+.2:
                b.solid_xy(g,mn,eave,pal.masonry if wall else pal.paint,way=int(ref))
            if roof!='flat':
                local_roof(b,g,eave,rh,pal,kind=kind,grey=grey or wall,green=green,way=int(ref))
            else:b.solid_xy(g,mn,h,pal.bank,way=int(ref))
            if not is_part and not wall and W>5 and D>3:
                # Simple window rhythm follows actual building orientation.
                x,y,W,D,yaw=rectangle(g);ct,st=math.cos(yaw),math.sin(yaw)
                for sy in (-1,1):
                    n=max(1,round(W/3.2))
                    for i in range(n):
                        xx=-W/2+(i+.5)*W/n;yy=sy*(D/2+.015)
                        px,py=x+xx*ct-yy*st,y+xx*st+yy*ct
                        if g.buffer(.10).covers(Point(px,py)):
                            b.box((px,py,max(mn+.7,eave*.50)),(min(1.4,W/n*.52),.10,max(.3,min(1.8,eave-mn-1))),pal.door,yaw=yaw)
        title=t.get('name') or ('构件' if is_part else '院落建筑')
        obj=b.finish(title+' · OSM '+ref,group,properties={'osm_id':ref,'source_height':t.get('height','inferred'),
            'accuracy':'Contributed footprint; untagged heights and roof details are interpreted'})
        if obj:count+=1
    log('Generic source meshes: %d'%count)
    return count


def three_hall_terrace(site,pal,parent):
    group=collection('03 · 三台 / continuous triple marble terrace',parent)
    # Union the full middle platform with the separately mapped south/north aprons.
    centre=[site.geom(i,'relation') for i in ('8854307','8854308','8854309')]
    south=[site.geom(i) for i in ('638449448','638449444','638449443')]
    north=[site.geom(i) for i in ('638467898','638467899','638467900')]
    halls=unary_union([site.geom('638449447'),site.geom('638473471'),site.geom('8854350','relation')])
    courses=[make_valid(unary_union([centre[i],south[i],north[i],halls])) for i in range(3)]
    stair_specs=[]
    for rid in ('8854044','8854310','8854434'):
        for ref,t,g in site.parts(rid):
            if t.get('roof:shape')!='skillion':continue
            x,y,W,D,yaw=rectangle(g)
            direction=number(t.get('roof:direction'),180)
            # Downslope direction in the local palace frame.
            a=math.radians(direction)+ANGLE;u=Vector((math.sin(a),math.cos(a)))
            span=max(abs((p[0]-x)*u.x+(p[1]-y)*u.y) for p in g.exterior.coords)*2
            width=g.area/span
            h=number(t.get('height'))*8.13/9;rh=number(t.get('roof:height'))*8.13/9
            lo=(x+u.x*span/2,y+u.y*span/2);hi=(x-u.x*span/2,y-u.y*span/2)
            stair_specs.append((lo,hi,width,max(0,h-rh),h,ref))
    exclusion=unary_union([LineString((a,b)).buffer(w/2+.45) for a,b,w,_,_,_ in stair_specs])
    for i,shape in enumerate(courses):
        z=(i+1)*2.71;b=Batch();b.solid_xy(shape,i*2.71,z,pal.marble_dark,top=pal.terrace_floor)
        # The cornice and base mouldings follow every mapped polygon edge.
        for p in polygons(shape):
            coords=list(p.exterior.coords)
            line_boxes(b,coords,z-.18,z+.02,.24,pal.marble)
            line_boxes(b,coords,i*2.71+.08,i*2.71+.27,.18,pal.marble)
            for a,c in zip(coords,coords[1:]):
                railing(b,LineString((a,c)),z,pal,exclude=exclusion,drains=True)
        b.finish('第 %d 层 · %.2f m'%(i+1,z),group,properties={'platform_top_m':z,'source':'OSM compound terrace plan; 8.13 m total derived from Palace Museum hall heights'})
    b=Batch()
    for a,c,w,z0,z1,ref in stair_specs:
        stairs(b,a,c,w,z0,z1,pal,central=ref in ('638449442','638467897'))
    b.finish('三台所有已标注踏道 · solid stone steps',group)
    return len(stair_specs)


def important_halls(site,pal,parent):
    group=collection('04 · 中轴殿宇 / principal ceremonial halls',parent)
    specs=[
        # Name, timber source, width/depth, floor, lower eave, upper eave, rise, bays, kind.
        ('太和殿','638449346',57.8,30.8,8.13,18.7,22.4,9.25,11,'hip'),
        ('中和殿','638463064',20.8,20.8,8.13,16.1,None,5.1,3,'pyramid'),
        ('保和殿','638473411',45.2,21.5,8.13,17.0,20.8,6.4,9,'xieshan'),
        ('乾清宫','638981318',46.0,24.1,3.0,11.3,14.7,6.4,9,'hip'),
        ('交泰殿','638981203',17.0,17.0,3.0,11.4,None,6.0,3,'pyramid'),
        ('坤宁宫','639012194',43.4,18.8,3.0,10.2,14.1,5.2,9,'hip'),
        ('太和门','638308747',47.0,20.4,6.0,14.9,18.4,6.6,9,'xieshan'),
        ('乾清门','638807675',27.6,13.7,1.4,8.3,None,5.0,5,'xieshan'),
    ]
    for name,ref,W,D,f,e,ue,r,bays,kind in specs:
        x,y,_,_,yaw=rectangle(site.geom(ref))
        if name=='中和殿' or name=='交泰殿':yaw=0.008
        if f<7:
            platform=Batch((x,y,0),yaw)
            platform.box((0,0,f/2),(W+7,D+7,f),pal.marble_dark)
            platform.box((0,0,f-.06),(W+7.4,D+7.4,.15),pal.marble)
            railing(platform,LineString([(-W/2-3.5,-D/2-3.5),(-5,-D/2-3.5)]),f,pal)
            railing(platform,LineString([(5,-D/2-3.5),(W/2+3.5,-D/2-3.5)]),f,pal)
            stairs(platform,(0,-D/2-3.5-f*2),(0,-D/2-3.5),8,0,f,pal)
            for sx in (-1,1):
                railing(platform,LineString([(sx*(W/2+3.5),-D/2-3.5),(sx*(W/2+3.5),D/2+3.5)]),f,pal)
            platform.finish(name+' · stone platform and access',group)
        hall(name,group,pal,origin=(x,y,0),yaw=yaw,width=W,depth=D,floor=f,eave=e,upper_eave=ue,
             rise=r,bays=bays,deep_bays=5 if name=='太和殿' else 3,kind=kind,tiles=True,
             beasts=10 if name=='太和殿' else 7,plaque=name,open_gate=name in ('太和门','乾清门'),
             roof_width=67.4 if name=='太和殿' else None,roof_depth=40.0 if name=='太和殿' else None,
             post_radius=.53 if name=='太和殿' else .36,interior_posts=name=='太和殿',
             terminal_height=3.40 if name=='太和殿' else None)
        log('Detailed hall built: '+name)
    b=Batch()
    for x in (-31,27):
        bronze_lion(b,x,-332,0,pal,scale=1.22)
    # Bronze vats and ritual furniture on the Taihe apron.
    for x,y in ((-26,-121),(22,-121),(-38,-139),(34,-139)):
        ritual_vessel(b,x,y,8.13,pal)
    for x in (-27,23):
        b.lathe(x,-130,((.90,8.13),(.90,8.45),(.65,8.60),(.65,8.80)),pal.marble,sides=20)
        # A bronze crane with separate long legs, curved neck, beak and wings.
        for off in (-.17,.17):b.rod((x+off,-130,8.8),(x+off,-130,10.1),.045,pal.bronze,sides=8)
        b.ellipsoid((x,-130,10.28),(.30,.62,.31),pal.bronze,sides=12,rings=6)
        b.path([(x,-130.35,10.4),(x,-130.55,10.95),(x,-130.45,11.55),(x,-130.77,11.75)],.08,pal.bronze,sides=8)
        b.rod((x,-130.78,11.75),(x,-131.25,11.67),.075,pal.bronze,r1=.005,sides=8)
    b.finish('陈设 · bronze lions, cranes and ritual vessels',group)


def perimeter_and_gates(site,pal,parent):
    group=collection('05 · 城垣四门与四角楼 / walls and gateways',parent)
    platform=site.geom('638157005')
    gates=[Point(p).buffer(r) for p,r in (((0,477),25),((-374,-351),24),((375,-348),25))]
    gaps=unary_union([platform.buffer(-.17),*gates])
    b=Batch()
    for wall_index,coords in enumerate(site.walls):
        line=LineString(coords).difference(gaps)
        if wall_index==0:
            line=line.difference(box(-64.0,-568,60.6,-480))
        lines=list(line.geoms) if hasattr(line,'geoms') else [line]
        for ln in lines:
            pts=list(ln.coords)
            for a,c in zip(pts,pts[1:]):
                dx,dy=c[0]-a[0],c[1]-a[1];L=math.hypot(dx,dy);nx,ny=-dy/L,dx/L
                verts=[(p[0]+s*nx*w,p[1]+s*ny*w,z) for z,w in ((0,4.31),(9.9,3.33)) for p,s in ((a,-1),(c,-1),(c,1),(a,1))]
                b.add(verts,[(3,2,1,0),(4,5,6,7)],pal.masonry)
                b.add(verts,[(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],pal.paint if wall_index==0 else pal.masonry)
                b.box(((a[0]+c[0])/2,(a[1]+c[1])/2,1.0),(L,8.5,2.0),pal.masonry,yaw=math.atan2(dy,dx))
                inside=1 if site.boundary.covers(Point((a[0]+c[0])/2+nx*5,(a[1]+c[1])/2+ny*5)) else -1
                yaw=math.atan2(dy,dx)
                for offset,z,h,mat in ((inside*3.06,10.27,.74,pal.masonry),(-inside*3.06,10.17,.54,pal.masonry),
                                       (inside*3.06,10.66,.11,pal.grey_clay)):
                    b.box(((a[0]+c[0])/2+nx*offset,(a[1]+c[1])/2+ny*offset,z),(L,.38,h),mat,yaw=yaw)
                n=max(1,round(L/2.05))
                for i in range(n):
                    t=(i+.5)/n;x=a[0]+dx*t-inside*nx*3.06;y=a[1]+dy*t-inside*ny*3.06
                    b.box((x,y,10.83),(1.13,.37,.70),pal.masonry,yaw=yaw)
                    b.box((x,y,11.2),(1.21,.44,.08),pal.bank,yaw=yaw)
    b.finish('城墙 · tapered sections, wall walks and crenels',group,properties={'height_m':9.9,'base_width_m':8.62,'top_width_m':6.66})
    meridian_platform('午门 · 凹形墩台与五门洞',group,pal,platform)
    # Official bay count and plan dimensions, with eaves fitted to photographs.
    hall('午门 · 正楼',group,pal,origin=(-1.94,-470.29,0),yaw=-.010,width=60.05,depth=25.0,floor=12,
         eave=21.5,upper_eave=25.5,rise=8.1,bays=9,deep_bays=5,kind='hip',beasts=9,plaque='午门',open_gate=False)
    for ref in ('638156655','638156665','638156677','638156830'):
        x,y,_,_,_=rectangle(site.geom(ref))
        hall('午门 · 阙亭 '+ref,group,pal,origin=(x,y,0),yaw=-.010,width=14.6,depth=14.4,floor=12,
             eave=20.0,upper_eave=23.05,rise=6.3,bays=3,deep_bays=3,kind='pyramid',beasts=5)
    for cx,cy in ((48.11,-512.18),(-54.0,-511.08)):
        hall('午门 · 雁翅廊',group,pal,origin=(cx,cy,0),yaw=math.pi/2-.010,width=67.0,depth=9.3,floor=12,
             eave=17.6,rise=3.8,bays=13,deep_bays=1,kind='gable',beasts=0,open_gate=True,roof_width=67.6,roof_depth=13.1)
    for name,ref,yaw in (('神武门','638741729',.008),('东华门','638768064',math.pi/2+.008),('西华门','638765805',math.pi/2+.008)):
        x,y,_,_,_=rectangle(site.geom(ref))
        arch_block(name+' · 三门洞',group,pal,origin=(x,y,0),yaw=yaw,width=51,depth=24,height=9.9,
                   openings=[(-12,4.2,5.5),(0,4.6,6.2),(12,4.2,5.5)])
        hall(name,group,pal,origin=(x,y,0),yaw=yaw,width=40,depth=18.9,floor=9.9,
             eave=17.1,upper_eave=21.3,rise=5.0,bays=9,deep_bays=3,kind='hip',beasts=7,plaque=name)
    for name,base,floor in (('西北角楼','638703834','638703811'),('东北角楼','638703759','638703732'),
                            ('东南角楼','638700731','638700506'),('西南角楼','638700402','638700432')):
        corner_tower(name,group,pal,site.geom(base),site.geom(floor))
    for ref in ('42740554','42740573'):
        x,y,w,d,yaw=rectangle(site.geom(ref))
        hall('筒子河 · 灰瓦临水廊 '+ref,group,pal,origin=(x,y,0),yaw=yaw,width=w-.6,depth=d-.8,floor=.52,
             eave=5.1,rise=2.5,bays=7,deep_bays=5,kind='hip',beasts=0,open_gate=True,
             roof_width=w+1.6,roof_depth=d+1.6,post_radius=.18,roof_grey=True)


def bridges_and_trees(site,pal,parent):
    group=collection('06 · 石桥与苑树 / bridges and mapped trees',parent)
    for ref in ('41439019','41439020','41439021','41439022','41439023'):
        pp=site.points(ref);a=Vector(pp[0]);c=Vector(pp[-1]);mid=(a+c)/2
        L=(c-a).length;yaw=math.atan2(c.y-a.y,c.x-a.x)
        width=6.8 if abs(mid.x)<8 else 4.1
        arch_block('内金水桥 '+ref,group,pal,origin=(mid.x,mid.y,-2.3),yaw=yaw,width=L,depth=width,height=3.4,
                   openings=[(0,L*.70,2.9)],rise=2.05,stone=True)
        b=Batch((mid.x,mid.y,0),yaw)
        b.box((0,0,1.12),(L+.6,width+.35,.20),pal.marble)
        for sy in (-1,1):railing(b,LineString([(-L/2,sy*width/2),(L/2,sy*width/2)]),1.22,pal,spacing=1.8)
        for sx in (-1,1):stairs(b,(sx*(L/2+3.0),0),(sx*L/2,0),width,0,1.22,pal,handrails=False)
        b.finish('内金水桥 '+ref+' · deck, stairs and balustrades',group)
    # The mapped north access spans the outer moat rather than ending at its bank.
    a,c=[Vector(pt) for pt in (site.points('42501520')[0],site.points('42501520')[-1])]
    mid=(a+c)/2;yaw=math.atan2(c.y-a.y,c.x-a.x);span=(c-a).length+4
    arch_block('神武门外 · 筒子河桥身',group,pal,origin=(mid.x,mid.y,-2.25),yaw=yaw,width=span,depth=11.6,height=2.15,
               openings=[(x,12.9,1.91) for x in (-15.0,0,15.0)],rise=1.6,stone=True)
    crossing=Batch((mid.x,mid.y,0),yaw)
    crossing.box((0,0,.01),(span,12.1,.24),pal.path)
    for sign in (-1,1):railing(crossing,LineString([(-span/2,sign*5.9),(span/2,sign*5.9)]),.14,pal,spacing=2.05)
    crossing.finish('神武门外 · 筒子河桥面与石栏',group,properties={'osm_way':'42501520','form':'Interpreted arch and railing detail'})
    trees=Batch();count=0
    positions=[]
    for nid,t in site.node_tags.items():
        if t.get('natural')=='tree' and site.boundary.buffer(18).covers(Point(site.nodes[nid])):positions.append((*site.nodes[nid],nid))
    for x,y,nid in positions:
        h=random.uniform(6.0,12.0);r=h*.24;count+=1
        trees.rod((x,y,0),(x,y,h*.77),.22,pal.trunk,r1=.08,sides=8)
        for k in range(7):
            a=k*2.399;zz=h*(.35+k*.065);reach=r*(1-k*.06)
            xx=x+math.cos(a)*reach*.63;yy=y+math.sin(a)*reach*.63
            trees.beam((x,y,zz*.8),(xx,yy,zz),.12,.10,pal.trunk)
            trees.ellipsoid((xx,yy,zz+reach*.24),(reach*.88,reach*.77,reach*.65),pal.leaves[k%4],sides=11,rings=6,jitter=.16,rng=random)
        trees.ellipsoid((x,y,h*.85),(r*.63,r*.65,h*.23),pal.leaves[1],sides=11,rings=6,jitter=.12,rng=random)
    trees.finish('苑树 · individual mapped positions',group,properties={'tree_count':count,'canopies':'Interpreted mature evergreen forms; not individual botanical scans'})
    # Riverbank vegetation follows the north and east strips visible in aerial imagery.
    willows=Batch();moat=site.geom('4845030');pavilions=[site.geom(ref).buffer(3) for ref in ('42740554','42740573')]
    stream_bank=[(x,484.9+(x+375)*.008) for x in list(range(-336,-26,8))+list(range(32,356,8))]
    stream_bank.extend((382.8,y) for y in range(-305,469,11))
    planted=0
    for x,y in stream_bank:
        x+=random.uniform(-1.5,1.5);y+=random.uniform(-1.3,1.3);p=Point(x,y)
        if site.boundary.buffer(5.2).covers(p) or moat.buffer(2).covers(p) or any(g.covers(p) for g in pavilions):continue
        h=random.uniform(7.1,11.7);z=-.13;planted+=1
        sgn=random.choice((-1,1));c=Vector((x+sgn*.4,y+.32,z+h*.46))
        willows.rod((x,y,z),c,h*.036,pal.trunk,r1=h*.022,sides=9)
        for branch in range(11):
            a=branch*2.399+random.uniform(-.27,.27);u=Vector((math.cos(a),math.sin(a),0))
            r=h*random.uniform(.20,.38);top=c+r*.54*u+Vector((0,0,h*.44))
            end=top+.48*r*u-Vector((0,0,h*.19))
            willows.path([c,top,end],.061,pal.trunk,sides=6)
            for leaf in range(3):
                v=top.lerp(end,(leaf+.6)/3)+Vector((random.uniform(-.8,.8),random.uniform(-.8,.8),0))
                willows.ellipsoid((v.x,v.y,v.z-h*.077),(r*.35,r*.31,h*.135),pal.willow[(leaf+branch)%len(pal.willow)],
                                   sides=8,rings=5,jitter=.23,rng=random,yaw=a)
    willows.finish('筒子河岸柳 · 航拍植被带推定',group,properties={'indicative_tree_count':planted})
    return count


def aerial_reference(site,parent):
    image_path=ROOT/'source/textures/forbidden_city_georeferenced_aerial.jpg'
    if not image_path.is_file():
        return
    group=collection('90 · 参考图层 / hidden georeferenced aerial',parent)
    img=bpy.data.images.load(str(image_path),check_existing=True)
    material=bpy.data.materials.new('参考影像 · Esri World Imagery');material.use_nodes=True
    tex=material.node_tree.nodes.new('ShaderNodeTexImage');tex.image=img
    material.node_tree.links.new(tex.outputs['Color'],material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    # Plane is hidden for all final renders and exports; the entire visible palace is mesh geometry.
    trans=Transformer.from_crs(3857,32650,always_xy=True)
    bounds=(12955600,4852970,12957350,4854720);x0,y0,x1,y1=bounds
    v=[]
    for e,n in (trans.transform(x0,y0),trans.transform(x1,y0),trans.transform(x1,y1),trans.transform(x0,y1)):
        v.append((CA*(e-E0)+SA*(n-N0),-SA*(e-E0)+CA*(n-N0),-.01))
    b=Batch();b.face(v,material,uv=[(0,0),(1,0),(1,1),(0,1)])
    obj=b.finish('参考影像 · 隐藏，非模型替代物',group)
    obj.hide_render=True;obj.hide_set(True);obj['attribution']='Source: Esri, Vantor, Earthstar Geographics, and the GIS User Community'
    group.hide_render=True;group.hide_viewport=True


def camera(name,position,target,lens=50,ortho=None):
    data=bpy.data.cameras.new(name);obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj)
    obj.location=position;obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    data.lens=lens;data.clip_start=.1;data.clip_end=6000
    if ortho:data.type='ORTHO';data.ortho_scale=ortho
    return obj


def lighting():
    scene=bpy.context.scene
    world=bpy.data.worlds.new('北京晴空 · physical sky');scene.world=world;world.use_nodes=True
    sky=world.node_tree.nodes.new('ShaderNodeTexSky');sky.sky_type='NISHITA'
    sky.sun_elevation=math.radians(47);sky.sun_rotation=math.radians(230)
    sky.air_density=1.0;sky.dust_density=.68;sky.ozone_density=1.0;sky.sun_disc=False
    nodes=world.node_tree.nodes;links=world.node_tree.links
    ambient=nodes['Background'];ambient.label='Ambient daylight'
    links.new(sky.outputs['Color'],ambient.inputs['Color']);ambient.inputs['Strength'].default_value=.165
    coords=nodes.new('ShaderNodeTexCoord');sep=nodes.new('ShaderNodeSeparateXYZ')
    links.new(coords.outputs['Normal'],sep.inputs[0])
    height=nodes.new('ShaderNodeMath');height.operation='ABSOLUTE';links.new(sep.outputs['Z'],height.inputs[0])
    gradient=nodes.new('ShaderNodeValToRGB');links.new(height.outputs[0],gradient.inputs[0])
    ramp=gradient.color_ramp;ramp.elements[0].color=(.32,.53,.74,1)
    ramp.elements[1].color=(.032,.14,.39,1);ramp.elements[1].position=.60
    ramp.elements.new(.18).color=(.087,.28,.60,1)
    cloud_noise=nodes.new('ShaderNodeTexNoise');cloud_noise.inputs['Scale'].default_value=8.1
    cloud_noise.inputs['Detail'].default_value=3.4;cloud_noise.inputs['Roughness'].default_value=.59
    stretch=nodes.new('ShaderNodeVectorMath');stretch.operation='MULTIPLY';stretch.inputs[1].default_value=(1,1,3.6)
    links.new(coords.outputs['Normal'],stretch.inputs[0]);links.new(stretch.outputs[0],cloud_noise.inputs['Vector'])
    cloud_tone=nodes.new('ShaderNodeValToRGB');cloud_tone.color_ramp.elements[0].position=.60;cloud_tone.color_ramp.elements[1].position=.78
    links.new(cloud_noise.outputs['Fac'],cloud_tone.inputs[0])
    cloud_mix=nodes.new('ShaderNodeMixRGB');cloud_mix.inputs[2].default_value=(.70,.77,.85,1)
    links.new(cloud_tone.outputs['Color'],cloud_mix.inputs[0]);links.new(gradient.outputs['Color'],cloud_mix.inputs[1])
    background=nodes.new('ShaderNodeBackground');background.name='Camera atmosphere'
    links.new(cloud_mix.outputs[0],background.inputs['Color']);background.inputs['Strength'].default_value=1.0
    ray=nodes.new('ShaderNodeLightPath');mix=nodes.new('ShaderNodeMixShader')
    links.new(ray.outputs['Is Camera Ray'],mix.inputs[0]);links.new(ambient.outputs[0],mix.inputs[1]);links.new(background.outputs[0],mix.inputs[2])
    links.new(mix.outputs[0],nodes['World Output'].inputs['Surface'])
    data=bpy.data.lights.new('日光 · south west','SUN');data.energy=3.1;data.angle=.038
    obj=bpy.data.objects.new('日光 · south west',data);scene.collection.objects.link(obj)
    elevation=math.radians(47);azimuth=math.radians(230)
    sun=Vector((math.cos(elevation)*math.cos(azimuth), math.cos(elevation)*math.sin(azimuth),math.sin(elevation)))
    obj.rotation_euler=(-sun).to_track_quat('-Z','Y').to_euler()
    scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_denoising=True
    scene.cycles.max_bounces=6;scene.cycles.diffuse_bounces=3;scene.cycles.glossy_bounces=3
    scene.cycles.transmission_bounces=3;scene.cycles.transparent_max_bounces=4
    try:
        prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
        for d in prefs.devices:d.use=d.type=='OPTIX'
        if any(d.use for d in prefs.devices):scene.cycles.device='GPU'
    except Exception as exc:log('GPU fallback: '+str(exc))
    scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
    scene.view_settings.exposure=-.04
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
    scene.render.resolution_percentage=100;scene.render.resolution_x=1800;scene.render.resolution_y=1350
    scene.render.film_transparent=False
    scene.render.use_persistent_data=True


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--export',action='store_true')
    parser.add_argument('--garden',action='store_true',help='Build the four detailed northern garden structures and pools.')
    options=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    RENDERS.mkdir(exist_ok=True)
    EXPORTS.mkdir(exist_ok=True)
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    for c in list(bpy.data.collections):
        if c.name=='Collection':bpy.data.collections.remove(c)
    scene=bpy.context.scene;scene.name='紫禁城 · metric architectural reconstruction'
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1.0;scene.unit_settings.length_unit='METERS'
    site=Site();pal=palette();root=collection('紫禁城 · EDITABLE 3D MASTER')
    log('Source loaded; site %.1f square metres'%site.boundary.area)
    garden_ids={s.way for s in STUDIES}|{hall[1] for hall in HALLS} if options.garden else ()
    garden_pools={s.pond for s in STUDIES} if options.garden else ()
    metrics=terrain(site,pal,root,detailed_pools=garden_pools)
    metrics['generic_source_meshes']=generic_buildings(site,pal,root,detailed=garden_ids)
    metrics['terrace_stairs']=three_hall_terrace(site,pal,root)
    important_halls(site,pal,root)
    perimeter_and_gates(site,pal,root);log('Gates, walls and corner towers complete')
    metrics['mapped_trees']=bridges_and_trees(site,pal,root)
    _, metrics['wenyuan']=build_wenyuan(root,pal)
    if options.garden:
        group=collection('御花园 · 浮碧亭与澄瑞亭',root)
        plans=[plan_from_map(site,study) for study in STUDIES]
        materials=garden_materials(pal)
        pavilions=[build_pavilion(study,plan,group,materials) for study,plan in zip(STUDIES,plans)]
        metrics['imperial_garden']={'pavilions':[p.name for p in pavilions],
                                    'context':garden_context(site,plans,group,materials)}
    aerial_reference(site,root);lighting()
    camera('01 · 全城鸟瞰 / overview',(-650,-1030,1250),(0,-3,4),ortho=1670)
    camera('02 · 太和殿 / architectural portrait',(-89,-221,8.3),(-4,-116,15),lens=46)
    camera('03 · 三大殿 / three halls',(-206,-305,172),(-2,-52,9),lens=45)
    camera('04 · 午门 / Meridian Gate',(-27,-566,2.8),(-3,-476,16),lens=26)
    camera('05 · 角楼 / corner tower',(461,546,3.4),(369,476,13.0),lens=54)
    camera('06 · 檐下 / Taihe close detail',(7,-129,19.4),(0,-105,21.6),lens=68)
    camera('07 · 正投影总平 / orthographic plan',(0,-.01,1500),(0,0,0),ortho=1710)
    camera('08 · 内金水河与午门 / Golden Water River',(-73,-382,7.1),(-4,-460,13.0),lens=32)
    wx, wy=metrics['wenyuan']['placement_metres']
    camera('09 · 文渊阁 / Wenyuan Ge',(wx-30,wy-37,9.4),(wx,wy,8.1),lens=40)
    scene.camera=bpy.data.objects['02 · 太和殿 / architectural portrait']
    if options.garden:
        plan=plans[0]
        camera('40 · 浮碧亭 / Fubi pool and pavilion',plan.world(13.98,-10.02,2.17),plan.world(0,-.74,3.64),lens=26.2)
        scene.camera=bpy.data.objects['40 · 浮碧亭 / Fubi pool and pavilion']
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
            area.spaces.active.clip_end=6000
            area.spaces.active.shading.type='SOLID'
            area.spaces.active.shading.color_type='MATERIAL'
    scene['scale']='1 Blender unit = 1 metre; WGS84 -> UTM 50N -> local palace frame'
    scene['georeference']=json.dumps({'utm_epsg':32650,'origin_e':E0,'origin_n':N0,'axis_rotation_degrees':1.8})
    scene['accuracy']='Public-source metric architectural reconstruction, not a laser-scan digital twin. Exterior emphasis; inaccessible interiors, ornaments, unspecified heights are interpretive.'
    scene['source_credit']='OpenStreetMap contributors, ODbL 1.0; Palace Museum building descriptions and photographs; hidden reference imagery Esri, Vantor, Earthstar Geographics, GIS User Community'
    bpy.context.view_layer.update()
    meshes=[o for o in scene.objects if o.type=='MESH' and not o.hide_render]
    metrics.update({'mesh_objects':len(meshes),'vertices':sum(len(o.data.vertices) for o in meshes),
                    'polygons':sum(len(o.data.polygons) for o in meshes),'site_area_m2':round(site.boundary.area,2),
                    'source':'OpenStreetMap contributors; downloaded 2026-11-19','build_seconds':round(time.time()-T0,1)})
    # All photography and fonts are packed; no linked library or missing external image dependency.
    for font in list(bpy.data.fonts):
        if font.users==0:bpy.data.fonts.remove(font)
    bpy.context.preferences.filepaths.save_version=2
    bpy.ops.file.pack_all()
    output=ROOT/'The_Forbidden_City_Imperial_Garden_Base.blend' if options.garden else BLEND
    bpy.ops.wm.save_as_mainfile(filepath=str(output),compress=True)
    (ROOT/'build_metrics.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False),'utf-8')
    log('SAVED '+str(output)+'; '+str(metrics))
    if options.export:
        # Visible architecture only; exclude the hidden reference plane.
        bpy.ops.object.select_all(action='DESELECT')
        for obj in meshes:obj.select_set(True)
        export_name='Forbidden_City_Imperial_Garden_Base.glb' if options.garden else 'Forbidden_City_1to1_Architectural_Reconstruction.glb'
        bpy.ops.export_scene.gltf(filepath=str(EXPORTS/export_name),export_format='GLB',
                                  use_selection=True,export_apply=True,export_yup=True,export_extras=True,export_materials='EXPORT')
        log('GLB export complete')
    if options.preview:
        scene.render.resolution_x=1100;scene.render.resolution_y=825;scene.cycles.samples=20
        scene.render.filepath=str(RENDERS/('fubi_garden_preview.png' if options.garden else 'taihe_preview_v3.png'))
        bpy.ops.render.render(write_still=True);log('First architectural preview complete')


if __name__=='__main__':main()
