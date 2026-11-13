from pathlib import Path
from datetime import datetime
import hashlib
import json
import numpy as np

APP_ROOT=Path(__file__).resolve().parents[1]
VERSION='0.3.0'

def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(x) for x in value]
    if isinstance(value,np.ndarray):return clean(value.tolist())
    if isinstance(value,np.generic):return clean(value.item())
    if isinstance(value,Path):return str(value)
    if isinstance(value,float) and not np.isfinite(value):return None
    return value

def write_json(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_name(p.name+'.tmp')
    temp.write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    temp.replace(p)

def make_run(output_root,input_path):
    root=Path(output_root).expanduser().resolve()
    inputs=[input_path] if isinstance(input_path,(str,Path)) else input_path
    for value in inputs:
        src=Path(value).expanduser().resolve()
        if src.is_file():src=src.parent
        if root==src or src in root.parents:raise ValueError('输出目录不能等于输入目录或位于输入目录内。')
    root.mkdir(parents=True,exist_ok=True)
    run=root/('run_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    run.mkdir()
    return run

class Cancelled(RuntimeError):pass
