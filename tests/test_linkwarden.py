import importlib.util
import json
import time
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests
from backend.app import create_app
from backend import linkwarden

TOKEN='personal.token.'+'a'*24
H={'X-CSRF-Token':'csrf'}


@pytest.fixture
def env(tmp_path,monkeypatch):
    accounts=tmp_path/'accounts.json'
    accounts.write_text(json.dumps([{'email':'admin@example.test','role':'admin'}, {'email':'user@example.test','role':'user','modules':['bookmarks']}, {'email':'other@example.test','role':'user','modules':['terminal']}]))
    app=create_app(data_dir=tmp_path/'data',accounts_path=accounts)
    app.config['TESTING']=True
    calls=[]
    responses={'/users/me':{'response':{'email':'user@example.test'}},'/collections':{'response':[{'id':1,'name':'Personal'}]},'/search':{'data':{'links':[{'id':1,'url':'https://example.com','name':'Example','tags':[{'name':'tag'}],'collection':{'name':'Personal'}}],'nextCursor':None}},'/links':{'response':{'id':2}}}
    def fake(method,url,**kwargs):
        calls.append((method,url,kwargs))
        endpoint=url.split('/api/v1')[1]
        response=responses[endpoint]
        if isinstance(response,Exception):raise response
        return Mock(status_code=200,json=Mock(return_value=response))
    monkeypatch.setattr(linkwarden.requests,'request',fake)
    monkeypatch.setattr('backend.installations.requests.get',Mock(return_value=Mock(status_code=200)))
    def client(email='user@example.test'):
        c=app.test_client()
        with c.session_transaction() as session:
            session['identity']={'email':email,'sub':email};session['csrf']='csrf'
        return c
    admin=client('admin@example.test')
    assert admin.put('/api/linkwarden/connection',json={'url':'https://linkwarden.example.com'},headers=H).status_code==200
    return client,responses,calls,tmp_path/'data'


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_url(case):
    if case=='normaal':assert linkwarden.base_url('https://links.example.com/dashboard')=='https://links.example.com'
    elif case=='boundary':assert linkwarden.base_url('http://192.168.1.119:3000/')=='http://192.168.1.119:3000'
    else:
        for value in (None,'http://example.com','https://u:p@example.com','https://example.com?secret=a','https://example.com/api','https://example.com:99999','https://exa mple.com'):
            with pytest.raises(ValueError):linkwarden.base_url(value)


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_token_identity_and_storage(env,case):
    client,responses,calls,data=env;c=client()
    if case=='boundary':responses['/users/me']['response']['email']='USER@EXAMPLE.TEST'
    elif case=='faal':responses['/users/me']['response']['email']='admin@example.test'
    result=c.put('/api/linkwarden/token',json={'token':TOKEN},headers=H)
    assert result.status_code==(502 if case=='faal' else 200)
    assert TOKEN not in result.get_data(as_text=True)
    files=list((data/'linkwarden/users').glob('*.json'))
    assert bool(files)==(case!='faal')
    if files:assert json.loads(files[0].read_text())['token']==TOKEN
    if calls:assert calls[0][2]['allow_redirects'] is False


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_rows(case):
    data={'data':{'links':[{'id':1,'url':'https://example.com','name':'Example','tags':[{'name':'tag'}]}],'nextCursor':2}}
    if case=='normaal':assert linkwarden.link_rows(data)['links'][0]['tags']==['tag']
    elif case=='boundary':
        data['data']['links'].extend([{'id':2,'url':'javascript:alert(1)'},{'url':'https://example.com'}]);data['data']['nextCursor']=True
        assert len(linkwarden.link_rows(data)['links'])==1
        assert linkwarden.link_rows(data)['nextCursor'] is None
    else:
        for value in ({},{'data':{'links':'broken'}}):
            with pytest.raises(linkwarden.LinkwardenError):linkwarden.link_rows(value)


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_bookmarks_search_and_collections(env,case):
    client,responses,calls,data=env;c=client();c.put('/api/linkwarden/token',json={'token':TOKEN},headers=H)
    if case=='normaal':
        assert c.get('/api/linkwarden/bookmarks?query=tag&collection=1').json['links'][0]['name']=='Example'
        assert c.get('/api/linkwarden/collections').json['collections'][0]['id']==1
        assert next(call for call in calls if call[1].endswith('/search'))[2]['params']['collectionId']=='1'
    elif case=='boundary':
        responses['/search']={'data':{'links':[],'nextCursor':None}};responses['/collections']={'response':[]}
        assert c.get('/api/linkwarden/bookmarks?query='+('a'*200)+'&cursor=1').json['links']==[]
        assert c.get('/api/linkwarden/collections').json['collections']==[]
    else:
        assert c.get('/api/linkwarden/bookmarks?cursor=-1').status_code==400
        responses['/search']=requests.Timeout('private secret')
        result=c.get('/api/linkwarden/bookmarks');assert result.status_code==502
        assert 'private secret' not in result.get_data(as_text=True)
        responses['/collections']={'response':'invalid'}
        assert c.get('/api/linkwarden/collections').status_code==502


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_create_bookmark(env,case):
    client,responses,calls,data=env;c=client();c.put('/api/linkwarden/token',json={'token':TOKEN},headers=H)
    body={'url':'https://example.com','name':'Example','collectionId':1}
    if case=='boundary':body['name']='';body['collectionId']=999999
    elif case=='faal':body['url']='javascript:alert(1)'
    result=c.post('/api/linkwarden/bookmarks',json=body,headers=H)
    assert result.status_code==(400 if case=='faal' else 201)
    if case!='faal':assert calls[-1][2]['json']['collection']['id']==body['collectionId']


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_connection_and_token_lifecycle(env,case):
    client,responses,calls,data=env;c=client();admin=client('admin@example.test')
    if case=='normaal':
        c.put('/api/linkwarden/token',json={'token':TOKEN},headers=H)
        assert c.get('/api/linkwarden/token').json['connected'] is True
        assert c.delete('/api/linkwarden/token',headers=H).json['connected'] is False
        assert admin.get('/api/linkwarden/connection').json['connected'] is True
    elif case=='boundary':
        c.put('/api/linkwarden/token',json={'token':TOKEN},headers=H)
        admin.put('/api/linkwarden/connection',json={'url':'https://other.example.com'},headers=H)
        assert c.get('/api/linkwarden/token').json['connected'] is False
        assert c.get('/api/linkwarden/bookmarks').status_code==502
        admin.delete('/api/linkwarden/connection',headers=H)
        assert admin.get('/api/linkwarden/connection').json['connected'] is False
    else:
        assert c.get('/api/linkwarden/connection').status_code==403
        assert c.put('/api/linkwarden/token',json={'token':TOKEN}).status_code==403
        assert client('other@example.test').get('/api/linkwarden/token').status_code==403
        assert admin.put('/api/linkwarden/connection',json={'url':'bad'},headers=H).status_code==400


def test_anonymous_and_revoked_token(env):
    client,responses,calls,data=env;c=client();c.put('/api/linkwarden/token',json={'token':TOKEN},headers=H)
    with c.session_transaction() as session:session.clear()
    assert c.get('/api/linkwarden/bookmarks').status_code==401
    responses['/users/me']['response']['email']='different@example.test'
    assert client().get('/api/linkwarden/bookmarks').status_code==502
    assert not any(call[1].endswith('/search') for call in calls)


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_installation_plan_and_worker_allowlist(env,case):
    client,responses,calls,data=env;c=client('admin@example.test');root=data/'installations'
    (root/'queue').mkdir(parents=True);(root/'results').mkdir();(root/'worker.json').write_text(json.dumps({'updatedAt':time.time(),'version':3}))
    body={'module':'linkwarden','method':'docker','target':'local'}
    spec=importlib.util.spec_from_file_location('lw_worker',Path(__file__).resolve().parent.parent/'scripts/install-worker.py')
    worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    job={**body,'id':'a'*32,'requestedBy':'admin@example.test','createdAt':time.time()}
    if case=='normaal':
        (root/'linkwarden-ready.json').write_text('{}')
        assert c.post('/api/installations/plan',json=body,headers=H).json['canInstall'] is True
        assert c.post('/api/installations/jobs',json=body,headers=H).status_code==202
        assert worker.validate_job(job,'a'*32,time.time())['module']=='linkwarden'
    elif case=='boundary':
        assert c.post('/api/installations/plan',json=body,headers=H).json['canInstall'] is False
        body.update(method='lxc',target='proxmox')
        assert c.post('/api/installations/plan',json=body,headers=H).json['installer']=='proxmox-helper-scripts'
        assert c.post('/api/installations/jobs',json=body,headers=H).status_code==409
    else:
        assert c.post('/api/installations/jobs',json=body,headers=H).status_code==409
        with pytest.raises(ValueError):worker.validate_job({**job,'action':'uninstall','keepData':False},'a'*32,time.time())


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_upstream_and_private_write(tmp_path,monkeypatch,case):
    path=tmp_path/'new/token.json';linkwarden.save_private(path,{'token':TOKEN})
    if case=='normaal':
        assert json.loads(path.read_text())['token']==TOKEN
        monkeypatch.setattr(linkwarden.requests,'request',Mock(return_value=Mock(status_code=200,json=Mock(return_value={'response':{}}))))
        assert linkwarden.upstream('https://example.com',TOKEN,'/users/me')=={'response':{}}
    elif case=='boundary':
        linkwarden.save_private(path,{'token':'replacement'});assert json.loads(path.read_text())['token']=='replacement'
        assert list(path.parent.iterdir())==[path]
        monkeypatch.setattr(linkwarden.requests,'request',Mock(return_value=Mock(status_code=302)))
        with pytest.raises(linkwarden.LinkwardenError):linkwarden.upstream('https://example.com',TOKEN,'/users/me')
    else:
        monkeypatch.setattr(linkwarden.requests,'request',Mock(return_value=Mock(status_code=401)))
        with pytest.raises(linkwarden.LinkwardenError):linkwarden.upstream('https://example.com',TOKEN,'/users/me')
        monkeypatch.setattr(linkwarden.requests,'request',Mock(return_value=Mock(status_code=200,json=Mock(return_value=[]))))
        with pytest.raises(linkwarden.LinkwardenError):linkwarden.upstream('https://example.com',TOKEN,'/users/me')

@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_explicit_local_account_mapping(env,case):
    client,responses,calls,data=env
    responses['/users/me']={'response':{'id':7,'email':None}}
    if case=='normaal':linkwarden.verify_identity('https://example.com',TOKEN,'admin@example.test',7)
    elif case=='boundary':
        with pytest.raises(linkwarden.LinkwardenError):linkwarden.verify_identity('https://example.com',TOKEN,'admin@example.test',8)
        responses['/users/me']['response']['email']='different@example.test'
        with pytest.raises(linkwarden.LinkwardenError):linkwarden.verify_identity('https://example.com',TOKEN,'admin@example.test',7)
    else:
        for invalid in (None,True,'7',-1):
            with pytest.raises(linkwarden.LinkwardenError):linkwarden.verify_identity('https://example.com',TOKEN,'admin@example.test',invalid)

@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_installation_nodes(env,monkeypatch,case):
    client,responses,calls,data=env
    path=data/'proxmox/connection.json';path.parent.mkdir(parents=True);path.write_text('{}')
    nodes=[{'type':'node','name':'pve-amd','online':1},{'type':'node','name':'pve-nas','online':0}]
    if case=='boundary':nodes=[]
    elif case=='faal':nodes={'invalid':'nodes'}
    monkeypatch.setattr(linkwarden,'ProxmoxClient',Mock(return_value=Mock(get=Mock(return_value=nodes))))
    result=client('admin@example.test').get('/api/linkwarden/installation-nodes')
    assert result.status_code==(503 if case=='faal' else 200)
    if case=='normaal':assert result.json['nodes']==[{'name':'pve-amd','online':True},{'name':'pve-nas','online':False}]
    elif case=='boundary':assert result.json['nodes']==[]
    assert client().get('/api/linkwarden/installation-nodes').status_code==403

@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_ip_address_input(case):
    if case=='normaal':assert linkwarden.base_url('192.168.1.119')=='http://192.168.1.119:3000'
    elif case=='boundary':
        assert linkwarden.base_url('192.168.1.119:8080')=='http://192.168.1.119:8080'
        assert linkwarden.base_url('[fd00::119]:3000')=='http://[fd00::119]:3000'
    else:
        for value in ('8.8.8.8','192.168.1.119:99999','192.168.1.119?token=secret','192.168.1.119;echo'):
            with pytest.raises(ValueError):linkwarden.base_url(value)
