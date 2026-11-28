"""Render README visitor views from the saved public v0.2.0 model.

Run with Blender 4.5 in background mode. The input project is read only;
camera, exposure and render settings are changed in memory and never saved.
No geometry, materials or lighting are replaced for the README image.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

import bpy


CITY = '紫禁城 · metric architectural reconstruction'
VIEWS = {
    'wumen': {
        'scene': '午门 · 穿过正门砖券看内金水河',
        'camera': '105 · 午门 · 广庭内的人眼尺度',
        'filename': 'wumen-entrance-v0.2.0.png',
        'aspect': 9 / 16,
        'exposure': .45,
    },
    'taihe': {
        'scene': '内金水桥 · 石券、栏板与人眼过桥',
        'camera': '141 · 御桥南端看太和门',
        'filename': 'taihe-approach-v0.2.0.png',
        'aspect': 9 / 16,
        'exposure': .35,
    },
    'garden': {
        'scene': CITY,
        'camera': '57 · 千秋亭 · 从踏道仰望重檐',
        'filename': 'qianqiu-pavilion-v0.2.0.png',
        'aspect': 11 / 16,
        'exposure': .15,
    },
    'interior': {
        'scene': CITY,
        'camera': '10 · 太和殿御座正视 / interior ceremonial view',
        'filename': 'taihe-interior-v0.2.0.png',
        'aspect': 3 / 4,
        'exposure': .40,
    },
}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    parser.add_argument('output', type=Path, help='Output directory.')
    parser.add_argument('--width', type=int, default=1920)
    parser.add_argument('--samples', type=int, default=128)
    parser.add_argument('--views', choices=tuple(VIEWS), nargs='+', default=list(VIEWS))
    parser.add_argument('--exposure', type=float, default=None, help='Optional override for every view.')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    project, output = args.project.resolve(), args.output.resolve()
    if not project.is_file():
        parser.error('The public Blender project does not exist.')
    for key in args.views:
        image = output / VIEWS[key]['filename']
        if image.exists() or image.with_suffix('.render.json').exists():
            parser.error('Keep previous render evidence; choose a new output directory.')
    if args.width < 320 or args.samples < 1:
        parser.error('Expected width >= 320 and at least one sample.')
    source_hash = digest(project)
    bpy.ops.wm.open_mainfile(filepath=str(project), load_ui=False)
    device_type = 'CPU'
    preferences = bpy.context.preferences.addons['cycles'].preferences
    try:
        preferences.compute_device_type = 'OPTIX'
        preferences.get_devices()
        for device in preferences.devices:
            device.use = device.type == 'OPTIX'
        if any(device.use for device in preferences.devices):
            device_type = 'GPU'
    except (RuntimeError, TypeError):
        pass
    output.mkdir(parents=True, exist_ok=True)
    for key in args.views:
        view = VIEWS[key]
        scene = bpy.data.scenes[view['scene']]
        camera = scene.objects[view['camera']]
        if camera.type != 'CAMERA':
            raise RuntimeError('Expected a saved visitor-view camera.')
        bpy.context.window.scene = scene
        scene.frame_set(1)
        scene.camera = camera
        scene.render.engine = 'CYCLES'
        scene.cycles.device = device_type
        scene.cycles.samples = args.samples
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.adaptive_threshold = .012
        scene.cycles.use_denoising = True
        scene.cycles.denoiser = 'OPTIX' if device_type == 'GPU' else 'OPENIMAGEDENOISE'
        scene.cycles.max_bounces = 8
        scene.cycles.diffuse_bounces = 4
        scene.cycles.glossy_bounces = 4
        scene.render.resolution_x = args.width
        scene.render.resolution_y = round(args.width * view['aspect'])
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = 'PNG'
        scene.render.image_settings.color_mode = 'RGB'
        scene.render.image_settings.color_depth = '8'
        scene.render.film_transparent = False
        scene.render.use_file_extension = True
        scene.render.use_border = False
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.look = 'AgX - Medium High Contrast'
        scene.view_settings.exposure = view['exposure'] if args.exposure is None else args.exposure
        image = output / view['filename']
        scene.render.filepath = str(image)
        print('README_GALLERY_RENDER_START', key, scene.name, camera.name, device_type, flush=True)
        bpy.ops.render.render(write_still=True, scene=scene.name)
        report = {
            'rendered_at': datetime.now().astimezone().isoformat(),
            'project': project.name,
            'project_sha256': source_hash,
            'image': image.name,
            'image_sha256': digest(image),
            'scene': scene.name,
            'camera': camera.name,
            'camera_location_m': list(camera.matrix_world.translation),
            'camera_lens_mm': camera.data.lens,
            'frame': scene.frame_current,
            'resolution': [scene.render.resolution_x, scene.render.resolution_y],
            'samples': scene.cycles.samples,
            'device': device_type,
            'view_transform': scene.view_settings.view_transform,
            'look': scene.view_settings.look,
            'exposure_ev': scene.view_settings.exposure,
            'native_public_geometry_materials_and_lights': True,
            'input_model_saved': False,
            'whole_city_pixel_perfect_reconstruction_proven': False,
        }
        image.with_suffix('.render.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('README_GALLERY_VIEW_COMPLETE', key, str(image), flush=True)
    if source_hash != digest(project):
        raise RuntimeError('The input model changed during the render.')
    print('README_GALLERY_COMPLETE', ','.join(args.views), flush=True)


if __name__ == '__main__':
    main()
