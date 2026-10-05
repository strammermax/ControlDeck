"""Privileged, finite allowlist worker; never execute commands from a queued job."""
try:
    import fcntl
except ImportError:
    fcntl=None
import json
import os
import re
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path('/var/lib/controldeck/installations')
INSTALLER = Path('/opt/controldeck-integrations/installer/scripts/install-termix.sh')


def validate_job(value,job_id,now):
    if not isinstance(value,dict) or set(value)!={'id','module','method','target','requestedBy','createdAt'}:
        raise ValueError('Invalid job fields')
    if value['id']!=job_id or not re.fullmatch('[a-f0-9]{32}',value['id']): raise ValueError('Invalid job id')
    if (value['module'],value['method'],value['target'])!=('termix','docker','local'): raise ValueError('Unsupported installation')
    if not isinstance(value['requestedBy'],str) or type(value['createdAt']) not in (float,int): raise ValueError('Invalid requester')
    if not 0<=now-value['createdAt']<600: raise ValueError('Expired installation')
    return value


def read_job(path):
    descriptor=os.open(path,os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor,'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode): raise ValueError('Invalid job file')
        content=stream.read(16385)
    if len(content)>16384: raise ValueError('Job is too large')
    return validate_job(json.loads(content),path.stem,time.time())


def write_result(directory_fd,name,value):
    temporary=name+'.'+uuid.uuid4().hex+'.tmp'
    descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o640,dir_fd=directory_fd)
    try:
        os.fchown(descriptor,0,os.fstat(directory_fd).st_gid)
        with os.fdopen(descriptor,'w') as stream:
            json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,name,src_dir_fd=directory_fd,dst_dir_fd=directory_fd)
    finally:
        try:os.unlink(temporary,dir_fd=directory_fd)
        except FileNotFoundError:pass


def main():
    if fcntl is None or os.geteuid()!=0: raise SystemExit('Run as root on Linux')
    lock=open('/run/lock/controldeck-install.lock','a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return
    descriptors=[]
    try:
        # Keep opened directory handles. Renaming a parent cannot redirect writes.
        for directory in (ROOT,ROOT/'results'):
            descriptor=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            info=os.fstat(descriptor)
            if info.st_uid!=0 or info.st_mode & 0o022: raise SystemExit('Unsafe worker directory')
            descriptors.append(descriptor)
        write_result(descriptors[0],'worker.json',{'updatedAt':time.time()})
        for path in sorted((ROOT/'queue').glob('*.json')):
            if not re.fullmatch('[a-f0-9]{32}',path.stem):continue
            try:
                result_fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=descriptors[1])
                with os.fdopen(result_fd) as existing:
                    if json.load(existing).get('status') in ('succeeded','failed'):continue
            except FileNotFoundError:pass
            try:
                job=read_job(path)
                profiles=json.loads(Path('/var/lib/controldeck/accounts.json').read_text())
                if not any(a['email']==job['requestedBy'] and a['role']=='admin' and a.get('enabled',True) and a.get('ssoType','google')=='google' for a in profiles):
                    raise ValueError('Administrator no longer allowed')
                write_result(descriptors[1],path.name,{'id':path.stem,'status':'running','message':'Termix installeren en met ControlDeck koppelen…'})
                info=INSTALLER.stat()
                if info.st_uid!=0 or info.st_mode & 0o022 or INSTALLER.is_symlink(): raise ValueError('Unsafe installer')
                # Installation output stays out of the browser (may include identities).
                with open('/var/log/controldeck-install.log','w') as log:
                    os.chmod(log.name,0o600)
                    subprocess.run(['/bin/bash',str(INSTALLER)],stdout=log,stderr=subprocess.STDOUT,timeout=480,check=True)
                result={'id':path.stem,'status':'succeeded','message':'Termix is geïnstalleerd en gekoppeld. Je kunt Terminal openen.'}
            except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError):
                result={'id':path.stem,'status':'failed','message':'De installatie is niet afgerond. De beheerder kan het installatielog op de host controleren.'}
            write_result(descriptors[1],path.name,result)
        write_result(descriptors[0],'worker.json',{'updatedAt':time.time()})
    finally:
        for descriptor in descriptors:os.close(descriptor)
        lock.close()


if __name__=='__main__':main()
