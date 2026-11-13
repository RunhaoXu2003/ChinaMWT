from dataclasses import dataclass,field
from pathlib import Path
import json
import re
import numpy as np
import nibabel as nib
from .common import Cancelled,sha256

CINE=re.compile(r'^CineSAX-(\d+)_(\d+)_(.+)$',re.I)

def stem(path):
    n=Path(path).name
    return n[:-7] if n.lower().endswith('.nii.gz') else Path(n).stem

@dataclass
class Plane:
    slice:int
    frame:int
    image:np.ndarray
    affine:np.ndarray
    spacing:tuple
    source:str
    unit_note:str
    masks:dict=field(default_factory=dict)
    json_data:dict|None=None
    source_index:tuple=()
    input_metadata:dict=field(default_factory=dict)
    @property
    def key(self):return self.slice,self.frame
    @property
    def name(self):return f'CineSAX-{self.slice:03d}_{self.frame:03d}_image.nii.gz'

@dataclass
class Case:
    source:str
    planes:list
    notes:list=field(default_factory=list)
    run_dir:str|None=None
    metadata:dict=field(default_factory=dict)
    source_paths:list=field(default_factory=list)
    @property
    def frames(self):return sorted({p.frame for p in self.planes})
    @property
    def slices(self):return sorted({p.slice for p in self.planes})
    def by_key(self,key):return next((p for p in self.planes if p.key==tuple(key)),None)

class InputAmbiguity(ValueError):
    """Metadata cannot identify one unambiguous slice/time arrangement."""
    def __init__(self,message,options=('position_order','file_slices','file_time')):
        super().__init__(message);self.options=tuple(options)

def geometry(nii):
    unit=nii.header.get_xyzt_units()[0];factor={'unknown':1.,'mm':1.,'meter':1000.,'micron':.001}.get(unit)
    if factor is None:raise ValueError(f'不支持的空间单位：{unit}')
    a=np.array(nii.affine,float);a[:3,:]*=factor
    sp=np.array(nii.header.get_zooms()[:2])*factor
    if not np.isfinite(a).all() or not np.isfinite(sp).all() or np.any(sp<=0):raise ValueError('无效像素间距/affine。')
    lengths=np.linalg.norm(a[:3,:2],axis=0)
    if not np.allclose(lengths,sp,rtol=1e-4,atol=1e-4):raise ValueError('NIfTI affine与header像素间距不一致。')
    if abs(np.dot(a[:3,0],a[:3,1])/np.prod(lengths))>1e-4:raise ValueError('不支持剪切的层面几何，请先核对图像。')
    note='Header单位unknown；按研究约定将zoom视为mm' if unit=='unknown' else f'NIfTI {unit} → mm'
    return a,tuple(map(float,sp)),note

def validate_image(a):
    if a.ndim!=2 or max(a.shape)>4096 or min(a.shape)<8:raise ValueError(f'不支持的2D尺寸：{a.shape}')
    if not np.isfinite(a).all():raise ValueError('影像含非有限像素。')

def validate_mask(a,shape):
    if a.shape!=shape:raise ValueError('ROI与原图尺寸不一致。')
    if not np.isfinite(a).all() or not np.allclose(a,np.rint(a),atol=1e-5):raise ValueError('ROI必须是离散标签。')
    if not set(np.unique(a)).issubset({0,1,2,3}):raise ValueError('ROI标签应为0/1/2/3。')
    return a.astype(np.uint8)

def mask_path(folder,name):
    folder=Path(folder);base=stem(name)
    candidates=[folder/('ROI-'+Path(name).name),folder/('ROI-'+base+'.nii.gz'),folder/('ROI-'+base+'.nii')]
    return next((p for p in candidates if p.exists()),None)

def mask_for_2d(p,plane):
    n=nib.load(str(p));a=np.asarray(n.dataobj)
    if any(k!=1 for k in a.shape[2:]):raise ValueError('配对2D ROI含多个层面/时相。')
    a=a.reshape(a.shape[:2]);aff,_,_=geometry(n)
    if not np.allclose(aff,plane.affine,rtol=0,atol=1e-4):raise ValueError('ROI与原图affine不匹配；不会自动配准。')
    plane.masks['existing']=validate_mask(a,plane.image.shape)
    jp=p.with_name(stem(p)+'.json')
    if jp.exists():plane.json_data=json.loads(jp.read_text(encoding='utf-8-sig'))

def load_nifti(path,mask_folder=None):
    from .importers import read_nifti
    return read_nifti(Path(path).resolve(),mask_folder)

def load_dicoms(paths,series_uid=None,cancel=lambda:False):
    from .dicom_reader import read_dicoms
    from .importers import organize_planes
    planes=read_dicoms([Path(p).resolve() for p in paths],series_uid=series_uid,cancel=cancel)
    return organize_planes(planes)[0]

def load_case(path,mask_folder=None,progress=None,cancel=lambda:False,organization='auto'):
    from .importers import import_case
    return import_case(path,mask_folder,progress,cancel,organization)

def input_manifest(case):
    return dict(schema='lvwt.input-manifest.v1',source_index_base=0,
        output_id_convention='Explicit filename IDs are retained; other slice/frame IDs are normalized to 1-based indices.',selection=case.source_paths or [case.source],
        organization=case.metadata.get('organization',{}),warnings=case.metadata.get('input_warnings',[]),
        planes=[dict(output=p.name,slice=p.slice,frame=p.frame,source=p.source,source_index=list(p.source_index),shape=list(p.image.shape),spacing_mm=list(p.spacing),affine_ras_mm=p.affine.tolist(),
                     metadata=p.input_metadata) for p in case.planes])

def save_plane(plane,path,array=None,mask=False):
    a=plane.image if array is None else array
    n=nib.Nifti1Image(np.asarray(a,dtype=np.uint8 if mask else np.float32),plane.affine)
    n.header.set_xyzt_units('mm');n.set_qform(plane.affine,code=1);n.set_sform(plane.affine,code=1)
    nib.save(n,str(path))
