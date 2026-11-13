"""Resolve the locally verified regional case, retaining CPU artifacts."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'assets/private/water_system'
def allowed(name):
    return isinstance(name,str) and (name=='hydraulics' or re.fullmatch(r'hydraulics_gpu(?:_[A-Za-z0-9_-]+)?',name) is not None)


def active_directory():
    pointer=BASE/'active_case.json'
    if pointer.exists():
        p=json.loads(pointer.read_text());name=p.get('directory')
        if not allowed(name):raise ValueError('Unknown active regional case')
        directory=BASE/name
        manifest=directory/'manifest.json';verification=directory/'verification.json'
        if manifest.exists() and verification.exists():
            m=json.loads(manifest.read_text());v=json.loads(verification.read_text())
            state={'size':manifest.stat().st_size,'mtime_ns':manifest.stat().st_mtime_ns}
            if m.get('status')=='complete' and v.get('status')=='passed' and state==p['manifest_state']:return directory
    return BASE/'hydraulics'


def activate(directory):
    from datetime import datetime,timezone
    directory=Path(directory).resolve()
    if directory.parent!=BASE.resolve() or not allowed(directory.name):raise ValueError('Case must be a known private regional directory')
    manifest=directory/'manifest.json';m=json.loads(manifest.read_text());v=json.loads((directory/'verification.json').read_text())
    acceptance=json.loads((BASE/'acceptance.json').read_text());coupling=json.loads((BASE/'coupling.json').read_text())
    if m.get('status')!='complete' or v.get('status')!='passed' or acceptance.get('stage')!='complete' or acceptance.get('model_directory')!=directory.name or coupling.get('model_directory','hydraulics')!=directory.name:raise ValueError('Case verification and coupling must pass before activation')
    record={'directory':directory.name,'backend':m.get('execution',{}).get('backend','cpu'),'activated_utc':datetime.now(timezone.utc).isoformat(),
        'manifest_state':{'size':manifest.stat().st_size,'mtime_ns':manifest.stat().st_mtime_ns},'scientific_validation':'exploratory; not calibrated'}
    temp=BASE/'active_case.tmp.json';temp.write_text(json.dumps(record,indent=2));temp.replace(BASE/'active_case.json');return record
