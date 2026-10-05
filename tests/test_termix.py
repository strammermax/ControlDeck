import copy
import json
from unittest.mock import Mock

import pytest
import requests
from backend.app import create_app
from backend.configuration import DEFAULT_PATH, ConfigurationError, load_config, validate


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTROLDECK_BASE_URL", "https://control.example.test")
    config = load_config(DEFAULT_PATH)
    next(p for p in config['providers'] if p['id'] == 'termix').update(enabled=True, url='https://control.example.test/termix/')
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(config))
    accounts = tmp_path / 'accounts.json'
    accounts.write_text(json.dumps([{'email':'admin@example.test','role':'admin'}, {'email':'user@example.test','role':'user'}]))
    app = create_app(config_path=path, data_dir=tmp_path/'data', accounts_path=accounts)
    app.config['TESTING'] = True
    client = app.test_client()
    with client.session_transaction() as session:
        session['identity'] = {'email':'user@example.test','sub':'user'}
        session['csrf'] = 'csrf'
    return client, path, accounts


def response(status=200, **data):
    return Mock(status_code=status, json=lambda:data, cookies={'jwt':'signed'})


@pytest.mark.parametrize('case', ['normaal', 'boundary', 'faal'])
def test_terminal_configuration(case):
    config = load_config(DEFAULT_PATH)
    module = next(m for m in config['modules'] if m['id']=='terminal')
    if case == 'normaal':
        assert module['view'] == 'terminal'
    elif case == 'boundary':
        # Disabled provider keeps the module visible with setup guidance.
        assert any(m['id']=='terminal' for m in validate(config)['modules'])
    else:
        next(m for m in config['modules'] if m['id']=='dashboard')['view']='terminal'
        with pytest.raises(ConfigurationError): validate(config)


@pytest.mark.parametrize('case', ['normaal', 'boundary', 'faal'])
def test_provision_and_login(bridge, monkeypatch, case):
    client, _, _ = bridge
    mocked = Mock(side_effect=[response(201 if case=='normaal' else 409), response(success=True, username='user@example.test', is_admin=False)])
    monkeypatch.setattr('backend.termix.requests.post', mocked)
    if case == 'faal': mocked.side_effect=requests.ConnectionError()
    result=client.post('/api/termix/session', headers={'X-CSRF-Token':'csrf'})
    assert result.status_code == (503 if case=='faal' else 200)
    if case != 'faal':
        assert result.json == {'ready':True}
        assert 'signed' not in result.get_data(as_text=True)
        assert 'Secure' in result.headers['Set-Cookie'] and 'HttpOnly' in result.headers['Set-Cookie']
        assert 'Path=/termix/' in result.headers['Set-Cookie']
        assert mocked.call_args_list[0].kwargs['json']['username']=='user@example.test'
        assert mocked.call_args_list[1].kwargs['headers']['X-Forwarded-Role']=='user'


@pytest.mark.parametrize('problem', ['anonymous','csrf','disabled','restricted','revoked'])
def test_session_cannot_bypass_control_accounts(bridge, monkeypatch, problem):
    client,path,accounts=bridge
    mocked=Mock()
    monkeypatch.setattr('backend.termix.requests.post',mocked)
    headers={'X-CSRF-Token':'csrf'}
    if problem=='anonymous':
        with client.session_transaction() as session: session.clear()
    elif problem=='csrf': headers={}
    elif problem=='disabled':
        config=json.loads(path.read_text())
        next(p for p in config['providers'] if p['id']=='termix')['enabled']=False
        path.write_text(json.dumps(config))
    else:
        data=json.loads(accounts.read_text())
        data[1].update({'modules':['dashboard']} if problem=='restricted' else {'enabled':False})
        accounts.write_text(json.dumps(data))
    assert client.post('/api/termix/session',headers=headers).status_code in (401,403)
    mocked.assert_not_called()


@pytest.mark.parametrize('case', ['normaal','boundary','faal'])
def test_gateway_bootstrap(bridge,case):
    client,_,_=bridge
    headers={'X-Original-URI':'/termix/','X-Forwarded-Username':'forged@example.test','X-Forwarded-Role':'admin'}
    if case=='boundary': headers['X-Original-URI']='/termix/assets/app.js'
    elif case=='faal': headers['X-Original-URI']='/other/'
    result=client.get('/api/termix/authorize',headers=headers)
    assert result.status_code == (403 if case=='faal' else 204)
    if case!='faal':
        assert result.headers['X-Forwarded-Username']=='user@example.test'
        assert result.headers['X-Forwarded-Role']=='user'


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_api_and_websocket_identity(bridge,monkeypatch,case):
    client,_,_=bridge
    mocked=Mock(return_value=response(username='user@example.test' if case!='faal' else 'admin@example.test',is_admin=False))
    monkeypatch.setattr('backend.termix.requests.get',mocked)
    headers={'X-Original-URI':'/termix/users/me','Authorization':'Bearer signed'}
    if case=='boundary': headers={'X-Original-URI':'/termix/plugin-ws/terminal/session','Sec-WebSocket-Protocol':'termix.jwt.signed','X-Original-Upgrade':'websocket','Origin':'https://control.example.test'}
    assert client.get('/api/termix/authorize',headers=headers).status_code == (403 if case=='faal' else 204)


@pytest.mark.parametrize('problem',['missing','expired','role','outage','malformed','cross-origin'])
def test_private_termix_requests_fail_closed(bridge,monkeypatch,problem):
    client,_,_=bridge
    mocked=Mock(return_value=response(username='user@example.test',is_admin=False))
    monkeypatch.setattr('backend.termix.requests.get',mocked)
    headers={'X-Original-URI':'/termix/users/me','Authorization':'Bearer signed'}
    expected=403
    if problem=='missing': headers.pop('Authorization'); expected=401
    elif problem=='expired': mocked.return_value=response(401)
    elif problem=='role': mocked.return_value=response(username='user@example.test',is_admin=True)
    elif problem=='outage': mocked.side_effect=requests.Timeout();expected=503
    elif problem=='malformed': mocked.return_value=Mock(status_code=200,json=lambda:[])
    elif problem=='cross-origin': headers.update({'X-Original-Method':'POST','Origin':'https://attacker.example.test'})
    assert client.get('/api/termix/authorize',headers=headers).status_code==expected


@pytest.mark.parametrize('case',['normaal','boundary','faal'])
def test_write_origin(bridge,case):
    client,_,_=bridge
    headers={'X-Original-URI':'/termix/users/proxy-login','X-Original-Method':'POST','Origin':'https://control.example.test'}
    if case=='boundary': headers['X-Original-Method']='OPTIONS';headers.pop('Origin')
    elif case=='faal': headers.pop('Origin')
    assert client.get('/api/termix/authorize',headers=headers).status_code==(403 if case=='faal' else 204)
