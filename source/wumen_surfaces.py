"""Gate-local procedural surfaces and intact per-ceramic-element variation.

Weathering patterns are authored, not measured historic damage. No shared city
material is edited. The native city keeps its existing geometry and sources.
"""
import hashlib
from types import SimpleNamespace

import bpy
import numpy as np

from palace_materials import paint

PREFIX = '午门修订 · '
ATTR = 'wumen_ceramic_element_tone'


def digest_geometry(mesh):
    values = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', values)
    return hashlib.sha256(values.tobytes()).hexdigest()


def weathered_red(material, floor):
    nodes, links = material.node_tree.nodes, material.node_tree.links
    surface = nodes.get('Principled BSDF')
    original = surface.inputs['Base Color'].links[0].from_socket
    geo = nodes.new('ShaderNodeNewGeometry')
    split = nodes.new('ShaderNodeSeparateXYZ')
    links.new(geo.outputs['Position'], split.inputs[0])
    stretch = nodes.new('ShaderNodeVectorMath'); stretch.operation = 'MULTIPLY'
    stretch.inputs[1].default_value = (7.8, 7.8, .31)
    links.new(geo.outputs['Position'], stretch.inputs[0])
    cracks = nodes.new('ShaderNodeTexVoronoi'); cracks.feature = 'DISTANCE_TO_EDGE'
    cracks.inputs['Scale'].default_value = 5.5
    links.new(stretch.outputs['Vector'], cracks.inputs['Vector'])
    threshold = nodes.new('ShaderNodeMapRange')
    threshold.inputs['From Min'].default_value = .002
    threshold.inputs['From Max'].default_value = .017
    threshold.inputs['To Min'].default_value = .55
    threshold.inputs['To Max'].default_value = 0.
    links.new(cracks.outputs['Distance'], threshold.inputs['Value'])
    mottle = nodes.new('ShaderNodeTexNoise')
    mottle.inputs['Scale'].default_value = 1.74
    mottle.inputs['Detail'].default_value = 3.2
    links.new(geo.outputs['Position'], mottle.inputs['Vector'])
    mask = nodes.new('ShaderNodeMath'); mask.operation = 'MULTIPLY'
    links.new(threshold.outputs['Result'], mask.inputs[0])
    links.new(mottle.outputs['Fac'], mask.inputs[1])
    mix = nodes.new('ShaderNodeMixRGB')
    mix.inputs[2].default_value = (.108, .063, .033, 1.)
    links.new(mask.outputs[0], mix.inputs[0]); links.new(original, mix.inputs[1])
    # Very restrained dull grey ground at column feet, with irregular height.
    lower = nodes.new('ShaderNodeMapRange')
    lower.inputs['From Min'].default_value = floor + .17
    lower.inputs['From Max'].default_value = floor + .55
    lower.inputs['To Min'].default_value = .32
    lower.inputs['To Max'].default_value = 0.
    links.new(split.outputs['Z'], lower.inputs['Value'])
    dull = nodes.new('ShaderNodeMixRGB')
    dull.inputs[2].default_value = (.155, .112, .078, 1.)
    links.new(lower.outputs['Result'], dull.inputs[0]); links.new(mix.outputs[0], dull.inputs[1])
    links.new(dull.outputs[0], surface.inputs['Base Color'])
    rough = nodes.new('ShaderNodeMapRange')
    rough.inputs['To Min'].default_value = .47
    rough.inputs['To Max'].default_value = .79
    links.new(mottle.outputs['Fac'], rough.inputs['Value'])
    links.new(rough.outputs['Result'], surface.inputs['Roughness'])
    bump = nodes.new('ShaderNodeBump'); bump.invert = True
    bump.inputs['Strength'].default_value = .14
    bump.inputs['Distance'].default_value = .00032
    if surface.inputs['Normal'].is_linked:
        links.new(surface.inputs['Normal'].links[0].from_socket, bump.inputs['Normal'])
    links.new(mask.outputs[0], bump.inputs['Height']); links.new(bump.outputs['Normal'], surface.inputs['Normal'])
    material['condition_status'] = 'Authored fine paint fissures and restrained foot wear, not a registered condition map.'


def glaze(material):
    nodes, links = material.node_tree.nodes, material.node_tree.links
    surface = nodes.get('Principled BSDF')
    old = surface.inputs['Base Color'].links[0].from_socket
    attribute = nodes.new('ShaderNodeAttribute'); attribute.attribute_name = ATTR
    tones = nodes.new('ShaderNodeMapRange')
    tones.inputs['To Min'].default_value = .78
    tones.inputs['To Max'].default_value = 1.23
    links.new(attribute.outputs['Fac'], tones.inputs['Value'])
    mix = nodes.new('ShaderNodeMixRGB'); mix.blend_type = 'MULTIPLY'
    mix.inputs[0].default_value = 1.
    links.new(old, mix.inputs[1]); links.new(tones.outputs['Result'], mix.inputs[2])
    links.new(mix.outputs[0], surface.inputs['Base Color'])
    roughness = nodes.new('ShaderNodeMapRange')
    roughness.inputs['To Min'].default_value = .24
    roughness.inputs['To Max'].default_value = .43
    links.new(attribute.outputs['Fac'], roughness.inputs['Value'])
    links.new(roughness.outputs['Result'], surface.inputs['Roughness'])
    material['variation_status'] = 'Per native ceramic element; colour variation is unmeasured.'


def materials(base):
    p = SimpleNamespace(**base.__dict__)
    def mat(label, a, b=None, **kwargs):
        return paint(PREFIX + label, a, second=b, **kwargs)
    p.red = mat('朱漆木与细裂', (.19, .018, .010), (.38, .047, .023),
                scale=1.8, rough=.58, grain=360., bump=.00024, coat=.055)
    weathered_red(p.red, 12.)
    p.door = mat('厚板门暗朱漆', (.12, .012, .007), (.255, .032, .014),
                 scale=2.5, rough=.55, grain=410., bump=.00021, coat=.06)
    p.gate_red = mat('城门朱漆木与细裂', (.21, .020, .010), (.37, .041, .019),
                     scale=2.2, rough=.58, grain=370., bump=.00024, coat=.055)
    weathered_red(p.gate_red, .065)
    p.paint = mat('墩台胭脂红灰面', (.292, .040, .022), (.338, .051, .028),
                  scale=.65, rough=.88, grain=210., bump=.00095)
    p.marble_dark = mat('下碱青白石', (.132, .139, .126), (.30, .30, .263),
                        scale=1.4, rough=.87, grain=290., bump=.0011,
                        brick=(1.16, .35, .0055, True))
    p.masonry = mat('上下碱石块', (.205, .206, .181), (.36, .35, .303),
                    scale=2.4, rough=.86, grain=350., bump=.0008,
                    brick=(.88, .332, .0048, True))
    p.bank = p.masonry
    p.marble = mat('台上望柱石', (.29, .285, .252), (.49, .47, .415),
                   scale=.8, rough=.80, grain=320., bump=.00075)
    p.gold = mat('铜件残金', (.41, .23, .062), (.66, .435, .126),
                 scale=25., rough=.36, metal=.76, grain=520., bump=.00007)
    p.old_gold = mat('铜钉与包叶暗金', (.235, .117, .026), (.47, .28, .071),
                     scale=15., rough=.45, metal=.72, grain=430., bump=.0001)
    p.iron = mat('旧铁轴与背带', (.028, .023, .018), (.083, .055, .032),
                 scale=31., rough=.69, metal=.72, grain=230., bump=.0003)
    p.vault_bricks = [mat(f'券砖本体 {i+1}', color, tuple(c * 1.32 for c in color),
                          scale=8.2, rough=.90, grain=210., bump=.00055)
                      for i, color in enumerate(((.152, .148, .122), (.188, .178, .145),
                                                 (.214, .195, .153), (.139, .140, .121),
                                                 (.174, .169, .145), (.223, .202, .169)))]
    p.mortar = mat('砖券细灰缝', (.218, .212, .188), (.282, .270, .232),
                   scale=26., rough=.97, grain=410., bump=.00021)
    p.floor_stones = [mat(f'门洞踏面石 {i+1}', color, tuple(c * 1.24 for c in color),
                          scale=3.6, rough=.80, grain=270., bump=.00045)
                      for i, color in enumerate(((.24, .227, .19), (.285, .261, .214),
                                                 (.204, .201, .177), (.273, .25, .205)))]
    p.tiles = [mat(f'老黄釉筒瓦 {i+1}', color, tuple(c * 1.30 for c in color),
                   scale=22., rough=.34, grain=390., bump=.00016, coat=.11)
               for i, color in enumerate(((.38, .18, .047), (.47, .234, .062),
                                          (.40, .195, .054), (.44, .22, .071),
                                          (.35, .16, .044)))]
    for tile in p.tiles:
        glaze(tile)
    return p


def rematerialize(objects, old, p):
    replacements = {old.red.name: p.red, old.door.name: p.door,
                    old.paint.name: p.paint, old.marble.name: p.marble,
                    old.marble_dark.name: p.marble_dark,
                    old.gold.name: p.gold}
    replacements.update({a.name: b for a, b in zip(old.tiles, p.tiles)})
    records = []
    for obj in objects:
        if obj.type != 'MESH':
            continue
        changed = []
        # Always keep a private mesh for changed slots and face attributes.
        if any(material and material.name in replacements for material in obj.data.materials):
            obj.data = obj.data.copy()
            for index, material in enumerate(obj.data.materials):
                if material and material.name in replacements:
                    new = replacements[material.name]
                    changed.append([material.name, new.name])
                    obj.data.materials[index] = new
            records.append(dict(object=obj.name, changed_slots=changed))
    return records


def tile_attributes(objects):
    records = []
    for obj in sorted(objects, key=lambda o: o.name):
        if obj.type != 'MESH' or not str(obj.get('detail', '')).startswith('Continuous fixed-pitch channels'):
            continue
        mesh = obj.data
        digest = digest_geometry(mesh)
        starts = np.empty(len(mesh.polygons), dtype=np.int32)
        vertices = np.empty(len(mesh.loops), dtype=np.int32)
        mesh.polygons.foreach_get('loop_start', starts)
        mesh.loops.foreach_get('vertex_index', vertices)
        low, high = np.minimum.reduceat(vertices, starts), np.maximum.reduceat(vertices, starts)
        new = np.ones(len(starts), dtype=bool)
        new[1:] = low[1:] > np.maximum.accumulate(high)[:-1]
        elements = np.cumsum(new) - 1
        lo = np.minimum.reduceat(low, np.flatnonzero(new))
        hi = np.maximum.reduceat(high, np.flatnonzero(new))
        if np.any(lo[1:] <= hi[:-1]):
            raise RuntimeError('Ceramic element indexing overlaps: ' + obj.name)
        seed = int.from_bytes(hashlib.sha256(obj.name.encode()).digest()[:8], 'little')
        tones = np.random.default_rng(seed).uniform(.035, .965, int(elements[-1]) + 1).astype(np.float32)
        attr = mesh.attributes.get(ATTR) or mesh.attributes.new(ATTR, 'FLOAT', 'FACE')
        attr.data.foreach_set('value', tones[elements]); mesh.update()
        if digest_geometry(mesh) != digest:
            raise RuntimeError('A tile position was changed during tone assignment.')
        records.append(dict(object=obj.name, native_ceramic_elements=len(tones),
                            faces=len(mesh.polygons), attribute=ATTR,
                            vertex_geometry_sha256=digest, seed=seed))
    return records
