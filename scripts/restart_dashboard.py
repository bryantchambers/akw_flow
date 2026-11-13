#!/usr/bin/env python3
"""Restart only this checkout's managed dashboard and verify readiness."""
import argparse,json,os,signal,socket,subprocess,sys,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=9090);p.add_argument('--host',default='0.0.0.0');a=p.parse_args()
    if not 1<=a.port<=65535:raise ValueError('Invalid port')
    stopped_managed=False
    runtime=ROOT/'.runtime';runtime.mkdir(exist_ok=True);pidfile=runtime/f'server-{a.port}.pid';logfile=runtime/f'server-{a.port}.log'
    if pidfile.exists():
        old=int(pidfile.read_text());proc=Path(f'/proc/{old}')
        if proc.exists():
            command=(proc/'cmdline').read_bytes()
            if command:
                if b'server.py' not in command or (proc/'cwd').resolve()!=ROOT:raise RuntimeError('PID belongs to an unexpected process; refusing to stop it')
                os.kill(old,signal.SIGTERM);stopped_managed=True
                limit=time.monotonic()+10
                while proc.exists() and time.monotonic()<limit:
                    try:
                        if (proc/'stat').read_text().split()[2]=='Z':break
                    except FileNotFoundError:break
                    time.sleep(.1)
                else:
                    if proc.exists():raise RuntimeError('Previous dashboard did not stop')
    connect_host='127.0.0.1' if a.host=='0.0.0.0' else a.host
    limit=time.monotonic()+(5 if stopped_managed else 0)
    while True:
        with socket.socket() as check:
            check.settimeout(.5);occupied=check.connect_ex((connect_host,a.port))==0
        if not occupied:break
        if time.monotonic()>=limit:raise RuntimeError('Port occupied by an unmanaged listener')
        time.sleep(.1)
    with logfile.open('ab') as log:
        child=subprocess.Popen([sys.executable,'-u',str(ROOT/'server.py'),'--host',a.host,'--port',str(a.port)],cwd=ROOT,stdout=log,stderr=log,start_new_session=True)
    pidfile.write_text(str(child.pid)+'\n');limit=time.monotonic()+15
    while time.monotonic()<limit:
        if child.poll() is not None:raise RuntimeError(f'Dashboard exited; inspect {logfile}')
        try:
            with urllib.request.urlopen(f'http://{connect_host}:{a.port}/healthz',timeout=1) as response:data=json.load(response)
            if data.get('status')=='ok' and child.poll() is None:
                print(json.dumps({'pid':child.pid,'port':a.port,'health':data}));return
        except (OSError,ValueError):pass
        time.sleep(.1)
    child.terminate();raise RuntimeError('Dashboard did not become ready')
if __name__=='__main__':main()
