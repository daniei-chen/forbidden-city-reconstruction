"""Add a publicly sourced ceremonial hall interior and human-eye cameras.

This creates a new derivative file and preserves the original verified master.
The throne, screen, dragons and carvings are clearly tagged interpretations,
not claimed conservation drawings or scan data.
"""
from pathlib import Path
import json
import math
import sys
import time

import bpy
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mesh_tools import Batch, collection
from palace_architecture import hall

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'The_Forbidden_City_1to1.blend'
OUTPUT = ROOT / 'The_Forbidden_City_Museum_Study.blend'
T0 = time.time()


def log(text):
    print('[IMMERSIVE %.1fs] %s' % (time.time() - T0, text), flush=True)


def use_existing_palette():
    from types import SimpleNamespace
    p = SimpleNamespace()
    names = {
        'red': '01 · 深红漆木 / vermilion timber',
        'paint': '02 · 宫墙朱砂 / aged cinnabar plaster',
        'door': '03 · 格扇暗红 / recessed red lacquer',
        'black': '04 · 檐下暗部 / deep unlit interior',
        'inset': '05 · 格心底 / dark lattice backing',
        'blue': '06 · 石青 / mineral blue paint',
        'cobalt': '07 · 匾额蓝漆 / cobalt enamel',
        'teal': '08 · 石绿 / turquoise painted wood',
        'gold': '09 · 鎏金 / warm aged gilding',
        'giltpaint': '10 · 金线彩画 / gold painted detail',
        'roof': '11 · 黄琉璃 / ochre glazed tiling',
        'green': '12 · 绿琉璃 / jade green tiling',
        'grey': '13 · 灰瓦 / smoked grey roof',
        'tiles': [f'14 · 琉璃筒瓦 / fired glaze {i}' for i in range(1, 6)],
        'darktile': '15 · 板瓦 / warm occluded pan tile',
        'green_clay': '绿釉构件 / smooth green glaze',
        'grey_clay': '灰瓦构件 / weathered dark ceramic',
        'marble': '18 · 汉白玉 / warm aged marble',
        'marble_dark': '19 · 三台石砌 / weathered terrace masonry',
        'terrace_floor': '台面 · 风化石板 / weathered terrace flagstones',
        'court': '20 · 青灰地砖 / grey-green court pavers',
        'path': '21 · 石板御路 / pale large slabs',
        'bronze': '26 · 铜器 / patinated ritual bronze',
        'stream': '28 · 金水河 / inner river',
        'trunk': '24 · 树干 / aged bark',
        'leaves': [f'25 · 苑树枝叶 / foliage {i}' for i in range(1, 5)],
    }
    for attribute, name in names.items():
        if attribute in ('tiles', 'leaves'):
            setattr(p, attribute, [bpy.data.materials.get(n) for n in name])
            if any(m is None for m in getattr(p, attribute)):
                raise RuntimeError('A master material is missing: ' + attribute)
        else:
            material = bpy.data.materials.get(name)
            if material is None and attribute in ('green', 'green_clay'):
                material = bpy.data.materials.get('11 · 黄琉璃 / ochre glazed tiling')
                if attribute == 'green_clay':
                    material = bpy.data.materials.get('灰瓦构件 / weathered dark ceramic')
            if material is None:
                raise RuntimeError('A master material is missing: ' + name)
            setattr(p, attribute, material)
    # Some construction-stage materials were not referenced by any master mesh
    # and therefore were intentionally not serialized in the original .blend.
    p.bed = bpy.data.materials.get('11a · 筒瓦下灰背 / ceramic roof bed') or p.door
    p.green_clay = bpy.data.materials.get('绿釉构件 / smooth green glaze') or p.grey_clay
    p.goldbrick = bpy.data.materials.get('太和殿金砖 · 精磨深灰陶质')
    if p.goldbrick is None:
        p.goldbrick = bpy.data.materials.new('太和殿金砖 · 精磨深灰陶质')
        p.goldbrick.use_nodes = True
        p.goldbrick.diffuse_color = (.115, .102, .082, 1)
        bsdf = p.goldbrick.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value = (.13, .119, .097, 1)
        bsdf.inputs['Roughness'].default_value = .27
        bsdf.inputs['Coat Weight'].default_value = .16
        bsdf.inputs['Coat Roughness'].default_value = .24
        noise = p.goldbrick.node_tree.nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 7.0
        noise.inputs['Detail'].default_value = 2.4
        coords = p.goldbrick.node_tree.nodes.new('ShaderNodeTexCoord')
        bump = p.goldbrick.node_tree.nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = .12
        bump.inputs['Distance'].default_value = .009
        p.goldbrick.node_tree.links.new(coords.outputs['Object'], noise.inputs['Vector'])
        p.goldbrick.node_tree.links.new(noise.outputs['Fac'], bump.inputs['Height'])
        p.goldbrick.node_tree.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return p


def camera(name, position, target, focal_length=38):
    data = bpy.data.cameras.new(name)
    data.lens = focal_length
    data.sensor_width = 36
    data.clip_start = .06
    data.clip_end = 1000
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()
    return obj


def add_terrace_details(pal):
    """Small furnishing items placed to documented ground/terrace metre levels."""
    detail = collection('太和殿御座空间 · 礼制陈设与沉浸观察点')
    b = Batch()
    # Rebuild absent north/south sections of the old generic black mass as warm
    # timber-panelled walls behind the structural edge columns.
    b.finish('阶段性陈设占位', detail)


def main():
    if not SOURCE.is_file():
        raise RuntimeError('The previously verified master Blender file is missing.')
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    scene = bpy.context.scene
    if scene.unit_settings.scale_length != 1.0:
        raise RuntimeError('Expected a metric 1 Blender unit = 1 metre master.')
    old = bpy.data.collections.get('太和殿')
    if old is None:
        raise RuntimeError('Could not locate the original editable Taihe hall collection.')
    for obj in list(old.all_objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(old)

    pal = use_existing_palette()
    gold_surface=pal.gold.node_tree.nodes.get('Principled BSDF')
    gold_surface.inputs['Roughness'].default_value=.54
    for node in pal.gold.node_tree.nodes:
        if node.type=='BUMP':
            node.inputs['Distance'].default_value=.0015
    # The OSM timber-part rectangle is 62.44 × 35.47 m. The three eaves and
    # public total height come from the official Palace Museum description.
    # 67.4 × 40.0 m remains the roof span of the separately editable tile shell.
    assembly = bpy.data.collections.get('紫禁城 · EDITABLE 3D MASTER')
    if assembly is None:
        raise RuntimeError('The master collection is missing.')
    hero = hall(
        '太和殿', assembly, pal, origin=(-1.70, -90.87, 0), yaw=-0.008,
        width=63.96, depth=37.17, floor=8.13,
        eave=16.80, upper_eave=22.50, rise=9.18,
        bays=11, deep_bays=5, kind='hip', tiles=True, beasts=10, plaque='太和殿',
        roof_width=67.4, roof_depth=40.0, post_radius=.53,
        interior_posts=True, terminal_height=3.40,
        lower_stop=.54, open_central_portal=True, ceremonial_interior=True)
    hero['official_plan_m'] = '63.96 x 37.17; Palace Museum cited architectural publication'
    hero['mapped_timber_part_envelope_m'] = 'approximately 62.44 x 35.47; OpenStreetMap way 638449346'
    hero['museum_height_m'] = 35.05
    hero['height_interpretation'] = 'Official total including terrace 35.05 m; faceted ornaments may vary by centimetres'
    hero['known_bays'] = '11 front × 5 depth; 72 posts; nonuniform centres from Palace Museum Journal 2007/4 tables 2 and 3'
    hero['source_accuracy'] = 'OSM placement; published mean post-grid measurements; museum exterior/interior photographs; sculpture is interpretive'
    hero['throne_reference_dimensions_m'] = json.dumps({
        'overall_height': 1.725,
        'seat_height': 0.49,
        'maximum_width': 1.585,
        'footstool_height': 0.30,
        'chair_detail_count': 13,
        'chair_source': 'Palace Museum: 太和殿宝座档案, p.012; https://www.dpm.org.cn/Uploads/pdf/5063/T00012_00.pdf',
        'note': 'Published chair/footstool dimensions; screen, dais, carving and furnishing placement are inferred from photographs.'
    }, ensure_ascii=False)

    origin = Vector((-1.70, -90.87, 0.))
    yaw = -.008
    for name, local_position, local_target, power, size in (
        ('太和殿室内天光 · soft skylight', (0., 0., 29.5), (0., 0., 9.), 24000., 20.),
        ('太和殿御座面光 · bounced daylight', (0., -18.8, 17.5), (0., -2.0, 15.0), 8500., 10.),
        ('太和殿内殿漫射反光 · bounced diffuse fill', (0., 7.5, 20.5), (0., -3.0, 14.0), 4200., 7.),
    ):
        data = bpy.data.lights.new(name, 'AREA')
        data.energy = power
        data.shape = 'DISK'
        data.size = size
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        local = Vector(local_position)
        target = Vector(local_target)
        c, s = math.cos(yaw), math.sin(yaw)
        light.location = origin + Vector((local.x*c-local.y*s, local.x*s+local.y*c, local.z))
        aim = Vector((target.x*c-target.y*s, target.x*s+target.y*c, target.z)) + origin
        light.rotation_euler = (aim-light.location).to_track_quat('-Z', 'Y').to_euler()

    # Dedicated chest-height human-view compositions, eye height 1.65 m above
    # the southern platform top. The first is the interior visitor route.
    camera('09 · 丹陛尽头步入太和殿 / human eye, 1.65m',
           (-1.7, -131.0, 9.80), (-1.7, -105.3, 14.5), 42)
    camera('10 · 太和殿御座正视 / interior ceremonial view',
           (-1.7, -105.0, 10.032), (-1.7, -87.0, 16.1), 24)
    camera('11 · 太和殿近身檐下 / human scale eaves',
           (-5.0, -112.4, 9.80), (-1.7, -98.0, 20.6), 35)
    camera('13 · 太和殿藻井仰视 / recessed caisson and Xuanyuan mirror',
           (.3, -85.47, 11.05), (-1.7, -85.27, 22.5), 26)
    camera('14 · 太和殿御座雕刻 / modeled throne relief',
           (-1.7, -86.9, 11.3), (-1.7, -81.0, 12.0), 34)
    scene['refinement_20261120'] = json.dumps({
        'scope': 'reconstructed Taihe exterior dimensions, genuine open portal, double leaves, interpretive throne/screen, human-eye cameras',
        'master_preserved': str(SOURCE.name),
        'metric_units': 1,
        'verified_reference': 'Palace Museum public Taihe description, architectural source photographs; OSM mapped timber footprint',
        'measured_vs_interpreted': 'Mapped exterior envelope / published 11×5 bays and 35.05 m gross height; interior furnishing and carving interpretive',
    }, ensure_ascii=False)
    from prepare_walkthrough import tune_finish_and_sun
    tune_finish_and_sun()
    scene.camera = bpy.data.objects.get('10 · 太和殿御座正视 / interior ceremonial view')
    scene.render.resolution_percentage = 100
    scene.render.resolution_x, scene.render.resolution_y = 1800, 1350
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.view_settings.exposure = -0.16
    bpy.context.preferences.filepaths.save_version = 2
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT), compress=True)
    log('Saved separate refined native scene: ' + str(OUTPUT))

    visible_meshes = [o for o in scene.objects if o.type == 'MESH' and not o.hide_render]
    report = {
        'master_preserved': SOURCE.name,
        'refined_file': OUTPUT.name,
        'visible_mesh_objects': len(visible_meshes),
        'taihe_objects': len([o for o in hero.all_objects if o.type == 'MESH']),
        'taihe_columns': next(o.get('column_count') for o in hero.all_objects
                              if o.type == 'MESH' and o.get('column_count')),
        'people_eye_cameras': [o.name for o in scene.objects if o.type == 'CAMERA' and o.name.startswith(('09 ', '10 ', '11 '))],
        'portal_walkable': next(o.get('walkable') for o in hero.all_objects
                                if o.type == 'MESH' and o.get('walkable')),
        'refinement_scope': scene['refinement_20261120'],
        'time_seconds': round(time.time() - T0, 1),
    }
    (ROOT / 'museum_study_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    log('REFINEMENT_REPORT ' + json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
