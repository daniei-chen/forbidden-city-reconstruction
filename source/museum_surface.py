"""Photographic painted surface references used on real modeled components.

UV crops are selected directly from the unmodified archived source image.
These supplement the three-dimensional molding and relief; they are not
photogrammetry or a substitute for an accurately surveyed carving.
"""
from pathlib import Path
import bpy
import numpy as np

_PIXELS={}


def photo_material(name,filename,*,metal=.12,rough=.72):
    name='参考表面 · '+name
    material=bpy.data.materials.get(name)
    if material is not None:
        return material
    image_path=Path(__file__).resolve().parent/'textures'/filename
    material=bpy.data.materials.new(name);material.use_nodes=True
    material.diffuse_color=(.28,.19,.08,1)
    material['reference']=filename
    material['method']='Photographic pigment/relief surface on editable geometric component; source illumination remains in reference'
    surface=material.node_tree.nodes.get('Principled BSDF')
    surface.inputs['Metallic'].default_value=metal
    surface.inputs['Roughness'].default_value=rough
    if not image_path.is_file():
        material['method']='Plain pigment fallback. Optional photograph is absent.'
        surface.inputs['Base Color'].default_value=material.diffuse_color
        return material
    image=bpy.data.images.load(str(image_path),check_existing=True)
    tex=material.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image
    uv=material.node_tree.nodes.new('ShaderNodeUVMap');uv.uv_map='Roof UV'
    material.node_tree.links.new(uv.outputs['UV'],tex.inputs['Vector'])
    material.node_tree.links.new(tex.outputs['Color'],surface.inputs['Base Color'])
    bump=material.node_tree.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value=.17;bump.inputs['Distance'].default_value=.0025
    material.node_tree.links.new(tex.outputs['Color'],bump.inputs['Height'])
    material.node_tree.links.new(bump.outputs['Normal'],surface.inputs['Normal'])
    return material


def crop_uv(x0,y0,x1,y1):
    """Normalized image coordinates with y measured from the top of the photo."""
    return [(x0,1-y1),(x1,1-y1),(x1,1-y0),(x0,1-y0)]


def relief_panel(batch,center,w,h,material,uv,*,facing='front',nx=36,ny=120,depth=.026):
    """Make actual low-relief vertices from the referenced pigment luminance.

    This is an explicitly inferred relief, not photogrammetric depth recovery.
    It adds editable surface geometry to the photographed carving pattern.
    """
    image=next((n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image),None)
    if image is None:
        x,y,z=center
        if facing=='front':
            face=[(x-w/2,y,z-h/2),(x+w/2,y,z-h/2),(x+w/2,y,z+h/2),(x-w/2,y,z+h/2)]
        else:
            face=[(x-w/2,y-h/2,z),(x+w/2,y-h/2,z),(x+w/2,y+h/2,z),(x-w/2,y+h/2,z)]
        batch.face(face,material,uv=uv)
        return
    if image.name not in _PIXELS:
        raw=np.empty(len(image.pixels),dtype=np.float32)
        image.pixels.foreach_get(raw)
        _PIXELS[image.name]=raw.reshape(image.size[1],image.size[0],4)
    pixels=_PIXELS[image.name]
    u0,v0=uv[0];u1,v1=uv[2]
    x,y,z=center;verts=[];mapping=[]
    for j in range(ny+1):
        t=j/ny;v=v0+(v1-v0)*t
        for i in range(nx+1):
            s=i/nx;u=u0+(u1-u0)*s
            px=min(image.size[0]-1,max(0,round(u*(image.size[0]-1))))
            py=min(image.size[1]-1,max(0,round(v*(image.size[1]-1))))
            color=pixels[py,px,:3]
            lum=float(np.dot(color,(.2126,.7152,.0722)))
            relief=.001+depth*max(0,min(1,lum*1.8))
            if facing=='front':
                verts.append((x+(s-.5)*w,y-relief,z+(t-.5)*h))
            else:
                verts.append((x+(s-.5)*w,y+(t-.5)*h,z-relief))
            mapping.append((u,v))
    faces=[]
    for j in range(ny):
        for i in range(nx):
            a=j*(nx+1)+i
            faces.append((a,a+1,a+nx+2,a+nx+1) if facing=='front' else (a,a+nx+1,a+nx+2,a+1))
    batch.add(verts,faces,material,uv=mapping,smooth=True)
