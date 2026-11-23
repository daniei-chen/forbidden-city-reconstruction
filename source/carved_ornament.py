"""Editable raised Chinese cloud and dragon ornaments for architectural work.

Authored sculpture from reference silhouettes, not a scan or traced antiquity.
The same local XY relief can be laid on a ceiling, a vertical screen or a post.
"""
import math
from mathutils import Vector


def cloud(batch, point, scale, material, *, facing='front', rotation=0.):
    x, y, z = point
    co, si = math.cos(rotation), math.sin(rotation)
    points = []
    for i in range(43):
        a = i / 42 * math.tau * 1.35
        r = scale * (.08 + .43 * i / 42)
        u, v = r * math.cos(a), r * math.sin(a)
        u, v = co * u - si * v, si * u + co * v
        points.append((x+u, y-.015, z+v) if facing == 'front' else (x+u, y+v, z))
    batch.path(points, scale*.025, material, sides=6)


def dragon(batch, point, width, height, pal, *, facing='front', mirror=False,
           detailed=True, z_relief=.07, phase=0.):
    """Connected tapering body with scales, mane, horns, whiskers and four claws."""
    center = Vector(point)
    sign = -1. if mirror else 1.

    def mapped(u, v, relief=0.):
        u *= sign
        if facing == 'front':
            return center + Vector((u*width, -relief, v*height))
        return center + Vector((u*width, v*height, -relief))

    count = 117 if detailed else 67
    line = []
    for i in range(count):
        t = i / (count-1)
        u = .32*math.sin(t*math.tau*1.58+phase)*(1-.23*t)
        v = -.43 + .83*t
        line.append(mapped(u, v, z_relief + .008*math.sin(t*15)))
    verts = []
    sides = 9 if detailed else 7
    for i, point in enumerate(line):
        tangent = line[min(count-1, i+1)] - line[max(0, i-1)]
        tangent.normalize()
        normal = Vector((0,-1,0)) if facing == 'front' else Vector((0,0,-1))
        side = tangent.cross(normal).normalized()
        t = i/(count-1)
        r = min(width,height)*(.007+.028*math.sin(min(1,t*2.2)*math.pi/2))
        for j in range(sides):
            a = j/sides*math.tau
            verts.append(tuple(point + side*(r*math.cos(a)) + normal*(r*.52*math.sin(a))))
    faces = [(i*sides+j, i*sides+(j+1)%sides, (i+1)*sides+(j+1)%sides,
              (i+1)*sides+j) for i in range(count-1) for j in range(sides)]
    batch.add(verts, faces, pal.gold, smooth=True)
    # The scales are short crescent meshes that follow the body, rather than
    # spheres scattered around the post or an unconnected helical wire.
    if detailed:
        for i in range(8,count-6,3):
            t = i/(count-1)
            tangent=(line[i+1]-line[i-1]).normalized()
            normal=Vector((0,-1,0)) if facing=='front' else Vector((0,0,-1))
            side=tangent.cross(normal).normalized()
            radius=min(width,height)*(.009+.020*min(1,t*2))
            for row in (-1,0,1):
                p=line[i]+side*radius*row*.61+normal*radius*.48
                pts=[tuple(p+side*radius*.40*math.cos(a)+tangent*radius*.32*math.sin(a))
                     for a in [math.pi*k/7 for k in range(8)]]
                batch.path(pts,max(.0025,radius*.10),pal.giltpaint,sides=5)
    head=line[-1]
    unit=min(width,height)
    r=unit*.062
    if facing=='front':
        batch.ellipsoid(tuple(head), (r,.045+r*.22,r*.83),pal.gold,sides=14,rings=8)
        batch.ellipsoid(tuple(head+Vector((0,-r*.36,-r*.54))),
                        (r*.90,r*.41,r*.38),pal.gold,sides=12,rings=6)
        for sx in (-1,1):
            eye=head+Vector((sx*r*.54,-r*.45,r*.15))
            batch.ellipsoid(tuple(eye),(r*.16,r*.12,r*.13),pal.door,sides=9,rings=5)
            batch.path([tuple(head+Vector((sx*r*.42,0,r*.50))),
                        tuple(head+Vector((sx*r*.72,0,r*1.12))),
                        tuple(head+Vector((sx*r*.57,0,r*1.47))),
                        tuple(head+Vector((sx*r*.95,0,r*1.65)))],r*.105,pal.gold,sides=6)
            batch.path([tuple(head+Vector((sx*r*.48,-r*.45,-r*.15))),
                        tuple(head+Vector((sx*r*1.10,-r*.55,-r*.40))),
                        tuple(head+Vector((sx*r*1.65,-r*.45,r*.08)))],r*.055,pal.gold,sides=6)
        for i in range(11):
            a=i/10*math.pi
            batch.path([tuple(head+Vector((math.cos(a)*r*.7,0,math.sin(a)*r*.8))),
                        tuple(head+Vector((math.cos(a)*r*1.12,.006,math.sin(a)*r*1.15))),
                        tuple(head+Vector((math.cos(a+.20)*r*1.19,.005,math.sin(a+.20)*r*1.23)))],
                       r*.052,pal.giltpaint,sides=5)
    else:
        batch.ellipsoid(tuple(head),(r,r*.83,.055+r*.24),pal.gold,sides=14,rings=8)
        for sx in (-1,1):
            batch.path([tuple(head+Vector((sx*r*.4,r*.5,0))),
                        tuple(head+Vector((sx*r*.8,r*1.3,-.03))),
                        tuple(head+Vector((sx*r*1.2,r*1.55,-.03)))],r*.11,pal.gold,sides=6)
            batch.ellipsoid(tuple(head+Vector((sx*r*.5,0,-.07))),
                            (r*.15,r*.15,.025),pal.door,sides=8,rings=4)
    for t, side_sign in ((.27,-1),(.43,1),(.65,-1),(.81,1)):
        index=int(t*(count-1));p=line[index]
        direction=Vector((side_sign*unit*.09,0,-height*.075)) if facing=='front' else Vector((side_sign*unit*.09,-height*.075,0))
        elbow=p+direction
        tip=elbow+direction*.72
        batch.path([tuple(p),tuple(elbow),tuple(tip)],unit*.014,pal.gold,sides=7)
        for k in (-1,0,1):
            spread=Vector((k*unit*.023,-unit*.008,-height*.055)) if facing=='front' else Vector((k*unit*.023,-height*.055,-unit*.008))
            batch.path([tuple(tip),tuple(tip+spread),tuple(tip+spread*1.17+Vector((0,0,unit*.015)))],
                       unit*.005,pal.giltpaint,sides=5)
