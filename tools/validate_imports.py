"""Known-value synthetic single/multiple-file NIfTI and DICOM import fixtures."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import numpy as np
import nibabel as nib
import pydicom
from pydicom.dataset import Dataset,FileDataset,FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian,MRImageStorage,EnhancedMRImageStorage,RLELossless,generate_uid
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.images import load_case,InputAmbiguity,input_manifest,save_plane
from core.common import write_json,sha256,make_run,Cancelled,VERSION

CHECKS=[]
def check(name,value):
    assert value,name
    CHECKS.append(name)
def rejects(name,fn,error=ValueError):
    try:fn()
    except error:check(name,True)
    else:raise AssertionError(name)

def nifti(path,z=1,t=1,z_offset=0,t_offset=0,base=0,ndim=4):
    array=np.empty((16,20,z,t),np.float32)
    for k in range(z):
        for j in range(t):array[:,:,k,j]=base+10*k+j
    if ndim==2:array=array[:,:,0,0]
    elif ndim==3:array=array[:,:,:,0]
    affine=np.diag([1.3,1.7,8.,1.]);affine[:3,3]=[11,22,z_offset]
    img=nib.Nifti1Image(array,affine);img.header.set_xyzt_units('mm','sec');img.header['toffset']=t_offset
    if ndim==4:img.header.set_zooms((1.3,1.7,8.,.04))
    nib.save(img,path);return path

def dicom(path,frames,*,enhanced=False,legacy=False,patient='fixture',study=None,reference=None,series=None,dimensions_only=False):
    """frames=(spatial index, temporal index); values and per-frame rescale are known."""
    meta=FileMetaDataset();meta.TransferSyntaxUID=ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID=EnhancedMRImageStorage if enhanced else MRImageStorage;meta.MediaStorageSOPInstanceUID=generate_uid()
    d=FileDataset(str(path),{},file_meta=meta,preamble=b'\0'*128);d.SOPClassUID=meta.MediaStorageSOPClassUID;d.SOPInstanceUID=meta.MediaStorageSOPInstanceUID
    d.PatientID=patient;d.StudyInstanceUID=study or generate_uid();d.FrameOfReferenceUID=reference or generate_uid();d.SeriesInstanceUID=series or generate_uid();d.Modality='MR'
    d.Rows=16;d.Columns=20;d.SamplesPerPixel=1;d.PhotometricInterpretation='MONOCHROME2';d.BitsAllocated=16;d.BitsStored=16;d.HighBit=15;d.PixelRepresentation=0
    row=np.array([2**-.5,2**-.5,0]);col=np.array([0.,0.,1.]);normal=np.cross(row,col);origin=np.array([11.,22.,33.]);iop=np.r_[row,col].tolist()
    pixels=np.stack([np.full((16,20),10*z+t+10,np.uint16) for z,t in frames])
    if enhanced:
        d.NumberOfFrames=len(frames);shared=Dataset();measures=Dataset();measures.PixelSpacing=[1.3,1.7];measures.SliceThickness=8
        orientation=Dataset();orientation.ImageOrientationPatient=iop;shared.PixelMeasuresSequence=Sequence([measures]);shared.PlaneOrientationSequence=Sequence([orientation]);d.SharedFunctionalGroupsSequence=Sequence([shared])
        definitions=[]
        for tag in [0x00209128,0x00209057]:
            definition=Dataset();definition.DimensionIndexPointer=tag;definition.FunctionalGroupPointer=0x00209111;definitions.append(definition)
        d.DimensionIndexSequence=Sequence(definitions);per=[]
        for z,t in frames:
            group=Dataset();position=Dataset();position.ImagePositionPatient=(origin+normal*z*8).tolist();group.PlanePositionSequence=Sequence([position])
            content=Dataset();content.InStackPositionNumber=z+1;content.DimensionIndexValues=[t+1,z+1]
            if not dimensions_only:content.TemporalPositionIndex=t+1
            group.FrameContentSequence=Sequence([content]);transform=Dataset();transform.RescaleSlope=t+2;transform.RescaleIntercept=-3-z;group.PixelValueTransformationSequence=Sequence([transform]);per.append(group)
        d.PerFrameFunctionalGroupsSequence=Sequence(per)
    else:
        z,t=frames[0];d.ImageOrientationPatient=iop;d.ImagePositionPatient=(origin+normal*z*8).tolist();d.PixelSpacing=[1.3,1.7];d.SliceThickness=8;d.RescaleSlope=2;d.RescaleIntercept=-3
        d.TemporalPositionIdentifier=t+1;d.InstanceNumber=100*z+t+1
        if legacy:d.NumberOfFrames=len(frames);d.FrameTime=40
    d.PixelData=pixels.tobytes();d.save_as(path,enforce_file_format=True)
    return path

def fixtures(root):
    result={};root=Path(root);root.mkdir(exist_ok=True)
    single=root/'single';single.mkdir();result['single_nifti']=nifti(single/'单张图像.nii.gz',base=7,ndim=2)
    group=root/'2d';group.mkdir();files=[]
    for z in range(3):
        for t in range(2):
            p=nifti(group/f'part{7-z*2-t}.nii.gz',z_offset=z*8,base=z*10+t,ndim=2)
            write_json(group/(p.name[:-7]+'.json'),{'TemporalPositionIndex':t+1});files.append(p)
    result['single_frame_nifti']=files
    group=root/'3d';group.mkdir();result['volumes3d']=[nifti(group/f'frame{t+1}.nii.gz',z=3,base=100*t,ndim=3) for t in range(2)]
    group=root/'4d_spatial';group.mkdir();result['volumes4d_spatial']=[nifti(group/f'stack{i}.nii.gz',z=3,t=2,z_offset=i*24,base=i*100) for i in range(2)]
    group=root/'4d_temporal';group.mkdir();result['volumes4d_temporal']=[nifti(group/f'block{i}.nii.gz',z=3,t=2,t_offset=i*.08,base=i*100) for i in range(2)]
    group=root/'ambiguous';group.mkdir();result['ambiguous4d']=[nifti(group/f'volume{i}.nii.gz',z=3,t=2,base=i*100) for i in [2,10]]
    group=root/'flat';group.mkdir();result['ambiguous2d']=[nifti(group/f'image{i}.nii.gz',base=i,ndim=2) for i in [10,2,3]]
    study=generate_uid();reference=generate_uid();series=generate_uid();identity=dict(study=study,reference=reference,series=series)
    group=root/'classic';group.mkdir();result['classic']=[dicom(group/f'file{7-z*2-t}.dcm',[(z,t)],**identity) for z in range(3) for t in range(2)]
    result['single_dicom']=result['classic'][0]
    order=[(2,1),(0,0),(1,1),(2,0),(0,1),(1,0)]
    result['enhanced']=dicom(root/'enhanced.dcm',order,enhanced=True,**identity)
    result['dimension_index']=dicom(root/'dimension_index.dcm',order,enhanced=True,dimensions_only=True,**identity)
    group=root/'enhanced_spatial';group.mkdir();result['enhanced_spatial']=[dicom(group/f'part{i}.dcm',[(z+i*3,t) for t in range(2) for z in range(3)],enhanced=True,**identity) for i in range(2)]
    group=root/'enhanced_temporal';group.mkdir();result['enhanced_temporal']=[dicom(group/f'part{i}.dcm',[(z,t+i*2) for z in range(3) for t in range(2)],enhanced=True,**identity) for i in range(2)]
    result['legacy']=dicom(root/'legacy.dcm',[(0,t) for t in range(3)],legacy=True,**identity)
    return result

def verify_dicom(case,enhanced=True):
    row=np.array([2**-.5,2**-.5,0]);col=np.array([0.,0.,1.]);normal=np.cross(row,col);origin=np.array([11.,22.,33.]);ras=np.diag([-1.,-1.,1.])
    for p in case.planes:
        z,t=p.slice-1,p.frame-1;expected=(10*z+t+10)*(t+2)-3-z if enhanced else (10*z+t+10)*2-3
        check(f'DICOM per-frame pixels {p.key} '+str(enhanced),np.all(p.image==expected))
        check(f'DICOM physical geometry {p.key} '+str(enhanced),np.allclose((p.affine@np.array([4,7,0,1]))[:3],ras@(origin+normal*z*8+col*4*1.3+row*7*1.7),atol=1e-5))

def main():
    qa=ROOT/'qa';qa.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=qa) as temp:
        root=Path(temp);f=fixtures(root)
        c=load_case(f['single_nifti']);check('Single 2D NIfTI admitted',len(c.planes)==1 and c.planes[0].source_index==(0,0) and np.all(c.planes[0].image==7))
        c=load_case(f['single_frame_nifti'][::-1]);check('Multiple arbitrary-named 2D NIfTI use metadata',len(c.slices)==3 and len(c.frames)==2)
        check('2D metadata order and values',all(np.all(p.image==10*(p.slice-1)+p.frame-1) for p in c.planes))
        c=load_case(f['volumes3d'][::-1]);check('Multiple 3D NIfTI form spatial/time grid',len(c.planes)==6 and c.frames==[1,2])
        check('3D file temporal labels',all(np.all(p.image==100*(p.frame-1)+10*(p.slice-1)) for p in c.planes))
        c=load_case(f['volumes4d_spatial'][::-1]);check('Multiple 4D spatial blocks combine',len(c.slices)==6 and len(c.frames)==2 and len(c.planes)==12)
        check('Spatial blocks retain values',np.all(c.by_key((4,2)).image==101))
        c=load_case(f['volumes4d_temporal'][::-1]);check('Multiple 4D temporal blocks combine by offset',len(c.slices)==3 and len(c.frames)==4 and len(c.planes)==12)
        check('Temporal blocks retain original source indices',c.by_key((2,3)).source_index==(1,0) and np.all(c.by_key((2,3)).image==110))
        rejects('Overlapping 4D blocks request interpretation',lambda:load_case(f['ambiguous4d']),InputAmbiguity)
        c=load_case(f['ambiguous4d'],organization='file_time');check('Confirmed file-time blocks use natural order',len(c.frames)==4 and np.all(c.by_key((1,1)).image==200) and np.all(c.by_key((1,3)).image==1000))
        rejects('Identity-affine 2D files are not silently assigned',lambda:load_case(f['ambiguous2d']),InputAmbiguity)
        c=load_case(f['ambiguous2d'],organization='position_order');check('Confirmed same-position frame ordering',c.slices==[1] and [float(p.image[0,0]) for p in c.planes]==[2,3,10])
        c=load_case(f['ambiguous2d'],organization='file_slices');check('Confirmed file-slice ordering preserves physical affines',c.frames==[1] and len(c.slices)==3 and all(np.array_equal(p.affine,c.planes[0].affine) for p in c.planes))
        c=load_case(f['single_dicom']);check('Single classic DICOM admitted',len(c.planes)==1 and c.planes[0].source_index==(0,));verify_dicom(c,False)
        c=load_case(f['classic'][::-1]);check('Classic multiframe grid built from separate files',len(c.planes)==6);verify_dicom(c,False)
        for name,nz,nt in [('enhanced',3,2),('dimension_index',3,2),('enhanced_spatial',6,2),('enhanced_temporal',3,4)]:
            c=load_case(f[name]);check(name+' dimensions',len(c.slices)==nz and len(c.frames)==nt and len(c.planes)==nz*nt);verify_dicom(c)
        c=load_case(f['legacy']);check('Legacy multi-frame same-plane cine',len(c.slices)==1 and len(c.frames)==3);verify_dicom(c,False)
        partial=load_case(f['classic'][:-1]);check('Missing slice/frame combinations are explicit',partial.metadata['organization']['missing_combinations']==1 and len(partial.planes)==5)
        mixed_echo=root/'mixed_echo.dcm';d=pydicom.dcmread(f['enhanced'])
        for i,group in enumerate(d.PerFrameFunctionalGroupsSequence):
            echo=Dataset();echo.EffectiveEchoTime=2.0+i%2;group.MREchoSequence=Sequence([echo])
        d.save_as(mixed_echo,enforce_file_format=True)
        rejects('Enhanced echo dimension is not merged as cine time',lambda:load_case(mixed_echo))
        bad_frequency=root/'frequency.nii.gz';image=nib.Nifti1Image(np.zeros((16,20,2,2),np.float32),np.eye(4));image.header.set_xyzt_units('mm','hz');nib.save(image,bad_frequency)
        rejects('Frequency NIfTI axis is not treated as cine time',lambda:load_case(bad_frequency))
        compressed=root/'rle.dcm';d=pydicom.dcmread(f['enhanced']);d.compress(RLELossless);d.save_as(compressed,enforce_file_format=True)
        c=load_case(compressed);check('RLE compressed enhanced DICOM decoded',len(c.planes)==6);verify_dicom(c)
        copy=root/'duplicate.dcm';shutil.copy2(f['single_dicom'],copy);c=load_case([f['single_dicom'],copy]);check('Duplicate SOP instance is not double counted',len(c.planes)==1 and bool(c.planes[0].input_metadata.get('duplicate_sources')))
        d=pydicom.dcmread(copy);d.TemporalPositionIdentifier=99;d.save_as(copy,enforce_file_format=True)
        rejects('Conflicting duplicate SOP timing is not silently dropped',lambda:load_case([f['single_dicom'],copy]))
        other=root/'other_patient.dcm';d=pydicom.dcmread(f['single_dicom']);d.PatientID='another';d.SOPInstanceUID=generate_uid();d.save_as(other,enforce_file_format=True)
        rejects('Different patients cannot be merged',lambda:load_case([f['single_dicom'],other]))
        missing=root/'missing.dcm';d=pydicom.dcmread(f['enhanced']);del d.PerFrameFunctionalGroupsSequence[0].PlanePositionSequence;d.save_as(missing,enforce_file_format=True)
        rejects('Enhanced missing physical position rejected',lambda:load_case(missing))
        rejects('Cancellation before decode',lambda:load_case(f['enhanced'],cancel=lambda:True),Cancelled)
        rejects('Output protection covers every selected source',lambda:make_run(f['volumes3d'][0].parent/'out',[f['single_nifti'],f['volumes3d'][0]]))
        c=load_case(f['enhanced_temporal']);manifest=input_manifest(c)
        check('Manifest maps every decoded source frame',len(manifest['planes'])==12 and len({(p['source'],tuple(p['source_index'])) for p in manifest['planes']})==12)
        check('All normalized output names unique',len({p.name for p in c.planes})==len(c.planes))
        original={str(p):sha256(p) for value in f.values() for p in (value if isinstance(value,list) else [value])}
        export=root/'normalized';export.mkdir()
        for p in c.planes:save_plane(p,export/p.name)
        replay=load_case(export);check('Multi-file normalized export replays image grid',all(np.array_equal(p.image,replay.by_key(p.key).image) for p in c.planes))
        check('Source fixture files preserved during export',all(sha256(p)==h for p,h in original.items()))
    sources={str(p.relative_to(ROOT)):sha256(p) for pattern in ['core/images.py','core/importers.py','core/dicom_reader.py','core/common.py','tools/validate_imports.py'] for p in ROOT.glob(pattern)}
    write_json(qa/'imports_verification.json',dict(version=VERSION,status='PASS',checks=CHECKS,source_sha256=sources,
        scope='Known-value synthetic input/organization/physical-geometry fixtures, including RLE enhanced MR; not actual scanner/vendor clinical validation.'))
    print(json.dumps(dict(status='PASS',checks=len(CHECKS),version=VERSION)))

if __name__=='__main__':main()
