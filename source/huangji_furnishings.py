"""Photo-led enamel elephants; catalogue envelope and inferred placement are explicit."""
import math
from types import SimpleNamespace

from mathutils import Vector

from carved_ornament import cloud, dragon
from garden_bridge_pavilions import transfer
from mesh_tools import Batch, collection
from ning_shou_halls import DECK
from paired_halls import frame
from palace_materials import paint


CATALOGUE = 'https://www.dpm.org.cn/collection/enamel/229316.html'
PANORAMA = 'https://www.sigoo.com/inside-the-hall-of-imperial-supremacy/'
ENVELOPE = (.55, 1.00, 1.70)
POSITIONS = ((-5.52, -.94), (5.52, -.94))


def enamel_palette(p):
    return SimpleNamespace(
        white=paint('皇极殿陈设 · 月白珐琅与旧釉', (.36,.49,.49), second=(.64,.72,.68),
                    scale=41, rough=.29, coat=.32, bump=.00012, grain=490),
        blue=paint('皇极殿陈设 · 宝蓝珐琅', (.010,.100,.160), second=(.031,.277,.321),
                   scale=37, rough=.31, coat=.29, bump=.00013, grain=460),
        green=paint('皇极殿陈设 · 珐琅勾云', (.052,.180,.118), second=(.117,.260,.172),
                    scale=52, rough=.36, metal=.12, bump=.00009),
        pink=paint('皇极殿陈设 · 胭脂珐琅莲瓣', (.251,.057,.062), second=(.474,.166,.166),
                   scale=47, rough=.38, coat=.22, bump=.0001),
        eye=paint('皇极殿陈设 · 乌珠与沟线', (.010,.016,.016), rough=.24, bump=0),
        ivory=paint('皇极殿陈设 · 象牙色釉', (.40,.33,.20), second=(.68,.61,.43),
                    scale=53, rough=.36, bump=.00012),
        gilt=p.old_gold,
    )


def pedestal(b,e,p):
    for z,w,d,h,m in ((.020,.514,.894,.040,e.gilt),(.054,.540,.927,.027,e.blue),
                       (.082,.499,.879,.031,e.gilt),(.159,.454,.832,.134,e.blue),
                       (.235,.516,.900,.028,e.gilt),(.263,.546,.938,.027,e.blue),
                       (.281,.548,.939,.013,e.gilt)):
        b.box((0,0,z),(w,d,h),m)
    for side in (-1,1):
        for y in (-.410,.410):
            b.lathe(side*.232,y,((.020,.085),(.019,.105),(.028,.129),(.020,.150),
                                (.014,.174),(.023,.205),(.018,.231)),e.gilt,sides=20)
        # Front and back cartouches with visible supporting borders.
        y=side*.426
        frame(b,0,y,.161,.396,.110,.010,e.gilt)
        for i in range(7):
            cloud(b,((i-3)*.051,y-side*.009,.159),.039,e.green,rotation=i*.61)
        for row in range(3):
            for i in range(19):
                x=(i-9)*.022
                b.ellipsoid((x,side*.448,.103+row*.016),(.004,.003,.004),e.pink,sides=8,rings=5)
    for side in (-1,1):
        for j in range(31):
            y=(j-15)*.027
            b.path([(side*.268,y,.285),(side*.268,y,.307),
                    (side*.268,y+.012,.307),(side*.268,y+.012,.295)],.0026,e.gilt,sides=6)
        for row in range(4):
            for i in range(27):
                y=(i-13)*.030
                b.ellipsoid((side*.230,y,.114+row*.027),(.0025,.004,.004),e.gilt,sides=7,rings=5)


def ellipsoid_scrolls(b,center,radii,e,phase=0.):
    """Small raised cloison outlines following the enamel body, in metres."""
    x,y,z=center; rx,ry,rz=radii
    for row in range(10):
        latitude=-1.16+row*.25
        for column in range(39):
            longitude=column*math.tau/39+phase+row*.071
            points=[]
            for k in range(25):
                t=k/24
                a=t*math.tau*1.32
                radius=.018*(1-.84*t)
                theta=longitude+radius*math.cos(a)/max(.12,rx)
                phi=latitude+radius*math.sin(a)/max(.15,rz)
                points.append((x+rx*math.cos(phi)*math.cos(theta),
                               y+ry*math.cos(phi)*math.sin(theta), z+rz*math.sin(phi)))
            b.path(points,.00085,e.green,sides=6)
            if column%3==0:
                b.path(points[:7],.0006,e.gilt,sides=5)


def animal(body,detail,e):
    body.ellipsoid((0,.025,.835),(.224,.358,.243),e.white,sides=64,rings=36)
    ellipsoid_scrolls(detail,(0,.025,.835),(.226,.360,.245),e)
    for side in (-1,1):
        for y in (-.207,.255):
            body.rod((side*.151,y,.305),(side*.155,y,.760),.067,e.white,r1=.082,sides=36)
            body.ellipsoid((side*.151,y,.327),(.070,.075,.038),e.white,sides=32,rings=17)
            for j in range(4):
                x=side*.151+(j-1.5)*.025
                body.ellipsoid((x,y-.067,.319),(.013,.008,.015),e.ivory,sides=16,rings=9)
            for j in range(7):
                z=.371+j*.047
                for k in range(10):
                    a=k*math.tau/10+j*.24
                    points=[]
                    for i in range(23):
                        t=i/22; angle=t*math.tau*1.30; radius=.013*(1-.85*t)
                        theta=a+radius*math.cos(angle)/(.071+.002*j)
                        points.append((side*.154+(.071+.002*j)*math.cos(theta),
                                       y+(.071+.002*j)*math.sin(theta),z+radius*math.sin(angle)))
                    detail.path(points,.0009,e.green,sides=6)
    body.ellipsoid((0,-.287,.909),(.170,.168,.183),e.white,sides=56,rings=32)
    ellipsoid_scrolls(detail,(0,-.287,.909),(.172,.170,.185),e,phase=.31)
    for side in (-1,1):
        # Broad ears are gently domed through a shared front/back outline.
        outline=[(side*.121,-.260,1.034),(side*.218,-.244,1.063),
                 (side*.275,-.217,.995),(side*.269,-.237,.864),
                 (side*.221,-.280,.805),(side*.149,-.312,.828)]
        center=Vector((side*.192,-.282,.933))
        vertices=[tuple(center)]+outline
        back=[(x,y+.019,z) for x,y,z in vertices]
        n=len(vertices)
        faces=[]
        for j in range(1,n):
            k=j+1 if j+1<n else 1
            faces.extend(((0,j,k),(n,n+k,n+j),(j,j+n,k+n,k)))
        body.add(vertices+back,faces,e.white,smooth=True)
        detail.path(outline+[outline[0]],.0038,e.gilt,sides=7)
        for j in range(4):
            cloud(detail,(side*(.161+j*.019),-.301+j*.004,.846+j*.047),.026,e.green,rotation=j*.73)
        body.ellipsoid((side*.130,-.412,.957),(.026,.010,.014),e.gilt,sides=24,rings=14)
        body.ellipsoid((side*.132,-.422,.958),(.010,.004,.008),e.eye,sides=22,rings=13)
        body.path([(side*.092,-.388,.837),(side*.125,-.449,.768),
                   (side*.137,-.499,.675),(side*.137,-.520,.641)],.024,e.ivory,sides=18)
        # Chains and pendants are actual open rings, not painted silhouettes.
        for j in range(7):
            detail.path([(side*.177+.009*math.cos(a),-.293,.852-j*.020+.013*math.sin(a))
                         for a in (i*math.tau/17 for i in range(18))],.0022,e.gilt,sides=6)
        body.lathe(side*.177,-.293,((.018,.679),(.025,.695),(.027,.724),(.009,.745)),e.pink,sides=22)
    points=[(0,-.410,.858),(0,-.444,.747),(0,-.475,.632),(0,-.472,.511),
            (0,-.442,.426),(0,-.390,.399),(0,-.339,.420),(0,-.319,.465)]
    # Decreasing radius prevents a uniformly cylindrical hose-shaped trunk.
    for i,(start,end) in enumerate(zip(points,points[1:])):
        body.rod(start,end,.056-i*.0054,e.white,r1=.056-(i+1)*.0054,sides=30)
        body.ellipsoid(end,(.051-i*.0051,)*3,e.white,sides=28,rings=16)
    for j in range(23):
        t=j/22; segment=min(6,int(t*7)); a=t*7-segment
        point=Vector(points[segment]).lerp(Vector(points[segment+1]),a)
        tangent=(Vector(points[segment+1])-Vector(points[segment])).normalized()
        u=Vector((1,0,0)); v=tangent.cross(u).normalized()
        rr=.055-.036*t
        detail.path([tuple(point+rr*(u*math.cos(q)+v*math.sin(q)))
                     for q in (i*math.tau/33 for i in range(34))],.0015,e.green,sides=5)
    body.path([(0,.345,.913),(.011,.404,.802),(.016,.436,.638),
               (.021,.442,.537)],.018,e.ivory,sides=15)
    body.ellipsoid((.021,.442,.531),(.024,.019,.053),e.gilt,sides=24,rings=14)


def saddle_and_vase(b,e,p):
    b.ellipsoid((0,.029,1.025),(.222,.274,.061),e.gilt,sides=52,rings=20)
    b.ellipsoid((0,.029,1.051),(.206,.254,.043),e.blue,sides=52,rings=20)
    # Drooping saddle pads on both sides, with modeled rolled edges.
    for side in (-1,1):
        work=Batch()
        work.box((0,0,.839),(.337,.021,.348),e.blue)
        bottom=[(.157*math.cos(a),-.015,.688-.066*math.sin(a))
                for a in (i*math.pi/48 for i in range(49))]
        work.path([(-.168,-.017,1.010),(-.168,-.017,.688)]+list(reversed(bottom))+
                  [(.168,-.017,1.010)],.008,e.gilt,sides=9)
        frame(work,0,-.019,.852,.285,.274,.004,e.gilt)
        dragon(work,(0,-.023,.849),.250,.237,p,detailed=True,z_relief=.004)
        for j in range(11):
            cloud(work,((j-5)*.025,-.026,.718),.019,e.green,rotation=j*.51)
        for j in range(15):
            u=(j-7)*.021
            work.path([(u,-.027,.700),(u,-.029,.673),(u+.003,-.029,.663)],.0019,e.gilt,sides=6)
        # Map pad coordinates into the two lateral vertical planes.
        for slot,material in enumerate(work.mats):
            b.add([(side*(.228-v),.029+u,z) for u,v,z in work.v],
                  [f for f,mi in zip(work.f,work.mi) if mi==slot],material,smooth=True)
    profile=((.074,1.068),(.089,1.096),(.102,1.117),(.100,1.151),(.079,1.177),
             (.068,1.198),(.086,1.224),(.105,1.237),(.084,1.274),(.068,1.300),
             (.061,1.328),(.073,1.354),(.106,1.393),(.133,1.430),(.142,1.467),
             (.137,1.501),(.111,1.532),(.078,1.548),(.062,1.559),(.063,1.583))
    b.lathe(0,.029,profile,e.blue,sides=72)
    for rr,z in ((.090,1.102),(.101,1.140),(.083,1.202),(.103,1.236),
                 (.069,1.300),(.073,1.353),(.138,1.483),(.065,1.564),(.072,1.588)):
        b.lathe(0,.029,((rr,z-.004),(rr+.002,z+.004)),e.gilt,sides=72)
    for j in range(20):
        angle=j*math.tau/20
        for k,z in enumerate((1.145,1.244,1.397,1.450,1.501)):
            radius=(.102,.100,.108,.139,.137)[k]
            # Delicate flower rosettes sit on the vase's cylindrical surface.
            q=Vector((radius*math.cos(angle),.029+radius*math.sin(angle),z))
            tangent=Vector((-math.sin(angle),math.cos(angle),0))
            for petal in range(6):
                a=petal*math.tau/6
                center=q+tangent*(.011*math.cos(a))+Vector((0,0,.011*math.sin(a)))
                b.ellipsoid(center,(.004,.004,.006),e.pink if (j+k)%3 else e.white,sides=10,rings=7)
        b.path([(.064*math.cos(angle),.029+.064*math.sin(angle),1.595),
                (.055*math.cos(angle+.10),.029+.055*math.sin(angle+.10),1.639),
                (.028*math.cos(angle+.17),.029+.028*math.sin(angle+.17),1.690)],.0038,e.gilt,sides=8)
    b.ellipsoid((0,.029,1.638),(.036,.036,.048),e.gilt,sides=32,rings=20)


def build_elephants(loc,target,p):
    group=collection('皇极殿 · 太平有象成对珐琅陈设',target)
    group['catalogue']=CATALOGUE
    group['association']='Typological match to the photographed pair; catalogue inventory identity unconfirmed.'
    e=enamel_palette(p)
    for index,(x,y) in enumerate(POSITIONS,1):
        pieces={name:Batch() for name in ('束腰座','月白象体','勾云与链饰','鞍垫与宝瓶')}
        pedestal(pieces['束腰座'],e,p)
        animal(pieces['月白象体'],pieces['勾云与链饰'],e)
        saddle_and_vase(pieces['鞍垫与宝瓶'],e,p)
        vertices=[v for piece in pieces.values() for v in piece.v]
        lower=[min(v[a] for v in vertices) for a in range(3)]
        upper=[max(v[a] for v in vertices) for a in range(3)]
        scale=[ENVELOPE[a]/(upper[a]-lower[a]) for a in range(3)]
        for name,piece in pieces.items():
            work=loc.batch()
            for slot,material in enumerate(piece.mats):
                points=[(x+(v[0]-(lower[0]+upper[0])/2)*scale[0],
                         y+(v[1]-(lower[1]+upper[1])/2)*scale[1],
                         DECK+.012+(v[2]-lower[2])*scale[2]) for v in piece.v]
                work.add(points,[face for face,mi in zip(piece.f,piece.mi) if mi==slot],material,smooth=True)
            work.finish(f'皇极殿 · 太平有象 {index} · {name}',group,
                        properties={'role':'huangji_enamel_elephant','pair_index':index,'part':name,
                                    'catalogue_envelope_xyz_m':list(ENVELOPE), 'catalogue':CATALOGUE,
                                    'catalogue_identity_confirmed':False,'local_xy_m':[x,y],
                                    'placement_evidence':PANORAMA,'sculpture_and_position_inferred':True})
    return group
