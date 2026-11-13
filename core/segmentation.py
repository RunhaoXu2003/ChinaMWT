from pathlib import Path
import time
import numpy as np
from .common import APP_ROOT,Cancelled,sha256,write_json
from .images import save_plane,input_manifest
from .measurement import jade_json

class Segmenter:
    def __init__(self,checkpoint=None,device='auto'):
        import torch
        from vendor.mednext import create_mednext
        self.torch=torch;self.path=Path(checkpoint or APP_ROOT/'weights/Multi-20260908.pth')
        self.device=torch.device('cuda' if device=='auto' and torch.cuda.is_available() else 'cpu' if device=='auto' else device)
        if self.device.type=='cuda' and not torch.cuda.is_available():raise RuntimeError('当前Python环境不支持CUDA，请选择CPU或使用已配置GPU启动器。')
        ckpt=torch.load(str(self.path),map_location='cpu',weights_only=True)
        cfg=ckpt.get('config',{})
        self.cfg=dict(spatial_dims=2,in_channels=1,num_classes=4,mednext_variant='L',mednext_kernel=5,img_size=[224,224]);self.cfg.update(cfg)
        if int(self.cfg['spatial_dims'])!=2 or int(self.cfg['in_channels'])!=1 or int(self.cfg['num_classes'])!=4:raise ValueError('当前程序仅支持单通道2D四标签CineSAX权重。')
        lm=self.cfg.get('label_map',{})
        if any(int(k)!=int(v) for k,v in lm.items()):raise ValueError('权重label_map不是0/1/2/3恒等映射，不能自动替换标签语义。')
        self.model=create_mednext(variant=self.cfg['mednext_variant'],spatial_dims=2,in_channels=1,out_channels=4,kernel_size=self.cfg['mednext_kernel'],deep_supervision=False)
        self.model.load_state_dict(ckpt.get('model_state_dict',ckpt),strict=True)
        self.model.to(self.device).eval()
        self.info=dict(checkpoint=self.path.name,sha256=sha256(self.path),config=self.cfg,device=str(self.device),
                       precision='CUDA FP16 autocast' if self.device.type=='cuda' else 'CPU float32',weights_type=ckpt.get('weights_type'),
                       torch=torch.__version__,preprocess='Resize bilinear align_corners=False; nonzero resized-pixel mean/std; restore argmax by nearest interpolation.')
        del ckpt

    def predict(self,image):
        torch=self.torch;F=torch.nn.functional
        a=np.asarray(image,dtype=np.float32)
        t=torch.from_numpy(np.ascontiguousarray(a)).float()[None,None]
        t=F.interpolate(t,size=tuple(self.cfg['img_size']),mode='bilinear',align_corners=False)
        nz=t!=0
        if nz.any():
            mu,sd=t[nz].mean(),t[nz].std()
            if sd>1e-8:t=(t-mu)/sd
            t[~nz]=0.
        t=t.to(self.device)
        with torch.no_grad():
            if self.device.type=='cuda':
                with torch.autocast(device_type='cuda',dtype=torch.float16):logits=self.model(t)
            else:logits=self.model(t)
        pred=logits.argmax(dim=1).squeeze(0).cpu()
        if tuple(pred.shape)!=a.shape:pred=F.interpolate(pred.float()[None,None],size=a.shape,mode='nearest').squeeze(0).squeeze(0).to(torch.uint8)
        return pred.numpy().astype(np.uint8)

    def close(self):
        self.model=None
        if self.device.type=='cuda':self.torch.cuda.empty_cache()

def segment_case(case,run_dir,checkpoint=None,device='auto',steps=None,progress=None,cancel=lambda:False):
    from vendor.corseg_postprocessing import apply_postprocessing
    run=Path(run_dir);steps=steps or {'step1':True,'step2':True,'step3':True}
    for name in ['images','Prediction','Postprocess','Contours']:(run/name).mkdir(parents=True,exist_ok=True)
    write_json(run/'input_manifest.json',input_manifest(case))
    started=time.perf_counter();engine=Segmenter(checkpoint,device);stats=[]
    try:
        for i,p in enumerate(case.planes):
            if cancel():raise Cancelled('自动分割已取消；已完成文件保留在当前run目录。')
            raw=engine.predict(p.image)
            post,details=apply_postprocessing(raw,steps)
            p.masks['raw']=raw;p.masks['post']=post
            save_plane(p,run/'images'/p.name)
            for folder,mask in [('Prediction',raw),('Postprocess',post)]:save_plane(p,run/folder/('ROI-'+p.name),mask,mask=True)
            data=jade_json(p,post)
            write_json(run/'Postprocess'/('ROI-'+p.name[:-7]+'.json'),data)
            write_json(run/'Contours'/('ROI-'+p.name[:-7]+'.json'),data)
            stats.append(dict(slice=p.slice,frame=p.frame,**details))
            if progress:progress(i+1,len(case.planes),'自动分割')
        info=dict(**engine.info,postprocessing=steps,planes=len(case.planes),elapsed_seconds=time.perf_counter()-started)
        write_json(run/'segmentation.json',dict(status='complete',model=info,planes=stats))
        case.run_dir=str(run);case.metadata['segmentation']=info
        return info
    finally:engine.close()
