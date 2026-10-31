"""Native bookmark login: normal use, boundaries, rejection and owner isolation."""
import json
from unittest.mock import Mock

import pytest
import requests

from backend.app import create_app
from backend.vault import VaultError

H = {'X-CSRF-Token': 'csrf'}
LINK = {'name': 'App', 'url': 'https://app.example.test', 'collection': 'Apps'}
SSO = {'method': 'sso', 'loginUrl': LINK['url'] + '/apps/user_oidc/login/1'}
KASM = {'method': 'kasm', 'apiKey': 'synthetic-key', 'apiSecret': 'synthetic-secret',
        'userId': '12345678-1234-4234-8234-123456789abc'}
TICKET = LINK['url'] + '/#/connect/login/dash/user/temporary-ticket'


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr('backend.auth.Vault.from_env', classmethod(lambda cls: None))
    accounts = tmp_path / 'accounts.json'
    accounts.write_text(json.dumps([{'email': 'admin@example.test', 'role': 'admin'},
        {'email': 'alice@example.test', 'role': 'user', 'modules': ['bookmarks']},
        {'email': 'bob@example.test', 'role': 'user', 'modules': ['bookmarks']},
        {'email': 'denied@example.test', 'role': 'user', 'modules': ['terminal']}]))
    data = tmp_path / 'data'
    app = create_app(data_dir=data, accounts_path=accounts)
    app.config['TESTING'] = True
    values = {}
    vault = Mock()
    vault.read.side_effect = lambda: dict(values)
    vault.write.side_effect = lambda key, value: values.__setitem__(key, value)
    app.extensions['controldeck_vault'] = vault
    post = Mock(return_value=Mock(status_code=200, json=Mock(return_value={'url': TICKET})))
    monkeypatch.setattr('backend.modules.kasm.requests.post', post)

    def client(email='alice@example.test'):
        c = app.test_client()
        if email:
            with c.session_transaction() as session:
                session['identity'] = {'email': email, 'sub': email}
                session['csrf'] = 'csrf'
        return c
    assert client('admin@example.test').post('/api/homepage/links', json=LINK, headers=H).status_code == 201
    return client, app, vault, values, post, data


def test_normal_sso_personal_vault_save_launch_and_clear(env):
    clients, _, vault, values, post, _ = env
    c = clients()
    assert c.put('/api/bookmark-logins/1', json=SSO, headers=H).json == {'saved': True, 'method': 'sso'}
    assert len(values) == 1 and next(iter(values)).startswith('CONTROLDECK_BOOKMARK_LOGIN_')
    assert c.get('/api/bookmark-logins').json == {'available': True, 'logins': [{'linkId': 1, 'method': 'sso'}]}
    r = c.post('/api/bookmark-logins/1/launch', json={}, headers=H)
    assert r.json == {'url': SSO['loginUrl']}
    assert r.headers['Cache-Control'] == 'no-store' and r.headers['Referrer-Policy'] == 'no-referrer'
    post.assert_not_called()
    assert c.delete('/api/bookmark-logins/1', headers=H).status_code == 200
    assert list(values.values()) == ['']
    assert c.get('/api/bookmark-logins').json['logins'] == []
    assert c.post('/api/bookmark-logins/1/launch', json={}, headers=H).status_code == 409


def test_normal_kasm_uses_owner_account_and_never_returns_stored_credentials(env):
    clients, _, _, values, post, data = env
    c = clients()
    response = c.put('/api/bookmark-logins/1', json=KASM, headers=H)
    assert response.status_code == 200
    assert 'synthetic' not in response.get_data(as_text=True)
    assert c.post('/api/bookmark-logins/1/launch', json={}, headers=H).json == {'url': TICKET}
    assert post.call_args.kwargs['json']['target_user'] == {'user_id': KASM['userId']}
    assert post.call_args.kwargs['allow_redirects'] is False
    assert KASM['apiSecret'].encode() not in (data / 'users.sqlite3').read_bytes()
    assert KASM['apiSecret'] not in c.get('/api/bookmark-logins').get_data(as_text=True)


def test_boundary_empty_settings_unknown_link_and_maximum_secret(env):
    clients, _, _, _, _, _ = env
    c = clients()
    assert c.get('/api/bookmark-logins').json['logins'] == []
    assert c.put('/api/bookmark-logins/999', json=SSO, headers=H).status_code == 404
    assert c.put('/api/bookmark-logins/1', json={**KASM, 'apiSecret': 'x' * 4096}, headers=H).status_code == 200
    assert c.put('/api/bookmark-logins/1', json={**KASM, 'apiSecret': 'x' * 4097}, headers=H).status_code == 400
    assert c.put('/api/bookmark-logins/1', json={**SSO, 'loginUrl': LINK['url'] + '/sso?provider=google&realm=google'}, headers=H).status_code == 200


@pytest.mark.parametrize('payload', [None, [], {'method': 'password', 'username': 'x', 'password': 'synthetic'},
    {'method': 'apiKey', 'apiKey': 'synthetic'}, {**SSO, 'email': 'bob@example.test'},
    {**SSO, 'loginUrl': 'https://other.example.test/login'},
    {**SSO, 'loginUrl': LINK['url'] + '/login?code=synthetic'},
    {**SSO, 'loginUrl': LINK['url'] + '/login#synthetic'},
    {**SSO, 'loginUrl': LINK['url'] + '/%0alogin'},
    {**KASM, 'userId': 'not-a-uuid'}, {**KASM, 'apiSecret': ''}, {**KASM, 'apiKey': 'x\ny'}])
def test_failure_unsupported_or_unsafe_configuration_never_written(env, payload):
    clients, _, vault, _, post, _ = env
    assert clients().put('/api/bookmark-logins/1', json=payload, headers=H).status_code == 400
    vault.write.assert_not_called()
    post.assert_not_called()


def test_authentication_module_authorization_csrf_and_owner_isolation(env):
    clients, _, vault, values, post, _ = env
    assert clients(None).get('/api/bookmark-logins').status_code == 401
    assert clients('denied@example.test').get('/api/bookmark-logins').status_code == 403
    assert clients().put('/api/bookmark-logins/1', json=SSO).status_code == 403
    assert clients().put('/api/bookmark-logins/1', json=SSO, headers=H).status_code == 200
    reads = vault.read.call_count
    assert clients('bob@example.test').get('/api/bookmark-logins').json['logins'] == []
    assert clients('bob@example.test').post('/api/bookmark-logins/1/launch', json={}, headers=H).status_code == 409
    assert vault.read.call_count == reads
    assert clients('bob@example.test').delete('/api/bookmark-logins/1', headers=H).status_code == 200
    assert clients().post('/api/bookmark-logins/1/launch', json={}, headers=H).status_code == 200
    assert len(values) == 2
    post.assert_not_called()


def test_failure_bookmark_url_change_cannot_retarget_saved_credentials(env):
    """Regression: changed shared URL must never send a saved API key to a new host."""
    clients, _, vault, _, post, _ = env
    clients().put('/api/bookmark-logins/1', json=KASM, headers=H)
    clients('admin@example.test').put('/api/homepage/links/1', json={**LINK, 'url': 'https://other.example.test'}, headers=H)
    assert clients().get('/api/bookmark-logins').json['logins'] == []
    assert clients().post('/api/bookmark-logins/1/launch', json={}, headers=H).status_code == 409
    vault.read.assert_not_called()
    post.assert_not_called()


def test_failure_vault_unavailable_corrupt_record_and_missing_secret(env):
    clients, app, vault, _, _, _ = env
    c = clients()
    c.put('/api/bookmark-logins/1', json=SSO, headers=H)
    for values in ({}, {'unrelated': 'synthetic-private'}):
        vault.read.side_effect = None
        vault.read.return_value = values
        assert c.post('/api/bookmark-logins/1/launch', json={}, headers=H).status_code == 503
    vault.write.side_effect = VaultError('synthetic-private')
    r = c.put('/api/bookmark-logins/1', json=SSO, headers=H)
    assert r.status_code == 503 and 'synthetic-private' not in r.get_data(as_text=True)
    app.extensions['controldeck_vault'] = None
    assert c.get('/api/bookmark-logins').json['available'] is False
    assert c.put('/api/bookmark-logins/1', json=SSO, headers=H).status_code == 503


@pytest.mark.parametrize('body', [None, [], {'url': 'https://other.example.test'}, {'userId': KASM['userId']}])
def test_failure_launch_payload_cannot_select_target_or_identity(env, body):
    clients, _, vault, _, post, _ = env
    assert clients().post('/api/bookmark-logins/1/launch', json=body, headers=H).status_code == 400
    vault.read.assert_not_called()
    post.assert_not_called()


def test_failure_upstream_refusal_redirect_and_private_error_are_not_reflected(env):
    clients, _, _, _, post, _ = env
    c = clients()
    c.put('/api/bookmark-logins/1', json=KASM, headers=H)
    for result in ({'url': 'https://other.example.test/#/connect/login/dash/a/b'}, {'error_message': 'synthetic-private'}):
        post.return_value.json.return_value = result
        r = c.post('/api/bookmark-logins/1/launch', json={}, headers=H)
        assert r.status_code == 400 and 'synthetic-private' not in r.get_data(as_text=True)
    post.side_effect = requests.Timeout('synthetic-private')
    r = c.post('/api/bookmark-logins/1/launch', json={}, headers=H)
    assert r.status_code == 503 and 'synthetic-private' not in r.get_data(as_text=True)


def test_internal_kasm_api_overrides_require_administrator(env):
    clients, _, vault, _, _, _ = env
    assert clients().put('/api/bookmark-logins/1', json={**KASM, 'apiUrl': 'https://internal.example.test'}, headers=H).status_code == 403
    vault.write.assert_not_called()
    assert clients('admin@example.test').put('/api/bookmark-logins/1', json={**KASM, 'apiUrl': 'https://internal.example.test'}, headers=H).status_code == 200


def test_failure_http_bookmark_never_stores_login_secrets(env):
    clients, _, vault, _, _, _ = env
    clients('admin@example.test').put('/api/homepage/links/1', json={**LINK, 'url': 'http://192.0.2.1:8000'}, headers=H)
    assert clients().put('/api/bookmark-logins/1', json=KASM, headers=H).status_code == 400
    vault.write.assert_not_called()


def test_failure_account_revocation_blocks_saved_login(env):
    clients, _, vault, _, post, data = env
    c = clients()
    c.put('/api/bookmark-logins/1', json=KASM, headers=H)
    accounts_path = data.parent / 'accounts.json'
    accounts = json.loads(accounts_path.read_text())
    accounts[1]['enabled'] = False
    accounts_path.write_text(json.dumps(accounts))
    assert c.post('/api/bookmark-logins/1/launch', json={}, headers=H).status_code in (401, 403)
    vault.read.assert_not_called()
    post.assert_not_called()
