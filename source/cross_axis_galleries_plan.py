"""Evidence-bounded plans for the four long Taihe forecourt side ranges.

The museum describes eleven bays on either side of both gates. Applying those
eleven bays to the four long mapped ranges is an explicit working interpretation:
the short gate-adjoining pieces are mapped under the gate relations and remain
outside this replacement. Neither their room-count membership nor a measured
bay grid has been established. No source below is a certified as-built survey.
"""
import math
from dataclasses import dataclass

from osm_site import rectangle
from qinan_survey import Location


RANGES = (
    dict(key='xihe_south', name='熙和门南庑长段', gate='熙和门', gate_body='638218837', turn=0,
         relation='8850524', body='638218812', deck='638218845',
         roofs=('638218802', '638218804', '638218805')),
    dict(key='xihe_north', name='熙和门北庑长段', gate='熙和门', gate_body='638218837', turn=0,
         relation='8850523', body='638218791', deck='638218840',
         roofs=('638218786', '638218784', '638218775')),
    dict(key='xiehe_north', name='协和门北庑长段', gate='协和门', gate_body='638238329', turn=1,
         relation='8850778', body='638238383', deck='638238323',
         roofs=('638238391', '638238333', '638238389')),
    dict(key='xiehe_south', name='协和门南庑长段', gate='协和门', gate_body='638238329', turn=1,
         relation='8850777', body='638238358', deck='638238324',
         roofs=('638238338', '638238330', '638238328')),
)

BAY_COUNT = 11
FLOOR = 1.0  # retained source-map deck height, not the gates' published 2.62 m
EAVE = 7.0  # retained source-map lean-to roof outer-edge height
RIDGE_SHELL = 10.455  # gives 11.0 m at the modeled ridge cap upper surface
POST_TOP = 6.12
PAVER_THICKNESS = .058
PAVER_RECESS = .003
STATUS = (
    'Museum: eleven bays per side, yellow glazed roof, front porch, rear fire-protected eave. '
    'Eleven bays assigned to each long mapped range provisionally; short gate-adjoining '
    'pieces are excluded and their count membership is unresolved. Footprints and 1 m '
    'deck / 7 m eave / 11 m ridge are inherited map estimates. Exact spans, porch setback, '
    'member sections, fire-eave detail, joinery, finishes and individual window pattern '
    'are interpretations. Hollow room shells are unfurnished, not surveyed interiors.'
)


@dataclass(frozen=True)
class Plan:
    loc: Location
    bounds: tuple
    xs: tuple
    front_y: float
    wall_y: float
    rear_y: float

    @property
    def centre(self):
        x0, y0, x1, y1 = self.bounds
        return (x0+x1)/2, (y0+y1)/2

    @property
    def width(self):
        return self.bounds[2]-self.bounds[0]

    @property
    def depth(self):
        return self.bounds[3]-self.bounds[1]

    @property
    def porch_path_y(self):
        return (self.front_y+self.wall_y)/2

    def roof_z(self, y):
        t = max(0., min(1., 1-abs(y-self.centre[1])/(self.depth/2)))
        return EAVE+(RIDGE_SHELL-EAVE)*(.10*t+.90*t**1.71)+.07*(1-t)**14


def plan(site, spec):
    gx, gy, _, _, yaw = rectangle(site.geom(spec['gate_body']))
    loc = Location(gx, gy, yaw-spec['turn']*math.pi)
    bounds = tuple(loc.local(site.geom(spec['body'])).bounds)
    x0, y0, x1, y1 = bounds
    xs = tuple(x0+.34+(x1-x0-.68)*i/BAY_COUNT for i in range(BAY_COUNT+1))
    front = y0+.56
    wall = front+2.20
    rear = y1-.30
    return Plan(loc, bounds, xs, front, wall, rear)


def replacement_names():
    return sorted([f'构件 · OSM {ref}' for s in RANGES for ref in (s['body'], s['deck'], *s['roofs'])]
                  + [f'宫院屋面 · 三维瓦作 {ref}' for s in RANGES for ref in s['roofs']])


def record(site, spec):
    p = plan(site, spec)
    return {**spec, 'local_bounds_m': p.bounds,
            'location_m_and_radians': [p.loc.x, p.loc.y, p.loc.yaw],
            'bay_count_working_interpretation': BAY_COUNT,
            'column_grid_x_m': p.xs,
            'front_post_y_m': p.front_y, 'setback_facade_y_m': p.wall_y,
            'rear_fire_wall_y_m': p.rear_y, 'clear_porch_setback_m': p.wall_y-p.front_y,
            'map_estimated_floor_m': FLOOR,
            'map_estimated_outer_eave_m': EAVE,
            'authored_ridge_shell_m': RIDGE_SHELL,
            'inferred_post_top_m': POST_TOP, 'status': STATUS}
