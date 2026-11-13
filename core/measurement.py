from dataclasses import dataclass,field
import numpy as np
from scipy import ndimage
from skimage import measure
from vendor import study_engine as study
from vendor.jade_coordinates import _convert_v1_coords_to_v2
from .common import Cancelled

@dataclass
class Measurement:
    ed_frame:int
    auto_ed_frame:int
    ordered_slices:list
    valid_ed_slices:list
    mwt_mm:float
    raw_max_mm:float
    max_key:tuple
    aha_location:str
    aha_values:dict
    mask_mode:str
    slices:dict=field(default_factory=dict)
    rows:list=field(default_factory=list)
    flags:list=field(default_factory=list)
    cavity_profile:dict=field(default_factory=dict)

def longest_run(values):
    best=[];run=[]
    for v in sorted(set(values)):
        if run and v!=run[-1]+1:
            if len(run)>len(best):best=run
            run=[]
        run.append(v)
    return run if len(run)>len(best) else best

def valid(mask):return mask is not None and np.any(mask==1) and np.any(mask==2)

def read_rvip(data,shape):
    if not data:return None
    points=data.get('insertion_points',{})
    pair=np.asarray([points.get('anterior'),points.get('posterior')],dtype=float)
    if pair.shape!=(2,2) or not np.isfinite(pair).all():return None
    major=int(str(data.get('version','1.5.0')).split('.')[0])
    if major<2:pair=np.array([_convert_v1_coords_to_v2(p,shape) for p in pair])
    elif data.get('image_orientation','original')!='original':raise ValueError('v2 JSON不是original坐标约定。')
    if np.any(pair<-.5) or np.any(pair[:,0]>shape[0]-.5) or np.any(pair[:,1]>shape[1]-.5):raise ValueError('JSON插入点超出原图，可能为转置坐标；请核对。')
    return pair

def detect_rvip(mask):
    rotated=np.rot90(mask,k=-1)
    a,p=study._jade_find_septum_endpoints(rotated)
    if a is None:
        a,p=study.find_rvip_pair(rotated)
        if a is not None:
            a,p=(a,p) if a[0]<=p[0] else (p,a)
    if a is None:return None
    return np.array([_convert_v1_coords_to_v2(np.asarray(v,float),mask.shape) for v in [a,p]])

def measure_case(case,mask_mode='existing',ed_override=None,excluded=None,manual_rvip=None,use_json=True,cancel=lambda:False,progress=None):
    excluded=set(excluded or []);manual_rvip=manual_rvip or {}
    usable=[p for p in case.planes if valid(p.masks.get(mask_mode)) and p.slice not in excluded]
    ordered=longest_run([p.slice for p in usable]);flags=[]
    if not ordered:raise ValueError('没有同时包含LV心肌和LV腔的有效ROI。')
    candidate=[p for p in case.planes if p.slice in ordered and p.masks.get(mask_mode) is not None]
    first=candidate[0];normal=first.affine[:3,2].copy()
    if np.linalg.norm(normal)==0:normal=np.cross(first.affine[:3,0],first.affine[:3,1])
    normal/=np.linalg.norm(normal)
    positions={s:float(np.dot(next(p.affine[:3,3] for p in candidate if p.slice==s),normal)) for s in ordered}
    if len(ordered)>1 and len({round(v,4) for v in positions.values()})<len(ordered):flags.append('部分层面物理位置重复，需核对覆盖和AHA位置。')
    ordered=sorted(ordered,key=positions.get)
    areas={s:np.mean([np.count_nonzero(p.masks[mask_mode]) for p in candidate if p.slice==s]) for s in ordered}
    cut=max(1,len(ordered)//3)
    if len(ordered)>=2 and np.mean([areas[s] for s in ordered[:cut]])<np.mean([areas[s] for s in ordered[-cut:]]):ordered.reverse()
    volumes={f:sum(int((p.masks[mask_mode]==2).sum()) for p in candidate if p.frame==f) for f in case.frames}
    auto=max(volumes,key=volumes.get);ed=int(ed_override) if ed_override is not None else auto
    if ed not in case.frames:raise ValueError('指定ED帧不在当前序列。')
    if len(case.frames)==1:flags.append('单时相输入：请确认该帧为舒张末期。')
    if ed_override is not None:flags.append(f'人工指定ED帧：{ed}')
    if excluded:flags.append('人工排除层面：'+','.join(map(str,sorted(excluded))))
    ed_valid=[s for s in ordered if any(p.key==(s,ed) for p in usable)]
    rvip={};sources={}
    for s in ordered:
        p=case.by_key((s,ed));pair=None
        if p is None or not valid(p.masks.get(mask_mode)):
            rvip[(s,ed)]=(None,None);continue
        if p.key in manual_rvip:
            pair=np.asarray(manual_rvip[p.key],float);sources[p.key]='manual points'
            if pair.shape!=(2,2) or not np.isfinite(pair).all() or np.any(pair<0) or np.any(pair[:,0]>=p.image.shape[0]) or np.any(pair[:,1]>=p.image.shape[1]):raise ValueError('手动RV插入点必须为图像内两个有效坐标。')
        elif use_json and mask_mode=='existing' and p.json_data:
            try:
                pair=read_rvip(p.json_data,p.image.shape)
                if pair is not None:sources[p.key]='JADE JSON v'+str(p.json_data.get('version','1.5.0'))
            except (ValueError,TypeError) as error:flags.append(f'层{s} JSON忽略：{error}')
        if pair is None:
            pair=detect_rvip(p.masks[mask_mode]);sources[p.key]='study mask detector'
        if pair is None:
            a,b=study.find_rvip_pair(p.masks[mask_mode]);a,b=study.assign_anterior_posterior(a,b)
            if a is not None:pair=np.asarray([a,b],float);sources[p.key]='study dilation fallback'
        rvip[p.key]=tuple(pair) if pair is not None else (None,None)
    before={k:(v[0] is not None) for k,v in rvip.items()}
    rvip=study.interpolate_rvip(rvip,ordered,ed)
    measured={};rows=[]
    for i,s in enumerate(ed_valid):
        if cancel():raise Cancelled('已取消厚度计算')
        p=case.by_key((s,ed));points=rvip.get(p.key,(None,None))
        reason=''
        try:
            if points[0] is None:raise ValueError('无RV插入点；可导入JSON或手动定位')
            lv=np.isin(p.masks[mask_mode],[1,2])
            if np.any(lv[0,:]) or np.any(lv[-1,:]) or np.any(lv[:,0]) or np.any(lv[:,-1]):flags.append(f'层{s}的LV标签接触图像边缘，请核对覆盖。')
            inner,outer,center=study.extract_smooth_contours(p.masks[mask_mode])
            if inner is None:raise ValueError('无法提取有效LV轮廓')
            td=study.compute_thickness_midline_normal(inner,outer,center,points[0],p.spacing,n_samples=72)
            if not np.isfinite(td['thicknesses']).all():raise ValueError('非有限厚度结果')
            td['rvip']=np.asarray(points);td['rvip_source']=sources.get(p.key,'interpolated') if before.get(p.key) else 'study spatial interpolation'
            measured[s]=td
            rows.append(dict(slice=s,frame=ed,max_mm=float(td['max_thickness']),study_max_mm=round(float(td['max_thickness']),2),rvip_source=td['rvip_source'],status='measured'))
        except (ValueError,TypeError,IndexError) as error:
            reason=str(error);rows.append(dict(slice=s,frame=ed,max_mm=None,study_max_mm=None,rvip_source='',status=reason));flags.append(f'层{s}未测量：{reason}')
        if progress:progress(i+1,len(ed_valid),'提取厚度')
    if not measured:raise ValueError('未获得可用厚度；请检查ROI、RV插入点及层面覆盖。')
    mwt,pos,aha=study.compute_aha16(measured,ed_valid,len(ed_valid)>=4)
    max_slice=max(measured,key=lambda s:measured[s]['max_thickness'])
    if len(ed_valid)<4:flags.append('有效ED层数少于4；AHA位置未分配，需核对短轴覆盖。')
    if any((s,ed) in manual_rvip for s in measured):flags.append('包含手动RV插入点。')
    if len(ordered)<len({p.slice for p in usable}):flags.append('按研究规则仅使用最长连续有效层段。')
    return Measurement(ed,auto,ordered,ed_valid,float(mwt),float(measured[max_slice]['max_thickness']),(max_slice,ed),str(pos),dict(aha),mask_mode,
                       { (s,ed):v for s,v in measured.items()},rows,flags,volumes)

def jade_json(plane,mask,td=None):
    contours={}
    for key,region in [('lv_endo',mask==2),('lv_epi',np.isin(mask,[1,2]))]:
        curves=measure.find_contours(region.astype(float),.5)
        if curves:
            curve=max(curves,key=len)
            # Control points are for JADE review, not the measurement boundaries.
            ids=np.linspace(0,len(curve)-1,min(48,len(curve)),endpoint=False).astype(int)
            contours[key]=dict(control_points=curve[ids].tolist(),closed=True,line_width=1.,control_point_size=2.,bound_endpoints={'start':None,'end':None})
    pair=td.get('rvip') if td else detect_rvip(mask)
    return dict(version='2.0.0',source_file=plane.name,mode='two_lines' if len(contours)==2 else 'none',image_orientation='original',
                image_shape=list(mask.shape),coordinate_order='row,column',contours=contours,
                insertion_points={} if pair is None else dict(anterior=np.asarray(pair[0]).tolist(),posterior=np.asarray(pair[1]).tolist()),
                measurement_note='Study MWT comes from ROI masks; exported control points are for JADE review. Export an updated ROI after contour editing.')
