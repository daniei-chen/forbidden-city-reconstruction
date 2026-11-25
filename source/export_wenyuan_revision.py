"""Export the current whole city and a separately reusable Wenyuan component.

The .blend is the visual master. Exchange copies keep architectural mesh and
Wenyuan's real tiles, while the generic city tile instances remain native-only.
"""
from pathlib import Path
import json
import sys
import time
import bpy

ROOT=Path(__file__).resolve().parents[1]


def export_selected(path,objects):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    if objects:
        bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,
                              export_animations=False,export_cameras=False,export_lights=False,
                              export_extras=True,export_materials='EXPORT',export_yup=True,
                              export_apply=False,export_image_format='AUTO')
    return {'file':path.name,'bytes':path.stat().st_size,'selected_mesh_objects':len(objects),
            'mesh_datablocks':len({o.data.as_pointer() for o in objects})}


def main():
    start=time.time()
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'The_Forbidden_City_Wenyuan_Architectural_Revision.blend'))
    group=bpy.data.collections['文渊阁 · 实测柱网与三层藏书楼']
    component=[o for o in group.all_objects if o.type=='MESH' and len(o.data.polygons)]
    report={'component':export_selected(ROOT/'exports/Wenyuan_Ge_Survey_Based_Reconstruction.glb',component)}
    all_meshes=[];native_tile_modules=0
    for obj in bpy.context.scene.objects:
        if obj.get('tile_carrier'):
            native_tile_modules+=int(obj.get('tile_module_count',0))
            continue
        if obj.type!='MESH' or not obj.data.polygons or obj.hide_render or not obj.visible_get():
            continue
        if obj.name.startswith('城外地表延伸'):
            continue
        if any(c.hide_render for c in obj.users_collection):
            continue
        all_meshes.append(obj)
    report['city']=export_selected(ROOT/'exports/Forbidden_City_Architectural_Revision.glb',all_meshes)
    report['native_only_instanced_tile_modules']=native_tile_modules
    report['native_file']='The_Forbidden_City_Wenyuan_Architectural_Revision.blend'
    report['exchange_limits']=[
        'Generic city Geometry Nodes tile carriers are omitted; underlying roof meshes remain.',
        'Individually modelled tiles on Wenyuan and major halls are retained.',
        'Image textures and base PBR parameters export; procedural shaders and light linking are Blender-specific.',
        'The exchange files do not claim identical shading to the Cycles renders.',
        'Unmeasured distant ground continuation excluded to preserve useful framing.'
    ]
    report['seconds']=round(time.time()-start,2)
    (ROOT/'export_architectural_revision_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
