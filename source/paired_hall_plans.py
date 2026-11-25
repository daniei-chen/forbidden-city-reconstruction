"""Separate the three mapped roof envelopes of the outer-court hall pairs."""

from dataclasses import dataclass
import math

from shapely import affinity
from shapely.geometry import box
from shapely.ops import unary_union


@dataclass(frozen=True)
class Pair:
    ref: str
    front: str
    rear: str
    gate: str
    museum_url: str
    floor: float
    front_eave: float
    front_rise: float
    rear_eave: float
    rear_rise: float
    marble_railing: bool


PAIRS = (
    Pair('43519304', '文华殿', '主敬殿', '40478705',
         'https://www.dpm.org.cn/explore/building/236531.html', 1.48, 7.05, 5.42, 6.70, 4.78, False),
    Pair('43512262', '武英殿', '敬思殿', '40542454',
         'https://www.dpm.org.cn/explore/building/236500.html', 1.60, 7.32, 5.54, 6.85, 4.90, True),
)


@dataclass(frozen=True)
class Envelope:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def centre(self):
        return ((self.x0+self.x1)*.5, (self.y0+self.y1)*.5)

    @property
    def width(self):
        return self.x1-self.x0

    @property
    def depth(self):
        return self.y1-self.y0

    @property
    def polygon(self):
        return box(self.x0, self.y0, self.x1, self.y1)


@dataclass(frozen=True)
class Plan:
    origin: tuple
    yaw: float
    front: Envelope
    rear: Envelope
    link: Envelope
    source_fit: float

    def world(self, x, y, z=0.):
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        return (self.origin[0]+x*c-y*s, self.origin[1]+x*s+y*c, z)


def split_plan(outline):
    """Fit two east-west eaves and one narrower, perpendicular roof.

    The shoulders are the four inside turns of the OSM outline. Differences
    between west and east ends are averaged so the tile rows stay square.
    """
    edges = list(zip(outline.exterior.coords, outline.exterior.coords[1:]))
    horizontal = [(a, b) for a, b in edges if abs(a[0]-b[0]) > 14 and abs(a[1]-b[1]) < 1]
    a, b = sorted(min(horizontal, key=lambda edge: (edge[0][1]+edge[1][1])/2))
    yaw = math.atan2(b[1]-a[1], b[0]-a[0])
    origin = tuple(outline.centroid.coords[0])
    local = affinity.rotate(affinity.translate(outline, -origin[0], -origin[1]),
                            -yaw, origin=(0, 0), use_radians=True)
    x0, y0, x1, y1 = local.bounds
    neck = [(x, y) for x, y in list(local.exterior.coords)[:-1]
            if x0+(x1-x0)*.21 < x < x1-(x1-x0)*.21 and y0+5 < y < y1-5]
    if len(neck) != 4:
        raise ValueError(f'Expected four inner shoulders, found {len(neck)}')
    neck.sort(key=lambda point: point[1])
    south, north = neck[:2], neck[2:]
    j0, j1 = [sum(v[1] for v in edge)/2 for edge in (south, north)]
    link_min = (min(v[0] for v in south) + min(v[0] for v in north))/2
    link_max = (max(v[0] for v in south) + max(v[0] for v in north))/2
    front = Envelope(*local.intersection(box(x0, y0, x1, j0)).bounds)
    rear = Envelope(*local.intersection(box(x0, j1, x1, y1)).bounds)
    link = Envelope(link_min, j0, link_max, j1)
    merged = unary_union([item.polygon for item in (front, rear, link)])
    fit = local.intersection(merged).area/local.union(merged).area
    if fit < .93:
        raise ValueError(f'Roof decomposition does not fit the mapped shape: {fit:.3f}')
    return Plan(origin, yaw, front, rear, link, fit)
