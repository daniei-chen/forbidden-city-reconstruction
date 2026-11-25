"""Photo-led rock face creepers and the branching pine beside Dui Xiu."""
import math
import random

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from mesh_tools import collection
from palace_materials import paint


def pine(loc,target):
    group=collection('堆秀山 · 山前古松',target)
    rng=random.Random(202911)
    light=paint('山前古松 · 灰白斑驳树皮',(.16,.153,.130),second=(.486,.461,.391),
                scale=3.3,rough=.91,grain=74,bump=.013)
    dark=paint('山前古松 · 开裂老皮',(.076,.062,.043),second=(.254,.237,.187),
               scale=7.2,rough=.96,grain=49,bump=.014)
    greens=[paint('山前古松 · 松针 '+str(i+1),color,rough=.72,coat=.05) for i,color in enumerate(
        ((.039,.069,.024),(.062,.091,.025),(.096,.126,.040),(.123,.148,.058)))]
    bark,needles=loc.batch(),loc.batch()
    base=Vector((-7.52,-9.38,.06))

    def stem(points,radii,sides):
        vertices=[]; faces=[]
        for i,(point,r) in enumerate(zip(points,radii)):
            axis=(points[min(i+1,len(points)-1)]-points[max(0,i-1)]).to_track_quat('Z','Y')
            for j in range(sides):
                a=math.tau*j/sides
                rr=r*(1+.107*math.sin(a*3.0+i*.28)+.042*math.cos(a*7.0+i*.63))
                vertices.append(point+axis@Vector((rr*math.cos(a),rr*math.sin(a),0)))
            if i:
                faces.extend(((i-1)*sides+j,(i-1)*sides+(j+1)%sides,i*sides+(j+1)%sides,i*sides+j)
                             for j in range(sides))
        faces.extend((tuple(reversed(range(sides))),tuple(range(len(vertices)-sides,len(vertices)))))
        bark.add(vertices,faces,light if radii[0]>.039 else dark,smooth=True)

    def sprays(end,axis):
        q=axis.to_track_quat('Z','Y')
        for j in range(56):
            a=rng.random()*math.tau;rad=rng.uniform(.42,1.)
            local=Vector((math.cos(a)*rad,math.sin(a)*rad,rng.uniform(-.14,.84)))
            direction=q@local.normalized();root=end+axis*rng.uniform(-.15,.026)
            tip=root+direction*rng.uniform(.064,.159)
            side=direction.cross(axis).normalized()*rng.uniform(.0010,.0022)
            centre=root.lerp(tip,.63)+axis*.012
            needles.add((root,centre-side,tip,centre+side),((0,1,3),(1,2,3)),rng.choice(greens),smooth=True)

    def branch(a,d,length,r,depth):
        d=d.normalized()
        c=a+d*length;mid=a.lerp(c,.46)+Vector((0,0,-length*.118))
        stem((a,mid,c),(r,r*.66,r*.23),9 if depth>1 else 6)
        if not depth:
            sprays(mid,d);sprays(c,d);return
        for k in range(3 if depth>1 else 4):
            theta=2.399*k+rng.uniform(-.19,.19)
            twig=d*.67+Vector((.80*math.cos(theta),.80*math.sin(theta),rng.uniform(.12,.67)))
            branch(mid.lerp(c,(k+.43)/4),twig,length*rng.uniform(.338,.59),r*.405,depth-1)

    for x,y,height,rad,lean in ((-.09,.03,11.45,.365,(2.31,.37)),
                                (-.22,.22,10.86,.261,(-1.14,.72)),(.13,-.13,10.18,.237,(1.21,-1.36))):
        points=[base+Vector((x+lean[0]*t**1.32+.16*math.sin(6*t),y+lean[1]*t+.13*math.sin(8*t),height*t))
                for t in (0,.08,.19,.31,.43,.54,.65,.73,.82,.90,1.)]
        stem(points,[max(.014,rad*(1-i*.091)**.87) for i in range(11)],24)
        for i in range(4,11):
            a=i*2.4+x*6.3
            d=Vector((math.cos(a),math.sin(a),rng.uniform(.19,.43)))
            branch(points[i],d,(3.86-.205*i)*rng.uniform(.76,1.20),max(.034,.14-i*.009),3 if i<8 else 2)
    for k in range(7):
        a=math.tau*k/7;tip=base+Vector((.83*math.cos(a),.83*math.sin(a),-.037))
        stem((base+Vector((0,0,.21)),base.lerp(tip,.49)+Vector((0,0,.07)),tip),(.106,.059,.019),9)
    source={'position_evidence':'Inferred from the Palace Museum photographs; trunk dimensions are not measured.'}
    bark.finish('堆秀山 · 古松分干、根与枝',group,properties=source)
    needles.finish('堆秀山 · 山前松针',group,properties=source)
    return group


def creepers(loc,target,rocks,p):
    """Place each ivy sprig on the first visible limestone face, in metre space."""
    bpy.context.view_layer.update()
    graph=bpy.context.evaluated_depsgraph_get()
    cache={};items=[]
    ray=Vector((-math.sin(loc.yaw),math.cos(loc.yaw),0))
    for obj in rocks.objects:
        xs=[(obj.matrix_world@Vector(co)).x for co in obj.bound_box]
        zs=[(obj.matrix_world@Vector(co)).z for co in obj.bound_box]
        key=obj.data.as_pointer()
        if key not in cache:
            cache[key]=BVHTree.FromObject(obj,graph)
        m=obj.matrix_world.copy();inv=m.inverted_safe()
        dr=inv.to_3x3()@ray
        items.append((min(xs),max(xs),min(zs),max(zs),m,inv,dr.normalized(),dr.length,cache[key]))

    def face_at(x,z):
        origin=Vector(loc.world(x,-8.18,z));limit=11.0;near=None
        for x0,x1,z0,z1,m,inv,direction,scale,tree in items:
            if not (x0-.07<=origin.x<=x1+.07 and z0<=z<=z1):
                continue
            co,_,_,dist=tree.ray_cast(inv@origin,direction,limit*scale)
            if co is not None and dist/scale<limit:
                limit=dist/scale;near=co
        return Vector((x,-8.18+limit-.023,z)) if near is not None else None

    group=collection('堆秀山 · 石缝地锦与攀附藤条',target)
    b,stems=loc.batch(),loc.batch()
    rng=random.Random(120249)
    for x,z,length in ((-5.15,7.95,2.08),(-4.44,5.88,2.42),(-2.92,7.64,2.01),(-2.21,4.97,1.54),
                       (1.84,9.48,2.65),(2.73,6.72,2.46),(4.16,8.21,2.24),(5.16,5.21,1.69)):
        last=None
        for i in range(round(length/.087)):
            u=x+.102*math.sin(i*.43)+.036*math.sin(i*1.03);h=z-i*.087
            node=face_at(u,h)
            if node is None:
                last=None;continue
            if last is not None and (last-node).length<.43:
                stems.rod(last,node,.0045,p.creeper[0],sides=6)
            last=node
            for j in range(4):
                v=u+rng.uniform(-.19,.19); zz=h+rng.uniform(-.071,.095)
                leaf=face_at(v,zz)
                if leaf is None or abs(leaf.y-node.y)>.45:
                    continue
                r=rng.uniform(.041,.088);angle=rng.uniform(-2.8,2.8)
                verts=[leaf+Vector((0,-.018,0))]
                for k in range(10):
                    a=angle+math.tau*k/10
                    rr=r*(.51 if k%2 else 1.)
                    verts.append(leaf+Vector((rr*math.cos(a),-.020-.014*math.sin(a),rr*math.sin(a))))
                b.add(verts,[(0,j+1,(j+1)%10+1) for j in range(10)],rng.choice(p.creeper),smooth=True)
    stems.finish('堆秀山 · 随石面起伏的藤蔓',group)
    b.finish('堆秀山 · 地锦叶片',group,properties={'coverage':'Photo-derived placement on the modeled limestone.'})
    return group
