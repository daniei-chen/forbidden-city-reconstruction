"""The garden's northbound sightlines: the two documented halls and their foregrounds."""
import math
import random

from mathutils import Vector
from shapely import affinity
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from architectural_roofs import swept_roof
from garden_bridge_pavilions import laid_pavers, painted_span, raised_stair, transfer
from mesh_tools import Batch, collection
from osm_site import rectangle
from palace_materials import paint


HALLS=(
    ('摛藻堂','40795239','https://www.dpm.org.cn/explore/building/236432.html',True),
    ('位育斋','40795237','https://www.dpm.org.cn/explore/building/236445.html',False),
)


def north_hall(site,study,target,p):
    name,ref,source,veranda=study
    x,y,w,d,yaw=rectangle(site.geom(ref))
    floor,eave,rise=.329,4.36,2.18 if veranda else 2.54
    cols=[w*s for s in (-.464,-.291,-.102,.102,.291,.464)]
    col_y=-d/2+.66
    front=col_y+(1.03 if veranda else .22)
    group=collection(name+' · 原址五开间与硬山屋顶',target)
    group['source']=source
    group['source_osm_building_way']=ref
    b,frieze,panels=(Batch((x,y,0),yaw) for _ in range(3))
    b.solid_xy(box(-w*.50,col_y-.64,w*.50,d/2+.11),-.06,floor-.058,p.understone)
    laid_pavers(b,box(-w*.50,col_y-.64,w*.50,d/2+.11),floor,p,course=.65,width=.83)
    raised_stair(b,col_y-1.36,col_y-.635,0,w*.195,.022,floor,2,p)
    for i,u in enumerate(cols):
        b.lathe(u,col_y,((.272,floor),(.273,floor+.087),(.208,floor+.147)),p.stone,sides=24)
        b.lathe(u,col_y,((.194,floor+.13),(.190,floor+.65),(.177,eave-1.46),(.172,eave-.98)),p.red,sides=24)
        if i:
            painted_span(frieze,b,(cols[i-1],col_y),(u,col_y),eave-1.57,p,'flowers')
    for sign in (-1,1):
        xx=sign*(w/2-.152)
        side=Batch()
        gable=[]
        for i in range(25):
            t=i/24
            v=-d/2+d*t
            a=1-abs(1-2*t)
            gable.append((v,eave+rise*(.10*a+.90*a**1.71)-.126))
        from palace_architecture import arch_mesh
        arch_mesh(side,Polygon([(-d/2,floor),(d/2,floor),*reversed(gable)]),.304,p.fascia)
        transfer(b,side,xx,0,math.pi/2)
        b.path([(xx,v,z+.088) for v,z in gable],.126,p.tiles[1],sides=10)
    b.box((0,d/2-.165,eave*.5),(w-.29,.33,eave),p.fascia)
    wall_top=eave-1.36
    for j,(a,c) in enumerate(zip(cols,cols[1:])):
        centre=(a+c)/2;span=c-a-.36
        base=floor+.13 if j==2 else floor+.88
        win_h=wall_top-base
        if j!=2:
            panels.box((centre,front+.091,(floor+base)/2),(span,.238,base-floor),p.understone)
            panels.box((centre,front-.02,base-.039),(span+.064,.318,.078),p.stone)
        panels.box((centre,front+.072,(base+wall_top)/2),(span,.116,win_h),p.inset)
        leaf_count=4 if j==2 or not veranda else 3
        for k in range(leaf_count):
            sw=span/leaf_count
            xx=centre+(k+.5-leaf_count/2)*sw
            for sign in (-1,1):
                panels.box((xx+sign*(sw*.5-.031),front,(base+wall_top)/2),(.061,.117,win_h),p.red)
                panels.box((xx,front,(base if sign<0 else wall_top)-sign*.04),(sw,.14,.080),p.red)
            mid=base+win_h*(.30 if j==2 else .43)
            panels.box((xx,front-.01,mid),(sw,.123,.049),p.red)
            if j==2:
                panels.box((xx,front-.031,(base+mid)/2),(sw-.130,.062,mid-base-.087),p.door)
                panels.box((xx,front-.065,(base+mid)/2),(sw-.184,.010,mid-base-.149),p.faded_teal)
            else:
                for row in (base+.34*(mid-base),base+.67*(mid-base)):
                    panels.box((xx,front-.027,row),(sw-.09,.048,.027),p.red)
            for i in range(1,6):
                panels.box((xx+(i/6-.5)*(sw-.105),front-.029,(mid+wall_top)*.5),
                           (.020,.040,wall_top-mid-.091),p.red)
            for i in range(1,8):
                panels.box((xx,front-.038,mid+i*(wall_top-mid)/8),(sw-.10,.040,.019),p.fascia)
        panels.box((centre,front-.027,wall_top+.173),(span+.35,.166,.384),p.faded_teal)
    b.finish(name+' · 檐柱、墙体、山墙与台明',group)
    frieze.finish(name+' · 梁枋',group)
    panels.finish(name+' · 独立槅扇、支摘窗及槛墙',group)
    swept_roof(name+' 硬山',group,p,origin=(x,y,0),yaw=yaw,width=w,depth=d,
               eave=eave,rise=rise,kind='gable',tiles=True,pitch=.29,detail=1,gable_ends=False,
               terminal_height=.50,ridge_terminals=False,soffit=True)
    return {'name':name,'collection':group.name,'source':source,'osm_id':ref,'mapped_roof_plan_m':[w,d],
            'documented_bays':5,'has_documented_veranda':veranda,'inferred_eave_z_m':eave}


def old_cypress(target,plan,p,label,x,y,h,seed):
    rng=random.Random(seed)
    group=collection(label,target)
    b,needles=plan.batch(),plan.batch()
    colors=p.cypress
    lean=Vector((rng.uniform(-.93,.93),rng.uniform(-.64,.64),0))
    origin=Vector((x,y,.057))
    trunk=[origin+lean*t+Vector((.15*math.sin(t*4.5),.08*math.sin(t*6.5),h*t))
           for t in (0,.10,.20,.29,.41,.52,.63,.73,.83,.92)]
    def tapered(points,radii,sides):
        verts=[];faces=[]
        for i,(q,r) in enumerate(zip(points,radii)):
            axis=(points[min(i+1,len(points)-1)]-points[max(0,i-1)]).to_track_quat('Z','Y')
            for k in range(sides):
                phase=k*math.tau/sides
                uneven=r*(1+.104*math.sin(phase*4.0+i*.21)+.045*math.cos(phase*7.0+i*.39))
                verts.append(q+axis@Vector((uneven*math.cos(phase),uneven*math.sin(phase),0)))
            if i:
                faces.extend(((i-1)*sides+k,(i-1)*sides+(k+1)%sides,i*sides+(k+1)%sides,i*sides+k)
                             for k in range(sides))
        faces.extend([tuple(reversed(range(sides))),tuple(range(len(verts)-sides,len(verts)))])
        b.add(verts,faces,p.bark,smooth=True)

    tapered(trunk,[h*(.004+.039*(1-i/10)**1.26) for i in range(10)],23)
    for i in range(7):
        a=i*math.tau/7+rng.uniform(-.15,.15)
        d=Vector((math.cos(a),math.sin(a),0))
        b.rod(origin+d*h*.105,origin+Vector((0,0,.35)),.037,p.bark,r1=h*.028,sides=9)

    def branch(a,d,length,r,depth):
        d=d.normalized()
        c=a+d*length
        m=a+d*length*.49+Vector((0,0,-length*.087))
        tapered([a-d*r*.24,m,c],[r*.94,r*.71,max(.002,r*.17)],11 if depth>1 else 7)
        if depth>0:
            for j in range(3 if depth>1 else 4):
                phase=rng.random()*math.tau
                twig=d*.56+Vector((math.cos(phase)*.71,math.sin(phase)*.71,rng.uniform(.09,.75)))
                branch(m.lerp(c,(j+.4)/4),twig,length*rng.uniform(.42,.62),r*.44,depth-1)
        else:
            for i in range(31):
                q=m.lerp(c,rng.random())+Vector((rng.uniform(-.09,.09),rng.uniform(-.09,.09),rng.uniform(-.05,.11)))
                angle=rng.random()*math.tau
                d1=Vector((math.cos(angle),math.sin(angle),rng.uniform(-.3,1.2))).normalized()
                width=Vector((-d1.y,d1.x,.048))*.021
                tip=q+d1*rng.uniform(.066,.203)
                crown=(q+tip)*.5+Vector((0,0,.033))
                needles.add([q,tip-width,tip+width,crown],[(0,1,3),(0,3,2),(1,2,3)],
                            colors[rng.randrange(len(colors))],smooth=True)
    for i in range(1,10):
        angle=i*2.399+rng.uniform(-.39,.39)
        d=Vector((math.cos(angle),math.sin(angle),rng.uniform(.22,.58)))
        branch(trunk[i],d,h*(.528-.032*i)*rng.uniform(.75,1.10),h*(.020-.0016*i),3)
    b.finish(label+' · 干、根和枝',group)
    needles.finish(label+' · 疏密交错的柏叶',group)
    return plan.world(x,y)


def planting_bed(plan,target,p,x,y,wide,deep,seed,rock=False):
    rng=random.Random(seed)
    b,plants=plan.batch(),plan.batch()
    outline=box(x-wide/2,y-deep/2,x+wide/2,y+deep/2)
    rim=outline.difference(outline.buffer(-.16,join_style=2))
    b.solid_xy(rim,.031,.324,p.fascia if rock else p.stone,bottom=False)
    b.solid_xy(outline.buffer(-.138,join_style=2),.045,.237,p.soil,bottom=False)
    if rock:
        from palace_architecture import arch_mesh
        outline=Polygon([(-.56,.21),(-.63,.52),(-.50,.93),(-.47,1.20),(-.23,1.46),(-.18,1.84),
                         (.05,1.98),(.22,1.73),(.14,1.42),(.36,1.29),(.41,1.05),(.33,.82),
                         (.53,.67),(.64,.31),(.44,.24)])
        for u,v,rx,rz in ((-.21,1.19,.126,.173),(-.12,.56,.181,.115),(.07,1.60,.047,.091),(.27,.84,.067,.121)):
            hole=Point(u,v).buffer(1.,quad_segs=9)
            outline=outline.difference(affinity.scale(hole,rx,rz,origin=(u,v)))
        jagged=Batch();arch_mesh(jagged,outline,.48,p.rock)
        jagged.v=[(u+.032*math.sin(v*42),d*(.87+.33*math.sin(u*24+v*5))+.103*math.cos(v*10.68+u*14.1),
                   v+.033*math.sin(u*39+v*4)) for u,d,v in jagged.v]
        transfer(b,jagged,x,y,.38)
    for i in range(max(8,round(wide*deep*5))):
        xx=x+rng.uniform(-wide*.42,wide*.42)
        yy=y+rng.uniform(-deep*.42,deep*.42)
        if rock and (abs(xx-x)<.66 and abs(yy-y)<.47):
            continue
        z=.237+rng.uniform(.19,.50)
        plants.rod((xx,yy,.237),(xx,yy,z),.009,p.leaves[0],sides=5)
        for j in range(7):
            a=rng.random()*math.tau
            ln=rng.uniform(.062,.133)
            base=(xx,yy,z-rng.uniform(.048,.173))
            tip=(xx+ln*math.cos(a),yy+ln*math.sin(a),base[2]+.049)
            side=(-math.sin(a)*.037,math.cos(a)*.037)
            plants.add([base,((base[0]+tip[0])/2+side[0],(base[1]+tip[1])/2+side[1],base[2]+.043),
                        tip,((base[0]+tip[0])/2-side[0],(base[1]+tip[1])/2-side[1],base[2]+.043)],
                       [(0,1,2,3)],p.leaves[j%4])
        if i%4==0:
            for j in range(13):
                a=j*2.4
                plants.ellipsoid((xx+(.029+j*.002)*math.cos(a),yy+(.029+j*.002)*math.sin(a),z+.035+j*.0016),
                                (.037,.022,.018),p.lotus_pink if i%3 else p.cream,sides=8,rings=4,yaw=a)
    name='太湖石与盆栽花圃' if rock else '低矮花圃'
    b.finish(name+' · 石景与种植槽',target)
    plants.finish(name+' · 枝叶和花瓣',target)


def garden_context(site,plans,target,p):
    p.bark=paint('御花园 · 古柏斑驳树皮',(.074,.048,.027),second=(.235,.206,.150),
                 scale=4.6,rough=.95,bump=.019,grain=32)
    p.cypress=[paint(f'御花园 · 柏叶{n+1}',c,rough=.66,bump=.002) for n,c in enumerate(
        ((.038,.075,.022),(.084,.115,.035),(.065,.116,.049),(.094,.138,.054)))]
    p.soil=paint('御花园 · 花池腐殖土',(.064,.043,.023),second=(.153,.125,.080),scale=7.3,rough=.94,bump=.011)
    p.rock=paint('御花园 · 太湖石风化表面',(.25,.213,.143),second=(.593,.556,.415),scale=3.7,
                 rough=.94,bump=.048,grain=41)
    pavers=paint('御花园 · 已磨平的旧墁地青石',(.158,.144,.111),second=(.366,.347,.286),
                 scale=2.47,rough=.88,grain=81,bump=.009)
    old_floor=p.terrace_floor
    p.terrace_floor=pavers
    group=collection('御花园 · 背殿、古柏与池外墁地',target)
    metrics={'halls':[north_hall(site,study,group,p) for study in HALLS],'garden_trees_m':[]}
    for i,plan in enumerate(plans):
        side='东' if i==0 else '西'
        patch=plan.batch()
        start=plan.front_y-9.42
        pad=box(-10.8,start,11.67,plan.front_y+1.18).union(box(-3.98,plan.front_y+1.,3.98,plan.front_y+1.47))
        shade=unary_union([Point(x,y).buffer(.74,quad_segs=14) for x,y in ((9.67,-11.89),(-9.83,-9.15))])
        pad=pad.difference(shade).difference(plan.pond.buffer(.51))
        laid_pavers(patch,pad,.043,p,course=.58,width=1.03)
        patch.finish(f'御花园 · {side}池前旧石墁地',group)
        for j,(x,y,h) in enumerate(((9.67,-11.89,9.6),(-9.83,-9.15,7.8))):
            metrics['garden_trees_m'].append(old_cypress(group,plan,p,f'御花园 · {side}池古柏 {j+1}',
                                                        x,y,h,620+i*74+j*21))
        planting_bed(plan,group,p,-7.08,plan.front_y-2.87,3.58,1.99,79+i*6,rock=i==0)
        planting_bed(plan,group,p,7.02,plan.front_y-3.46,3.89,1.76,52+i*17)
    p.terrace_floor=old_floor
    metrics['landscape_fidelity']='Vegetation specimen positions and masonry surface layout inferred from photos; no inventory measurements.'
    return metrics
