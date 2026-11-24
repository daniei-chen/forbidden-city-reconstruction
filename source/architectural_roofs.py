"""Curved Chinese roof surfaces with real cap tiles, pan tiles and ridge sculpture.

Local coordinates: x runs along the principal ridge; front is negative y.
Every roof is a group of independently editable mesh assets, in metre units.
"""
from __future__ import annotations

import math
from mathutils import Vector
from mathutils.noise import noise_vector

from mesh_tools import Batch, collection


def swept_roof(name, target, pal, *, origin=(0,0,0), yaw=0., width=20., depth=12.,
               eave=12., rise=6., kind="hip", stop=1., tiles=False, pitch=.36,
               beasts=0, grey=False, green=False, detail=1, terminal_height=None,
               soffit=True, eave_lift=None, sculpted=False, ridge_length=None,
               ridge_terminals=True, gable_ends=True, border_glaze=None,
               pyramid_finial=True):
    group=collection(name,target)
    substrate=pal.grey if grey else pal.green if green else pal.roof
    clay=border_glaze or (pal.grey_clay if grey else pal.green_clay if green else pal.tiles[1])
    shell=Batch(origin,yaw); ridges=Batch(origin,yaw); tiling=Batch(origin,yaw)
    hw,hd=width/2,depth/2
    pyramid=kind=="pyramid"
    straight_gable=kind in ("gable","juanpeng")
    gable=straight_gable or kind=="xieshan"
    ridge_half=0.0 if pyramid else hw if straight_gable else hw*.80 if kind=="xieshan" else max(.35,hw-hd*.76)
    if ridge_length is not None and not pyramid:
        if not 0 < ridge_length <= width:
            raise ValueError('The ridge must fit within the roof width.')
        ridge_half=ridge_length/2
    upturn=min(.84,depth*.044) if eave_lift is None else eave_lift

    def level(t,u):
        lift=upturn*(abs(u)**8)*(1-t)**2 if not straight_gable or eave_lift is not None else 0
        profile=.10*t+.90*t**1.71
        if kind=='juanpeng' and t>.72:
            # Tangent continuity at the join and a horizontal tangent at the crown.
            a=.72
            v=.10*a+.90*a**1.71
            d=(.10+.90*1.71*a**.71)*(1-a)
            s=(t-a)/(1-a)
            profile=(2*s**3-3*s*s+1)*v+(s**3-2*s*s+s)*d-2*s**3+3*s*s
        return eave+rise*profile+lift+.07*(1-t)**14

    def half_span(t):
        tt=min(t/.38,1) if kind=="xieshan" else t
        return hw+(ridge_half-hw)*tt

    def position(side,u,t):
        if side<2:
            sgn=-1 if side==0 else 1
            return Vector((u*half_span(t),sgn*hd*(1-t),level(t,u)))
        sgn=-1 if side==2 else 1
        if kind=="xieshan":
            xx=hw+(ridge_half-hw)*min(t/.38,1)
        else:
            xx=hw+(ridge_half-hw)*t
        return Vector((sgn*xx,u*hd*(1-t),level(t,u)))

    panels=(0,1) if straight_gable else (0,1,2,3)
    for side in panels:
        end=min(stop,.38) if kind=="xieshan" and side>=2 else stop
        across=max(6,min(56,math.ceil((width if side<2 else depth)/1.1)))
        along=max(6,math.ceil(end*20))
        verts=[];uv=[];faces=[]
        for j in range(along+1):
            t=end*j/along
            for i in range(across+1):
                u=-1+2*i/across
                p=position(side,u,t)
                verts.append(tuple(p))
                uv.append(((p.x if side<2 else p.y),t*hd))
        for j in range(along):
            for i in range(across):
                k=j*(across+1)+i
                f=(k,k+1,k+across+2,k+across+1)
                if math.dist(verts[f[2]],verts[f[3]])<1e-7:
                    f=f[:3]
                a,b,c=(Vector(verts[k]) for k in f[:3])
                if (b-a).cross(c-a).z<0:f=tuple(reversed(f))
                faces.append(f)
        shell.add(verts,faces,substrate,uv=uv,smooth=True)
        # Real underside and narrow fired-clay eave lip, no floating roof plane.
        verts_bottom=[(x,y,z-.19) for x,y,z in verts]
        shell.add(verts_bottom,[tuple(reversed(f)) for f in faces],pal.door,smooth=True)
        for border in ([(i) for i in range(across+1)],
                       [along*(across+1)+i for i in range(across+1)]):
            for a,b in zip(border,border[1:]):
                if math.dist(verts[a],verts[b])>.0001:
                    shell.face([verts[a],verts[b],verts_bottom[b],verts_bottom[a]],clay)
        ridges.path([tuple(position(side,-1+2*i/40,0)+Vector((0,0,-.20))) for i in range(41)],.105,pal.door,sides=8)

        if tiles:
            # Fix each channel's transverse coordinate at the eave. Ridges trim
            # the courses; rows never gain or lose columns halfway up the slope.
            span=hw if side<2 else hd
            count=max(1,round(2*span/pitch)); spacing=2*span/count
            nominal_rows=max(2,math.ceil((position(side,0,end)-position(side,0,0)).length/.42))
            def tile_position(offset,t):
                across=half_span(t) if side<2 else hd*(1-t)
                return position(side,max(-1.,min(1.,offset/max(across,1e-6))),t)

            def frame(offset,t):
                center=tile_position(offset,t)
                tangent=(tile_position(offset,min(end,t+.002))-tile_position(offset,max(0.,t-.002))).normalized()
                across=tile_position(offset+.012,t)-tile_position(offset-.012,t)
                across=(across-tangent*across.dot(tangent)).normalized()
                normal=tangent.cross(across).normalized()
                if normal.z<0:normal=-normal
                return center,tangent,across,normal

            for is_cap in (True,False):
                across_steps=7 if is_cap else 5
                for column in range(count if is_cap else count-1):
                    offset=-span+spacing*(column+(.5 if is_cap else 1.0))
                    margin=abs(offset)+spacing*(.27 if is_cap else .38)
                    if side>=2:
                        last=max(0.,1-margin/hd)
                    elif straight_gable or margin<=ridge_half:
                        last=end
                    else:
                        last=(hw-margin)/(hw-ridge_half)*(.38 if kind=='xieshan' else 1.)
                    last=min(end,last)
                    if last<.011:continue
                    rows=max(1,math.ceil(nominal_rows*last/end))
                    color_index=abs(int(10000*noise_vector(Vector((offset*1.2,side*2.7,width*.09))).x))%len(pal.tiles)
                    base=pal.grey_clay if grey else pal.green_clay if green else pal.tiles[color_index]
                    for row in range(rows):
                        ta=last*row/rows;tb=last*(row+1)/rows
                        # The tucked upper edge is covered by the next tile. Its
                        # crown rises a few millimetres at the visible lower lap.
                        lap=min(last,last*(row+1.065)/rows)
                        vv=[]
                        for t,seam in ((ta,.010),(min(tb,ta+(tb-ta)*.095),0.),(lap,-.009)):
                            p,along,across,normal=frame(offset,t)
                            for j in range(across_steps):
                                f=j/(across_steps-1)
                                if is_cap:
                                    angle=math.pi*f
                                    section=across*(spacing*.315*math.cos(angle))+normal*(.034+spacing*.33*math.sin(angle)+seam)
                                else:
                                    u=2*f-1
                                    section=across*(u*spacing*.46)+normal*(.016+spacing*.135*u*u+seam*.4)
                                vv.append(tuple(p+section))
                        faces=[]
                        for i in range(2):
                            for j in range(across_steps-1):
                                k=i*across_steps+j
                                ff=(k,k+1,k+across_steps+1,k+across_steps)
                                a,b,c=(Vector(vv[n]) for n in ff[:3])
                                if (b-a).cross(c-a).dot(normal)<0:ff=tuple(reversed(ff))
                                faces.append(ff)
                        material=base
                        if border_glaze and (row==0 or abs(offset)>span-spacing*2 or
                                            (not straight_gable and last<end-.004 and row==rows-1)):
                            material=border_glaze
                        tiling.add(vv,faces,material,smooth=True)
                    p,tangent,across,normal=frame(offset,0.)
                    if is_cap:
                        radius=spacing*.33;c=p-tangent*.039+normal*(.06+spacing*.18)
                        face_glaze=border_glaze or base
                        tiling.rod(c-tangent*.020,c+tangent*.048,radius,face_glaze,sides=12 if detail>1 else 9)
                        if detail>1:
                            tiling.rod(c-tangent*.032,c-tangent*.022,radius*.76,pal.darktile,sides=12)
                            for petal in range(5):
                                angle=petal*math.tau/5
                                q=c-tangent*.035+(across*math.cos(angle)+normal*math.sin(angle))*radius*.40
                                tiling.ellipsoid(q,(.018,.013,.022),face_glaze,sides=5,rings=3)
                    else:
                        # Pointed drip tiles hang between the round end disks.
                        q=p-tangent*.063
                        tiling.face([tuple(q-across*spacing*.32+normal*.04),tuple(q-normal*.115),
                                     tuple(q+across*spacing*.32+normal*.04)],clay)
                    if soffit:
                        rafter_a=p-tangent*.09-Vector((0,0,.26))
                        rafter_b=p+tangent*min(2.7,depth*.22)-Vector((0,0,.37))
                        ridges.beam(rafter_a,rafter_b,.09,.12,pal.teal if column%2 else pal.blue)
                        if is_cap and detail>1:
                            ridges.beam(rafter_a+tangent*.004,rafter_a-tangent*.020,.061,.069,pal.giltpaint)

    # Gable timber infill is present only above the lower hipped edge of a歇山顶.
    if gable and stop>=.999 and gable_ends:
        t=.38 if kind=="xieshan" else 0.
        yy=hd*(1-t); xx=half_span(t)
        for sign in (-1,1):
            profile=[tuple(position(0 if i<=16 else 1,sign,1-abs(i-16)/16*(1-t))) for i in range(33)]
            base_z=level(t,0)-.10
            for a,b in zip(profile,profile[1:]):
                shell.face([a,b,(b[0],b[1],base_z),(a[0],a[1],base_z)],pal.door)
            ridges.path(profile,.13,clay,sides=9)
            for q in range(11):
                y=-yy+2*yy*(q+.5)/11;z=level(1-abs(y)/hd,sign)-.08
                if z>base_z+.15:
                    ridges.beam((sign*(xx+.028),y,base_z),(sign*(xx+.028),y,z),.09,.12,pal.red)

    # Four actual sloping hip ridges with projecting raised eave corners.
    if sculpted:
        from roof_sculpture import guardian,chiwen,ORDER
        import math as _math
        from mathutils import Matrix
        c,s=math.cos(yaw),math.sin(yaw)
        def world(p):
            return (origin[0]+c*p.x-s*p.y,origin[1]+s*p.x+c*p.y,origin[2]+p.z)
    for sx in (() if straight_gable else (-1,1)):
        for sy in (-1,1):
            end=min(stop,.38) if kind=="xieshan" else stop
            pts=[tuple(position(0 if sy<0 else 1,sx,end*i/24)+Vector((0,0,.055))) for i in range(25)]
            ridges.path(pts,.18 if width>30 else .12,clay,sides=9)
            if beasts and sculpted:
                # The published Taihe arrangement is a rider followed by ten
                # distinct beasts, at .321 m carrier length plus small gaps.
                side=0 if sy<0 else 1
                outward=(position(side,sx,.01)-position(side,sx,.08)).normalized()
                orientation=math.atan2(outward.y,outward.x)+yaw
                strip=collection('走兽序列 %s%s'%('西' if sx<0 else '东','南' if sy<0 else '北'),group)
                span=(position(side,sx,min(end,.50))-position(side,sx,0)).length
                spacing=.389 if width>40 else .29
                dt=min(end*.84,(beasts+1)*spacing/max(span,1e-5)*min(end,.50))
                for index in range(beasts+1):
                    t=.018+dt*(index+.28)/(beasts+1)
                    point=position(side,sx,t)+Vector((0,0,.18))
                    guardian(strip,pal,point=world(point),yaw=orientation,
                             ordinal=max(1,index),immortal=index==0,height=.69 if index==0 else .66,
                             label=('骑凤仙人' if index==0 else '%02d · %s'%(index,ORDER[index-1])))
                strip['order_from_eave']='骑凤仙人 → '+' → '.join(ORDER[:beasts])
                strip['guardians_excluding_rider']=beasts
            elif beasts:
                beast_count=beasts
                lead=position(0 if sy<0 else 1,sx,.047)+Vector((0,0,.18))
                ridge_guardian(ridges,tuple(lead),sx,sy,.54 if width>40 else .35,clay,kind=0)
                for k in range(beast_count):
                    t=.07+(k+1)*min(.36,end*.65)/(beast_count+1)
                    p=position(0 if sy<0 else 1,sx,t)+Vector((0,0,.16))
                    s=.62 if width>52 else .43 if width>33 else .28
                    ridge_guardian(ridges,tuple(p),sx,sy,s,clay,kind=k)

    if stop>=.999:
        if pyramid and pyramid_finial:
            ridges.lathe(0,0,((.31,eave+rise-.02),(.25,eave+rise+.12),(.13,eave+rise+.20),
                              (.25,eave+rise+.43),(.19,eave+rise+.62),(.03,eave+rise+.82)),pal.gold,sides=18)
        elif not pyramid and kind!='juanpeng':
            z=eave+rise
            ridges.box((0,0,z+.14),(2*ridge_half,.39,.36),clay)
            ridges.box((0,0,z+.38),(2*ridge_half,.26,.15),clay)
            ridges.path([(-ridge_half-.14,0,z+.46),(ridge_half+.14,0,z+.46)],.085,clay,sides=10)
            for end in ((-1,1) if ridge_terminals else ()):
                height=terminal_height or (1.8 if width>40 else .97)
                if sculpted:
                    local=Vector((end*ridge_half,0,z+.16))
                    chiwen(group,pal,origin=world(local),yaw=yaw,end=end,height=height,
                           width=2.68*height/3.46,thickness=.52*height/3.46,
                           label=('东' if end>0 else '西')+'正吻 · 独立十六拼')
                else:
                    terminal(ridges,(end*ridge_half,0,z+.16),end,max(.25,(height-.16)/1.35),clay,pal)

    shell_obj=shell.finish(name+" · curved ceramic shell and dark timber soffit",group)
    if shell_obj:
        shell_obj["roof_type"]=kind
        shell_obj["geometry_units"]="metres"
    ridges.finish(name+" · sculpted ridge, chiwen terminals and roof guardians",group)
    tile_obj=tiling.finish(name+" · individually curved cylinder tiles, pan tiles and round eave seals",group)
    if tile_obj:
        tile_obj["detail"]="Continuous fixed-pitch channels, lapped convex/concave tiles, moulded eave seals and drip tiles"
    return group


def terminal(batch,origin,end,s,clay,pal):
    x,y,z=origin
    # Stylized fish-tailed chiwen with a curved dragon crest and engraved face.
    batch.ellipsoid((x,y,z+.21*s),(.30*s,.22*s,.36*s),clay,sides=12,rings=6)
    batch.path([(x,y,z),(x+end*.21*s,y,z+.27*s),(x+end*.29*s,y,z+.73*s),
                (x+end*.08*s,y,z+1.10*s),(x-end*.15*s,y,z+1.22*s)],.13*s,clay,sides=9)
    batch.ellipsoid((x-end*.14*s,y,z+.68*s),(.25*s,.21*s,.23*s),clay,sides=10,rings=5)
    for sy in (-1,1):
        batch.ellipsoid((x-end*.24*s,y+sy*.18*s,z+.74*s),(.044*s,.035*s,.047*s),pal.darktile,sides=7,rings=4)
        batch.path([(x-end*.13*s,y+sy*.14*s,z+.95*s),(x-end*.34*s,y+sy*.16*s,z+1.10*s),
                    (x-end*.22*s,y+sy*.17*s,z+1.16*s)],.043*s,clay,sides=6)


def ridge_guardian(batch,point,sx,sy,s,material,kind=0):
    x,y,z=point
    batch.box((x,y,z-.08*s),(.85*s,.60*s,.18*s),material)
    batch.ellipsoid((x,y,z+.20*s),(.46*s,.26*s,.23*s),material,sides=9,rings=4)
    for dx in (-1,1):
        batch.rod((x+dx*.29*s,y-.15*s,z-.02*s),(x+dx*.27*s,y-.14*s,z+.18*s),.075*s,material,sides=7)
        batch.rod((x+dx*.29*s,y+.15*s,z-.02*s),(x+dx*.27*s,y+.14*s,z+.18*s),.075*s,material,sides=7)
    batch.ellipsoid((x-sx*.28*s,y-sy*.03*s,z+.43*s),(.18*s,.18*s,.22*s),material,sides=9,rings=4)
    batch.rod((x-sx*.28*s,y-sy*.03*s,z+.57*s),(x-sx*.25*s,y-sy*.03*s,z+.82*s),.05*s,material,r1=.005,sides=6)
    if kind%3==0:
        batch.path([(x+sx*.3*s,y,z+.29*s),(x+sx*.61*s,y,z+.46*s),
                    (x+sx*.5*s,y,z+.73*s)],.07*s,material,sides=6)
