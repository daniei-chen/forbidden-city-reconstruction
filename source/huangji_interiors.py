"""Editable Huangji furnishings and the documented rear-hall room arrangement."""
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from mathutils import Vector
from shapely.geometry import Polygon, box

from carved_ornament import cloud, dragon
from garden_bridge_pavilions import ceiling_tile, dragon_relief, ring_outline
from huangji_furnishings import build_elephants
from huangji_caisson import add_caisson_details, hanging_pearl
from mesh_tools import Batch, collection
from museum_surface import relief_panel
from ning_shou_halls import (DECK, GOLD_COLUMNS, MAIN_X, MAIN_Y, REAR_X, REAR_Y,
                            MAIN_SOURCE, REAR_SOURCE, STUDY, image_surface, inscription, rail_cut)
from paired_halls import frame, lattice
from palace_materials import paint
from qinan_hall import painted_bay


DAIS_Y = 2.16
DAIS_FRONT = -.796
DAIS_RISE = 1.239
DAIS_STEPS = 7
SOFFIT = 8.79
CAISSON_Y = 3.93
CAISSON_OUTER = 4.68


def dark_wood(p):
    p.rosewood=paint('两殿室内 · 上蜡紫檀纹理',(.067,.020,.013),second=(.172,.073,.043),
                     scale=8.1,rough=.45,grain=130,bump=.0027,coat=.17)
    p.carpet=paint('皇极殿 · 旧地平纤维',(.252,.211,.143),second=(.452,.405,.314),
                   scale=6.2,rough=.92,grain=202,bump=.006)
    p.dark_silk=paint('皇极殿 · 藏蓝纱与毡面',(.023,.025,.042),second=(.092,.109,.147),
                      scale=8.6,rough=.74,grain=145,bump=.004)
    p.seat_gilt=paint('皇极殿 · 宝座擦金和温润包浆',(.38,.16,.028),second=(.75,.45,.105),
                      scale=62.,rough=.36,metal=.85,coat=.05,grain=430,bump=.00018)
    p.cushion=paint('宁寿宫 · 暖色暗缎',(.252,.083,.023),second=(.504,.235,.082),
                     scale=18.,rough=.66,grain=140,bump=.002)
    p.caisson_shade,p.caisson_gilt=p.old_gold,p.gold


def gilt_columns(loc,target,p):
    reference=Path(__file__).resolve().parent/'references/ning_shou_court/huangji_column_relief.npz'
    with np.load(reference,allow_pickle=False) as data:
        relief=data['relief']
    material=image_surface('huangji_gilt_column_detail',rough=.41,metal=.83)
    for idx,(x,y) in enumerate(GOLD_COLUMNS,1):
        b=loc.batch(); floor=DECK+.014; h=SOFFIT-floor+.31; r=.411
        b.lathe(x,y,((.571,floor),(.568,floor+.111),(.495,floor+.202),(.455,floor+.245)),p.stone,sides=52)
        z0,z1=floor+.202,floor+h
        nx=math.ceil(math.tau*(r+.006)/.0094)
        nz=math.ceil((z1-z0)/.0094)
        us,ts=np.meshgrid(np.linspace(0.,1.,nx+1),np.linspace(0.,1.,nz+1))
        vs=1.-ts
        texture_u=np.mod(us*4.+idx*.137,1.)
        px=(texture_u*(relief.shape[1]-1)).astype(int)
        py=(vs*(relief.shape[0]-1)).astype(int)
        amplitude=.0008*relief[py,px]
        rr=r*(1.-.077*ts)+amplitude
        angle=us*math.tau+idx*.42
        vertices=np.stack((x+rr*np.cos(angle),y+rr*np.sin(angle),z0+ts*(z1-z0)),axis=-1).reshape(-1,3)
        faces=[]
        for j in range(nz):
            for i in range(nx):
                a=j*(nx+1)+i
                faces.append((a,a+1,a+nx+2,a+nx+1))
        b.add(vertices,faces,material,uv=np.stack((us*4.+idx*.137,ts),axis=-1).reshape(-1,2),smooth=True)
        b.lathe(x,y,((r*.923,z1-.033),(r*.923,z1)),p.old_gold,sides=nx)
        b.finish('皇极殿 · 沥粉盘龙金柱 '+str(idx),target,properties={'role':'huangji_gilt_column',
                 'source':MAIN_SOURCE,'local_column_xy_m':[x,y],'diameter_and_position_inferred':True,
                 'surface_evidence':'Sigoo public interior panorama, visible column sector',
                 'sampled_rows':nz+1,'sampled_longitudes':nx+1,'max_nominal_grid_pitch_m':.0094,
                 'interpreted_relief_max_m':.0008,'hidden_longitude':'Repeated visible sector; unsurveyed.'})


def gold_rail(b,x,y0,y1,z0,z1,p):
    for lift,wide,h,m in ((.070,.160,.109,p.cinnabar),(.211,.107,.055,p.old_gold),(.636,.121,.105,p.cinnabar),
                          (.688,.109,.031,p.gold)):
        b.beam((x,y0,z0+lift),(x,y1,z1+lift),wide,h,m)
    length=abs(y1-y0)
    count=max(2,round(length/.45))
    pitch=(y1-y0)/count
    slope=(z1-z0)/(y1-y0)
    for row in (.302,.463):
        for j in range(count):
            t=(j+.5)/count; yy=y0+t*(y1-y0); zz=z0+t*(z1-z0)+row
            span=abs(pitch)-.042
            panel=Batch()
            # Open interlace is supported by actual timber dividers and its
            # shaped gold leaves. It remains an interpretation of the carving.
            for end in (-1,1):
                u=end*span/2
                panel.box((u,0,0),(.018,.046,.122),p.cinnabar)
            for lift in (-.064,.064):
                panel.box((0,0,lift),(span,.046,.020),p.old_gold)
            dragon(panel,(0,-.009,-.003),span*.93,.118,p,mirror=j%2==0,
                   detailed=True,z_relief=.008,phase=j*.24)
            for sign in (-1,1):
                cloud(panel,(sign*span*.277,-.009,0.),.074,p.old_gold,rotation=sign*j*.33)
            vertices=[(x-v,yy+u,zz+h+u*slope) for u,v,h in panel.v]
            for slot,mat in enumerate(panel.mats):
                b.add(vertices,[face for face,m in zip(panel.f,panel.mi) if m==slot],mat,smooth=True)
    for i,(yy,z) in enumerate(((y0,z0),(y1,z1))):
        b.box((x,yy,z+.326),(.137,.149,.652),p.cinnabar)
        b.lathe(x,yy,((.093,z+.630),(.085,z+.669),(.064,z+.698),(.082,z+.743),(.056,z+.831),(.018,z+.856)),p.gold,sides=19)
        for k in range(8):
            a=k*math.tau/8
            b.path([(x+r*math.cos(a),yy+r*math.sin(a),z+v) for r,v in ((.059,.703),(.090,.736),(.066,.784),(.039,.823))],
                   .008,p.old_gold,sides=7)
        if i==0:
            # The rail foot is a gilt animal-shaped support with a curled back.
            b.ellipsoid((x,yy-.095,z+.199),(.067,.100,.133),p.old_gold,sides=19,rings=10)
            b.ellipsoid((x,yy-.132,z+.330),(.069,.071,.077),p.gold,sides=18,rings=10)
            for s in (-1,1):
                b.rod((x+s*.043,yy-.136,z+.16),(x+s*.052,yy-.224,z+.058),.021,p.gold,sides=9)
                b.path([(x+s*.028,yy-.103,z+.36),(x+s*.064,yy-.081,z+.446),(x+s*.068,yy-.040,z+.471)],
                       .009,p.gold,sides=7)


def dais(loc,target,p):
    b,rails,small = (loc.batch() for _ in range(3))
    foot=DECK+.015; z=foot+DAIS_RISE
    b.box((0,4.57,foot+DAIS_RISE/2),(6.79,4.82,DAIS_RISE),p.lacquer)
    b.box((0,4.57,z+.013),(6.80,4.78,.027),p.carpet)
    for i,(x,w) in enumerate(((-2.22,1.55),(0.,1.85),(2.22,1.55))):
        step=loc.batch()
        run=(DAIS_Y-DAIS_FRONT)/DAIS_STEPS
        for j in range(DAIS_STEPS):
            y=DAIS_FRONT+(j+.5)*run; h=(j+1)*DAIS_RISE/DAIS_STEPS
            step.box((x,y,foot+h/2),(w,run+.004,h),p.rosewood)
            step.box((x,y-.004,foot+h+.010),(w-.017,run+.012,.023),p.carpet)
            step.rod((x-w*.493,y-run*.493,foot+h+.004),(x+w*.493,y-run*.493,foot+h+.004),.006,p.carpet,sides=9)
        step.finish('皇极殿 · 地平御阶 '+str(i+1),target,bevel=.009,
                    properties={'role':'huangji_dais_stair','riser_count':DAIS_STEPS,'source':STUDY})
        for s in (-1,1):
            x0=x+s*(w/2+.084)
            gold_rail(rails,x0,DAIS_FRONT-.13,DAIS_Y+.12,foot+.041,z,p)
    for sy in (-1,1):
        x=sy*3.18
        gold_rail(rails,x,DAIS_Y+.12,6.85,z,z,p)
    for yy in (DAIS_Y+.195,6.94):
        for x in (-3.05,-1.73,1.73,3.05):
            b.box((x,yy,foot+DAIS_RISE*.45),(.81,.059,.489),p.rosewood)
            frame(b,x,yy-.049,foot+DAIS_RISE*.45,.726,.415,.018,p.old_gold)
            cloud(b,(x,yy-.062,foot+DAIS_RISE*.45),.251,p.gold,rotation=x)
    b.finish('皇极殿 · 大地平漆木台身与地毯',target)
    dais_fascia(loc,target,p,foot,z)
    rails.finish('皇极殿 · 三路御阶朱栏与鎏金卷鬃栏首',target,bevel=.003)
    for zz,w,d,h,material in ((z+.117,2.48,1.97,.215,p.rosewood),(z+.231,2.57,2.04,.064,p.old_gold),
                              (z+.280,2.46,1.96,.059,p.lacquer),(z+.322,2.41,1.92,.028,p.dark_silk)):
        small.box((0,4.02,zz),(w,d,h),material)
    for j in range(9):
        cloud(small,((j-4)*.255,3.01,z+.148),.161,p.gold,rotation=j*.73)
    small.finish('皇极殿 · 宝座小地平和嵌金牙板',target)
    return z+.337


def dais_fascia(loc,target,p,floor,top):
    """Actual projecting cornices and shallow carved bands on the dais sides."""
    b=loc.batch()
    for side in (-1,1):
        x=side*3.409
        for lift,depth,height,material in ((.081,.090,.083,p.lacquer),(.179,.103,.058,p.old_gold),
                                          (.259,.119,.072,p.rosewood),(.742,.109,.098,p.rosewood),
                                          (.813,.126,.038,p.gold),(1.165,.124,.091,p.lacquer)):
            b.box((x,4.57,floor+lift),(depth,4.86,height),material)
        for center,height,key in ((floor+.424,.292,'huangji_dais_lower_fascia'),
                                   (floor+.987,.233,'huangji_dais_upper_fascia')):
            work=Batch()
            relief_panel(work,(0,0,center),4.74,height,image_surface(key,rough=.55,metal=.36),
                         ((0,0),(1,0),(1,1),(0,1)),nx=math.ceil(4.74/.007),ny=math.ceil(height/.007),depth=.022)
            for slot,material in enumerate(work.mats):
                b.add([(x-side*v,4.57+side*u,z) for u,v,z in work.v],
                      [face for face,mi in zip(work.f,work.mi) if mi==slot],material,smooth=True)
        for index in range(42):
            y=2.23+index*.114
            b.ellipsoid((x+side*.048,y,floor+.812),(.022,.043,.025),p.old_gold,sides=16,rings=9)
        for row in (.225,.680):
            for index in range(28):
                y=2.25+index*.171
                b.path([(x+side*(.053+.022*math.sin(a)),y+.058*math.cos(a),floor+row+.052*math.sin(a))
                        for a in (j*math.tau/32 for j in range(33))],.007,p.old_gold,sides=7)
    b.finish('皇极殿 · 地平束腰雕龙牙板、莲瓣与连珠',target,
             properties={'role':'huangji_dais_fascia','surface_source':'Sigoo throne_reference.jpg',
                         'max_projected_pitch_m':.007,'carved_depth_inferred_m':.022})


def chair_dragon(batch,x,y,z,height,p,mirror):
    """An independent coiling spindle, head, horns, scales and open claws."""
    sign=-1 if mirror else 1
    points=[]
    for i in range(91):
        t=i/90
        angle=t*math.tau*1.65
        points.append(Vector((x+sign*.062*math.sin(angle),y+.042*math.cos(angle),z+height*t)))
    batch.path(points,.026,p.old_gold,sides=14)
    for i in range(5,86,3):
        q=points[i]
        for j in (-1,0,1):
            batch.path([(q.x+j*.015+.010*math.cos(a),q.y-.025,q.z+.013*math.sin(a))
                        for a in (k*math.pi/7 for k in range(8))],.0028,p.gold,sides=5)
    q=points[-1]
    batch.ellipsoid(q+Vector((0,-.015,.024)),(.062,.048,.063),p.old_gold,sides=24,rings=14)
    batch.ellipsoid(q+Vector((sign*.025,-.061,.015)),(.055,.036,.025),p.gold,sides=22,rings=12)
    batch.ellipsoid(q+Vector((sign*.027,-.061,-.029)),(.054,.032,.014),p.old_gold,sides=20,rings=10)
    for k in range(5):
        x0=q.x-.035+k*.017
        batch.rod((x0,q.y-.077,q.z+.003),(x0,q.y-.077,q.z-.014),.005,p.gold,r1=.002,sides=8)
    for s in (-1,1):
        batch.ellipsoid(q+Vector((s*.041,-.047,.045)),(.012,.010,.010),p.rosewood,sides=12,rings=7)
        batch.path([q+Vector((s*.029,.004,.056)),q+Vector((s*.047,.017,.11)),
                    q+Vector((s*.070,.008,.133))],.008,p.gold,sides=10)
        batch.path([q+Vector((s*.031,-.061,.016)),q+Vector((s*.088,-.069,-.005)),
                    q+Vector((s*.113,-.056,.021))],.005,p.gold,sides=8)
        for fraction in (.31,.68):
            start=points[round(fraction*90)]
            wrist=start+Vector((s*.073,-.011,-.052))
            batch.path([start,start+Vector((s*.043,.014,-.036)),wrist],.014,p.old_gold,sides=10)
            for finger in range(4):
                batch.path([wrist,wrist+Vector((s*(.022+.008*finger),-.019,-.015*finger)),
                            wrist+Vector((s*(.039+.008*finger),-.034,.013-.017*finger))],.005,p.gold,sides=7)


def throne(loc,z,target,p):
    b=loc.batch(); cy=3.91
    for h,w,d,zth,m in ((.063,1.69,.949,.098,p.old_gold),(.153,1.67,.923,.082,p.faded_blue),
                         (.245,1.75,.993,.086,p.old_gold),(.396,1.72,.968,.115,p.giltpaint),(.491,1.53,.824,.068,p.lacquer)):
        b.box((0,cy,z+h),(w,d,zth),m)
    for j in range(11):
        cloud(b,((j-5)*.141,cy-.499,z+.154),.107,p.gold,rotation=j*2.68)
    for sx in (-1,1):
        for sy in (-1,1):
            xx=sx*.714; yy=cy+sy*.394
            b.ellipsoid((xx,yy,z+.111),(.103,.102,.061),p.gold,sides=16,rings=10)
            b.path([(xx,yy,z+.09),(xx-sx*.027,yy,z+.241),(xx,yy,z+.341)],.042,p.old_gold,sides=10)
        b.path([(sx*.727,cy-.423,z+.44),(sx*.797,cy-.435,z+.718),(sx*.754,cy-.236,z+.884),
                (sx*.653,cy+.28,z+.940)],.062,p.gold,sides=14)
        b.ellipsoid((sx*.774,cy-.489,z+.728),(.082,.121,.083),p.gold,sides=22,rings=12)
    for i in (-2,-1,0,1,2):
        height=(.71,.84,.99,.84,.71)[i+2]
        chair_dragon(b,i*.258,cy+.405,z+.515,height,p,i<0)
    b.path([(-.70,cy+.40,z+.507),(-.68,cy+.40,z+.98),(-.43,cy+.40,z+1.10),
            (0,cy+.40,z+1.28),(.43,cy+.40,z+1.10),(.68,cy+.40,z+.98),(.70,cy+.40,z+.507)],
           .023,p.old_gold,sides=12)
    b.box((0,cy+.414,z+.652),(1.29,.066,.092),p.faded_blue)
    relief_panel(b,(0,cy+.374,z+.652),1.23,.071,image_surface('huangji_throne_apron',rough=.47,metal=.35),
                 ((0,0),(1,0),(1,1),(0,1)),nx=186,ny=13,depth=.003)
    relief_panel(b,(0,cy-.507,z+.156),1.52,.169,image_surface('huangji_throne_apron',rough=.58,metal=.21),
                 ((0,0),(1,0),(1,1),(0,1)),nx=152,ny=17,depth=.006)
    frame(b,0,cy-.511,z+.156,1.58,.204,.028,p.old_gold)
    for s in (-1,1):
        dragon(b,(s*.490,cy-.476,z+.151),.308,.113,p,mirror=s<0,z_relief=.018,detailed=True)
        b.box((s*.741,cy-.466,z+.287),(.13,.042,.166),p.old_gold)
    for side in (-1,1):
        for sy in (-1,1):
            b.box((side*.291,cy-.846+sy*.151,z+.074),(.062,.062,.155),p.rosewood)
    b.box((0,cy-.856,z+.174),(.758,.423,.074),p.old_gold)
    b.finish('皇极殿 · 独立龙纹宝座、扶手与脚踏',target,bevel=.006,
             properties={'role':'huangji_throne','source':STUDY,'exact_carving_inferred':True})


def crest_relief(batch,center,width,height,index):
    """Give a photographed crest a closed editable relief and a shaped back."""
    folder=Path(__file__).resolve().parent/'references/ning_shou_court'
    with np.load(folder/f'huangji_screen_crest_{index}.npz',allow_pickle=False) as data:
        image_mask=data['mask'][::-1]
        height_map=data['relief'][::-1]
        fine_relief=data['fine_relief'][::-1]
    nx,nz=math.ceil(width/.0045),math.ceil(height/.0045)
    u,v=np.meshgrid(np.linspace(0,1,nx+1),np.linspace(0,1,nz+1))
    image_x=np.rint(u*(image_mask.shape[1]-1)).astype(int)
    image_y=np.rint(v*(image_mask.shape[0]-1)).astype(int)
    mask=image_mask[image_y,image_x]
    active=mask[:-1,:-1]&mask[1:,:-1]&mask[:-1,1:]&mask[1:,1:]
    xx,yy,zz=center
    topography=.024+.047*height_map[image_y,image_x]+.035*fine_relief[image_y,image_x]
    front=np.stack((xx+(u-.5)*width,yy-topography,zz+(v-.5)*height),axis=-1).reshape(-1,3)
    back=np.stack((xx+(u-.5)*width,np.full_like(u,yy+.026),zz+(v-.5)*height),axis=-1).reshape(-1,3)
    count=len(front)
    faces=[]
    for row,column in zip(*np.nonzero(active)):
        a=row*(nx+1)+column
        ring=(a,a+1,a+nx+2,a+nx+1)
        faces.extend((ring,tuple(i+count for i in reversed(ring))))
        for dr,dc,start,end in ((-1,0,ring[0],ring[1]),(0,1,ring[1],ring[2]),
                                (1,0,ring[2],ring[3]),(0,-1,ring[3],ring[0])):
            r,c=row+dr,column+dc
            if r<0 or c<0 or r>=nz or c>=nx or not active[r,c]:
                faces.append((start,start+count,end+count,end))
    coordinates=np.concatenate((front,back))
    uv=np.concatenate((np.stack((u,v),axis=-1).reshape(-1,2),)*2)
    used=np.unique(np.array([vertex for face in faces for vertex in face],dtype=np.int32))
    remap=np.full(len(coordinates),-1,np.int32); remap[used]=np.arange(len(used))
    batch.add(coordinates[used],[tuple(int(remap[v]) for v in face) for face in faces],
              image_surface(f'huangji_screen_crest_{index}',rough=.40,metal=.46),uv=uv[used],smooth=True)


def screen(loc,z,target,p):
    yy=5.17
    widths=(.62,.695,.772,1.138,.772,.695,.62)
    heights=(2.34,2.65,2.95,3.20,2.95,2.65,2.34)
    start=-sum(widths)/2
    for index,(w,h) in enumerate(zip(widths,heights),1):
        b=loc.batch(); x=start+w/2; zz=z+h/2-.198
        b.box((x,yy,zz),(w-.012,.169,h),p.lacquer)
        b.box((x,yy-.097,zz),(w-.081,.033,h-.287),p.rosewood)
        for margin,material in ((.095,p.old_gold),(.152,p.giltpaint)):
            frame(b,x,yy-.132,zz,w-margin,h-margin*1.89,.028,material)
        field=(1,2,3,4,3,2,1)[index-1]
        material=image_surface(f'huangji_carved_screen_{field}',rough=.53,metal=.34)
        for fraction,h_fraction in ((.142,.112),(.555,.65),(.915,.066)):
            zc=z-.198+h*fraction; height=h*h_fraction
            frame(b,x,yy-.151,zc,w-.181,height,.021,p.old_gold)
            relief_panel(b,(x,yy-.141,zc),w-.215,height-.052,material,
                         ((0,0),(1,0),(1,1),(0,1)),nx=max(16,math.ceil((w-.215)/.0065)),
                         ny=max(12,math.ceil((height-.052)/.0065)),depth=.012)
        outline=[(x-w*.511,z+h-.160),(x-w*.44,z+h+.049),(x-w*.24,z+h+.041),(x-w*.181,z+h+.181),
                 (x,z+h+.227),(x+w*.181,z+h+.181),(x+w*.24,z+h+.041),(x+w*.44,z+h+.049),(x+w*.511,z+h-.160)]
        for y in (yy-.128,yy-.169):
            b.path([(a,y,c) for a,c in outline],.027 if y>yy-.16 else .014,p.gold,sides=9)
        crest_relief(b,(x,yy-.183,z+h+.155),w*1.075,max(.418,w*.57),field)
        b.finish(f'皇极殿 · 七扇金漆围屏 {index}',target,bevel=.002,properties={'role':'huangji_screen_leaf','leaf':index,'source':STUDY,
                 'fine_pattern_source':'Sigoo public interior panorama','max_projected_panel_pitch_m':.0065,
                 'depth_inferred_m':.012,'occluded_pattern_assignment':field})
        start+=w
    backdrop=loc.batch(); by=5.91
    backdrop.box((0,by,4.75),(6.24,.28,5.73),p.lacquer)
    for side in (-1,1):
        backdrop.box((side*2.92,by-.176,4.55),(.284,.056,5.20),p.faded_blue)
        for j in range(13):
            cloud(backdrop,(side*2.92,by-.215,2.31+.365*j),.205,p.giltpaint,rotation=side*j*.46)
    w,h,cz=5.41,1.20,7.21
    frame(backdrop,0,by-.156,cz,w+.18,h+.16,.061,p.old_gold)
    backdrop.face(((-w/2,by-.175,cz-h/2),(w/2,by-.175,cz-h/2),
                   (w/2,by-.175,cz+h/2),(-w/2,by-.175,cz+h/2)),image_surface('huangji_screen_band'),
                  uv=((0,0),(1,0),(1,1),(0,1)))
    inscription(backdrop,0,by-.19,8.46,3.21,1.05,p,'renshou_inscription',painted=True)
    for side,key in ((-1,'huangji_couplet_left'),(1,'huangji_couplet_right')):
        x=side*3.20; y=by-.189; z0,z1=3.49,7.80; w=.395
        backdrop.box((x,y,(z0+z1)/2),(w+.12,.134,z1-z0+.11),p.rosewood)
        frame(backdrop,x,y-.078,(z0+z1)/2,w+.024,z1-z0+.024,.029,p.old_gold)
        backdrop.face(((x-w/2,y-.085,z0),(x+w/2,y-.085,z0),(x+w/2,y-.085,z1),(x-w/2,y-.085,z1)),
                      image_surface(key,rough=.76),uv=((0,0),(1,0),(1,1),(0,1)))
    backdrop.finish('皇极殿 · 后屏双龙、楹架与仁德大隆匾',target,
                    properties={'role':'huangji_throne_plaque','inscription':'仁德大隆','source':STUDY})


def painted_coffer(batch,x,y,z,width,depth,p,index):
    batch.box((x,y,z+.041),(width+.021,depth+.021,.084),p.faded_teal)
    for sign in (-1,1):
        batch.box((x+sign*(width/2-.037),y,z-.006),(.068,depth,.026),p.faded_teal)
        batch.box((x,y+sign*(depth/2-.037),z-.006),(width,.068,.026),p.faded_teal)
        batch.box((x+sign*(width/2-.080),y,z-.018),(.012,depth-.141,.014),p.cream)
        batch.box((x,y+sign*(depth/2-.080),z-.018),(width-.141,.012,.014),p.cream)
    w,d=width/2-.045,depth/2-.045
    material=image_surface(f'huangji_ceiling_roundel_{index%4+1}',rough=.82,metal=.04)
    batch.face(((x-w,y-d,z-.019),(x-w,y+d,z-.019),(x+w,y+d,z-.019),(x+w,y-d,z-.019)),material,
               uv=((0,0),(0,1),(1,1),(1,0)))


def ceiling(loc,target,p,*,rear=False):
    b=loc.batch()
    xs,ys=(REAR_X,REAR_Y) if rear else (MAIN_X,MAIN_Y)
    blue=6.42 if rear else 6.72
    x0,x1=xs[0]+.16,xs[-1]-.16; y0,y1=ys[1]+.016,ys[-1]-.064
    parts=[(box(x0,y0,x1,y1),blue)] if rear else [(box(x0,y0,-9.12,y1),blue),(box(9.12,y0,x1,y1),blue),
                                                  (box(-9.12,y0,9.12,y1),SOFFIT)]
    if not rear:
        gap=box(-CAISSON_OUTER/2,CAISSON_Y-CAISSON_OUTER/2,CAISSON_OUTER/2,CAISSON_Y+CAISSON_OUTER/2)
    for i,(area,z) in enumerate(parts):
        a,c,d,e=area.bounds; count=max(1,round((d-a)/.92)); rows=round((e-c)/.92)
        for j in range(rows):
            for k in range(count):
                w,h=(d-a)/count,(e-c)/rows
                panel=box(a+k*w,c+j*h,a+(k+1)*w,c+(j+1)*h)
                if not rear and i==2 and panel.intersects(gap):
                    b.solid_xy(panel.difference(gap),z,z+.079,p.faded_teal,bottom=True)
                    continue
                x,y=panel.centroid.coords[0]
                if rear:
                    ceiling_tile(b,x,y,z,w-.024,h-.024,p,'flowers',j+k)
                else:
                    painted_coffer(b,x,y,z,w-.024,h-.024,p,j*7+k*3)
                if rear:
                    rr=min(w,h)*.16
                    b.path([(x+rr*math.cos(a),y+rr*math.sin(a),z-.048) for a in (i*math.tau/27 for i in range(28))],
                           .0062,p.giltpaint,sides=5)
                    for j in (-1,1):
                        b.path([(x+j*(.12+k*.027),y+.042*math.sin(k*.61),z-.044) for k in range(10)],.008,p.old_gold,sides=6)
    if not rear:
        for side in (-1,1):
            b.box((side*9.12,(y0+y1)/2,(blue+SOFFIT)/2),(.225,y1-y0,SOFFIT-blue),p.fascia)
            for j in range(3):
                y=y0+(j+.5)*(y1-y0)/3
                painted_bay(b,side*9.12,y,SOFFIT-.34,(y1-y0)/3-.022,p,yaw=math.pi/2,height=.413)
    label='宁寿宫' if rear else '皇极殿'
    b.finish(label+' · 分格井口天花与梁底',target,properties={'ceiling_kind':'square_panels','height_m':blue})
    if rear:
        return
    b=loc.batch(); y=CAISSON_Y
    def octagon(r):
        return Polygon([(u,y+v) for u,v in ring_outline(r)])
    def beam_outline(coords,z,r,mat):
        b.path([(x,yy,z) for x,yy in coords],r,mat,sides=9)
    outer=box(-CAISSON_OUTER/2,y-CAISSON_OUTER/2,CAISSON_OUTER/2,y+CAISSON_OUTER/2)
    cut=octagon(2.21)
    b.solid_xy(outer.difference(cut),SOFFIT-.081,SOFFIT+.083,p.old_gold,bottom=True)
    beam_outline(outer.exterior.coords,SOFFIT-.087,.067,p.gold)
    for scale,angle,z in ((.474,0.,SOFFIT-.096),(.326,math.pi/4,SOFFIT-.106),(.386,0.,SOFFIT-.114)):
        h=CAISSON_OUTER*scale
        square=[(h*math.cos(angle)*i-h*math.sin(angle)*j,y+h*math.sin(angle)*i+h*math.cos(angle)*j)
                for i,j in ((-1,-1),(1,-1),(1,1),(-1,1),(-1,-1))]
        for a,c in zip(square,square[1:]):
            if math.dist(a,c)<.1:
                continue
            b.beam((*a,z),(*c,z),.069,.081,p.old_gold)
            b.path([(*a,z-.049),(*c,z-.049)],.015,p.gold,sides=8)
            for m in range(13):
                t=(m+.5)/13
                xx,yy=a[0]+(c[0]-a[0])*t,a[1]+(c[1]-a[1])*t
                if abs(xx)<2.31 and abs(yy-y)<2.31:
                    cloud(b,(xx,yy,z-.050),.099,p.giltpaint,facing='down',rotation=m*.91)
    for j in range(5):
        outside=octagon(2.21-j*.199); inside=octagon(2.21-(j+1)*.199)
        z=SOFFIT+.155*j
        b.solid_xy(outside.difference(inside),z,z+.178,p.old_gold,bottom=True)
        beam_outline(outside.exterior.coords,z-.019,.028,p.gold)
        for i in range(8):
            a=(i+.5)*math.tau/8
            for n in range(-5,6):
                r=2.085-j*.184; delta=n*(.128-.006*j)
                x=(r*math.cos(a)-delta*math.sin(a)); yy=y+r*math.sin(a)+delta*math.cos(a)
                cloud(b,(x,yy,z-.021),.123,p.giltpaint,facing='down',rotation=i*.75+n*.34)
    top=SOFFIT+.794
    b.solid_xy(octagon(1.218),top,top+.135,p.old_gold,bottom=True)
    for rr in (.46,.91,1.13):
        beam_outline([(rr*math.cos(a),y+rr*math.sin(a)) for a in (i*math.tau/72 for i in range(73))],top-.017,.027,p.old_gold)
    add_caisson_details(b,y,SOFFIT,CAISSON_OUTER,p)
    hanging_pearl(b,y,SOFFIT,p)
    b.finish('皇极殿 · 八角抹角藻井、盘龙与垂珠',target,bevel=.004,
             properties={'role':'huangji_caisson','side_count':8,'ceiling_z_m':SOFFIT,'aperture_width_m':CAISSON_OUTER,
                         'source':STUDY,'detail_reference':'Sigoo cube u, level 5, local cropped atlas',
                         'sampled_disk_pitch_m':.0065,'surface_depth_inferred':True,
                         'pearl_occlusion':'Hidden part of the dragon field repeated from the unobstructed sector.'})


def devices(loc,target,p):
    for i,x in enumerate((-16.53,-12.04,12.04,16.53),1):
        b=loc.batch(); yy=8.09; w=2.21
        for sx in (-1,1):
            for sy in (-1,1):
                b.box((x+sx*w*.46,yy+sy*.286,DECK+.194),(.119,.119,.396),p.rosewood)
            b.box((x+sx*w*.46,yy,DECK+1.827),(.121,.595,3.00),p.rosewood)
        b.box((x,yy+.256,DECK+1.773),(w,.083,2.98),p.rosewood)
        for j in range(6):
            b.box((x,yy-.006,DECK+.395+j*.565),(w,.625,.079),p.rosewood)
        b.finish('皇极殿 · 后檐书格 '+str(i),target,bevel=.004,properties={'role':'huangji_shelf','positions_inferred':True})
    b=loc.batch(); x,y=-6.19,4.28
    for j in range(4):
        z=DECK+.43+j*.457; rr=.286-j*.029
        b.lathe(x,y,((rr*.69,z-.09),(rr*.92,z),(rr,z+.27),(rr*.93,z+.34),(rr*.70,z+.345),(rr*.65,z+.253)),p.bronze,sides=40)
        b.path([(x+rr*.56,y-.183,z-.021),(x+rr*.77,y-.41,z-.048),(x+rr*.67,y-.449,z-.141)],.019,p.old_gold,sides=10)
    for sy in (-1,1):
        b.box((x, y+sy*.29,DECK+1.104),(.718,.048,2.28),p.rosewood)
    b.box((x,y,DECK+.111),(.98,.78,.213),p.rosewood)
    b.finish('皇极殿 · 铜壶滴漏与分层支架',target,properties={'role':'water_clock','presence_documented':True,'form_inferred':True})
    b=loc.batch(); x,y=6.19,4.28
    b.box((x,y,DECK+1.32),(.67,.412,2.68),p.rosewood)
    for i in range(4):
        b.box((x,y-.01,DECK+.081+i*.047),(.87-i*.041,.54-i*.033,.046),p.lacquer)
    b.lathe(x,y,((.325,DECK+2.643),(.331,DECK+2.715),(.143,DECK+2.890),(.072,DECK+2.964),(.018,DECK+3.002)),p.rosewood,sides=24)
    face=Vector((x,y-.230,DECK+2.237)); sy=Vector((0,-1,0))
    b.rod(face-sy*.019,face+sy*.020,.245,p.giltpaint,sides=72)
    b.rod(face+sy*.021,face+sy*.023,.209,p.cream,sides=72)
    for i in range(60):
        a=i*math.tau/60; radial=Vector((math.sin(a),0,math.cos(a)))
        b.rod(face+sy*.026+radial*.193,face+sy*.026+radial*(.168 if i%5==0 else .180),.0036,p.inset,sides=6)
    for a,r in ((.69,.133),(1.94,.171)):
        b.rod(face+sy*.035,face+sy*.035+Vector((math.sin(a)*r,0,math.cos(a)*r)),.006,p.inset,r1=.003,sides=8)
    b.finish('皇极殿 · 大自鸣钟、刻度与外壳',target,properties={'role':'striking_clock','presence_documented':True,'form_inferred':True})
    for i,x in enumerate((-4.24,4.24),1):
        b=loc.batch(); y=1.67
        b.lathe(x,y,((.239,DECK+.017),(.252,DECK+.098),(.177,DECK+.248),(.389,DECK+.378),(.417,DECK+.506),
                     (.388,DECK+.588),(.297,DECK+.707),(.120,DECK+.838),(.051,DECK+.862)),p.bronze,sides=62)
        for j in range(28):
            a=j*math.tau/28
            for rad,z in ((.379,DECK+.593),(.285,DECK+.723),(.184,DECK+.797)):
                b.ellipsoid((x+rad*math.cos(a),y+rad*math.sin(a),z),(.022,.022,.024),p.old_gold,sides=8,rings=5)
        b.finish('皇极殿 · 铜熏炉 '+str(i),target,properties={'positions_inferred':True})


def rear_rooms(loc,target,p):
    room=collection('宁寿宫后殿 · 历史室内陈设研究',target)
    room['display_state']='Historical typological reconstruction. It does not reproduce the present museum gallery installation.'
    room['source']=REAR_SOURCE
    b, wood = loc.batch(), loc.batch()
    z=DECK+.012
    for x,y0,y1 in ((3.41,-3.94,6.28),(16.03,-3.94,6.28),(-3.43,-3.94,6.28)):
        for a,c in ((y0,.122),(2.83,y1)):
            b.box((x,(a+c)/2,z+2.22),(.171,c-a,4.44),p.lacquer)
            for j in range(4):
                u=a+(j+.5)*(c-a)/4
                b.box((x+.113,u,z+2.27),(.063,.087,4.39),p.fascia)
    # Three connected western bays with a wrapped heated platform.
    for x,y,w,d in ((-17.05,4.96,9.16,2.72),(-19.81,.58,3.68,6.67),(-11.87,2.98,2.28,1.28)):
        b.box((x,y,z+.274),(w,d,.549),p.understone)
        b.box((x,y,z+.563),(w+.04,d+.045,.063),p.rosewood)
        wood.box((x,y,z+.614),(w-.10,d-.12,.049),p.dark_silk)
    for j in range(7):
        x=-19.78+j*1.02; y=5.68
        wood.box((x,y,z+.945),(.302,.202,.680),p.rosewood)
        wood.box((x,y-.113,z+.992),(.244,.032,.529),p.lacquer)
        frame(wood,x,y-.133,z+.992,.218,.483,.019,p.giltpaint)
    for x in (-15.69,-14.40):
        wood.lathe(x,4.55,((.153,z+.646),(.157,z+.733),(.128,z+.902),(.206,z+1.05),(.174,z+1.137)),p.bronze,sides=35)
    # Documented kitchen behind the entry and the connected eastern rooms.
    b.box((6.86,5.35,z+.60),(3.15,1.81,1.20),p.lightjade)
    for x in (6.16,7.57):
        b.lathe(x,5.41,((.255,z+1.194),(.420,z+1.237),(.471,z+1.368),(.453,z+1.391),(.408,z+1.38),(.229,z+1.23)),p.bronze,sides=60)
    for x in (9.11,14.14):
        wood.box((x,4.20,z+.328),(3.68,2.88,.65),p.rosewood)
        wood.box((x,4.20,z+.692),(3.52,2.73,.135),p.cushion)
        for sy in (-1,1):
            for sx in (-1,1):
                wood.box((x+sx*1.71,4.20+sy*1.33,z+1.31),(.093,.093,2.60),p.lacquer)
        wood.box((x,4.20,z+2.63),(3.78,3.01,.103),p.rosewood)
        for k in (-1.,0.,1.):
            wood.ellipsoid((x+k*.91,5.01,z+.805),(.395,.354,.138),p.cushion,sides=19,rings=9)
    b.finish('宁寿宫 · 祭祀间、炕台、隔间与锅灶',room,properties={'role':'historical_rear_rooms','source':REAR_SOURCE})
    wood.finish('宁寿宫 · 祭位陈设及东屋木榻',room)
    chimney=loc.batch()
    for sign in (-1,1):
        x=sign*17.91; y=10.04
        chimney.box((x,y,1.13),(.834,.810,2.249),p.lightjade)
        chimney.box((x,y,2.31),(.909,.887,.126),p.understone)
        chimney.box((x,y,2.44),(.682,.668,.176),p.bronze)
        chimney.lathe(x,y,((.466,2.531),(.434,2.562),(.30,2.673),(.073,2.762)),p.bronze,sides=4)
    chimney.finish('宁寿宫 · 殿后东西砖烟囱与铜帽',target,properties={'role':'rear_chimneys','count':2,'source':REAR_SOURCE})


def build_interiors(main,rear,groups,p):
    dark_wood(p)
    front=collection('皇极殿 · 七级地平、宝座及藻井',groups[0])
    gilt_columns(main.loc,front,p)
    z=dais(main.loc,front,p)
    throne(main.loc,z,front,p)
    screen(main.loc,z,front,p)
    stairs=collection('皇极殿 · 日常陈设与井口天花',groups[0])
    ceiling(main.loc,stairs,p)
    devices(main.loc,stairs,p)
    build_elephants(main.loc,stairs,p)
    ceiling(rear.loc,groups[1],p,rear=True)
    rear_rooms(rear.loc,groups[1],p)
