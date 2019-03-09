#!.venv/bin/python

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

REF_DIR = 'ref/still-16'
DIS_DIR = 'dis/still'
TIME_LOG_FNAME = 'time.csv'
GRAPH_FNAME = 'graph.png'

IM_TYPE = 'ImageMagick'
SVTAV1_TYPE = 'SVT-AV1'
LIBAOM_TYPE = 'libaom'

def get_ref_name(fname):
    return Path.splitext(fname)[0] + '.y4m'

def get_ref_path(fname):
    return Path.join(REF_DIR, get_ref_name(fname))

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
        if dname.endswith('.jpg'):
            dtype = IM_TYPE
        elif dname.endswith('.ivf'):
            dtype = SVTAV1_TYPE
        elif dname.endswith('.webm'):
            dtype = LIBAOM_TYPE
        else:
            continue
        rname = get_ref_name(dname)
        rpath = get_ref_path(dname)
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

def get_label(typ, data, kb=0):
    typ = IM_TYPE if typ == 'i' else SVTAV1_TYPE if typ == 's' else LIBAOM_TYPE
    if kb:
        return '{} (mean: {:.2f}kb)'.format(typ, np.mean(data) / 1024)
    else:
        return '{} (mean: {:.2f})'.format(typ, np.mean(data))

@FuncFormatter
def kb_formatter(n, pos):
    return '{}kb'.format(int(n / 1024))

def draw_graph(results, dis_info, title):
    ids = [res.asset.asset_id for res in results]
    im_ids = [aid for aid in ids if dis_info[aid]['type'] == IM_TYPE]
    svtav1_ids = [aid for aid in ids if dis_info[aid]['type'] == SVTAV1_TYPE]
    libaom_ids = [aid for aid in ids if dis_info[aid]['type'] == LIBAOM_TYPE]

    im_scores = [res.result_dict['VMAF_scores'][0] for res in results if res.asset.asset_id in im_ids]
    svtav1_scores = [res.result_dict['VMAF_scores'][0] for res in results if res.asset.asset_id in svtav1_ids]
    libaom_scores = [res.result_dict['VMAF_scores'][0] for res in results if res.asset.asset_id in libaom_ids]

    im_times = [dis_info[aid]['encode_time'] for aid in im_ids]
    svtav1_times = [dis_info[aid]['encode_time'] for aid in svtav1_ids]
    libaom_times = [dis_info[aid]['encode_time'] for aid in libaom_ids]

    im_sizes = [dis_info[aid]['size'] for aid in im_ids]
    svtav1_sizes = [dis_info[aid]['size'] for aid in svtav1_ids]
    libaom_sizes = [dis_info[aid]['size'] for aid in libaom_ids]

    fig, (ax_score, ax_time, ax_size) = plt.subplots(3, 1, figsize=(10, 12))
    fig.suptitle(title, fontsize=18)

    ax_score.set_title('VMAF')
    ax_score.xaxis.set_visible(False)
    ax_score.plot(im_scores, 'C0o', label=get_label('i', im_scores))
    ax_score.plot(svtav1_scores, 'C1o', label=get_label('s', svtav1_scores))
    ax_score.plot(libaom_scores, 'C3o', label=get_label('l', libaom_scores))
    ax_score.legend(loc='lower right')

    ax_time.set_title('Encoding time')
    ax_time.xaxis.set_visible(False)
    ax_time.plot(im_times, 'C0o', label=get_label('i', im_times))
    ax_time.plot(svtav1_times, 'C1o', label=get_label('s', svtav1_times))
    ax_time.plot(libaom_times, 'C3o', label=get_label('l', libaom_times))
    ax_time.legend(loc='lower right')

    ax_size.set_title('File size')
    ax_size.xaxis.set_visible(False)
    ax_size.yaxis.set_major_formatter(kb_formatter)
    ax_size.plot(im_sizes, 'C0o', label=get_label('i', im_sizes, 1))
    ax_size.plot(svtav1_sizes, 'C1o', label=get_label('s', svtav1_sizes, 1))
    ax_size.plot(libaom_sizes, 'C3o', label=get_label('l', libaom_sizes, 1))
    ax_size.legend(loc='lower right')

    return fig

def main():
    title = sys.argv[1] if len(sys.argv) > 1 else 'SVT-AV1 vs libaom'
    assets, dis_info = get_assets()
    runner = VmafQualityRunner(assets, logger=None)
    runner.run()
    fig = draw_graph(runner.results, dis_info, title)
    gpath = get_graph_path()
    fig.savefig(gpath, bbox_inches='tight')
    print 'Saved graph to ' + gpath

if __name__ == '__main__':
    main()
