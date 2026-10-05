import json
from pathlib import Path
import pytest
from backend.app import create_app
from backend.homepage import validate_homepage_link

ROW={'name':'Proxmox','url':'https://proxmox.example.test','collection':'Infra','description':'Node','icon':'proxmox.png'}
H={'X-CSRF-Token':'csrf'}

@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_native_homepage_link_validation(case):
    if case=='normaal':assert validate_homepage_link(ROW)['icon']=='proxmox.png'
    elif case=='boundary':
        value={**ROW,'name':'n'*300,'collection':'g'*200,'description':'d'*1000,'icon':''};assert validate_homepage_link(value)['name']==value['name']
    else:
        for patch in ({'url':'javascript:alert(1)'},{'url':'https://u:p@example.test'},{'url':'https://example.test?apiKey=private'},{'url':'https://example.test:99999'},{'icon':'../../secret'},{'name':''},{'collection':''},{'description':'d'*1001}):
            with pytest.raises(ValueError):validate_homepage_link({**ROW,**patch})
        with pytest.raises(ValueError):validate_homepage_link(None)

@pytest.fixture
def setup(tmp_path):
    accounts=tmp_path/'accounts.json';accounts.write_text(json.dumps([{'email':'admin@example.test','role':'admin'},{'email':'user@example.test','role':'user','modules':['bookmarks']},{'email':'other@example.test','role':'user','modules':['terminal']}]))
    app=create_app(data_dir=tmp_path/'data',accounts_path=accounts);app.config['TESTING']=True
    def client(email='admin@example.test',application=app):
        c=application.test_client()
        if email:
            with c.session_transaction() as session:session['identity']={'email':email,'sub':email};session['csrf']='csrf'
        return c
    return client,tmp_path,accounts

@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_native_homepage_read_without_upstream(setup,monkeypatch,case):
    clients,tmp,accounts=setup;c=clients()
    # Fixed module: neither Homepage nor another remote service may be required.
    monkeypatch.setattr('requests.get',lambda *a,**k:pytest.fail('Native Homepage must not fetch a server'))
    if case=='normaal':
        assert c.post('/api/homepage/links',json=ROW,headers=H).status_code==201
        assert clients('user@example.test').get('/api/homepage/links').json['links'][0]['name']=='Proxmox'
    elif case=='boundary':assert c.get('/api/homepage/links').json=={'links':[]}
    else:
        p=tmp/'data/homepage/links.json';p.parent.mkdir();p.write_text('broken')
        assert c.get('/api/homepage/links').status_code==400

@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_native_homepage_create(setup,case):
    clients,tmp,accounts=setup;c=clients()
    if case=='normaal':
        r=c.post('/api/homepage/links',json=ROW,headers=H);assert r.status_code==201;assert r.json['links'][0]['id']==1
    elif case=='boundary':
        p=tmp/'data/homepage/links.json';p.parent.mkdir();p.write_text(json.dumps([{'id':i+1,**ROW} for i in range(500)]))
        assert c.post('/api/homepage/links',json=ROW,headers=H).status_code==400;assert len(json.loads(p.read_text()))==500
    else:
        assert c.post('/api/homepage/links',json={'url':'https://example.test'},headers=H).status_code==400
        assert c.get('/api/homepage/links').json['links']==[]

@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_native_homepage_edit_delete_and_backup(setup,case):
    clients,tmp,accounts=setup;c=clients();c.post('/api/homepage/links',json=ROW,headers=H)
    if case=='normaal':
        assert c.put('/api/homepage/links/1',json={**ROW,'name':'Changed'},headers=H).json['links'][0]['name']=='Changed'
        assert json.loads((tmp/'data/homepage/links.previous.json').read_text())[0]['name']=='Proxmox'
    elif case=='boundary':
        assert c.delete('/api/homepage/links/1',headers=H).json['links']==[]
        assert json.loads((tmp/'data/homepage/links.previous.json').read_text())[0]['id']==1
    else:
        assert c.put('/api/homepage/links/1',json={**ROW,'url':'invalid'},headers=H).status_code==400
        assert c.delete('/api/homepage/links/999',headers=H).status_code==404
        assert c.get('/api/homepage/links').json['links'][0]['name']=='Proxmox'

@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_native_homepage_authorization_csrf(setup,case):
    clients,tmp,accounts=setup
    if case=='normaal':assert clients('user@example.test').get('/api/homepage/links').status_code==200
    elif case=='boundary':
        for method,path in [('post','/api/homepage/links'),('put','/api/homepage/links/1'),('delete','/api/homepage/links/1')]:
            assert getattr(clients('user@example.test'),method)(path,json=ROW,headers=H).status_code==403
        assert clients().post('/api/homepage/links',json=ROW).status_code==403
    else:
        assert clients(None).get('/api/homepage/links').status_code==401
        assert clients('other@example.test').get('/api/homepage/links').status_code==403


def test_native_homepage_regression_concurrent_workers_preserve_all_links(setup):
    """A per-process lock loses links when two workers write the same JSON; SQLite serializes both."""
    from concurrent.futures import ThreadPoolExecutor
    clients,tmp,accounts=setup
    other=create_app(data_dir=tmp/'data',accounts_path=accounts)
    def add(i):
        c=clients(application=other) if i%2 else clients()
        return c.post('/api/homepage/links',json={**ROW,'name':f'Link {i}'},headers=H).status_code
    with ThreadPoolExecutor(max_workers=4) as pool:assert list(pool.map(add,range(12)))==[201]*12
    rows=clients().get('/api/homepage/links').json['links']
    assert len(rows)==12;assert len({item['id'] for item in rows})==12
