"""Metric mesh primitives and batched, separately editable architectural meshes."""
from __future__ import annotations

import math
from collections import defaultdict

import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient


def collection(name, parent=None):
    item = bpy.data.collections.new(name)
    (parent if parent is not None else bpy.context.scene.collection).children.link(item)
    return item


def polygons(geom):
    if geom.geom_type == "Polygon":
        if not geom.is_empty and geom.area > 1e-6:
            yield orient(geom, 1.0)
    elif hasattr(geom, "geoms"):
        for sub in geom.geoms:
            yield from polygons(sub)


def signed_area(coords):
    return sum(a[0]*b[1] - b[0]*a[1] for a,b in zip(coords, coords[1:]+coords[:1])) * 0.5


class Batch:
    def __init__(self, origin=(0,0,0), yaw=0.0):
        self.v, self.f, self.mi, self.ids, self.sm, self.uv = [], [], [], [], [], []
        self.mats = []
        self.slots = {}
        self.origin = Vector(origin)
        self.yaw = yaw

    def add(self, verts, faces, material, *, way=0, smooth=False, uv=None):
        off = len(self.v)
        verts = list(verts)
        if material not in self.slots:
            self.slots[material] = len(self.mats)
            self.mats.append(material)
        slot = self.slots[material]
        self.v.extend(verts)
        for face in faces:
            self.f.append(tuple(off+i for i in face))
            self.mi.append(slot)
            self.ids.append(int(way))
            self.sm.append(smooth)
            self.uv.append(tuple(uv[i] for i in face) if uv is not None else None)

    def face(self, coords, material, *, way=0, uv=None, smooth=False):
        self.add(coords, [tuple(range(len(coords)))], material, way=way, uv=uv, smooth=smooth)

    def box(self, center, dims, mat, *, yaw=0., way=0):
        x,y,z = center
        a,b,c = (d*.5 for d in dims)
        ct, st = math.cos(yaw), math.sin(yaw)
        verts = [(x+u*ct-v*st, y+u*st+v*ct, z+w)
                 for w in (-c,c) for u,v in ((-a,-b),(a,-b),(a,b),(-a,b))]
        self.add(verts, ((3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)), mat, way=way)

    def beam(self, a, b, width, height, mat):
        """Rectangular chamfer-free beam, oriented along any 3-D segment."""
        start, end = Vector(a), Vector(b)
        direction = end-start
        if direction.length < .0001:
            return
        q = direction.to_track_quat("Z","Y")
        u = q @ Vector((width/2,0,0))
        v = q @ Vector((0,height/2,0))
        cs = [(-u-v),(u-v),(u+v),(-u+v)]
        self.add([tuple(p+c) for p in (start,end) for c in cs],
                 ((3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)), mat)

    def rod(self, a, b, r0, mat, *, r1=None, sides=10, smooth=True, caps=True):
        start, end = Vector(a), Vector(b)
        if (end-start).length < .0001:
            return
        q = (end-start).to_track_quat("Z","Y")
        U,V = q @ Vector((1,0,0)), q @ Vector((0,1,0))
        co = [math.cos(i*math.tau/sides)*U+math.sin(i*math.tau/sides)*V for i in range(sides)]
        verts = [tuple(p+r*d) for p,r in ((start,r0),(end,r0 if r1 is None else r1)) for d in co]
        fs = [(i,(i+1)%sides,(i+1)%sides+sides,i+sides) for i in range(sides)]
        if caps:
            fs.extend((tuple(reversed(range(sides))),tuple(range(sides,2*sides))))
        self.add(verts,fs,mat,smooth=smooth)

    def path(self, points, radius, mat, *, sides=7):
        pp = [Vector(p) for p in points]
        if len(pp)<2:
            return
        verts=[]
        for i,p in enumerate(pp):
            tangent = pp[min(i+1,len(pp)-1)]-pp[max(i-1,0)]
            if tangent.length < 1e-7:
                return
            q = tangent.to_track_quat("Z","Y")
            for k in range(sides):
                a=k*math.tau/sides
                verts.append(tuple(p+q @ Vector((radius*math.cos(a),radius*math.sin(a),0))))
        faces=[(i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j)
               for i in range(len(pp)-1) for j in range(sides)]
        self.add(verts,faces,mat,smooth=True)

    def ellipsoid(self, center, scale, mat, *, sides=10, rings=5, jitter=0., rng=None, yaw=0.):
        x,y,z = center; a,b,c = scale
        ct, st = math.cos(yaw),math.sin(yaw)
        verts=[(x,y,z-c)]
        for j in range(1,rings):
            t=j/rings*math.pi
            for i in range(sides):
                p=i/sides*math.tau
                n=1.0+(rng.uniform(-jitter,jitter) if rng is not None else 0)
                xx=a*n*math.sin(t)*math.cos(p); yy=b*n*math.sin(t)*math.sin(p)
                verts.append((x+ct*xx-st*yy,y+st*xx+ct*yy,z-c*n*math.cos(t)))
        verts.append((x,y,z+c))
        fs=[]
        for i in range(sides):
            s=(i+1)%sides
            fs += [(0,1+s,1+i)]
            for j in range(rings-2):
                k=1+j*sides
                fs.append((k+i,k+s,k+s+sides,k+i+sides))
            k=1+(rings-2)*sides
            fs.append((k+i,k+s,len(verts)-1))
        self.add(verts,fs,mat,smooth=True)

    def lathe(self, x, y, profile, mat, *, sides=24):
        vals=[(x+r*math.cos(i*math.tau/sides),y+r*math.sin(i*math.tau/sides),z)
              for r,z in profile for i in range(sides)]
        fs=[(j*sides+i,j*sides+(i+1)%sides,(j+1)*sides+(i+1)%sides,(j+1)*sides+i)
            for j in range(len(profile)-1) for i in range(sides)]
        fs.extend((tuple(reversed(range(sides))),tuple((len(profile)-1)*sides+i for i in range(sides))))
        self.add(vals,fs,mat,smooth=True)

    def solid_xy(self, shape, z0, z1, mat, *, top=None, way=0, bottom=True):
        for p in polygons(shape):
            rings=[list(p.exterior.coords)[:-1]]+[list(h.coords)[:-1] for h in p.interiors]
            top_mat=top or mat
            if len(rings)==1:
                points=rings[0]
                self.face([(x,y,z1) for x,y in points],top_mat,way=way)
                if bottom:
                    self.face([(x,y,z0) for x,y in reversed(points)],mat,way=way)
            else:
                for tri in constrained_delaunay_triangles(p).geoms:
                    pp=list(orient(tri,1.).exterior.coords)[:-1]
                    self.face([(x,y,z1) for x,y in pp],top_mat,way=way)
                    if bottom:
                        self.face([(x,y,z0) for x,y in reversed(pp)],mat,way=way)
            for coords in rings:
                self.add([(x,y,z) for z in (z0,z1) for x,y in coords],
                         [(i,(i+1)%len(coords),(i+1)%len(coords)+len(coords),i+len(coords))
                          for i in range(len(coords))], mat,way=way)

    def solid_welded(self, shape, z0, z1, mat):
        """Manifold prism for arch booleans. All cap and side faces share vertices."""
        for p in polygons(shape):
            rings=[list(p.exterior.coords)[:-1]]+[list(h.coords)[:-1] for h in p.interiors]
            flat=[(x,y) for ring in rings for x,y in ring]; n=len(flat)
            tris=tessellate_polygon([[Vector((x,y,0)) for x,y in ring] for ring in rings])
            faces=[]
            for ia,ib,ic in tris:
                if signed_area([flat[i] for i in (ia,ib,ic)])<0:
                    ib,ic=ic,ib
                faces.extend(((ic,ib,ia),(ia+n,ib+n,ic+n)))
            offset=0
            for rr in rings:
                for i in range(len(rr)):
                    a,b=offset+i,offset+((i+1)%len(rr))
                    faces.append((a,b,b+n,a+n))
                offset+=len(rr)
            self.add([(x,y,z) for z in (z0,z1) for x,y in flat],faces,mat)

    def finish(self, name, target, *, bevel=0., properties=None):
        if not self.f:
            return None
        data=bpy.data.meshes.new(name+" · 网格")
        data.from_pydata(self.v, [], self.f)
        data.update()
        for m in self.mats:
            data.materials.append(m)
        data.polygons.foreach_set("material_index",self.mi)
        if any(self.sm):
            data.polygons.foreach_set("use_smooth",self.sm)
        if any(self.ids):
            low=data.attributes.new("osm_id_low", "INT", "FACE")
            low.data.foreach_set("value",[i%1_000_000_000 for i in self.ids])
            if max(self.ids)>=1_000_000_000:
                high=data.attributes.new("osm_id_high", "INT", "FACE")
                high.data.foreach_set("value",[i//1_000_000_000 for i in self.ids])
        if any(x is not None for x in self.uv):
            values=[e for f,uv in zip(self.f,self.uv) for p in (uv if uv else [(0,0)]*len(f)) for e in p]
            layer=data.uv_layers.new(name="Roof UV")
            layer.data.foreach_set("uv",values)
        obj=bpy.data.objects.new(name,data)
        target.objects.link(obj)
        obj.location=self.origin
        obj.rotation_euler.z=self.yaw
        if bevel > 0:
            modifier=obj.modifiers.new("石材与漆木倒角", "BEVEL")
            modifier.width=bevel; modifier.segments=2
            modifier.limit_method="ANGLE"
        if properties:
            for k,v in properties.items():
                obj[k]=v
        return obj


def line_boxes(batch, points, bottom, top, width, material):
    for (x,y),(xx,yy) in zip(points,points[1:]):
        d=math.hypot(xx-x,yy-y)
        if d<.025:
            continue
        batch.box(((x+xx)/2,(y+yy)/2,(top+bottom)/2),(d+.02,width,top-bottom),
                  material,yaw=math.atan2(yy-y,xx-x))


def object_to_mesh(obj):
    """Freeze evaluated lettering/Boolean geometry without a selection-context dependency."""
    eval_graph=bpy.context.evaluated_depsgraph_get()
    eval_obj=obj.evaluated_get(eval_graph)
    new_mesh=bpy.data.meshes.new_from_object(eval_obj, preserve_all_data_layers=True, depsgraph=eval_graph)
    parents=list(obj.users_collection)
    name=obj.name
    matrix=obj.matrix_world.copy()
    bpy.data.objects.remove(obj,do_unlink=True)
    result=bpy.data.objects.new(name,new_mesh)
    for parent in parents:
        parent.objects.link(result)
    result.matrix_world=matrix
    return result
