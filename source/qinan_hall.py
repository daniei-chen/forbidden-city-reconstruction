"""Measured Qin'an timber layout and photo-led stone, joinery and roof surfaces."""
import math
import os
from pathlib import Path
from types import SimpleNamespace

import bpy
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from architectural_roofs import swept_roof, terminal
from carved_ornament import cloud, dragon
from garden_bridge_pavilions import flower, laid_pavers, panel_motif, ring_outline, transfer
from mesh_tools import Batch, collection, object_to_mesh, polygons
from palace_architecture import arch_mesh
from palace_materials import paint
from qinan_survey import (ANNEX_EXTENT, BRACKET_STEPS, CEILING, DATUM, EAVE_COLUMN, FLOOR, FLOWER_BEAM,
                          GOLD_COLUMN, LOW_FOOT_X, LOW_FOOT_Y, LOW_HEAD_X, LOW_HEAD_Y, LOW_PURLIN,
                          PROJECTIONS, QIN, QIN_SOURCE, TIMBER_SOURCE, TOP_BOARD, TOP_PLAN,
                          UP_HEAD_X, UP_HEAD_Y, UP_PURLIN, centres, source_report)

REFERENCES=Path(__file__).parent/'references'/'garden_north'
TEXTURES=Path(__file__).parent/'textures'


def materials(base):
    p=SimpleNamespace(**base.__dict__)
    p.stone=paint('钦安殿 · 老汉白玉',(.354,.347,.319),second=(.648,.615,.542),scale=2.4,
                  rough=.84,grain=102,bump=.007)
    p.understone=paint('御花园北部 · 发灰石脚',(.22,.218,.19),second=(.468,.453,.403),scale=7.2,
                       rough=.87,grain=93,bump=.009)
    p.bluebrick=paint('天一门 · 磨砖对缝青砖',(.283,.276,.253),second=(.422,.413,.378),scale=9.8,rough=.86,
                       brick=(.49,.126,.0015,True),grain=118,bump=.0021)
    p.fascia=paint('钦安殿 · 暗朱漆木',(.14,.024,.013),second=(.311,.055,.028),scale=9.,rough=.63,
                   grain=122,bump=.003,coat=.08)
    p.faded_teal=paint('钦安殿 · 檐下石绿',(.036,.100,.078),second=(.109,.221,.147),scale=8.6,rough=.69,
                       grain=102,bump=.0038)
    p.faded_blue=paint('钦安殿 · 檐下石青',(.019,.041,.119),second=(.072,.111,.211),scale=6.7,rough=.73,
                       grain=128,bump=.0042)
    p.cream=paint('钦安殿 · 褪色彩画旧粉线',(.275,.228,.129),second=(.53,.458,.291),scale=19.,rough=.74,
                  grain=115,bump=.0038)
    p.lacquer=paint('钦安殿 · 神龛深漆',(.073,.020,.011),second=(.18,.051,.025),scale=7.,rough=.45,
                    grain=130,bump=.0025,coat=.22)
    p.old_gold=paint('钦安殿 · 老镀金与氧化铜底',(.18,.097,.033),second=(.61,.38,.12),scale=17.,rough=.45,
                     grain=113,bump=.006,metal=.7)
    p.joint=paint('御花园 · 石子地仗灰泥',(.20,.187,.158),second=(.35,.324,.280),scale=4.,rough=.96,bump=.010)
    return p


def text_mesh(target,location,label,text,x,y,z,scale,material,*,face_yaw=0.):
    font_file=Path(os.environ.get('PALACE_CJK_FONT','C:/Windows/Fonts/simkai.ttf'))
    if not font_file.is_file():
        return None
    font=bpy.data.fonts.load(str(font_file),check_existing=True)
    data=bpy.data.curves.new(label,'FONT')
    data.font=font;data.body=text;data.size=scale
    data.align_x='CENTER';data.align_y='CENTER';data.extrude=.002;data.bevel_depth=.0011
    obj=bpy.data.objects.new(label,data)
    target.objects.link(obj)
    obj.location=location.world(x,y,z)
    obj.rotation_euler=(math.pi/2,0,location.yaw+face_yaw)
    data.materials.append(material)
    bpy.context.view_layer.update()
    return object_to_mesh(obj)


def photo_material(name,filename,url):
    path=TEXTURES/filename
    if not path.is_file():
        return None
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(.088,.115,.34,1)
    m['reference']=url
    nodes=m.node_tree.nodes
    image=nodes.new('ShaderNodeTexImage');image.image=bpy.data.images.load(str(path),check_existing=True)
    image.image['photo_credit']='Palace Museum: '+url
    surf=nodes.get('Principled BSDF');surf.inputs['Roughness'].default_value=.56
    m.node_tree.links.new(image.outputs['Color'],surf.inputs['Base Color'])
    return m


def plaque(location,target,name,x,y,z,w,h,p,photo=None,gilded=False):
    b=location.batch()
    s=Batch()
    pts=[(0,.69),(.30,.66),(.55,.55),(.72,.62),(1.10,.67),(1.33,.54),(1.38,.43),(.88,.35),
         (.87,.20),(1.00,.06),(.94,-.23),(.85,-.44),(.91,-.58),(.81,-.76),(.65,-.76),(.51,-.59),(0,-.65)]
    left=[(x-u*w/2,z+v*h) for u,v in pts]
    outline=Polygon(left+[(x+u*w/2,z+v*h) for u,v in reversed(pts[1:-1])]).buffer(.008).buffer(-.008)
    arch_mesh(s,outline,.10,p.old_gold if gilded else p.fascia)
    transfer(b,s,0,y,0)
    border=[(u,y-.058,v) for u,v in outline.exterior.coords]
    b.path(border,.0138,p.giltpaint,sides=8)
    corners=[(x+sx*w/2,y-.068,z+sz*h/2) for sx,sz in ((-1,-1),(1,-1),(1,1),(-1,1))]
    m=photo_material(name+' · 馆方实拍匾心',*photo) if photo else None
    b.face(corners,m or p.cobalt,uv=((0,0),(1,0),(1,1),(0,1)))
    b.path([*corners,corners[0]],.012,p.giltpaint,sides=7)
    for dx in (-1,1):
        for dz in (-1,1):
            cloud(b,(x+dx*.56*w,y-.060,z+dz*.547*h),h*.22,p.giltpaint,rotation=dx*dz*1.86)
    b.finish(name+' · 独立漆木匾框与匾心',target)
    if m is None:
        for i,char in enumerate(name):
            text_mesh(target,location,name+' 匾字 '+char,char,x,y-.077,z+h*(.30-.3*i),h*.28,p.giltpaint)


def stone_step_run(b,start,end,width,z0,z1,p,*,count=None,danbi=False):
    dx,dy=end[0]-start[0],end[1]-start[1]
    length=math.hypot(dx,dy)
    n=count or max(2,round((z1-z0)/.167))
    u=(dx/length,dy/length);v=(-u[1],u[0]);angle=math.atan2(dy,dx)
    stone=Batch()
    for i in range(n):
        height=z0+(z1-z0)*(i+1)/n
        mid=length*(i+.5)/n
        bands=((-width*.33,width*.336),(width*.33,width*.336)) if danbi else ((0,width),)
        for off,w in bands:
            stone.box((mid,off,(height+z0)*.5),(length/n+.011,w,height-z0),p.stone)
            stone.box((mid-.013,off,height-.025),(length/n+.035,w+.012,.049),p.stone)
    for side in (-1,1):
        cheek=Batch()
        arch_mesh(cheek,Polygon([(0,z0),(length,z0),(length,z1+.27),(length*.75,z1+.20),
                                 (length*.32,z0+.37),(.28,z0+.21),(0,z0+.10)]),.21,p.stone)
        transfer(stone,cheek,0,side*(width/2+.10),0)
    if danbi:
        stone.face([(0,-width*.166,z0+.027),(length,-width*.166,z1+.06),
                    (length,width*.166,z1+.06),(0,width*.166,z0+.027)],p.understone)
        for i in range(6):
            hw=width*.13
            q=.23+length*(i+.30)/6
            coords=[(q+length*.058*math.sin(j*math.tau/24),hw*math.sin(j*math.tau/24+.81),
                     z0+((q+length*.058*math.sin(j*math.tau/24))/length)*(z1-z0)+.073)
                    for j in range(25)]
            stone.path(coords,.019,p.stone,sides=7)
            stone.ellipsoid((q,-hw*.78,z0+q/length*(z1-z0)+.098),(.038,.053,.031),p.stone,sides=12,rings=7)
    transfer(b,stone,*start,angle)


def marble_rail(b,line,z,p,*,step=1.72,pierced=True,center_dragon=False):
    source=Batch()
    a,c=line
    length=math.dist(a,c)
    direction=math.atan2(c[1]-a[1],c[0]-a[0])
    count=max(1,round(length/step));pitch=length/count
    for i in range(count+1):
        x=i*pitch
        source.box((x,0,z+.389),(.209,.213,.767),p.stone)
        source.box((x,0,z+.075),(.266,.264,.144),p.understone)
        source.lathe(x,0,((.129,z+.755),(.119,z+.78),(.106,z+.842),(.127,z+.904),
                           (.111,z+.966),(.082,z+1.024),(.034,z+1.047)),p.stone,sides=18)
        for side in (-1,1):
            for j in range(3):
                cloud(source,(x,side*.107,z+.78+j*.078),.123,p.stone,rotation=j*2.3)
        if i==count or pitch<.52:
            continue
        cx=x+pitch/2
        span=pitch-.188
        plate=box(cx-span/2,z+.083,cx+span/2,z+.712)
        if pierced:
            for k in (-1,0,1):
                q=cx+k*span*.247
                shape=Point(q,z+.505).buffer(.085,quad_segs=6)
                plate=plate.difference(shape.union(box(q-.065,z+.48,q+.065,z+.61)))
        arch_mesh(source,plate,.127,p.stone)
        source.box((cx,0,z+.738),(span+.031,.166,.077),p.stone)
        for k in (-1,1):
            q=cx+k*span*.211
            # Serpentine carving flows around the stone flowers below the pierced field.
            for s in (-1,1):
                rs=.18 if center_dragon and i==count//2 else .129
                source.path([(q+span*.21*math.sin(t*math.pi*2.2),s*.068,z+.263+rs*math.sin(5*t+.4*k))
                             for t in (j/32 for j in range(33))],.014,p.stone,sides=6)
                cloud(source,(q,s*.09,z+.309),.117,p.stone,rotation=k*1.7)
    transfer(b,source,*a,direction)


def plinth(site,loc,target,p):
    group=collection('钦安殿 · 一层须弥座、月台和丹陛',target)
    shape=loc.local(unary_union([site.geom(QIN),site.geom('685600276')])).buffer(.04,join_style=2)
    b=loc.batch()
    for a,c,off,mat in ((-.09,.115,.04,p.understone),(.115,.366,.018,p.stone),(.366,.480,-.063,p.stone),
                        (.480,1.063,-.123,p.stone),(1.063,1.201,-.061,p.understone),
                        (1.201,1.384,-.019,p.stone),(1.384,FLOOR-.058,.035,p.stone)):
        b.solid_xy(shape.buffer(off,join_style=2),a,c,mat,bottom=False)
    laid_pavers(b,shape,FLOOR,p,course=.72,width=1.12)
    for ref in ('685600273','685600274','685600275'):
        g=loc.local(site.geom(ref));x0,y0,x1,y1=g.bounds
        if ref=='685600273':
            a=((x0+x1)/2,y0);c=((x0+x1)/2,y1+.06);width=x1-x0
        else:
            side=1 if ref=='685600274' else -1
            a=(x1 if side>0 else x0,(y0+y1)/2);c=((x0-.049 if side>0 else x1+.049),(y0+y1)/2)
            width=y1-y0
        stone_step_run(b,a,c,width,.031,FLOOR,p,danbi=ref=='685600273')
    obj=b.finish('钦安殿 · 分层石作、丹陛与三面独立踏步',group,properties={'source_osm_terrace':'685600276','model_floor_z':FLOOR})
    x0,y0,x1,y1=shape.bounds
    rail=loc.batch()
    cuts=unary_union([loc.local(site.geom(k)).buffer(.17,join_style=2) for k in ('685600273','685600274','685600275')])
    for a,c,back in (((x0+.17,y0+.14),(x1-.15,y0+.14),False),((x0+.17,y1-.12),(x1-.15,y1-.12),True),
                     ((x0+.16,y0+.14),(x0+.16,y1-.12),False),((x1-.16,y0+.14),(x1-.16,y1-.12),False)):
        path=LineString((a,c)).difference(cuts)
        for sec in getattr(path,'geoms',(path,)):
            if sec.geom_type=='LineString' and sec.length>.6:
                marble_rail(rail,(sec.coords[0],sec.coords[-1]),FLOOR,p,center_dragon=back)
    for q in range(15):
        x=x0+(q+.5)*(x1-x0)/15
        if cuts.distance(Point(x,y0))>.4:
            rail.ellipsoid((x,y0-.127,FLOOR-.20),(.113,.23,.095),p.stone,sides=13,rings=7)
    rail.finish('钦安殿 · 穿花龙纹栏板及龙凤望柱',group)
    return obj


def timber_post(loc,target,title,foot,head,r,p,*,inner=False):
    b=loc.batch()
    x,y,z=foot;xx,yy,zz=head
    b.lathe(x,y,((r*1.43,FLOOR-.035),(r*1.44,FLOOR+.075),(r*1.19,FLOOR+.127),(r*1.08,z)),p.stone,sides=28)
    verts=[];faces=[];n=28
    for i,t in enumerate((0,.045,.28,.56,.81,.965,1.)):
        r0=r*(1-.083*t-.011*math.sin(t*math.pi))
        for j in range(n):
            a=j/n*math.tau
            rr=r0*(1+.008*math.sin(3*a)+.005*math.cos(8*a))
            verts.append((x+(xx-x)*t+rr*math.cos(a),y+(yy-y)*t+rr*math.sin(a),z+(zz-z)*t))
        if i:
            faces.extend(((i-1)*n+j,(i-1)*n+(j+1)%n,i*n+(j+1)%n,i*n+j) for j in range(n))
    faces.extend((tuple(reversed(range(n))),tuple(range(len(verts)-n,len(verts)))))
    b.add(verts,faces,p.red,smooth=True)
    return b.finish(title,target,properties={'post_role':'gold' if inner else 'eave','foot_centre_m':foot,
                                             'head_centre_m':head,'timber_height_m':zz-z})


def bracket(b,x,y,z,yaw,p,*,upper=False,glazed=False):
    frame=Batch()
    base=p.green_clay if glazed else p.faded_teal
    trim=p.tiles[2] if glazed else p.giltpaint
    frame.box((0,0,z+.061),(.358,.365,.123),base)
    xz=Polygon([(-.167,z+.112),(.167,z+.112),(.216,z+.186),(.311,z+.195),(.346,z+.321),
                (-.346,z+.321),(-.311,z+.195),(-.216,z+.186)])
    arch_mesh(frame,xz,.211,base)
    for i,s in enumerate((0.,PROJECTIONS[0],sum(PROJECTIONS),sum(PROJECTIONS)+.182) if upper else
                         (0.,PROJECTIONS[0],sum(PROJECTIONS))):
        h=z+.123+sum(BRACKET_STEPS[:i])
        extent=.285+i*.012
        frame.box((0,-s,h+.082),(extent,.213,.134),base)
        frame.beam((0,.57+i*.19,h+.124+i*.076),(0,-s-.185,h-.025),.125,.123,p.faded_blue if not glazed else base)
        for j in (-1,1):
            frame.box((j*extent*.462,-s,h+.157),(.106,.169,.053),trim)
        frame.path([(-extent*.49,-s-.118,h+.096),(0,-s-.128,h+.025),(extent*.49,-s-.118,h+.096)],
                   .013,trim,sides=6)
    transfer(b,frame,x,y,yaw)


def painted_bay(b,x,y,z,w,p,*,yaw=0,height=.49):
    s=Batch()
    s.box((0,0,z),(w,.311,height),p.faded_teal)
    s.box((0,0,z-height*.56),(w,.352,.08),p.fascia)
    s.box((0,0,z+height*.54),(w,.344,.075),p.faded_blue)
    for sign in (-1,1):
        small=Batch()
        panel_motif(small,0,-.167,z,w*.76,height*.81,p,'dragons')
        for side in (-1,1):
            for i in range(3):
                cloud(small,(side*w*(.36+i*.038),-.167,z),height*.37,p.cream,rotation=side*1.71)
        transfer(s,small,0,0,0 if sign<0 else math.pi)
    transfer(b,s,x,y,yaw)


def shutter(b,x,y,z,w,h,p,*,yaw=0,leaves=4,open_center=False):
    small=Batch()
    for i in range(leaves):
        xx=w*((i+.5)/leaves-.5);dw=w/leaves-.012
        sy=0.
        leaf=Batch()
        for side in (-1,1):
            leaf.box((side*(dw/2-.054),0,z+h/2),(.104,.132,h),p.red)
            leaf.box((0,0,z+h*(.027 if side<0 else .973)),(dw,.136,.105),p.red)
        mid=z+h*.315
        leaf.box((0,0,mid),(dw,.13,.097),p.fascia)
        leaf.box((0,.009,z+h*.169),(dw-.16,.088,h*.252),p.door)
        leaf.box((0,-.044,z+h*.169),(dw-.229,.013,h*.197),p.fascia)
        for side in (-1,1):
            for hh in (.095,.242):
                leaf.box((0,-.062,z+h*hh),(dw-.222,.022,.018),p.giltpaint)
            leaf.box((side*(dw-.222)/2,-.062,z+h*.17),(.015,.022,h*.16),p.giltpaint)
        for c in range(1,8):
            leaf.box(((c/8-.5)*(dw-.183),-.003,(z+h-.087+mid)/2),(.019,.064,z+h-mid-.128),p.fascia)
        for j in range(1,13):
            leaf.box((0,-.007,mid+(h*.643)*j/13),(dw-.193,.071,.021),p.red)
        if not open_center or i not in (leaves//2-1,leaves//2):
            leaf.box((0,.056,(mid+z+h)/2),(dw-.167,.025,z+h-mid-.121),p.inset)
        leaf.ellipsoid((dw*.222,-.084,mid-.12),(.027,.016,.034),p.old_gold,sides=10,rings=6)
        if open_center and i in (leaves//2-1,leaves//2):
            side=-1 if i<leaves//2 else 1
            hinge=xx+side*dw/2
            turn=-side*math.radians(82)
            transfer(small,leaf,hinge-side*dw/2*math.cos(turn),-side*dw/2*math.sin(turn),turn)
        else:
            transfer(small,leaf,xx,sy,0)
    transfer(b,small,x,y,yaw)


def framing(loc,target,p):
    group=collection('钦安殿 · 实测柱网、减柱大木与花台枋',target)
    low_x,low_y=centres(LOW_FOOT_X),centres(LOW_FOOT_Y)
    head_x,head_y=centres(LOW_HEAD_X),centres(LOW_HEAD_Y)
    upper_x=centres(UP_HEAD_X)
    upper_y=(-UP_HEAD_Y/2,UP_HEAD_Y/2)
    structural,colors,joins,purlins=(loc.batch() for _ in range(4))
    eaves=gold=0
    for j,y in enumerate(low_y):
        for i,x in enumerate(low_x):
            if j in (0,3) or i in (0,5):
                eaves+=1
                timber_post(loc,group,f'钦安殿 · 檐柱 {eaves:02d}',(x,y,DATUM),(head_x[i],head_y[j],DATUM+EAVE_COLUMN),.296,p)
            elif i in (1,4):
                gold+=1
                timber_post(loc,group,f'钦安殿 · 金柱 {gold:02d}',(x,y,DATUM),(upper_x[i],upper_y[j-1],DATUM+GOLD_COLUMN),.351,p,inner=True)

    for sign in (-1,1):
        yy=sign*UP_HEAD_Y/2
        x0,x1=upper_x[1]-.33,upper_x[-2]+.33
        h,w=FLOWER_BEAM
        z=DATUM+GOLD_COLUMN+.10
        beam=loc.batch()
        beam.box(((x0+x1)/2,yy,z-h/2),(x1-x0,w,h),p.fascia)
        beam.finish('钦安殿 · '+('前' if sign<0 else '后')+'金柱间通长花台枋',group,
                    properties={'section_height_m':h,'section_width_m':w,'source':TIMBER_SOURCE})
        for x in upper_x[2:4]:
            structural.box((x,yy,z+.129),(.338,.327,.283),p.fascia)
        for x in (upper_x[2]-.8,upper_x[3]+.8):
            structural.beam((x,-3.76,DATUM+8.78),(x,3.76,DATUM+8.78),.32,.48,p.door)

    for side,yy in enumerate((head_y[0],head_y[-1])):
        yaw=side*math.pi
        for i,x in enumerate(head_x):
            bracket(joins,x,yy,DATUM+EAVE_COLUMN+.10,yaw,p)
            if i:
                a=head_x[i-1];w=x-a
                painted_bay(colors,(a+x)/2,yy,DATUM+3.91,w-.061,p,yaw=yaw,height=.49)
                for k in range(1,5):
                    bracket(joins,a+k*w/5,yy,DATUM+EAVE_COLUMN+.10,yaw,p)
        purlins.rod((head_x[0]-.30,yy,DATUM+sum(LOW_PURLIN)/2),
                    (head_x[-1]+.30,yy,DATUM+sum(LOW_PURLIN)/2),(LOW_PURLIN[1]-LOW_PURLIN[0])/2,p.door,sides=20)
    for side in (-1,1):
        xx=head_x[0 if side<0 else -1];yaw=side*math.pi/2
        for i,(a,c) in enumerate(zip(head_y,head_y[1:])):
            painted_bay(colors,xx,(a+c)/2,DATUM+3.91,c-a-.047,p,yaw=yaw)
            for k in range(1,(9 if i==1 else 2)):
                bracket(joins,xx,a+k*(c-a)/(9 if i==1 else 2),DATUM+EAVE_COLUMN+.10,yaw,p)
        purlins.rod((xx,head_y[0]-.3,DATUM+sum(LOW_PURLIN)/2),(xx,head_y[-1]+.3,DATUM+sum(LOW_PURLIN)/2),
                    (LOW_PURLIN[1]-LOW_PURLIN[0])/2,p.door,sides=20)

    for side,yy in enumerate(upper_y):
        yy+=(-1 if side==0 else 1)*.58
        yaw=side*math.pi
        for i,x in enumerate(upper_x):
            bracket(joins,x,yy,DATUM+7.84,yaw,p,upper=True)
            if i:
                a=upper_x[i-1];w=x-a
                painted_bay(colors,(a+x)/2,yy,DATUM+7.45,w-.04,p,yaw=yaw)
                n=3 if i in (1,5) else 5
                for k in range(1,n):
                    bracket(joins,a+k*w/n,yy,DATUM+7.84,yaw,p,upper=True)
        purlins.rod((upper_x[0]-.3,yy,DATUM+sum(UP_PURLIN)/2),(upper_x[-1]+.3,yy,DATUM+sum(UP_PURLIN)/2),
                    (UP_PURLIN[1]-UP_PURLIN[0])/2,p.door,sides=20)
    for side in (-1,1):
        x=side*(sum(UP_HEAD_X)/2+.13)
        y0,y1=upper_y[0]-.58,upper_y[1]+.58
        for k in range(9):
            bracket(joins,x,y0+(k+.5)*(y1-y0)/9,DATUM+7.84,side*math.pi/2,p,upper=True)
        painted_bay(colors,x,0,DATUM+7.45,y1-y0,p,yaw=side*math.pi/2)
    structural.finish('钦安殿 · 侏儒柱、露明与暗梁架',group)
    colors.finish('钦安殿 · 石青石绿老彩画梁枋',group)
    joins.finish('钦安殿 · 下檐五踩溜金与上檐七踩斗栱',group,properties={'measured_mean_projections_m':PROJECTIONS})
    purlins.finish('钦安殿 · 两层檐檩下皮与上皮',group)
    return {'eave_posts':eaves,'retained_gold_posts':gold,'omitted_gold_posts':4}


def roofwork(site,loc,target,p):
    group=collection('钦安殿 · 重檐盝顶、平板与鎏金宝顶',target)
    from osm_site import rectangle
    _,_,ww,dd,_=rectangle(site.geom(QIN))
    swept_roof('钦安殿 下檐',group,p,origin=loc.world(),yaw=loc.yaw,width=ww,depth=dd,
               eave=DATUM+5.12,rise=1.49,tiles=True,pitch=.255,beasts=4,detail=2,
               upper_rectangle=(18.82,8.64),eave_lift=.49)
    roof_z=DATUM+TOP_BOARD[1]
    swept_roof('钦安殿 上檐',group,p,origin=loc.world(),yaw=loc.yaw,width=21.69,depth=11.31,
               eave=DATUM+8.52,rise=TOP_BOARD[1]-8.52,tiles=True,pitch=.252,beasts=4,detail=2,
               upper_rectangle=TOP_PLAN,eave_lift=.515)
    top=loc.batch()
    w,d=TOP_PLAN
    top.box((0,0,DATUM+sum(TOP_BOARD)/2),(w,d,TOP_BOARD[1]-TOP_BOARD[0]),p.door)
    board=top.finish('钦安殿 · 盝顶平板实测上下皮',group,properties={'source':TIMBER_SOURCE,'board_levels_from_base_m':TOP_BOARD})
    crest=loc.batch()
    top_poly=box(-w/2,-d/2,w/2,d/2)
    crest.solid_xy(top_poly,roof_z-.012,roof_z+.078,p.tiles[1])
    for side in (-1,1):
        for major in (False,True):
            run=w if major else d
            dist=d/2 if major else w/2
            yaw=0. if major else math.pi/2
            s=Batch()
            for high,thick,tall,mat in ((.122,.234,.157,p.tiles[0]),(.293,.196,.211,p.tiles[2]),(.472,.263,.114,p.tiles[1])):
                s.box((0,0,roof_z+high),(run+.216,thick,tall),mat)
            for i in range(round(run/.46)):
                x=run*((i+.5)/round(run/.46)-.5)
                for face in (-1,1):
                    cloud(s,(x,face*.113,roof_z+.288),.30,p.tiles[3],rotation=i*math.pi/5)
            transfer(crest,s,0 if major else side*dist,side*dist if major else 0,yaw)
        for y in (-d/2,d/2):
            terminal(crest,(side*w/2,y,roof_z+.26),side,.48,p.tiles[2],p)
    crest.lathe(0,0,((.63,roof_z+.05),(.64,roof_z+.24),(.60,roof_z+.325),(.44,roof_z+.422),
                    (.44,roof_z+.49),(.69,roof_z+.68),(.73,roof_z+.82),(.655,roof_z+1.047),
                    (.46,roof_z+1.264),(.33,roof_z+1.38),(.45,roof_z+1.51),(.48,roof_z+1.62),
                    (.605,roof_z+1.73),(.53,roof_z+1.84),(.44,roof_z+2.02),(.24,roof_z+2.118),
                    (.018,roof_z+2.18)),p.old_gold,sides=72)
    for side in (-1,1):
        for sy in (-1,1):
            crest.path([(.466*side,.32*sy,roof_z+1.58),(w*.15*side,d*.31*sy,roof_z+.96),
                        (w*.424*side,d*.488*sy,roof_z+.515)],.0092,p.old_gold,sides=7)
    for j in range(16):
        angle=j*math.tau/16
        crest.path([((.552-.128*t)*math.cos(angle+t*.20),(.552-.128*t)*math.sin(angle+t*.20),
                     roof_z+1.70+t*.372) for t in (i/14 for i in range(15))],.012,p.giltpaint,sides=5)
    crest.finish('钦安殿 · 四周花龙边脊、角吻和带拉链的金宝顶',group)
    return board


def roof_enclosure(site,loc,target,p):
    """Close the timber and masonry interfaces under the two sloping roof skirts."""
    from osm_site import rectangle

    _,_,ww,dd,_=rectangle(site.geom(QIN))
    group=collection('钦安殿 · 檐下墙顶、塞板与重檐夹层',target)
    b=loc.batch()

    def skirt_height(x,y,outer,inner,eave,rise,lift):
        rx,ry=outer[0]/2,outer[1]/2
        ix,iy=inner[0]/2,inner[1]/2
        tx,ty=(rx-abs(x))/(rx-ix),(ry-abs(y))/(ry-iy)
        t=min(1.,tx,ty)
        u=abs(y)/(ry+(iy-ry)*t) if tx<ty else abs(x)/(rx+(ix-rx)*t)
        return eave+rise*(.10*t+.90*t**1.71)+lift*u**8*(1-t)**2+.07*(1-t)**14

    def enclosure_ring(rx,ry,bottoms,gap,roof,side_materials,inside_material):
        for k,(a,c) in enumerate(zip(((-rx,-ry),(rx,-ry),(rx,ry),(-rx,ry)),
                                      ((rx,-ry),(rx,ry),(-rx,ry),(-rx,-ry)))):
            dx,dy=c[0]-a[0],c[1]-a[1]
            n=math.ceil(math.hypot(dx,dy)/.72)
            ux,uy=dy/math.hypot(dx,dy),-dx/math.hypot(dx,dy)
            vertices=[]
            for j in range(n+1):
                x,y=(a[0]+dx*j/n,a[1]+dy*j/n)
                # Extend the top into the roof's 190 mm sheathing.
                z=roof(x,y)-.093
                vertices.extend(((x,y,bottoms[k]),(x,y,z),(x-ux*gap,y-uy*gap,z),(x-ux*gap,y-uy*gap,bottoms[k])))
            for j in range(n):
                i=j*4
                b.add(vertices[i:i+8],((0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)),side_materials[k])
            for f in (.18,.62,.86):
                x,y=a[0]+dx*f,a[1]+dy*f
                b.box((x-ux*.152,y-uy*.152,(bottoms[k]+roof(x,y)-.21)/2),
                      (.073,.073,roof(x,y)-.21-bottoms[k]),inside_material)

    def lower(x,y):
        return skirt_height(x,y,(ww,dd),(18.82,8.64),DATUM+5.12,1.49,.49)

    def upper(x,y):
        return skirt_height(x,y,(21.69,11.31),TOP_PLAN,DATUM+8.52,TOP_BOARD[1]-8.52,.515)

    # Reach from the lattice and masonry heads to the underside of the lower eave.
    enclosure_ring(10.45,5.30,(FLOOR+3.47,DATUM+3.38,DATUM+3.47,DATUM+3.38),.17,lower,
                   (p.fascia,p.paint,p.paint,p.paint),p.door)
    lower_z=DATUM+5.12+1.49
    collar=box(-9.44,-4.35,9.44,4.35).difference(box(-8.83,-4.01,8.83,4.01))
    b.solid_xy(collar,lower_z-.142,lower_z-.048,p.door)
    enclosure_ring(8.90,4.08,(lower_z-.16,)*4,.146,upper,(p.door,)*4,p.fascia)
    ceiling_perimeter=box(-8.89,-4.08,8.89,4.08).difference(box(-8.56,-3.56,8.56,3.56))
    b.solid_xy(ceiling_perimeter,DATUM+CEILING+.012,DATUM+CEILING+.085,p.faded_blue)
    b.finish('钦安殿 · 护檐封护、重檐转接木与天花边板',group,properties={
        'dimensions_evidence':'The roof interfaces are inferred from the measured framing sections and the mapped eave envelope.'})


def enclosure(loc,target,p):
    group=collection('钦安殿 · 抱厦与槅扇装修',target)
    b,windows,small=(loc.batch() for _ in range(3))
    px,py=centres(LOW_FOOT_X),centres(LOW_FOOT_Y)
    for j,(a,c) in enumerate(zip(px,px[1:])):
        shutter(windows,(a+c)/2,py[0]+.043,FLOOR+.112,c-a-.49,3.40,p,open_center=j==2)
    # Side and rear walls remain solid but keep the front hall free of an invisible bulk mesh.
    for side in (-1,1):
        b.box((side*(sum(LOW_FOOT_X)/2+.31),0,(FLOOR+DATUM+3.60)/2),(.39,10.15,DATUM+3.60-FLOOR),p.paint)
    b.box((0,py[-1]+.16,(FLOOR+DATUM+3.64)/2),(sum(LOW_FOOT_X)+.94,.375,DATUM+3.64-FLOOR),p.paint)
    x0,y0,x1,y1=ANNEX_EXTENT
    yfront=y0+.72
    xs=(-7.36,-2.315,2.315,7.36)
    for x in xs:
        pp=loc.batch()
        pp.lathe(x,yfront,((.331,FLOOR),(.326,FLOOR+.095),(.261,FLOOR+.189)),p.stone,sides=24)
        pp.lathe(x,yfront,((.25,FLOOR+.172),(.245,FLOOR+.36),(.218,5.08)),p.red,sides=24)
        pp.finish('钦安殿 抱厦 · 前檐柱 '+str(x),group)
    for j,(a,c) in enumerate(zip(xs,xs[1:])):
        xx=(a+c)/2
        painted_bay(b,xx,yfront,5.11,c-a-.012,p,height=.435)
        for i in range(5):
            bracket(small,a+i*(c-a)/5,yfront,5.32,0,p)
        shutter(windows,xx,yfront+.054,FLOOR+.088,c-a-.44,3.32,p,open_center=j==1)
    for side in (-1,1):
        cx=side*7.36
        for a,c in ((yfront,-10.11),(-10.11,-6.01)):
            yy=(a+c)*.5
            painted_bay(b,cx,yy,5.11,c-a,p,yaw=side*math.pi/2,height=.435)
            shutter(windows,cx,yy,FLOOR+.075,c-a-.47,3.27,p,yaw=side*math.pi/2)
        small.lathe(cx,-10.11,((.317,FLOOR),(.269,FLOOR+.16)),p.stone,sides=22)
        small.lathe(cx,-10.11,((.236,FLOOR+.14),(.206,5.12)),p.red,sides=24)
    b.finish('钦安殿 · 后山墙、抱厦大额枋与支承',group)
    windows.finish('钦安殿 · 独立格心、裙板与明间开启扇',group)
    small.finish('钦安殿 · 抱厦耳柱及檐下承托',group)
    swept_roof('钦安殿 抱厦黄瓦',group,p,origin=loc.world(0,(y0+y1)/2),yaw=loc.yaw,width=x1-x0,depth=y1-y0,
               eave=5.942,rise=1.129,kind='xieshan',tiles=True,pitch=.25,detail=2,beasts=3,terminal_height=.63)
    plaque(loc,group,'钦安殿',0,-4.53,DATUM+7.45,.66,.79,p,
           ('north_qinan_plaque.jpg','https://img.dpm.org.cn/Uploads/Picture/2020/07/03/s5efef832a6177.jpg'))


def ceiling(loc,target,p):
    group=collection('钦安殿 · 天花与内凹藻井',target)
    z=DATUM+CEILING
    b,g,frieze=(loc.batch() for _ in range(3))
    width,depth=17.18,7.18
    ring=Polygon(ring_outline(1.70))
    void=box(-1.71,-1.71,1.71,1.71)
    for i in range(20):
        for j in range(8):
            x=(i+.5)*width/20-width/2;y=(j+.5)*depth/8-depth/2
            a=box(x-width/40+.028,y-depth/16+.028,x+width/40-.028,y+depth/16-.028).difference(void)
            for shape in polygons(a):
                b.solid_xy(shape,z,z+.062,p.faded_teal)
                if shape.area>.57:
                    flower(g,x,y,z-.012,.192,p.cream,p.giltpaint)
                    for dx in (-1,1):
                        cloud(g,(x+dx*.26,y+.17*dx,z-.008),.201,p.giltpaint,facing='ceiling')
    b.solid_xy(void.difference(ring),z,z+.11,p.faded_blue)
    for i in range(21):
        x=i*width/20-width/2
        for p0,p1 in ((-depth/2,depth/2),) if abs(x)>1.76 else ((-depth/2,-1.7),(1.7,depth/2)):
            frieze.box((x,(p0+p1)/2,z-.043),(.074,p1-p0,.086),p.fascia)
    for j in range(9):
        y=j*depth/8-depth/2
        for p0,p1 in ((-width/2,width/2),) if abs(y)>1.76 else ((-width/2,-1.7),(1.7,width/2)):
            frieze.box(((p0+p1)/2,y,z-.045),(p1-p0,.071,.084),p.faded_blue)
    levels=((1.70,z),(1.62,z+.136),(1.48,z+.31),(1.38,z+.43),(1.20,z+.62),(1.11,z+.794))
    for j,((a,za),(c,zc)) in enumerate(zip(levels,levels[1:])):
        lower,upper=ring_outline(a),ring_outline(c)
        for i in range(8):
            k=(i+1)%8
            b.face([(*lower[i],za),(*upper[i],zc),(*upper[k],zc),(*lower[k],za)],p.faded_blue if j%2 else p.old_gold)
            frieze.rod((*lower[i],za-.012),(*lower[k],za-.012),.032,p.giltpaint,sides=8)
            for t in (.21,.50,.79):
                u=(lower[i][0]+upper[i][0])*(1-t)/2+(lower[k][0]+upper[k][0])*t/2
                v=(lower[i][1]+upper[i][1])*(1-t)/2+(lower[k][1]+upper[k][1])*t/2
                cloud(g,(u,v,(za+zc)/2-.023),.22,p.giltpaint,facing='ceiling',rotation=i*math.pi/4)
    crown=levels[-1][1]
    b.solid_xy(Polygon(ring_outline(levels[-1][0])),crown,crown+.062,p.faded_blue)
    dragon(g,(0,0,crown-.019),1.44,1.56,SimpleNamespace(gold=p.old_gold,giltpaint=p.giltpaint,door=p.door),facing='ceiling')
    g.ellipsoid((0,.36,crown-.124),(.144,.144,.105),p.old_gold,sides=24,rings=11)
    b.finish('钦安殿 · 井口板、天花下皮与八方井壁',group,properties={'ceiling_underside_m_from_column_base':CEILING})
    frieze.finish('钦安殿 · 天花梁格与藻井边枋',group)
    g.finish('钦安殿 · 内井金龙及云纹饰面',group)


def build_qinan(site,loc,target,p):
    group=collection('钦安殿 · 实测大木与御花园中轴',target)
    group['source_osm_id']=QIN
    group['survey_paper']=TIMBER_SOURCE
    group['museum_source']=QIN_SOURCE
    data=source_report()
    data['column_counts']=framing(loc,group,p)
    plinth(site,loc,group,p)
    enclosure(loc,group,p)
    roofwork(site,loc,group,p)
    roof_enclosure(site,loc,group,p)
    ceiling(loc,group,p)
    data['collection']=group.name
    return group,data
