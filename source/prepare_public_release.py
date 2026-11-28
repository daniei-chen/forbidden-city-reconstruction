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
    'taihe_title_reference_crop.jpg': '太和殿',
    'taihe_plaque_face.png': '太和門',
    'wumen_plaque_face_reference.jpg': '午門',
    'xiehe_plaque_face.png': '協和門',
    'xihe_plaque_face.png': '熙和門',
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
PUBLIC_PALETTES = {
    'stone': ((.16, .15, .13), (.29, .27, .23), .35, .86, 0.),
    'paper': ((.34, .30, .23), (.52, .46, .35), .55, .92, 0.),
    'lacquer': ((.14, .018, .012), (.32, .043, .025), 2.6, .53, .02),
    'gold': ((.27, .13, .025), (.67, .42, .105), 12., .43, .28),
    'blue': ((.014, .045, .12), (.052, .15, .28), 8., .52, .06),
    'turquoise': ((.018, .092, .082), (.09, .25, .19), 7., .57, .04),
    'red_gold': ((.12, .018, .011), (.52, .28, .07), 5., .58, .12),
    'interior': ((.09, .035, .021), (.34, .17, .07), 4., .78, .01),
}
PREVIEWS = {
    '01': ('Forbidden_City_Overview', .625, .05),
    '57': ('Qianqiu_Pavilion', .6875, .06),
    '60': ('Wanchun_Caisson', .6875, .44),
    '交接检查相机 · 208': ('Cross_Axis_Junctions', .5625, .05),
}


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


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


def public_fallback(material, image):
    label = (material.name + ' ' + image).casefold()
    if any(key in label for key in ('nine_dragons', 'dais_lower', 'dais_upper', 'stone', '石')):
        family = 'stone'
    elif 'study_page_02_detail' in label:
        family = 'paper'
    elif any(key in label for key in ('plaque', '匾额', '匾心')):
        family = 'blue'
    elif any(key in label for key in ('throne', 'gilt_column', 'dragon_disk', 'couplet', 'gold', '鎏金')):
        family = 'gold' if 'throne' in label or 'gilt_column' in label else 'red_gold'
    elif any(key in label for key in ('carved_screen', 'screen_crest', 'screen_band', 'renshou')):
        family = 'red_gold'
    elif any(key in label for key in ('caisson', 'roundel', 'painted', 'paint', 'beam', 'eave', '彩画', '梁枋')):
        family = 'turquoise'
    elif any(key in label for key in ('qianqing_palace', 'kunning_palace', 'jiaotai_hall')):
        family = 'interior'
    else:
        family = 'lacquer'

    base, highlight, scale, roughness, metal = PUBLIC_PALETTES[family]
    seed = hashlib.sha256((image + material.name).encode('utf-8')).digest()[0]
    shift = (seed % 5 - 2) * .018
    low = tuple(max(0., min(1., channel + shift)) for channel in base)
    high = tuple(max(0., min(1., channel + shift * 1.5)) for channel in highlight)
    return paint('公开版 · ' + material.name, low, second=high, scale=scale,
                 rough=roughness, metal=metal, bump=.006, grain=72.)


def primary_scene():
    candidates = [scene for scene in bpy.data.scenes
                  if any(obj.type == 'CAMERA' and obj.name.startswith('01 ') for obj in scene.objects)]
    if not candidates:
        raise RuntimeError('The editable city scene with its overview camera is missing.')
    return max(candidates, key=lambda item: (len(item.objects), item.name.startswith('紫禁城')))


def clear_local_library_paths():
    cleared = 0
    for prop in bpy.data.bl_rna.properties:
        if prop.type != 'COLLECTION' or prop.identifier == 'rna_type':
            continue
        try:
            datablocks = getattr(bpy.data, prop.identifier)
        except AttributeError:
            continue
        for datablock in datablocks:
            if not isinstance(datablock, bpy.types.ID):
                continue
            reference = datablock.library_weak_reference
            if reference and reference.filepath:
                reference.filepath = ''
                cleared += 1
    return cleared


def prepare():
    aerial = bpy.data.collections[REFERENCE_LAYER]
    for obj in list(aerial.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(aerial)

    font_path = Path(os.environ.get('PALACE_CJK_FONT') or
                     Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/simkai.ttf')
    if not font_path.is_file():
        raise FileNotFoundError('Set PALACE_CJK_FONT to a local CJK font before packaging.')
    font = bpy.data.fonts.load(str(font_path), check_existing=True)
    enamel = bpy.data.materials.get('07 · 匾额蓝漆 / cobalt enamel')
    if enamel is None:
        enamel = paint('07 · 匾额蓝漆 / cobalt enamel', (.013, .046, .186),
                       second=(.026, .102, .353), scale=6.4, rough=.40, bump=.025)
    gilt = bpy.data.materials.get('10 · 金线彩画 / gold painted detail')
    if gilt is None:
        gilt = paint('10 · 金线彩画 / gold painted detail', (.55, .30, .070),
                     second=(.79, .49, .145), scale=13., rough=.52, metal=.30, bump=.008)
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
            if material.name in PIGMENTS:
                title, low, high, roughness, metal = PIGMENTS[material.name]
                replacement = paint(title, low, second=high, scale=8.2, rough=roughness,
                                    metal=metal, bump=.0025, grain=116)
            else:
                replacement = public_fallback(material, image)
            replacements[material] = replacement, None

    represented = set()
    objects = list(bpy.data.objects)
    used_materials = {slot.material for obj in objects for slot in obj.material_slots if slot.material}
    expected = {inscription for material, (_, inscription) in replacements.items()
                if inscription and material in used_materials}
    for obj in objects:
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
    if represented != expected:
        raise RuntimeError(f'Inscription meshes differ: expected {sorted(expected)}, got {sorted(represented)}')

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
    scene = primary_scene()
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
    dependencies = sorted({path for path in bpy.utils.blend_paths() + bpy.utils.blend_paths(packed=True)
                           if path})
    assert not dependencies, f'File dependencies remain: {dependencies}'
    weak_paths = [obj.name for prop in bpy.data.bl_rna.properties if prop.type == 'COLLECTION'
                  and prop.identifier != 'rna_type' for obj in getattr(bpy.data, prop.identifier, ())
                  if isinstance(obj, bpy.types.ID) and obj.library_weak_reference
                  and obj.library_weak_reference.filepath]
    assert not weak_paths, f'Local library provenance paths remain: {weak_paths[:10]}'
    inscriptions = {o['public_inscription'] for o in bpy.data.objects if o.get('public_inscription')}
    assert inscriptions == set(INSCRIPTIONS.values()), 'Missing published inscriptions.'
    cleared_weak_paths = sum(1 for prop in bpy.data.bl_rna.properties if prop.type == 'COLLECTION'
                             and prop.identifier != 'rna_type'
                             for obj in getattr(bpy.data, prop.identifier, ())
                             if isinstance(obj, bpy.types.ID) and obj.library_weak_reference
                             and not obj.library_weak_reference.filepath)
    scenes = {name: {key: data[key] for key in ('scale', 'frames', 'meshes', 'faces',
                                                'mesh_identity_sha256', 'cameras')}
              for name, data in reopened['scenes'].items()}
    return {'file': path.name, 'scene_count': len(scenes), 'scenes': scenes,
            'action_count': len(reopened['actions']), 'replaced_photo_materials': replaced,
            'inscriptions_as_mesh': sorted(inscriptions), 'external_dependencies': [],
            'packed_source_images': 0, 'reopened_and_verified': True,
            'local_library_provenance_paths_cleared': cleared_weak_paths,
            'whole_city_pixel_perfect_reconstruction_proven': False}


def preview(target, views):
    scene = primary_scene()
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
        candidates = [(candidate, camera) for candidate in bpy.data.scenes for camera in candidate.objects
                      if camera.type == 'CAMERA' and camera.name.startswith(index)]
        if not candidates:
            raise RuntimeError(f'Preview camera {index} is missing.')
        scene, camera = max(candidates, key=lambda pair: (len(pair[0].objects),
                                                           pair[0].name.startswith('紫禁城')))
        configure_cycles(scene)
        scene.camera = camera
        scene.render.resolution_x = 1600
        scene.render.resolution_y = round(1600 * aspect)
        scene.view_settings.exposure = exposure
        scene.render.filepath = str(target / (name + '.png'))
        print('PUBLIC_RENDER', name, flush=True)
        bpy.ops.render.render(write_still=True, scene=scene.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--preview-only', action='store_true', help='Render a previously packaged public file.')
    parser.add_argument('--verify-existing', action='store_true', help='Verify an existing package against the open source file.')
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
    source_path = Path(bpy.data.filepath).resolve()
    source_hash = file_sha256(source_path)
    source_image_count = len([image for image in bpy.data.images if image.source != 'VIEWER'])
    original = inventory()
    if args.verify_existing:
        replaced = sum(1 for material in bpy.data.materials if material.use_nodes and material.node_tree
                       and any(node.type == 'TEX_IMAGE' and node.image
                               for node in material.node_tree.nodes))
        cleared_weak_paths = 0
    else:
        replaced = prepare()
        cleared_weak_paths = clear_local_library_paths()
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
    report = verify(path, original, replaced)
    report.update({'source_file': source_path.name, 'source_sha256': source_hash,
                   'public_sha256': file_sha256(path),
                   'source_images_removed': source_image_count})
    path.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('PUBLIC_VERIFIED', path.name, len(report['scenes']), flush=True)
    if args.preview:
        preview(path.parent, args.views)


if __name__ == '__main__':
    main()
