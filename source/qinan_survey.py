"""Qin'an sources and settings. All model dimensions are in metres."""
from dataclasses import dataclass
from itertools import accumulate
import math

from shapely import affinity

from osm_site import rectangle

QIN='40795244'
TIANYI='685600291'
DUIXIU='42424158'
YUJING='42424174'
QIN_RELATION='9514591'
COURT_WALLS=('685600255','685600256','685600257','685600258','685600259','685600260')
TERRACE_PARTS=('685600272','685600273','685600274','685600275','685600276')
COUPLED_CYPRESS_NODES=('529665395','529665396')

MUSEUM='https://www.dpm.org.cn/explore/building/'
QIN_SOURCE=MUSEUM+'236494.html'
GATE_SOURCE=MUSEUM+'236541.html'
ROCK_SOURCE=MUSEUM+'236429.html'
PAVILION_SOURCE=MUSEUM+'236490.html'
TIMBER_SOURCE='https://www.dpm.org.cn/Uploads/File/2018/06/04/u5b1521c1583e4.pdf'
INTERIOR_SOURCE='https://www.dpm.org.cn/Uploads/File/2020/02/18/u5e4bb67fc7439.pdf'
ROCK_ARTICLE='https://img.dpm.org.cn/Uploads/pdf/1603/T00091_00.pdf'
GARDEN_SOURCE='https://www.dpm.org.cn/Uploads/File/2024/07/22/u669dd30a7f61c.pdf'

# Tables 2, 3, 5 and 8, 故宫博物院院刊 2015.6, printed pp. 48–56.
LOW_FOOT_X=(4.030,4.150,4.710,4.150,4.030)
LOW_FOOT_Y=(1.650,7.340,1.650)
LOW_HEAD_X=(4.085,4.116,4.6755,4.122,4.085)
LOW_HEAD_Y=(1.680,7.255,1.680)
UP_HEAD_X=(2.382,4.114,4.625,4.1145,2.397)
UP_HEAD_Y=7.1905
EAVE_COLUMN=4.290
GOLD_COLUMN=7.485
LOW_PURLIN=(5.180,5.460)
UP_PURLIN=(8.555,8.834)
CEILING=8.271
TOP_BOARD=(10.346,10.596)
FLOWER_BEAM=(.920,.540)
PROJECTIONS=(.2145,.2251)
BRACKET_STEPS=(.1596,.1600,.1594)

FLOOR=1.56
DATUM=FLOOR+.172  # stone plinth top; local site elevation is photo-derived
ANNEX_EXTENT=(-8.36,-14.15,8.36,-6.12)  # rebuilt porch: photo-derived envelope
TOP_PLAN=(12.15,3.66)  # measured drawing proportion, not a tabulated dimension
SUMMIT_Z=9.95  # Official height: approximately ten metres to rock summit.


@dataclass(frozen=True)
class Location:
    x: float
    y: float
    yaw: float

    @classmethod
    def from_map(cls,site,ref):
        x,y,_,_,yaw=rectangle(site.geom(ref))
        return cls(x,y,(yaw+math.pi/2)%math.pi-math.pi/2)

    def world(self,x=0.,y=0.,z=0.):
        c,s=math.cos(self.yaw),math.sin(self.yaw)
        return self.x+c*x-s*y,self.y+s*x+c*y,z

    def local(self,shape):
        return affinity.rotate(affinity.translate(shape,-self.x,-self.y),-self.yaw,(0,0),use_radians=True)

    def batch(self):
        from mesh_tools import Batch
        return Batch(self.world(),self.yaw)


def centres(spans):
    return tuple(advance-sum(spans)/2 for advance in accumulate(spans,initial=0.))


def replacements(site):
    # The flat-roof part is mapped separately from the enclosing building relation.
    return {QIN,TIANYI,YUJING,'685600281',*TERRACE_PARTS,*COURT_WALLS,*site.members(QIN_RELATION)}


def source_report():
    return {
        'sources':{'building':QIN_SOURCE,'timber_survey':TIMBER_SOURCE,'furnishing_catalogue':INTERIOR_SOURCE},
        'adopted_state':'Main hall with the porch rebuilt during the 2004–2008 conservation work, §1 in the 2015 timber study.',
        'column_base_grid_2004_m':{'width_bays':LOW_FOOT_X,'depth_bays':LOW_FOOT_Y},
        'column_head_grid_2013_m':{'upper_width_bays':UP_HEAD_X,'upper_depth':UP_HEAD_Y,
                                  'lower_central_span':LOW_HEAD_X[2],'lower_middle_depth':LOW_HEAD_Y[1]},
        'column_head_grid_mixed_records_m':{'lower_x':LOW_HEAD_X,'lower_y':LOW_HEAD_Y,
            'note':'Lower outer flank and gallery spans use the earlier survey, the accessible main spans use 2013 results.'},
        'from_stone_column_base_top_m':{'eave_post_clear':EAVE_COLUMN,'gold_post_clear':GOLD_COLUMN,
            'lower_eave_purlin':LOW_PURLIN,'upper_eave_purlin':UP_PURLIN,'ceiling_underside':CEILING,
            'flat_roof_board':TOP_BOARD},
        'flower_beam_section_height_width_m':FLOWER_BEAM,'bracket_measured_mean_projections_m':PROJECTIONS,
        'bracket_measured_mean_step_heights_m':BRACKET_STEPS,
        'derived_or_inferred':{'site_floor_z_m':FLOOR,'column_base_top_z_m':DATUM,
            'flat_roof_plan_m_from_section_ratios':TOP_PLAN,
            'note':'Column diameters, surface wear, upper roof ornaments, front porch timber, decorations and current object states have photo or typology estimates.'},
    }
