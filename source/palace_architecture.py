"""Editable architectural assemblies. Dimensions are metres.

Joinery and sculpture are interpretive reconstructions from exterior photographs;
they must not be described as measured conservation drawings or scanned carvings.
"""
import math
import os
from pathlib import Path
import bpy
from mathutils import Vector
from shapely.geometry import Polygon, Point, LineString
from mesh_tools import Batch, collection, polygons, object_to_mesh
from architectural_roofs import swept_roof
from ceremonial_furnishings import add_throne, add_gilded_dragon_columns
from taihe_interior import add_ceiling, add_imperial_plaque
from taihe_survey import X_POSTS, Y_POSTS, GILDED_POSTS, OUTER_POST_HEIGHT, INNER_POST_HEIGHT, SOURCE_TITLE

FONT = None


def railing(batch, line, z, pal, *, spacing=2.15, exclude=None, drains=False):
    if line.length < .8:
        return
    n = max(1, round(line.length/spacing))
    previous = None
    for i in range(n+1):
        p = line.interpolate(line.length*i/n)
        if exclude is not None and exclude.distance(p) < .6:
            previous = None
            continue
        x,y=p.x,p.y
        batch.lathe(x,y,((.23,z),(.23,z+.12),(.14,z+.20),(.13,z+1.13),
                         (.19,z+1.17),(.19,z+1.27),(.06,z+1.42)),pal.marble,sides=10)
        batch.ellipsoid((x,y,z+1.30),(.19,.19,.19),pal.marble,sides=8,rings=4)
        if previous is not None:
            xx,yy=previous
            batch.beam((xx,yy,z+.30),(x,y,z+.30),.17,.16,pal.marble)
            batch.beam((xx,yy,z+1.08),(x,y,z+1.08),.15,.18,pal.marble)
            mid=((x+xx)/2,(y+yy)/2)
            for f in (.25,.5,.75):
                u=xx+(x-xx)*f;v=yy+(y-yy)*f
                batch.rod((u,v,z+.37),(u,v,z+.97),.048,pal.marble,sides=6)
            # Stone quatrefoil openings, expressed as raised carved rails.
            direction=Vector((x-xx,y-yy,0)).normalized()
            pts=[]
            for j in range(17):
                a=j*math.tau/16;r=.21*(1+.20*math.cos(4*a))
                pts.append((mid[0]+direction.x*r*math.cos(a),mid[1]+direction.y*r*math.cos(a),z+.70+r*math.sin(a)))
            batch.path(pts,.033,pal.marble,sides=5)
        previous=(x,y)
        if drains and i<n:
            tangent=line.interpolate(min(line.length,line.length*i/n+.15))
            dx,dy=tangent.x-x,tangent.y-y; ll=math.hypot(dx,dy) or 1
            nx,ny=dy/ll,-dx/ll
            batch.ellipsoid((x+nx*.28,y+ny*.28,z-.17),(.23,.23,.15),pal.marble,sides=8,rings=4)
            batch.ellipsoid((x+nx*.48,y+ny*.48,z-.20),(.15,.15,.11),pal.marble_dark,sides=8,rings=4)


def stairs(batch, start, end, width, z0, z1, pal, *, handrails=True, central=False):
    a,b=Vector((*start,0)),Vector((*end,0)); d=b-a
    length=d.length
    if length<.1 or z1<=z0:
        return
    ux,uy=d.x/length,d.y/length
    # Each step remains an actual editable solid rather than a bump map.
    n=max(2,round((z1-z0)/.17));run=length/n
    yaw=math.atan2(uy,ux)
    for i in range(n):
        dd=(i+.5)*run;h=(i+1)*(z1-z0)/n
        batch.box((a.x+ux*dd,a.y+uy*dd,z0+h/2),(run+.01,width,h),pal.marble,yaw=yaw)
    for sign in (-1,1):
        offset=Vector((-uy,ux,0))*(width/2+.17)*sign
        p=a+offset;q=b+offset
        batch.beam((p.x,p.y,z0+.16),(q.x,q.y,z1+.16),.34,.35,pal.marble)
        if handrails:
            batch.beam((p.x,p.y,z0+1.04),(q.x,q.y,z1+1.04),.15,.20,pal.marble)
            for i in range(max(3,round(length/2))+1):
                t=i/max(3,round(length/2));p0=p.lerp(q,t); zz=z0+(z1-z0)*t
                batch.rod((p0.x,p0.y,zz),(p0.x,p0.y,zz+1.18),.13,pal.marble,sides=10)
    if central:
        # Raised cloud/dragon scrolls; a documented interpretive relief, not a scan.
        side=Vector((-uy,ux,0))
        vv=[(a.x+side.x*width*.27,a.y+side.y*width*.27,z0+.05),
            (a.x-side.x*width*.27,a.y-side.y*width*.27,z0+.05),
            (b.x-side.x*width*.27,b.y-side.y*width*.27,z1+.05),
            (b.x+side.x*width*.27,b.y+side.y*width*.27,z1+.05)]
        batch.face(vv,pal.marble)
        for i in range(7):
            t=(i+.5)/7;c=a.lerp(b,t);zz=z0+(z1-z0)*t+.10
            pts=[]
            for j in range(21):
                f=-1+2*j/20;off=math.sin(f*math.pi*1.7+i)*width*.16
                pts.append((c.x+side.x*off+ux*f*.65,c.y+side.y*off+uy*f*.65,zz+f*.65*(z1-z0)/length))
            batch.path(pts,.055,pal.marble,sides=6)


def dougong(batch,x,y,z,pal, *, scale=1., direction=(0,-1)):
    dx,dy=direction
    yaw=math.atan2(dx,-dy)
    ux,uy=-dy,dx
    for tier in range(5):
        level=z+tier*.218*scale
        reach=(.29+tier*.13)*scale
        projection=(.02+tier*.115)*scale
        cx,cy=x+dx*projection,y+dy*projection
        batch.box((cx,cy,level),(reach*1.9,.24*scale,.155*scale),pal.teal if tier%2 else pal.blue,yaw=yaw)
        batch.box(((x+cx)/2,(y+cy)/2,level+.044*scale),(.21*scale,projection+.30*scale,.15*scale),pal.blue,yaw=yaw)
        for sign in (-1,1):
            px,py=cx+sign*ux*reach*.70,cy+sign*uy*reach*.70
            batch.box((px,py,level+.12*scale),(.205*scale,.28*scale,.12*scale),pal.teal,yaw=yaw)
            batch.box((px+dx*.147*scale,py+dy*.147*scale,level+.12*scale),(.16*scale,.021*scale,.040*scale),pal.giltpaint,yaw=yaw)


def frieze(batch,width,depth,z,pal,*,bay=4.7,height=.70,ornate=True):
    sides=((width,0,-depth/2,1,0,0,-1),(width,0,depth/2,1,0,0,1),
           (depth,-width/2,0,0,1,-1,0),(depth,width/2,0,0,1,1,0))
    for length,x,y,ux,uy,nx,ny in sides:
        yaw=math.atan2(uy,ux)
        def face_point(u,v,off=.177):
            return (x+ux*u+nx*off,y+uy*u+ny*off,z+v)
        batch.box((x,y,z),(length,.30,height),pal.blue,yaw=yaw)
        for delta in (-.45,.45):
            batch.box(face_point(0,height*delta),(length,.039,height*.034),pal.giltpaint,yaw=yaw)
        if not ornate:
            continue
        n=max(1,round(length/bay));step=length/n
        for i in range(n):
            center=-length/2+(i+.5)*step
            batch.box(face_point(center,0,.16),(step*.87,.026,height*.76),pal.teal,yaw=yaw)
            for sign in (-1,1):
                pts=[(center+sign*s*step,v*height) for s,v in ((.43,-.31),(.30,-.31),(.23,-.17),(.21,0),(.23,.17),(.30,.31),(.43,.31))]
                batch.path([face_point(u,v,.181) for u,v in pts],height*.018,pal.giltpaint,sides=6)
                for j in range(3):
                    cu=center+sign*step*(.05+j*.068)
                    cv=height*(.11 if j%2 else -.11)
                    spiral=[]
                    for k in range(17):
                        a=k*math.tau/13
                        r=height*(.020+.107*k/16)
                        spiral.append(face_point(cu+math.cos(a)*r*sign,cv+math.sin(a)*r,.192))
                    batch.path(spiral,height*.0105,pal.giltpaint,sides=5)


def window_panel(batch,x,y,z,width,height,pal,*,lattice=True):
    batch.box((x,y,z+height/2),(width,.15,height),pal.door)
    batch.box((x,y-.09,z+height*.67),(width*.83,.035,height*.52),pal.inset)
    for off in (-width*.47,width*.47):
        batch.box((x+off,y-.13,z+height/2),(.065,.09,height),pal.red)
    for zz in (.10,height*.38,height*.94):
        batch.box((x,y-.13,z+zz),(width,.08,.08),pal.red)
    batch.box((x,y-.095,z+height*.21),(width*.76,.025,height*.25),pal.paint)
    if lattice:
        w=width*.81;h=height*.50;zbase=z+height*.415;pitch=.33
        # True diagonal wooden lattice, clipped to each rectangular window field.
        from shapely.geometry import box
        field=box(-w/2,0,w/2,h)
        for sign in (-1,1):
            for k in range(-int(h/pitch)-3,int(w/pitch)+int(h/pitch)+4):
                segment=LineString([(k*pitch-w/2,-1),(k*pitch-w/2+sign*(h+2),h+1)]).intersection(field)
                if segment.geom_type=='LineString' and segment.length>.08:
                    a,b=list(segment.coords)[0],list(segment.coords)[-1]
                    batch.beam((x+a[0],y-.15,zbase+a[1]),(x+b[0],y-.15,zbase+b[1]),.032,.036,pal.red)


def hall(name,target,pal,*,origin,yaw=0.,width,depth,floor,eave,upper_eave=None,
         rise=7.,bays=9,deep_bays=5,kind='hip',tiles=True,beasts=7,plaque=None,open_gate=False,
         lower_stop=.57,roof_width=None,roof_depth=None,post_radius=.40,interior_posts=False,
         terminal_height=None,roof_grey=False,open_central_portal=False,ceremonial_interior=False):
    group=collection(name,target);body=Batch(origin,yaw);joinery=Batch(origin,yaw)
    W,D=width,depth;roofW=roof_width or W+5.0;roofD=roof_depth or D+5.0
    body.box((0,0,floor-.12),(W+1.4,D+1.4,.24),pal.marble)
    measured=name=='太和殿' and ceremonial_interior
    posttop=eave-1.58
    xs=list(X_POSTS) if measured else [-W/2+i*W/bays for i in range(bays+1)]
    ys=list(Y_POSTS) if measured else [-D/2+i*D/deep_bays for i in range(deep_bays+1)]
    if measured:
        posttop=floor+OUTER_POST_HEIGHT
        group['column_grid_source']=SOURCE_TITLE
        group['column_grid_note']='Published mean bay spans; individual lean, ovality and row-to-row differences are not reproduced.'
        group['column_x_centres_m']=xs
        group['column_y_centres_m']=ys
    count=0
    for j,y in enumerate(ys):
        for i,x in enumerate(xs):
            edge=i in (0,bays) or j in (0,deep_bays)
            if not edge and not interior_posts:
                continue
            count+=1
            top=(floor+INNER_POST_HEIGHT) if measured and not edge else posttop
            material=pal.gold if measured and (x,y) in GILDED_POSTS else pal.red
            body.lathe(x,y,((post_radius*1.26,floor),(post_radius*1.26,floor+.19),
                             (post_radius*.99,floor+.32),(post_radius*.94,top-.28),
                             (post_radius*.88,top)),material,sides=32 if measured else 16)
            body.lathe(x,y,((post_radius*1.43,floor-.03),(post_radius*1.43,floor+.13),
                             (post_radius*1.20,floor+.28)),pal.marble,sides=16)
            if edge:
                direction=(0,-1 if j==0 else 1) if j in (0,deep_bays) else (-1 if i==0 else 1,0)
                dougong(joinery,x,y,posttop+.49,pal,scale=1.0 if W>50 else .79,direction=direction)
    wall_y=-ys[1] if measured else D/2-min(2.3,D*.13)
    portal_clear_w=min(6.95,(xs[6]-xs[5])*.83) if measured else (min(4.9,W/bays*.88) if open_central_portal else 0.)
    if not open_gate:
        if open_central_portal:
            # Construct an enclosed room around a real, traversable central entry.
            # The previous solid black mass swallowed all columns and could not be entered.
            wall_bottom=floor+.18
            wall_top=(floor+INNER_POST_HEIGHT) if measured else eave-1.58
            wall_h=wall_top-wall_bottom
            wall_z=(wall_top+wall_bottom)/2
            back_y=ys[-2]+.20 if measured else D/2-.24
            # Leave the sampled front wall and its latticed bays open to the real
            # panel assembly below. Close only the north end; exterior side bays
            # already receive individual timber-and-lattice panels.
            body.box((0,back_y,wall_z),(W-2.2,.52,wall_h),pal.door)
            body.box((0,0,floor+.08),(W-1.1,D-.8,.16),pal.terrace_floor)
        else:
            body.box((0,0,floor+(eave-floor)*.43),(W-4.4,max(2.,D-5), (eave-floor)*.86),pal.black)
        h=min(6.5,(eave-floor)*.70)
        if measured:
            top=floor+INNER_POST_HEIGHT
            low=floor+.18+h
            # Recess the tall enclosure behind the upper frieze. Keeping it
            # at the lower door plane hid the blue-green upper painted beams.
            body.box((0,-wall_y+.46,(top+low)/2),(xs[-2]-xs[1]+.4,.28,top-low),pal.door)
        for sy in (-1,1):
            y=sy*wall_y
            for bay in range(bays):
                bay_width=xs[bay+1]-xs[bay]
                xx=(xs[bay]+xs[bay+1])/2
                if open_central_portal and sy<0 and bay==bays//2:
                    # The middle ceremonial doorway remains an actual opening; the
                    # two leaves are hinged into the hall rather than painted on.
                    continue
                panels=max(3,round(bay_width/1.1)) if measured else (4 if W/bays>3.4 else 3)
                for j in range(panels):
                    xp=xx+(j-(panels-1)/2)*(bay_width*.88/panels)
                    # Face orientation is reversed for north facade by its own local batch.
                    if sy<0:
                        window_panel(joinery,xp,y,floor+.18,bay_width*.88/panels-.04,h,pal,lattice=True)
                    else:
                        body.box((xp,y,floor+h/2),(bay_width*.88/panels-.04,.16,h),pal.door)
                        for dz in (.3,h*.40,h*.90):
                            joinery.box((xp,y+.10,floor+dz),(bay_width*.84/panels,.07,.055),pal.giltpaint)
        for sx in (-1,1):
            if measured:
                side_x=(xs[1]-.17) if sx<0 else (xs[-2]+.17)
                body.box((side_x,0,floor+INNER_POST_HEIGHT/2),(.32,2*wall_y,INNER_POST_HEIGHT),pal.door)
            else:
                body.box((sx*(W/2-1.2),0,floor+(eave-floor)*.43),(.32,D-4,(eave-floor)*.86),pal.paint)
        if open_central_portal:
            portal=Batch(origin,yaw)
            clear_w=portal_clear_w
            jamb_h=min(6.15,eave-floor-2.3)
            yy=-wall_y-.18
            # Stone threshold, vermilion jambs, lacquered lintel, and a carved head.
            portal.box((0,-wall_y,floor+.12),(clear_w+.58,.52,.24),pal.marble)
            for sx in (-1,1):
                portal.box((sx*clear_w/2,yy,floor+jamb_h/2),(.24,.30,jamb_h),pal.red)
                for dx in (-.075,.075):
                    portal.box((sx*(clear_w/2+dx),yy-.16,floor+jamb_h/2),(.035,.035,jamb_h*.91),pal.giltpaint)
            portal.box((0,yy,floor+jamb_h+.13),(clear_w+.48,.35,.34),pal.red)
            for zoff in (-.07,.07):
                portal.box((0,yy-.19,floor+jamb_h+.13+zoff),(clear_w+.33,.05,.035),pal.gold)
            portal.box((0,yy-.21,floor+jamb_h-.57),(clear_w-.34,.045,.045),pal.gold)
            # Two sculpted leaves stand open inside the aperture at opposite angles.
            leaf_len=clear_w/2-.12
            for sign in (-1,1):
                hinge_x=sign*clear_w/2
                swing=-math.radians(68) if sign>0 else math.radians(68)
                cx=hinge_x-sign*math.cos(swing)*leaf_len/2
                cy=-wall_y+math.sin(abs(swing))*leaf_len/2
                door_yaw=swing
                portal.box((cx,cy,floor+jamb_h*.47),(leaf_len,.19,jamb_h*.91),pal.door,yaw=door_yaw)
                for local_x in (-leaf_len*.40,leaf_len*.40):
                    px=cx+local_x*math.cos(door_yaw);py=cy+local_x*math.sin(door_yaw)
                    portal.box((px,py-.12,floor+jamb_h*.49),(.07,.06,jamb_h*.82),pal.red,yaw=door_yaw)
                for fraction in (.18,.39,.61,.82):
                    px=cx+(fraction-.5)*leaf_len*math.cos(door_yaw)
                    py=cy+(fraction-.5)*leaf_len*math.sin(door_yaw)
                    portal.box((px,py-.125,floor+jamb_h*.48),(leaf_len*.105,.075,jamb_h*.74),pal.inset,yaw=door_yaw)
                    for zf in (.16,.37,.60,.83):
                        portal.ellipsoid((px,py-.18,floor+jamb_h*zf),(.048,.035,.048),pal.gold,sides=8,rings=4)
                # Small glazed, carved brass fittings on each leaf's inward face.
                for zf in (.24,.50,.76):
                    px=cx-sign*.18*math.cos(door_yaw)
                    py=cy-sign*.18*math.sin(door_yaw)-.16
                    portal.ellipsoid((px,py,floor+jamb_h*zf),(.080,.038,.105),pal.gold,sides=9,rings=5)
            portal.finish(name+' · open ceremonial doorway and hinged leaves',group,
                          properties={'clear_opening_m':round(clear_w,3),'walkable':True,'construction':'interpretive reconstruction'})
            if ceremonial_interior:
                interior=Batch(origin,yaw)
                # The floor is modeled as genuine individual fired bricks at the
                # published 2 chi 2 cun module (~0.704 m), with narrow seams.
                # This is geometry, not a photographic floor texture.
                brick=.704
                xcount=max(1,math.floor((W-3.0)/brick))
                ycount=max(1,math.floor((D-3.0)/brick))
                span_x=xcount*brick;span_y=ycount*brick
                sx0=-span_x/2;sy0=-span_y/2
                bricks=(pal.goldbrick if hasattr(pal,'goldbrick') else pal.marble_dark)
                for row in range(ycount):
                    for col in range(xcount):
                        xx=sx0+(col+.5)*brick;yy=sy0+(row+.5)*brick
                        # 12 mm joints and a barely visible hand-laid height variation.
                        z=floor+.225+.002*((col*13+row*7)%5)
                        interior.box((xx,yy,z),(brick-.012,brick-.012,.045),bricks)
                interior.finish('太和殿 · individually laid goldbrick floor',group,
                                properties={'brick_module_m':.704,'geometry':'actual individual solids'})
                ceiling=Batch(origin,yaw)
                ceiling_z=add_ceiling(ceiling,pal,xs,ys,floor)
                ceiling.finish('太和殿 · open recessed caisson and painted coffer ceiling',group,
                               properties={'ceiling_underside_z_m':ceiling_z,
                                           'caisson_center_local_m':[0.,5.60,ceiling_z],
                                           'open_caisson':True,
                                           'reference':'Palace Museum caisson/interior photographs; ornament and elevations inferred'})
                furniture=Batch(origin,yaw)
                add_throne(furniture,stairs,floor,D,W,pal)
                furniture.finish('太和殿 · seven-panel screen, carved throne and ritual furnishings',group,
                                 properties={'screen_panels':7,'carving':'authored relief, not a scan',
                                             'reference':'Palace Museum frontal throne photograph',
                                             'dimensions':'Chair and footstool from Palace Museum catalogue p.012; other furnishings and relief inferred'})
                dragon_posts=Batch(origin,yaw)
                add_gilded_dragon_columns(dragon_posts,pal,post_radius=post_radius,floor=floor)
                dragon_posts.finish('太和殿 · six gilded dragon-wrapped interior columns',group,
                                    properties={'count':6,'centres_local_m':str(GILDED_POSTS),
                                                'source':'Measured column grid; photograph-led gold sheath and authored dragon relief'})
                add_imperial_plaque(group,pal,origin,yaw)
    frieze(joinery,W+.2,D+.2,posttop+.18,pal,bay=W/bays,height=.65 if W>40 else .45)
    frieze(joinery,W+.56,D+.56,eave-.20,pal,bay=W/bays,height=.34,ornate=False)
    for sy in (-1,1):
        for i in range(bays):
            for f in (.28,.72):
                dougong(joinery,xs[i]+f*(xs[i+1]-xs[i]),sy*(D/2+.09),posttop+.52,pal,
                        scale=.92 if W>45 else .72,direction=(0,sy))
    hero=name=='太和殿'
    if upper_eave is not None:
        # The lower eave is an annular skirt, without a hidden second full roof.
        swept_roof('下檐 · lower curved skirt',group,pal,origin=origin,yaw=yaw,width=roofW,depth=roofD,
                   eave=eave,rise=min(6.0,max(2.6,(upper_eave-eave)*1.42)),kind='hip' if kind=='xieshan' else kind,
                   stop=lower_stop,tiles=tiles,pitch=.34 if hero else .40,beasts=min(beasts,7),detail=2 if hero else 1)
        upperW=W*.86;upperD=D*.70
        upper_gap=upper_eave-eave
        if ceremonial_interior:
            # The upper storey is a hollow timber enclosure, not a black solid
            # intersecting the raised interior ceiling and blocking the caisson.
            for sign in (-1,1):
                body.box((0,sign*upperD/2,(eave+upper_eave)/2),(upperW,.26,upper_gap),pal.door)
                body.box((sign*upperW/2,0,(eave+upper_eave)/2),(.26,upperD,upper_gap),pal.door)
        else:
            body.box((0,0,(eave+upper_eave)/2),(upperW-.12,upperD-.12,upper_gap),pal.black)
        frieze(joinery,upperW,upperD,upper_eave-upper_gap*.60,pal,bay=4,height=upper_gap*.56)
        frieze(joinery,upperW+.46,upperD+.46,upper_eave-.21,pal,bay=4,height=.31,ornate=False)
        for sy in (-1,1):
            for i in range(2*bays+1):
                xx=-upperW/2+i*upperW/(2*bays)
                dougong(joinery,xx,sy*upperD/2,upper_eave-.71,pal,scale=.56,direction=(0,sy))
        swept_roof('上檐 · upper principal roof',group,pal,origin=origin,yaw=yaw,width=roofW*.885,depth=roofD*.78,
                   eave=upper_eave,rise=rise,kind=kind,tiles=tiles,pitch=.34 if hero else .40,beasts=beasts,
                   detail=2 if hero else 1,terminal_height=terminal_height)
        if plaque:
            plaque_object(plaque,group,pal,origin,yaw,(0,-upperD/2-.28,upper_eave-1.13),height=1.68 if W>40 else 1.31)
    else:
        swept_roof('屋面 · principal roof',group,pal,origin=origin,yaw=yaw,width=roofW,depth=roofD,
                   eave=eave,rise=rise,kind=kind,tiles=tiles,pitch=.40,beasts=beasts,detail=1,grey=roof_grey)
        if plaque:
            plaque_object(plaque,group,pal,origin,yaw,(0,-wall_y-.24,eave-2),height=1.8)
    obj=body.finish(name+' · columns, plinths and recessed timber',group,properties={
        'column_count':count,'geometry_units':'metres','interpretation':'Photographic reconstruction; editable geometry'})
    joinery.finish(name+' · dougong, lattice and painted beam relief',group)
    return group


def plaque_object(text,target,pal,origin,yaw,pos,*,height=2.):
    x,y,z=pos;w=height*.68
    b=Batch(origin,yaw)
    b.box((x,y,z),(w,.16,height),pal.cobalt)
    for off in (-1,1):
        b.box((x+off*w*.54,y-.10,z),(.105,.15,height*1.1),pal.gold)
        b.box((x,y-.10,z+off*height*.53),(w*1.15,.15,.12),pal.gold)
    for sx in (-1,1):
        for sz in (-1,1):
            b.path([(x+sx*w*.40,y-.19,z+sz*height*.50),
                    (x+sx*w*.68,y-.19,z+sz*height*.56),
                    (x+sx*w*.64,y-.19,z+sz*height*.40)],.07,pal.giltpaint,sides=7)
    frame=b.finish('匾额 · '+text+' · three-dimensional frame',target)

    # The blue enamel panels are mapped from the inspected Palace Museum
    # close-ups when a building-specific crop exists.  The frame remains real
    # geometry, so the image is only the photographed painted face and does not
    # turn the plaque into a flat billboard.
    photo_names={
        '太和殿': 'taihe_title_reference_crop.jpg',
        '中和殿': 'zhonghe_plaque_face_reference.jpg',
        '保和殿': 'baohe_plaque_face_reference.jpg',
        '午门': 'wumen_plaque_face_reference.jpg',
        '乾清宫': 'qianqing_plaque_face_reference.jpg',
    }
    photo_path=Path(__file__).parent/'textures'/photo_names.get(text,'')
    if photo_path.is_file():
        material_name='匾额 · '+text+' · Palace Museum photographic face'
        material=bpy.data.materials.get(material_name)
        if material is None:
            material=bpy.data.materials.new(material_name);material.use_nodes=True
            material['source_reference']=str(photo_path.name)
            image=bpy.data.images.load(str(photo_path),check_existing=True)
            image['source_reference']=str(photo_path.name)
            node=material.node_tree.nodes.new('ShaderNodeTexImage');node.name='实拍匾心 · '+text
            node.image=image;node.interpolation='Linear';node.extension='CLIP'
            bsdf=material.node_tree.nodes.get('Principled BSDF')
            material.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
            bsdf.inputs['Roughness'].default_value=.55
            bsdf.inputs['Metallic'].default_value=.05
        face=Batch(origin,yaw)
        face.face([(x-w/2,y-.091,z-height/2),(x+w/2,y-.091,z-height/2),
                   (x+w/2,y-.091,z+height/2),(x-w/2,y-.091,z+height/2)],material,
                  uv=[(0,0),(1,0),(1,1),(0,1)])
        face.finish('匾额 · '+text+' · photographed blue enamel face',target,
                    properties={'source_reference':photo_path.name,
                                'geometry_note':'Photographic face on editable 3D plaque frame'})
        return

    # Actual extruded editable glyph meshes for plaques without an inspected
    # building-specific face crop.
    global FONT
    if FONT is None:
        configured=os.environ.get('PALACE_CJK_FONT')
        font_path=Path(configured) if configured else Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/simkai.ttf'
        if not font_path.is_file():
            frame['inscription']='Optional CJK font unavailable. Set PALACE_CJK_FONT to a local CJK font path.'
            return
        FONT=bpy.data.fonts.load(str(font_path))
    for i,ch in enumerate(text):
        curve=bpy.data.curves.new('楷书 '+ch,'FONT');curve.body=ch;curve.font=FONT
        curve.align_x='CENTER';curve.align_y='CENTER';curve.size=height/(len(text)+.5)
        curve.extrude=.008;curve.bevel_depth=.003;curve.bevel_resolution=1
        obj=bpy.data.objects.new('匾字 '+ch,curve);target.objects.link(obj)
        obj.location=Vector(origin)+Vector((math.cos(yaw)*x-math.sin(yaw)*(y-.105),math.sin(yaw)*x+math.cos(yaw)*(y-.105),z+height*.30-i*height*.30))
        obj.rotation_euler=(math.pi/2,0,yaw)
        curve.materials.append(pal.gold)
        bpy.context.view_layer.update();object_to_mesh(obj)


def arch_section(x,w,h,*,bottom=-.25,rise=None):
    radius=w/2
    crown=rise or radius
    spring=h-crown
    bottom=min(bottom,spring-.20)
    coords=[(x-radius,bottom),(x+radius,bottom)]
    coords.extend((x+radius*math.cos(i*math.pi/24),spring+crown*math.sin(i*math.pi/24)) for i in range(25))
    return Polygon(coords)


def arch_mesh(batch,section,depth,material):
    temp=Batch();temp.solid_welded(section,-depth/2,depth/2,material)
    batch.add([(x,-d,z) for x,z,d in temp.v],temp.f,material)


def meridian_platform(name,target,pal,shape):
    """Use the mapped U plan and cut the three straight and two turned openings."""
    foundation=Batch();foundation.solid_welded(shape,0,12,pal.paint)
    obj=foundation.finish(name,target)
    cutters=[]
    courses=[(-16.58,-470,5.1,6.65,34,0),(-3.75,-470,6.0,7.45,34,0),(9.96,-470,5.1,6.65,34,0)]
    for cx,toward in ((-53.5,1),(48.5,-1)):
        courses.append((cx,-476,5.0,6.0,42,0))
        courses.append((cx+toward*6.9,-492.6,4.9,5.7,18.2,math.pi/2))
    for i,(x,y,w,h,length,yaw) in enumerate(courses):
        cutter=Batch((x,y,0),yaw)
        arch_mesh(cutter,arch_section(0,w,h),length,pal.masonry)
        tool=cutter.finish('门洞切割体 '+str(i),target);cutters.append(tool)
        mod=obj.modifiers.new('门洞 '+str(i+1),'BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=tool
    bpy.context.view_layer.update()
    baked=object_to_mesh(obj)
    for tool in cutters:bpy.data.objects.remove(tool,do_unlink=True)
    baked['straight_tunnels']=3;baked['turned_tunnels']=2
    trim=Batch()
    for p in polygons(shape):
        from mesh_tools import line_boxes
        coords=list(p.exterior.coords)
        line_boxes(trim,coords,11.57,11.87,.22,pal.masonry)
        line_boxes(trim,coords,11.86,12.06,.28,pal.marble_dark)
        railing(trim,LineString(coords),12.03,pal,spacing=2.2)
        # The rear bar and side wings have stone courses at ground level.
        sill=LineString(coords).difference(
            Point(-3.75,-470).buffer(18).union(Point(-53.5,-467).buffer(12)).union(Point(48.5,-467).buffer(12)))
        for line in (sill.geoms if hasattr(sill,'geoms') else [sill]):
            if line.geom_type=='LineString':line_boxes(trim,list(line.coords),.05,.43,.26,pal.marble_dark)
    trim.finish('午门 · 墩台石护沿与栏板',target)
    return baked


def arch_block(name,target,pal,*,origin,width,depth,height,openings,yaw=0.,rise=None,stone=False):
    """Extruded facade cross-section with genuinely open arch-shaped holes."""
    shape=Polygon([(-width/2,0),(width/2,0),(width/2,height),(-width/2,height)])
    for x,w,h in openings:
        shape=shape.difference(arch_section(x,w,h,rise=rise))
    batch=Batch(origin,yaw)
    # Build a welded solid with Z as original cross-section's Y, and Y as depth.
    arch_mesh(batch,shape,depth,pal.bank if stone else pal.paint)
    obj=batch.finish(name,target,properties={'passages':'Actual empty arch tunnels; no black painted door substitutes'})
    stones=Batch(origin,yaw)
    for x,w,h in openings:
        r=w/2;crown=rise or r;spring=h-crown
        for side in (-1,1):
            y=side*(depth/2+.015)
            for i in range(18):
                a=i*math.pi/18;b=(i+1)*math.pi/18
                stones.face([(x+r*math.cos(a),y,spring+crown*math.sin(a)),
                             (x+r*math.cos(b),y,spring+crown*math.sin(b)),
                             (x+(r+.28)*math.cos(b),y,spring+(crown+.28)*math.sin(b)),
                             (x+(r+.28)*math.cos(a),y,spring+(crown+.28)*math.sin(a))],pal.marble_dark)
            if spring>0:
                for sign in (-1,1):
                    stones.box((x+sign*(r+.16),y,spring/2),(.31,.08,spring),pal.bank)
    stones.finish(name+' · arch voussoirs',target)
    return obj


def bronze_lion(batch,x,y,z,pal,*,scale=1.,direction=1):
    s=scale
    batch.box((x,y,z+.33*s),(2.3*s,2.1*s,.66*s),pal.marble)
    batch.box((x,y,z+.74*s),(1.85*s,1.7*s,.18*s),pal.marble_dark)
    batch.ellipsoid((x,y,z+1.45*s),(.58*s,.57*s,.75*s),pal.bronze,sides=12,rings=6)
    for dx in (-1,1):
        batch.rod((x+dx*.32*s,y-direction*.30*s,z+.85*s),(x+dx*.32*s,y-direction*.27*s,z+1.68*s),.16*s,pal.bronze,sides=10)
        batch.ellipsoid((x+dx*.32*s,y-direction*.43*s,z+.91*s),(.23*s,.32*s,.12*s),pal.bronze,sides=9,rings=4)
    batch.ellipsoid((x,y-direction*.13*s,z+2.05*s),(.59*s,.48*s,.53*s),pal.bronze,sides=12,rings=6)
    for k in range(14):
        a=k*math.tau/14
        batch.ellipsoid((x+math.sin(a)*.48*s,y+direction*.13*s,z+(2.05+math.cos(a)*.45)*s),(.16*s,.18*s,.17*s),pal.bronze,sides=7,rings=4)
    batch.ellipsoid((x,y-direction*.53*s,z+2.01*s),(.36*s,.23*s,.20*s),pal.bronze,sides=10,rings=4)
    for sign in (-1,1):
        batch.ellipsoid((x+sign*.23*s,y-direction*.51*s,z+2.24*s),(.09*s,.06*s,.07*s),pal.black,sides=7,rings=4)
    batch.path([(x+.25*s,y+.37*s,z+1.3*s),(x+.67*s,y+.48*s,z+1.58*s),
                (x+.77*s,y+.43*s,z+1.92*s),(x+.55*s,y+.32*s,z+2.05*s)],.10*s,pal.bronze,sides=8)


def ritual_vessel(batch,x,y,z,pal):
    batch.lathe(x,y,((.9,z),(.9,z+.18),(.68,z+.30),(.65,z+.48),(.87,z+.56),
                      (.95,z+1.32),(.95,z+1.48),(1.02,z+1.54),(.94,z+1.65)),pal.bronze,sides=24)
    for side in (-1,1):
        batch.path([(x+side*.87,y,z+.8),(x+side*1.12,y,z+.87),(x+side*1.18,y,z+1.15),
                    (x+side*.93,y,z+1.3)],.09,pal.bronze,sides=8)


def corner_tower(name,target,pal,foundation,platform):
    """Three eaves on the mapped masonry podium with crossed Xieshan ridges."""
    x,y=platform.centroid.coords[0]
    origin=(x,y,0);g=collection(name,target)
    masonry=Batch()
    masonry.solid_xy(foundation,0,9.9,pal.masonry)
    masonry.solid_xy(platform,9.9,11.02,pal.bank,top=pal.terrace_floor)
    masonry.solid_xy(platform.buffer(.21,join_style=2),10.85,11.02,pal.marble_dark)
    masonry.finish(name+' · 原始围合轮廓与石墩台',g)
    b=Batch(origin)
    for bottom,top,w in ((11.02,16.7,12.1),(17.85,20.6,9.7),(21.48,23.5,6.6)):
        height=top-bottom
        b.box((0,0,(top+bottom)/2),(w-.68,w-.68,height),pal.door)
        for yaw in (0,math.pi/2,math.pi,math.pi*1.5):
            side=Batch(origin,yaw)
            for i in range(5):
                xx=-w/2+i*w/4
                side.rod((xx,-w/2,bottom),(xx,-w/2,top-.44),.14,pal.red,sides=12)
                dougong(side,xx,-w/2,top-.42,pal,scale=.48)
            for i in range(4):
                window_panel(side,-w/2+(i+.5)*w/4,-w/2+.24,bottom+.14,w/4*.82,height*.76,pal,lattice=bottom<12)
            side.finish(name+' · 分面格扇与斗栱',g)
        frieze(b,w,w,top-.59,pal,bay=2.85,height=.48)
    b.finish(name+' · 十字楼身与彩画梁枋',g)
    swept_roof('首层腰檐',g,pal,origin=origin,width=17.3,depth=16.45,eave=16.64,rise=2.8,
               kind='hip',stop=.43,tiles=True,pitch=.34,beasts=5)
    swept_roof('二层檐与四角垂脊',g,pal,origin=origin,width=15.30,depth=14.45,eave=20.02,rise=3.5,
               kind='hip',stop=.53,tiles=True,pitch=.34,beasts=5)
    for index,yaw in enumerate((0,math.pi/2),1):
        swept_roof('二层歇山抱厦 '+str(index),g,pal,origin=origin,yaw=yaw,width=14.2,depth=7.3,
                   eave=20.36,rise=2.7,kind='xieshan',tiles=True,pitch=.34,beasts=3,terminal_height=.62)
        swept_roof('上层相交歇山 '+str(index),g,pal,origin=origin,yaw=yaw,width=12.2,depth=7.3,
                   eave=23.48,rise=3.10,kind='xieshan',tiles=True,pitch=.32,beasts=3,terminal_height=.74)
    crown=Batch(origin)
    crown.lathe(0,0,((.28,26.58),(.28,26.76),(.13,26.92),(.21,27.03),(.18,27.27),
                     (.075,27.32),(.045,27.50)),pal.gold,sides=20)
    crown.finish(name+' · 交脊鎏金宝顶',g,properties={'museum_overall_height_m':27.50})
    return g
