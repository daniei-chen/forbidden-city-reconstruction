"""Native ceramic cap/pan tile geometry instanced on every eligible mapped roof.

The contributed roof surface is retained; tile modules and placement are
reconstruction parameters, not a field survey of each historic tile. Points,
orientations and provenance remain editable in Blender. Nothing is rendered
as a photograph of a roof. Instancing shares genuine 3D tile mesh data.
"""
from pathlib import Path
from collections import Counter
import json
import math
import sys
import time
import numpy as np
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from shapely import contains_xy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from osm_site import Site,tags,number,rectangle
from mesh_tools import Batch,collection
from refine_immersive import use_existing_palette

ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'The_Forbidden_City_Conservation_Detail.blend'
OUTPUT=ROOT/'The_Forbidden_City_Detailed_City.blend'
PITCH=.34
LENGTH=.38


def ceramic_module(p,group,color):
    b=Batch()
    cap=p.grey_clay if color=='grey' else p.green_clay if color=='green' else p.tiles[2]
    pan=cap if color!='yellow' else p.darktile
    # Convex cap and concave pan, both have physical thickness and overlapping
    # lips. The carrier's Y axis runs upslope; its Z axis is the roof normal.
    for is_cap in (True,False):
        sides=9 if is_cap else 7
        verts=[]
        for bottom in (False,True):
            for row,yy in enumerate((-.198,-.164,.196)):
                for j in range(sides):
                    f=j/(sides-1)
                    if is_cap:
                        a=math.pi*f
                        x=math.cos(a)*.098
                        z=.014+math.sin(a)*.092
                    else:
                        u=2*f-1
                        x=PITCH/2+u*.15
                        z=.006+.044*u*u
                    z+=.009 if row==0 else 0
                    z-=.012 if bottom else 0
                    verts.append((x,yy,z))
        faces=[];count=3*sides
        for row in range(2):
            for j in range(sides-1):
                k=row*sides+j
                faces.append((k,k+1,k+sides+1,k+sides))
                faces.append((k+count+sides,k+count+sides+1,k+count+1,k+count))
        for row in (0,2):
            for j in range(sides-1):
                k=row*sides+j
                faces.append((k,k+count,k+count+1,k+1))
        for j in (0,sides-1):
            for row in range(2):
                k=row*sides+j
                faces.append((k,k+sides,k+sides+count,k+count))
        b.add(verts,faces,cap if is_cap else pan,smooth=True)
    obj=b.finish('共享三维瓦件 · 筒瓦与板瓦 · '+color,group,
                 properties={'nominal_module_m':[PITCH,LENGTH],
                             'geometry':'Real convex cap and concave pan with ceramic thickness',
                             'accuracy':'Nominal reconstruction module; not an individually surveyed tile'})
    obj.hide_render=True;obj.hide_set(True)
    return obj


def instance_nodes(archetype,color):
    name='全城实瓦 · 实例化 '+color
    tree=bpy.data.node_groups.new(name,'GeometryNodeTree')
    tree.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
    tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    nodes=tree.nodes;links=tree.links
    input=nodes.new('NodeGroupInput');input.location=(-470,130)
    output=nodes.new('NodeGroupOutput');output.location=(340,130)
    mesh=nodes.new('GeometryNodeObjectInfo');mesh.inputs['Object'].default_value=archetype
    mesh.inputs['As Instance'].default_value=False;mesh.transform_space='ORIGINAL';mesh.location=(-470,-70)
    instance=nodes.new('GeometryNodeInstanceOnPoints');instance.location=(70,130)
    rotation=nodes.new('GeometryNodeInputNamedAttribute');rotation.data_type='FLOAT_VECTOR'
    rotation.inputs['Name'].default_value='tile_rotation';rotation.location=(-230,-260)
    scale=nodes.new('GeometryNodeInputNamedAttribute');scale.data_type='FLOAT_VECTOR'
    scale.inputs['Name'].default_value='tile_scale';scale.location=(-230,-420)
    links.new(input.outputs['Geometry'],instance.inputs['Points'])
    links.new(mesh.outputs['Geometry'],instance.inputs['Instance'])
    links.new(rotation.outputs['Attribute'],instance.inputs['Rotation'])
    links.new(scale.outputs['Attribute'],instance.inputs['Scale'])
    links.new(instance.outputs['Instances'],output.inputs['Geometry'])
    return tree


def roof_candidates(site):
    group=bpy.data.collections['02 · 宫院群 / individual source footprints and roof parts']
    for obj in list(group.objects):
        ref=str(obj.get('osm_id',''))
        raw=site.ways.get(ref)
        kind='way'
        if raw is None:
            raw=site.rels.get(ref);kind='relation'
        if raw is None:
            continue
        t=tags(raw)
        if t.get('building:material')=='stone' or t.get('roof:material')=='stone' or t.get('building')=='wall':
            continue
        if 'building:part' in t and not t.get('roof:shape'):
            continue
        if t.get('roof:shape')=='flat':
            continue
        geometry=site.geom(ref,kind)
        if geometry.geom_type not in ('Polygon','MultiPolygon'):
            continue
        yield obj,ref,t,geometry


def add_carrier(name,group,tree,positions,rotations,scales,ref,color):
    data=bpy.data.meshes.new(name+' · 可编辑瓦位')
    data.vertices.add(len(positions))
    data.vertices.foreach_set('co',np.asarray(positions,dtype=np.float32).reshape(-1))
    for attr,vals in (('tile_rotation',rotations),('tile_scale',scales)):
        values=data.attributes.new(attr,'FLOAT_VECTOR','POINT')
        values.data.foreach_set('vector',np.asarray(vals,dtype=np.float32).reshape(-1))
    data.update()
    obj=bpy.data.objects.new(name,data);group.objects.link(obj)
    modifier=obj.modifiers.new('真正三维筒瓦板瓦 · 可编辑瓦位与朝向','NODES');modifier.node_group=tree
    obj['tile_carrier']=True;obj['tile_module_count']=len(positions)
    obj['physical_ceramic_tile_count']=len(positions)*2
    obj['source_osm_id']=ref;obj['nominal_pitch_m']=PITCH;obj['roof_color']=color
    obj['placement_method']='Raycast onto the actual saved mapped-roof mesh, using its real surface normals'
    obj['accuracy']='Contributed roof envelope; tile spacing, overlaps, irregular wear and exact individual tile lengths are inferred'
    return obj


def main():
    start=time.time();bpy.ops.wm.open_mainfile(filepath=str(INPUT))
    site=Site();p=use_existing_palette()
    root=bpy.data.collections['紫禁城 · EDITABLE 3D MASTER']
    detail=collection('全城逐片瓦作 · 真实三维实例',root)
    assets=collection('瓦件原型 · 共享几何与米制尺寸',root)
    nodegroups={color:instance_nodes(ceramic_module(p,assets,color),color) for color in ('yellow','grey','green')}
    counts=Counter();rows=[];candidates=list(roof_candidates(site))
    depsgraph=bpy.context.evaluated_depsgraph_get()
    for index,(obj,ref,t,g) in enumerate(candidates):
        x,y,w,d,yaw=rectangle(g)
        if min(w,d)<.5:
            continue
        c,s=math.cos(yaw),math.sin(yaw)
        grey=any(q in t.get('roof:colour','').lower() for q in ('gray','grey','#8080'))
        color='grey' if grey else 'green' if 'green' in t.get('roof:colour','').lower() else 'yellow'
        nx=max(1,round(w/PITCH));ny=max(1,round(d/.34))
        xx,yy=np.meshgrid((np.arange(nx)+.5)*w/nx-w/2,(np.arange(ny)+.5)*d/ny-d/2)
        xx=xx.reshape(-1);yy=yy.reshape(-1)
        wx=x+xx*c-yy*s;wy=y+xx*s+yy*c
        # Keep the cap and pan assembly inside the actual, possibly concave
        # contributed polygon instead of filling its enclosing rectangle.
        mask=contains_xy(g,wx,wy)
        for dx,dy in ((-.13,-.15),(.29,-.15),(-.13,.15),(.29,.15)):
            mask &= contains_xy(g,wx+dx*c-dy*s,wy+dx*s+dy*c)
        indices=np.flatnonzero(mask)
        if not len(indices):
            continue
        positions=[];rotations=[];scales=[]
        # Build a BVH of the saved object, not a mathematically smoother roof
        # that might leave tiles floating above the actual triangulation.
        tree=BVHTree.FromObject(obj,depsgraph,epsilon=.00001)
        high=max(v.co.z for v in obj.data.vertices)+1
        for i in indices:
            hit,normal,face,distance=tree.ray_cast(Vector((float(wx[i]),float(wy[i]),high)),Vector((0,0,-1)),100)
            if hit is None or abs(normal.z)<.16:
                continue
            # Only the upward ceramic roof faces, excluding vertical sides and
            # timber triangles that share the same source building mesh.
            material=obj.data.materials[obj.data.polygons[face].material_index]
            if not any(token in material.name for token in ('黄琉璃','灰瓦','绿琉璃')):
                continue
            if normal.z<0:
                normal=-normal
            horizontal=Vector((normal.x,normal.y,0))
            if horizontal.length<.0001:
                horizontal=Vector((s,-c,0))
            # Upslope is opposite the horizontal component of the roof normal.
            upslope=-horizontal
            upslope.z=horizontal.length_squared/max(normal.z,.01)
            upslope.normalize()
            # Z track fixes the module normal; local Y is aligned along slope.
            rotation=normal.to_track_quat('Z','Y').to_euler()
            # to_track_quat chooses the closest Y, then rotate around normal
            # until that axis follows the physically correct slope direction.
            q=normal.to_track_quat('Z','Y')
            local_y=q@Vector((0,1,0))
            angle=math.atan2(normal.dot(local_y.cross(upslope)),local_y.dot(upslope))
            from mathutils import Quaternion
            q=Quaternion(normal,angle)@q
            # Strongly tilted roofs need longer tiles in projection to keep
            # continuous overlapping courses at the same physical pitch.
            length_scale=max(.90,min(2.3,(d/ny)/(.38*normal.z)))
            positions.append(tuple(hit+normal*.023))
            rotations.append(tuple(q.to_euler()))
            scales.append((w/nx/PITCH,length_scale,1.))
        if not positions:
            continue
        name=(t.get('name') or '宫院屋面')+' · 三维瓦作 '+ref
        add_carrier(name,detail,nodegroups[color],positions,rotations,scales,ref,color)
        counts[color]+=len(positions)
        rows.append({'osm_id':ref,'name':t.get('name',''),'modules':len(positions),
                     'physical_tiles':len(positions)*2,'color':color})
        if index%75==0:
            print('ROOF_TILING_PROGRESS',index,'of',len(candidates),'modules',sum(counts.values()),'seconds',round(time.time()-start,1),flush=True)
    report={'input':INPUT.name,'output':OUTPUT.name,'source_roof_objects':len(candidates),
            'roofs_with_real_tile_instances':len(rows),'cap_and_pan_modules':sum(counts.values()),
            'ceramic_tile_instances':2*sum(counts.values()),'color_module_counts':dict(counts),
            'module_metres':[PITCH,LENGTH],
            'method':'Native mesh point attributes + Geometry Nodes instances of thick three-dimensional cap and pan tiles; raycast to actual roof surfaces',
            'accuracy':'Nominal reconstruction modules on contributed OSM roof geometry; no claim of survey measurements for individual tiles',
            'exchange_note':'Full-city tile instances are in the native Blender master; optimized GLB may omit this procedural instance layer',
            'elapsed_seconds':round(time.time()-start,2),'roofs':rows}
    scene=bpy.context.scene
    scene['citywide_roof_tile_instances']=report['ceramic_tile_instances']
    scene['citywide_roof_tiling_accuracy']=report['accuracy']
    bpy.ops.file.pack_all();bpy.context.preferences.filepaths.save_version=1
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT),compress=True)
    (ROOT/'city_roof_tiles_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print('CITY_ROOF_TILES',len(rows),'roofs',sum(counts.values())*2,'tiles',round(time.time()-start,1),'seconds',flush=True)


if __name__=='__main__':
    main()
