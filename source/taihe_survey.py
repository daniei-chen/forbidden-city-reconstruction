"""Taihe post centres from published measurements, in metres.

Zhang Xueqin and Liu Chang, Palace Museum Journal 2007/4, pp. 034–035,
tables 2 and 3. These are the reported mean bay spans, not an invented
equally spaced 11-by-5 grid. The local model does not reproduce the small
per-row departures or the measured inclination of each individual post.
"""
from itertools import accumulate

X_BAYS = (3.5932, 5.5573, 5.5523, 5.5550, 5.5607, 8.4660,
          5.5462, 5.5572, 5.5470, 5.5607, 3.6020)
Y_BAYS = (3.6034, 7.4778, 11.1887, 7.4628, 3.6033)
OUTER_POST_HEIGHT = 7.380
INNER_POST_HEIGHT = 12.705
SOURCE_URL = 'https://www.dpm.org.cn/Uploads/pdf/5077/T00035_00.pdf'
SOURCE_TITLE = '张学芹、刘畅：《康熙三十四年建太和殿大木结构研究》，故宫博物院院刊2007年第4期，表二、表三'


def centres(spans):
    half = sum(spans) / 2
    return [value - half for value in accumulate((0., *spans))]


X_POSTS = centres(X_BAYS)
Y_POSTS = centres(Y_BAYS)
GILDED_POSTS = [(X_POSTS[i], Y_POSTS[j]) for i in (5, 6) for j in (2, 3, 4)]
