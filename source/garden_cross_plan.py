"""Map anchors and source distinctions for Wanchun and Qianqiu Pavilions."""
from dataclasses import dataclass
import math

from shapely import affinity
from shapely.geometry import box
from shapely.ops import unary_union

from qinan_survey import Location

MUSEUM='https://www.dpm.org.cn/explore/building/236521.html'
PLAN_PAPER='https://img.dpm.org.cn/Uploads/File/2020/04/08/u5e8d77d699010.pdf'
PLAZA_FLOOR=.026
FLOOR=1.27


@dataclass(frozen=True)
class Twin:
    name: str
    way: str
    relation: str
    terrace: str
    timber: str
    inner_timber: str
    drum: str
    top: str
    cap_footprint: str
    stairs: tuple
    plaque: str
    photograph: str


TWINS=(
    Twin('万春亭','685673149','9515309','685673151','685673159','685673156','685673162','685673158',
         '685673152',('685673161','685673157','685673155','685673160'),
         's5e9d3c256d095.jpg','s5e9d3c109fb73.jpg'),
    Twin('千秋亭','685673150','9515310','685673170','685673169','685673167','685673168','685673176',
         '685673171',('685673166','685673164','685673163','685673165'),
         's5e9d3cbc112ed.jpg','s5e9d3ca8f21a5.jpg'),
)


def side_frame(side):
    return side*math.pi/2


def in_side(shape,side):
    return affinity.rotate(shape,-side_frame(side),origin=(0,0),use_radians=True)


def stepped_outline(a,b,within_x,within_y,arm_x,arm_y):
    return unary_union((box(-a,-b,a,b),box(-within_x,-arm_y,within_x,arm_y),
                        box(-arm_x,-within_y,arm_x,within_y)))


def map_plan(site,twin):
    outer=Location.from_map(site,twin.way)
    pose=Location(outer.x,outer.y,outer.yaw-math.pi/4)
    outline=pose.local(site.geom(twin.terrace))
    lower=pose.local(site.geom(twin.cap_footprint))
    drum=pose.local(site.geom(twin.drum))
    roof=pose.local(site.geom(twin.top))
    timber=pose.local(site.geom(twin.timber))
    square=pose.local(site.geom(twin.inner_timber))
    stairs=[in_side(pose.local(site.geom(ref)),i) for i,ref in enumerate(twin.stairs)]
    width=(lower.bounds[2]-lower.bounds[0])/2
    depth=(lower.bounds[3]-lower.bounds[1])/2
    return pose,outline,stairs,{
        'lower_corner_extents':(width,depth,3.38,3.25),
        'upper_eave_radius_m':math.sqrt(roof.area/math.pi),
        'drum_mapped_diameter_m':2*math.sqrt(drum.area/math.pi),
        'outer_timber_spans_m':(timber.bounds[2]-timber.bounds[0],timber.bounds[3]-timber.bounds[1]),
        'inner_timber_spans_m':(square.bounds[2]-square.bounds[0],square.bounds[3]-square.bounds[1]),
        'stone_platform_mapped_area_m2':outline.area,
        'stairs_mapped_areas_m2':[s.area for s in stairs],
    }
