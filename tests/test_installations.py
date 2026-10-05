import importlib.util
import json
import time
import os
from pathlib import Path
from unittest.mock import Mock

import pytest
from backend.app import create_app
from backend.installations import validate_install_request

SELECTION={'module':'termix','method':'docker','target':'local'}


@pytest.fixture
def wizard(tmp_path,monkeypatch):
    accounts=tmp_path/'accounts.json'
    accounts.write_text(json.dumps([{'email':'admin@example.test','role':'admin'},{'email':'user@example.test','role':'user'}]))
    root=tmp_path/'data/installations'
    (root/'queue').mkdir(parents=True)
    (root/'results').mkdir()
    (root/'worker.json').write_text(json.dumps({'updatedAt':time.time()}))
    monkeypatch.setattr('backend.installations.requests.get',Mock(return_value=Mock(status_code=200)))
    app=create_app(data_dir=tmp_path/'data',accounts_path=accounts)
    app.config['TESTING']=True
    client=app.test_client()
    with client.session_transaction() as session:
        session['identity']={'email':'admin@example.test','sub':'admin'}
        session['csrf']='csrf'
    return client,root


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_install_selection(case):
    if case=='normaal':assert validate_install_request(SELECTION)=={**SELECTION,'action':'install'}
    elif case=='boundary':assert validate_install_request({'module':'termix','method':'lxc','target':'proxmox'})['method']=='lxc'
    else:
        for invalid in (None,{}, {**SELECTION,'module':'shell'}, {**SELECTION,'command':'rm'}, {**SELECTION,'target':'proxmox'}):
            with pytest.raises(ValueError):validate_install_request(invalid)


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_catalog_and_status(wizard,case):
    client,root=wizard
    if case=='boundary':(root/'worker.json').unlink()
    elif case=='faal':(root/'worker.json').write_text('broken')
    result=client.get('/api/installations')
    assert result.status_code==200
    assert result.json['modules'][0]['id']=='termix'
    assert result.json['status']['workerAvailable']==(case=='normaal')


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_preflight_plan(wizard,case):
    client,root=wizard
    selected=SELECTION
    if case=='boundary':selected={'module':'termix','method':'lxc','target':'proxmox'}
    elif case=='faal':(root/'worker.json').write_text(json.dumps({'updatedAt':time.time()-100}))
    result=client.post('/api/installations/plan',json=selected,headers={'X-CSRF-Token':'csrf'})
    assert result.status_code==200
    assert result.json['canInstall']==(case=='normaal')
    if case=='boundary':
        assert result.json['installer']=='proxmox-helper-scripts'
        assert result.json['resources']['memoryMb']==4096
        assert result.json['blockers']


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_queue_installation(wizard,case):
    client,root=wizard
    if case=='faal':(root/'worker.json').unlink()
    result=client.post('/api/installations/jobs',json=SELECTION,headers={'X-CSRF-Token':'csrf'})
    assert result.status_code==(503 if case=='faal' else 202)
    if case=='faal':assert list((root/'queue').iterdir())==[];return
    job_id=result.json['id']
    stored=json.loads((root/'queue'/f'{job_id}.json').read_text())
    assert stored['requestedBy']=='admin@example.test' and stored['module']=='termix'
    assert client.get('/api/installations/jobs/'+job_id).json['status']=='queued'
    if case=='boundary':
        (root/'results'/f'{job_id}.json').write_text(json.dumps({'id':job_id,'status':'running'}))
        assert client.post('/api/installations/jobs',json=SELECTION,headers={'X-CSRF-Token':'csrf'}).status_code==409


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_job_status(wizard,case):
    client,root=wizard
    job_id='a'*32
    if case=='normaal':(root/'results'/f'{job_id}.json').write_text(json.dumps({'id':job_id,'status':'succeeded'}))
    elif case=='boundary':(root/'queue'/f'{job_id}.json').write_text('{}')
    else:job_id='../accounts'
    result=client.get('/api/installations/jobs/'+job_id)
    assert result.status_code==(404 if case=='faal' else 200)
    if case=='normaal':assert result.json['status']=='succeeded'


@pytest.mark.parametrize('actor',['anonymous','user','csrf'])
def test_installations_require_admin_and_csrf(wizard,actor):
    client,root=wizard
    with client.session_transaction() as session:
        if actor=='anonymous':session.clear()
        elif actor=='user':session['identity']={'email':'user@example.test','sub':'user'}
    headers={} if actor=='csrf' else {'X-CSRF-Token':'csrf'}
    for path in ('/plan','/jobs'):
        assert client.post('/api/installations'+path,json=SELECTION,headers=headers).status_code in (401,403)
    assert list((root/'queue').iterdir())==[]
    if actor!='csrf':assert client.get('/api/installations').status_code in (401,403)


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_root_worker_job_allowlist(case):
    spec=importlib.util.spec_from_file_location('worker',Path(__file__).resolve().parent.parent/'scripts/install-worker.py')
    worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    value={**SELECTION,'id':'a'*32,'requestedBy':'admin@example.test','createdAt':1000}
    if case=='normaal':assert worker.validate_job(value,'a'*32,1010)==value
    elif case=='boundary':assert worker.validate_job(value,'a'*32,1000)==value
    else:
        for invalid,now in (({**value,'command':'shell'},1010),({**value,'module':'shell'},1010),(value,1600),(value,999)):
            with pytest.raises(ValueError):worker.validate_job(invalid,'a'*32,now)


def test_lxc_cannot_enqueue_without_proxmox(wizard):
    client,root=wizard
    assert client.post('/api/installations/jobs',json={'module':'termix','method':'lxc','target':'proxmox'},headers={'X-CSRF-Token':'csrf'}).status_code==409
    assert list((root/'queue').iterdir())==[]


@pytest.mark.skipif(os.name!='posix',reason='Privileged worker file protections run on Linux in CI')
@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_worker_reads_bounded_regular_job_files(tmp_path,case):
    spec=importlib.util.spec_from_file_location('worker',Path(__file__).resolve().parent.parent/'scripts/install-worker.py')
    worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    job_id='a'*32
    value={**SELECTION,'id':job_id,'requestedBy':'admin@example.test','createdAt':time.time()}
    serialized=json.dumps(value)
    path=tmp_path/(job_id+'.json')
    if case=='normaal':path.write_text(serialized);assert worker.read_job(path)['module']=='termix'
    elif case=='boundary':path.write_text(serialized+' '*(16384-len(serialized)));assert worker.read_job(path)['id']==job_id
    else:
        path.write_text(serialized+' '*(16385-len(serialized)))
        with pytest.raises(ValueError):worker.read_job(path)
        path.unlink();source=tmp_path/'source.json';source.write_text(serialized);path.symlink_to(source)
        with pytest.raises(OSError):worker.read_job(path)


UNINSTALL={**SELECTION,'action':'uninstall','keepData':True}


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_uninstall_selection(case):
    if case=='normaal':assert validate_install_request(UNINSTALL)==UNINSTALL
    elif case=='boundary':assert validate_install_request({**SELECTION,'action':'uninstall'})['keepData'] is True
    else:
        for invalid in ({**UNINSTALL,'keepData':'no'},{**SELECTION,'keepData':False},{**SELECTION,'action':'delete'},
                        {'module':'termix','method':'lxc','target':'proxmox','action':'uninstall'},{**UNINSTALL,'command':'rm -rf /'}):
            with pytest.raises(ValueError):validate_install_request(invalid)


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_catalog_marks_installed_modules(wizard,tmp_path,case):
    client,root=wizard
    data=root.parent
    if case=='normaal':
        termix=client.get('/api/installations').json
        assert next(m for m in termix['modules'] if m['id']=='termix')['installed'] is False  # test config: provider disabled
    elif case=='boundary':
        (data/'proxmox').mkdir();(data/'proxmox/connection.json').write_text('{}')
        modules={m['id']:m['installed'] for m in client.get('/api/installations').json['modules']}
        assert modules['proxmox'] is True and modules['proxmenux'] is False
    else:
        assert all(module['installed'] is False for module in client.get('/api/installations').json['modules'])


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_uninstall_plan_and_queue(wizard,monkeypatch,case):
    client,root=wizard
    import backend.installations as installations
    monkeypatch.setattr(installations,'load_config',lambda path:{'providers':[{'id':'termix','type':'termix','enabled':case!='faal'}]})
    selection=UNINSTALL if case!='boundary' else {**UNINSTALL,'keepData':False}
    plan=client.post('/api/installations/plan',json=selection,headers={'X-CSRF-Token':'csrf'}).json
    if case=='faal':
        assert plan['canInstall'] is False and 'niet geïnstalleerd' in plan['blockers'][0]
        assert client.post('/api/installations/jobs',json=selection,headers={'X-CSRF-Token':'csrf'}).status_code==409
        assert list((root/'queue').iterdir())==[]
        return
    assert plan['canInstall'] is True and plan['preservesData'] is (case=='normaal')
    assert ('Verwijder alle Termix-gegevens' in plan['steps'][-1])==(case=='boundary')
    job=client.post('/api/installations/jobs',json=selection,headers={'X-CSRF-Token':'csrf'}).json
    stored=json.loads((root/'queue'/f"{job['id']}.json").read_text())
    assert stored['action']=='uninstall' and stored['keepData'] is (case=='normaal')


def test_install_job_keeps_shape_for_older_worker(wizard):
    client,root=wizard
    job=client.post('/api/installations/jobs',json=SELECTION,headers={'X-CSRF-Token':'csrf'}).json
    stored=json.loads((root/'queue'/f"{job['id']}.json").read_text())
    assert set(stored)=={'id','module','method','target','requestedBy','createdAt'}


def test_uninstall_requires_admin_and_csrf(wizard,tmp_path):
    client,root=wizard
    assert client.post('/api/installations/jobs',json=UNINSTALL).status_code==403
    with client.session_transaction() as session:
        session['identity']={'email':'user@example.test','sub':'user'}
    assert client.post('/api/installations/jobs',json=UNINSTALL,headers={'X-CSRF-Token':'csrf'}).status_code==403
    assert list((root/'queue').iterdir())==[]


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_worker_accepts_uninstall_jobs(case):
    spec=importlib.util.spec_from_file_location('worker',Path(__file__).resolve().parent.parent/'scripts/install-worker.py')
    worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    value={**SELECTION,'id':'a'*32,'requestedBy':'admin@example.test','createdAt':1000}
    if case=='normaal':assert worker.validate_job({**value,'action':'uninstall','keepData':True},'a'*32,1001)['action']=='uninstall'
    elif case=='boundary':assert worker.validate_job({**value,'action':'uninstall','keepData':False},'a'*32,1599)['keepData'] is False
    else:
        for invalid in ({**value,'action':'uninstall'},{**value,'action':'install','keepData':True},{**value,'action':'uninstall','keepData':'false'},{**value,'keepData':True}):
            with pytest.raises(ValueError):worker.validate_job(invalid,'a'*32,1001)
