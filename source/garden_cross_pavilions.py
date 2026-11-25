"""Native pavilion assemblies based on Garden plan figure 14 and museum photographs."""
import math
from types import SimpleNamespace

from mathutils import Vector
from shapely.affinity import rotate
from shapely.geometry import LineString, Point, Polygon, box

from garden_bridge_pavilions import laid_pavers, transfer
from garden_cross_plan import FLOOR, MUSEUM, PLAN_PAPER, PLAZA_FLOOR, in_side, map_plan, side_frame
from garden_cross_roofs import DRUM_R, LOW_CREST, LOW_EAVE, UP_EAVE, lower_roof, umbrella_roof
from garden_cross_room import upper_room
from mesh_tools import Batch, collection
from palace_architecture import arch_mesh
from palace_materials import paint
from qinan_hall import bracket, painted_bay, plaque

IMAGE_BASE='https://img.dpm.org.cn/Uploads/Picture/2020/04/20/'
INNER_WALL=3.33
FRAME_HEAD=4.90


def palette(base):
    p=SimpleNamespace(**base.__dict__)
    p.twin_glaze=[]
    for i,(lo,hi) in enumerate((((.44,.234,.044),(.76,.499,.136)),((.39,.207,.064),(.57,.356,.109)),
                                ((.46,.24,.044),(.70,.479,.122)),((.34,.180,.042),(.64,.421,.129)),
                                ((.36,.210,.075),(.67,.453,.182)))):
        mat=paint(f'万春千秋 · 斑驳黄釉 {i+1}',lo,second=hi,scale=14.8,rough=.40,grain=111,bump=.004,coat=.21)
        nodes=mat.node_tree.nodes;links=mat.node_tree.links
        glint=nodes.new('ShaderNodeTexNoise');glint.inputs['Scale'].default_value=61.;glint.inputs['Detail'].default_value=4.
        geometry=nodes.new('ShaderNodeNewGeometry');links.new(geometry.outputs['Position'],glint.inputs['Vector'])
        mask=nodes.new('ShaderNodeValToRGB');mask.color_ramp.elements[0].position=.603
        mask.color_ramp.elements[1].position=.712;links.new(glint.outputs['Fac'],mask.inputs[0])
        mix=nodes.new('ShaderNodeMixRGB');mix.inputs[2].default_value=(.242,.191,.133,1.)
        glaze=next(n for n in nodes if n.type=='VALTORGB' and n!=mask)
        links.new(mask.outputs[0],mix.inputs[0]);links.new(glaze.outputs[0],mix.inputs[1])
        links.new(mix.outputs[0],nodes.get('Principled BSDF').inputs['Base Color'])
        p.twin_glaze.append(mat)
    p.terracotta=paint('万春千秋 · 瓦当暗底',(.158,.106,.046),second=(.37,.268,.137),scale=35.,rough=.77,grain=92,bump=.009)
    p.enamel=paint('万春千秋 · 绿釉宝瓶与龟背锦',(.030,.117,.076),second=(.091,.240,.123),
                   scale=12.9,rough=.35,grain=113,bump=.004,coat=.31)
    p.bronze_twin=paint('万春千秋 · 风化铜活',(.079,.069,.044),second=(.245,.191,.08),scale=26.,
                        rough=.52,grain=99,bump=.003,metal=.76)
    return p


def in_world_side(loc,side,x,y,z=0.):
    c,s=math.cos(side_frame(side)),math.sin(side_frame(side))
    return loc.world(x*c-y*s,x*s+y*c,z)


def rail_panel(b,w,z,p,y=0.,slope=0.,bases=True):
    def raised(u,v,h):return (u,v+y,h+slope*(u+w/2))
    main=Batch()
    region=box(-w/2+.065,z+.087,w/2-.065,z+.817)
    for i in (-1,1):
        u=i*w*.195;s=min(.111,w*.115)
        hole=Polygon([(u+x*s,z+h) for x,h in ((-1.20,.51),(-1.20,.605),(-.78,.62),(-.68,.68),
                    (-.37,.68),(-.32,.728),(.32,.728),(.37,.68),(.68,.68),(.78,.62),(1.20,.605),
                    (1.20,.51),(.79,.493),(.66,.442),(.27,.448),(0,.422),(-.27,.448),(-.66,.442),(-.79,.493))])
        region=region.difference(hole)
        main.path([(u+s*.68*math.cos(a),-.066,z+.267+.072*math.sin(a))
                   for a in (j*math.tau/23 for j in range(24))],.007,p.understone,sides=5)
    arch_mesh(main,region,.118,p.stone)
    main.box((0,0,z+.806),(w,.161,.064),p.stone)
    main.box((0,0,z+.084),(w,.178,.084),p.stone)
    main.v=[raised(*v) for v in main.v]
    transfer(b,main,0,0,0)
    if bases:
        for u in (-w/2,w/2):
            x,v,level=raised(u,0,z)
            b.box((x,v,level+.405),(.186,.18,.815),p.stone)
            b.box((x,v,level+.049),(.237,.228,.091),p.understone)
            b.lathe(x,v,((.104,level+.789),(.099,level+.849),(.085,level+.886),(.087,level+.937),
                         (.054,level+1.016),(.020,level+1.082)),p.stone,sides=21)


def basework(twin,loc,target,p,deck,stairs):
    platform=collection('白石墩台 · 亚字须弥座与四向踏道',target)
    b,flag,rail=(loc.batch() for _ in range(3))
    for grow,lo,hi,mat in ((.095,PLAZA_FLOOR,.112,p.understone),(.048,.112,.266,p.stone),(.014,.266,.381,p.understone),
                           (-.028,.381,FLOOR-.245,p.stone),(.058,FLOOR-.245,FLOOR-.175,p.understone),
                           (.076,FLOOR-.175,FLOOR-.082,p.stone),(.033,FLOOR-.082,FLOOR-.035,p.stone)):
        b.solid_xy(deck.buffer(grow,join_style=2),lo,hi,mat,way=int(twin.terrace))
    laid_pavers(flag,deck,FLOOR,p,course=.438,width=.743)
    stair_info=[]
    openings=[]
    for side,shape in enumerate(stairs):
        a,low,c,_=shape.bounds
        inset=.18
        x=(a+c)/2
        local_deck=in_side(deck,side)
        touching=local_deck.intersection(LineString(((x,-15),(x,0))))
        edge=touching.bounds[1]
        y0=min(low,edge-1.85);y1=edge+.016
        w=c-a-inset*2
        count=7
        work=Batch();steel=Batch()
        for i in range(count):
            ya=y0+(y1-y0)*i/count;yb=y0+(y1-y0)*(i+1)/count
            top=PLAZA_FLOOR+(FLOOR-PLAZA_FLOOR)*(i+1)/count
            work.box((x,(ya+yb)/2,(top+PLAZA_FLOOR)/2),(w,yb-ya+.011,top-PLAZA_FLOOR),p.stone)
            work.box((x,(ya+yb)/2-.009,top-.023),(w+.032,yb-ya+.031,.045),p.stone)
        for sign in (-1,1):
            fill=Batch()
            rise=FLOOR-PLAZA_FLOOR
            span=y1-y0
            arch_mesh(fill,Polygon(((0,PLAZA_FLOOR),(span,PLAZA_FLOOR),(span,FLOOR+.079),(0,PLAZA_FLOOR+.074))),.19,p.stone)
            transfer(work,fill,x+sign*(w/2+.108),y0,math.pi/2)
            panel=Batch()
            rail_panel(panel,span,PLAZA_FLOOR,p,slope=rise/span)
            transfer(steel,panel,x+sign*(w/2+.108),(y0+y1)/2,math.pi/2)
        added=Batch(loc.world(),loc.yaw)
        transfer(added,work,0,0,side_frame(side))
        added.finish('台阶 · '+('南','东','北','西')[side]+'抱厦踏面与垂带',platform,
                     properties={'source_osm_id':twin.stairs[side],'tread_count':count})
        transfer(rail,steel,0,0,side_frame(side))
        openings.append((side,x,w/2+.22,edge))
        stair_info.append({'side':side,'width_m':round(w,3),'run_m':round(y1-y0,3),'treads':count,
                           'mapped_way':twin.stairs[side],'local_centre_xy':(x,(y0+y1)/2),'start_end_y':(y0,y1)})
    boundary=deck.buffer(-.123,join_style=2).simplify(.035,preserve_topology=True)
    for a,c in zip(list(boundary.exterior.coords),list(boundary.exterior.coords)[1:]):
        ln=LineString((a,c))
        for side,x,w,edge in openings:
            opening=rotate(box(x-w,edge-.50,x+w,edge+.56),math.degrees(side_frame(side)),origin=(0,0))
            ln=ln.difference(opening)
        for line in getattr(ln,'geoms',(ln,)):
            if line.length>.42:
                first,last=line.coords[0],line.coords[-1]
                length=line.length;parts=max(1,round(length/1.29))
                angle=math.atan2(last[1]-first[1],last[0]-first[0]);panel=Batch()
                for j in range(parts):
                    u=length*(j+.5)/parts
                    part=Batch();rail_panel(part,length/parts,FLOOR,p)
                    transfer(panel,part,u,0,0)
                transfer(rail,panel,*first,angle)
    b.finish('亚字台基 · 分层石作线脚',platform)
    flag.finish('亚字台基 · 连续墁地石面',platform,properties={'platform_elevation_m':FLOOR})
    rail.finish('亚字台基 · 透雕栏板、望柱与斜栏',platform)
    return stair_info


def hex_lattice(b,x,z,w,h,p,*,spacing=.111):
    clip=box(x-w/2,z-h/2,x+w/2,z+h/2)
    span=math.hypot(w,h)
    for n,direction in enumerate((math.pi/6,math.pi/2,5*math.pi/6)):
        t=Vector((math.cos(direction),math.sin(direction)))
        v=Vector((-t.y,t.x));center=Vector((x,z))
        for i in range(-math.ceil(span/spacing),math.ceil(span/spacing)+1):
            point=center+v*spacing*(i+(0.34 if n==2 else .13))
            edge=LineString((point-span*t,point+span*t)).intersection(clip)
            if edge.geom_type!='LineString' or edge.length<.006:continue
            a,c=edge.coords[0],edge.coords[-1]
            b.beam((a[0],-.023+n*.012,a[1]),(c[0],-.023+n*.012,c[1]),.022,.015,p.red)


def timber_panel(b,x,z,w,h,p,*,door=False,open_leaf=False):
    for s in (-1,1):
        b.box((x+s*(w/2-.034),0,z+h/2),(.071,.121,h),p.red)
        b.box((x,0,z+(.039 if s<0 else h-.039)),(w,.123,.078),p.red)
    bottom=z+(h*.284 if door else .114)
    b.box((x,0,bottom-.027),(w-.088,.123,.067),p.fascia)
    if door:
        b.box((x,.007,(z+.060+bottom)*.5),(w-.095,.076,bottom-z-.086),p.door)
        for s in (-1,1):
            b.box((x+s*(w/2-.098),-.047,(z+.067+bottom)*.5),(.012,.014,bottom-z-.112),p.old_gold)
    hex_lattice(b,x,(bottom+z+h-.072)/2,w-.125,z+h-.091-bottom,p)
    if door:
        offset=(math.copysign(1.,x) if open_leaf else 1)*w*.305
        b.ellipsoid((x+offset,-.066,z+h*.435),(.033,.012,.054),p.bronze_twin,sides=12,rings=7)
        b.path([(x+offset+.028*math.cos(a),-.083,z+h*.428+.035*math.sin(a))
                for a in (i*math.tau/21 for i in range(22))],.0055,p.bronze_twin,sides=5)


def sill_tiles(b,width,base,top,p):
    b.box((0,.004,(base+top)/2),(width,.228,top-base),p.enamel)
    h=top-base-.073;count=round(width/.194)
    for i in range(count):
        x=width*((i+.5)/count-.5)
        r=.110
        for z in (base+.102+(i%2)*.093,base+.286+(i%2)*.093,base+.470+(i%2)*.093):
            outline=[(x+r*math.cos(i*math.tau/6),-.114,z+r*math.sin(i*math.tau/6)) for i in range(7)]
            if z+r<base+h+.035:
                b.path(outline,.0086,p.twin_glaze[2],sides=5)
    b.box((0,0,top+.015),(width+.033,.282,.065),p.red)
    b.box((0,0,base+.043),(width+.023,.27,.060),p.stone)


def doorway(twin,loc,target,side,p,x,y,width,open_angle,label):
    orient=loc.yaw+side_frame(side)
    start=FLOOR+.033;height=2.85;jamb=loc.batch();part=Batch()
    for sign in (-1,1):
        part.box((x+sign*width*.5,y, start+height*.5),(.123,.26,height),p.red)
        part.box((x+sign*(width*.5-.081),y-.132,start+height*.5),(.018,.018,height),p.giltpaint)
        pivot=x+sign*(width/2-.079)
        leaf=Batch(in_world_side(loc,side,pivot,y+.013),orient+sign*open_angle)
        w=(width-.200)/2
        timber_panel(leaf,-sign*w/2,start+.118,w,height-.206,p,door=True,open_leaf=True)
        leaf.finish(f'{twin.name} · {label} {("南","东","北","西")[side]} {sign:+d}',target,properties={
            'closed_world_yaw_rad':orient,'door_layer':label,'side':side,'designed_viewing_pose':abs(open_angle)>1.})
    part.box((x,y,start+.053),(width+.10,.258,.106),p.fascia)
    part.box((x,y,start+height+.032),(width+.154,.25,.125),p.red)
    if label=='外门':
        transom=Batch()
        timber_panel(transom,x,start+height+.101,width+.10,FRAME_HEAD-start-height-.079,p)
        transfer(part,transom,0,y,0)
    transfer(jamb,part,0,0,side_frame(side));jamb.finish(f'{twin.name} · {label}门枋 {side}',target)


def timberwork(twin,loc,target,p,dimensions):
    group=collection('方亭 · 红漆柱、龙锦梁枋和三交六椀木格',target)
    inner=collection('方亭 · 平面图所示四柱和四道重门',target)
    walls,wood=(loc.batch() for _ in range(2))
    sx,sy=(v/2 for v in dimensions['outer_timber_spans_m'])
    cx,cy=4.00,3.96
    half=2.34
    runs=[(cx,cy,sy),(cy,cx,sx),(cx,cy,sy),(cy,cx,sx)]
    centres=[]
    for side,(corner,core,front) in enumerate(runs):
        y0=-front
        for x,y in ((-corner,-core),(-half,y0),(half,y0)):
            centre=in_world_side(loc,side,x,y)
            post=Batch(centre,loc.yaw)
            post.lathe(0,0,((.287,FLOOR),(.278,FLOOR+.047),(.243,FLOOR+.162)),p.stone,sides=28)
            post.lathe(0,0,((.228,FLOOR+.158),(.218,FLOOR+.363),(.202,FRAME_HEAD+.031)),p.red,sides=32)
            post.finish(f'{twin.name} · 外檐柱 {len(centres)+1:02d}',group,properties={'post_role':'outer_eave'})
            centres.append(centre[:2])
        # The two sidelights and four returns surround each double-door opening.
        doorway(twin,loc,group,side,p,0,y0,2.06,1.39,'外门')
        doorway(twin,loc,inner,side,p,0,-INNER_WALL,2.08,1.43,'内重门')
        spans=[((-half,y0),(-1.03,y0)),((1.03,y0),(half,y0)),
               ((-corner,-core),(-half,-core)),((half,-core),(corner,-core)),
               ((-half,-core),(-half,y0)),((half,y0),(half,-core))]
        for i,(a,c) in enumerate(spans):
            w=math.dist(a,c)-.191
            x,y=(a[0]+c[0])/2,(a[1]+c[1])/2
            angle=math.atan2(c[1]-a[1],c[0]-a[0])
            if i in (4,5):angle+=math.pi
            local=Batch();sill_tiles(local,w,FLOOR+.039,FLOOR+.711,p)
            for sign in (-1,1):
                timber_panel(local,sign*(w/4),FLOOR+.772,w/2-.022,2.057,p)
            cap_low=FLOOR+2.834
            local.box((0,0,(FRAME_HEAD+cap_low)/2),(w,.195,FRAME_HEAD-cap_low),p.fascia)
            local.box((0,-.088,FLOOR+2.919),(w+.05,.081,.109),p.red)
            piece=Batch();transfer(piece,local,x,y,angle)
            transfer(walls,piece,0,0,side_frame(side))
        pframe=Batch()
        outline=[(-corner,-core),(-half,-core),(-half,y0),(half,y0),(half,-core),(corner,-core)]
        for i,(a,c) in enumerate(zip(outline,outline[1:])):
            x,y=((a[0]+c[0])/2,(a[1]+c[1])/2);w=math.dist(a,c)
            angle=math.atan2(c[1]-a[1],c[0]-a[0]);angle+=math.pi if i in (1,3) else 0
            painted_bay(pframe,x,y,FRAME_HEAD+.125,w+.055,p,yaw=angle,height=.375)
            painted_bay(pframe,x,y,FRAME_HEAD+.561,w+.055,p,yaw=angle,height=.448)
            steps=max(2,round(w/.69))
            for k in range(steps):
                f=(k+.39)/steps
                bracket(pframe,a[0]+(c[0]-a[0])*f,a[1]+(c[1]-a[1])*f,FRAME_HEAD+.799,angle,p)
            pframe.beam((*a,LOW_EAVE-.295),(*c,LOW_EAVE-.295),.292,.328,p.fascia)
            pframe.beam((*a,FRAME_HEAD+.984),(*c,FRAME_HEAD+.984),.164,.49,p.door)
        transfer(wood,pframe,0,0,side_frame(side))
        fill=loc.batch();v=Batch()
        for sign in (-1,1):
            w=INNER_WALL-1.03
            x=sign*(INNER_WALL+1.03)/2
            v.box((x,-INNER_WALL,(FLOOR+FRAME_HEAD)/2),(w,.199,FRAME_HEAD-FLOOR),p.paint)
            v.box((x,-INNER_WALL-.105,FLOOR+.944),(w,.054,1.731),p.red)
        v.box((0,-INNER_WALL,4.68),(2.092,.204,.573),p.fascia)
        transfer(fill,v,0,0,side_frame(side));fill.finish('抱厦与亭心之间 · 内墙 '+str(side),inner)
    for x in (-INNER_WALL,INNER_WALL):
        for y in (-INNER_WALL,INNER_WALL):
            post=loc.batch();post.lathe(x,y,((.296,FLOOR),(.28,FLOOR+.125),(.243,FLOOR+.190)),p.stone,sides=28)
            post.lathe(x,y,((.233,FLOOR+.16),(.221,FLOOR+.32),(.204,6.74)),p.red,sides=32)
            post.finish(f'{twin.name} · 内方柱 {x:+.2f},{y:+.2f}',inner,properties={'post_role':'four_main_corners'})
    walls.finish('抱厦 · 透空三交六椀格心与实砌绿釉槛墙',group)
    wood.finish('抱厦 · 双层梁枋、下檐斗栱与檩木',group)
    return len(centres)


def lantern(twin,loc,target,p):
    group=collection('圆亭上身 · 红柱、漏窗与上檐斗栱',target)
    timber,window,glaze=(loc.batch() for _ in range(3))
    n=12
    board_bottom=LOW_CREST-.124
    r=DRUM_R
    face_r=r*math.cos(math.pi/n)
    width=2*r*math.sin(math.pi/n)
    for i in range(n):
        a=-math.pi/2+i*math.tau/n;x,y=face_r*math.cos(a),face_r*math.sin(a)
        angle=a+math.pi/2;piece=Batch()
        piece.box((0,0,board_bottom+.125),(width+.008,.153,.268),p.red)
        piece.box((0,0,UP_EAVE-.762),(width+.012,.162,.186),p.red)
        opening=.57
        for sign in (-1,1):
            piece.box((sign*(width+opening)/4,0,(board_bottom+.22+UP_EAVE-.79)/2),
                      ((width-opening)/2+.007,.158,UP_EAVE-.79-board_bottom-.22),p.red)
        # Individual recessed perforated panes instead of a dark square decal.
        pane=box(-.299,board_bottom+.23,.299,UP_EAVE-.739)
        for j in range(3):
            for k in range(6):
                pane=pane.difference(Point((k-2.5)*.086,board_bottom+.327+j*.096).buffer(.032,quad_segs=5))
        arch_mesh(piece,pane,.048,p.fascia)
        for sign in (-1,1):
            piece.box((sign*.300,-.056,(board_bottom+.23+UP_EAVE-.74)*.5),(.033,.042,UP_EAVE-.74-board_bottom-.23),p.giltpaint)
        transfer(window,piece,x,y,angle)
        painted_bay(timber,x,y,UP_EAVE-.608,width+.040,p,yaw=angle,height=.286)
        for j in (-1,0,1):
            u=j*width*.33
            bracket(timber,x+u*math.cos(angle),y+u*math.sin(angle),UP_EAVE-.451,angle,p,upper=True)
        t=a+math.pi/n
        timber.lathe(r*math.cos(t),r*math.sin(t),((.092,board_bottom),(.096,UP_EAVE-.48)),p.red,sides=14)
    for radius,z,mat in ((face_r+.022,board_bottom+.219,p.twin_glaze[2]),(r+.056,UP_EAVE-.228,p.fascia)):
        glaze.path([(radius*math.cos(i*math.tau/160),radius*math.sin(i*math.tau/160),z) for i in range(161)],.070,mat,sides=8)
    window.finish('高窗 · 十二组透眼花格与朱漆墙',group)
    timber.finish('上檐 · 石青石绿圆枋、五踩斗栱及圆柱',group)
    glaze.finish('上檐 · 黄釉束圈和连檐木',group)
    panel=('cross_wanchun_plaque.jpg' if twin.name=='万春亭' else 'cross_qianqiu_plaque.jpg')
    plaque(loc,group,twin.name,0,-r-.318,UP_EAVE-.574,.535,.772,p,(panel,IMAGE_BASE+twin.plaque))


def build_twin(site,twin,target,base):
    p=palette(base)
    loc,outline,stairs,metrics=map_plan(site,twin)
    group=collection(twin.name+' · 亚字平面和重檐圆攒尖',target)
    group['source_osm_id']=twin.way
    group['museum_source']=MUSEUM
    group['plan_figure_14_source']=PLAN_PAPER
    group['part_elevations_are_inferred']=True
    stairs_info=basework(twin,loc,group,p,outline,stairs)
    posts=timberwork(twin,loc,group,p,metrics)
    lower_roof(loc,group,p,metrics['lower_corner_extents'])
    lantern(twin,loc,group,p)
    umbrella_roof(loc,group,p,metrics['upper_eave_radius_m'])
    room_info=upper_room(twin,loc,group,p)
    return loc,group,{'name':twin.name,'collection':group.name,'map_outline':twin.way,'map_relation':twin.relation,
           'sources':{'museum':MUSEUM,'plan_fig_14':PLAN_PAPER,'plaque':IMAGE_BASE+twin.plaque,'architecture_photo':IMAGE_BASE+twin.photograph},
           'map_dimensions':metrics,'reference_features':{'annexes':4,'stairs':4,'roof':'lower square, upper round bamboo-joint tile',
           'second_door_layer':True,'ceiling_subject':'paired phoenix panels and gilded coiled dragon holding a pearl'},
           'model_estimates':{'floor_z_m':FLOOR,'main_four_inner_posts_pitch_m':INNER_WALL*2,'outer_posts':posts,
                              'lower_eave_z_m':LOW_EAVE,'upper_eave_z_m':UP_EAVE,'stairs':stairs_info,'interior':room_info}}
