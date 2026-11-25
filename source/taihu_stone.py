"""Solid limestone forms with drilled-through and blind erosion pockets."""
import math
import random

import bpy
import numpy as np


CORNER=np.array(((0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,1),(1,0,1),(1,1,1),(0,1,1)),dtype=np.int32)
TETRA=((0,1,2,6),(0,2,3,6),(0,3,7,6),(0,7,4,6),(0,4,5,6),(0,5,1,6))


def mesh_field(name,axes,field,stone,pocket=None,pockets=None):
    """March the consistently subdivided voxel grid and share its edge vertices."""
    slices=[field[dx:field.shape[0]-1+dx,dy:field.shape[1]-1+dy,dz:field.shape[2]-1+dz] for dx,dy,dz in CORNER]
    cells=np.argwhere((np.minimum.reduce(slices)<0)&(np.maximum.reduce(slices)>=0))
    verts=[];faces=[];shades=[];edges={}
    pitch=np.array([a[1]-a[0] for a in axes]);origin=np.array([a[0] for a in axes])
    grid_y,grid_z=field.shape[1:]
    flat=field.ravel()
    deep=pockets.ravel() if pockets is not None else None
    dark=[]
    for i,j,k in cells:
        nodes=[(int(i+dx),int(j+dy),int(k+dz)) for dx,dy,dz in CORNER]
        keys=[(a*grid_y+b)*grid_z+c for a,b,c in nodes]
        vv=[float(flat[n]) for n in keys]
        neg=[v<0 for v in vv]

        def edge(a,b):
            key=tuple(sorted((keys[a],keys[b])))
            if key in edges:
                return edges[key]
            t=vv[a]/(vv[a]-vv[b])
            verts.append(tuple(origin+pitch*np.subtract(nodes[a],0)+pitch*(np.subtract(nodes[b],nodes[a]))*t))
            dark.append(False if deep is None else max(deep[keys[a]],deep[keys[b]])>0)
            edges[key]=len(verts)-1
            return len(verts)-1

        def face(a,b,c,inside):
            va,vb,vc=(verts[ix] for ix in (a,b,c))
            u=(vb[0]-va[0],vb[1]-va[1],vb[2]-va[2]);v=(vc[0]-va[0],vc[1]-va[1],vc[2]-va[2])
            n=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
            toward=tuple(origin[m]+nodes[inside][m]*pitch[m]-va[m] for m in range(3))
            faces.append((a,c,b) if sum(n[m]*toward[m] for m in range(3))>0 else (a,b,c))
            shades.append(int(dark[a] and dark[b] and dark[c]))

        for tet in TETRA:
            ix=[t for t in tet if neg[t]]
            ox=[t for t in tet if not neg[t]]
            if len(ix)==1:
                face(*(edge(ix[0],a) for a in ox),ix[0])
            elif len(ox)==1:
                face(*(edge(ox[0],a) for a in ix),ix[0])
            elif len(ix)==2:
                a,b,c,d=(edge(ix[0],ox[0]),edge(ix[0],ox[1]),edge(ix[1],ox[1]),edge(ix[1],ox[0]))
                face(a,b,c,ix[0]);face(a,c,d,ix[0])
    if not faces:
        raise RuntimeError(f'No limestone surface was generated for {name}.')
    data=bpy.data.meshes.new(name)
    data.from_pydata(verts,[],faces)
    data.materials.append(stone)
    if pocket is not None:
        data.materials.append(pocket)
        data.polygons.foreach_set('material_index',shades)
    data.polygons.foreach_set('use_smooth',np.ones(len(faces),dtype=np.bool_))
    data.update()
    return data


def waves(x,y,z,phase=0.):
    return (.49*np.sin(6.1*x+3.2*y-4.8*z+phase)*np.cos(4.1*y+3.4*z)
            +.24*np.sin(11.8*x-7.4*y+8.6*z+phase*2.3)
            +.17*np.cos(18.7*x-14.3*y)*np.sin(17.1*z-8.4*x)
            +.10*np.sin(28.6*x+24.4*y+23.3*z))


def smin(a,b,k):
    t=np.clip(.5+.5*(b-a)/k,0.,1.)
    return (1-t)*b+t*a-k*t*(1-t)


def limestone(name,index,stone,pocket):
    rng=random.Random(27191+index*405)
    axis=np.linspace(-1.37,1.37,43)
    x,y,z=np.meshgrid(axis,axis,axis,indexing='ij',sparse=True)
    a=(.74+.21*rng.random(),.56+.26*rng.random(),.70+.19*rng.random())
    u=x+.14*np.sin(z*3.8+index*.7)+.088*np.cos(y*5.2-index)
    v=y+.09*np.sin(x*3.1+z*4.7)
    w=z+.073*np.sin(x*5.5+index*.3)
    d=(np.sqrt((u/a[0])**2+(v/a[1])**2+(w/a[2])**2)-1)*.64
    for j in range(4):
        cx=rng.uniform(-.60,.60);cy=rng.uniform(-.37,.37);cz=rng.uniform(-.71,.72)
        rx=rng.uniform(.29,.51);ry=rng.uniform(.30,.51);rz=rng.uniform(.26,.52)
        l=(np.sqrt(((u-cx)/rx)**2+((v-cy)/ry)**2+((w-cz)/rz)**2)-1)*min(rx,ry,rz)
        d=smin(d,l,.143)
    rough=waves(x,y,z,index*.78)
    d+=.19*rough+.047*np.sin(16*z+4*x+6*y)+.038*np.cos(8*x+11*z)*np.sin(7*z-4*y)
    pocket_field=np.full(d.shape,2.)
    for j in range(6):
        px=rng.uniform(-.67,.67);pz=rng.uniform(-.78,.79)
        px+=.10*np.sin(z*7.1+j);pz+=.09*np.cos(x*7.6+j*.3)
        cy=-.78 if j%3!=2 else .59
        rx=rng.uniform(.117,.269);rz=rng.uniform(.131,.321)
        ride=rng.uniform(.21,.47)
        if index%3!=2 and j==0:
            # One eroded throat continues through the limestone mass.
            cy=0.;ride=1.34;rx=.179+.065*rng.random();rz=.192+.047*rng.random()
        empty=(np.sqrt(((x-px)/rx)**2+((y-cy)/ride)**2+((z-pz)/rz)**2)-1)*min(rx,rz)
        pocket_field=np.minimum(pocket_field,empty+.065*rough)
    result=np.maximum(d,-pocket_field)
    mesh=mesh_field(name,(axis,axis,axis),result,stone,pocket,-pocket_field-.009)
    pos=np.empty(len(mesh.vertices)*3,dtype=np.float32)
    mesh.vertices.foreach_get('co',pos)
    xyz=pos.reshape(-1,3)
    lo,hi=np.min(xyz,axis=0),np.max(xyz,axis=0)
    xyz-=(lo+hi)*.5;xyz/=((hi-lo)*.5)
    mesh.vertices.foreach_set('co',xyz.ravel())
    mesh.update()
    return mesh
