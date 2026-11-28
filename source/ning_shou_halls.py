"""Huangji and the rear Ningshou hall on the shared stone podium, in metres."""
from dataclasses import dataclass
import math
from pathlib import Path
from types import SimpleNamespace

import bpy
from mathutils import Vector
from shapely.affinity import rotate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from architectural_roofs import swept_roof
from carved_ornament import cloud, dragon
from garden_bridge_pavilions import laid_pavers, transfer
from mesh_tools import Batch, collection
from ning_shou_gate import local_shape
from ning_shou_inner_gate import INNER_FLOOR
from osm_site import rectangle
from paired_halls import column, frame, lattice
from palace_architecture import arch_mesh
from palace_materials import paint
from qinan_hall import painted_bay, stone_step_run
from qinan_survey import Location, centres
from roof_sculpture import chiwen

REFS = Path(__file__).resolve().parent / 'references' / 'ning_shou_court'
MAIN_ID, REAR_ID = '40592355', '40592356'
FLANKS = ('40592358', '40592359', '40592360', '40592361', '40592362', '40592363')
CROSS_GATES = ('41662971', '41662972')
MAP_PATHS = (41662973, 41662974, 41662975)
MAIN_SOURCE = 'https://www.dpm.org.cn/explore/building/236476.html'
REAR_SOURCE = 'https://www.dpm.org.cn/explore/building/236471.html'
STUDY = 'https://img.dpm.org.cn/Uploads/File/2019/12/15/u5df60ccd5aae1.pdf'
PLAN_SOURCE = 'https://img.dpm.org.cn/Uploads/pdf/1609/T00070_00.pdf'
SECTION_SOURCE = 'https://img.dpm.org.cn/Uploads/pdf/1609/T00071_00.pdf'
ROAD_Z, DECK = 1.60, 2.105
ROAD_SOUTH, ROAD_NORTH, ROAD_WIDTH = -56.15, -26.15, 6.0
LANDING_Y, STAIR_X = -24.31, 1.58
MAIN_EAVE, MAIN_UPPER, RIDGE_BASE = 7.48, 11.35, 18.455
MAIN_X = centres((4.36, 4.78, 5.16, 5.53, 6.25, 5.53, 5.16, 4.78, 4.36))
MAIN_Y = (-10.05, -7.14, -3.03, 2.12, 6.38, 10.06)
REAR_X = centres((5.76, 6.36, 6.72, 6.85, 6.72, 6.36, 5.76))
REAR_Y = (-6.64, -3.99, 1.96, 6.55)
GOLD_COLUMNS = ((-3.47, .13), (3.47, .13), (-3.47, 5.12), (3.47, 5.12))


@dataclass(frozen=True)
class Envelope:
    loc: Location
    width: float
    depth: float

    @classmethod
    def from_way(cls, site, ref):
        x, y, w, d, yaw = rectangle(site.geom(ref))
        return cls(Location(x, y, yaw), w, d)


def palette(base):
    p = SimpleNamespace(**base.__dict__)
    def mat(label, first, second, **opts):
        return paint('两殿 · '+label, first, second=second, **opts)
    p.stone = mat('石栏 · 灰白粉化', (.365,.344,.300), (.695,.658,.575), scale=3.3, rough=.81, grain=148, bump=.0042)
    p.understone = mat('青白石须弥束腰', (.218,.206,.177), (.52,.486,.416), scale=4.6, rough=.84, grain=123, bump=.006)
    p.terrace_floor = mat('青白石台面', (.231,.212,.184), (.479,.447,.387), scale=4.2, rough=.87, grain=136, bump=.005)
    p.court_paver = mat('海墁青砖', (.164,.152,.133), (.328,.304,.271), scale=4.3, rough=.89, grain=137, bump=.004)
    p.path_stones = [mat(f'御路旧石 {i+1}', c, tuple(v*1.46 for v in c), scale=5.1, rough=.83, bump=.0038)
                    for i,c in enumerate(((.30,.281,.249),(.255,.241,.214),(.285,.259,.228),(.243,.220,.195)))]
    p.faded_blue = mat('石青 · 褪色矿物', (.018,.031,.072), (.090,.119,.180), scale=6.1, rough=.76, bump=.0039)
    p.faded_teal = mat('石绿 · 旧漆', (.026,.094,.078), (.130,.221,.157), scale=7., rough=.73, bump=.0037)
    p.fascia = mat('暗朱漆柁枋', (.090,.013,.009), (.247,.045,.028), scale=6.8, rough=.63, bump=.003)
    p.cinnabar = mat('磨蚀朱红细漆', (.23,.021,.012), (.470,.062,.030), scale=8.8, rough=.51, bump=.002)
    p.cream = mat('沥粉线与旧地仗', (.247,.210,.140), (.455,.411,.304), scale=6.1, rough=.75, bump=.004)
    p.lacquer = mat('朱红描金漆器', (.164,.021,.010), (.418,.058,.026), scale=12, rough=.42, coat=.17, bump=.002)
    p.old_gold = mat('金箔与擦损', (.397,.218,.067), (.564,.353,.123), scale=64., rough=.40,
                     metal=.76, grain=430, bump=.00018)
    p.gold = mat('鎏金高光及细刻', (.615,.367,.116), (.804,.574,.249), scale=81., rough=.34,
                 metal=.88, grain=510, bump=.00011)
    p.giltpaint = mat('沥粉贴金线脚', (.27,.134,.034), (.597,.388,.117), scale=17., rough=.57, metal=.21, bump=.0018)
    p.old_wall = mat('胭脂红墙与砖缝', (.220,.034,.024), (.395,.079,.048), scale=3.3, rough=.87, bump=.008)
    p.green_clay = mat('深绿釉龟锦纹', (.019,.091,.054), (.064,.237,.133), scale=11.8, rough=.42, coat=.18, bump=.0022)
    p.glaze_yellow = mat('黄釉透风砖', (.343,.151,.025), (.649,.383,.105), scale=17., rough=.42, coat=.17, bump=.0024)
    p.goldbrick = mat('承重地面 · 磨光金砖', (.038,.044,.047), (.112,.114,.102), scale=1.7, rough=.42, bump=.004)
    p.lightjade = mat('烟囱外皮青砖', (.177,.170,.155), (.345,.322,.281), scale=3.3, rough=.88,
                      bump=.004, brick=(.394,.091,.003,True))
    p.marble = p.stone
    # Each glazed tube carries both fine ceramic grain and irregular light wear.
    p.tiles = [mat(f'旧黄琉璃筒瓦 {i+1}', c, tuple(v*1.47 for v in c), scale=8.9, rough=.37+i*.043,
                   coat=.12, grain=164, bump=.0035)
               for i,c in enumerate(((.438,.179,.041),(.521,.232,.054),(.454,.197,.047),(.390,.167,.043),(.485,.231,.067)))]
    p.darktile = mat('旧琉璃板瓦缝',(.201,.073,.024),(.432,.214,.067),scale=19.1,rough=.61,grain=208,bump=.004)
    for material in p.tiles:
        weathered_glaze(material)
    return p


def weathered_glaze(material):
    """Local worn glaze patches visible in the museum's roof detail photograph.

    Distribution is procedural and explicitly not a record of individual chips.
    The tile sections and overlaps remain independent editable geometry.
    """
    nodes,links=material.node_tree.nodes,material.node_tree.links
    surface=nodes.get('Principled BSDF')
    previous=surface.inputs['Base Color'].links[0].from_socket
    vector=next(n for n in nodes if n.type=='TEX_COORD').outputs['Object']
    noise=nodes.new('ShaderNodeTexNoise'); noise.label='实拍参照 · 不规则釉蚀分布（推定）'
    noise.inputs['Scale'].default_value=24.7; noise.inputs['Detail'].default_value=3.4
    noise.inputs['Roughness'].default_value=.67
    links.new(vector,noise.inputs['Vector'])
    threshold=nodes.new('ShaderNodeMapRange')
    threshold.inputs['From Min'].default_value=.716; threshold.inputs['From Max'].default_value=.821
    threshold.inputs['To Min'].default_value=0.; threshold.inputs['To Max'].default_value=.78
    threshold.clamp=True
    links.new(noise.outputs['Fac'],threshold.inputs['Value'])
    mix=nodes.new('ShaderNodeMixRGB'); mix.blend_type='MIX'
    mix.inputs[2].default_value=(.59,.522,.363,1.)
    links.new(threshold.outputs['Result'],mix.inputs[0]); links.new(previous,mix.inputs[1])
    links.new(mix.outputs['Color'],surface.inputs['Base Color'])
    rough=nodes.new('ShaderNodeMapRange')
    rough.inputs['To Min'].default_value=surface.inputs['Roughness'].default_value
    rough.inputs['To Max'].default_value=.77
    links.new(threshold.outputs['Result'],rough.inputs['Value'])
    links.new(rough.outputs['Result'],surface.inputs['Roughness'])
    material['weathering_reference']='source/references/ning_shou_court/huangji_hall_01.jpg'
    material['weathering_status']='Photo-led procedural wear; exact chip positions unsurveyed.'


def image_surface(key, *, rough=.62, metal=.08):
    found = bpy.data.materials.get('宁寿宫两殿 · '+key)
    if found:
        return found
    image = bpy.data.images.load(str(REFS / f'{key}.jpg'), check_existing=True)
    image.pack()
    image['usage'] = 'Local comparison; Palace Museum source image, rectified visible face'
    mat = bpy.data.materials.new('宁寿宫两殿 · '+key)
    mat.use_nodes = True
    mat.diffuse_color = (.30,.20,.09,1)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    uv = nodes.new('ShaderNodeUVMap'); uv.uv_map = 'Roof UV'
    tex = nodes.new('ShaderNodeTexImage'); tex.image = image; tex.extension = 'EXTEND'
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Metallic'].default_value = metal; bsdf.inputs['Roughness'].default_value = rough
    links.new(uv.outputs['UV'], tex.inputs['Vector'])
    if key=='huangji_gilt_column_detail':
        tex.extension='REPEAT'
        ramp=nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position=.10
        ramp.color_ramp.elements[0].color=(.41,.244,.078,1.)
        ramp.color_ramp.elements[1].position=.91
        ramp.color_ramp.elements[1].color=(.62,.408,.153,1.)
        links.new(tex.outputs['Color'],ramp.inputs['Fac'])
        links.new(ramp.outputs['Color'],bsdf.inputs['Base Color'])
        bump=nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value=.18
        bump.inputs['Distance'].default_value=.00020
        links.new(tex.outputs['Color'],bump.inputs['Height'])
        links.new(bump.outputs['Normal'],bsdf.inputs['Normal'])
    elif key.startswith('huangji_screen_crest_'):
        gamma=nodes.new('ShaderNodeGamma'); gamma.inputs['Gamma'].default_value=.64
        links.new(tex.outputs['Color'],gamma.inputs['Color'])
        links.new(gamma.outputs['Color'],bsdf.inputs['Base Color'])
        bsdf.inputs['Metallic'].default_value=.54
        bump=nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value=.18; bump.inputs['Distance'].default_value=.0017
        links.new(tex.outputs['Color'],bump.inputs['Height']);links.new(bump.outputs['Normal'],bsdf.inputs['Normal'])
        mat['albedo_method']='Photographed carving color with reduced baked shadow; no exact material recovery.'
    elif key.startswith('huangji_caisson_'):
        # These photographs show gilded wood under very dim illumination.
        # Interpret their fine pattern as a reflectance guide rather than
        # multiplying the photographed shadow by the scene illumination again.
        gamma=nodes.new('ShaderNodeGamma'); gamma.inputs['Gamma'].default_value=.42
        links.new(tex.outputs['Color'],gamma.inputs['Color'])
        ramp=nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position=0.
        ramp.color_ramp.elements[0].color=(.115,.047,.010,1.)
        ramp.color_ramp.elements[1].position=.51
        ramp.color_ramp.elements[1].color=(.59,.366,.126,1.)
        links.new(gamma.outputs['Color'],ramp.inputs['Fac'])
        links.new(ramp.outputs['Color'],bsdf.inputs['Base Color'])
        bsdf.inputs['Metallic'].default_value=.76
        bump=nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value=.19; bump.inputs['Distance'].default_value=.0018
        links.new(tex.outputs['Color'],bump.inputs['Height']); links.new(bump.outputs['Normal'],bsdf.inputs['Normal'])
        mat['albedo_method']='Authored gold reflectance from photographed pattern; illumination and exact spectral response unmeasured.'
    else:
        links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    return mat


def inscription(b, x, y, z, w, h, p, key, *, painted=False):
    """Separate wooden back, trims, relief frame and planar calligraphic face."""
    edge = p.cream if painted else p.gold
    b.box((x,y,z),(w+.29,.18,h+.29),p.fascia if painted else p.lacquer)
    for i, (gap,m) in enumerate(((.13,p.giltpaint),(.088,p.lacquer),(.039,edge))):
        frame(b,x,y-.095-i*.020,z,w+2*gap,h+2*gap,.035,m)
    b.face(((x-w/2,y-.116,z-h/2),(x+w/2,y-.116,z-h/2),
            (x+w/2,y-.116,z+h/2),(x-w/2,y-.116,z+h/2)),image_surface(key),
           uv=((0,0),(1,0),(1,1),(0,1)))
    if not painted:
        p0 = SimpleNamespace(**p.__dict__)
        if key.startswith('ning_shou'):
            p0.gold, p0.giltpaint = p.understone, p.cream
        for sign in (-1,1):
            dragon(b,(x+sign*(w/2+.092),y-.134,z-.017),.264,h*.998,p0,mirror=sign<0,z_relief=.030)
            for i in range(7):
                cloud(b,(x+(i-3)*w*.161,y-.148,z+sign*(h/2+.105)),h*.142,p0.gold,rotation=-sign*i*.733)
        for i in range(2):
            b.ellipsoid((x,y-.171,z+h/2+.157+i*.012),(.078,.041,.065),p0.giltpaint,sides=14,rings=8)


def axial_setts(flag, road, p, *, margin=1.02, edge_by_side=None):
    """Lay the larger axial stone panels, diagonal brick and inset curb seams.

    ``margin`` is the measured-in-the-model half-width of the contrasting
    middle panel, not a claim about a historic building survey. When supplied,
    ``edge_by_side`` extends the paired diagonal fields to each mapped boundary.
    """
    edge_by_side=edge_by_side or {-1:3.,1:3.}
    flag.solid_xy(road,ROAD_Z-.056,ROAD_Z,p.understone,bottom=False)
    y0,y1=road.bounds[1],road.bounds[3]
    path=road.intersection(box(-margin,y0-1.,margin,y1+1.))
    laid_pavers(flag,path,ROAD_Z+.001,SimpleNamespace(terrace_floor=p.path_stones[0]),course=1.39,width=2.04)
    for side in (-1,1):
        outer=max(margin+.48,float(edge_by_side[side])-.20)
        a,c=sorted((side*(margin+.174),side*(outer-.19)))
        line_a,line_b=sorted((side*margin,side*(margin+.174)))
        seam=road.intersection(box(line_a,y0-1.,line_b,y1+1.))
        laid_pavers(flag,seam,ROAD_Z+.0017,
                    SimpleNamespace(terrace_floor=p.path_stones[2]),course=.97,width=.19)
        band=road.intersection(box(a,y0-1.,c,y1+1.))
        theta=-side*32.5
        ref=tuple(band.centroid.coords[0])
        u,v,w,d=rotate(band,-theta,origin=ref).bounds
        for j in range(math.ceil((d-v)/.153)):
            yy=v+j*.153
            for i in range(math.ceil((w-u)/.37)+1):
                x=u+(i-.5*(j%2))*.37
                brick=rotate(box(x+.0026,yy+.0023,x+.367,yy+.150),theta,origin=ref).intersection(band)
                flag.solid_xy(brick,ROAD_Z-.03,ROAD_Z+.0012+.0006*math.sin(j*1.51+i*.64),p.court_paver,bottom=False)
        line_a,line_b=sorted((side*(outer-.19),side*outer))
        edge=road.intersection(box(line_a,y0-1.,line_b,y1+1.))
        laid_pavers(flag,edge,ROAD_Z+.0017,
                    SimpleNamespace(terrace_floor=p.path_stones[2]),course=1.02,width=.23)


def carved_posts(b,x,y0,y1,z,p):
    n=max(1,round((y1-y0)/1.55))
    for j in range(n+1):
        y=y0+j*(y1-y0)/n
        for zz,r,h in ((.084,.157,.153),(.226,.139,.122),(.742,.126,.067)):
            b.box((x,y,z+zz),(2*r,2*r,h),p.stone)
        b.lathe(x,y,((.122,z+.751),(.132,z+.796),(.123,z+.880),(.092,z+.982),(.057,z+1.046),(.035,z+1.06)),p.stone,sides=26)
        for k in range(5):
            zz=z+.30+k*.082
            t=(k*.44)
            b.path([(x+.119*math.cos(a),y+.119*math.sin(a),zz+.049*math.sin(a*.95+t))
                    for a in (i*math.tau/44 for i in range(45))],.013,p.stone,sides=7)
            for i in range(8):
                a=i*math.tau/8+t; v=zz+.032*math.sin(i*.79+t)
                b.ellipsoid((x+.120*math.cos(a),y+.120*math.sin(a),v),(.017,.017,.025),p.stone,sides=8,rings=5)


def marble_rail(batch,line,z,p,*,step=1.55):
    """Huangji's pierced stone panels and separately carved cylindrical heads."""
    start,end=line
    length=math.dist(start,end)
    count=max(1,round(length/step))
    pitch=length/count
    work=Batch()
    for i in range(count+1):
        x=i*pitch
        work.box((x,0,z+.439),(.213,.216,.879),p.stone)
        work.box((x,0,z+.072),(.253,.257,.143),p.understone)
        for side in (-1,1):
            frame(work,x,side*.111,z+.476,.157,.689,.011,p.stone)
        work.lathe(x,0,((.128,z+.870),(.131,z+.895),(.122,z+.916),(.126,z+.966),
                        (.130,z+1.035),(.115,z+1.090),(.102,z+1.102)),p.stone,sides=40)
        # Curled ruyi cloud engraving suits the round pale-stone caps better
        # than the gold dragon inherited from the Ningshou bronze balusters.
        # Keep it shallow and on both visible faces, following the museum's
        # photograph of the Inner Court railings.
        for side in (-1,1):
            cloud(work,(x,-.129,z+.985),.135,p.stone,
                  rotation=0. if side<0 else math.pi)
        if i==count:
            continue
        center=x+pitch/2
        span=pitch-.207
        # The broad lower stone field has recessed double molding. The upper
        # rail is open around vase-shaped supports and scrolling leaf brackets.
        work.box((center,0,z+.268),(span,.135,.405),p.stone)
        for side in (-1,1):
            frame(work,center,side*.071,z+.267,span-.115,.268,.015,p.understone)
            frame(work,center,side*.078,z+.267,span-.150,.232,.011,p.stone)
        work.box((center,0,z+.775),(span+.019,.164,.080),p.stone)
        for position in (-.32,0.,.32):
            xx=center+span*position
            work.lathe(xx,0,((.047,z+.471),(.061,z+.492),(.038,z+.529),(.036,z+.589),
                              (.079,z+.629),(.087,z+.666),(.067,z+.708),(.086,z+.735)),p.stone,sides=24)
            for side in (-1,1):
                for orientation in (-1,1):
                    work.path([(xx+orientation*.023,side*.071,z+.688),
                               (xx+orientation*.060,side*.083,z+.726),
                               (xx+orientation*.096,side*.074,z+.714),
                               (xx+orientation*.103,side*.068,z+.684)],.014,p.stone,sides=8)
    transfer(batch,work,*start,math.atan2(end[1]-start[1],end[0]-start[0]))


def drainage_head(batch,x,y,z,p,side):
    """Open stone spout with an interior channel, muzzle and shallow eye relief."""
    head=Batch()
    sides=40
    profile=((-.279,.111,.088),(-.229,.143,.118),(-.104,.163,.132),(.105,.141,.119),(.266,.114,.105))
    vertices=[]
    for inner in (False,True):
        for yy,rx,rz in profile:
            for i in range(sides):
                angle=i*math.tau/sides
                xx=(.047 if inner else rx)*math.cos(angle)
                zz=z-.032+(.037 if inner else rz)*math.sin(angle)
                vertices.append((xx,yy,zz))
    shift=len(profile)*sides
    faces=[]
    for j in range(len(profile)-1):
        for i in range(sides):
            a=j*sides+i; b=j*sides+(i+1)%sides
            faces.append((a,b,b+sides,a+sides))
            faces.append((a+shift,a+sides+shift,b+sides+shift,b+shift))
    for i in range(sides):
        a=i; b=(i+1)%sides
        faces.append((a,a+shift,b+shift,b))
        a=(len(profile)-1)*sides+i; b=(len(profile)-1)*sides+(i+1)%sides
        faces.append((a,b,b+shift,a+shift))
    head.add(vertices,faces,p.stone,smooth=True)
    mouth=Point(0,z-.040).buffer(.072,quad_segs=18)
    muzzle=Point(0,z-.021).buffer(.111,quad_segs=20).difference(mouth)
    rail_cut(head,muzzle,-.259,.091,p.stone)
    for sign in (-1,1):
        head.ellipsoid((sign*.095,-.193,z+.074),(.061,.057,.039),p.stone,sides=19,rings=10)
        head.ellipsoid((sign*.094,-.237,z+.077),(.022,.009,.017),p.understone,sides=16,rings=9)
        head.path([(sign*.030,-.272,z+.118),(sign*.085,-.249,z+.144),
                   (sign*.139,-.209,z+.122)],.022,p.stone,sides=10)
        head.path([(sign*.115,-.149,z+.022),(sign*.177,-.159,z+.061),
                   (sign*.188,-.106,z+.084)],.019,p.stone,sides=9)
    transfer(batch,head,x,y,0 if side<0 else math.pi)


def approach_stairs(b,d,p):
    for side in (-1,1):
        x=side*STAIR_X
        stone_step_run(b,(x,ROAD_NORTH-.02),(x,LANDING_Y+.014),1.50,ROAD_Z,DECK,p,count=3)
    half=.806; a=ROAD_NORTH+.015; c=LANDING_Y+.032
    incline=(DECK-ROAD_Z)/(c-a)
    def z_at(y): return ROAD_Z+.019+(y-a)*incline
    d.face(((-half,a,z_at(a)),(half,a,z_at(a)),(half,c,z_at(c)),(-half,c,z_at(c))),p.stone)
    for s in (-1,1):
        d.path([(s*half,y,z_at(y)+.021) for y in (a,c)],.036,p.stone,sides=11)
    guide=Batch()
    dragon(guide,(0,(a+c)/2-.033,0),1.31,1.77,SimpleNamespace(**(p.__dict__|{'gold':p.stone,'giltpaint':p.stone})),
           facing='down',z_relief=.013,phase=.57)
    for i in range(17):
        y=a+.11+((i*9)%17)*(c-a-.22)/17
        x=.54*math.sin(i*2.36)
        cloud(guide,(x,y,-.014),.165,p.stone,facing='down',rotation=i*.83)
    for i,m in enumerate(guide.mats):
        d.add([(x,y,z_at(y)-z) for x,y,z in guide.v],[f[::-1] for f,j in zip(guide.f,guide.mi) if i==j],m,smooth=True)


def courtyard(site, main, rear, target, p):
    loc = main.loc
    rear_y = loc.local(LineString([rear.loc.world()[:2],rear.loc.world(0,1)[:2]])).coords[0][1]
    rear_top = (rear_y - rear.depth/2 - 3.53, rear_y + rear.depth/2 + 1.76)
    front = unary_union([box(-25.12,-14.15,25.12,13.8), box(-17.09,LANDING_Y,17.09,-13.8),
                         box(-17.09,ROAD_NORTH,-2.63,LANDING_Y+.01),box(2.63,ROAD_NORTH,17.09,LANDING_Y+.01)])
    tail = box(-23.60,rear_top[0],25.86,rear_top[1])
    road = box(-ROAD_WIDTH/2,ROAD_SOUTH,ROAD_WIDTH/2,ROAD_NORTH)
    link = box(-3.59,13.79,3.60,rear_top[0]+.02)
    podium = unary_union([front, tail, link])
    deck = podium.union(road)
    group = collection('两殿 · 王字形共台、月台和两段甬路',target)
    b, flag, road_surface, r, land, stairs, danbi = (loc.batch() for _ in range(7))
    for z0,z1,d,m in ((.012,.175,.112,p.understone),(.175,.293,.062,p.stone),(.293,.435,.009,p.stone),
                      (.435,1.174,-.055,p.understone),(1.174,1.292,.047,p.stone),(1.292,1.436,.093,p.stone),
                      (1.436,ROAD_Z-.053,.013,p.understone)):
        b.solid_xy(deck.buffer(d,join_style=2),z0,z1,m,bottom=False)
    for z0,z1,d,m in ((ROAD_Z-.054,1.725,.056,p.stone),(1.725,1.892,-.018,p.understone),
                      (1.892,2.001,.048,p.stone),(2.001,DECK-.016,.007,p.understone)):
        b.solid_xy(podium.buffer(d,join_style=2),z0,z1,m,bottom=False)
    laid_pavers(flag,podium,DECK,p,course=.73,width=1.24)
    axial_setts(road_surface,road,p)
    approach_stairs(stairs,danbi,p)
    # Join the previously reconstructed gate apron to the published 1.60 m road.
    for j in range(4):
        yy = ROAD_SOUTH - 1.92 + (j+.5)*.48
        zz = INNER_FLOOR+(ROAD_Z-INNER_FLOOR)*(j+1)/4
        b.box((0,yy,zz*.5),(ROAD_WIDTH,.484,zz),p.stone)
    b.box((0,ROAD_SOUTH-2.06,INNER_FLOOR/2),(ROAD_WIDTH,.48,INNER_FLOOR),p.understone)
    for side in (-1,1):
        x=side*2.86
        for a,c in ((ROAD_SOUTH,ROAD_SOUTH+2.85),(ROAD_SOUTH+5.80,ROAD_NORTH-5.32),
                    (ROAD_NORTH-2.45,ROAD_NORTH)):
            marble_rail(r,((x,a),(x,c)),ROAD_Z,p,step=1.55)
        for yy in (ROAD_SOUTH+4.33,ROAD_NORTH-3.89):
            stone_step_run(b,(x+side*3.98,yy),(x+side*.12,yy),2.63,.025,ROAD_Z,p,count=9)
        marble_rail(r,((side*2.77,ROAD_NORTH+.13),(side*16.94,ROAD_NORTH+.13)),DECK,p,step=1.56)
        marble_rail(r,((side*16.93,ROAD_NORTH+.13),(side*16.93,-22.43)),DECK,p)
        marble_rail(r,((side*16.93,-18.24),(side*16.93,-14.07)),DECK,p)
        stone_step_run(b,(side*21.67,-20.34),(side*16.96,-20.34),3.78,.022,DECK,p,count=9)
        marble_rail(r,((side*16.97,-14.08),(side*24.96,-14.08)),DECK,p)
        marble_rail(r,((side*24.96,-14.08),(side*24.96,13.67)),DECK,p)
        marble_rail(r,((side*24.96,13.67),(side*3.49,13.67)),DECK,p)
        marble_rail(r,((side*3.46,13.67),(side*3.46,rear_top[0])),DECK,p,step=1.60)
    for x in (-23.6,-20.5,-17.4,-14.3,-11.2,-8.1,-5.,5.,8.1,11.2,14.3,17.4,20.5,23.6):
        drainage_head(b,x,-14.20,DECK-.231,p,-1)
    b.finish('两殿 · 须弥石座、侧阶和高差衔接',group,bevel=.012)
    stairs.finish('两殿 · 月台前两路石踏跺',group,bevel=.005,
                  properties={'role':'forecourt_stairs','inferred_levels':3,'landing_z':DECK})
    danbi.finish('两殿 · 月台前丹陛石与盘龙浮雕',group,properties={'role':'forecourt_danbi','relief_inferred':True})
    flag.finish('两殿 · 共台踏面与殿前月台铺石',group)
    road_surface.finish('两殿 · 30 米御路条石、双侧斜纹砖和嵌边',group,properties={'role':'measured_axial_walkway','top_z_m':ROAD_Z,
                        'long_road_m':[ROAD_NORTH-ROAD_SOUTH,ROAD_WIDTH,ROAD_Z],'publication':PLAN_SOURCE})
    r.finish('两殿 · 御道与月台雕石栏板',group,bevel=.006)
    apron = unary_union([local_shape(site.geom(str(ref)),loc) for ref in (41662973,41662975)])
    apron = apron.difference(deck.buffer(.014))
    laid_pavers(land,apron,.023,SimpleNamespace(terrace_floor=p.court_paver),course=.26,width=.53)
    land.finish('两殿 · 地面海墁、散水与甬路两院',group)
    return {'main_road_m':[ROAD_NORTH-ROAD_SOUTH,ROAD_WIDTH,ROAD_Z],'road_local_y_m':[ROAD_SOUTH,ROAD_NORTH],
            'estimated_raised_terrace_z_m':DECK,'estimated_steps_to_terrace':3,
            'rear_deck_local_y_m': rear_top,'section_source':PLAN_SOURCE,'joined_platform_area_m2':deck.area}


def terminal_pair(env, roof, p):
    ridge = env.width*.61/2
    # The published original has 11 pieces; this grouping describes the model only.
    divisions = ((0,1),(2,3),(4,5),(6,7),(8,9),(10,),(11,),(12,),(13,),(14,),(15,))
    for sign in (-1,1):
        chiwen(roof,p,origin=env.loc.world(sign*ridge,0,RIDGE_BASE+.16),yaw=env.loc.yaw,end=sign,
               width=1.98,thickness=.48,height=2.60,divisions=divisions,source=SECTION_SOURCE,
               label=f'皇极殿 · {"东" if sign>0 else "西"}正吻十一拼')


def roofwork(env, rear, group, p):
    loc = env.loc
    if rear:
        swept_roof('宁寿宫 · 黄琉璃单檐歇山',group,p,origin=loc.world(),yaw=loc.yaw,width=env.width,depth=env.depth,
                   eave=7.10,rise=4.22,kind='xieshan',tiles=True,detail=2,pitch=.245,beasts=7,
                   ridge_length=.735*env.width,eave_lift=.51,terminal_height=1.63)
        return
    opening=(env.width*.814,env.depth*.672)
    swept_roof('皇极殿 · 下檐四坡腰檐',group,p,origin=loc.world(),yaw=loc.yaw,width=env.width,depth=env.depth,
               eave=MAIN_EAVE,rise=2.13,kind='hip',upper_rectangle=opening,
               pitch=.244,beasts=9,tiles=True,detail=2,eave_lift=.56,sculpted=True)
    top=swept_roof('皇极殿 · 上檐庑殿四坡',group,p,origin=loc.world(),yaw=loc.yaw,
                   width=env.width*.884,depth=env.depth*.816,eave=MAIN_UPPER,rise=RIDGE_BASE-MAIN_UPPER,
                   kind='hip',pitch=.251,beasts=9,tiles=True,detail=2,eave_lift=.83,sculpted=True,
                   ridge_length=env.width*.61,ridge_terminals=False)
    terminal_pair(env,top,p)
    waist, rail = loc.batch(), loc.batch()
    wx,wy = (d*.5 for d in opening)
    for sx in (-1,1):
        waist.box((sx*(wx-.13),0,10.3),(.28,2*wy,2.25),p.fascia)
        waist.box((0,sx*(wy-.145),10.3),(2*wx-.25,.29,2.25),p.fascia)
        upper_bays=tuple(x*.883 for x in MAIN_X)
        for a,c in zip(upper_bays,upper_bays[1:]):
            painted_bay(rail,(a+c)/2,sx*(wy+.019),10.27,c-a-.015,p,height=.78)
            if sx<0:
                xx=(a+c)/2; ww=(c-a)*.65; z=10.286; y=-wy-.182
                rail.face(((xx-ww/2,y,z-.258),(xx+ww/2,y,z-.258),(xx+ww/2,y,z+.258),(xx-ww/2,y,z+.258)),
                          image_surface('huangji_eave_paint'),uv=((0,0),(1,0),(1,1),(0,1)))
                frame(rail,xx,y-.005,z,ww+.024,.534,.018,p.cream)
            for j in range(5):
                bracket(rail,a+(j+.5)*(c-a)/5,sx*(wy+.095),10.73,.72,p,7,0 if sx<0 else math.pi)
        for j in range(11):
            yy=(j-5)*1.46
            bracket(rail,sx*wx,yy,10.73,.71,p,7,math.pi/2 if sx>0 else -math.pi/2)
    waist.finish('皇极殿 · 重檐间围合大木',group)
    inscription(rail,0,-wy-.264,10.42,1.26,1.82,p,'huangji_eave_face')
    rail.finish('皇极殿 · 上檐七踩斗科和双语匾额',group,bevel=.003)


def bracket(b, x, y, z, scale, p, courses, yaw):
    """Layered blocks and projecting, swept gong arms; sectional sizes inferred."""
    t=Batch()
    t.box((0,0,z+.057*scale),(.34*scale,.34*scale,.114*scale),p.faded_teal)
    for i in range(courses):
        h=z+scale*(.132+i*.090)
        out=i*.107*scale
        w=scale*(.152+.024*i)
        profile=Polygon(((-w*.61,h-.016), (w*.61,h-.016), (w*.88,h+.018), (w,h+.050*scale),
                         (-w,h+.050*scale),(-w*.88,h+.018)))
        arm=Batch()
        arch_mesh(arm,profile,scale*.152,p.faded_teal if i%2==0 else p.faded_blue)
        transfer(t,arm,0,-out,0)
        t.beam((0,.50*scale,h+.04),(0,-out-.123*scale,h+.055),.115*scale,.095*scale,p.faded_teal)
        t.rod((-w,-out-.079*scale,h+.027),(w,-out-.079*scale,h+.027),.007*scale,p.giltpaint,sides=6)
    transfer(b,t,x,y,yaw)


def rail_cut(b, shape, y, thick, material):
    part=Batch(); arch_mesh(part,shape,thick,material); transfer(b,part,0,y,0)


def eave_joinery(env, rear, target, p):
    loc=env.loc
    post, beam, trim = (loc.batch() for _ in range(3))
    xs,ys,eave=(REAR_X,REAR_Y,7.10) if rear else (MAIN_X,MAIN_Y,MAIN_EAVE)
    yd=ys[0]
    label='宁寿宫' if rear else '皇极殿'
    for x in xs:
        for y in (ys[0],ys[-1]):
            column(post,x,y,DECK,eave-.94,.255 if rear else .34,p)
    for x in (xs[0],xs[-1]):
        for y in ys[1:-1]:
            column(post,x,y,DECK,eave-.94,.252 if rear else .325,p)
    inside=[(x,ys[1]) for x in xs[1:-1]]
    if not rear:
        inside += [(x,y) for x in (xs[1],xs[3],xs[6],xs[-2]) for y in (ys[2],ys[3],ys[4])]
    for x,y in inside:
        column(post,x,y,DECK,8.92 if not rear else 6.14,.34 if not rear else .246,p)
    post.finish(label+' · 檐柱、内柱与石柱础',target,
                properties={'width_axis_coordinates_m':list(xs),'depth_axis_coordinates_m':list(ys),'source_kind':'proportions inferred'})
    for y,sgn in ((yd,-1),(ys[-1],1)):
        for a,c in zip(xs,xs[1:]):
            span=c-a
            painted_bay(beam,(a+c)/2,y,eave-1.32,span-.035,p,height=.57)
            beam.box(((a+c)/2,y,eave-.913),(span-.022,.434,.226),p.fascia)
            for j in range(7):
                xx=a+(j+.5)*span/7
                bracket(trim,xx,y,eave-.864,.83 if rear else .91,p,4 if rear else 5,0 if sgn<0 else math.pi)
            if y==yd:
                for side in (-1,1):
                    xx=(a if side<0 else c)-side*.64
                    cloud(trim,(xx,y-.233,eave-1.74),.88,p.old_gold,rotation=math.pi*.14*side)
                    dragon(trim,(xx+side*.10,y-.225,eave-1.69),.98,.41,p,mirror=side>0,z_relief=.023,detailed=False)
    for side in (-1,1):
        x=xs[0] if side<0 else xs[-1]
        for a,c in zip(ys,ys[1:]):
            yaw=side*math.pi/2
            painted_bay(beam,x,(a+c)/2,eave-1.31,c-a-.034,p,yaw=yaw,height=.545)
            for j in range(5):
                bracket(trim,x,a+(j+.5)*(c-a)/5,eave-.858,.82,p,4 if rear else 5,yaw)
    for x in xs:
        beam.beam((x,ys[0],eave-1.09),(x,ys[-1],eave-1.09),.265,.359,p.fascia)
    if rear:
        # The later secondary supports surround the original column line.
        for y in (ys[0]-.318,ys[-1]+.318):
            for a,c in zip(xs,xs[1:]):
                column(trim,(a+c)/2,y,DECK,eave-.99,.144,p)
        for side in (-1,1):
            for j in range(7):
                y=ys[0]+(j+.5)*(ys[-1]-ys[0])/7
                column(trim,side*(xs[-1]+.34),y,DECK,eave-.99,.144,p)
    beam.finish(label+' · 彩画大额枋与进深梁',target,bevel=.007)
    trim.finish(label+' · 飞檐斗栱、描金雀替与擎檐构件',target,bevel=.003)


def diamond_leaf(b,w,z,h,p,*,small=False):
    b.box((0,0,z+h*.12),(w-.015,.105,h*.24),p.lacquer)
    frame(b,0,-.052,z+h*.120,w-.072,h*.212,.021,p.old_gold)
    for sign in (-1,1):
        b.box((sign*(w/2-.044),0,z+h/2),(.086,.124,h),p.lacquer)
        b.box((sign*(w/2-.078),-.069,z+h/2),(.031,.021,h-.036),p.giltpaint)
        b.box((sign*(w/2-.025),-.065,z+h/2),(.020,.016,h-.037),p.old_gold)
    for t in (.018,.255,.885,.982):
        b.box((0,0,z+t*h),(w,.119,.072),p.lacquer)
        b.box((0,-.065,z+t*h),(w-.044,.036,.036),p.giltpaint)
    lattice(b,0,-.007,z+.273*h,w-.169,.595*h,SimpleNamespace(red=p.giltpaint),pitch=.126,radius=.009)
    med_w,med_h=w*.350,h*.101
    zz=z+h*.12
    b.path([(med_w*math.cos(a),-.070,zz+med_h*math.sin(a)) for a in (i*math.tau/48 for i in range(49))],
           .017,p.gold,sides=9)
    if not small:
        for side in (-1,1):
            dragon(b,(side*med_w*.43,-.075,zz),med_w*.88,med_h*1.45,p,mirror=side<0,detailed=True,z_relief=.016)
            for i in range(3):
                cloud(b,(side*(i+.27)*med_w*.24,-.086,zz+(i-1)*med_h*.49),med_w*.35,p.old_gold,rotation=side*i*.91)
    for s in (-1,1):
        for k in (-1,1):
            cloud(b,(s*w*.345,-.063,zz+k*h*.066),h*.042,p.old_gold,rotation=s*k*1.39)


def shutters(env,rear,target,p):
    loc=env.loc
    xs,ys=(REAR_X,REAR_Y) if rear else (MAIN_X,MAIN_Y)
    label='宁寿宫' if rear else '皇极殿'
    geometry, wall, gilding = (loc.batch() for _ in range(3))
    front_y,back_y=ys[1],ys[-1]
    open_front=4
    group=collection(label+' · 可编辑槅扇、槛墙及亮子',target)
    for i,(a,c) in enumerate(zip(xs,xs[1:])):
        w=c-a-.49; x=(a+c)/2
        h=3.77 if rear else 4.34
        z=DECK+.067
        base=z
        if rear and i!=open_front or not rear and i not in (3,4,5):
            dado=.82 if rear else .75
            wall.box((x,front_y,z+dado/2),(w,.278,dado),p.old_wall)
            wall.box((x,front_y,z+dado),(w+.061,.332,.110),p.fascia)
            if not rear:
                turtle_dado(gilding,x,front_y-.155,z+.098,w-.131,dado-.19,p)
            h-=dado; base+=dado
        width=w/4
        if rear and i==open_front:
            for s in (-1,1):
                xx=x+s*1.39
                geometry.box((xx,front_y,base+h*.42),(w/2-.05,.135,h*.84),p.lacquer)
            for s in (-1,1):
                geometry.ellipsoid((x+s*.155,front_y-.084,base+1.64),(.065,.033,.068),p.old_gold,sides=16,rings=8)
        else:
            for j in range(4):
                xx=x+(j-1.5)*width
                if not rear and i==open_front and j in (1,2):
                    s=-1 if j==1 else 1
                    hinge=xx+s*(width-.016)/2
                    ang=-s*math.radians(91)
                    leaf=Batch()
                    diamond_leaf(leaf,width-.023,base,h,p)
                    leaf.v=[(u-s*(width-.016)/2,v,z) for u,v,z in leaf.v]
                    posed=loc.batch()
                    transfer(posed,leaf,hinge,front_y+.052,ang)
                    posed.finish(f'皇极殿 · 明间开启槅扇 {j}',group,bevel=.003,
                                 properties={'portal':'front_central','hinge_local_xy_m':[hinge,front_y+.052],'virtual_pose':True})
                elif rear:
                    w0=width-.031
                    frame(geometry,xx,front_y,z+(base-z)+h/2,w0,h,.056,p.red)
                    for k in range(1,12):
                        xx0=xx+(k/12-.5)*(w0-.065)
                        geometry.box((xx0,front_y,base+h/2),(.019,.063,h-.083),p.red)
                    for u in (.20,.52,.82):
                        geometry.box((xx,front_y,base+h*u),(w0-.071,.060,.041),p.fascia)
                else:
                    leaf=Batch(); diamond_leaf(leaf,width-.023,base,h,p,small=i in (0,1,7,8))
                    transfer(geometry,leaf,xx,front_y,0)
        transom=DECK+(4.10 if rear else 4.64)
        for n in (-1,0,1):
            xx=x+n*w/3
            frame(geometry,xx,front_y,transom,w/3-.017,.394,.036,p.giltpaint)
            lattice(geometry,xx,front_y+.014,transom-.166,w/3-.085,.333,SimpleNamespace(red=p.fascia))
        wall.box((x,front_y+.002,transom+.31),(w+.266,.241,.25),p.fascia)
        wall.box((x,front_y-.012,DECK+.041),(w,.242,.082),p.understone)
        if i not in ((2,3,4) if rear else (3,4,5)):
            wall.box((x,back_y,DECK+2.30),(w+.40,.37,4.60),p.old_wall)
        else:
            for j in range(4):
                leaf=Batch(); diamond_leaf(leaf,w/4-.021,z,4.30,p,small=True)
                transfer(geometry,leaf,x+(j-1.5)*w/4,back_y,math.pi)
            wall.box((x,back_y,DECK+4.49),(w+.25,.264,.222),p.fascia)
    attic_gap=loc.batch()
    for sign in (-1,1):
        xx=xs[0] if sign<0 else xs[-1]
        wall.box((xx,(ys[1]+ys[-1])/2,DECK+2.56),(.423,ys[-1]-ys[1],5.12),p.old_wall)
        wall.box((xx,(ys[1]+ys[-1])/2,DECK+.301),(.513,ys[-1]-ys[1]+.066,.59),p.lightjade)
    if not rear:
        for yi in (ys[1],ys[-1]):
            for lo,hi in ((xs[0],-9.12),(9.12,xs[-1])):
                attic_gap.box(((lo+hi)/2,yi+.125,DECK+4.637),(hi-lo+.053,.25,.743),p.fascia)
                for dz,mat in ((-.191,p.faded_blue),(.015,p.faded_teal)):
                    attic_gap.box(((lo+hi)/2,yi-.006,DECK+4.637+dz),(hi-lo+.05,.043,.066),mat)
        attic_gap.finish('皇极殿 · 侧间梁后连续暗枋',group)
        closure=loc.batch()
        for yi in (ys[1],ys[-1]):
            # Raised middle bays meet the ceiling through solid lintels. The
            # lower side bays already have their individual continuous beams.
            for lo,hi in ((-9.13,-3.10),(3.10,9.13)):
                closure.box(((lo+hi)/2,yi+.165,7.465),(hi-lo,.314,2.79),p.fascia)
                for zz,mat in ((6.215,p.faded_teal),(6.327,p.faded_blue),(8.635,p.faded_teal)):
                    closure.box(((lo+hi)/2,yi-.016,zz),(hi-lo,.052,.116),mat)
            # The central lintel is above the visitor opening and remains solid.
            closure.box((0,yi+.165,7.71),(6.22,.314,2.30),p.fascia)
        closure.finish('皇极殿 · 高明间后檐梁与天花封接',group,
                       properties={'role':'interior_eave_closure','section_evidence':'Photographic enclosure; section depth inferred.'})
    geometry.finish(label+' · 榫棂、剪边、槅扇及窗扇',group,bevel=.003)
    wall.finish(label+' · 槛墙、山墙和抱框',group)
    if rear:
        inscription(gilding,0,ys[0]-.253,6.71,1.25,1.66,p,'ning_shou_eave_face')
    gilding.finish(label+' · 琉璃龟锦和檐下题署',group)


def turtle_dado(b,x,y,z,w,h,p):
    for row in range(max(1,int(h/.115))):
        zz=z+.058+row*.115
        for col in range(int(w/.13)):
            xx=x-w*.5+.067+(col+.5*(row%2))*.13
            if abs(xx-x)>w/2-.05:
                continue
            for radius,mat in ((.058,p.glaze_yellow),(.044,p.green_clay)):
                b.path([(xx+radius*math.cos(a),y,zz+radius*math.sin(a)) for a in (i*math.tau/6 for i in range(7))],
                       .0058,mat,sides=5)
            b.ellipsoid((xx,y+.002,zz),(.037,.010,.036),p.green_clay,sides=7,rings=4)


def rear_parapet(main,rear,target,p):
    b=main.loc.batch()
    shape=main.loc.local(LineString([rear.loc.world()[:2],rear.loc.world(0,1)[:2]]))
    y=shape.coords[0][1]
    # Alternating hollow glazed lattice, never a green/yellow painted slab.
    plan=[((-23.37,y-12.43),(-3.48,y-12.43)),((3.48,y-12.43),(25.67,y-12.43)),
          ((-23.44,y-12.50),(-23.20,y+10.64)),((25.68,y-12.47),(25.84,y+10.61)),
          ((-23.20,y+10.64),(25.84,y+10.61))]
    for a,c in plan:
        length=math.dist(a,c); t=math.atan2(c[1]-a[1],c[0]-a[0]); small=Batch()
        small.box((length*.5,0,DECK+.050),(length,.312,.111),p.stone)
        small.box((length*.5,0,DECK+.711),(length,.285,.082),p.glaze_yellow)
        for j in range(4):
            for i in range(math.ceil(length/.36)):
                xx=(i+.40+.5*(j%2))*.36
                if xx>length-.16:
                    break
                small.box((xx,0,DECK+.185+j*.139),(.273,.192,.130),p.glaze_yellow if (i+j)%2 else p.green_clay)
                if j%2==0:
                    small.box((xx+.154,0,DECK+.241+j*.139),(.065,.193,.101),p.green_clay)
        for j in range(math.ceil(length/2.31)+1):
            xx=min(j*2.31,length)
            small.box((xx,0,DECK+.385),(.179,.302,.764),p.stone)
        transfer(b,small,*a,t)
    b.finish('宁寿宫 · 黄绿透风灯笼砖槛',target,bevel=.004,
             properties={'masonry':'open yellow-green glazed alternating courses','source':REAR_SOURCE})


def range_build(name, target, loc, width, depth, p, *, bays=9, openings=(), deck=.26, eave=4.02, rise=1.86,
                hip=False, back=True, ref=None):
    group=collection(name,target)
    u=width/2; vy=-depth/2+.73; iy=vy+min(1.64,depth*.25)
    stone, wall, timber, join = (loc.batch() for _ in range(4))
    stone.box((0,0,deck*.5),(width-.29,depth-.48,deck),p.understone)
    laid_pavers(stone,box(-u+.18,-depth/2+.23,u-.18,iy+.39),deck+.006,p,course=.70,width=1.06)
    xp=tuple(-u+.47+(width-.94)*i/bays for i in range(bays+1))
    if back:
        wall.box((0,depth/2-.58,(eave+deck-.46)/2),(width-.43,.412,eave-deck-.46),p.old_wall)
    for sign in (-1,1):
        wall.box((sign*(u-.32),(.43+iy+depth/2)/2,(eave+deck-.45)/2),(.30,depth/2-iy-.43,eave-deck-.45),p.old_wall)
    for i,x in enumerate(xp):
        column(timber,x,vy,deck,eave-.66,.172,p)
        column(timber,x,iy,deck,eave-.59,.145,p)
        timber.beam((x,vy,eave-.72),(x,depth/2-.60,eave-.72),.225,.255,p.fascia)
        if i==bays:
            break
        a,c=x,xp[i+1]; xx=(a+c)/2; w=c-a-.29
        painted_bay(join,xx,vy,eave-.88,w+.22,p,height=.406)
        if i+1 in openings:
            for sign in (-1,1):
                join.box((xx+sign*(w/2-.10),iy,deck+1.362),(.120,.20,2.73),p.lacquer)
            join.box((xx,iy,deck+2.79),(w+.09,.188,.265),p.lacquer)
            wall.box((xx,iy+.15,deck+3.11),(w+.13,.17,.55),p.fascia)
            stone_step_run(stone,(xx,vy-1.57),(xx,vy-.02),min(2.65,w),.022,deck,p,count=2 if deck<.4 else 4)
            continue
        wall.box((xx,iy,deck+.325),(w,.253,.65),p.old_wall)
        wall.box((xx,iy,deck+.639),(w+.061,.329,.116),p.fascia)
        for j in range(3):
            x0=xx+(j-1)*w/3
            frame(join,x0,iy-.109,deck+1.553,w/3-.019,1.61,.045,p.lacquer)
            for k in range(1,9):
                wx=x0+(k/9-.5)*(w/3-.12)
                join.box((wx,iy-.127,deck+1.56),(.019,.054,1.53),p.door)
            for zz in (.94,1.37,1.81,2.21):
                join.box((x0,iy-.134,deck+zz),(w/3-.102,.042,.023),p.lacquer)
            frame(join,x0,iy-.101,deck+2.557,w/3-.021,.34,.026,p.faded_teal)
    properties={'bays':bays,'open_local_bay_indices':list(openings),'section_dimensions_inferred':True}
    if ref: properties['source_osm_id']=ref
    stone.finish(name+' · 阶沿、廊地和门踏跺',group)
    timber.finish(name+' · 庑廊柱与承檐梁',group,properties=properties)
    join.finish(name+' · 格窗、门框和连檐彩画',group)
    wall.finish(name+' · 台脚以上砖木围护',group)
    swept_roof(name+' · 琉璃瓦面',group,p,origin=loc.world(),yaw=loc.yaw,width=width,depth=depth,
               eave=eave,rise=rise,kind='xieshan' if hip else 'gable',tiles=True,pitch=.257,detail=1,
               eave_lift=.22 if hip else None,beasts=3 if hip else 0,ridge_terminals=hip,terminal_height=.69)
    return group


def surrounding_ranges(site,main,target,p):
    group=collection('两殿周边 · 东西庑、门楼及转角',target)
    m=main.loc
    for side,ref in ((-1,'40592360'),(1,'40592361')):
        label='东庑 · 凝祺门' if side>0 else '西庑 · 昌泽门'
        geo=local_shape(site.geom(ref),m)
        x0,y0,x1,y1=geo.bounds
        # Cut the L at the surveyed return rather than filling its bounding box.
        shoulder=29.12 if side>0 else 28.95
        x_out=geo.intersection(LineString([(x0-1,0),(x1+1,0)])).bounds[2 if side>0 else 0]
        inner_edge=34.52 if side>0 else -34.59
        cx=(x_out+inner_edge)/2; end=shoulder+.42
        loc=Location(*m.world(cx,(y0+end)/2)[:2],m.yaw+(math.pi/2 if side<0 else -math.pi/2))
        range_build(label,group,loc,end-y0,abs(x_out-inner_edge),p,openings=(3,6) if side<0 else (4,7),ref=ref,back=False)
        rear_edge=25.18 if side>0 else -23.05
        return_loc=Location(*m.world((x_out+rear_edge)/2,(shoulder+y1)/2)[:2],m.yaw)
        range_build(('东' if side>0 else '西')+'庑回折廊',group,return_loc,abs(x_out-rear_edge),y1-shoulder,p,
                    bays=3,openings=(1 if side>0 else 3,),eave=3.99,rise=1.80,ref=ref)
    for ref in FLANKS:
        if ref in ('40592360','40592361'):
            continue
        g=local_shape(site.geom(ref),m)
        x0,y0,x1,y1=g.bounds
        label='东转角庑房' if ref in ('40592358','40592362') else '西转角庑房'
        if ref in ('40592358','40592359'):
            c=g.centroid
            loc=Location(*m.world(c.x,c.y)[:2],m.yaw+(math.pi/2 if c.x<0 else -math.pi/2))
            range_build(label,group,loc,y1-y0,x1-x0,p,bays=3,openings=(2,),hip=True,eave=4.35,rise=2.68,ref=ref)
        else:
            mid=next(y for y in sorted({round(y,2) for _,y in g.exterior.coords}) if y0+4<y<y1-3)
            bottom=g.intersection(box(x0-1,y0-1,x1+1,mid))
            arm=g.intersection(box(x0-1,mid,x1+1,y1+1))
            for i,part in enumerate((bottom,arm)):
                a,b,c,d=part.bounds
                loc=Location(*m.world((a+c)/2,(b+d)/2)[:2],m.yaw+(math.pi/2 if i and c<0 else -math.pi/2 if i else math.pi))
                range_build(label+(' · 西东连廊' if not i else ' · 南北连廊'),group,loc,d-b if i else c-a,
                            c-a if i else d-b,p,bays=3 if i else 5,openings=(2,) if i else (3,),ref=ref)
    for side,ref in zip((-1,1),CROSS_GATES):
        env=Envelope.from_way(site,ref)
        name=('西' if side<0 else '东')+'垂花门'
        range_build(name,group,env.loc,env.width,env.depth,p,bays=3,openings=(2,),deck=.34,eave=4.24,rise=1.23,
                    hip=False,back=False,ref=ref)
        trim=env.loc.batch()
        for x in (-env.width*.183,env.width*.183):
            yy=-env.depth*.40
            trim.lathe(x,yy,((.038,3.12),(.119,3.15),(.150,3.25),(.101,3.38),(.069,3.42),(.106,3.73)),p.faded_teal,sides=18)
            for i in range(8):
                a=i*math.tau/8
                trim.path([(x+r*math.cos(a),yy+r*math.sin(a),z) for r,z in ((.053,3.151),(.148,3.247),(.075,3.346))],
                          .012,p.giltpaint,sides=7)
        trim.finish(name+' · 垂莲柱头',group)
    return group


def terrace_objects(main,target,p):
    loc=main.loc
    group=collection('皇极殿月台 · 日晷、嘉量、灯座和铜缸',target)
    def pedestal(b,x,y,z,r):
        b.lathe(x,y,tuple((r*a,z+b) for a,b in ((1,0),(.98,.091),(.85,.153),(.66,.204),(.71,.438),
                                                   (.94,.517),(.98,.571),(1.015,.628))),p.stone,sides=32)
    b=loc.batch(); pedestal(b,-6.43,-20.75,DECK,.55)
    dial=Vector((-6.43,-20.75,DECK+1.13)); perpendicular=Vector((0,-.637,.771))
    b.rod(dial-perpendicular*.065,dial+perpendicular*.045,.56,p.stone,sides=92)
    b.rod(dial+perpendicular*.045,dial+perpendicular*.58,.016,p.bronze,r1=.009,sides=14)
    b.beam((-6.43,-20.75,DECK+.55),dial,.29,.36,p.stone)
    a=Vector((1,0,0)); c=perpendicular.cross(a)
    for i in range(96):
        t=i*math.tau/96; u=(a*math.cos(t)+c*math.sin(t))
        b.rod(dial+perpendicular*.047+u*.495,dial+perpendicular*.047+u*(.446 if i%8==0 else .471),.004,p.understone,sides=6)
    b.finish('皇极殿 · 石日晷、晷针和刻度',group,properties={'documented_subject':'sundial','sculpture_inferred':True})
    b=loc.batch(); pedestal(b,6.43,-20.75,DECK,.55)
    x,y=6.43,-20.75; z=DECK+.632
    b.lathe(x,y,((.254,z),(.282,z+.092),(.303,z+.328),(.317,z+.351),(.309,z+.369),(.264,z+.369),(.249,z+.107)),p.bronze,sides=68)
    for sx in (-1,1):
        b.rod((x+sx*.20,y,z+.102),(x+sx*.49,y,z+.112),.083,p.bronze,sides=16)
        b.rod((x+sx*.48,y,z+.112),(x+sx*.50,y,z+.298),.089,p.bronze,r1=.092,sides=16)
    b.finish('皇极殿 · 铜嘉量、容器内壁和石座',group,properties={'documented_subject':'jia liang','sculpture_inferred':True})
    for i,side in enumerate((-1,1)):
        b=loc.batch(); x=side*4.57; y=-31.84
        b.lathe(x,y,((.52,.026),(.53,.123),(.459,.186),(.344,.374),(.460,.463),(.511,.534),(.513,.583),(.103,.583),(.090,.516)),
                p.stone,sides=6)
        b.lathe(x,y,((.090,.512),(.100,.542),(.108,.584),(.068,.585),(.054,.488)),p.bronze,sides=30)
        for j in range(12):
            a=j*math.tau/12
            b.ellipsoid((x+.442*math.cos(a),y+.442*math.sin(a),.199),(.062,.062,.038),p.stone,sides=12,rings=6)
        b.finish('皇极殿 · 六方灯杆旧石座 '+str(i+1),group,properties={'documented_subject':'hexagonal lamp base only'})
    for i,(x,y) in enumerate(((-29.1,-34.6),(28.7,-36.0),(-28.4,-12.1),(28.3,-12.4))):
        b=loc.batch(); z=.025
        b.lathe(x,y,((.56,z),(.55,z+.15),(.49,z+.22)),p.understone,sides=48)
        b.lathe(x,y,((.265,.24),(.341,.28),(.441,.48),(.505,.766),(.521,.905),(.549,.924),(.55,.964),
                     (.514,.979),(.489,.947),(.471,.806),(.336,.480),(.237,.309)),p.bronze,sides=64)
        for k in (-1,1):
            b.ellipsoid((x+k*.495,y,.758),(.045,.091,.087),p.bronze,sides=15,rings=10)
            b.path([(x+k*.54,y+.073*math.cos(a),.709+.074*math.sin(a)) for a in (i*math.tau/26 for i in range(27))],
                   .012,p.bronze,sides=8)
        b.finish('两殿院内 · 铜水缸与耳环 '+str(i+1),group,properties={'position_evidence':'partial exterior photographs and inferred repetitions'})


def build_shell(site, target, base):
    p=palette(base)
    main,rear=(Envelope.from_way(site,ref) for ref in (MAIN_ID,REAR_ID))
    metrics=courtyard(site,main,rear,target,p)
    groups=[]
    for env,is_rear,label,ref,source in ((main,False,'皇极殿',MAIN_ID,MAIN_SOURCE),(rear,True,'宁寿宫后殿',REAR_ID,REAR_SOURCE)):
        group=collection(label+' · 木构本体、歇山' if is_rear else label+' · 重檐庑殿与九间殿身',target)
        group['source_osm_id']=ref; group['museum_source']=source
        groups.append(group)
        eave_joinery(env,is_rear,group,p)
        shutters(env,is_rear,group,p)
        roofwork(env,is_rear,group,p)
        floor=env.loc.batch()
        ys=REAR_Y if is_rear else MAIN_Y; xs=REAR_X if is_rear else MAIN_X
        laid_pavers(floor,box(xs[0]+.02,ys[1]+.052,xs[-1]-.02,ys[-1]-.062),DECK+.011,
                    SimpleNamespace(terrace_floor=p.goldbrick),course=.63,width=.63)
        floor.finish(label+' · 逐块磨光地面金砖',group)
    rear_parapet(main,rear,target,p)
    surrounding_ranges(site,main,target,p)
    terrace_objects(main,target,p)
    return main,rear,groups,p,metrics
