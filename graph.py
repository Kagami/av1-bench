#!.venv/bin/python
# coding: utf-8

import os
import sys
import os.path as Path
import subprocess
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from vmaf.core.asset import Asset
from vmaf.core.quality_runner import VmafQualityRunner

REF_DIR = 'ref/still-32'
DIS_DIR = 'dis/still'
TIME_LOG_FNAME = 'time.csv'
GRAPH_FNAME = 'graph.png'

LIBAOM_TYPE = A = 'libaom'
SVTAV1_TYPE = S = 'SVT-AV1'
LIBJPEG_TYPE = J = 'libjpeg'

def get_ref_name(fname):
    bare1 = Path.splitext(fname)[0]
    bare2 = Path.splitext(bare1)[0]
    return bare2 + '.y4m'

def get_ref_path(rname):
    return Path.join(REF_DIR, rname)

def get_dis_path(fname):
    return Path.join(DIS_DIR, fname)

def get_graph_path():
    return Path.join(DIS_DIR, GRAPH_FNAME)

def get_asset_id(dname):
    return abs(hash(dname)) % (10 ** 16)

def get_time_info():
    fpath = Path.join(DIS_DIR, TIME_LOG_FNAME)
    df = pd.read_csv(fpath, sep='|')
    time_info = {}
    for row in df.itertuples():
        time_info[row.filename] = row.elapsed
    return time_info

def get_file_size(fpath):
    return Path.getsize(fpath)

def get_width_height(fpath):
    p = subprocess.Popen([
        'ffprobe', '-v', 'quiet', '-of', 'csv=p=0',
        '-show_entries', 'frame=width,height',
        '-i', fpath,
    ], stdout=subprocess.PIPE)
    out, err = p.communicate()
    w, h = out.split(',')
    return int(w), int(h)

def get_cached_width_height(ref_info, rname):
    try:
        return ref_info[rname]
    except KeyError:
        rpath = get_ref_path(rname)
        dims = get_width_height(rpath)
        ref_info[rname] = dims
        return dims

def get_assets():
    ref_info = {}
    assets = []
    dis_info = {}
    time_info = get_time_info()
    for dname in os.listdir(DIS_DIR):
        if dname.endswith('.aom.ivf'):
            dtype = LIBAOM_TYPE
        elif dname.endswith('.svt.ivf'):
            dtype = SVTAV1_TYPE
        elif dname.endswith('.jpg.jpg'):
            dtype = LIBJPEG_TYPE
        else:
            continue
        rname = get_ref_name(dname)
        rpath = get_ref_path(rname)
        dpath = get_dis_path(dname)
        qwidth, qheight = get_cached_width_height(ref_info, rname)
        asset_opts = {
            'ref_yuv_type': 'notyuv',
            'dis_yuv_type': 'notyuv',
            'quality_width': qwidth,
            'quality_height': qheight,
        }
        aid = get_asset_id(dname)
        asset = Asset(
            dataset="cmd",
            content_id=aid,  # XXX(Kagami): Should we use something else?
            asset_id=aid,
            ref_path=rpath,
            dis_path=dpath,
            asset_dict=asset_opts,
        )
        assets.append(asset)
        dis_info[aid] = {
            'type': dtype,
            'size': get_file_size(dpath),
            'encode_time': time_info.get(dname, 0)
        }
    return assets, dis_info

def get_label(typ, data, sec=0, kb=0):
    if kb:
        return '{} (mean: {:.2f}kb)'.format(typ, np.mean(data) / 1024)
    else:
        return '{} (mean: {:.2f}{})'.format(typ, np.mean(data), 's' if sec else '')

@FuncFormatter
def sec_formatter(x, pos):
    return '{}s'.format(int(x))

@FuncFormatter
def kb_formatter(x, pos):
    return '{}kb'.format(int(x / 1024))

def draw_graph(results, dis_info, title):
    ids = [res.asset.asset_id for res in results]
    libaom_ids = [aid for aid in ids if dis_info[aid]['type'] == LIBAOM_TYPE]
    svtav1_ids = [aid for aid in ids if dis_info[aid]['type'] == SVTAV1_TYPE]
    libjpeg_ids = [aid for aid in ids if dis_info[aid]['type'] == LIBJPEG_TYPE]

    libaom_scores = [res.result_dict['VMAF_scores'][0] for res in results if res.asset.asset_id in libaom_ids]
    svtav1_scores = [res.result_dict['VMAF_scores'][0] for res in results if res.asset.asset_id in svtav1_ids]
    libjpeg_scores = [res.result_dict['VMAF_scores'][0] for res in results if res.asset.asset_id in libjpeg_ids]

    libaom_times = [dis_info[aid]['encode_time'] for aid in libaom_ids]
    svtav1_times = [dis_info[aid]['encode_time'] for aid in svtav1_ids]
    libjpeg_times = [dis_info[aid]['encode_time'] for aid in libjpeg_ids]

    libaom_sizes = [dis_info[aid]['size'] for aid in libaom_ids]
    svtav1_sizes = [dis_info[aid]['size'] for aid in svtav1_ids]
    libjpeg_sizes = [dis_info[aid]['size'] for aid in libjpeg_ids]

    fig, (ax_score, ax_time, ax_size) = plt.subplots(3, 1, figsize=(10, 12))
    fig.suptitle(title, fontsize=16)

    ax_score.set_title(u'VMAF ↑')
    ax_score.xaxis.set_visible(False)
    ax_score.plot(libaom_scores, 'C3o', label=get_label(A, libaom_scores))
    ax_score.plot(svtav1_scores, 'C1o', label=get_label(S, svtav1_scores))
    ax_score.plot(libjpeg_scores, 'C0o', label=get_label(J, libjpeg_scores))
    ax_score.legend(loc='lower right')

    ax_time.set_title(u'Encode time ↓')
    ax_time.xaxis.set_visible(False)
    ax_time.yaxis.set_major_formatter(sec_formatter)
    ax_time.plot(libaom_times, 'C3o', label=get_label(A, libaom_times, sec=1))
    ax_time.plot(svtav1_times, 'C1o', label=get_label(S, svtav1_times, sec=1))
    ax_time.plot(libjpeg_times, 'C0o', label=get_label(J, libjpeg_times, sec=1))
    ax_time.legend(loc='lower right')

    ax_size.set_title(u'File size ≈')
    ax_size.xaxis.set_visible(False)
    ax_size.yaxis.set_major_formatter(kb_formatter)
    ax_size.plot(libaom_sizes, 'C3o', label=get_label(A, libaom_sizes, kb=1))
    ax_size.plot(svtav1_sizes, 'C1o', label=get_label(S, svtav1_sizes, kb=1))
    ax_size.plot(libjpeg_sizes, 'C0o', label=get_label(J, libjpeg_sizes, kb=1))
    ax_size.legend(loc='lower right')

    return fig

def main():
    title = sys.argv[1]
    assets, dis_info = get_assets()
    runner = VmafQualityRunner(assets, logger=None)
    runner.run()
    fig = draw_graph(runner.results, dis_info, title)
    gpath = get_graph_path()
    fig.savefig(gpath, bbox_inches='tight')
    print 'Saved graph to ' + gpath

if __name__ == '__main__':
    main()
