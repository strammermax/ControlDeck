import json
from types import SimpleNamespace
import pytest
import requests
from backend.app import create_app
from backend.auth import database
from backend.homepage_integrations import integration_url, validate_integration, integration_summary

ROW={'type':'seerr','name':'Seerr','group':'Media','url':'https://seerr.example.test','authMode':'apiKey','apiKey':'private-test-key'}
COUNTS={'total':12,'pending':2,'available':10}
H={'X-CSRF-Token':'csrf'}

@pytest.fixture
def setup(tmp_path,monkeypatch):
    accounts=tmp_path/'accounts.json'
    accounts.write_text(json.dumps([{'email':'admin@example.test','role':'admin'},{'email':'user@example.test','role':'user','modules':['bookmarks']},{'email':'other@example.test','role':'user','modules':['terminal']}]))
    app=create_app(data_dir=tmp_path/'data',accounts_path=accounts);app.config['TESTING']=True
    monkeypatch.setattr('backend.homepage_integrations.requests.request',lambda *a,**k:SimpleNamespace(status_code=200,json=lambda:COUNTS))
    def client(email='admin@example.test',application=app):
        c=application.test_client()
        if email:
            with c.session_transaction() as session:session['identity']={'email':email,'sub':email};session['csrf']='csrf'
        return c
    return client,tmp_path,app,accounts

@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_integration_validation(case):
    if case=='normaal':assert validate_integration(ROW)[1]['apiKey']=='private-test-key'
    elif case=='boundary':
        result,secret=validate_integration({**ROW,'name':'n'*300,'group':'g'*200,'apiKey':'k'*4096,'appUrl':'https://open.example.test/','showApp':False})
        assert result['appUrl']=='https://open.example.test';assert not result['showApp'];assert len(secret['apiKey'])==4096
    else:
        for patch in [{'type':'fake'},{'authMode':'password'},{'name':''},{'group':'g'*201},{'apiKey':''},{'showApp':'yes'},{'apiKey':'x\nsecret'}]:
            with pytest.raises(ValueError):validate_integration({**ROW,**patch})
        with pytest.raises(ValueError):validate_integration(None)

@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_integration_url(case):
    if case=='normaal':assert integration_url('http://linkwarden.home:5055/')=='http://linkwarden.home:5055'
    elif case=='boundary':assert integration_url('https://example.test/custom/path/')=='https://example.test/custom/path'
    else:
        for value in ['https://user:secret@example.test','https://example.test?key=secret','file:///etc/passwd','https://example.test:99999','https://example.test/../secret','https://example.test/#token',None,'https://example.test/ space']:
            with pytest.raises(ValueError):integration_url(value)

@pytest.mark.parametrize('provider',['seerr','jellyfin'])
@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_integration_adapter(provider,case,monkeypatch):
    payload=COUNTS if provider=='seerr' else {'MovieCount':4,'SeriesCount':2,'EpisodeCount':8}
    if case=='boundary':payload={key:0 for key in payload}
    if case=='faal':payload={**payload,next(iter(payload)):True}
    calls=[]
    def respond(method,url,**kwargs):
        calls.append((method,url,kwargs));return SimpleNamespace(status_code=200,json=lambda:payload)
    monkeypatch.setattr('backend.homepage_integrations.requests.request',respond)
    record,secret=validate_integration({**ROW,'type':provider})
    if case=='faal':
        with pytest.raises(ValueError):integration_summary(record,secret)
    else:
        result=integration_summary(record,secret);assert result[0]['value']==next(iter(payload.values()))
        assert calls[0][0]=='GET';assert calls[0][2]['allow_redirects'] is False;assert calls[0][2]['timeout']==10
        assert 'private-test-key' not in calls[0][1]
        assert set(result[0])=={'label','value'}

@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_jellyfin_password_auth(case,monkeypatch):
    calls=[]
    def respond(method,url,**kwargs):
        calls.append((method,url,kwargs))
        if method=='POST':return SimpleNamespace(status_code=200,json=lambda:({'AccessToken':'ephemeral-token','User':{'Id':'abc123'}} if case!='faal' else {'AccessToken':''}))
        return SimpleNamespace(status_code=200,json=lambda:{'MovieCount':0 if case=='boundary' else 4,'SeriesCount':2,'EpisodeCount':8})
    monkeypatch.setattr('backend.homepage_integrations.requests.request',respond)
    record,secret=validate_integration({**ROW,'type':'jellyfin','authMode':'password','username':'jellyuser','password':'test-password'})
    if case=='faal':
        with pytest.raises(ValueError):integration_summary(record,secret)
        assert len(calls)==1
    else:
        assert integration_summary(record,secret)[0]['value']==(0 if case=='boundary' else 4)
        assert calls[0][2]['json']=={'Username':'jellyuser','Pw':'test-password'}
        assert calls[1][1].endswith('/Items/Counts?userId=abc123')
        assert 'ephemeral-token' in calls[1][2]['headers']['Authorization']
        assert 'test-password' not in str(calls[1])

@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_integrations_create_private_and_restart(setup,case):
    clients,tmp,app,accounts=setup;c=clients()
    if case=='boundary':assert c.get('/api/homepage/integrations').json=={'integrations':[]};return
    if case=='faal':assert c.post('/api/homepage/integrations',json={**ROW,'apiKey':''},headers=H).status_code==400;return
    result=c.post('/api/homepage/integrations',json=ROW,headers=H);assert result.status_code==201
    assert 'private-test-key' not in str(result.json);assert 'apiKey' not in result.json['integration']
    with database(tmp/'data/users.sqlite3') as db:encrypted=db.execute('SELECT credentials FROM homepage_integrations').fetchone()[0]
    assert 'private-test-key' not in encrypted
    other=create_app(data_dir=tmp/'data',accounts_path=accounts)
    assert clients(application=other).get('/api/homepage/integrations/1/status').status_code==200
    assert clients('user@example.test').get('/api/homepage/integrations').json['integrations'][0]['name']=='Seerr'

@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_integrations_update_delete(setup,case):
    clients,tmp,app,accounts=setup;c=clients();c.post('/api/homepage/integrations',json=ROW,headers=H)
    if case=='normaal':assert c.put('/api/homepage/integrations/1',json={**ROW,'name':'New'},headers=H).json['integration']['name']=='New'
    elif case=='boundary':
        assert c.delete('/api/homepage/integrations/1',headers=H).status_code==200
        assert c.get('/api/homepage/integrations/1/status').status_code==404
    else:
        assert c.put('/api/homepage/integrations/1',json={**ROW,'apiKey':''},headers=H).status_code==400
        assert c.delete('/api/homepage/integrations/999',headers=H).status_code==404
        assert c.get('/api/homepage/integrations').json['integrations'][0]['name']=='Seerr'

@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_integrations_authorization(setup,case):
    clients,tmp,app,accounts=setup
    if case=='normaal':assert clients('user@example.test').get('/api/homepage/integrations/catalog').status_code==200
    elif case=='boundary':
        assert clients().post('/api/homepage/integrations',json=ROW).status_code==403
        for method,path in [('post','/api/homepage/integrations'),('put','/api/homepage/integrations/1'),('delete','/api/homepage/integrations/1')]:
            assert getattr(clients('user@example.test'),method)(path,json=ROW,headers=H).status_code==403
    else:
        for suffix in ['', '/catalog','/1/status']:
            assert clients(None).get('/api/homepage/integrations'+suffix).status_code==401
            assert clients('other@example.test').get('/api/homepage/integrations'+suffix).status_code==403

@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_integrations_upstream_errors_never_save(setup,monkeypatch,case):
    clients,tmp,app,accounts=setup;c=clients()
    def respond(*a,**k):
        if case=='faal':raise requests.Timeout('private-test-key')
        return SimpleNamespace(status_code=401 if case=='normaal' else 302,json=lambda:COUNTS)
    monkeypatch.setattr('backend.homepage_integrations.requests.request',respond)
    result=c.post('/api/homepage/integrations',json=ROW,headers=H)
    assert result.status_code==400;assert 'private-test-key' not in str(result.json)
    assert c.get('/api/homepage/integrations').json['integrations']==[]

@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_integrations_status_and_corrupt_secret(setup,monkeypatch,case):
    clients,tmp,app,accounts=setup;c=clients();c.post('/api/homepage/integrations',json=ROW,headers=H)
    if case=='normaal':assert c.get('/api/homepage/integrations/1/status').json['summary'][0]['value']==12
    elif case=='boundary':
        monkeypatch.setattr('backend.homepage_integrations.requests.request',lambda *a,**k:SimpleNamespace(status_code=403,json=lambda:COUNTS))
        assert c.get('/api/homepage/integrations/1/status').status_code==502
    else:
        with database(tmp/'data/users.sqlite3') as db:db.execute("UPDATE homepage_integrations SET credentials='broken'")
        result=c.get('/api/homepage/integrations/1/status');assert result.status_code==503;assert 'broken' not in str(result.json)


def test_integrations_limit_and_concurrent_writes(setup):
    from concurrent.futures import ThreadPoolExecutor
    clients,tmp,app,accounts=setup
    with ThreadPoolExecutor(max_workers=4) as pool:assert list(pool.map(lambda n:clients().post('/api/homepage/integrations',json={**ROW,'name':str(n)},headers=H).status_code,range(12)))==[201]*12
    with database(tmp/'data/users.sqlite3') as db:
        for _ in range(38):db.execute('INSERT INTO homepage_integrations(metadata,credentials) VALUES (?,?)',(json.dumps(ROW),'unused'))
    assert clients().post('/api/homepage/integrations',json=ROW,headers=H).status_code==400


def test_homepage_integration_regression_catalog_endpoint_collision(setup):
    """A generic catalog endpoint name collided with installations and stopped app startup."""
    clients,tmp,app,accounts=setup
    assert clients().get("/api/homepage/integrations/catalog").status_code==200
    assert "catalog" in app.view_functions
    assert "homepage_integration_catalog" in app.view_functions
@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_integration_existing_homepage_link(setup,case):
    clients,tmp,app,accounts=setup;c=clients()
    row={'name':'Jellyfin link','url':'https://open.example.test/web/index.html#/home','collection':'Media'}
    c.post('/api/homepage/links',json=row,headers=H)
    if case=='normaal':
        r=c.post('/api/homepage/integrations',json={**ROW,'linkId':1},headers=H);assert r.status_code==201
        assert r.json['integration']['linkId']==1;assert r.json['integration']['appUrl']==row['url']
        assert len(c.get('/api/homepage/links').json['links'])==1
        assert c.delete('/api/homepage/integrations/1',headers=H).status_code==200
        assert len(c.get('/api/homepage/links').json['links'])==1
    elif case=='boundary':
        assert c.post('/api/homepage/integrations',json={**ROW,'linkId':1},headers=H).status_code==201
        assert c.post('/api/homepage/integrations',json={**ROW,'linkId':1},headers=H).status_code==400
        assert c.put('/api/homepage/integrations/1',json={**ROW,'linkId':1},headers=H).status_code==200
    else:
        for link_id in [True,0,-1,'1',999]:
            assert c.post('/api/homepage/integrations',json={**ROW,'linkId':link_id},headers=H).status_code==400
        assert c.get('/api/homepage/integrations').json['integrations']==[]

@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_integration_application_deep_link(setup,case):
    clients,tmp,app,accounts=setup
    if case=='normaal':assert validate_integration({**ROW,'appUrl':'https://open.example.test/web/index.html#/dashboard'})[0]['appUrl'].endswith('#/dashboard')
    elif case=='boundary':assert validate_integration({**ROW,'appUrl':''})[0]['appUrl']==ROW['url']
    else:
        for value in ['javascript:alert(1)','https://user:secret@example.test','https://example.test?apiKey=secret']:
            with pytest.raises(ValueError):validate_integration({**ROW,'appUrl':value})


def test_integration_regression_deep_link_retains_fragment_and_normalizes_root_slash():
    """Opening URLs need hash routes; normal root URLs must keep the previous canonical form."""
    assert validate_integration({**ROW,"appUrl":"https://example.test/"})[0]["appUrl"]=="https://example.test"
    assert validate_integration({**ROW,"appUrl":"https://example.test/web/index.html#/"})[0]["appUrl"].endswith("#/")
