"""Registered color on an open, stepped native caisson, bracket blocks and pearl."""
import math
from pathlib import Path

import bpy
import numpy as np

from ning_shou_halls import image_surface


REFS=Path(__file__).resolve().parent/'references/ning_shou_court'
SOURCE='https://www.sigoo.com/inside-the-hall-of-imperial-supremacy/'


def map_architectural_color(batch,cy,outer):
    """Surface mapping retains the modeled undercuts and different elevations."""
    material=image_surface('huangji_caisson_atlas',rough=.56,metal=.34)
    batch.mats=[material]; batch.slots={material:0}; batch.mi=[0]*len(batch.f)
    batch.uv=[tuple(((batch.v[index][0]/outer+.5),
                     (batch.v[index][1]-cy)/outer+.5) for index in face) for face in batch.f]


def field_mesh(batch,cx,cy,z,width,relief,material,*,circular=False,hole_radius=None,pitch=.008,amplitude=.018):
    nx=math.ceil(width/pitch)
    u,v=np.meshgrid(np.linspace(0,1,nx+1),np.linspace(0,1,nx+1))
    x,y=(u-.5)*width,(v-.5)*width
    image_x=np.rint(u*(relief.shape[1]-1)).astype(np.int32)
    image_y=np.rint((1-v)*(relief.shape[0]-1)).astype(np.int32)
    heights=z-amplitude*relief[image_y,image_x]
    if circular:
        active=x*x+y*y<(width/2-.002)**2
    elif hole_radius is not None:
        ax,ay=np.abs(x),np.abs(y)
        across=hole_radius*math.cos(math.pi/8)
        active=np.maximum.reduce((ax,ay,(ax+ay)/math.sqrt(2)))>across+.005
    else:
        active=np.ones(u.shape,bool)
    cells=active[:-1,:-1]&active[1:,:-1]&active[:-1,1:]&active[1:,1:]
    vertices=np.stack((x+cx,y+cy,heights),axis=-1).reshape(-1,3)
    coordinates=np.stack((u,v),axis=-1).reshape(-1,2)
    faces=[]
    for row,column in zip(*np.nonzero(cells)):
        a=int(row*(nx+1)+column)
        faces.append((a,a+nx+1,a+nx+2,a+1))
    used=np.unique(np.array(faces,np.int32))
    remap=np.full(len(vertices),-1,np.int32);remap[used]=np.arange(len(used))
    batch.add(vertices[used],[tuple(int(remap[v]) for v in face) for face in faces],material,
              uv=coordinates[used],smooth=True)


def add_caisson_details(batch,cy,soffit,outer,p):
    """Block rhythm and sampled carving without closing the actual aperture."""
    with np.load(REFS/'huangji_caisson_relief.npz',allow_pickle=False) as data:
        disk_relief,atlas_relief=data['disk_relief'],data['atlas_relief']
    for tier in range(5):
        radius=2.21-tier*.199
        z=soffit+.155*tier+.025
        corners=[(radius*math.cos(math.pi/8+i*math.tau/8),
                  cy+radius*math.sin(math.pi/8+i*math.tau/8)) for i in range(9)]
        for a,c in zip(corners,corners[1:]):
            length=math.dist(a,c); count=max(3,round(length/.127))
            dx,dy=(c[0]-a[0])/length,(c[1]-a[1])/length
            angle=math.atan2(dy,dx)
            for j in range(count):
                t=(j+.5)/count; x,y=a[0]+t*(c[0]-a[0]),a[1]+t*(c[1]-a[1])
                batch.box((x,y,z),(.078,.115,.048),p.old_gold,yaw=angle)
                batch.box((x-dy*.036,y+dx*.036,z-.026),(.105,.041,.029),p.gold,yaw=angle)
                batch.box((x+dy*.052,y-dx*.052,z+.032),(.047,.159,.042),p.old_gold,yaw=angle)
    map_architectural_color(batch,cy,outer)
    field_mesh(batch,0,cy,soffit-.092,outer,atlas_relief,
               image_surface('huangji_caisson_atlas',rough=.56,metal=.34),hole_radius=2.21,
               amplitude=.017)
    # The ceiling disk is a concave top closure above all five rings. It is
    # sampled independently so the original plane is never substituted for
    # the geometric well. Small surface depths remain authored estimates.
    field_mesh(batch,0,cy,soffit+.766,2.35,disk_relief,
               image_surface('huangji_caisson_dragon_disk',rough=.54,metal=.36),circular=True,
               pitch=.0065,amplitude=.066)


def hanging_pearl(batch,cy,soffit,p):
    surface=bpy.data.materials.new('皇极殿藻井 · 旧镜珠与暗银反光')
    surface.use_nodes=True
    bsdf=surface.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=(.25,.26,.25,1.)
    bsdf.inputs['Metallic'].default_value=.88
    bsdf.inputs['Roughness'].default_value=.21
    bsdf.inputs['Coat Weight'].default_value=.16
    top=soffit+.766
    batch.rod((0,cy,top-.041),(0,cy,top-.393),.016,p.old_gold,sides=20)
    batch.ellipsoid((0,cy,top-.514),(.137,.137,.137),surface,sides=64,rings=38)
    batch.lathe(0,cy,((.060,top-.376),(.073,top-.393),(.047,top-.410)),p.old_gold,sides=40)
    for index in range(8):
        angle=index*math.tau/8
        x,y=.179*math.cos(angle),cy+.179*math.sin(angle)
        batch.rod((x,y,top-.132),(x,y,top-.792),.008,p.fascia,sides=12)
        for j in range(11):
            z=top-.151-j*.056
            batch.lathe(x,y,((.010,z-.018),(.015,z-.014),(.014,z+.014),(.009,z+.018)),p.old_gold,sides=12)
    for radius,z in ((.173,top-.184),(.181,top-.707)):
        batch.path([(radius*math.cos(a),cy+radius*math.sin(a),z)
                    for a in (i*math.tau/64 for i in range(65))],.009,p.fascia,sides=10)
