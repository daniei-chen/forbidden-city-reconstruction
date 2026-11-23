"""Reference-led, fully modeled roof sculpture, with separately editable parts.

Taihe chiwen envelope: 3.46 H x 2.68 W x .52 T metres, measured by Wang
Wentao, Palace Museum article 浅析紫禁城建筑上的琉璃吻, pp.011–013.
Silhouette, relief, manufacturing joints and guardian sculpture are authored
from the accompanying photographs, not measured conservation meshes.
"""
import math
from mathutils import Vector
from shapely.geometry import Polygon
from mesh_tools import Batch, collection

ORDER=('龙','凤','狮子','天马','海马','狻猊','押鱼','獬豸','斗牛','行什')
CHI_SOURCE='https://www.dpm.org.cn/Uploads/File/2020/04/28/u5ea7f1abc452d.pdf'
GUARD_SOURCE='https://img.dpm.org.cn/Uploads/File/2018/06/04/u5b1530b6437db.pdf'


def profile(batch,outline,thickness,material):
    """Welded shaped ceramic body; XZ silhouette, Y is physical thickness."""
    # Rounded ceramic corners, not a low-sided straight polygon extrusion.
    smooth=Polygon(outline).buffer(0).buffer(.028,quad_segs=6,join_style=1).buffer(-.028,quad_segs=6,join_style=1)
    temp=Batch();temp.solid_welded(smooth,-thickness/2,thickness/2,material)
    batch.add([(x,y,z) for x,z,y in temp.v],temp.f,material)


def spiral(batch,point,radius,material,*,side=-1.,turns=1.25,tube=.012):
    x,y,z=point
    points=[]
    for i in range(49):
        t=i/48;a=t*math.tau*turns
        r=radius*(.15+.85*t)
        points.append((x+r*math.cos(a),y+side*.003*math.sin(a),z+r*math.sin(a)))
    batch.path(points,tube,material,sides=7)


def scale_field(batch,shape,y,material,*,pitch=.14,radius=.068,side=1):
    """Each overlapping fish scale is an actual shallow crescent mesh."""
    from shapely.geometry import Point
    x0,z0,x1,z1=shape.bounds
    row=0;z=z0+pitch*.50
    while z<z1:
        x=x0+pitch*.5+(row%2)*pitch*.5
        while x<x1:
            if shape.buffer(-radius*.85).covers(Point(x,z)):
                points=[]
                for k in range(13):
                    a=math.pi*k/12
                    points.append((x+radius*math.cos(a),y+side*(.004+.010*math.sin(a)),z-radius*.70*math.sin(a)))
                batch.path(points,.0085,material,sides=5)
            x+=pitch
        row+=1;z+=pitch*.68


def chiwen(target,pal,*,origin,yaw=0.,end=1,height=3.46,width=2.68,thickness=.52,label='正吻'):
    """16 editable ceramic assemblies inside the independently cited envelope."""
    group=collection(label,target)
    parts=[Batch() for _ in range(16)]
    clay=pal.tiles[2];deep=pal.darktile;gold=pal.giltpaint
    body=[(-.36,.08),(1.17,.08),(1.20,.35),(1.12,.78),(1.08,1.12),
          (1.12,1.45),(.91,1.78),(.63,1.96),(.30,2.01),(.09,1.91),
          (-.04,1.55),(-.34,1.32),(-.40,.98),(-.25,.58)]
    # Three dimensional moulding underneath the jointed sculpture.
    profile(parts[14],[(-.56,0),(1.25,0),(1.25,.17),(-.56,.17)],.49,clay)
    for level in (.03,.13):
        parts[14].box((.34,0,level),(1.89,.54,.045),gold)
    profile(parts[7],body,.40,clay)
    # Open jaws facing inwards and swallowing the central ridge.
    head=[(-.33,.80),(-.69,.80),(-1.27,.83),(-1.34,1.04),(-1.18,1.18),
          (-1.18,1.39),(-.97,1.54),(-.64,1.55),(-.27,1.39),(-.16,1.08)]
    profile(parts[10],head,.48,clay)
    jaw=[(-1.22,.22),(-.87,.16),(-.39,.20),(-.28,.41),(-.49,.59),(-.74,.52),(-1.23,.53)]
    profile(parts[8],jaw,.45,clay)
    # A recessed mouth backing leaves real empty space between the lips.
    parts[8].box((-.80,.10,.67),(.72,.05,.24),deep)
    for sy in (-1,1):
        yy=sy*.235
        parts[10].ellipsoid((-.89,yy,1.28),(.245,.082,.18),clay,sides=22,rings=12)
        parts[10].ellipsoid((-.92,sy*.302,1.30),(.095,.020,.105),deep,sides=18,rings=10)
        parts[10].path([(-1.14,sy*.27,1.48),(-.93,sy*.29,1.54),(-.68,sy*.24,1.49)],.037,clay,sides=9)
        # Individual teeth and lower fangs, with a visible mouth slit.
        for i in range(6):
            xx=-1.23+i*.115
            parts[10].rod((xx,sy*.20,.84),(xx+.018,sy*.20,.69),.035,clay,r1=.011,sides=9)
            parts[8].rod((xx,sy*.19,.49),(xx+.018,sy*.19,.59),.028,clay,r1=.009,sides=8)
        parts[10].path([(-1.15,yy,1.39),(-1.34,yy,1.46),(-1.30,yy,1.67),(-1.17,yy,1.70)],.047,clay,sides=9)
        for i in range(5):
            spiral(parts[5],(-.45+i*.27,sy*.224,.91+i*.055),.16-i*.012,clay,side=sy,tube=.023)
        parts[12].path([(.68,sy*.19,.91),(.88,sy*.24,.63),(.81,sy*.30,.35)],.045,clay,sides=10)
        for toe in range(4):
            parts[12].path([(.81,sy*.30,.35),(.73+toe*.077,sy*.31,.23),
                            (.70+toe*.080,sy*.32,.19)],.021,clay,sides=7)
        # Horns are fired separately and lean behind the eyebrow.
        parts[9].path([(-.48,sy*.16,1.53),(-.41,sy*.23,1.75),
                       (-.50,sy*.25,1.98),(-.67,sy*.23,2.02)],.041,clay,sides=10)
    # Fish-tail back, curled top and a raised rolled rim on both faces.
    tail=[(-.09,1.71),(-.39,1.93),(-.72,2.22),(-.81,2.62),(-.72,2.95),
          (-.48,3.16),(-.15,3.20),(.14,3.04),(.27,2.76),(.20,2.49),
          (.02,2.34),(-.20,2.38),(-.30,2.54),(-.26,2.72),(-.11,2.81),
          (.00,2.75),(-.01,2.62),(-.10,2.59),(.11,2.45),(.40,2.32),(.60,2.03)]
    profile(parts[0],tail,.34,clay)
    for sy in (-1,1):
        parts[0].path([(x,sy*.195,z) for x,z in tail[:-4]],.038,clay,sides=10)
        scale_field(parts[0],Polygon(tail).buffer(0),sy*.177,clay,pitch=.125,radius=.060,side=sy)
        scale_field(parts[7],Polygon(body),sy*.212,clay,pitch=.15,radius=.068,side=sy)
    # The sixteen assemblies correspond to 13 jointed main sections, sword
    # sections and lower mounting. Exact conservation joint surfaces are inferred.
    for section,z0 in ((3,1.43),(4,1.72),(6,1.07),(11,.63),(13,.32)):
        for sy in (-1,1):
            parts[section].path([(-.21,sy*.219,z0),(.29,sy*.223,z0-.025),(.82,sy*.220,z0+.015)],.009,deep,sides=5)
            for xx in (.14,.71):
                parts[section].path([(xx-.025,sy*.235,z0-.03),(xx-.025,sy*.25,z0+.036),
                                     (xx+.026,sy*.25,z0+.036),(xx+.026,sy*.235,z0-.03)],.008,gold,sides=6)
    # Upright sword: stalk, five cloud heads and the high central tip.
    profile(parts[2],[(.26,1.86),(.54,1.86),(.57,2.83),(.20,2.83)],.23,clay)
    crown=[(-.05,2.79),(-.08,3.06),(.01,3.20),(.15,3.22),(.18,3.36),
           (.29,3.46),(.42,3.36),(.46,3.25),(.60,3.23),(.67,3.11),(.68,2.79)]
    profile(parts[1],crown,.25,clay)
    for sy in (-1,1):
        for xx,zz,rr in ((.02,3.10,.11),(.23,3.27,.12),(.44,3.15,.11),(.59,3.06,.085)):
            spiral(parts[1],(xx,sy*.145,zz),rr,clay,side=sy,tube=.017)
        for xx in (.25,.42):
            parts[2].path([(xx,sy*.13,1.91),(xx,sy*.14,2.90)],.014,gold,sides=6)
    # A second small dragon crosses the body beneath the sword.
    for sy in (-1,1):
        small=[(-.28,sy*.23,1.85),(-.02,sy*.27,1.72),(.35,sy*.29,1.81),(.58,sy*.23,1.98)]
        parts[4].path(small,.065,clay,sides=11)
        parts[3].ellipsoid((-.27,sy*.25,1.86),(.14,.08,.105),clay,sides=16,rings=9)
        for j in range(3):
            parts[4].path([(.03+j*.17,sy*.27,1.75),(.01+j*.18,sy*.32,1.55),
                           (-.04+j*.20,sy*.32,1.50)],.023,clay,sides=7)
    # Rear beast has its own horns and remains a modeled volume.
    parts[15].ellipsoid((1.11,0,1.05),(.24,.20,.24),clay,sides=20,rings=12)
    for sy in (-1,1):
        parts[15].path([(1.03,sy*.12,1.19),(1.11,sy*.17,1.42),(1.23,sy*.14,1.49)],.032,clay,sides=8)
    # Normalize the entire molded assembly to the independently measured
    # envelope, before applying the roof-space transform and mirror.
    allv=[v for batch in parts for v in batch.v]
    lower=[min(v[k] for v in allv) for k in range(3)]
    upper=[max(v[k] for v in allv) for k in range(3)]
    factors=[width/(upper[0]-lower[0]),thickness/(upper[1]-lower[1]),height/(upper[2]-lower[2])]
    for i,batch in enumerate(parts):
        batch.v=[(end*(x-(lower[0]+upper[0])/2)*factors[0],
                  (y-(lower[1]+upper[1])/2)*factors[1],(z-lower[2])*factors[2]) for x,y,z in batch.v]
        if end<0:
            batch.f=[tuple(reversed(face)) for face in batch.f]
        batch.origin=Vector(origin);batch.yaw=yaw
        obj=batch.finish(label+' · 琉璃拼件 %02d'%(i+1),group,bevel=.013,
                         properties={'component_index':i+1,'source':CHI_SOURCE,
                                     'fidelity':'Measured overall envelope; photograph-led modeled surfaces and joints'})
    group['measured_width_height_thickness_m']=[width,height,thickness]
    group['source']=CHI_SOURCE
    return group


def wing(batch,x,y,z,sign,material,*,scale=1.,bird=False):
    for i in range(8):
        t=i/7
        end=(x+(.12-.38*t)*scale,y+sign*(.20+.25*math.sin(t*math.pi))*scale,
             z+(.26-.18*t)*scale)
        start=(x+.10*scale,y+sign*.10*scale,z+.02*scale)
        batch.rod(start,end,.026*scale,material,r1=.007*scale,sides=8)


def guardian(target,pal,*,point,yaw=0.,ordinal=1,height=.68,immortal=False,label=None):
    """A distinct native sculpture for each of the ten named guardian species."""
    b=Batch();clay=pal.tiles[1];eye=pal.darktile
    name='骑凤仙人' if immortal else ORDER[ordinal-1]
    b.box((0,0,.012),(.34,.20,.045),clay)
    human=(ordinal==10 and not immortal)
    bird=immortal or ordinal==2
    if human:
        for sy in (-1,1):
            b.path([(0,sy*.07,.07),(-.01,sy*.08,.23),(.01,sy*.055,.35)],.031,clay,sides=10)
            b.ellipsoid((.035,sy*.075,.075),(.07,.04,.025),clay,sides=12,rings=6)
        b.ellipsoid((0,0,.41),(.075,.11,.13),clay,sides=18,rings=10)
        b.ellipsoid((.018,0,.60),(.077,.071,.085),clay,sides=18,rings=12)
        b.ellipsoid((.09,0,.595),(.038,.054,.034),clay,sides=14,rings=8)
        for sy in (-1,1):
            wing(b,-.065,0,.43,sy,clay,scale=1.05)
            b.path([(.01,sy*.10,.49),(.08,sy*.14,.39),(.17,sy*.12,.41)],.024,clay,sides=9)
            b.ellipsoid((.071,sy*.047,.626),(.012,.011,.013),eye,sides=9,rings=5)
        b.rod((.19,-.14,.13),(.19,-.14,.60),.016,clay,sides=10)
        b.ellipsoid((.19,-.14,.62),(.024,.024,.045),clay,sides=10,rings=6)
    elif bird:
        b.ellipsoid((-.025,0,.19),(.13,.085,.12),clay,sides=18,rings=10)
        for sy in (-1,1):
            b.rod((.04,sy*.05,.04),(.02,sy*.05,.18),.018,clay,sides=9)
            wing(b,-.04,0,.24,sy,clay,scale=.60,bird=True)
        b.path([(.06,0,.21),(.12,0,.34),(.12,0,.44),(.17,0,.48)],.028,clay,sides=11)
        b.ellipsoid((.17,0,.48),(.055,.041,.054),clay,sides=16,rings=9)
        b.rod((.21,0,.48),(.28,0,.47),.025,clay,r1=.003,sides=10)
        for j in range(5):
            yy=(j-2)*.022
            b.path([(-.12,yy,.23),(-.23,yy,.31),(-.28,yy,.46),(-.20,yy,.52)],.012,clay,sides=7)
        if immortal:
            b.ellipsoid((-.02,0,.38),(.060,.05,.09),clay,sides=16,rings=9)
            b.ellipsoid((-.005,0,.51),(.047,.045,.057),clay,sides=18,rings=10)
            b.lathe(-.005,0,((.058,.56),(.049,.59),(.02,.62)),clay,sides=18)
            for sy in (-1,1):
                b.path([(-.04,sy*.035,.40),(-.02,sy*.11,.32),(.055,sy*.11,.29)],.018,clay,sides=8)
                b.path([(.01,sy*.045,.43),(.08,sy*.07,.42),(.12,sy*.065,.39)],.015,clay,sides=8)
    else:
        lion=ordinal in (3,6)
        horse=ordinal in (4,5)
        fish=ordinal==7
        bull=ordinal==9
        b.ellipsoid((-.015,0,.22),(.14,.083,.12 if not horse else .105),clay,sides=20,rings=12)
        for sx in (-1,1):
            for sy in (-1,1):
                px=sx*.10
                b.path([(px,sy*.058,.23),(px+.017,sy*.067,.12),(px+.028,sy*.067,.045)],
                       .023 if lion else .018,clay,sides=9)
                b.ellipsoid((px+.043,sy*.067,.04),(.045,.028,.026),clay,sides=11,rings=6)
                if not horse:
                    for toe in (-1,0,1):
                        b.rod((px+.06,sy*.067+toe*.015,.035),(px+.082,sy*.067+toe*.017,.026),
                              .006,clay,r1=.002,sides=5)
        # Neck and head are substantial volumes, with a visible snout.
        b.path([(.08,0,.25),(.11,0,.36),(.12,0,.43)],.048 if horse else .062,clay,sides=13)
        b.ellipsoid((.13,0,.43),(.064,.063,.075),clay,sides=20,rings=12)
        b.ellipsoid((.20,0,.405),(.075 if horse else .060,.055,.043),clay,sides=18,rings=10)
        for sy in (-1,1):
            b.ellipsoid((.171,sy*.054,.459),(.012,.010,.013),eye,sides=10,rings=6)
            b.path([(.135,sy*.06,.485),(.18,sy*.06,.49),(.20,sy*.05,.477)],.009,clay,sides=6)
            b.rod((.092,sy*.041,.485),(.080,sy*.051,.553),.020,clay,r1=.006,sides=9)
        b.path([(-.14,0,.25),(-.23,0,.34),(-.26,0,.46),(-.19,0,.49)],.019,clay,sides=9)
        if lion:
            for i in range(18):
                a=i*math.tau/18
                b.ellipsoid((.075,math.sin(a)*.077,.417+math.cos(a)*.084),(.027,.027,.027),clay,sides=10,rings=6)
            for sy in (-1,1):
                spiral(b,(.03,sy*.08,.35),.05,clay,side=sy,tube=.009)
        if horse:
            for k in range(10):
                b.path([(.062-k*.005,0,.34+k*.014),(.01-k*.006,0,.37+k*.014)],.008,clay,sides=6)
            for sy in (-1,1):
                wing(b,-.03,0,.29,sy,clay,scale=.55 if ordinal==4 else .38)
        if ordinal in (1,7,9):
            for sy in (-1,1):
                for i in range(9):
                    xx=-.13+i*.027
                    for j in range(3):
                        zz=.17+j*.035
                        b.path([(xx-.013,sy*.082,zz),(xx,sy*.087,zz-.014),
                                (xx+.013,sy*.082,zz)],.0048,clay,sides=5)
        if ordinal in (1,8,9):
            for sy in ((0,) if ordinal==8 else (-1,1)):
                b.path([(.09,sy*.037,.49),(.068,sy*.055,.60),(.11,sy*.06,.65)],.014,clay,sides=9)
        if fish:
            for i in range(8):
                xx=-.12+i*.031
                b.face([(xx,0,.32),(xx-.018,0,.42),(xx+.025,0,.33)],clay)
            b.rod((.23,0,.395),(.28,0,.38),.035,clay,r1=.004,sides=10)
    # Preserve a common .321 m ceramic carrier scale; height is inferred from
    # the close-up photographs. Only the complete chiwen envelope is measured.
    low=min(v[2] for v in b.v);high=max(v[2] for v in b.v)
    factor=height/(high-low)
    b.v=[(x*.82,y*.86,(z-low)*factor) for x,y,z in b.v]
    b.origin=Vector(point);b.yaw=yaw
    return b.finish(label or ('脊兽 · '+name),target,bevel=.001,
                    properties={'guardian_species':name,'guardian_ordinal':0 if immortal else ordinal,
                                'source':GUARD_SOURCE,
                                'fidelity':'Documented order; species silhouette/height reconstructed from photographs'})
