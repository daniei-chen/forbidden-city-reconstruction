"""Original OSM geometry in a reproducible local, metre-based coordinate frame.

Contributed map data is a plan reference, not a certified measured survey.
"""
from pathlib import Path
import math
import xml.etree.ElementTree as ET

from pyproj import Transformer
from shapely.geometry import Polygon, LineString, GeometryCollection
from shapely.ops import unary_union, polygonize
from shapely import make_valid

SOURCE = Path(__file__).resolve().parent
E0, N0, ANGLE = 447935.0, 4418691.0, math.radians(1.8)
CA, SA = math.cos(ANGLE), math.sin(ANGLE)
TO_UTM = Transformer.from_crs(4326, 32650, always_xy=True)


def tags(element):
    return {t.get('k'): t.get('v') for t in element.findall('tag')}


def number(value, default=0.0):
    try:
        return float(str(value).split(';')[0].replace(' m', ''))
    except (TypeError, ValueError):
        return default


class Site:
    def __init__(self, source_file=None):
        self.source_file=Path(source_file) if source_file is not None else SOURCE/'palace_osm_full.xml'
        root = ET.parse(self.source_file).getroot()
        self.nodes = {}
        self.node_tags = {}
        for n in root.findall('node'):
            e, no = TO_UTM.transform(float(n.get('lon')), float(n.get('lat')))
            dx, dy = e-E0, no-N0
            self.nodes[n.get('id')] = (CA*dx+SA*dy, -SA*dx+CA*dy)
            if len(n):
                self.node_tags[n.get('id')] = tags(n)
        self.ways = {w.get('id'): w for w in root.findall('way')}
        self.rels = {r.get('id'): r for r in root.findall('relation')}
        self._geom = {}
        self.wall_ids = ['638176319', '638252480', '1341826249', '1341826250']
        self.walls = [self.points(i) for i in self.wall_ids]
        self.boundary = max(polygonize(unary_union([LineString(p) for p in self.walls])), key=lambda p:p.area)

    def points(self, way_id):
        return [self.nodes[n.get('ref')] for n in self.ways[str(way_id)].findall('nd') if n.get('ref') in self.nodes]

    def geom(self, ref, kind='way'):
        ref = str(ref)
        key = (kind, ref)
        if key in self._geom:
            return self._geom[key]
        if kind == 'way':
            pts = self.points(ref)
            g = make_valid(Polygon(pts)) if len(pts) >= 4 and pts[0] == pts[-1] else LineString(pts)
        else:
            r = self.rels[ref]
            outer, inner = [], []
            for m in r.findall('member'):
                typ, role = m.get('type'), m.get('role')
                if typ not in ('way', 'relation'):
                    continue
                if tags(r).get('type') == 'building' and role != 'outline':
                    continue
                g0 = self.geom(m.get('ref'), typ)
                (inner if role == 'inner' else outer).append(g0)
            def polygons_of(items):
                areas = [g for g in items if g.geom_type in ('Polygon', 'MultiPolygon')]
                lines = [g for g in items if g.geom_type in ('LineString', 'MultiLineString')]
                if lines:
                    areas.extend(polygonize(unary_union(lines)))
                return unary_union(areas) if areas else GeometryCollection()
            g = polygons_of(outer).difference(polygons_of(inner))
        self._geom[key] = g
        return g

    def members(self, relation, include_outline=True):
        """Recursively enumerate every member way, including multipolygon rings."""
        result = set()
        for m in self.rels[str(relation)].findall('member'):
            if not include_outline and m.get('role') == 'outline':
                continue
            if m.get('type') == 'way':
                result.add(m.get('ref'))
            elif m.get('type') == 'relation':
                result.update(self.members(m.get('ref')))
        return result

    def parts(self, relation):
        for m in self.rels[str(relation)].findall('member'):
            if m.get('role') != 'outline' and m.get('type') in ('way', 'relation'):
                element = (self.ways if m.get('type') == 'way' else self.rels)[m.get('ref')]
                yield m.get('ref'), tags(element), self.geom(m.get('ref'), m.get('type'))


def rectangle(shape):
    """Centre, long dimension, short dimension, and long-axis yaw."""
    pp = list(shape.minimum_rotated_rectangle.exterior.coords)[:4]
    edges = [(math.dist(pp[i], pp[(i+1)%4]), i) for i in range(4)]
    width, i = max(edges)
    depth = min(d for d, _ in edges)
    a, b = pp[i], pp[(i+1)%4]
    yaw = math.atan2(b[1]-a[1], b[0]-a[0])
    while yaw > math.pi/2: yaw -= math.pi
    while yaw <= -math.pi/2: yaw += math.pi
    c = shape.minimum_rotated_rectangle.centroid
    return c.x, c.y, width, depth, yaw


if __name__ == '__main__':
    site = Site()
    print('Site area m2:', round(site.boundary.area))
    for rid in ['8854043','8854044','8854352','8854507']:
        print('REL',rid)
        for ref,t,g in site.parts(rid):
            if t.get('building:material') == 'stone':
                print(ref,t,tuple(round(n,2) for n in g.bounds),round(g.area,1))
