"""Ceiling coffers, paired phoenix paintings and a separate carved dragon."""
import math
from types import SimpleNamespace

from mathutils import Vector
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from carved_ornament import cloud
from garden_bridge_pavilions import flower, ring_outline
from mesh_tools import collection, polygons

CEILING_Z=6.27
RECESS=.79


def phoenix(b,x,y,z,s,p,flip):
    def pt(u,v,h=0.):
        return (x+flip*s*u,y+s*v,z+h)

    feather=p.giltpaint if flip<0 else p.cream
    b.face([pt(u,v,-.008) for u,v in ((-.092,-.17),(.061,-.23),(.158,-.126),(.119,.014),
                                    (.183,.109),(.149,.196),(.076,.201),(.033,.098),
                                    (-.079,.038),(-.149,-.065))],p.enamel)
    skull=pt(.132,.177,-.012)
    b.ellipsoid(skull,(s*.043,s*.042,.010),feather,sides=9,rings=5)
    b.face([pt(*uv,-.014) for uv in ((.162,.18),(.237,.156),(.167,.141))],p.old_gold)
    b.path([pt(*uv,-.015) for uv in ((.109,.205),(.085,.248),(.119,.276),(.145,.261))],s*.011,feather,sides=6)
    for j in range(7):
        q=j/6
        contour=[(-.073,-.119),(-.162-.075*q,.02),(-.402,-.015+.157*q),(-.523+.12*q,.114+.167*q)]
        left=Vector(contour[0]);u,v,w=(Vector(co) for co in contour[1:])
        coords=[(1-t)**3*left+3*t*(1-t)**2*u+3*t*t*(1-t)*v+t**3*w for t in (i/13 for i in range(14))]
        b.path([pt(k,l,-.014) for k,l in coords],s*.0105,feather,sides=5)
    for j in range(5):
        curve=[pt(-.10+(0.13-.066*j)*t-.069*math.sin(t*4.8),-.14-t*(.32+.030*j),-.014)
               for t in (k/20 for k in range(21))]
        b.path(curve,s*.009,p.giltpaint,sides=5)
        b.ellipsoid(curve[-1],(.019*s,.016*s,.010),p.cream,sides=7,rings=4)


def coiled_dragon(b,z,s,p):
    def at(t):
        angle=t*math.tau*1.405-.51
        r=(.762-.594*t)*s
        return Vector((r*math.cos(angle),r*math.sin(angle),z-(.066+.187*t*t)))

    vertices=[];faces=[];count=111;sides=13
    samples=[at(i/(count-1)) for i in range(count)]
    for i,q in enumerate(samples):
        t=i/(count-1)
        d=(samples[min(i+1,count-1)]-samples[max(0,i-1)]).normalized()
        v=d.cross(Vector((0,0,1))).normalized();u=v.cross(d).normalized()
        r=s*(.022+.054*math.sin(min(1.,t*.97)*math.pi*.67))
        for j in range(sides):
            a=j*math.tau/sides
            vertices.append(q+v*r*math.cos(a)+u*r*.76*math.sin(a))
        if i:
            faces.extend(((i-1)*sides+j,(i-1)*sides+(j+1)%sides,i*sides+(j+1)%sides,i*sides+j) for j in range(sides))
    faces.extend((tuple(reversed(range(sides))),tuple(range(len(vertices)-sides,len(vertices)))))
    b.add(vertices,faces,p.old_gold,smooth=True)
    flat=Vector((0,0,-1))
    for i in range(12,count-9,3):
        d=(samples[i+1]-samples[i-1]).normalized();v=d.cross(flat).normalized()
        r=.028+.038*i/count
        for row in (-1,0,1):
            q=samples[i]+v*r*.57*row+flat*r*(.57 if row else .73)
            scale=[q+v*.025*s*math.cos(a)+d*.023*s*math.sin(a) for a in (j*math.pi/8 for j in range(9))]
            b.path(scale,.0045*s,p.giltpaint,sides=5)
    for j,i in enumerate((36,54,72,91)):
        q=samples[i];d=(samples[i+1]-samples[i-1]).normalized();v=d.cross(flat).normalized()*(-1 if j%2 else 1)
        elbow=q+v*s*.132+d*.025*s+flat*.044*s
        heel=q+v*s*.248-d*.048*s+flat*.078*s
        b.path((q,elbow,heel),.022*s,p.old_gold,sides=9)
        for q in range(4):
            toe=heel+v*s*(.065-.012*abs(q-1.5))+d*(q-1.5)*.021*s
            b.path((heel,heel.lerp(toe,.67)+flat*.015,toe-flat*.016),.009*s,p.giltpaint,sides=6)
    h=samples[-1];d=(h-samples[-3]).normalized();bar=d.cross(flat).normalized()
    b.ellipsoid(h,(.111*s,.098*s,.060*s),p.old_gold,sides=21,rings=11)
    nose=h+d*.094*s+flat*.037*s
    b.ellipsoid(nose,(.079*s,.065*s,.041*s),p.giltpaint,sides=16,rings=9)
    b.ellipsoid(nose+flat*.058*s,(.073*s,.059*s,.017*s),p.old_gold,sides=16,rings=9)
    for sign in (-1,1):
        a=h+bar*sign*.080*s+flat*.042*s
        b.ellipsoid(a,(.021*s,.022*s,.014*s),p.cream,sides=9,rings=6)
        b.ellipsoid(a+flat*.014*s,(.008,.008,.006),p.door,sides=9,rings=5)
        b.path((h+bar*sign*.081*s,h+bar*sign*.146*s-d*.051*s,h+bar*sign*.129*s-d*.122*s),.016*s,p.giltpaint,sides=8)
        b.path((nose+bar*sign*.045*s,nose+bar*sign*.14*s+d*.047*s,nose+bar*sign*.202*s-d*.033*s),
               .008*s,p.old_gold,sides=6)
    pearl=nose+d*.108*s+flat*.102*s
    b.ellipsoid(pearl,(.090*s,.090*s,.096*s),p.giltpaint,sides=27,rings=13)


def upper_room(twin,loc,target,p):
    group=collection('亭内 · 雙鳳天花、內凹井口和盤龍',target)
    frame,decor,sculpture=(loc.batch() for _ in range(3))
    alternate=twin.name=='千秋亭'
    levels=((1.54,CEILING_Z),(1.44,CEILING_Z+.109),(1.31,CEILING_Z+.289),
            (1.13,CEILING_Z+.504),(1.02,CEILING_Z+.677),(.94,CEILING_Z+RECESS))
    void=Polygon(ring_outline(levels[0][0]))
    outline=unary_union((box(-3.34,-3.34,3.34,3.34),box(-2.27,-5.35,2.27,5.35),box(-5.09,-2.27,5.09,2.27)))
    for i in range(-6,7):
        for j in range(-6,7):
            x,y=i*.833,j*.832
            region=box(x-.403,y-.402,x+.403,y+.402).intersection(outline).difference(void)
            frame.solid_xy(region,CEILING_Z,CEILING_Z+.081,p.faded_blue if alternate else p.faded_teal)
            if region.area>.53:
                for sign in (-1,1):
                    phoenix(decor,x+sign*.081,y+sign*.018,CEILING_Z,.425,p,sign)
                cloud(decor,(x,y+.269,CEILING_Z-.011),.135,p.cream,facing='ceiling',rotation=(i+j)*math.pi)
    for i in range(-7,7):
        for axis in range(2):
            x=(i+.5)*.833
            line=LineString(((x,-6.0),(x,6.0)) if axis else ((-6.0,x),(6.0,x)))
            region=line.intersection(outline).difference(void)
            for ln in getattr(region,'geoms',(region,)):
                if ln.length>.01:
                    frame.beam((*ln.coords[0],CEILING_Z-.033),(*ln.coords[-1],CEILING_Z-.033),.079,.088,p.fascia)
    for j,((r,h),(rr,zz)) in enumerate(zip(levels,levels[1:])):
        a,b=ring_outline(r),ring_outline(rr)
        for i in range(8):
            k=(i+1)%8
            frame.face([(*a[i],h),(*b[i],zz),(*b[k],zz),(*a[k],h)],p.faded_blue if (j+int(alternate))%2 else p.faded_teal)
            decor.rod((*a[i],h-.010),(*a[k],h-.010),.024,p.old_gold,sides=10)
            for t in (.23,.50,.78):
                x=(a[i][0]+b[i][0])*(1-t)/2+(a[k][0]+b[k][0])*t/2
                y=(a[i][1]+b[i][1])*(1-t)/2+(a[k][1]+b[k][1])*t/2
                cloud(decor,(x,y,(h+zz)/2-.022),.187,p.giltpaint,facing='ceiling',rotation=-(i+.5)*math.pi/4)
                if j in (1,3) and t==.5:
                    flower(decor,x,y,(h+zz)/2-.031,.065,p.cream,p.old_gold)
    r,crown=levels[-1]
    frame.solid_xy(Polygon(ring_outline(r)),crown,crown+.081,p.cobalt)
    coiled_dragon(sculpture,crown,.99,p)
    frame.finish('亭内 · 真凹藻井、承框与双层天花板',group,properties={'ceiling_z_m':CEILING_Z,'coffer_recess_m':RECESS})
    decor.finish('亭内 · 双凤彩画、金云和井圈',group)
    sculpture.finish('亭内 · 独立鎏金衔珠盘龙',group,properties={
        'museum_documented_subject':'Gilded dragon holding a pearl. This sculpted shape is interpreted.'})
    return {'documented_subjects':['paired phoenix','coiled dragon with pearl'],'ceiling_z_m':CEILING_Z,
            'coffer_recess_m':RECESS,'finish_note':'The two coffer palettes differ. Specific layout and decoration are estimates.'}
