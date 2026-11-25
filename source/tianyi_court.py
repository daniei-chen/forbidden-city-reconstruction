"""Tianyi Gate, compound walls and individual stone and bronze court fittings."""
import math
import random

from shapely.geometry import LineString, Point, Polygon, box

from architectural_roofs import swept_roof
from carved_ornament import cloud
from garden_bridge_pavilions import flower, laid_pavers, transfer
from garden_context import old_cypress, planting_bed
from mesh_tools import Batch, collection, polygons
from osm_site import rectangle
from palace_architecture import arch_mesh, arch_section
from palace_materials import paint
from qinan_hall import bracket, marble_rail, painted_bay, plaque, stone_step_run
from qinan_survey import COURT_WALLS, GARDEN_SOURCE, GATE_SOURCE, Location, QIN, TIANYI

GATE_FLOOR=.47
GATE_CROWN=3.39
GATE_W=5.04
GATE_D=2.57
GATE_CLEAR=2.18
GATE_RISE=1.03
SIDE_GATE_X=(-22.35,18.18)
SIDE_GATE_Y=390.34
PAVING_SOURCE='https://www.dpm.org.cn/Uploads/File/2022/03/09/u622827d596a09.pdf'


def arch_courses(b,w,crown,rise,depth,p):
    centre=crown-rise
    covered=arch_section(0,w,crown,bottom=GATE_FLOOR-.3,rise=rise)
    for side in (-1,1):
        y=side*(depth/2+.005)
        for i in range(15):
            lo,hi=(i+.006)*math.pi/15,(i+.994)*math.pi/15
            pts=[(r*math.cos(a),y,centre+h*math.sin(a)) for r,h,aa in
                 ((w/2-.006,rise-.004,(lo,hi)),(w/2+.346,rise+.329,(hi,lo))) for a in aa]
            b.face(pts if side<0 else list(reversed(pts)),p.bluebrick)
        for sx in (-1,1):
            for i in range(7):
                z=GATE_FLOOR+(i+.5)*(centre-GATE_FLOOR)/7
                b.box((sx*(w/2+.109),y,z),(.229,.023,(centre-GATE_FLOOR)/7-.003),p.bluebrick)
    return covered


def gate_leaf(loc,target,p,side):
    width=GATE_CLEAR/2-.018
    bottom=GATE_FLOOR+.015
    height=GATE_CROWN-bottom-.055
    work=Batch()
    hinge=side*(width+.017)
    cx=side*(width*.5+.010)-hinge
    work.box((cx,0,bottom+height/2),(width,.151,height),p.red)
    for i in range(5):
        x=cx+width*((i+.5)/5-.5)
        work.box((x,.083,bottom+height/2),(width/5-.007,.024,height-.033),p.fascia)
    for j in (.14,.49,.84):
        work.box((cx,.093,bottom+height*j),(width-.054,.065,.083),p.door)
    for j in range(9):
        z=bottom+.161+j*(height-.26)/8
        for i in range(9):
            x=side*(.063+i*(width-.112)/8)-hinge
            work.rod((x,-.079,z),(x,-.108,z),.033,p.old_gold,sides=11)
            work.ellipsoid((x,-.111,z),(.026,.024,.025),p.old_gold,sides=11,rings=6)
    x=side*.126-hinge;z=GATE_FLOOR+1.29
    work.ellipsoid((x,-.098,z),(.073,.032,.082),p.old_gold,sides=14,rings=7)
    work.path([(x+.042*math.cos(j*math.tau/18),-.13,z-.062+.054*math.sin(j*math.tau/18)) for j in range(19)],
              .009,p.bronze,sides=7)
    yaw=-side*math.radians(82)
    work.origin[:]=loc.world(hinge,.772);work.yaw=loc.yaw+yaw
    work.finish('天一门 · '+('西' if side<0 else '东')+'朱漆铜钮门扇',target,properties={
        'grid_columns_per_leaf':9,'grid_rows_per_leaf':9,'bronze_stud_count':81,'model_hinge_angle_deg':math.degrees(yaw),
        'closed_world_yaw_rad':loc.yaw,'open_world_yaw_rad':loc.yaw+yaw})


def crane_tile(b,x,y,z,scale,flip,p):
    s=scale
    vertices=[(x+s*flip*u,y,z+s*v) for u,v in ((-.23,-.12),(-.19,.01),(-.055,.071),(.11,.094),
              (.193,.176),(.129,.237),(.152,.337),(.211,.342),(.327,.282),(.225,.291),(.188,.221),
              (.24,.14),(.186,-.012),(.012,-.12),(-.10,-.155))]
    b.face(vertices,p.cream)
    b.path(vertices+[vertices[0]],.011*s,p.tiles[2],sides=6)
    for j in range(7):
        b.path([(x+.04*s*flip,y-.008,z+.035*s),(x-(.09+j*.023)*s*flip,y-.016,z+(.17+.025*j)*s),
                (x-(.19+j*.023)*s*flip,y-.013,z+(.17+.031*j)*s)],.009*s,p.cream,sides=6)
    for j in (-1,1):
        b.path([(x-.043*s*flip,y-.006,z-.115*s),(x+(j*.045-.08)*s*flip,y-.01,z-.235*s),
                (x+(j*.071-.166)*s*flip,y-.012,z-.268*s)],.007*s,p.tiles[1],sides=6)


def shadow_wall(loc,target,p,side):
    x=side*3.47
    width,depth=1.95,.62
    y=-.075
    b=loc.batch()
    b.box((x,y,1.38),(width,depth,2.66),p.paint)
    for z,h,mat in ((.14,.265,p.understone),(.40,.20,p.tiles[1]),(.61,.16,p.green_clay),
                    (.76,.095,p.tiles[3]),(2.39,.093,p.tiles[3]),(2.51,.145,p.green_clay),(2.625,.061,p.tiles[1])):
        b.box((x,y,z),(width+.028,depth+.031,h),mat)
    for j in (-1,1):
        b.box((x+j*.894,y-.329,1.58),(.085,.085,1.79),p.tiles[2])
    for f in (-1,1):
        v=y+f*.335;cz=1.55
        for j,mat in ((.635,p.tiles[2]),(.568,p.green_clay),(.525,p.tiles[1])):
            pts=[(x+j*(1+.11*math.cos(4*a))*math.cos(a),v,cz+j*(1+.11*math.cos(4*a))*math.sin(a))
                 for a in (i*math.tau/72 for i in range(73))]
            b.path(pts,.027,mat,sides=8)
        for k in (-1,1):
            crane_tile(b,x+k*.192,v-.04,cz+.105*k,.83,k,p)
            for a in (-1,1):
                cloud(b,(x+k*.708,v+.013,cz+a*.662),.33,p.tiles[1],rotation=k+a*.7)
            cloud(b,(x+k*.265,v+.007,cz+.29*k),.22,p.green_clay,rotation=-k)
        for i in range(9):
            cloud(b,(x+(i-4)*.202,v+.015,.571),.18,p.tiles[0],rotation=i*math.pi*.83)
    b.finish('天一门 · '+('西' if side<0 else '东')+'仙鹤云纹琉璃影壁',target)
    swept_roof('天一门 琉璃影壁 '+str(side),target,p,origin=loc.world(x,y),yaw=loc.yaw,
               width=width+.302,depth=.987,eave=2.79,rise=.40,kind='gable',tiles=True,pitch=.177,
               ridge_terminals=False,beasts=0,gable_ends=False)


def animal(b,x,y,z,p,*,size=1.,yaw=0.,stone=False,with_base=True):
    """A horned crouching guardian, with separately drawn main surfaces."""
    t=Batch();s=size
    a=p.stone if stone else p.old_gold
    accent=p.understone if stone else p.guards_bronze
    if with_base:
        t.solid_xy(box(-.57*s,-.55*s,.57*s,.59*s),0,.125*s,p.understone)
        t.solid_xy(box(-.52*s,-.51*s,.52*s,.55*s),.125*s,.373*s,p.stone)
        t.solid_xy(box(-.58*s,-.56*s,.58*s,.60*s),.373*s,.459*s,p.stone)
        for i in range(7):
            cloud(t,((i-3)*.131*s,-.513*s,.255*s),.154*s,p.stone,rotation=i*2.4)
    base=.462*s if with_base else 0.
    def C(u,v,h):
        return u*s,v*s,base+h*s
    t.ellipsoid(C(0,.081,.489),(.285*s,.387*s,.457*s),accent,sides=25,rings=17)
    t.ellipsoid(C(0,-.135,.644),(.24*s,.229*s,.403*s),accent,sides=24,rings=15)
    t.ellipsoid(C(0,-.208,.997),(.241*s,.225*s,.229*s),accent,sides=26,rings=17)
    t.ellipsoid(C(0,-.395,.974),(.179*s,.119*s,.101*s),a,sides=21,rings=14)
    t.ellipsoid(C(0,-.472,.942),(.118*s,.039*s,.044*s),p.black,sides=19,rings=9)
    for side in (-1,1):
        t.ellipsoid(C(side*.20,.198,.244),(.157*s,.224*s,.221*s),a,sides=20,rings=12)
        t.ellipsoid(C(side*.212,-.247,.118),(.105*s,.166*s,.081*s),a,sides=20,rings=11)
        t.path([C(side*.205,-.111,.665),C(side*.226,-.205,.438),C(side*.207,-.284,.167)],.079*s,a,sides=15)
        for toe in range(4):
            t.ellipsoid(C(side*(.159+.034*toe),-.374,.103),(.025*s,.045*s,.024*s),a,sides=10,rings=7)
        for row in range(9):
            t.path([C(side*.206,-.244-.012*j,.188+row*.041+.022*math.sin(j*.44)) for j in range(8)],
                   .0089*s,accent,sides=6)
        t.ellipsoid(C(side*.14,-.393,1.09),(.055*s,.04*s,.037*s),a,sides=15,rings=8)
        t.ellipsoid(C(side*.136,-.429,1.086),(.018*s,.016*s,.016*s),p.black,sides=11,rings=6)
        t.path([C(side*.104,-.414,1.115),C(side*.169,-.382,1.143),C(side*.212,-.323,1.103)],.023*s,a,sides=9)
        t.path([C(side*.185,-.152,1.152),C(side*.235,-.132,1.236),C(side*.241,-.052,1.274)],.033*s,a,sides=9)
        for j in range(9):
            t.rod(C(side*.169,-.238+j*.017,.941+j*.023),
                  C(side*(.294+j*.008),-.06+j*.019,1.01+j*.036),.024*s,a,r1=.005*s,sides=9)
        for j in range(3):
            t.ellipsoid(C(side*(.052+j*.027),-.463,.947),(.014*s,.022*s,.021*s),a,sides=9,rings=7)
    t.path([C(0,-.198,1.161),C(.007,-.166,1.309),C(.040,-.095,1.397)],.041*s,a,sides=13)
    t.path([C(.13,.349,.275),C(.332,.394,.382),C(.459,.303,.543),C(.395,.168,.62)],.054*s,a,sides=13)
    if z:
        t.v=[(u,v,w+z) for u,v,w in t.v]
    transfer(b,t,x,y,yaw)


def build_tianyi(site,loc,target,p):
    group=collection('天一门 · 青砖券门和琉璃影壁',target)
    group['museum_source']=GATE_SOURCE
    group['source_osm_id']=TIANYI
    b=loc.batch();decor=loc.batch()
    cut=arch_courses(b,GATE_CLEAR,GATE_CROWN,GATE_RISE,GATE_D,p)
    wall_face=box(-GATE_W/2,GATE_FLOOR-.21,GATE_W/2,4.12)
    fore=Batch();arch_mesh(fore,wall_face.difference(cut),1.72,p.bluebrick)
    transfer(b,fore,0,-GATE_D/2+.86,0)
    rear=Batch();arch_mesh(rear,wall_face.difference(box(-1.245,GATE_FLOOR-.14,1.245,GATE_CROWN+.108)),.85,p.bluebrick)
    transfer(b,rear,0,GATE_D/2-.425,0)
    b.solid_xy(box(-GATE_W/2-.10,-2.07,GATE_W/2+.10,1.97),.026,GATE_FLOOR-.057,p.understone)
    laid_pavers(b,box(-GATE_W/2-.10,-2.07,GATE_W/2+.10,1.97),GATE_FLOOR,p,course=.47,width=.68)
    stone_step_run(b,(0,-2.83),(0,-2.057),2.28,.030,GATE_FLOOR,p,count=3)
    stone_step_run(b,(0,2.73),(0,1.96),2.28,.026,GATE_FLOOR,p,count=3)
    for y in (-1.98,1.92):
        for side in (-1,1):
            marble_rail(b,((side*1.27,y),(side*2.50,y)),GATE_FLOOR,p,step=1.45)
    for side in (-1,1):
        for z,h,w in ((.357,.14,GATE_W+.077),(3.984,.15,GATE_W+.024),(4.149,.127,GATE_W+.042)):
            b.box((0,side*GATE_D/2,z),(w,.116,h),p.understone if z<1 else p.faded_teal)
        painted_bay(decor,0,side*GATE_D/2,4.259,GATE_W+.035,p,yaw=0 if side<0 else math.pi,height=.281)
        for i in range(11):
            bracket(decor,(i-5)*.461,side*GATE_D/2,4.39,0 if side<0 else math.pi,p,glazed=True)
        for i in range(5):
            bracket(decor,side*GATE_W/2,(i-2)*.512,4.39,side*math.pi/2,p,glazed=True)
        gate_leaf(loc,group,p,side)
        shadow_wall(loc,group,p,side)
    b.finish('天一门 · 通券、青石券脸及两面台阶',group,properties={'central_arch_count':1,
              'modelled_clear_width_m':GATE_CLEAR,'modelled_intrados_crown_z_m':GATE_CROWN})
    decor.finish('天一门 · 绿釉仿木椽枋及旋花',group)
    swept_roof('天一门 黄琉璃歇山',group,p,origin=loc.world(),yaw=loc.yaw,width=6.37,depth=3.72,eave=5.074,
               rise=.879,kind='xieshan',tiles=True,pitch=.192,detail=2,beasts=3,terminal_height=.49,eave_lift=.257)
    plaque(loc,group,'天一门',0,-1.61,4.545,.381,.461,p,
           ('north_tianyi_plaque.jpg','https://img.dpm.org.cn/Uploads/Picture/2020/04/20/s5e9d4ac16fcb4.jpg'))
    fittings=collection('天一门 · 铜镀金獬豸与青铜香炉',group)
    p.guards_bronze=paint('天一门 · 獬豸暗铜底色',(.067,.042,.019),second=(.234,.148,.069),scale=17.,
                          rough=.48,grain=136,bump=.004,metal=.82)
    for side in (-1,1):
        c=loc.batch()
        animal(c,side*3.24,-4.15,.037,p,size=.95,yaw=-side*.092)
        c.finish('天一门 · '+('西' if side<0 else '东')+'镀金獬豸',fittings,properties={'source':GATE_SOURCE,'geometry':'Photo-led, not measured.'})
    censer=loc.batch()
    censer.lathe(0,-6.29,((.41,.039),(.44,.10),(.30,.17),(.31,.35),(.43,.41),(.463,.55),(.427,.647),(.335,.712)),p.bronze,sides=32)
    for side in (-1,1):
        censer.path([(side*.34,-6.29,.40),(side*.53,-6.29,.61),(side*.40,-6.29,.711)],.035,p.bronze,sides=10)
    censer.finish('天一门 · 轴线上青铜香炉',fittings)
    return group,{'collection':group.name,'source':GATE_SOURCE,'source_osm':TIANYI,'modelled_masonry_clear_m':[GATE_CLEAR,GATE_CROWN-GATE_FLOOR],
                 'documented_features':['single brick arch','paired studded leaves','nine-by-nine nail rows','glazed crane and cloud side screens',
                                         'two gilded xiezhi and one bronze censer'],
                 'door_pose':'Master is open for inspection. South portrait closes the same modeled leaves on their hinges.'}


def rise_path(b,line,z,p,*,tile=True):
    points=list(line.coords)
    for a,c in zip(points,points[1:]):
        length=math.dist(a,c)
        if length<.07:
            continue
        angle=math.atan2(c[1]-a[1],c[0]-a[0]);u=(math.cos(angle),math.sin(angle));v=(-u[1],u[0])
        x,y=(a[0]+c[0])/2,(a[1]+c[1])/2
        b.box((x,y,z-.071),(length+.06,1.04,.148),p.faded_teal,yaw=angle)
        for sign in (-1,1):
            b.box((x+v[0]*sign*.41,y+v[1]*sign*.41,z+.017),(length+.05,.117,.11),p.tiles[2],yaw=angle)
        b.path([(a[0],a[1],z+.174),(c[0],c[1],z+.174)],.13,p.tiles[1],sides=10)
        if tile:
            n=max(1,round(length/.208))
            for i in range(n):
                t=(i+.5)/n
                px,py=a[0]*(1-t)+c[0]*t,a[1]*(1-t)+c[1]*t
                mat=p.tiles[i%5]
                for side in (-1,1):
                    b.rod((px,py,z+.119),(px+v[0]*side*.495,py+v[1]*side*.495,z+.008),.077,mat,sides=9)
                    b.rod((px+v[0]*side*.488,py+v[1]*side*.488,z+.007),
                          (px+v[0]*side*.535,py+v[1]*side*.535,z-.002),.086,mat,sides=12)


def court_walls(site,target,p):
    group=collection('钦安殿院 · 围墙、东西随墙门及地坪',target)
    b=Batch();wallcap=Batch()
    h=2.76
    for ref in (*COURT_WALLS,'685600247'):
        geom=site.geom(ref)
        x,y,w,d,yaw=rectangle(geom)
        loc=Location(x,y,yaw)
        local=loc.local(geom)
        if ref in ('685600256','685600259'):
            sign=1 if ref=='685600256' else -1
            from shapely.geometry import Point as P
            opening=loc.local(P(SIDE_GATE_X[0 if sign<0 else 1],SIDE_GATE_Y)).x
            g0=local.difference(box(opening-.61,-d,opening+.61,d))
            b.solid_xy(bpy_local_to_global(loc,g0),.033,h,p.paint)
            b.solid_xy(bpy_local_to_global(loc,g0.buffer(.047,join_style=2)),.030,.32,p.understone)
            gate=loc.batch()
            cut=arch_section(opening,1.213,2.16,bottom=.02,rise=.481)
            arch_mesh(gate,box(opening-.731,.045,opening+.731,h+.002).difference(cut),.87,p.bluebrick)
            gate.finish('钦安殿 · '+('东' if sign>0 else '西')+'随墙券门',group)
        elif ref in ('685600257','685600258'):
            gate=site.geom(TIANYI).buffer(1.10,join_style=2)
            geom=geom.difference(gate)
            b.solid_xy(geom,.033,h,p.paint)
            b.solid_xy(geom.buffer(.041,join_style=2),.031,.32,p.understone)
        else:
            b.solid_xy(geom,.033,h,p.paint)
            b.solid_xy(geom.buffer(.043,join_style=2),.031,.305,p.understone)
        bounds=loc.local(geom).bounds
        if len(bounds)==4:
            a,c=loc.world(bounds[0],0)[:2],loc.world(bounds[2],0)[:2]
            rise_path(wallcap,LineString((a,c)),h,p)
    b.finish('钦安殿院 · 按地图边界落位的红墙与灰石下碱',group)
    wallcap.finish('钦安殿院 · 琉璃瓦墙帽',group)
    return group


def bpy_local_to_global(loc,geometry):
    from shapely import affinity
    return affinity.translate(affinity.rotate(geometry,loc.yaw,(0,0),use_radians=True),loc.x,loc.y)


def pebble_inlay(location,target,p):
    group=collection('御花园 · 钦安殿西南石子路纹样样段',target)
    bed=location.batch();stones=location.batch()
    shades=[paint(f'御花园 · 铺石色号 {i+1}',value,rough=.78,bump=.0022,grain=146) for i,value in enumerate(
        ((.427,.394,.336),(.335,.314,.278),(.234,.210,.172),(.355,.262,.179),(.092,.105,.105),(.515,.486,.408)))]
    rnd=random.Random(62519)
    for k,cy in enumerate((-7.5,-8.71,-9.92,-11.13,-12.34,-13.55)):
        cx=-4.2;w=1.25;d=1.14
        bed.solid_xy(box(cx-w/2-.028,cy-d/2-.024,cx+w/2+.024,cy+d/2+.024),.025,.049,p.joint,bottom=False)
        for i in range(30):
            x=(i/29-.5)*w
            for j in range(27):
                y=(j/26-.5)*d
                rr=math.hypot(x,y)
                nose=((x-.16)**2/.14**2+(y+.014)**2/.073**2)<1
                body=(x*x/.214**2+y*y/.120**2)<1
                tail= -.36<x<-.165 and abs(y)<(.31+x*-1)*(-x-.16)
                fin=abs(y-.139)<.023 and -.05<x<.05
                shell=(x*x/.188**2+y*y/.143**2)<1
                claw= .154<abs(x)<.24 and (abs(y-.116)<.023 or abs(y+.103)<.023)
                shape=(body or nose or tail or fin) if k%2==0 else (shell or claw or (.19<x<.29 and abs(y)<.041))
                if .386<rr<.443 or i in (0,29) or j in (0,26):
                    mat=shades[4]
                elif shape:
                    mat=shades[3 if (i+j)%4 else 4]
                else:
                    mat=shades[rnd.choice((0,1,2,5))]
                stones.ellipsoid((cx+x+rnd.uniform(-.006,.006),cy+y+rnd.uniform(-.006,.006),.053),
                                 (.019+rnd.random()*.004,.016+rnd.random()*.005,.010+rnd.random()*.003),
                                 mat,sides=7,rings=4,yaw=rnd.random()*math.pi)
    bed.finish('御花园 · 样段地仗',group)
    stones.finish('御花园 · 鱼龟意象拼砌石子',group,properties={
        'source':PAVING_SOURCE,'fidelity':'Six interpreted panels using the documented aquatic animal subject; not the original panel sequence.'})


def court_landscape(site,target,p):
    group=collection('钦安殿院 · 古柏、花池及砖石铺地',target)
    p.bark=paint('御花园 · 柏树灰褐树皮',(.076,.048,.029),second=(.30,.238,.170),scale=4.7,rough=.95,bump=.015,grain=50)
    p.cypress=[paint(f'御花园中轴 · 枝叶 {i+1}',c,rough=.68,bump=.002) for i,c in enumerate(
        ((.031,.065,.029),(.052,.109,.041),(.074,.133,.042),(.098,.144,.055)))]
    p.soil=paint('御花园中轴 · 花池土',(.052,.038,.024),second=(.164,.133,.094),scale=6.8,rough=.96,bump=.008)
    p.rock=paint('御花园中轴 · 供石',(.175,.154,.119),second=(.498,.482,.408),scale=4.8,rough=.93,bump=.030)
    p.lotus_pink=paint('御花园中轴 · 花瓣胭脂',(.46,.122,.196),second=(.82,.38,.47),rough=.72,bump=.001)
    loc=Location.from_map(site,TIANYI)
    b=loc.batch()
    pad=box(-19.2,-11.3,17.8,15.74)
    reserved=(Point(-5.07,12.41).buffer(1.08).union(Point(6.07,12.69).buffer(1.04))
              .union(Point(-7.32,8.8).buffer(.76)).union(Point(8.73,8.9).buffer(.77)))
    laid_pavers(b,pad.difference(reserved),.042,p,course=.61,width=1.32)
    b.finish('钦安殿院 · 紧缝铺装与树穴',group)
    old_cypress(group,loc,p,'钦安殿 · 丹陛西侧古柏',-6.84,12.41,11.4,527,branch_start=4)
    old_cypress(group,loc,p,'钦安殿 · 丹陛东侧古柏',7.97,12.69,11.8,726,branch_start=4)
    old_cypress(group,loc,p,'钦安殿 · 西院古柏',-13.23,9.19,10.1,571)
    old_cypress(group,loc,p,'钦安殿 · 东院古柏',12.9,10.13,9.7,753)
    for i,id in enumerate(('529665395','529665396')):
        x,y=site.nodes[id]
        old_cypress(group,Location(x,y,0),p,'天一门内 · 连理柏干 '+str(i+1),0,0,10.72,361+i*17,branch_start=3)
    for side in (-1,1):
        planting_bed(loc,group,p,side*9.12,7.88,3.44,1.72,391+side*4,rock=False)
    pebble_inlay(loc,group,p)
    return group
