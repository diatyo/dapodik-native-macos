#!/usr/bin/env python3
"""Start, stop, inspect and back up this user's isolated native Dapodik install."""
import argparse
import fcntl
import json
import os
import pathlib
import re
import signal
import socket
import subprocess
import time
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parent
RUNTIME = ROOT/'runtime' if (ROOT/'runtime').exists() else ROOT.parent/'native-runtime'
PREFIX = RUNTIME/'root/opt/local'
PHP = PREFIX/'bin/php72'
PG = PREFIX/'lib/postgresql92/bin'
PORT = 54532
URL = 'http://127.0.0.1:5774/'

def environment():
    env = dict(os.environ)
    dirs = [PREFIX/'lib', PREFIX/'libexec/openssl11/lib', PREFIX/'libexec/openssl3/lib', PREFIX/'lib/postgresql92']
    extra = ROOT.parent/'tools/innoextract-macports/opt/local/lib'
    if extra.exists(): dirs.append(extra)
    env['DYLD_LIBRARY_PATH'] = ':'.join(map(str, dirs))
    env.pop('DAPODIK_NATIVE_DB_DIAGNOSTICS', None)
    env['TZ'] = 'Asia/Jakarta'
    env['DAPODIK_PREFILL_DIR'] = str(ROOT/'prefill_dapodik')
    env['DAPODIK_NATIVE_7ZA'] = str(PREFIX/'lib/p7zip/7za')
    if (PREFIX/'bin/7zz').exists(): env['DAPODIK_NATIVE_7ZA'] = str(PREFIX/'bin/7zz')
    env['DAPODIK_NATIVE_DB_SOCKET'] = str(ROOT/'run')
    return env

def configure():
    for folder in ['logs','run','sessions','backups','prefill_dapodik']:
        (ROOT/folder).mkdir(exist_ok=True, mode=0o700)
    os.chmod(ROOT/'run', 0o700)
    ext = PREFIX/'lib/php72/extensions/no-debug-non-zts-20170718'
    settings = [f'zend_extension="{RUNTIME}/ioncube/ioncube/ioncube_loader_mac_7.2.so"', f'extension_dir="{ext}"']
    settings += ['extension='+x+'.so' for x in ['mbstring','openssl','curl','gd','iconv','exif','gettext']]
    settings += [f'extension="{RUNTIME}/extensions/{x}.so"' for x in ['pgsql','pdo_pgsql']]
    for optional in ['zip', 'xmlrpc', 'snmp']:
        if (ext/(optional+'.so')).exists(): settings.append('extension='+optional+'.so')
    settings += ['date.timezone=Asia/Jakarta','memory_limit=512M','max_execution_time=300','upload_max_filesize=256M','post_max_size=256M',f'session.save_path="{ROOT}/sessions"','display_errors=Off','log_errors=On',f'error_log="{ROOT}/logs/php.log"','error_reporting=E_ALL & ~E_DEPRECATED & ~E_STRICT']
    (ROOT/'php.ini').write_text('\n'.join(settings)+'\n')
    manifest = json.loads((ROOT/'manifest.json').read_text())
    if 'installation_id' not in manifest:
        manifest['installation_id'] = str(uuid.uuid4())
        (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    installation_id = manifest['installation_id']
    ini = f'[config]\nAppId={installation_id}\nDefDBPort={PORT}\nDefWebPort=5774\nAppName=Dapodikdasmen\nHostname=localhost\nApproot="{ROOT}/app"\nAppRootWin="{ROOT}/app"\nDbPort={PORT}\nWebPort=5774\nSyncPortDikdas=5775\nDirektorat=Pauddikdasmen\n'
    for relative in ['app/config/install.ini','app/dataweb/apps/tmp/install.ini']:
        (ROOT/relative).write_text(ini)
    (ROOT/'app/config/path.ini').write_text(str(ROOT/'app'))

def pid_for(name):
    p = ROOT/'run'/(name+'.pid')
    try: pid = int(p.read_text().strip())
    except (OSError,ValueError): return None
    command = subprocess.run(['/bin/ps','-p',str(pid),'-o','command='],text=True,capture_output=True).stdout
    expected = str(PG/'postgres') if name == 'postgres' else str(PHP)
    return pid if expected in command and str(ROOT) in command else None

def reserve(port):
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: s.bind(('127.0.0.1',port))
        except OSError: raise RuntimeError(f'Port {port} sedang digunakan aplikasi lain.')

def spawn(name,args,env,cwd=None):
    with (ROOT/'logs'/(name+'.log')).open('ab') as log:
        child = subprocess.Popen(list(map(str,args)),env=env,cwd=cwd,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    (ROOT/'run'/(name+'.pid')).write_text(str(child.pid))
    return child

def start():
    env = environment()
    if not pid_for('postgres'):
        spawn('postgres',[PG/'postgres','-D',ROOT/'database','-p',PORT,'-h','','-k',ROOT/'run'],env)
        for _ in range(50):
            check = subprocess.run([str(PG/'psql'),'-X','-h',str(ROOT/'run'),'-p',str(PORT),'-U','postgres','-d','postgres','-Atc','SELECT 1'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if check.returncode == 0: break
            time.sleep(.1)
        else: raise RuntimeError('Database belum siap. Periksa logs/postgres.log.')
    for name,port,webroot in [('web',5774,ROOT/'app/dataweb/apps/web'),('sync',5775,ROOT/'app/dataweb/synch_dikdas')]:
        if not pid_for(name):
            reserve(port)
            specific = dict(env,DAPODIK_DOCUMENT_ROOT=str(webroot))
            spawn(name,[PHP,'-c',ROOT/'php.ini','-S',f'127.0.0.1:{port}','-t',webroot,ROOT/'router.php'],specific,cwd=webroot)
    for _ in range(50):
        try:
            with urllib.request.urlopen(URL,timeout=2) as r: content=r.read()
            if re.search(rb'id\s*=\s*["\x27]?form2\b', content): print('Dapodik 2027.b siap: '+URL); return
        except (OSError,TimeoutError): pass
        time.sleep(.1)
    raise RuntimeError('Halaman masuk belum siap. Periksa folder logs.')

def stop():
    for name in ['web','sync']:
        pid = pid_for(name)
        if pid: os.kill(pid,signal.SIGTERM)
    if pid_for('postgres'):
        subprocess.run([str(PG/'pg_ctl'),'-D',str(ROOT/'database'),'-m','fast','-w','stop'],env=environment(),check=True)
    print('Layanan Dapodik dihentikan.')

def backup():
    if not pid_for('postgres'): raise RuntimeError('Jalankan Dapodik sebelum membuat cadangan.')
    dest = ROOT/'backups'/time.strftime('%Y%m%d-%H%M%S')
    dest.mkdir(mode=0o700)
    for db in ['pendataan','dapodik_app']:
        subprocess.run([str(PG/'pg_dump'),'-h',str(ROOT/'run'),'-p',str(PORT),'-U','postgres','-Fc','-f',str(dest/(db+'.dump')),db],env=environment(),check=True)
    (dest/'manifest.json').write_text((ROOT/'manifest.json').read_text())
    print('Cadangan tersimpan: '+str(dest))

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['start','stop','status','backup'])
    parser.add_argument('--open',action='store_true')
    args=parser.parse_args()
    configure()
    with (ROOT/'run/control.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if args.action=='start': start()
        elif args.action=='stop': stop()
        elif args.action=='backup': backup()
        else: print(json.dumps({x:bool(pid_for(x)) for x in ['postgres','web','sync']}))
    if args.open and args.action=='start': subprocess.run(['/usr/bin/open',URL],check=True)
