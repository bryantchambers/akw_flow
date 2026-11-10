#!/usr/bin/env python3
"""Add display pyramids to a completed regional build, retaining native data."""
import json,os,sys,hashlib
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.build_regional_native import OUT,write_json
from hydraulics.regional_pyramids import build_pyramids
lock=OUT/'build.lock'
fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
m=json.loads((OUT/'manifest.json').read_text())
if m['status'] not in ('complete','preparing_display'):
    lock.unlink();raise ValueError('Complete numerical export required')
try:
    m['status']='preparing_display';write_json(OUT/'manifest.json',m)
    def progress(name):
        p={'stage':'preparing_display','message':'Building display-only pyramids: '+name,'pid':os.getpid(),'updated_utc':datetime.now(timezone.utc).isoformat()}
        write_json(OUT/'progress.json',p);print(json.dumps(p),flush=True)
    build_pyramids(OUT,progress)
    m.update(status='complete',display_pyramid_factors=[2,4,8,16,32,64,128],display_resampling='nearest',display_code_sha256=hashlib.sha256((Path(__file__).resolve().parents[1]/'hydraulics/regional_pyramids.py').read_bytes()).hexdigest())
    write_json(OUT/'manifest.json',m);write_json(OUT/'progress.json',{'stage':'complete','message':'Native model and display pyramids ready','updated_utc':datetime.now(timezone.utc).isoformat()})
finally:lock.unlink(missing_ok=True)
