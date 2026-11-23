"""Self-contained Cycles materials, with no linked photos or texture files."""
from types import SimpleNamespace
import bpy


def paint(name, color, *, second=None, scale=1., rough=.6, metal=0., bump=.03, grain=42., brick=None, coat=0.):
    m=bpy.data.materials.new(name); m.use_nodes=True
    m.diffuse_color=(*color,1.)
    nodes=m.node_tree.nodes; links=m.node_tree.links
    surface=nodes.get('Principled BSDF')
    surface.inputs['Base Color'].default_value=(*color,1.)
    surface.inputs['Roughness'].default_value=rough
    surface.inputs['Metallic'].default_value=metal
    surface.inputs['Coat Weight'].default_value=coat
    surface.inputs['Coat Roughness'].default_value=.32
    tex=nodes.new('ShaderNodeTexCoord'); tex.location=(-930,110)
    vec=tex.outputs['Object']
    if second:
        no=nodes.new('ShaderNodeTexNoise'); no.location=(-700,370)
        no.inputs['Scale'].default_value=scale; no.inputs['Detail'].default_value=4.2
        links.new(vec,no.inputs['Vector'])
        ramp=nodes.new('ShaderNodeValToRGB'); ramp.location=(-450,370)
        ramp.color_ramp.elements[0].position=.19; ramp.color_ramp.elements[0].color=(*color,1.)
        ramp.color_ramp.elements[1].position=.84; ramp.color_ramp.elements[1].color=(*second,1.)
        links.new(no.outputs['Fac'],ramp.inputs[0]); links.new(ramp.outputs['Color'],surface.inputs['Base Color'])
    if bump:
        grain_no=nodes.new('ShaderNodeTexNoise'); grain_no.location=(-700,-120)
        grain_no.inputs['Scale'].default_value=grain; grain_no.inputs['Detail'].default_value=3.0
        links.new(vec,grain_no.inputs['Vector'])
        small=nodes.new('ShaderNodeBump'); small.location=(-200,-210)
        small.inputs['Strength'].default_value=.19; small.inputs['Distance'].default_value=bump
        links.new(grain_no.outputs['Fac'],small.inputs['Height']); links.new(small.outputs['Normal'],surface.inputs['Normal'])
    if brick:
        width,height,joint,vertical=brick
        if vertical:
            # Map vertical courses correctly on walls regardless of their orientation.
            sep=nodes.new('ShaderNodeSeparateXYZ'); sep.location=(-710,25); links.new(vec,sep.inputs[0])
            combine=nodes.new('ShaderNodeCombineXYZ'); combine.location=(-480,25)
            u=nodes.new('ShaderNodeMath'); u.operation='ADD'
            links.new(sep.outputs['X'],u.inputs[0]);links.new(sep.outputs['Y'],u.inputs[1]);links.new(u.outputs[0],combine.inputs['X'])
            links.new(sep.outputs['Z'],combine.inputs['Y']); vec=combine.outputs[0]
        b=nodes.new('ShaderNodeTexBrick');b.location=(-440,105)
        b.inputs['Scale'].default_value=1.;b.inputs['Brick Width'].default_value=width
        b.inputs['Row Height'].default_value=height;b.inputs['Mortar Size'].default_value=joint
        b.inputs['Mortar Smooth'].default_value=joint*.7
        b.inputs['Color1'].default_value=(*color,1.)
        b.inputs['Color2'].default_value=(*(second or tuple(c*1.13 for c in color)),1.)
        b.inputs['Mortar'].default_value=(*(c*.48 for c in color),1.)
        links.new(vec,b.inputs['Vector'])
        if second:
            mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=.19
            links.new(b.outputs['Color'],mix.inputs[1]);links.new(ramp.outputs['Color'],mix.inputs[2])
            links.new(mix.outputs[0],surface.inputs['Base Color'])
        else:
            links.new(b.outputs['Color'],surface.inputs['Base Color'])
        bevel=nodes.new('ShaderNodeBump');bevel.invert=True;bevel.inputs['Strength'].default_value=.28
        bevel.inputs['Distance'].default_value=joint*2.3
        if bump: links.new(small.outputs['Normal'],bevel.inputs['Normal'])
        links.new(b.outputs['Fac'],bevel.inputs['Height']);links.new(bevel.outputs['Normal'],surface.inputs['Normal'])
    return m


def water(name, color, scale):
    m=paint(name,color,rough=.135, metal=0., bump=.042, grain=scale)
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['IOR'].default_value=1.333
    p.inputs['Transmission Weight'].default_value=.08
    p.inputs['Coat Weight'].default_value=.24;p.inputs['Coat Roughness'].default_value=.10
    small=next(n for n in m.node_tree.nodes if n.type=='BUMP');small.inputs['Strength'].default_value=.27
    nodes=m.node_tree.nodes;links=m.node_tree.links
    vector=nodes.new('ShaderNodeVectorMath');vector.operation='MULTIPLY';vector.inputs[1].default_value=(.52,2.8,1.)
    links.new(nodes.get('Texture Coordinate').outputs['Object'],vector.inputs[0])
    links.new(vector.outputs['Vector'],next(n for n in nodes if n.type=='TEX_NOISE').inputs['Vector'])
    return m


def roof_shader(name, c1,c2,c3):
    m=paint(name,c1,second=c2,scale=.55,rough=.36,metal=.0,bump=.012,grain=29.,coat=.14)
    p=m.node_tree.nodes.get('Principled BSDF')
    nodes=m.node_tree.nodes;links=m.node_tree.links
    uv=nodes.new('ShaderNodeUVMap');uv.uv_map='Roof UV'; uv.location=(-900,-430)
    sep=nodes.new('ShaderNodeSeparateXYZ');links.new(uv.outputs[0],sep.inputs[0])
    mult=nodes.new('ShaderNodeMath');mult.operation='MULTIPLY';mult.inputs[1].default_value=9.9
    links.new(sep.outputs['X'],mult.inputs[0])
    wave=nodes.new('ShaderNodeMath');wave.operation='SINE';links.new(mult.outputs[0],wave.inputs[0])
    absval=nodes.new('ShaderNodeMath');absval.operation='ABSOLUTE';links.new(wave.outputs[0],absval.inputs[0])
    r=nodes.new('ShaderNodeValToRGB');r.location=(-220,-400)
    r.color_ramp.elements[0].position=.08;r.color_ramp.elements[0].color=(*c3,1.)
    r.color_ramp.elements[1].position=.92;r.color_ramp.elements[1].color=(*c2,1.)
    links.new(absval.outputs[0],r.inputs[0])
    base=next(n for n in m.node_tree.nodes if n.type=='VALTORGB')
    mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=.29
    mix.inputs[0].default_value=.47
    links.new(base.outputs[0],mix.inputs[1]);links.new(r.outputs[0],mix.inputs[2]);links.new(mix.outputs[0],p.inputs['Base Color'])
    relief=nodes.new('ShaderNodeBump');relief.inputs['Strength'].default_value=.22;relief.inputs['Distance'].default_value=.026
    links.new(absval.outputs[0],relief.inputs['Height'])
    links.new(next(n for n in nodes if n.type=='BUMP' and n!=relief).outputs['Normal'],relief.inputs['Normal'])
    links.new(relief.outputs['Normal'],p.inputs['Normal'])
    return m


def palette():
    p=SimpleNamespace()
    p.red=paint('01 · 深红漆木 / vermilion timber',(.26,.019,.011),second=(.39,.038,.024),scale=2.3,rough=.51,bump=.009,coat=.14)
    p.paint=paint('02 · 宫墙朱砂 / aged cinnabar plaster',(.29,.038,.024),second=(.38,.056,.038),scale=.24,rough=.82,bump=.022,grain=37.)
    p.door=paint('03 · 格扇暗红 / recessed red lacquer',(.083,.011,.007),second=(.17,.021,.013),scale=2.6,rough=.49,bump=.009,coat=.11)
    p.black=paint('04 · 檐下暗部 / deep unlit interior',(.019,.014,.012),rough=.82,bump=0)
    p.inset=paint('05 · 格心底 / dark lattice backing',(.028,.028,.019),second=(.047,.047,.031),rough=.85,bump=.015)
    p.blue=paint('06 · 石青 / mineral blue paint',(.014,.048,.132),second=(.030,.109,.210),scale=9.3,rough=.48,bump=.01)
    p.cobalt=paint('07 · 匾额蓝漆 / cobalt enamel',(.013,.046,.186),second=(.026,.102,.353),scale=6.4,rough=.40,bump=.025)
    p.teal=paint('08 · 石绿 / turquoise painted wood',(.020,.105,.099),second=(.056,.220,.177),scale=6.5,rough=.54,bump=.013)
    p.gold=paint('09 · 鎏金 / warm aged gilding',(.68,.31,.048),second=(.95,.65,.201),scale=15.,rough=.33,metal=.68,bump=.025,grain=68.)
    p.giltpaint=paint('10 · 金线彩画 / gold painted detail',(.55,.30,.070),second=(.79,.49,.145),scale=13.,rough=.52,metal=.30,bump=.008)
    p.roof=roof_shader('11 · 黄琉璃 / ochre glazed tiling',(.49,.184,.025),(.66,.311,.051),(.26,.082,.015))
    p.bed=paint('11a · 筒瓦下灰背 / ceramic roof bed',(.29,.094,.015),second=(.43,.19,.033),scale=2.3,rough=.62,bump=.015)
    p.green=roof_shader('12 · 绿琉璃 / jade green tiling',(.025,.173,.093),(.083,.30,.174),(.020,.091,.065))
    p.grey=roof_shader('13 · 灰瓦 / smoked grey roof',(.155,.145,.121),(.235,.231,.198),(.058,.053,.045))
    p.tiles=[paint('14 · 琉璃筒瓦 / fired glaze '+str(i+1),c,second=(c[0]*1.22,c[1]*1.30,c[2]*1.49),
                   scale=8.,rough=.34+i*.029,bump=.009,grain=49.,coat=.19) for i,c in enumerate(
                   ((.52,.205,.028),(.57,.258,.045),(.48,.182,.023),(.54,.226,.035),(.45,.174,.024))) ]
    p.darktile=paint('15 · 板瓦 / warm occluded pan tile',(.27,.090,.015),second=(.42,.164,.026),scale=9.,rough=.50,bump=.013)
    p.green_clay=paint('绿釉构件 / smooth green glaze',(.037,.18,.095),second=(.078,.28,.15),scale=8.,rough=.43,bump=.012,coat=.12)
    p.grey_clay=paint('灰瓦构件 / weathered dark ceramic',(.105,.101,.084),second=(.17,.16,.132),scale=6.,rough=.69,bump=.009)
    p.masonry=paint('16 · 城砖 / weathered grey lime brick',(.17,.165,.146),second=(.235,.245,.224),
                      scale=.15,rough=.88,bump=.040,brick=(.49,.165,.016,True))
    p.bank=paint('17 · 石驳岸 / cut-stone revetment',(.31,.29,.234),second=(.52,.49,.402),
                 scale=.45,rough=.85,bump=.042,brick=(.96,.33,.022,True))
    p.marble=paint('18 · 汉白玉 / warm aged marble',(.46,.422,.351),second=(.66,.616,.527),
                   scale=2.2,rough=.72,bump=.024,grain=71.)
    p.marble_dark=paint('19 · 三台石砌 / weathered terrace masonry',(.34,.308,.249),second=(.49,.456,.376),
                   scale=.6,rough=.83,bump=.047,grain=60.,brick=(1.38,.50,.013,True))
    p.terrace_floor=paint('台面 · 风化石板 / weathered terrace flagstones',(.39,.366,.308),second=(.52,.482,.405),
                         scale=.64,rough=.87,bump=.031,brick=(1.55,.65,.011,False))
    p.court=paint('20 · 青灰地砖 / grey-green court pavers',(.119,.116,.103),second=(.187,.178,.153),
                  scale=.12,rough=.91,bump=.029,brick=(.39,.215,.009,False))
    p.path=paint('21 · 石板御路 / pale large slabs',(.20,.188,.163),second=(.31,.288,.237),
                  scale=.63,rough=.85,bump=.026,brick=(1.8,.65,.012,False))
    p.slab=paint('22 · 场景底座 / deep graphite plinth',(.053,.072,.073),rough=.84,bump=.012)
    p.grass=paint('23 · 苑地 / earth and dry grass',(.095,.119,.057),second=(.19,.202,.095),scale=.26,rough=.95,bump=.05)
    p.trunk=paint('24 · 树干 / aged bark',(.050,.039,.028),second=(.17,.12,.071),scale=6.,rough=.9,bump=.08,grain=16.)
    p.leaves=[paint('25 · 苑树枝叶 / foliage '+str(i+1),c,second=tuple(x*1.55 for x in c),
                    scale=6.,rough=.90,bump=.11,grain=20.) for i,c in enumerate(
                    ((.044,.105,.029),(.070,.143,.038),(.095,.161,.045),(.038,.079,.026)))]
    p.willow=[paint('河岸树叶 / willow foliage '+str(i+1),c,second=tuple(x*1.6 for x in c),
                    scale=9.,rough=.88,bump=.12,grain=18.) for i,c in enumerate(
                    ((.068,.115,.027),(.118,.177,.044),(.092,.153,.027),(.057,.094,.019)))]
    p.bronze=paint('26 · 铜器 / patinated ritual bronze',(.032,.090,.071),second=(.107,.18,.106),scale=9.,rough=.48,metal=.55,bump=.035)
    p.water=water('27 · 筒子河 / outer moat',(.019,.062,.056),1.05)
    p.stream=water('28 · 金水河 / inner river',(.015,.049,.042),1.75)
    p.studio=paint('29 · 渲染背景 / graphite studio',(.034,.063,.069),second=(.063,.092,.098),scale=.0013,rough=.95,bump=0)
    return p
