"""Native open porches, recessed fenestration, rear walls and laid roof tiles.

Only the four long mapped ranges are rebuilt here. Gate junction pieces, their
count boundary and the gate/gallery level transition are expressly not certified.
"""
import math
from types import SimpleNamespace

from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from architectural_roofs import swept_roof
from cross_axis_galleries_plan import (BAY_COUNT, EAVE, FLOOR, PAVER_RECESS,
                                      PAVER_THICKNESS, POST_TOP, RIDGE_SHELL,
                                      STATUS, plan, record)
from mesh_tools import collection
from paired_halls import column, frame
from palace_materials import paint


def materials(base):
    p = SimpleNamespace(**base.__dict__)
    def mat(label, a, b, **kwargs):
        return paint('朝房廊庑 · '+label, a, second=b, **kwargs)
    p.red = mat('旧朱漆柱木', (.145, .017, .012), (.255, .036, .024),
                rough=.64, scale=3.4, grain=450, bump=.00035, coat=.05)
    p.door = mat('暗朱门板', (.10, .012, .009), (.195, .026, .018),
                 rough=.67, scale=4., grain=480, bump=.0003)
    p.blue = mat('梁枋石青', (.014, .043, .090), (.028, .084, .156),
                 rough=.69, scale=6., grain=460, bump=.00020)
    p.teal = mat('梁枋石绿', (.018, .077, .061), (.036, .139, .107),
                 rough=.70, scale=6., grain=460, bump=.00020)
    p.giltpaint = mat('细金线', (.34, .225, .080), (.58, .407, .157),
                      rough=.64, scale=24., grain=500, bump=.0001)
    p.marble = mat('柱础青白石', (.29, .295, .277), (.46, .451, .411),
                   rough=.86, scale=4., grain=420, bump=.0005)
    p.brick = mat('后檐青砖', (.13, .14, .13), (.235, .24, .217),
                  rough=.92, scale=4., grain=420, bump=.0005, brick=(.49, .13, .0025, True))
    p.plaster = mat('山墙朱红灰面', (.22, .040, .026), (.32, .065, .042),
                    rough=.92, scale=2., grain=420, bump=.00045)
    p.mortar = mat('铺砖凹缝灰浆', (.125, .135, .125), (.175, .18, .16),
                   rough=.96, scale=24., grain=500, bump=.00025)
    p.pavers = [mat('廊下铺砖 '+str(i), c, tuple(v*1.18 for v in c),
                    rough=.89, scale=6., grain=430, bump=.0005)
                 for i, c in enumerate(((.18,.19,.175), (.205,.213,.195),
                                         (.225,.23,.209), (.195,.20,.184)))]
    p.roof = mat('黄瓦灰背底色', (.28, .11, .018), (.41, .18, .029),
                 rough=.68, scale=12., grain=450, bump=.0004)
    p.tiles = [mat('黄琉璃瓦 '+str(i), c, tuple(v*1.13 for v in c),
                   rough=.34+i*.014, scale=24., grain=480, bump=.00012, coat=.11)
                for i,c in enumerate(((.51,.235,.034), (.55,.265,.043), (.58,.286,.051),
                                        (.53,.25,.039), (.565,.272,.046)))]
    p.roof_under = mat('望板暗木', (.040,.023,.016), (.069,.041,.026),
                       rough=.94, scale=6., grain=450, bump=.00035)
    p.interior = mat('未布置室内灰面', (.16,.148,.124), (.24,.227,.196),
                     rough=.96, scale=4., grain=450, bump=.0003)
    return p


def pavement(tiles, mortar, footprint, p):
    x0, y0, x1, y1 = footprint.bounds
    pieces = []
    for j in range(math.ceil((y1-y0)/.58)):
        y = y0+j*.58
        for i in range(-1, math.ceil((x1-x0)/.86)+1):
            x = x0+(i+.5*(j%2))*.86
            piece = footprint.intersection(box(x+.004, y+.004, x+.856, y+.576))
            if piece.is_empty or piece.area<.00001:
                continue
            tiles.solid_xy(piece, FLOOR-PAVER_THICKNESS, FLOOR,
                           p.pavers[(i+3*j)%len(p.pavers)], bottom=False)
            pieces.append(piece)
    joints = footprint.difference(unary_union(pieces))
    mortar.solid_xy(joints, FLOOR-PAVER_THICKNESS, FLOOR-PAVER_RECESS, p.mortar, bottom=False)
    return {'pavers': len(pieces), 'paver_top_m': FLOOR,
            'joint_top_m': FLOOR-PAVER_RECESS,
            'paver_area_m2': sum(x.area for x in pieces),
            'joint_area_m2': joints.area,
            'footprint_area_m2': footprint.area,
            'joint_layout': 'Explicitly disjoint recessed native mortar solids; no coplanar support face.'}


def diamond_lattice(b, x, y, z, width, height, p):
    """Diagonal bars seen in the photos, without invented floral rosettes."""
    limits = box(-width/2, 0, width/2, height)
    length = math.hypot(width, height)+.2
    for index, sign in enumerate((-1, 1)):
        for j in range(-math.ceil(length/.145), math.ceil(length/.145)+1):
            offset = j*.145
            line = LineString(((-length, sign*-length+offset),
                               (length, sign*length+offset))).intersection(limits)
            if line.geom_type=='LineString' and line.length>.025:
                a, c = line.coords[0], line.coords[-1]
                b.rod((x+a[0], y-index*.006, z+a[1]),
                      (x+c[0], y-index*.006, z+c[1]), .008, p.red, sides=6)


def closed_leaf(b, x, y, z, width, height, p):
    frame(b, x, y, z+height/2, width, height, .063, p.red)
    # Lower solid panel; the upper geometric lattice opens into a hollow room.
    ph = .67
    b.box((x, y+.023, z+ph/2), (width-.10, .068, ph), p.door)
    frame(b, x, y-.020, z+ph/2, width-.20, ph-.17, .019, p.red)
    b.box((x, y, z+ph), (width-.05, .073, .086), p.red)
    diamond_lattice(b, x, y-.026, z+ph+.047,
                    width-.14, height-ph-.115, p)


def queti(b, x, y, sign, z, p):
    """Small flat bracket board; dimensions and outline remain interpreted."""
    points = [(0,.28), (.94,.28), (.94,.13), (.80,.13), (.76,.04),
              (.63,.04), (.57,-.07), (.43,-.07), (.38,-.19), (.17,-.19), (.11,-.26), (0,-.26)]
    face = [(x+sign*u, y, z+v) for u,v in points]
    b.face(face, p.blue)
    b.face([(a,c+.085,d) for a,c,d in reversed(face)], p.blue)
    for a,c in zip(face, face[1:]+face[:1]):
        b.face((a,c,(c[0],c[1]+.085,c[2]),(a[0],a[1]+.085,a[2])),p.blue)
    b.path([(a, c-.007, d+.018) for a,c,d in face[2:]], .010, p.giltpaint, sides=5)


def end_infill(b, x, a, c, thickness, q, p):
    # Physical end wall follows the modeled underside, leaving the porch open.
    profile = [(a, FLOOR), (c, FLOOR)]
    profile += [(c+(a-c)*i/32, q.roof_z(c+(a-c)*i/32)-.205) for i in range(33)]
    v = [(xx,y,z) for xx in (x-thickness/2, x+thickness/2) for y,z in profile]
    n = len(profile)
    faces = [tuple(reversed(range(n))), tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    b.add(v,faces,p.plaster)


def build_range(site, spec, parent, p):
    q = plan(site,spec)
    group = collection(spec['name']+' · 前廊与退后门窗', parent)
    x0,y0,x1,y1 = q.bounds
    batches = {role:q.loc.batch() for role in
               ('plinth','paving','mortar','posts','facade','painted_beams','roof_frame','enclosure')}
    stone, timber, facade, trim, rafters, walls = (batches[k] for k in
                   ('plinth','posts','facade','painted_beams','roof_frame','enclosure'))
    deck = q.loc.local(site.geom(spec['deck']))
    stone.solid_xy(deck,.005,FLOOR-.13,p.brick,bottom=False)
    stone.solid_xy(deck,FLOOR-.13,FLOOR-PAVER_THICKNESS,p.marble,bottom=False)
    paving = pavement(batches['paving'],batches['mortar'],deck,p)
    for post_index,x in enumerate(q.xs):
        column(timber,x,q.front_y,FLOOR,POST_TOP,.172,p)
        # Facade posts carry the inner longitudinal wall plate. A plain rear
        # masonry eave encloses the frame instead of another exposed porch.
        column(timber,x,q.wall_y,FLOOR,q.roof_z(q.wall_y)-.43,.167,p)
        timber.box((x,(q.front_y+q.wall_y)/2,POST_TOP+.13),
                   (.20,q.wall_y-q.front_y+.15,.29),p.blue)
        for sign in (-1,1):
            if (post_index==0 and sign<0) or (post_index==BAY_COUNT and sign>0):
                continue
            queti(trim,x,q.front_y-.185,sign,POST_TOP-.17,p)
    for bay,(a,c) in enumerate(zip(q.xs,q.xs[1:])):
        mid, span = (a+c)/2,c-a
        timber.box((mid,q.front_y,POST_TOP+.04),(span+.04,.31,.42),p.blue)
        trim.box((mid,q.front_y-.162,POST_TOP+.04),(span-.17,.014,.27),p.teal)
        # Restrained blue field and fine geometric border, not an exact tracing.
        trim.box((mid,q.front_y-.171,POST_TOP+.04),(span*.57,.010,.19),p.blue)
        frame(trim,mid,q.front_y-.180,POST_TOP+.04,span*.61,.22,.012,p.giltpaint)
        for s in (-1,1):
            trim.path([(mid+s*span*.37-.14,q.front_y-.181,POST_TOP+.04),
                       (mid+s*span*.37,q.front_y-.181,POST_TOP+.155),
                       (mid+s*span*.37+.14,q.front_y-.181,POST_TOP+.04),
                       (mid+s*span*.37,q.front_y-.181,POST_TOP-.075),
                       (mid+s*span*.37-.14,q.front_y-.181,POST_TOP+.04)],
                      .009,p.giltpaint,sides=5)
        opening = span-.35
        window_bottom, leaf_h = FLOOR+.40, 4.20
        stone.box((mid,q.wall_y,FLOOR+.16),(opening,.29,.32),p.brick)
        timber.box((mid,q.wall_y,FLOOR+.37),(opening+.07,.32,.12),p.red)
        for j in range(4):
            xx = mid-opening/2+(j+.5)*opening/4
            closed_leaf(facade,xx,q.wall_y-.045,window_bottom,
                        opening/4-.022,leaf_h,p)
        top = window_bottom+leaf_h+.12
        timber.box((mid,q.wall_y,top),(opening+.08,.27,.24),p.red)
        # Upper transom has genuine grid holes; no opaque map block survives.
        transom_h = max(.12,q.roof_z(q.wall_y)-.54-(top+.12))
        frame(facade,mid,q.wall_y-.04,top+.12+transom_h/2,opening,transom_h,.055,p.red)
        diamond_lattice(facade,mid,q.wall_y-.078,top+.15,
                        opening-.13,max(.04,transom_h-.075),p)
    # Rear fire eave: continuous masonry reaches the underside. Conserved
    # mouldings and exact cross-section are not supplied by available drawings.
    back_top = q.roof_z(q.rear_y)-.20
    walls.box(((x0+x1)/2,q.rear_y,(FLOOR+back_top)/2),
              (x1-x0,.42,back_top-FLOOR),p.brick)
    for x in (x0+.14,x1-.14):
        end_infill(walls,x,q.wall_y,q.rear_y,.28,q,p)
    # Seven purlins and short supporting posts/ties follow the actual authored
    # roof profile. They are visible through the open porch and lattice holes.
    for i in range(7):
        yy = y0+.38+(q.depth-.76)*i/6
        zz = q.roof_z(yy)-.34
        rafters.rod((x0+.13,yy,zz),(x1-.13,yy,zz),.105,p.blue,sides=12)
        for x in q.xs:
            tie_z = POST_TOP+.13
            if zz-.105>tie_z:
                rafters.box((x,yy,(tie_z+zz-.105)/2),(.15,.17,zz-.105-tie_z),p.red)
            rafters.box((x,yy,zz-.135),(.20,.23,.063),p.teal)
    for x in q.xs:
        tie_front = y0+.22
        rafters.box((x,(tie_front+q.rear_y)/2,POST_TOP+.13),
                    (.18,q.rear_y-tie_front+.12,.29),p.blue)
    count = round(q.width/.32)
    for j in range(count+1):
        xx = x0+.05+(q.width-.10)*j/count
        for side in (-1,1):
            centre_y = q.centre[1]
            limit = y0+.03 if side<0 else q.rear_y-.04
            points = [(xx,limit+(centre_y-limit)*i/16,
                       q.roof_z(limit+(centre_y-limit)*i/16)-.25) for i in range(17)]
            for a,c in zip(points,points[1:]):
                rafters.beam(a,c,.067,.082,p.teal)
    roles = {'plinth':'青砖台明与石沿','paving':'逐块廊下铺砖','mortar':'分离凹缝灰浆',
             'posts':'前廊柱列与内檐柱','facade':'退后槅扇与实体斜格',
             'painted_beams':'梁枋彩画与雀替','roof_frame':'七檩椽架','enclosure':'空心房壳与后部风火檐'}
    for role,b in batches.items():
        b.finish(spec['name']+' · '+roles[role],group,
                 properties={'cross_axis_gallery':spec['key'],'cross_axis_gallery_role':role,
                             'source_osm_id':spec['body'],'fidelity_status':STATUS},
                 bevel=.001 if role in ('plinth','posts','facade') else 0)
    roof_palette = SimpleNamespace(**p.__dict__)
    roof_palette.door = p.roof_under
    roof = swept_roof(spec['name']+' · 连续黄琉璃瓦屋面',group,roof_palette,
                      origin=q.loc.world(*q.centre),yaw=q.loc.yaw,
                      width=q.width,depth=q.depth,eave=EAVE,rise=RIDGE_SHELL-EAVE,
                      kind='gable',tiles=True,pitch=.32,detail=2,soffit=False,
                      ridge_terminals=False,gable_ends=False)
    for obj in roof.all_objects:
        obj['cross_axis_gallery']=spec['key']
        obj['cross_axis_gallery_role']='roof'
        obj['fidelity_status']=STATUS
    for obj in group.all_objects:
        obj['gallery_group']=group.name
    return {**record(site,spec),'group':group.name,'paving':paving,
            'native_objects':len(group.all_objects),
            'front_porch_posts':BAY_COUNT+1,'facade_posts':BAY_COUNT+1,
            'closed_lattice_leaves':BAY_COUNT*4,
            'room_shell_furnishings':False,'short_gate_junction_modified':False}
