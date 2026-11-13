"""Classic and enhanced MR DICOM decoding with per-frame physical metadata."""
from pathlib import Path
import numpy as np
import pydicom
from pydicom.pixels import iter_pixels
from pydicom.tag import Tag
from .images import Plane,validate_image
from .common import Cancelled

MAX_PLANES=5000
MAX_BYTES=700_000_000

def item(dataset,sequence):
    values=getattr(dataset,sequence,[]) if dataset is not None else []
    return values[0] if values else None

def attribute(frame,shared,dataset,sequence,key,default=None):
    for group in [item(frame,sequence),item(shared,sequence),dataset]:
        if group is not None and hasattr(group,key):return getattr(group,key)
    return default

def finite(value,name):
    result=float(value)
    if not np.isfinite(result):raise ValueError('无效DICOM数值：'+name)
    return result

def header(path):
    try:d=pydicom.dcmread(path,stop_before_pixels=True)
    except pydicom.errors.InvalidDicomError:d=pydicom.dcmread(path,stop_before_pixels=True,force=True)
    if not all(hasattr(d,k) for k in ['Rows','Columns']):raise ValueError('文件不是可读取的DICOM影像：'+Path(path).name)
    if int(getattr(d,'SamplesPerPixel',1))!=1:raise ValueError('仅支持单通道灰度DICOM影像。')
    if str(getattr(d,'Modality','MR'))!='MR':raise ValueError('请选择MR短轴影像，而不是其他DICOM模态。')
    if 'ModalityLUTSequence' in d:raise ValueError('当前输入包含非线性Modality LUT，请先转换为定量NIfTI。')
    return d

def frame_metadata(d,index):
    n=int(getattr(d,'NumberOfFrames',1));per=getattr(d,'PerFrameFunctionalGroupsSequence',[])
    if per and len(per)!=n:raise ValueError('DICOM逐帧元数据数量与NumberOfFrames不一致。')
    fg=per[index] if per else None;shared=item(d,'SharedFunctionalGroupsSequence')
    iop=attribute(fg,shared,d,'PlaneOrientationSequence','ImageOrientationPatient')
    ipp=attribute(fg,shared,d,'PlanePositionSequence','ImagePositionPatient')
    spacing=attribute(fg,shared,d,'PixelMeasuresSequence','PixelSpacing')
    if iop is None or ipp is None or spacing is None:raise ValueError('DICOM缺少方向/位置/PixelSpacing，不能可靠计算毫米厚度。')
    direction=np.asarray(iop,float);position=np.asarray(ipp,float);sp=np.asarray(spacing,float)
    if direction.shape!=(6,) or position.shape!=(3,) or sp.shape!=(2,) or not all(np.isfinite(x).all() for x in [direction,position,sp]) or np.any(sp<=0):raise ValueError('DICOM方向/位置/像素间距无效。')
    if not np.allclose([np.linalg.norm(direction[:3]),np.linalg.norm(direction[3:])],1.,atol=1e-4) or abs(np.dot(direction[:3],direction[3:]))>1e-4:raise ValueError('DICOM方向余弦必须为正交单位向量。')
    thickness=finite(attribute(fg,shared,d,'PixelMeasuresSequence','SliceThickness',1),'SliceThickness')
    if thickness<=0:raise ValueError('DICOM SliceThickness无效。')
    ras=np.diag([-1.,-1.,1.]);normal=np.cross(direction[:3],direction[3:]);affine=np.eye(4)
    affine[:3,0]=ras@direction[3:]*sp[0];affine[:3,1]=ras@direction[:3]*sp[1]
    affine[:3,2]=ras@normal*thickness;affine[:3,3]=ras@position
    candidates={};content=item(fg,'FrameContentSequence')
    temporal=getattr(content,'TemporalPositionIndex',None) if content is not None else None
    if temporal is None and content is not None and hasattr(content,'DimensionIndexValues'):
        pointers=getattr(d,'DimensionIndexSequence',[]);values=content.DimensionIndexValues
        values=list(values) if hasattr(values,'__iter__') else [values]
        if len(values)!=len(pointers):raise ValueError('DICOM DimensionIndexValues与维度定义不一致。')
        for definition,value in zip(pointers,values):
            if Tag(definition.DimensionIndexPointer)==Tag(0x0020,0x9128):temporal=value
    if temporal is None:temporal=getattr(d,'TemporalPositionIdentifier',None)
    if temporal is not None:candidates['temporal_index']=finite(temporal,'TemporalPositionIndex')
    trigger=attribute(fg,shared,d,'CardiacSynchronizationSequence','NominalCardiacTriggerDelayTime',getattr(d,'TriggerTime',None))
    if trigger is not None:candidates['trigger_ms']=finite(trigger,'TriggerTime')
    phase=attribute(fg,shared,d,'CardiacSynchronizationSequence','NominalPercentageOfCardiacPhase')
    if phase is not None:candidates['phase_percent']=finite(phase,'CardiacPhase')
    # Legacy same-plane cine: explicit FrameTime/FrameTimeVector, not a guessed
    # flattening of unknown multi-layer frames. Enhanced time keys take priority.
    if n>1 and not per:
        if hasattr(d,'FrameTimeVector'):
            vector=np.asarray(d.FrameTimeVector,float)
            if len(vector)!=n or not np.isfinite(vector).all() or np.any(vector<0):raise ValueError('DICOM FrameTimeVector无效。')
            candidates['trigger_ms']=finite(getattr(d,'TriggerTime',0),'TriggerTime')+float(np.cumsum(vector)[index])
        elif hasattr(d,'FrameTime'):
            interval=finite(d.FrameTime,'FrameTime')
            if interval<=0:raise ValueError('DICOM FrameTime无效。')
            candidates['trigger_ms']=float(getattr(d,'TriggerTime',0))+index*interval
        elif int(getattr(d,'NumberOfTemporalPositions',0))==n:
            candidates['temporal_index']=index+1
        # A constant top-level temporal identifier does not index multiple frames.
        if 'TemporalPositionIdentifier' in d and len(candidates)==1 and 'temporal_index' in candidates:candidates={}
        elif 'trigger_ms' in candidates and 'TemporalPositionIdentifier' in d:candidates.pop('temporal_index',None)
    slope=finite(attribute(fg,shared,d,'PixelValueTransformationSequence','RescaleSlope',1),'RescaleSlope')
    intercept=finite(attribute(fg,shared,d,'PixelValueTransformationSequence','RescaleIntercept',0),'RescaleIntercept')
    if slope==0:raise ValueError('DICOM RescaleSlope不能为0。')
    meta=dict(format='DICOM',source_frame=index,source_frames=n,time_candidates=candidates,
        sop_instance_uid=str(getattr(d,'SOPInstanceUID','')),series_instance_uid=str(getattr(d,'SeriesInstanceUID','')),
        instance_number=int(getattr(d,'InstanceNumber',0)),rescale_slope=slope,rescale_intercept=intercept,
        enhanced=bool(per),photometric=str(getattr(d,'PhotometricInterpretation','MONOCHROME2')))
    echo=attribute(fg,shared,d,'MREchoSequence','EffectiveEchoTime',getattr(d,'EchoTime',None))
    if echo is not None:meta['echo_time_ms']=finite(echo,'EchoTime')
    component=attribute(fg,shared,d,'MRImageFrameTypeSequence','ComplexImageComponent')
    if component is not None:meta['complex_component']=str(component)
    return affine,tuple(map(float,sp)),meta

def read_dicoms(paths,series_uid=None,cancel=lambda:False,progress=None):
    entries=[];budget=0;count=0
    for path in paths:
        if cancel():raise Cancelled('已取消DICOM加载')
        d=header(path)
        if series_uid is not None and str(getattr(d,'SeriesInstanceUID',''))!=series_uid:continue
        n=int(getattr(d,'NumberOfFrames',1))
        if n<1:raise ValueError('DICOM NumberOfFrames无效。')
        count+=n;budget+=n*int(d.Rows)*int(d.Columns)*4
        if count>MAX_PLANES or budget>MAX_BYTES:raise ValueError('输入超过5000平面或700MB影像内存限制。')
        entries.append((Path(path),d,n))
    if not entries:raise ValueError('没有匹配的DICOM切片。')
    for key in ['PatientID','StudyInstanceUID','FrameOfReferenceUID']:
        known={str(getattr(d,key,'')) for _,d,_ in entries if str(getattr(d,key,''))}
        if len(known)>1:raise ValueError('所选DICOM来自不同受试者、检查或空间参考系，请分批导入。')
    for key in ['EchoNumbers','EchoTime','ComplexImageComponent']:
        known={float(getattr(d,key)) if key=='EchoTime' else str(getattr(d,key)) for _,d,_ in entries if hasattr(d,key)}
        if len(known)>1:raise ValueError('所选DICOM含不同回波或图像分量，请分批导入。')
    planes=[];seen={}
    for path,d,n in entries:
        if cancel():raise Cancelled('已取消DICOM加载')
        try:
            decoded=iter_pixels(path)
            for index in range(n):
                if cancel():raise Cancelled('已取消DICOM加载')
                affine,spacing,meta=frame_metadata(d,index)
                a=np.asarray(next(decoded),dtype=np.float32)*meta['rescale_slope']+meta['rescale_intercept'];validate_image(a)
                plane=Plane(0,0,a,affine,spacing,str(path),'DICOM PixelSpacing mm; LPS geometry converted to RAS',source_index=(index,),input_metadata=meta)
                identity=(meta['sop_instance_uid'],index)
                if identity[0] and identity in seen:
                    old=seen[identity]
                    if not np.array_equal(old.image,a) or not np.allclose(old.affine,affine,rtol=0,atol=1e-4) or old.input_metadata['time_candidates']!=meta['time_candidates']:
                        raise ValueError('重复SOP实例的图像、几何或时相不一致。')
                    old.input_metadata.setdefault('duplicate_sources',[]).append(str(path));continue
                if identity[0]:seen[identity]=plane
                planes.append(plane)
                if progress:progress(len(planes),count,'载入影像')
            try:next(decoded)
            except StopIteration:pass
            else:raise ValueError('DICOM实际像素帧数与NumberOfFrames不一致。')
        except (NotImplementedError,RuntimeError,AttributeError,StopIteration) as error:
            raise ValueError('DICOM像素无法解码，请检查文件完整性或压缩解码器：'+str(error)) from error
    for key in ['echo_time_ms','complex_component']:
        if len({p.input_metadata[key] for p in planes if key in p.input_metadata})>1:raise ValueError('所选DICOM含不同回波或图像分量，请分批导入。')
    return planes
