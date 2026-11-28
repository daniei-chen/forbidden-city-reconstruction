"""Replace only generic ridge ornaments, retaining every original roof tile.

These are authored sculptural prototypes fitted to inherited roof envelopes.
Species counts, sections and assembly divisions have not been surveyed on Wu
Men. The sixteen editing parts of a chiwen are not a claim about its real joints.
"""
import math

import bpy

from architectural_roofs import swept_roof
from mesh_tools import Batch
from wumen_masonry import SOURCE


def finial(target, origin, yaw, bed, p):
    b = Batch(origin, yaw)
    b.lathe(0, 0, ((.31, bed - .02), (.31, bed + .035), (.25, bed + .12),
                   (.135, bed + .20), (.19, bed + .29), (.25, bed + .43),
                   (.235, bed + .50), (.19, bed + .62), (.085, bed + .72),
                   (.03, bed + .82)), p.gold, sides=64)
    for j in range(20):
        a = j * math.tau / 20
        b.path([((.16 + .12 * math.sin(t)) * math.cos(a),
                 (.16 + .12 * math.sin(t)) * math.sin(a),
                 bed + .07 + .12 * (1 - math.cos(t)))
                for t in (k * math.pi / 12 for k in range(13))],
               .0085, p.gold, sides=7)
    return b.finish('午门修订 · 铜宝顶及莲瓣细部', target,
                    properties={'role': 'wumen_authored_gilded_finial',
                                'envelope_status': 'Inherited finial envelope; detailed sections and lotus petals unmeasured.'})


def build(group, p, galleries):
    specs = [('午门 · 正楼', 65.05, 30., 21.5, 25.5, 8.1, 'hip', 9)]
    specs.extend(('午门 · 阙亭 ' + ref, 19.6, 19.4, 20., 23.05, 6.3, 'pyramid', 5)
                 for ref in ('638156655', '638156665', '638156677', '638156830'))
    specs.extend((name, 67.6, 13.1, 17.6, None, 3.8, 'gable', 0)
                 for name in ('午门 · 雁翅廊', '午门 · 雁翅廊.001'))
    specs.extend((r['name'], r['width_m'] + .44, 13.1, 17.6, None, 3.8, 'gable', 0)
                 for r in galleries)
    records = []
    for name, width, depth, eave, upper, rise, kind, beasts in specs:
        original = bpy.data.collections[name]
        body = next(o for o in original.objects if 'columns, plinths' in o.name)
        origin, yaw = tuple(body.location), float(body.rotation_euler.z)
        roofs = [c for c in original.children
                 if any(obj.get('roof_type') for obj in c.objects)]
        if len(roofs) != (2 if upper is not None else 1):
            raise RuntimeError('Unexpected inherited roof grouping: ' + name)
        for roof in roofs:
            high = any('上檐' in o.name for o in roof.objects)
            low = any('下檐' in o.name for o in roof.objects)
            rw, rd = (width * .885, depth * .78) if high else (width, depth)
            base = upper if high else eave
            rr = min(6.0, max(2.6, (upper - eave) * 1.42)) if low else rise
            count = min(beasts, 7) if low else beasts
            old_ridges = [o for o in roof.objects if 'sculpted ridge' in o.name]
            if len(old_ridges) != 1:
                raise RuntimeError('Expected one replaceable ridge batch: ' + roof.name)
            replaced = [o.name for o in old_ridges]
            for obj in old_ridges:
                mesh = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if not mesh.users:
                    bpy.data.meshes.remove(mesh)
            new = swept_roof('午门修订 · ' + name.replace('午门 · ', '') + ('上檐' if high else '下檐' if low else '联廊'),
                             group, p, origin=origin, yaw=yaw, width=rw, depth=rd,
                             eave=base, rise=rr, kind=kind, stop=.57 if low else 1.,
                             tiles=False, beasts=count, sculpted=True, soffit=False,
                             terminal_height=1.8 if name == '午门 · 正楼' else None,
                             ridge_terminals=kind != 'gable', pyramid_finial=False)
            for obj in list(new.objects):
                if obj.get('roof_type'):
                    mesh = obj.data
                    bpy.data.objects.remove(obj, do_unlink=True)
                    if not mesh.users:
                        bpy.data.meshes.remove(mesh)
            if kind == 'pyramid' and not low:
                finial(new, origin, yaw, base + rr, p)
            for obj in new.all_objects:
                obj['fitted_building'] = name
                obj['building_reference'] = SOURCE
                obj['sculpture_status'] = 'Authored prototype fitted to inherited outline, not a scan of the actual Wu Men sculpture.'
                obj['part_count_status'] = 'Authoring subdivisions do not establish original ceramic joint counts.'
            records.append(dict(building=name, course='upper' if high else 'lower' if low else 'gallery',
                                retained_tile_collection=roof.name, replaced_ridge_objects=replaced,
                                authored_sculpture_meshes=sum(o.type == 'MESH' for o in new.all_objects),
                                inherited_guardians_excluding_rider=count,
                                gable_terminals_omitted=kind == 'gable',
                                status='Retained tiles and envelope; sculptural surfaces and sections are interpretive.'))
            print('WUMEN_RIDGE_DETAIL', name, 'upper' if high else 'lower' if low else 'gallery', flush=True)
    return records
