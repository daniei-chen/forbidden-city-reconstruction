"""Four-annex eaves and radial bamboo-joint roof tiles for the garden twins."""
import math

from mathutils import Vector

from architectural_roofs import ridge_guardian, terminal
from carved_ornament import cloud
from mesh_tools import Batch, collection

LOW_EAVE=6.61
LOW_CREST=8.60
UP_EAVE=9.79
UP_RISE=2.36
DRUM_R=2.802


def reversed_if_down(points,faces):
    if (points[1]-points[0]).cross(points[2]-points[0]).z<0:
        return [tuple(reversed(f)) for f in faces]
    return faces


def roof_panels(b,grid,xsteps,ysteps,upper,lower):
    points=[grid(i/xsteps,j/ysteps) for j in range(ysteps+1) for i in range(xsteps+1)]
    ring=xsteps+1
    faces=[(k,k+1,k+ring+1,k+ring) for j in range(ysteps) for i in range(xsteps)
           for k in (j*ring+i,)]
    faces=reversed_if_down(points,faces)
    under=[p-Vector((0,0,.173)) for p in points]
    b.add(points,faces,upper,smooth=True)
    b.add(under,[tuple(reversed(f)) for f in faces],lower,smooth=True)
    for i in range(xsteps):
        b.face([points[i],under[i],under[i+1],points[i+1]],lower)


def fit_frame(position,u,t,end):
    q=position(u,t)
    along=(position(u,min(end,t+.002))-position(u,max(0.,t-.002))).normalized()
    cross=position(u+.0015,t)-position(u-.0015,t)
    cross=(cross-along*cross.dot(along)).normalized()
    normal=along.cross(cross).normalized()
    if normal.z<0:normal.negate()
    return q,along,cross,normal


def tile(b,position,u,t0,t1,end,pitch,mat,cap,bamboo=False):
    count=7 if cap else 5
    span=t1-t0
    divisions=(0,.055,.135,.216,.72,1.) if cap and bamboo else (0,.103,.88,1.)
    rings=[]
    for i,f in enumerate(divisions):
        t=t0+span*f
        q,_,side,n=fit_frame(position,u,t,end)
        w=pitch(t) if callable(pitch) else pitch
        collar=(1.09 if i in (1,2) else 1.0) if cap and bamboo else 1.
        for j in range(count):
            if cap:
                a=math.pi*j/(count-1)
                rings.append(q+side*(math.cos(a)*w*.330*collar)+n*(.022+math.sin(a)*w*.405*collar))
            else:
                a=2*j/(count-1)-1
                rings.append(q+side*(a*w*.468)+n*(.009+.125*w*a*a))
    faces=[]
    for i in range(len(divisions)-1):
        for j in range(count-1):
            k=i*count+j
            faces.append((k,k+1,k+count+1,k+count))
    # Orient the whole channel against its local upward normal.
    a,c,d=[rings[i] for i in faces[0][:3]]
    if (c-a).cross(d-a).dot(n)<0:faces=[tuple(reversed(f)) for f in faces]
    b.add(rings,faces,mat,smooth=True)


def eave_detail(b,wood,frame,spacing,p,mat,*,relief=True):
    q,t,s,n=frame
    front=q-t*.056+n*(.035+spacing*.20)
    radius=spacing*.35
    b.rod(front+t*.045,front,radius,mat,sides=16)
    b.rod(front,front-t*.011,radius*.779,p.terracotta,sides=14)
    seam=[front-t*.013+radius*.87*(s*math.cos(a)+n*math.sin(a))
          for a in (i*math.tau/23 for i in range(24))]
    b.path(seam,.007,mat,sides=5)
    if relief:
        curl=[front-t*.014+radius*(.13+.61*i/33)*(s*math.cos(i*.287)+n*math.sin(i*.287))
              for i in range(34)]
        b.path(curl,.0058,mat,sides=5)
        for a in (-.89,.72,2.45):
            center=front-t*.015+radius*.52*(s*math.cos(a)+n*math.sin(a))
            b.ellipsoid(center,(.013,.012,.012),mat,sides=6,rings=4)
    drip=q+s*(spacing*.505)-t*.068
    outline=[drip+s*(spacing*.418*a)+n*(-.009-spacing*.22*(1-abs(a)**1.5))
             for a in (i/6 for i in range(-6,7))]
    b.add([*outline,*[v-t*.019+n*.025 for v in outline]],
          [(i,i+1,i+14,i+13) for i in range(12)],mat)
    for height,gauge,material in ((.219,.106,p.faded_teal),(.372,.078,p.faded_blue)):
        start=q-t*.054-Vector((0,0,height));end=q+t*.75-Vector((0,0,height-.024))
        wood.beam(start,end,gauge,gauge,material)
        if height>.30:
            wood.rod(start+.006*t,start-.011*t,gauge*.47,p.cream,sides=9)


def lower_roof(loc,target,p,body):
    group=collection('下檐 · 四面抱厦与交接脊',target)
    width,depth,wing_x,wing_y=body
    # CCW eave outline. The outer and reentrant vertices alternate at the annexes.
    points=[(-width,-depth),(-wing_x,-depth),(-wing_x,-depth-1.60),(wing_x,-depth-1.60),
            (wing_x,-depth),(width,-depth),(width,-wing_y),(width+1.51,-wing_y),
            (width+1.51,wing_y),(width,wing_y),(width,depth),(wing_x,depth),
            (wing_x,depth+1.60),(-wing_x,depth+1.60),(-wing_x,depth),(-width,depth),
            (-width,wing_y),(-width-1.51,wing_y),(-width-1.51,-wing_y),(-width,-wing_y)]
    tips={0,2,3,5,7,8,10,12,13,15,17,18}
    lifts=[.56 if i in tips else .027 for i in range(len(points))]
    shell,tiles,ridges,wood=(loc.batch() for _ in range(4))
    radial=[Vector(q).normalized()*(DRUM_R-.145) for q in points]
    for i,(a0,b0) in enumerate(zip(points,points[1:]+points[:1])):
        j=(i+1)%len(points)
        a,b=Vector(a0),Vector(b0);ia,ib=radial[i],radial[j]
        along=b-a;edge=along.length;axis=along/edge
        lu,ru=(ia-a).dot(axis),(ib-a).dot(axis)

        def surface(s,t):
            xy=a.lerp(b,s).lerp(ia.lerp(ib,s),t)
            lift=(lifts[i]*(1-s)**5+lifts[j]*s**5)*(1-t)**2
            z=LOW_EAVE+(LOW_CREST-LOW_EAVE)*(.14*t+.86*t**1.67)+lift
            return Vector((xy.x,xy.y,z))

        def absolute(u,t):
            left=t*lu;right=edge+(ru-edge)*t
            return surface(min(1.,max(0.,(u-left)/max(.035,right-left))),t)

        roof_panels(shell,surface,max(8,math.ceil(edge/.23)),22,p.roof,p.fascia)
        wood.path([surface(v/30,0)-Vector((0,0,.15)) for v in range(31)],.087,p.fascia,sides=8)
        n=max(3,round(edge/.223));spacing=edge/n
        for cap in (True,False):
            for col in range(n if cap else n-1):
                u=spacing*(col+(.5 if cap else 1.))
                margin=spacing*(.30 if cap else .40)
                stop=min(1.,(u-margin)/lu if lu>0 else 1.,(edge-u-margin)/(edge-ru) if ru<edge else 1.)
                if stop<.027:continue
                path=(absolute(u,0)-absolute(u,stop)).length
                count=max(1,math.ceil(path/.343))
                mat=p.twin_glaze[(i*13+col*3)%len(p.twin_glaze)]
                for k in range(count):
                    tile(tiles,absolute,u,stop*k/count,min(stop,stop*(k+1.08)/count),stop,spacing,mat,cap)
                if cap:
                    eave_detail(tiles,wood,fit_frame(absolute,u,0,stop),spacing,p,mat)
        samples=[surface(0,t/30)+Vector((0,0,.076)) for t in range(31)]
        if i in tips:
            # Each projecting hip has a ridged glazed saddle and its own small beasts.
            ridges.path(samples,.106,p.twin_glaze[2],sides=10)
            ridges.path([q+Vector((0,0,.092)) for q in samples],.049,p.twin_glaze[0],sides=10)
            out=Vector(a0).normalized()
            for k in range(4):
                q=surface(0,.052+.107*k)
                ridge_guardian(ridges,tuple(q+Vector((0,0,.13))),math.copysign(1,out.x),math.copysign(1,out.y),
                               .39 if k==0 else .28,p.twin_glaze[2],kind=k)
            q=surface(0,.61)
            crest=Batch()
            terminal(crest,(0,0,q.z+.06),1,.42,p.twin_glaze[1],p)
            from garden_bridge_pavilions import transfer
            transfer(ridges,crest,q.x,q.y,math.atan2(out.y,out.x))
        else:
            ridges.path([q-Vector((0,0,.063)) for q in samples],.058,p.darktile,sides=8)
    shell.finish('下檐 · 连续黄瓦灰背与檐板',group,properties={'hip_tips':len(tips),'reentrant_eaves':len(points)-len(tips)})
    tiles.finish('下檐 · 可编辑筒板瓦、龙纹瓦当及滴水',group)
    ridges.finish('下檐 · 十二戗尖、夹沟、走兽和琉璃吻',group)
    wood.finish('下檐 · 翼角椽、飞椽及连檐木',group)


def umbrella_roof(loc,target,p,radius):
    group=collection('上檐 · 一把伞圆攒尖、竹节瓦和华盖',target)
    bark,tiles,wood,finial,ornament=(loc.batch() for _ in range(5))
    crown=UP_EAVE+UP_RISE
    stop_r=.234
    def radius_at(t):return radius+(stop_r-radius)*t
    def pos(angle,t):
        r=radius_at(t)
        return Vector((r*math.cos(angle),r*math.sin(angle),UP_EAVE+UP_RISE*(.094*t+.906*t**2.16)))

    roof_panels(bark,lambda u,t:pos(u*math.tau,t),192,37,p.roof,p.fascia)
    n=round(math.tau*radius/.208)
    space=math.tau/n
    trim=.995
    for i in range(n):
        angle=(i+.5)*space
        pitch=lambda t:radius_at(t)*space
        mat=p.twin_glaze[(i*19+i//8)%len(p.twin_glaze)]
        for j in range(16):
            lo=j/16;hi=min(trim,(j+1.15)/16)
            tile(tiles,pos,angle,lo,hi,trim,pitch,mat,True,bamboo=True)
            tile(tiles,pos,angle+space/2,lo,hi,trim,pitch,mat,False)
        eave_detail(tiles,wood,fit_frame(pos,angle,0,trim),pitch(0),p,mat)
        if i%4==0:
            for t in (.17,.39,.61,.79):
                q=pos(angle,t)
                tiles.ellipsoid(q+Vector((0,0,.048)),(.024,.024,.035),p.darktile,sides=8,rings=5)
    rim=[pos(i*math.tau/160,0)-Vector((0,0,.17)) for i in range(161)]
    wood.path(rim,.094,p.fascia,sides=9)
    bark.finish('上檐 · 真圆断面与弯曲伞面',group,properties={'outer_radius_m':radius,'eave_elevation_m':UP_EAVE})
    tiles.finish('上檐 · 逐垄放射收分的黄釉竹节筒瓦',group,properties={'radial_tile_courses':n,'tiles_per_course':16})
    wood.finish('上檐 · 圆檐椽头与二层飞椽',group)
    gold=p.old_gold
    finial.lathe(0,0,((.37,crown-.05),(.37,crown+.043),(.345,crown+.096),(.273,crown+.144),(.248,crown+.213)),p.twin_glaze[1],sides=64)
    finial.lathe(0,0,((.226,crown+.202),(.224,crown+.237),(.278,crown+.310),(.307,crown+.410),
                     (.302,crown+.534),(.260,crown+.626),(.194,crown+.696),(.174,crown+.767)),p.enamel,sides=64)
    finial.lathe(0,0,((.178,crown+.707),(.209,crown+.740),(.235,crown+.801),(.221,crown+.844),
                     (.113,crown+.878),(.115,crown+1.00),(.111,crown+1.118),(.265,crown+1.164),
                     (.375,crown+1.213),(.395,crown+1.306),(.330,crown+1.391),(.123,crown+1.449),(.035,crown+1.496)),gold,sides=64)
    finial.ellipsoid((0,0,crown+1.52),(.081,.081,.109),gold,sides=24,rings=13)
    for i in range(18):
        a=math.tau*i/18
        dx,dy=math.cos(a),math.sin(a)
        ornament.path([(.390*dx,.390*dy,crown+1.274),(.384*dx,.384*dy,crown+1.17),
                       (.440*dx,.440*dy,crown+1.123)],.018,gold,sides=7)
        ornament.ellipsoid((.448*dx,.448*dy,crown+1.127),(.022,.022,.035),gold,sides=8,rings=5)
        if i%2==0:
            work=Batch()
            cloud(work,(0,-.311,crown+.485),.243,p.twin_glaze[2],rotation=i*.9)
            from garden_bridge_pavilions import transfer
            transfer(ornament,work,0,0,a+math.pi/2)
    finial.finish('宝顶 · 黄釉底、绿釉瓶和鎏金花盖',group)
    ornament.finish('宝顶 · 金云纹、伞盖流苏和金珠',group)
