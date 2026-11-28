"""Resolve duplicated context proxies in Wu Men's concave forecourt.

The rectangular city-wall boundary does not include this projecting forecourt.
The old context builder therefore treated four palace annex footprints as
outside-city hutong houses. Two coexist with palace meshes. The other two keep
their source footprint and 5 m tagged height; their wood/red/yellow-tile tags
are used explicitly. Their sections and small joinery remain unmeasured.
"""
import math

import bpy
import numpy as np
from mathutils import Quaternion, Vector
from mathutils.bvhtree import BVHTree
from shapely import contains_xy

from city_roof_tiles import PITCH, add_carrier, ceramic_module, instance_nodes
from mesh_tools import collection
from osm_site import number, rectangle, tags
from palace_materials import paint
from wumen_surfaces import digest_geometry, weathered_red

COURTYARD_IDS = frozenset(('638156236', '638156248', '685292441', '685292442'))


def build(site, group, p):
    removed = []
    for ref in ('638156236', '638156248'):
        duplicate = bpy.data.objects.get('胡同建筑 · 城外轮廓 ' + ref)
        real = bpy.data.objects.get('院落建筑 · OSM ' + ref)
        if duplicate is None or real is None:
            raise RuntimeError('Expected both the palace annex and its duplicate context proxy: ' + ref)
        removed.append(dict(object=duplicate.name, osm_id=ref,
                            retained_palace_object=real.name,
                            reason='The same source footprint was represented twice across the concave city boundary.'))
        mesh = duplicate.data
        bpy.data.objects.remove(duplicate, do_unlink=True)
        if not mesh.users:
            bpy.data.meshes.remove(mesh)
    wood = paint('午门修订 · 前庭附房朱漆木护板', (.14, .012, .007),
                 second=(.255, .027, .013), scale=2.1, rough=.65,
                 grain=330., bump=.0003, coat=.045)
    weathered_red(wood, 0.)
    assets = collection('午门修订 · 附房共享实瓦原型', group)
    prototype = ceramic_module(p, assets, 'yellow')
    prototype.name = '午门修订 · 附房筒瓦板瓦原型'
    nodes = instance_nodes(prototype, 'wumen_annex_yellow')
    records = []
    for ref in ('685292441', '685292442'):
        obj = bpy.data.objects.get('胡同建筑 · 城外轮廓 ' + ref)
        if obj is None:
            raise RuntimeError('Missing mapped forecourt annex: ' + ref)
        tt = tags(site.ways[ref])
        if tt.get('building:material') != 'wood' or tt.get('roof:shape') != 'gabled':
            raise RuntimeError('The source annex tags changed; recheck its construction: ' + ref)
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        geometry_before = digest_geometry(obj.data)
        before = [m.name if m else None for m in obj.data.materials]
        roof_indices = [i for i, m in enumerate(obj.data.materials) if m and '灰瓦屋面' in m.name]
        if len(roof_indices) != 1:
            raise RuntimeError('Expected one generic grey roof slot: ' + obj.name)
        roof_faces = sum(face.material_index == roof_indices[0] for face in obj.data.polygons)
        if not roof_faces:
            raise RuntimeError('The generic annex roof has no faces: ' + ref)
        # Keep its exact roof/gable intersection. Overlaying a different curved
        # roof on this mesh would leave the old triangular gable protruding.
        obj.data.materials[roof_indices[0]] = p.tiles[1]
        for index, material in enumerate(obj.data.materials):
            if material and '城砖' in material.name:
                obj.data.materials[index] = wood
        obj['context_classification_revision'] = 'Palace forecourt annex, not outside-city hutong.'
        obj['material_source'] = 'source/palace_osm_full.xml #' + ref
        obj['material_status'] = 'Wood, red wall and tile hue follow contributed tags; not material spectroscopy.'
        footprint = site.geom(ref)
        x, y, width, depth, yaw = rectangle(footprint)
        total, rise = number(tt.get('height'), 5.), number(tt.get('roof:height'), 2.)
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        matrix = obj.evaluated_get(graph).matrix_world.copy()
        inverse = matrix.inverted()
        normal_matrix = inverse.transposed().to_3x3()
        tree = BVHTree.FromPolygons([v.co for v in obj.data.vertices],
                                   [list(f.vertices) for f in obj.data.polygons],
                                   all_triangles=False, epsilon=.000001)
        c, s = math.cos(yaw), math.sin(yaw)
        nx, ny = max(1, round(width / PITCH)), max(1, round(depth / .30))
        xx, yy = np.meshgrid((np.arange(nx) + .5) * width / nx - width / 2,
                             (np.arange(ny) + .5) * depth / ny - depth / 2)
        xx, yy = xx.ravel(), yy.ravel()
        wx, wy = x + xx * c - yy * s, y + xx * s + yy * c
        mask = contains_xy(footprint, wx, wy)
        for dx, dy in ((-.11, -.10), (.26, -.10), (-.11, .10), (.26, .10)):
            mask &= contains_xy(footprint, wx + dx * c - dy * s, wy + dx * s + dy * c)
        top = max((matrix @ v.co).z for v in obj.data.vertices) + 2.
        positions, rotations, scales = [], [], []
        for i in np.flatnonzero(mask):
            origin = inverse @ Vector((float(wx[i]), float(wy[i]), top))
            direction = (inverse.to_3x3() @ Vector((0., 0., -1.))).normalized()
            hit, normal, face, distance = tree.ray_cast(origin, direction, 100.)
            if hit is None or obj.data.polygons[face].material_index != roof_indices[0]:
                continue
            normal = (normal_matrix @ normal).normalized()
            if normal.z < 0:
                normal.negate()
            if normal.z < .16:
                continue
            horizontal = Vector((normal.x, normal.y, 0.))
            if horizontal.length < .0001:
                horizontal = Vector((s, -c, 0.))
            upslope = -horizontal
            upslope.z = horizontal.length_squared / max(normal.z, .01)
            upslope.normalize()
            q = normal.to_track_quat('Z', 'Y')
            local_y = q @ Vector((0, 1, 0))
            angle = math.atan2(normal.dot(local_y.cross(upslope)), local_y.dot(upslope))
            q = Quaternion(normal, angle) @ q
            positions.append(tuple(matrix @ hit + normal * .018))
            rotations.append(tuple(q.to_euler()))
            scales.append((width / nx / PITCH,
                           max(.90, min(2.3, (depth / ny) / (.38 * normal.z))), 1.))
        if not positions:
            raise RuntimeError('No tiles reached the retained annex roof: ' + ref)
        roof = add_carrier('午门修订 · 前庭附房三维黄瓦 ' + ref, group, nodes,
                           positions, rotations, scales, ref, 'yellow')
        roof['section_status'] = 'Original mapped roof and gable junction retained; nominal individual tiles, not surveyed.'
        geometry_after = digest_geometry(obj.data)
        if geometry_after != geometry_before:
            raise RuntimeError('The retained annex envelope changed: ' + ref)
        records.append(dict(object=obj.name, osm_id=ref, source_tags=tt,
                            preserved_footprint_area_m2=footprint.area,
                            retained_map_height_m=total, inferred_roof_rise_m=rise,
                            old_material_slots=before, preserved_roof_faces=roof_faces,
                            geometry_sha256=geometry_after, tile_carrier=roof.name,
                            tile_modules=len(positions), physical_tiles=len(positions) * 2,
                            section_status='Mapped, not surveyed. Existing window and wall sections are retained.'))
    return dict(removed_duplicate_proxies=removed, revised_annexes=records,
                boundary_issue='The projecting concave forecourt lies south of the simple city-wall boundary.',
                limits=['The photographs and contributed map are not a same-date measured facade survey.',
                        'The annex material classification is corrected; hidden construction, exact joinery and current temporary displays remain unverified.'])
