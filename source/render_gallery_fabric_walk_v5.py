"""Render all 960 native frames with a hash-bound, resumable frame ledger.

Run using Blender. The project is read only. Encode and inspect the complete
PNG sequence separately; a saved camera animation alone is not a movie.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'source'))
from cross_axis_galleries_plan import RANGES, plan
from osm_site import Site
from outer_court_walkthrough import configure_cycles
from refine_cross_axis_fabric_v5 import WALK, CAMERA, audit_route


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def dump(path, value):
    pending = path.with_suffix(path.suffix+'.pending')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    pending.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--route-report', type=Path, default=ROOT/'gallery_fabric_revision_v5_report.json')
    parser.add_argument('--samples', type=int, default=24)
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    source, folder = args.project.resolve(), args.output.resolve()
    source_hash = digest(source)
    route_report = json.loads(args.route_report.read_text(encoding='utf8'))
    profile = {'project':source.name, 'project_sha256':source_hash,
               'route_report_sha256':digest(args.route_report),
               'script_sha256':digest(Path(__file__)),
               'scene':WALK, 'camera':CAMERA, 'frame_start':1, 'frame_end':960,
               'fps':24, 'width':args.width, 'height':round(args.width*9/16),
               'samples':args.samples, 'render_bounces':8, 'diffuse_bounces':5}
    folder.mkdir(parents=True, exist_ok=True)
    ledger = folder/'frame_ledger.json'
    if ledger.exists():
        if not args.resume:
            parser.error('An earlier job exists; inspect its process before explicitly resuming.')
        manifest = json.loads(ledger.read_text(encoding='utf8'))
        if manifest['profile'] != profile:
            parser.error('Cannot reuse frames from a different project or render profile.')
    else:
        if any(folder.iterdir()):
            parser.error('Choose an empty output directory for an unambiguous new job.')
        manifest = {'profile':profile,'started_at':datetime.now().astimezone().isoformat(),
                    'complete':False,'frames':[]}
        dump(ledger,manifest)
    print('FABRIC_WALK_OPEN',source.name,flush=True)
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False)
    scene = bpy.data.scenes[WALK]
    bpy.context.window.scene = scene
    scene.frame_set(1)
    scene.camera = bpy.data.objects[CAMERA]
    route = audit_route(scene,plan(Site(),RANGES[0]),route_report['route_poses'])
    dump(folder/'render_input_route_audit.json',route)
    if not route['passed']:
        raise RuntimeError('The actual render input fails native route support or clearance.')
    configure_cycles(scene)
    scene.cycles.samples = args.samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .03
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = 'OPTIX' if scene.cycles.device == 'GPU' else 'OPENIMAGEDENOISE'
    scene.cycles.max_bounces = 8
    scene.cycles.diffuse_bounces = 5
    scene.cycles.glossy_bounces = 3
    scene.cycles.seed = 81
    scene.cycles.use_animated_seed = False
    scene.render.resolution_x,scene.render.resolution_y = profile['width'],profile['height']
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.render.film_transparent = False
    scene.render.use_border = False
    scene.render.use_persistent_data = True
    done = {r['frame']:r for r in manifest['frames']}
    for frame in range(1,961):
        output = folder/f'{frame:04d}.png'
        if frame in done:
            if not output.is_file() or digest(output) != done[frame]['sha256']:
                raise RuntimeError('A previously rendered frame changed: '+output.name)
            continue
        pending = folder/f'{frame:04d}.pending.png'
        if output.exists() or pending.exists():
            raise RuntimeError('Inspect an unreceipted frame before continuing: '+output.name)
        scene.frame_set(frame)
        scene.render.filepath = str(pending)
        bpy.ops.render.render(write_still=True,scene=scene.name)
        pending.replace(output)
        manifest['frames'].append({'frame':frame,'file':output.name,'sha256':digest(output)})
        dump(ledger,manifest)
        if frame == 1 or frame % 24 == 0:
            print('FABRIC_WALK_PROGRESS',frame,960,flush=True)
    if digest(source) != source_hash:
        raise RuntimeError('The render input changed while the sequence was rendering.')
    manifest['complete'] = True
    manifest['finished_at'] = datetime.now().astimezone().isoformat()
    dump(ledger,manifest)
    print('FABRIC_WALK_COMPLETE',len(manifest['frames']),flush=True)


if __name__ == '__main__':
    main()
