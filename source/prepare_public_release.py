"""Package the existing metric Blender master without distributing source photographs."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mesh_tools import object_to_mesh
from outer_court_walkthrough import configure_cycles
from palace_materials import paint


REFERENCE_LAYER = '90 · 参考图层 / hidden georeferenced aerial'
REPOSITORY = 'https://github.com/daniei-chen/forbidden-city-reconstruction'
INSCRIPTIONS = {
    'baohe_plaque_face_reference.jpg': '保和殿',
    'cross_qianqiu_plaque.jpg': '千秋亭',
    'cross_wanchun_plaque.jpg': '萬春亭',
    'garden_plaque_chengrui.jpg': '澄瑞亭',
    'garden_plaque_fubi.jpg': '浮碧亭',
    'north_qinan_plaque.jpg': '欽安殿',
    'north_tianyi_plaque.jpg': '天一門',
    'north_yujing_plaque.jpg': '御景亭',
    'qianqing_plaque_face_reference.jpg': '乾清宮',
    'taihe_title_reference_crop.jpg': '太和殿',
    'wumen_plaque_face_reference.jpg': '午門',
    'zhonghe_plaque_face_reference.jpg': '中和殿',
}
PIGMENTS = {
    '澄瑞亭 · 故宫仰拍对位的八方井壁': ('澄瑞亭 · 石青井壁', (.026, .065, .140), (.083, .160, .247), .64, .13),
    '参考表面 · 藻井彩绘与浮雕肌理': ('太和殿 · 藻井旧金地', (.23, .105, .024), (.58, .334, .096), .56, .32),
    '参考表面 · 内檐梁枋彩画': ('太和殿 · 石青梁枋', (.025, .038, .082), (.074, .116, .162), .67, .12),
    '参考表面 · 天花盘龙彩画': ('太和殿 · 天花暗青地', (.027, .052, .091), (.085, .135, .188), .66, .18),
    '参考表面 · 金柱盘龙表面': ('太和殿 · 盘柱柔金', (.18, .085, .019), (.49, .271, .055), .53, .42),
    '参考表面 · 御座围屏雕刻 · 官方305': ('太和殿 · 围屏鎏金起伏', (.22, .091, .018), (.58, .286, .063), .54, .53),
    '文渊阁 · 2025院刊实拍额枋彩画': ('文渊阁 · 额枋石绿', (.033, .085, .047), (.101, .179, .092), .70, .08),
}
PREVIEWS = {
    '01': ('Forbidden_City_Overview', .625, .05),
    '57': ('Qianqiu_Pavilion', .6875, .06),
    '60': ('Wanchun_Caisson', .6875, .44),
}


def inventory():
    scenes = {}
    for scene in bpy.data.scenes:
        rows = sorted((obj.name, obj.data.name, len(obj.data.vertices), len(obj.data.polygons))
                      for obj in scene.objects if obj.type == 'MESH' and not obj.get('public_inscription')
                      and not any(c.name == REFERENCE_LAYER for c in obj.users_collection))
        cameras = sorted(obj.name for obj in scene.objects if obj.type == 'CAMERA')
        scenes[scene.name] = {
            'scale': [scene.unit_settings.system, scene.unit_settings.scale_length],
            'frames': [scene.frame_start, scene.frame_end, scene.render.fps],
            'meshes': len(rows), 'faces': sum(row[3] for row in rows),
            'mesh_identity_sha256': hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest(),
            'cameras': cameras,
        }
    return {'scenes': scenes, 'actions': sorted((a.name, tuple(a.frame_range)) for a in bpy.data.actions)}


def put_letters(obj, polygon, inscription, material, font):
    mesh = obj.data
    vertices = [mesh.vertices[i].co.copy() for i in polygon.vertices]
    horizontal = Vector((1, 0, 0))
    normal = polygon.normal.copy()
    if normal.y > 0:
        normal.negate()
    vertical = normal.cross(horizontal).normalized()
    if vertical.z < .9 or abs(normal.dot(horizontal)) > .01:
        raise RuntimeError(f'Unexpected inscription plane: {obj.name}')
    centre = sum(vertices, Vector()) / len(vertices)
    width = max(v.dot(horizontal) for v in vertices) - min(v.dot(horizontal) for v in vertices)
    height = max(v.dot(vertical) for v in vertices) - min(v.dot(vertical) for v in vertices)
    advance = .78 * height / len(inscription)
    orientation = Matrix((horizontal, vertical, normal)).transposed().to_4x4()
    parts = obj.name.split(' · ', 2)
    hall = parts[1] if parts[0] == '匾额' else parts[0]
    for index, char in enumerate(inscription):
        label = f'{hall} · 公开版匾字 {char}'
        curve = bpy.data.curves.new(label, 'FONT')
        curve.body = char
        curve.font = font
        curve.align_x = curve.align_y = 'CENTER'
        curve.size = min(advance * .90, width * .77)
        curve.extrude = min(.006, height * .006)
        curve.bevel_depth = curve.extrude * .26
        curve.materials.append(material)
        letter = bpy.data.objects.new(label, curve)
        for group in obj.users_collection:
            group.objects.link(letter)
        offset = (len(inscription) / 2 - index - .5) * advance
        basis = orientation.copy()
        basis.translation = centre + vertical * offset + normal * .009
        letter.matrix_world = obj.matrix_world @ basis
        bpy.context.view_layer.update()
        letter = object_to_mesh(letter)
        if not letter.data.polygons:
            raise RuntimeError(f'No mesh for glyph {char}')
        letter.parent = obj
        letter.matrix_basis = basis
        letter['public_inscription'] = inscription
        bpy.data.curves.remove(curve)


def prepare():
    scene = bpy.context.scene
    aerial = bpy.data.collections[REFERENCE_LAYER]
    for obj in list(aerial.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(aerial)

    font_path = Path(os.environ.get('PALACE_CJK_FONT') or
                     Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/simkai.ttf')
    if not font_path.is_file():
        raise FileNotFoundError('Set PALACE_CJK_FONT to a local CJK font before packaging.')
    font = bpy.data.fonts.load(str(font_path), check_existing=True)
    enamel = bpy.data.materials['07 · 匾额蓝漆 / cobalt enamel']
    gilt = bpy.data.materials['10 · 金线彩画 / gold painted detail']
    replacements = {}
    for material in list(bpy.data.materials):
        if not material.use_nodes:
            continue
        images = {n.image.name for n in material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image}
        if not images:
            continue
        if len(images) != 1:
            raise RuntimeError(f'Unexpected image bindings on {material.name}')
        image = images.pop()
        if image == 'forbidden_city_georeferenced_aerial.jpg':
            if any(material == slot.material for obj in bpy.data.objects for slot in obj.material_slots):
                raise RuntimeError('Aerial image still bound to scene geometry.')
            bpy.data.materials.remove(material)
            continue
        if image in INSCRIPTIONS:
            replacements[material] = enamel, INSCRIPTIONS[image]
        else:
            title, low, high, roughness, metal = PIGMENTS[material.name]
            replacements[material] = paint(title, low, second=high, scale=8.2, rough=roughness,
                                           metal=metal, bump=.0025, grain=116), None

    represented = set()
    for obj in list(scene.objects):
        if obj.type != 'MESH':
            continue
        for slot, material in enumerate(obj.data.materials):
            if material not in replacements:
                continue
            _, inscription = replacements[material]
            if inscription:
                panels = [p for p in obj.data.polygons if p.material_index == slot]
                if len(panels) != 1:
                    raise RuntimeError(f'Expected one inscription panel on {obj.name}')
                put_letters(obj, panels[0], inscription, gilt, font)
                represented.add(inscription)
    if represented != set(INSCRIPTIONS.values()):
        raise RuntimeError('One or more inscription meshes are missing.')

    for original, (replacement, _) in replacements.items():
        original.user_remap(replacement)
        bpy.data.materials.remove(original)
    for image in list(bpy.data.images):
        if image.source != 'VIEWER':
            bpy.data.images.remove(image, do_unlink=True)
    if any(c.type == 'FONT' and c.font == font for c in bpy.data.curves):
        raise RuntimeError('Live font data remains in the publication copy.')
    bpy.data.fonts.remove(font, do_unlink=True)

    for text in list(bpy.data.texts):
        bpy.data.texts.remove(text)
    bpy.data.texts.new('先读我 · 紫禁城公开工程').write(
        '北京紫禁城 · 米制三维重建 · 御花园版\n\n'
        '使用 Blender 4.5 打开。主场景可编辑、测量。由顶部场景选择器切换四条漫游路线。\n'
        '匾额汉字已经转为网格，未复刻的满文及笔迹不作为考据依据。材质不含摄影贴图或航拍底图。\n'
        '地理底稿：© OpenStreetMap 贡献者，ODbL 1.0。https://www.openstreetmap.org/copyright\n'
        '地图轮廓、刊载尺寸与推定构件的区别，见仓库 README 和校核记录。\n' + REPOSITORY + '\n')
    scene.camera = next(o for o in scene.objects if o.type == 'CAMERA' and o.name.startswith('01 '))
    for scene in bpy.data.scenes:
        scene.render.filepath = '//renders/'
        scene['publication'] = 'Editable public edition without source images. ' + REPOSITORY
    return len(replacements)


def verify(path, original, replaced):
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False)
    reopened = inventory()
    assert reopened == original, 'Original architectural meshes, cameras or timelines changed.'
    assert not bpy.data.libraries, 'Linked libraries remain.'
    assert not [i for i in bpy.data.images if i.source != 'VIEWER' or i.packed_file], 'Source images remain.'
    assert not bpy.utils.blend_paths(packed=True), 'File dependencies remain.'
    inscriptions = {o['public_inscription'] for o in bpy.data.objects if o.get('public_inscription')}
    assert inscriptions == set(INSCRIPTIONS.values()), 'Missing published inscriptions.'
    return {'file': path.name, **reopened, 'replaced_photo_materials': replaced,
            'inscriptions_as_mesh': sorted(inscriptions), 'external_dependencies': [],
            'packed_source_images': 0, 'reopened_and_verified': True}


def preview(target, views):
    scene = bpy.context.scene
    configure_cycles(scene)
    target.mkdir(parents=True, exist_ok=True)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.use_persistent_data = True
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    if scene.cycles.device == 'GPU':
        scene.cycles.denoiser = 'OPTIX'
    for index in views:
        name, aspect, exposure = PREVIEWS[index]
        scene.camera = next(o for o in scene.objects if o.type == 'CAMERA' and o.name.startswith(index + ' '))
        scene.render.resolution_x = 1600
        scene.render.resolution_y = round(1600 * aspect)
        scene.view_settings.exposure = exposure
        scene.render.filepath = str(target / (name + '.png'))
        print('PUBLIC_RENDER', name, flush=True)
        bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--preview-only', action='store_true', help='Render a previously packaged public file.')
    parser.add_argument('--views', nargs='+', choices=tuple(PREVIEWS), default=tuple(PREVIEWS))
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    path = args.output.resolve()
    if args.preview_only:
        bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False)
        preview(path.parent, args.views)
        return
    if path == Path(bpy.data.filepath).resolve():
        parser.error('Output must be different from the source project.')
    path.parent.mkdir(parents=True, exist_ok=True)
    original = inventory()
    replaced = prepare()
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
    report = verify(path, original, replaced)
    path.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('PUBLIC_VERIFIED', path.name, len(report['scenes']), flush=True)
    if args.preview:
        preview(path.parent, args.views)


if __name__ == '__main__':
    main()
