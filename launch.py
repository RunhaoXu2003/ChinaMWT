"""Select a compatible environment without machine-specific developer paths."""
from pathlib import Path
from datetime import datetime
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def choose_python():
    candidates = []
    if os.environ.get('LVWT_PYTHON'):
        candidates.append(Path(os.environ['LVWT_PYTHON']))
    candidates += [ROOT / '.venv/Scripts/python.exe', ROOT / '.venv/bin/python', Path(sys.executable)]
    probe = "import importlib.util,sys;sys.exit(0 if all(importlib.util.find_spec(x) for x in ['torch','PyQt6','nibabel','numpy','scipy','skimage','pydicom','matplotlib','PIL']) else 2)"
    for candidate in dict.fromkeys(candidates):
        if candidate.is_file():
            result = subprocess.run([str(candidate), '-c', probe], capture_output=True, timeout=25)
            if result.returncode == 0:
                return candidate
    raise RuntimeError('Install requirements.txt in the active/local virtual environment, or set LVWT_PYTHON to its Python executable.')


def main():
    executable = choose_python()
    if '--check' in sys.argv:
        print(str(executable)); return
    (ROOT / 'logs').mkdir(exist_ok=True)
    logfile = ROOT / 'logs' / ('app_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.log')
    with logfile.open('w', encoding='utf-8') as stream:
        process = subprocess.Popen([str(executable), '-X', 'utf8', '-X', 'faulthandler', str(ROOT / 'app.py'), *sys.argv[1:]],
                                   cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
    time.sleep(1.5)
    if process.poll() is not None and process.returncode != 0:
        raise RuntimeError('Startup failed; see ' + str(logfile))
    (ROOT / 'logs/last_launch.json').write_text(json.dumps(dict(pid=process.pid, python=str(executable), log=str(logfile)), indent=2), encoding='utf-8')
    print(f'Started PID {process.pid}; log: {logfile}')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(error); sys.exit(1)
