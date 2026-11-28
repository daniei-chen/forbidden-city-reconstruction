"""Bounded, editable fabric refinements; no new measured-dimension claim.

The existing gallery plan, heights, tiles and fenestration remain authoritative.
Millimetre edge dressing and optical response are visual interpretations, not
measurements of the conserved surfaces. No photographic texture is introduced.
"""
import hashlib
import json
import math
import random

import bmesh
import bpy
import numpy as np

SEED = 'palace_fabric_piece_v5'
BEVEL_NAME = 'v5 · 廊下铺砖 1.2毫米细棱'
BEVEL_WIDTH = .0012
WELD_TOLERANCE = .00002


def encoded_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode('utf8')).hexdigest()


def mesh_hash(mesh):
    result = hashlib.sha256()
    for collection, field, width, dtype in (
        (mesh.vertices, 'co', 3, np.float32),
        (mesh.loops, 'vertex_index', 1, np.int32),
        (mesh.polygons, 'loop_start', 1, np.int32),
        (mesh.polygons, 'loop_total', 1, np.int32),
        (mesh.polygons, 'material_index', 1, np.int32),
        (mesh.polygons, 'use_smooth', 1, np.uint8),
    ):
        data = np.empty(len(collection)*width, dtype=dtype)
        collection.foreach_get(field, data)
        result.update(data.tobytes())
    return result.hexdigest()


def serial(value):
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, float):
        return round(value, 8)
    if isinstance(value, bpy.types.ID):
        return value.name
    try:
        return [serial(x) for x in value]
    except TypeError:
        return str(value)


def material_hash(material):
    tree = material.node_tree if material.use_nodes else None
    nodes = []
    if tree:
        for node in sorted(tree.nodes, key=lambda n: n.name):
            nodes.append([node.name, node.bl_idname,
                          [(socket.name, serial(socket.default_value))
                           for socket in node.inputs if hasattr(socket, 'default_value')],
                          [(key, serial(getattr(node, key))) for key in
                           ('operation', 'blend_type', 'attribute_name', 'noise_dimensions', 'image')
                           if hasattr(node, key)],
                          [[round(e.position, 8), serial(e.color)] for e in node.color_ramp.elements]
                          if node.type == 'VALTORGB' else None])
    links = sorted([l.from_node.name, l.from_socket.identifier,
                    l.to_node.name, l.to_socket.identifier] for l in tree.links) if tree else []
    return encoded_hash([serial(material.diffuse_color), nodes, links])


def piece_attribute(mesh, label):
    """One deterministic value per connected component, constant on its faces."""
    parent = list(range(len(mesh.vertices)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    edges = np.empty(len(mesh.edges)*2, dtype=np.int32)
    mesh.edges.foreach_get('vertices', edges)
    for a, b in edges.reshape(-1, 2):
        a, b = root(int(a)), root(int(b))
        if a != b:
            parent[b] = a
    rng = random.Random(int(hashlib.sha256(label.encode('utf8')).hexdigest()[:16], 16))
    values, known = [], {}
    for face in mesh.polygons:
        component = root(face.vertices[0])
        if component not in known:
            known[component] = rng.random()
        values.append(known[component])
    attribute = mesh.attributes.new(SEED, 'FLOAT', 'FACE')
    attribute.data.foreach_set('value', values)
    return len(known)


def dress_paving(obj):
    """Weld coincident cap/side vertices before adding a real bevel modifier."""
    if obj.data.users != 1:
        raise RuntimeError('Expected an independent paving mesh: '+obj.name)
    if any(abs(obj.matrix_world.to_scale()[i]-1.) > 1e-5 for i in range(3)):
        raise RuntimeError('The millimetre bevel requires a unit-scale object.')
    mesh = obj.data
    before = [len(mesh.vertices), len(mesh.polygons)]
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=WELD_TOLERANCE)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    top = [p for p in mesh.polygons if all(abs(mesh.vertices[i].co.z-1.) < 2e-5 for i in p.vertices)]
    if not top or min(p.normal.z for p in top) < .99:
        raise RuntimeError('Welding changed the expected upward paving surface.')
    components = piece_attribute(mesh, obj.name)
    modifier = obj.modifiers.new(BEVEL_NAME, 'BEVEL')
    modifier.width = BEVEL_WIDTH
    modifier.segments = 3
    modifier.limit_method = 'ANGLE'
    modifier.angle_limit = math.radians(35)
    modifier.use_clamp_overlap = True
    modifier.harden_normals = True
    return {'object': obj.name, 'before_vertices_faces': before,
            'after_vertices_faces': [len(mesh.vertices), len(mesh.polygons)],
            'connected_pavers': components, 'top_polygons': len(top),
            'bevel_width_m': BEVEL_WIDTH, 'bevel_segments': 3,
            'floor_top_retained_m': 1., 'weld_tolerance_m': WELD_TOLERANCE}


def node(tree, kind, label, x, y):
    n = tree.nodes.new(kind)
    n.name = n.label = 'v5 · '+label
    n.location = x, y
    return n


def remap(tree, source, low, high, label, x, y):
    n = node(tree, 'ShaderNodeMapRange', label, x, y)
    n.inputs['From Min'].default_value = 0.
    n.inputs['From Max'].default_value = 1.
    n.inputs['To Min'].default_value = low
    n.inputs['To Max'].default_value = high
    tree.links.new(source, n.inputs['Value'])
    return n.outputs['Result']


def refine_material(original, category):
    material = original.copy()
    material.name = 'v5 · '+original.name
    material['fabric_revision'] = 'gallery-fabric-v5'
    material['source_material'] = original.name
    material['evidence_status'] = 'Photograph-informed, inferred surface response; not measured BRDF or site wear mapping.'
    tree = material.node_tree
    surface = next(n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED')
    coord = next(n for n in tree.nodes if n.type == 'TEX_COORD')
    fine = node(tree, 'ShaderNodeTexNoise', '毫米级表面细度', -670, -690)
    fine.inputs['Scale'].default_value = 570.
    fine.inputs['Detail'].default_value = 2.3
    tree.links.new(coord.outputs['Object'], fine.inputs['Vector'])
    if category in ('paving', 'tile'):
        attribute = node(tree, 'ShaderNodeAttribute', '逐件稳定色差', -950, -470)
        attribute.attribute_name = SEED
        value = attribute.outputs['Fac']
        low, high = ((.78, .91) if category == 'paving' else (.43, .55))
        rough = remap(tree, value, low, high, '逐件粗糙度', -420, -490)
        tree.links.new(rough, surface.inputs['Roughness'])
        factor = remap(tree, value, .94, 1.055, '逐件低对比明度', -410, -320)
        incoming = surface.inputs['Base Color'].links[0].from_socket
        mix = node(tree, 'ShaderNodeMixRGB', '保留原色的逐件差异', 0, 300)
        mix.blend_type = 'MULTIPLY'
        mix.inputs[0].default_value = 1.
        tree.links.new(incoming, mix.inputs[1])
        tree.links.new(factor, mix.inputs[2])
        tree.links.new(mix.outputs[0], surface.inputs['Base Color'])
        if category == 'paving':
            mineral = node(tree, 'ShaderNodeTexNoise', '砖面细颗粒色泽', -680, -920)
            mineral.inputs['Scale'].default_value = 205.
            mineral.inputs['Detail'].default_value = 2.6
            tree.links.new(coord.outputs['Object'], mineral.inputs['Vector'])
            tone = remap(tree, mineral.outputs['Fac'], .89, 1.075,
                         '细颗粒低对比明度', -400, -900)
            grain_mix = node(tree, 'ShaderNodeMixRGB', '矿物颗粒与原砖色', 230, 300)
            grain_mix.blend_type = 'MULTIPLY'
            grain_mix.inputs[0].default_value = 1.
            tree.links.new(mix.outputs[0], grain_mix.inputs[1])
            tree.links.new(tone, grain_mix.inputs[2])
            tree.links.new(grain_mix.outputs[0], surface.inputs['Base Color'])
        if category == 'tile':
            surface.inputs['Coat Weight'].default_value = .055
            surface.inputs['Coat Roughness'].default_value = .38
        distance = .00036 if category == 'paving' else .00012
    else:
        base = float(surface.inputs['Roughness'].default_value)
        delta = .045 if category == 'lacquer' else .035
        rough = remap(tree, fine.outputs['Fac'], max(.2, base-delta), min(.97, base+delta),
                      '细微粗糙度', -410, -490)
        tree.links.new(rough, surface.inputs['Roughness'])
        distance = .00012 if category in ('stone', 'masonry') else .000055
        if category == 'lacquer':
            stretch = node(tree, 'ShaderNodeVectorMath', '漆下顺木纹尺度', -950, -700)
            stretch.operation = 'MULTIPLY'
            stretch.inputs[1].default_value = (130., 130., 3.6)
            tree.links.new(coord.outputs['Object'], stretch.inputs[0])
            tree.links.new(stretch.outputs['Vector'], fine.inputs['Vector'])
            fine.inputs['Scale'].default_value = 1.
            fine.inputs['Roughness'].default_value = .58
    bump = node(tree, 'ShaderNodeBump', '克制的物理微起伏', 0, -390)
    bump.inputs['Strength'].default_value = .20
    bump.inputs['Distance'].default_value = distance
    prior = surface.inputs['Normal'].links
    if prior:
        tree.links.new(prior[0].from_socket, bump.inputs['Normal'])
    tree.links.new(fine.outputs['Fac'], bump.inputs['Height'])
    tree.links.new(bump.outputs['Normal'], surface.inputs['Normal'])
    return material


def seed_hash(mesh):
    values = np.empty(len(mesh.attributes[SEED].data), dtype=np.float32)
    mesh.attributes[SEED].data.foreach_get('value', values)
    return hashlib.sha256(values.tobytes()).hexdigest()


def material_category(name):
    if '廊下铺砖' in name:
        return 'paving'
    if '黄釉' in name or '黄琉璃瓦' in name:
        return 'tile'
    if '旧朱漆柱木' in name or '暗朱门板' in name or '望板暗木' in name:
        return 'lacquer'
    if '柱础青白石' in name:
        return 'stone'
    if any(s in name for s in ('青砖', '灰浆', '灰面')):
        return 'masonry'
    if any(s in name for s in ('石青', '石绿', '细金线')):
        return 'paint'
    return None


def apply(city, keys):
    targets = sorted((o for o in city.objects if o.type == 'MESH' and
                      (o.get('cross_axis_gallery') in keys or o.get('cross_axis_junction') in keys)),
                     key=lambda o: o.name)
    paving = [o for o in targets if o.get('cross_axis_gallery_role') == 'paving']
    roofs = [o for o in targets if o.get('junction_role') == 'continuous_roof'
             and len(o.data.polygons) > 100000]
    if len(paving) != 4 or len(roofs) != 4:
        raise RuntimeError('Expected four gallery pavements and four continuous native tile meshes.')
    edges = [dress_paving(obj) for obj in paving]
    pieces = {}
    for obj in roofs:
        pieces[obj.name] = piece_attribute(obj.data, obj.name)
    copied, bindings = {}, []
    for obj in targets:
        for index, original in enumerate(list(obj.data.materials)):
            if original is None or not original.use_nodes:
                continue
            category = material_category(original.name)
            if category is None:
                continue
            # Only the explicit tile meshes have per-piece face values.
            if category == 'tile' and obj not in roofs:
                continue
            if original not in copied:
                copied[original] = refine_material(original, category)
                original.use_fake_user = True  # Keep the pre-revision graph for comparison.
            if obj.data.users != 1:
                raise RuntimeError('Refuse to change a material slot on shared mesh data: '+obj.name)
            obj.data.materials[index] = copied[original]
            bindings.append([obj.name, index, original.name, copied[original].name])
    return {'target_objects': [o.name for o in targets],
            'geometry_changed_objects': [o.name for o in paving],
            'paving': edges, 'roof_connected_piece_counts': pieces,
            'piece_attribute_hashes': {o.name: seed_hash(o.data) for o in paving+roofs},
            'material_bindings': bindings,
            'material_hashes': {m.name: material_hash(m) for m in copied.values()},
            'surface_method': 'Independent copies of existing materials; millimetre noise and face-constant deterministic per-piece variation.'}
