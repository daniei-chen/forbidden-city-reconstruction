"""Editable liturgical furnishings arranged using Qin'an's published object catalogue."""
import math
from types import SimpleNamespace

from architectural_roofs import swept_roof
from carved_ornament import cloud
from garden_bridge_pavilions import flower, transfer
from mesh_tools import Batch, collection
from palace_materials import paint
from qinan_hall import plaque, text_mesh
from qinan_survey import FLOOR, INTERIOR_SOURCE


def palette(base):
    p=SimpleNamespace(**base.__dict__)
    p.brocade=paint('钦安殿 · 暗墨绿织金袍',(.017,.036,.031),second=(.078,.105,.065),scale=11.,rough=.86,grain=157,bump=.004)
    p.silk=paint('钦安殿 · 织锦霞帔',(.143,.029,.018),second=(.455,.126,.054),scale=12.,rough=.79,grain=132,bump=.004)
    p.ceramic=paint('钦安殿 · 深青釉供器',(.017,.068,.048),second=(.059,.186,.147),scale=11.,rough=.33,grain=107,bump=.0015,coat=.26)
    p.flesh=paint('钦安殿 · 木胎朱砂泥金面',(.193,.088,.031),second=(.519,.351,.150),scale=14.,rough=.54,grain=122,bump=.005,metal=.42)
    p.redwood=paint('钦安殿 · 旧朱漆供案',(.118,.023,.012),second=(.282,.057,.026),scale=8.3,rough=.58,grain=123,bump=.003,coat=.13)
    return p


def foil_outline(b,x,y,z,w,h,p):
    b.path([(x-w/2,y,z),(x+w/2,y,z),(x+w/2,y,z+h),(x-w/2,y,z+h),(x-w/2,y,z)],
           .012,p.old_gold,sides=6)
    for sign in (-1,1):
        cloud(b,(x+sign*w*.38,y+.003,z+h*.50),h*.54,p.giltpaint,rotation=sign*2.2)


def drape(b,x,y,z,profile,p,*,side=0.,pleats=11,bands=True):
    """A mesh with fold depth that changes from shoulder to hem."""
    n=72
    points=[];quads=[]
    for i,(height,rx,ry,dy) in enumerate(profile):
        for j in range(n):
            a=j*math.tau/n
            wrinkle=(.065*math.sin(pleats*a+i*.59)+.032*math.sin(17*a+i*.42))*(1.08-i/(len(profile)+2))
            rr=1+wrinkle
            points.append((x+rx*rr*math.cos(a)+side*height,y+dy+ry*rr*math.sin(a),
                           z+height+.011*math.sin(a*pleats)*max(0,1-i/3)))
        if i:
            quads.extend(((i-1)*n+j,(i-1)*n+(j+1)%n,i*n+(j+1)%n,i*n+j) for j in range(n))
    quads.extend((tuple(reversed(range(n))),tuple(range(len(points)-n,len(points)))))
    b.add(points,quads,p.brocade,smooth=True)
    if bands:
        for i in range(min(4,len(profile))):
            band=[(a*1.009-.009*x,c*1.019-.019*y,k+.017) for a,c,k in points[i*n:(i+1)*n]]
            b.path(band+[band[0]],.0065,p.old_gold,sides=6)
        for j in range(n//2+4,n-3,4):
            b.path([(points[i*n+j][0],points[i*n+j][1]-.005,points[i*n+j][2])
                    for i in range(1,len(profile))],.0049,p.silk if j%3 else p.giltpaint,sides=5)


def portrait(b,x,y,z,s,p,*,crown=True):
    b.ellipsoid((x,y,z),(.116*s,.098*s,.166*s),p.flesh,sides=30,rings=18)
    b.ellipsoid((x,y-.053*s,z-.052*s),(.077*s,.052*s,.095*s),p.flesh,sides=22,rings=14)
    b.ellipsoid((x,y-.102*s,z-.014*s),(.023*s,.029*s,.050*s),p.flesh,sides=20,rings=13)
    for sign in (-1,1):
        dx=sign*.049*s
        b.ellipsoid((x+dx,y-.090*s,z+.023*s),(.026*s,.011*s,.009*s),p.lacquer,sides=14,rings=8)
        b.path([(x+dx*.55,y-.095*s,z+.053*s),(x+dx,y-.095*s,z+.065*s),
                (x+dx*1.53,y-.076*s,z+.053*s)],.007*s,p.lacquer,sides=7)
        b.ellipsoid((x+sign*.113*s,y-.008*s,z-.025*s),(.023*s,.024*s,.046*s),p.flesh,sides=19,rings=11)
        b.path([(x,y-.105*s,z-.064*s),(x+sign*.043*s,y-.103*s,z-.074*s),
                (x+sign*.051*s,y-.090*s,z-.106*s)],.0083*s,p.lacquer,sides=7)
    b.path([(x-.021*s,y-.107*s,z-.083*s),(x,y-.113*s,z-.09*s),(x+.022*s,y-.107*s,z-.083*s)],.0075*s,p.silk,sides=7)
    if crown:
        b.lathe(x,y,((.107*s,z+.090*s),(.129*s,z+.118*s),(.118*s,z+.142*s),
                     (.116*s,z+.194*s),(.092*s,z+.229*s),(.077*s,z+.254*s)),p.lacquer,sides=28)
        for i in (-2,-1,0,1,2):
            px=x+i*.038*s
            b.ellipsoid((px,y-.105*s,z+(.192-.013*abs(i))*s),(.018*s,.017*s,.030*s),p.old_gold,sides=13,rings=8)
            b.path([(px,y-.095*s,z+.154*s),(px,y-.095*s,z+.221*s),(px+i*.010*s,y-.082*s,z+.247*s)],
                   .007*s,p.giltpaint,sides=6)


def seated(b,x,y,z,s,p):
    b.box((x,y+.003,z+.124*s),(1.28*s,.856*s,.22*s),p.lacquer)
    foil_outline(b,x,y-.437*s,z+.062*s,1.22*s,.13*s,p)
    profile=((.24,.52,.37,-.045),(.34,.53,.40,-.05),(.42,.52,.39,-.043),(.54,.493,.38,-.019),
             (.67,.423,.31,.03),(.82,.32,.24,.07),(.96,.296,.206,.091),(1.105,.263,.183,.102),
             (1.22,.277,.176,.108),(1.327,.181,.141,.110),(1.382,.104,.093,.108))
    drape(b,x,y,z,[(h*s,a*s,c*s,d*s) for h,a,c,d in profile],p)
    portrait(b,x,y+.105*s,z+1.494*s,1.07*s,p)
    for sign in (-1,1):
        b.path([(x+sign*.217*s,y+.012*s,z+1.247*s),(x+sign*.29*s,y-.036*s,z+1.08*s),
                (x+sign*.357*s,y-.249*s,z+.888*s)],.118*s,p.brocade,sides=16)
        b.ellipsoid((x+sign*.357*s,y-.277*s,z+.869*s),(.079*s,.105*s,.057*s),p.old_gold,sides=20,rings=12)
        b.path([(x+sign*.025*s,y-.081*s,z+1.353*s),(x+sign*.114*s,y-.069*s,z+1.259*s),
                (x+sign*.115*s,y-.109*s,z+1.095*s),(x+sign*.228*s,y-.177*s,z+.917*s),
                (x+sign*.289*s,y-.292*s,z+.734*s)],.022*s,p.silk,sides=10)
        for j in range(10):
            u=x+sign*(.09+.028*j)*s
            cloud(b,(u,y-(.36-.071*math.sin(j*.97))*s,z+(.40+.036*j)*s),.119*s,p.giltpaint,rotation=j*.86)
    for j in range(4):
        cloud(b,(x+(j-1.5)*.141*s,y-.248*s,z+(.70+.041*j)*s),.132*s,p.old_gold)


def attendant(b,x,y,z,s,p,kind):
    b.lathe(x,y,((.121*s,z),(.146*s,z+.035*s),(.134*s,z+.074*s)),p.understone,sides=16)
    profile=((.07,.135,.096,0),(.22,.137,.091,0),(.44,.130,.093,.014),(.66,.142,.083,.015),
             (.85,.111,.071,.016),(.99,.146,.084,.018),(1.108,.075,.052,.009))
    drape(b,x,y,z,[(h*s,w*s,d*s,v*s) for h,w,d,v in profile],p,side=.019*(-1 if kind%2 else 1),pleats=9)
    portrait(b,x+.02*s,y,z+1.222*s,.48*s,p,crown=True)
    b.path([(x+.09*s,y-.031*s,z+.982*s),(x+.12*s,y-.102*s,z+.837*s),
            (x-.037*s,y-.126*s,z+.794*s)],.042*s,p.flesh,sides=10)
    for j in range(3):
        cloud(b,(x,y-.089*s,z+(.24+j*.25)*s),.103*s,p.old_gold,rotation=j*1.2)


def tablet(b,x,y,z,s,p):
    for dz,w,d,h,mat in ((.026,.31,.20,.052,p.lacquer),(.098,.252,.152,.101,p.redwood),
                          (.198,.227,.121,.089,p.old_gold),(.493,.167,.054,.59,p.lacquer)):
        b.box((x,y,z+dz*s),(w*s,d*s,h*s),mat)
    foil_outline(b,x,y-.034*s,z+.228*s,.148*s,.513*s,p)
    for j in range(4):
        cloud(b,(x,y-.040*s,z+(.30+j*.116)*s),.065*s,p.old_gold,rotation=.81*j)


def hood(b,x,y,z,w,d,p,tall):
    red=p.redwood
    for h,pad,mat in ((.0,.06,p.old_gold),(.07,0.,p.lacquer),(.18,-.097,red),(.267,.008,p.old_gold)):
        b.box((x,y,z+h),(w+pad,d+pad,.108),mat)
    if tall:
        for side in (-1,1):
            b.box((x+side*(w/2-.07),y,z+.505),(.11,d*.86,.42),p.lacquer)
    for i in range(max(4,round(w/.105))):
        xx=x+w*((i+.5)/round(w/.105)-.5)
        b.ellipsoid((xx,y-d*.51,z+.176),(.026,.019,.021),p.old_gold,sides=10,rings=7)
        for sign in (-1,1):
            b.path([(xx+sign*.039,y-d*.51,z+.108),(xx+sign*.016,y-d*.52,z+.146),
                    (xx+sign*.041,y-d*.52,z+.214)],.007,p.giltpaint,sides=6)


def altar(b,x,y,z,w,d,h,p):
    b.box((x,y,z+h-.057),(w+.085,d+.079,.116),p.redwood)
    b.box((x,y,z+h-.168),(w,.966*d,.133),p.lacquer)
    for sign in (-1,1):
        for jy in (-1,1):
            xx=x+sign*(w/2-.16);yy=y+jy*(d/2-.112)
            b.path([(xx,yy,z+h-.12),(xx-sign*.055,yy,z+h*.56),
                    (xx-sign*.008,yy,z+.153),(xx+sign*.041,yy,z+.051)],.056,p.redwood,sides=10)
            b.ellipsoid((xx+sign*.041,yy,z+.065),(.084,.073,.051),p.lacquer,sides=13,rings=7)
    foil_outline(b,x,y-d*.486,z+h-.229,w-.15,.124,p)
    for k in (j*.143 for j in range(-math.floor(w/.29),math.floor(w/.29)+1)):
        cloud(b,(x+k,y-d*.487,z+h-.176),.118,p.old_gold,rotation=k*1.04)
    b.box((x,y,z+.32*h),(w-.30,.064,.064),p.fascia)


def vessel(b,x,y,z,s,p,kind):
    mat=p.bronze if kind in ('censer','lamp') else p.ceramic
    if kind=='censer':
        profile=((.11,0),(.137,.05),(.17,.117),(.192,.222),(.185,.263),(.195,.28),(.174,.301),(.147,.28),(.142,.24))
    elif kind=='bowl':
        profile=((.066,0),(.067,.033),(.094,.057),(.129,.101),(.139,.143),(.129,.151),(.123,.127),(.087,.060))
    elif kind=='lamp':
        profile=((.111,0),(.113,.035),(.047,.073),(.043,.25),(.092,.285),(.101,.313),(.087,.345),(.064,.307))
    else:
        profile=((.109,0),(.12,.034),(.123,.102),(.150,.188),(.131,.278),(.080,.349),(.070,.411),
                 (.108,.456),(.100,.483),(.082,.472),(.049,.418))
    b.lathe(x,y,[(r*s,z+h*s) for r,h in profile],mat,sides=32)
    if kind=='censer':
        for sign in (-1,1):
            b.path([(x+sign*.151*s,y,z+.175*s),(x+sign*.253*s,y,z+.233*s),
                    (x+sign*.180*s,y,z+.328*s)],.022*s,p.bronze,sides=9)
    elif kind=='lamp':
        b.rod((x,y,z+.313*s),(x+.004*s,y,z+.379*s),.009*s,p.door,sides=7)


def shrine(loc,target,p,name,x,y,w,d,h,kind,index):
    group=collection('钦安殿 陈设 · '+name,target)
    b,figures,offers=(loc.batch() for _ in range(3))
    bottom=FLOOR+.20
    z=bottom+.36
    depth=d/2
    a=p.lacquer if kind in ('season','warrior') else p.redwood
    b.box((x,y,bottom+.112),(w+.066,d+.02,.235),p.understone)
    b.box((x,y,z-.072),(w,d,.155),a)
    b.box((x,y+depth-.05,z+h*.492),(w,.105,h),a)
    for sign in (-1,1):
        px=x+sign*(w/2-.095)
        b.box((px,y,z+h*.506),(.127,d,h),a)
        b.path([(px,y-depth-.022,z+.013),(px,y-depth-.022,z+h-.012)],.025,p.old_gold,sides=8)
        for i in range(6 if kind=='central' else 3):
            cloud(b,(px,y-depth-.03,z+(i+.7)*h/(6.3 if kind=='central' else 3.3)),.183,p.giltpaint,rotation=sign*i)
        if kind in ('central','large','tiered'):
            folds=12;curtain=[]
            for j in range(folds+1):
                t=j/folds
                xx=px-sign*t*w*.275
                yy=y-depth-.016+.038*math.sin(t*math.tau*8)
                curtain.append((xx,yy,z+h*(.34+.56*t**.63)))
            b.face([(xx,yy,z+h*.87) for xx,yy,zz in curtain]+list(reversed(curtain)),p.silk)
            b.path(curtain,.014,p.giltpaint,sides=7)
            for j in range(8):
                t=(j+.3)/8;xx=px-sign*w*.24*t
                hh=z+h*(.42+.49*t**.63)
                b.path([(xx,y-depth-.032,hh),(xx-sign*.021,y-depth-.043,hh-.092)],.012,p.old_gold,sides=6)
    hood(b,x,y,z+h,w,d,p,kind=='tiered')
    if kind=='tiered':
        # Ceremonial miniature roof details on the two documented double-tier shrines.
        swept_roof(name+' 木龛上檐',group,SimpleNamespace(**{**p.__dict__,'roof':p.lacquer,'tiles':[p.old_gold]*5}),
                   origin=loc.world(x,y),yaw=loc.yaw,width=w+.165,depth=d+.169,eave=z+h+.36,rise=.286,
                   kind='hip',tiles=False,pyramid_finial=False,ridge_terminals=False,eave_lift=.064)
    if kind in ('central','large','tiered'):
        seated(figures,x,y+.073,z+.016,min(w*.64,h*.465),p)
        for k in (-1,1):
            attend=.78 if kind=='central' else .53
            attendant(figures,x+k*w*.319,y-depth*.66,z+.063,attend,p,index+k)
            if kind=='central':
                attendant(figures,x+k*w*.376,y-depth*.39,z+.063,attend*.93,p,index-k)
    elif kind=='season':
        tablet(figures,x,y,z+.012,min(w*1.27,h*1.02),p)
    else:
        attendant(figures,x,y+.05,z+.04,min(w*.92,h*.73),p,index)
        for k in (-1,1):
            attendant(figures,x+k*w*.283,y-depth*.39,z+.02,.54,p,index+k)
    front=y-depth-.31
    altar(offers,x,front,FLOOR+.023,w*.90,.407,.77,p)
    for k in (-1,0,1):
        vessel(offers,x+k*w*.226,front,FLOOR+.793,.69 if k==0 else .76,p,'censer' if k==0 else 'bottle')
    wood=b.finish(name+' · 漆架、罩帘和分层底座',group,properties={'catalogue':INTERIOR_SOURCE,'reconstruction_role':kind})
    figures.finish(name+' · 独立神像或令牌体量',group,properties={
        'fidelity':'Catalogue-led subject; figure surfaces, scales and dress are interpretive.'})
    offers.finish(name+' · 供案与香供',group)
    return wood.name


def build_furnishings(loc,target,base):
    p=palette(base)
    group=collection('钦安殿 · 档案陈设与礼神空间',target)
    group['furnishing_catalogue']=INTERIOR_SOURCE
    rows=[]
    rows.append(shrine(loc,group,p,'北墙正龛',0,4.19,3.13,1.48,3.48,'central',0))
    for sign in (-1,1):
        side='东' if sign>0 else '西'
        for i,(x,y,w,d,h,kind,name) in enumerate(((2.58,4.15,1.81,1.33,2.92,'large','大龛'),
                            (4.35,4.19,1.60,1.19,2.66,'tiered','重檐龛'),
                            (5.74,4.35,1.06,.87,2.02,'season','夏令龛' if sign>0 else '秋令龛'),
                            (7.08,4.25,1.46,1.05,2.38,'warrior','描金漆龛'),
                            (8.49,4.37,1.06,.82,1.96,'season','春令龛' if sign>0 else '冬令龛'))):
            rows.append(shrine(loc,group,p,side+name,x*sign,y,w,d,h,kind,i+sign*4))
    carpet=loc.batch()
    mat=paint('钦安殿 · 暖褐拜垫织面',(.090,.037,.015),second=(.259,.138,.065),scale=8.9,rough=.94,grain=130,bump=.004)
    carpet.box((0,-1.24,FLOOR+.029),(1.43,1.053,.059),mat)
    for side in (-1,1):
        carpet.box((side*.633,-1.24,FLOOR+.06),(.024,.903,.009),p.old_gold)
        carpet.box((0,-1.24+side*.438,FLOOR+.06),(1.29,.019,.009),p.old_gold)
    carpet.finish('钦安殿 · 前部礼神拜垫',group)
    table=loc.batch()
    altar(table,0,1.87,FLOOR+.024,3.18,.84,.984,p)
    top=FLOOR+1.009
    vessel(table,0,1.76,top,1.44,p,'censer')
    for side in (-1,1):
        vessel(table,side*.577,1.92,top,1.14,p,'lamp')
        vessel(table,side*1.214,1.85,top,1.34,p,'bottle')
        for q in range(3):
            vessel(table,side*(.363+q*.289),1.55,top,.72,p,'bowl')
        altar(table,side*3.84,1.19,FLOOR+.022,1.23,.64,.783,p)
        for j in range(5):
            zz=FLOOR+.815+j*.019
            table.box((side*3.91,1.24,zz),(.316,.258,.018),p.faded_blue if j%2 else p.joint)
        vessel(table,side*4.15,1.08,FLOOR+.806,.83,p,'lamp')
    table.finish('钦安殿 · 明间供桌、旁案、铜器与经册',group)
    # The narrative catalogue notes two flanking large furnishings; the model omits
    # objects without enough placement information to represent them confidently.
    return {'collection':group.name,'catalogue':INTERIOR_SOURCE,'shrine_assemblies':len(rows),
            'modelled_sequence':rows,'confidence':'Appendix I object/type sequence, not an object-by-object scan or a dated inventory reconstruction.'}
