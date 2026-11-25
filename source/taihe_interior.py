"""Hollow ceiling and recessed caisson; photograph-led ornament, not scan data."""
import math
import os
from pathlib import Path
import bpy
from shapely.geometry import box, Polygon
from mesh_tools import Batch, object_to_mesh
from carved_ornament import dragon, cloud
from museum_surface import photo_material, crop_uv, relief_panel


def add_ceiling(b,p,xs,ys,floor,*,caisson_y=5.60):
    """The caisson has a genuine opening, with relief facing down into the hall."""
    z=floor+12.45
    xmin,xmax=xs[1]-.32,xs[-2]+.32
    ymin,ymax=ys[1]-.28,ys[-2]+.28
    aperture=box(-3.45,caisson_y-3.45,3.45,caisson_y+3.45)
    b.solid_xy(box(xmin,ymin,xmax,ymax).difference(aperture),z+.05,z+.19,p.blue)
    painted=photo_material('天花盘龙彩画','palace_museum_taihe_throne_reference.jpg',metal=.04,rough=.82)
    coffer_uv=crop_uv(.295,.145,.373,.245)
    nx=math.ceil((xmax-xmin)/1.05);ny=math.ceil((ymax-ymin)/1.05)
    wx=(xmax-xmin)/nx;dy=(ymax-ymin)/ny
    for row in range(ny):
        cy=ymin+(row+.5)*dy
        for col in range(nx):
            cx=xmin+(col+.5)*wx
            tile=box(cx-wx/2,cy-dy/2,cx+wx/2,cy+dy/2)
            if tile.intersects(aperture):
                continue
            b.box((cx,cy,z+.01),(wx-.05,dy-.05,.08),p.teal if (row+col)%3 else p.blue)
            b.face([(cx-wx/2+.04,cy-dy/2+.04,z-.035),
                    (cx+wx/2-.04,cy-dy/2+.04,z-.035),
                    (cx+wx/2-.04,cy+dy/2-.04,z-.035),
                    (cx-wx/2+.04,cy+dy/2-.04,z-.035)],painted,uv=coffer_uv)
            for sx in (-1,1):
                b.box((cx+sx*(wx/2-.065),cy,z-.055),(.032,dy-.11,.038),p.giltpaint)
            for sy in (-1,1):
                b.box((cx,cy+sy*(dy/2-.065),z-.055),(wx-.11,.032,.038),p.giltpaint)
            radius=min(wx,dy)*.25
            pts=[]
            for k in range(33):
                a=k/32*math.tau;r=radius*(.91+.08*math.cos(8*a))
                pts.append((cx+r*math.cos(a),cy+r*math.sin(a),z-.055))
            b.path(pts,.009,p.giltpaint,sides=5)
    for x in xs[1:-1]:
        b.solid_xy(box(x-.14,ymin,x+.14,ymax).difference(aperture),z-.42,z+.10,p.red)
        b.solid_xy(box(x-.09,ymin,x+.09,ymax).difference(aperture),z-.445,z-.415,p.giltpaint)
    for y in ys[1:-1]:
        b.solid_xy(box(xmin,y-.17,xmax,y+.17).difference(aperture),z-.46,z+.10,p.blue)
        b.solid_xy(box(xmin,y-.11,xmax,y+.11).difference(aperture),z-.49,z-.46,p.giltpaint)
    # Open ledges replace the earlier full panels that hid all higher tiers.
    caisson_paint=photo_material('藻井彩绘与浮雕肌理','palace_museum_taihe_caisson_square_reference.jpg',metal=.11,rough=.76)
    caisson_start=len(b.f)
    for tier,(outer,inner,height) in enumerate(((7.08,5.86,.46),(5.86,4.66,.48),(4.66,3.34,.48),(3.34,2.20,.43))):
        low=z+tier*.47
        def ring_shape(size):
            if tier<2:
                return box(-size/2,caisson_y-size/2,size/2,caisson_y+size/2)
            return Polygon([(size/2*math.cos(a),caisson_y+size/2*math.sin(a))
                            for a in [math.pi/8+k*math.tau/8 for k in range(8)]])
        outside=box(-outer/2,caisson_y-outer/2,outer/2,caisson_y+outer/2) if tier==2 else ring_shape(outer)
        inside=ring_shape(inner)
        b.solid_xy(outside.difference(inside),low,low+height,caisson_paint)
        for side in (-1,1):
            b.box((side*(outer/2-.06),caisson_y,low-.035),(.075,outer,.07),p.gold)
            b.box((0,caisson_y+side*(outer/2-.06),low-.035),(outer,.075,.07),p.gold)
        n=max(4,round(outer/.32))
        for side in range(4):
            a=side*math.pi/2
            for i in range(n):
                u=(i+.5)/n*outer-outer/2
                xx=u*math.cos(a)-(outer/2-.17)*math.sin(a)
                yy=caisson_y+u*math.sin(a)+(outer/2-.17)*math.cos(a)
                b.box((xx,yy,low-.09),(.19,.19,.16),p.gold,yaw=a)
                b.box((xx,yy,low-.17),(.12,.12,.10),p.teal,yaw=a)
        # Modest raised scrolls retain depth without hiding the photographed
        # original polychromy and the much denser underlying relief pattern.
    top=z+2.03
    b.box((0,caisson_y,top+.06),(2.27,2.27,.12),p.teal)
    ring_end=len(b.f)
    for index in range(caisson_start,ring_end):
        if b.mats[b.mi[index]]==caisson_paint:
            coordinates=[]
            for vi in b.f[index]:
                u=.5+b.v[vi][0]/7.08;v=.5+(b.v[vi][1]-caisson_y)/7.08
                coordinates.append((u,v))
            b.uv[index]=tuple(coordinates)
            z_values=[b.v[vi][2] for vi in b.f[index]]
            # The archived photograph contains hanging glass balls. Keep its
            # inner image area on the final carved medallion only, so it cannot
            # paint duplicate glass balls onto the upper ledges.
            if max(z_values)-min(z_values)>.10 or min(z_values)>z+.90:
                if p.giltpaint not in b.slots:
                    b.slots[p.giltpaint]=len(b.mats);b.mats.append(p.giltpaint)
                b.mi[index]=b.slots[p.giltpaint]
    relief_panel(b,(0,caisson_y,top-.003),2.25,2.25,caisson_paint,
                 crop_uv(.25,.225,.75,.495),facing='down',nx=192,ny=192,depth=.10)
    for r in (1.02,1.10):
        b.path([(r*math.cos(k*math.tau/96),caisson_y+r*math.sin(k*math.tau/96),top-.075)
                for k in range(97)],.028,p.gold,sides=7)
    silver=bpy.data.materials.get('轩辕镜 · 银色玻璃珠与铜胎')
    if silver is None:
        silver=bpy.data.materials.new('轩辕镜 · 银色玻璃珠与铜胎');silver.use_nodes=True
        silver.diffuse_color=(.52,.56,.51,1)
        bs=silver.node_tree.nodes.get('Principled BSDF')
        bs.inputs['Base Color'].default_value=(.52,.56,.51,1)
        bs.inputs['Metallic'].default_value=.83;bs.inputs['Roughness'].default_value=.25
    mirror_z=z-.10
    b.rod((0,caisson_y,top-.12),(0,caisson_y,mirror_z+.44),.034,p.gold,sides=12)
    b.ellipsoid((0,caisson_y,mirror_z),(.43,.43,.39),silver,sides=40,rings=24)
    for k in range(8):
        a=k*math.tau/8;cx=.69*math.cos(a);cy=caisson_y+.69*math.sin(a)
        b.rod((cx,cy,z+.52),(cx,cy,z+.15),.019,p.gold,sides=8)
        b.ellipsoid((cx,cy,z+.07),(.13,.13,.17),silver,sides=20,rings=12)
    # The upper wall behind the throne carries a dense painted beam register.
    # This avoids the featureless maroon strip of the earlier reconstruction.
    frieze=photo_material('内檐梁枋彩画','palace_museum_taihe_throne_reference.jpg',metal=.04,rough=.82)
    back_y=ys[-2]-.30
    for i in range(1,len(xs)-2):
        left,right=xs[i],xs[i+1]
        for zlow,zhigh in ((floor+6.55,floor+7.85),(floor+8.1,floor+9.6),(floor+9.85,floor+11.70)):
            b.face([(left,back_y,zlow),(right,back_y,zlow),
                    (right,back_y,zhigh),(left,back_y,zhigh)],
                   frieze,uv=crop_uv(.275,.070,.710,.205))
            for zz in (zlow,zhigh):
                b.box(((left+right)/2,back_y-.04,zz),(right-left,.075,.055),p.giltpaint)
    return z


def add_imperial_plaque(target,p,origin,yaw):
    b=Batch(origin,yaw)
    y=-5.50;z=18.45;w=4.55;h=1.55
    b.box((0,y,z),(w,.15,h),p.gold)
    for sign in (-1,1):
        b.box((sign*(w/2+.035),y-.10,z),(.13,.12,h+.22),p.door)
        b.box((0,y-.10,z+sign*(h/2+.035)),(w+.22,.12,.13),p.door)
    b.finish('太和殿 · 建極綏猷匾额立体框',target)
    default_font=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/simkai.ttf'
    font_path=Path(os.environ.get('PALACE_CJK_FONT') or default_font)
    if not font_path.is_file():
        return
    font=bpy.data.fonts.load(str(font_path),check_existing=True)
    for index,char in enumerate('建極綏猷'):
        curve=bpy.data.curves.new('内廷匾字 '+char,'FONT')
        curve.body=char;curve.font=font;curve.size=1.18
        curve.align_x='CENTER';curve.align_y='CENTER';curve.extrude=.004
        obj=bpy.data.objects.new('建極綏猷 · '+char,curve);target.objects.link(obj)
        x=(index-1.5)*1.05
        # Right-to-left inscription in the reference photograph.
        x=-x
        obj.location=(origin[0]+x*math.cos(yaw)-(y-.092)*math.sin(yaw),
                      origin[1]+x*math.sin(yaw)+(y-.092)*math.cos(yaw),z)
        obj.rotation_euler=(math.pi/2,0,yaw);curve.materials.append(p.door)
        bpy.context.view_layer.update();object_to_mesh(obj)
