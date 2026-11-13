"""One input path/list → explicit source planes → physical slice/time organization."""
from pathlib import Path
from collections import defaultdict
import json
import re
from math import prod
import numpy as np
import nibabel as nib
from .common import Cancelled
from .images import Plane,Case,InputAmbiguity,CINE,stem,geometry,validate_image,validate_mask,mask_path

MAX_PLANES=5000
MAX_BYTES=700_000_000
LAYOUTS=('auto','position_order','file_slices','file_time')
TIME_ORDER=('temporal_index','trigger_ms','phase_percent','nifti_time_s','local_index')

def natural_key(value):
    return tuple((1,int(x)) if x.isdigit() else (0,x.casefold()) for x in re.split(r'(\d+)',str(value)))

def selection_paths(value):
    values=[value] if isinstance(value,(str,Path)) else list(value)
    return sorted({str(Path(p).expanduser().resolve()) for p in values if str(p).strip()},key=natural_key)

def is_nifti(path):return str(path).lower().endswith(('.nii','.nii.gz'))

def collect_files(selection,cancel):
    files=[]
    for selected in selection:
        path=Path(selected)
        if path.is_file():files.append(path)
        elif path.is_dir():
            for p in path.iterdir():
                if cancel():raise Cancelled('已取消加载')
                if not p.is_file() or p.name.upper().startswith('ROI-') or p.name.upper()=='DICOMDIR':continue
                if is_nifti(p) or p.suffix.lower() in ['.dcm','.ima']:files.append(p)
                elif not p.suffix:
                    from pydicom.misc import is_dicom
                    if is_dicom(p):files.append(p)
        else:raise FileNotFoundError(selected)
        if len(files)>MAX_PLANES:raise ValueError('请载入单病例序列，不超过5000个文件。')
    files=sorted(set(files),key=natural_key)
    if not files:raise ValueError('目录中未发现直接属于该病例的NIfTI/DICOM文件；不会递归合并不同患者。')
    if any(p.name.upper().startswith('ROI-') for p in files):raise ValueError('请选择原始影像；ROI掩膜请放在已有ROI目录。')
    if any(is_nifti(p) for p in files) and not all(is_nifti(p) for p in files):raise ValueError('请将DICOM和NIfTI作为独立输入组导入，避免重复合并。')
    return files

def json_object(path,limit=1_000_000):
    if not path.exists():return {}
    if path.stat().st_size>limit:raise ValueError('输入来源说明文件过大。')
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    return value if isinstance(value,dict) else {}

def filename_hints(path):
    name=stem(path);match=CINE.match(name)
    if match:return int(match[1]),int(match[2])
    z=re.search(r'(?:^|[_-])(?:slice|sl|z|s)[_-]?(\d+)(?=$|[_-])',name,re.I)
    t=re.search(r'(?:^|[_-])(?:frame|phase|time|t)[_-]?(\d+)(?=$|[_-])',name,re.I)
    return (int(z[1]) if z else None),(int(t[1]) if t else None)

def read_nifti(path,mask_folder=None,cancel=lambda:False,remaining=MAX_BYTES):
    path=Path(path);n=nib.load(str(path));aff,spacing,note=geometry(n);shape=n.shape
    if not 2<=len(shape)<=4:raise ValueError(f'仅支持2D/3D/4D NIfTI：{shape}')
    if np.issubdtype(n.get_data_dtype(),np.complexfloating) or n.get_data_dtype().fields is not None:raise ValueError('仅支持实值单通道NIfTI影像。')
    voxels=prod(shape);nz=shape[2] if len(shape)>2 else 1;nt=shape[3] if len(shape)>3 else 1
    if nz*nt>MAX_PLANES or voxels*4>remaining:raise ValueError('输入超过5000平面或700MB影像内存限制。')
    if nz>1 and np.linalg.norm(aff[:3,2])<1e-6:raise ValueError('多层NIfTI缺少有效层间距。')
    array=np.asarray(n.dataobj,dtype=np.float32).reshape(shape[:2]+(nz,nt))
    side=json_object(path.with_name(stem(path)+'.json'))
    s_hint,t_hint=filename_hints(path);mp=mask_path(mask_folder or path.parent,path.name);ma=None
    if mp:
        mn=nib.load(str(mp));maff,_,_=geometry(mn)
        if not np.allclose(maff,aff,rtol=0,atol=1e-4):raise ValueError('体积ROI与原图affine不匹配。')
        mshape=mn.shape+(1,)*(4-len(mn.shape))
        if mshape!=array.shape:raise ValueError('体积ROI与原图shape不匹配。')
        ma=np.asarray(mn.dataobj).reshape(mshape)
    units=n.header.get_xyzt_units()[1];factor={'sec':1.,'msec':.001,'usec':.000001}.get(units)
    if nt>1 and units in ['hz','ppm','rads']:raise ValueError('NIfTI第4维为频率维度，不能作为cine时相。')
    repetition=side.get('RepetitionTime')
    dt=float(repetition if repetition is not None else float(n.header.get_zooms()[3])*factor if len(shape)==4 and factor is not None else 0)
    offset=float(n.header['toffset'])*(factor or 1.)
    timing=side.get('VolumeTiming')
    if timing is not None:
        timing=np.asarray(timing,float)
        if timing.shape!=(nt,) or not np.isfinite(timing).all() or (nt>1 and np.any(np.diff(timing)<=0)):raise ValueError('NIfTI VolumeTiming无效。')
    planes=[]
    for z in range(nz):
        for t in range(nt):
            if cancel():raise Cancelled('已取消加载')
            a=np.ascontiguousarray(array[:,:,z,t]);validate_image(a);af=aff.copy();af[:3,3]=aff[:3,3]+aff[:3,2]*z
            candidates={'local_index':t+1}
            explicit=side.get('TemporalPositionIndex',side.get('TemporalPositionIdentifier',t_hint))
            if explicit is not None:candidates['temporal_index']=float(explicit)+t
            if timing is not None:candidates['nifti_time_s']=float(timing[t])
            elif dt>0 and np.isfinite(dt) and np.isfinite(offset):candidates['nifti_time_s']=offset+t*dt
            meta=dict(format='NIfTI',source_shape=list(shape),local_slice=z,local_frame=t,time_candidates=candidates,
                      slice_hint=s_hint if nz==1 else None,frame_hint=t_hint if nt==1 else None)
            p=Plane(s_hint if s_hint is not None and nz==1 else z+1,t_hint if t_hint is not None and nt==1 else t+1,
                    a,af,spacing,str(path),note,source_index=(z,t),input_metadata=meta)
            if ma is not None:p.masks['existing']=validate_mask(ma[:,:,z,t],a.shape)
            if mp and nz==nt==1:p.json_data=json_object(mp.with_name(stem(mp)+'.json')) or None
            planes.append(p)
    return planes

def clusters(values,tolerance):
    """Deterministic bins anchored at their smallest value; no chaining drift."""
    anchors=[];labels={}
    for index in sorted(range(len(values)),key=lambda i:values[i]):
        value=float(values[index])
        if not anchors or value-anchors[-1]>tolerance:anchors.append(value)
        labels[index]=len(anchors)
    return [labels[i] for i in range(len(values))],anchors

def spatial_keys(planes):
    first=planes[0];direction=first.affine[:3,2].copy()
    if np.linalg.norm(direction)<1e-8:direction=np.cross(first.affine[:3,0],first.affine[:3,1])
    direction/=np.linalg.norm(direction)
    axes=first.affine[:3,:2]/np.asarray(first.spacing)
    for p in planes:
        if p.image.shape!=first.image.shape or not np.allclose(p.spacing,first.spacing,rtol=1e-4,atol=1e-4) or not np.allclose(p.affine[:3,:2]/np.asarray(p.spacing),axes,atol=1e-4):
            raise ValueError('所选影像方向、尺寸或像素间距不一致，请分组导入。')
    keys,positions=clusters([np.dot(p.affine[:3,3],direction) for p in planes],.05)
    origins={}
    for p,key in zip(planes,keys):
        if key in origins and np.linalg.norm(p.affine[:3,3]-origins[key])>.2:raise ValueError('同层面图像存在平面内位置偏移；不会自动配准。')
        origins.setdefault(key,p.affine[:3,3])
    return keys,positions

def temporal_keys(planes):
    common=set.intersection(*(set(p.input_metadata.get('time_candidates',{})) for p in planes))
    for kind in TIME_ORDER:
        if kind in common:
            values=[p.input_metadata['time_candidates'][kind] for p in planes]
            if not np.isfinite(values).all():raise ValueError('影像时间标记含非有限值。')
            tolerance={'trigger_ms':.1,'phase_percent':.001,'nifti_time_s':.00001}.get(kind,0.)
            return (*clusters(values,tolerance),kind)
    return None,[],'unavailable'

def organize_planes(planes,mode='auto'):
    if not planes:raise ValueError('没有可读取的影像平面。')
    if mode not in LAYOUTS:raise ValueError('不支持的序列组织方式。')
    named=all(p.input_metadata.get('slice_hint') is not None and p.input_metadata.get('frame_hint') is not None for p in planes)
    times,time_values,time_kind=temporal_keys(planes)
    files=sorted({p.source for p in planes},key=natural_key);warnings=[];method='physical_position'
    # Preserve explicit study IDs, including non-contiguous slices and original
    # phase numbers, for exact replay of already-reviewed cases/projects.
    if mode=='auto' and named:
        groups=defaultdict(list)
        for p in planes:groups[p.input_metadata['slice_hint']].append(p)
        for group in groups.values():spatial_keys(group)
        first=planes[0]
        if any(p.image.shape!=first.image.shape or not np.allclose(p.affine[:3,:2],first.affine[:3,:2],atol=1e-4) for p in planes):
            warnings.append('已按明确文件层号保留不同几何层面，请核对短轴覆盖。')
    elif mode!='file_slices':
        try:spatial,positions=spatial_keys(planes)
        except ValueError as error:
            if mode=='auto' and len(files)>1:raise InputAmbiguity(str(error),options=('file_slices',)) from error
            raise
    if mode=='auto' and named:
        keys=[(p.input_metadata['slice_hint'],p.input_metadata['frame_hint']) for p in planes]
        if len(keys)!=len(set(keys)):raise InputAmbiguity('文件的层面/时相标记发生冲突，请确认组织方式。')
        named_origins={}
        for p,(z,t) in zip(planes,keys):
            if z in named_origins and np.linalg.norm(p.affine[:3,3]-named_origins[z])>.2:raise ValueError('文件层号与物理位置不一致，请核对输入。')
            named_origins.setdefault(z,p.affine[:3,3])
        method='explicit_filename_ids'
    elif mode=='auto':
        if times is None:
            if any(p.input_metadata.get('time_candidates') for p in planes):raise InputAmbiguity('影像时间标记不完整，请确认时相组织方式。')
            if len(spatial)!=len(set(spatial)):raise InputAmbiguity('重复层面缺少统一时间标记，请确认文件如何组成时相。')
            times=[1]*len(planes)
        keys=list(zip(spatial,times));method+=' + '+time_kind
        if len(keys)!=len(set(keys)):raise InputAmbiguity('多个文件占用相同层面和时相，需确认是时间块还是层面块。')
        if len(files)>1 and time_kind=='local_index':warnings.append('多个NIfTI按内部帧序对齐，请核对各文件的心动时相一致性。')
    elif mode=='position_order':
        grouped=defaultdict(list)
        for i,z in enumerate(spatial):grouped[z].append(i)
        keys=[None]*len(planes)
        for z,indices in grouped.items():
            indices.sort(key=lambda i:(planes[i].input_metadata.get('instance_number',0),natural_key(planes[i].source),planes[i].source_index))
            for t,i in enumerate(indices,1):keys[i]=(z,t)
        warnings.append('已按用户确认的同位置文件/帧序配对时相；该顺序不代表已验证的触发时间。');method='confirmed_position_order'
    else:
        keys=[None]*len(planes);offset=0
        for source in files:
            ids=[i for i,p in enumerate(planes) if p.source==source];group=[planes[i] for i in ids]
            local_z,_=spatial_keys(group);local_t,_,_=temporal_keys(group)
            if local_t is None or len(set(zip(local_z,local_t)))!=len(ids):
                counters=defaultdict(int);local_t=[]
                for z in local_z:counters[z]+=1;local_t.append(counters[z])
            for j,i in enumerate(ids):keys[i]=(local_z[j]+offset,local_t[j]) if mode=='file_slices' else (spatial[i],local_t[j]+offset)
            offset+=max(local_z) if mode=='file_slices' else max(local_t)
        warnings.append('已按用户确认的自然文件顺序续接层面；原始物理位置未修改。' if mode=='file_slices' else '已按用户确认的自然文件顺序续接时间块。')
        method='confirmed_'+mode
    if len(keys)!=len(set(keys)):raise ValueError('组织后的层面/时相键仍有重复，请检查输入。')
    for p,(z,t) in zip(planes,keys):p.slice=int(z);p.frame=int(t)
    nz=len({p.slice for p in planes});nt=len({p.frame for p in planes});missing=nz*nt-len(planes)
    if missing:warnings.append(f'序列存在{missing}个缺失层面/时相组合；未补帧或插值。')
    organization=dict(method=method,requested_mode=mode,files=files,file_count=len(files),planes=len(planes),slices=nz,frames=nt,
                      missing_combinations=missing,position_tolerance_mm=.05,time_kind=time_kind,time_values=time_values)
    return sorted(planes,key=lambda p:p.key),organization,warnings

def import_case(value,mask_folder=None,progress=None,cancel=lambda:False,organization='auto'):
    selection=selection_paths(value);files=collect_files(selection,cancel);planes=[]
    if all(is_nifti(p) for p in files):
        used=0
        for index,path in enumerate(files):
            if cancel():raise Cancelled('已取消加载')
            pp=read_nifti(path,mask_folder,cancel,MAX_BYTES-used);used+=sum(p.image.nbytes for p in pp);planes.extend(pp)
            if len(planes)>MAX_PLANES:raise ValueError('当前交互版限制为单序列不超过5000个平面。')
            if progress:progress(index+1,len(files),'载入影像')
        family='NIfTI'
    else:
        from .dicom_reader import read_dicoms
        planes=read_dicoms(files,cancel=cancel,progress=progress);family='DICOM'
    planes,layout,warnings=organize_planes(planes,organization)
    notes=sorted({p.unit_note for p in planes})
    for parent in sorted({p.parent for p in files},key=natural_key):
        provenance=json_object(parent/'lvwt_source_notes.json',64000)
        if provenance.get('schema')=='lvwt.source-notes.v1':
            extra=provenance.get('input_notes',[])
            if not isinstance(extra,list) or not all(isinstance(x,str) for x in extra):raise ValueError('输入来源说明格式无效。')
            notes.extend(extra)
    notes=list(dict.fromkeys(notes+warnings))
    duplicates=sum(len(p.input_metadata.get('duplicate_sources',[])) for p in planes)
    if duplicates:
        warning=f'已核对并去重{duplicates}个重复SOP平面。';warnings.append(warning);notes.append(warning)
    return Case(selection[0],planes,notes,metadata=dict(format=family,input_planes=len(planes),selection=selection,
                mask_folder=str(Path(mask_folder).resolve()) if mask_folder else None,organization=layout,input_warnings=warnings),source_paths=selection)
