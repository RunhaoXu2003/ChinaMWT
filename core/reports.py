from pathlib import Path
from dataclasses import asdict
from datetime import datetime
import csv
import html
import json
from .common import VERSION,write_json,sha256,Cancelled
from .images import save_plane,input_manifest
from .measurement import jade_json,read_rvip
from .i18n import Translator

def export_analysis(case,measurement,reference,demographics,run_dir,view=None,manual_rvip=None,cancel=lambda:False,language='en'):
    tr=Translator(language)
    run=Path(run_dir);folder={'post':'Postprocess','raw':'Prediction','existing':'ExistingROI'}[measurement.mask_mode]
    for name in ['images',folder]:(run/name).mkdir(parents=True,exist_ok=True)
    write_json(run/'images/lvwt_source_notes.json',dict(schema='lvwt.source-notes.v1',input_notes=case.notes))
    write_json(run/'input_manifest.json',input_manifest(case))
    source_hashes={}
    for plane in case.planes:
        if cancel():raise Cancelled('已取消导出；当前run保留已写入的文件。')
        ip=run/'images'/plane.name
        if not ip.exists():save_plane(plane,ip)
        mask=plane.masks.get(measurement.mask_mode)
        if mask is not None:
            mp=run/folder/('ROI-'+plane.name)
            if not mp.exists():save_plane(plane,mp,mask,mask=True)
            td=measurement.slices.get(plane.key)
            if td is None and measurement.mask_mode=='existing' and plane.json_data:
                try:
                    pair=read_rvip(plane.json_data,plane.image.shape)
                    if pair is not None:td={'rvip':pair}
                except (ValueError,TypeError):pass
            write_json(mp.with_name(mp.name[:-7]+'.json'),jade_json(plane,mask,td))
        if plane.source not in source_hashes:source_hashes[plane.source]=sha256(plane.source)
    if cancel():raise Cancelled('已取消导出。')
    summary={k:v for k,v in asdict(measurement).items() if k!='slices'}
    summary['rows']=measurement.rows
    write_json(run/'analysis.json',dict(application='LVWT CineSAX Workbench',version=VERSION,created=datetime.now().isoformat(),
       status='complete',measurement=summary,reference=reference,demographics=demographics,source_sha256=source_hashes,
       input_notes=case.notes,segmentation=case.metadata.get('segmentation'),report_language=language,input_organization=case.metadata.get('organization'),input_warnings=case.metadata.get('input_warnings',[]),
       scope='Maximum over the available valid ED slices using the recorded study algorithm; coverage and contours require review. Z is not HCM probability.'))
    with (run/'slice_measurements.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=['slice','frame','max_mm','study_max_mm','rvip_source','status']);w.writeheader();w.writerows(measurement.rows)
    project=dict(schema=1,input_path='images',mask_folder=folder,mask_mode='existing',demographics=demographics,
                 analysis_file='analysis.json',ed_override=measurement.ed_frame if any(f.startswith('人工指定ED') for f in measurement.flags) else None,view=view or {},input_notes=case.notes,
                 report_language=language,manual_rvip=[dict(slice=k[0],frame=k[1],points=v) for k,v in (manual_rvip or {}).items()])
    write_json(run/'project.lvwt.json',project)
    fields=[('Measured MWT',f'{measurement.mwt_mm:.2f} mm'),('ED frame',str(measurement.ed_frame)),('Measured ED slices',str(len(measurement.slices))),('AHA location',measurement.aha_location)]
    if reference:
        fields += [('Expected normal MWT',f"{reference['expected_mwt_mm']:.3f} mm"),('Upper reference limit',f"{reference['upper_limit_mm']:.3f} mm"),('Z score',f"{reference['z_score']:.4f}"),('BSA',f"{reference['bsa_m2']:.4f} m²"),('Above reference limit',tr('Yes' if reference['above_limit'] else 'No'))]
    lines=''.join('<tr><th>'+html.escape(tr(a))+'</th><td>'+html.escape(b)+'</td></tr>' for a,b in fields)
    flags=list(dict.fromkeys(measurement.flags+(reference.get('support_flags',[]) if reference else ['Demographics/reference output incomplete'])+[x for x in case.notes if 'unknown' in x.lower()]+case.metadata.get('input_warnings',[])))
    (run/'report.html').write_text('<!doctype html><html lang="'+('zh-CN' if language=='zh' else 'en')+'"><meta charset="utf-8"><title>'+tr('LVWT research result')+'</title><style>body{font:16px Arial,"Microsoft YaHei",sans-serif;max-width:1000px;margin:40px auto;color:#243247}table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #ddd;padding:12px;text-align:left}img{max-width:100%}</style><h1>LVWT CineSAX Workbench</h1><p>'+tr('Research result')+' · '+VERSION+'</p><table>'+lines+'</table><h2>'+tr('Review notes')+'</h2><ul>'+''.join('<li>'+html.escape(tr.message(x))+'</li>' for x in flags)+'</ul><p>'+tr('Reference limits support clinical assessment; they do not independently diagnose HCM.')+'</p><img src="review.png" alt="'+tr('Image/contour/thickness review')+'"></html>',encoding='utf-8')
    case.run_dir=str(run)
    return run/'project.lvwt.json'

def export_segmentation_only(case,reason,demographics,run_dir,mode='post',view=None,language='en'):
    """A valid segmentation remains available even when a slice has no usable MWT."""
    run=Path(run_dir);tr=Translator(language);folder='Postprocess' if mode=='post' else 'Prediction'
    write_json(run/'images/lvwt_source_notes.json',dict(schema='lvwt.source-notes.v1',input_notes=case.notes))
    write_json(run/'input_manifest.json',input_manifest(case))
    write_json(run/'analysis.json',dict(application='LVWT CineSAX Workbench',version=VERSION,status='segmentation_only',
        measurement=None,reference=None,reason=reason,demographics=demographics,input_notes=case.notes,
        input_organization=case.metadata.get('organization'),segmentation=case.metadata.get('segmentation'),report_language=language))
    write_json(run/'project.lvwt.json',dict(schema=1,input_path='images',mask_folder=folder,mask_mode='existing',demographics=demographics,
        analysis_file='analysis.json',view=view or {},input_notes=case.notes,report_language=language,manual_rvip=[]))
    (run/'report.html').write_text('<!doctype html><html lang="'+('zh-CN' if language=='zh' else 'en')+'"><meta charset="utf-8"><h1>LVWT CineSAX Workbench</h1><p>'+html.escape(tr.message('自动分割完成，厚度结果不可用：'+reason))+'</p><img style="max-width:100%" src="review.png"></html>',encoding='utf-8')
    case.run_dir=str(run)
    return run/'project.lvwt.json'

def read_project(path):
    p=Path(path).resolve();d=json.loads(p.read_text(encoding='utf-8'))
    if d.get('schema')!=1:raise ValueError('不支持的项目版本。')
    for field in ['input_path','mask_folder']:
        q=Path(d[field]);d[field]=str(q if q.is_absolute() else p.parent/q)
    d['project_path']=str(p)
    if d.get('analysis_file'):
        previous=json.loads((p.parent/d['analysis_file']).read_text(encoding='utf-8'))
        d['segmentation']=previous.get('segmentation')
        d['analysis_status']=previous.get('status','complete')
    return d
