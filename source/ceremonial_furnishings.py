"""Photograph-led, editable Taihe furnishings; unsurveyed carving is interpretive."""
import math
from mathutils import Vector
from carved_ornament import cloud, dragon
from taihe_survey import GILDED_POSTS
from museum_surface import photo_material, crop_uv, relief_panel


def molding(b,x,y,z,w,h,p,thin=.035):
    for sx in (-1,1):
        b.box((x+sx*w/2,y,z+h/2),(thin,.055,h),p.gold)
    for k in (0,1):
        b.box((x,y,z+k*h),(w,.055,thin),p.gold)


def urn(b,x,y,z,p,scale=1.):
    b.lathe(x,y,[(r*scale,z+h*scale) for r,h in
                 ((.21,0),(.24,.10),(.18,.24),(.15,.40),(.27,.57),(.34,.85),
                  (.32,1.12),(.17,1.32),(.15,1.44),(.22,1.50))],p.bronze,sides=28)
    for sx in (-1,1):
        b.path([(x+sx*.29*scale,y,z+.85*scale),(x+sx*.46*scale,y,z+1.02*scale),
                (x+sx*.42*scale,y,z+1.21*scale),(x+sx*.20*scale,y,z+1.28*scale)],
               .035*scale,p.bronze,sides=8)


def lantern(b,x,y,z,p):
    for sx in (-1,1):
        for sy in (-1,1):
            b.path([(x+sx*.27,y+sy*.27,z),(x+sx*.18,y+sy*.18,z+1.85)],.035,p.door,sides=8)
    for height,w,t in ((.18,.62,.08),(1.78,.75,.12),(1.89,.89,.08)):
        b.box((x,y,z+height),(w,w,t),p.door)
    zz=z+2.24
    for k in range(4):
        a=k*math.pi/2;cx=x+math.sin(a)*.31;cy=y+math.cos(a)*.31
        b.box((cx,cy,zz),(.57,.035,.58),p.blue,yaw=-a)
        for sx in (-1,1):
            dx=math.cos(a)*sx*.25;dy=-math.sin(a)*sx*.25
            b.rod((cx+dx,cy+dy,zz-.30),(cx+dx,cy+dy,zz+.30),.025,p.bronze,sides=7)
        for sy in (-1,1):
            b.box((cx,cy,zz+sy*.28),(.61,.045,.045),p.bronze,yaw=-a)
    b.lathe(x,y,((.46,z+2.54),(.43,z+2.64),(.23,z+2.80),(.12,z+2.91),(.08,z+3.01)),p.bronze,sides=8)
    urn(b,x,y,z+3.03,p,.35)


def add_throne(b,stairs,floor,depth,width,p):
    """Screen, dais and placement are inferred from official frontal photographs.

    Chair and footstool dimensions are from the Palace Museum's Taihe throne
    catalogue (T00012_00.pdf, p.012). Sculpture and other furnishing dimensions
    remain inferred, rather than constituting a complete Taihe interior survey.
    """
    dais_y=8.95;dais_h=1.18;base=floor+dais_h+.25
    dais_w=9.;dais_d=6.15;front=dais_y-dais_d/2
    b.box((0,dais_y,floor+(dais_h+.25)/2),(dais_w,dais_d,dais_h+.25),p.door)
    b.box((0,dais_y,base-.10),(dais_w+.14,dais_d+.16,.20),p.red)
    for dz,ext in ((-.02,.20),(-.17,.12),(-.33,.05),(-1.10,.15)):
        b.box((0,dais_y,base+dz),(dais_w+ext,dais_d+ext,.045),p.giltpaint)
    run=2.26/7;rise=(base-floor-.25)/7
    for i in range(7):
        yy=front-2.26+(i+.5)*run;top=floor+.25+(i+1)*rise
        b.box((0,yy,(floor+.25+top)/2),(6.05,run+.008,top-floor-.25),p.door)
        b.box((0,yy,top+.006),(5.97,run-.024,.016),p.red)
        b.box((0,yy-run*.46,top+.017),(6.05,.023,.018),p.giltpaint)
        b.box((0,yy,top+.019),(1.42,run-.01,.012),p.door)
        for sx in (-1,1):
            b.box((sx*.69,yy,top+.028),(.027,run,.013),p.giltpaint)
            for j in range(5):
                b.ellipsoid((sx*(.22+j*.074),yy,top+.032),(.018,.025,.007),p.gold,sides=7,rings=4)
    for sx in (-1,1):
        b.beam((sx*3.17,front-2.27,floor+.42),(sx*3.17,front,base+.17),.20,.24,p.red)
        b.beam((sx*3.17,front-2.27,floor+.58),(sx*3.17,front,base+.32),.08,.06,p.giltpaint)
        urn(b,sx*3.70,dais_y-1.05,base,p,.77)
        lantern(b,sx*2.18,dais_y+.12,base,p)
    for i in range(17):
        cloud(b,((i-8)*.50,front-.025,base-.68),.37,p.giltpaint,rotation=(i%2)*math.pi)

    widths=(.66,.80,.88,1.62,.88,.80,.66)
    heights=(3.16,3.45,3.69,4.02,3.69,3.45,3.16)
    screen_y=dais_y+1.62;left=-sum(widths)/2
    carved_paint=photo_material('御座围屏雕刻 · 官方305','taihe_throne_official_305.jpg',metal=.20,rough=.66)
    fields=((.095,.448,.174,.675),(.209,.398,.282,.600),(.336,.336,.406,.532),
            (.459,.303,.553,.460),(.598,.354,.675,.570),(.737,.405,.800,.650),
            (.829,.448,.902,.675))
    for index,(w,h) in enumerate(zip(widths,heights)):
        x=left+w/2;z=base+.10
        b.box((x,screen_y,z+h/2),(w-.012,.22,h),p.red)
        b.box((x,screen_y-.135,z+h*.49),(w-.13,.042,h-.49),p.giltpaint)
        b.box((x,screen_y-.166,z+h*.49),(w-.22,.026,h-.61),p.door)
        # Pigment and fine carving come from the screen's unobstructed outer
        # panel; frame, thickness, crest and raised dragons remain real meshes.
        relief_panel(b,(x,screen_y-.183,z+h/2),w-.24,h-.60,carved_paint,
                     crop_uv(*fields[index]),nx=32,ny=160,depth=.035)
        molding(b,x,screen_y-.196,z+.21,w-.19,h-.42,p)
        molding(b,x,screen_y-.206,z+.28,w-.29,h-.56,p,.016)
        # The fine carved field is a genuine sampled relief mesh; do not cover
        # it with the earlier unrelated serpentine wire ornament.
        for dz in (.38,h-.47):
            cloud(b,(x,screen_y-.248,z+dz),w*.53,p.gold,rotation=(index%2)*math.pi)
        crest=[(x-w*.49,z+h-.08),(x-w*.40,z+h+.055),(x-w*.22,z+h+.09),
               (x-w*.14,z+h+.22),(x+w*.14,z+h+.22),(x+w*.22,z+h+.09),
               (x+w*.40,z+h+.055),(x+w*.49,z+h-.08)]
        b.path([(u,screen_y-.17,v) for u,v in crest],.037,p.gold,sides=8)
        cloud(b,(x,screen_y-.18,z+h+.24),w*.80,p.gold)
        for sx in (-1,1):
            b.path([(x+sx*w*.12,screen_y-.10,z+h+.17),
                    (x+sx*w*.33,screen_y-.10,z+h+.42),
                    (x+sx*w*.45,screen_y-.10,z+h+.30)],.027,p.gold,sides=7)
        left+=w

    # Complete carved chair: legs, apron, seat, stepped back and sweeping arms.
    chair_w,chair_d=1.585,.79;seat_y=dais_y-.43;seat_top=base+.49
    b.box((0,seat_y,base+.105),(1.62,.995,.21),p.gold)
    for zz in (base+.025,base+.185):
        b.box((0,seat_y,zz),(1.65,1.015,.035),p.giltpaint)
    b.box((0,seat_y-.507,base+.108),(1.43,.018,.092),p.cobalt)
    for i in range(11):
        cloud(b,((i-5)*.125,seat_y-.521,base+.109),.105,p.gold)
    for sx in (-1,1):
        for sy in (-1,1):
            x=sx*.67;y=seat_y+sy*.30
            b.path([(x,y,base+.045),(x+sx*.015,y,base+.20),(x-sx*.015,y,base+.42)],.048,p.gold,sides=10)
            b.ellipsoid((x,y,base+.065),(.08,.08,.055),p.gold,sides=10,rings=5)
    b.box((0,seat_y,base+.40),(chair_w,chair_d,.15),p.gold)
    b.box((0,seat_y,seat_top-.0275),(chair_w-.10,chair_d-.09,.055),p.giltpaint)
    for x in (-.59,-.30,0,.30,.59):
        cloud(b,(x,seat_y-chair_d/2-.035,base+.33),.24,p.giltpaint)
    for sx in (-1,1):
        b.path([(sx*.69,seat_y-.30,base+.49),(sx*.73,seat_y-.32,base+.77),
                (sx*.69,seat_y+.12,base+.97),(sx*.61,seat_y+.34,base+1.03)],.047,p.gold,sides=10)
        b.ellipsoid((sx*.70,seat_y-.32,base+.77),(.092,.12,.08),p.gold,sides=12,rings=6)
        for k in (-1,1):
            b.ellipsoid((sx*.73+k*.042,seat_y-.405,base+.79),(.018,.014,.018),p.door,sides=8,rings=4)
    back_y=seat_y+.33
    outline=[(-.72,base+.48),(-.72,base+1.12),(-.52,base+1.18),(-.52,base+1.39),
             (-.29,base+1.43),(-.29,base+1.59),(0,base+1.697),(.29,base+1.59),
             (.29,base+1.43),(.52,base+1.39),(.52,base+1.18),(.72,base+1.12),(.72,base+.48)]
    n=len(outline);verts=[(x,back_y,z) for x,z in outline]+[(x,back_y+.09,z) for x,z in outline]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    faces.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
    b.add(verts,faces,p.gold)
    b.path([(x,back_y-.035,z) for x,z in outline+[outline[0]]],.028,p.gold,sides=8)
    for x in (-.48,0,.48):
        if x:
            dragon(b,(x,back_y-.04,base+.94),.30,.48,p,mirror=x<0,z_relief=.012,detailed=True)
    relief_panel(b,(0,back_y-.04,base+1.08),.48,.72,carved_paint,
                 crop_uv(.459,.50,.553,.68),nx=64,ny=96,depth=.018)
    for sx in (-1,1):
        cloud(b,(sx*.39,back_y-.05,base+1.40),.36,p.gold,rotation=sx*.5)
    stool_y=seat_y-.86
    for sx in (-1,1):
        for sy in (-1,1):
            b.box((sx*.27,stool_y+sy*.14,base+.13),(.075,.075,.26),p.gold)
    b.box((0,stool_y,base+.27),(.705,.42,.06),p.gold)
    b.box((0,stool_y,base+.291),(.65,.37,.018),p.giltpaint)
    for i in range(5):
        cloud(b,((i-2)*.125,stool_y-.23,base+.17),.14,p.giltpaint)
    # The cranes stand on the floor beyond the dais edges, not in mid-air.
    for sx in (-1,1):
        x=sx*5.48;y=dais_y-1.27;z=floor+.25
        b.lathe(x,y,((.38,z),(.39,z+.12),(.23,z+.25),(.32,z+.39)),p.bronze,sides=24)
        for off in (-.12,.12):
            b.rod((x+off,y,z+.36),(x+off,y,z+1.30),.027,p.bronze,sides=9)
        b.ellipsoid((x,y,z+1.49),(.22,.42,.27),p.bronze,sides=16,rings=9)
        b.path([(x,y-.23,z+1.52),(x,y-.40,z+1.90),(x,y-.36,z+2.18),
                (x,y-.52,z+2.26)],.045,p.bronze,sides=10)
        b.rod((x,y-.52,z+2.26),(x,y-.78,z+2.22),.033,p.bronze,r1=.003,sides=10)
    return dais_y,dais_h


def add_gilded_dragon_columns(b,p,post_radius=.53,*,floor=8.13,positions=None):
    """Thin gold sheaths and low relief on the actual six supporting posts."""
    pigment=photo_material('金柱盘龙表面','palace_museum_taihe_throne_reference.jpg',metal=.36,rough=.65)
    for x,y in (positions or GILDED_POSTS):
        low=floor+.29;high=floor+12.20
        start=len(b.f)
        b.lathe(x,y,((post_radius*.99,low),(post_radius*.99,low+.13),
                     (post_radius*.951,high-.13),(post_radius*.94,high)),pigment,sides=48)
        for index in range(start,len(b.f)):
            values=[]
            for vi in b.f[index]:
                vx,vy,vz=b.v[vi]
                angle=math.atan2(vy-y,vx-x)%math.tau
                values.append((.095+.073*angle/math.tau,.17+.56*(vz-low)/(high-low)))
            b.uv[index]=tuple(values)
        for base in (low+.14,high-.23):
            b.lathe(x,y,((post_radius*1.015,base),(post_radius*1.015,base+.055)),p.giltpaint,sides=48)
        for repeat in range(3):
            z0=low+.45+repeat*3.35
            for side in range(2):
                phase=side*math.pi;points=[]
                for i in range(137):
                    t=i/136;a=phase+t*math.tau*1.04;r=post_radius*.972+.018*math.sin(t*18)
                    points.append((x+r*math.cos(a),y+r*math.sin(a),z0+t*2.65))
                b.path(points,.024,p.giltpaint,sides=7)
                for j in range(8,129,5):
                    t=j/136;a=phase+t*math.tau*1.04;r=post_radius*.987
                    tangent=Vector((-math.sin(a),math.cos(a),0))
                    point=Vector((x+r*math.cos(a),y+r*math.sin(a),z0+t*2.65))
                    scallop=[tuple(point+tangent*(.048*math.cos(k*math.pi/8))+
                                   Vector((0,0,.033*math.sin(k*math.pi/8)))) for k in range(9)]
                    b.path(scallop,.0065,p.gold,sides=5)
                hx,hy,hz=points[-1]
                b.ellipsoid((hx,hy,hz),(.115,.10,.12),p.giltpaint,sides=14,rings=8)
                for sx in (-1,1):
                    b.path([(hx+sx*.045,hy,hz+.04),(hx+sx*.09,hy,hz+.17),
                            (hx+sx*.12,hy-.02,hz+.19)],.011,p.gold,sides=6)
                    b.path([(hx+sx*.05,hy-.06,hz-.025),(hx+sx*.14,hy-.08,hz-.07),
                            (hx+sx*.20,hy-.06,hz-.03)],.008,p.gold,sides=5)
