"""A cosmetic network preference must not trust arbitrary forwarded headers."""
from types import SimpleNamespace
import pytest
from backend.network_context import connection_context, networks
from test_auth import app, login


def req(peer, **headers):
    return SimpleNamespace(remote_addr=peer, headers=headers)


@pytest.mark.parametrize('peer,local',[('192.168.1.20',True),('10.2.3.4',True),('172.16.2.3',True),('8.8.8.8',False),('::ffff:192.168.1.20',True),('fd00::2',True)])
def test_network_direct_normal_and_boundaries(monkeypatch,peer,local):
    monkeypatch.delenv('CONTROLDECK_LOCAL_NETWORKS',raising=False)
    monkeypatch.delenv('CONTROLDECK_TRUSTED_EDGE_PROXIES',raising=False)
    assert connection_context(req(peer))['isLocal'] is local


def test_network_proxy_public_home_ip_and_external_client(monkeypatch):
    monkeypatch.setenv('CONTROLDECK_TRUSTED_EDGE_PROXIES','192.168.20.127/32')
    monkeypatch.setenv('CONTROLDECK_LOCAL_NETWORKS','192.168.0.0/16,203.0.113.4/32')
    assert connection_context(req('127.0.0.1',**{'X-ControlDeck-Peer-IP':'192.168.20.127','CF-Connecting-IP':'203.0.113.4'}))['isLocal']
    assert connection_context(req('127.0.0.1',**{'X-ControlDeck-Peer-IP':'192.168.20.127','CF-Connecting-IP':'8.8.8.8'}))['scope']=='external'
    assert connection_context(req('127.0.0.1',**{'X-ControlDeck-Peer-IP':'192.168.20.127'}))['scope']=='unknown'


def test_network_failure_fails_closed_and_untrusted_header_cannot_claim_lan(monkeypatch):
    monkeypatch.delenv('CONTROLDECK_TRUSTED_EDGE_PROXIES',raising=False)
    assert not connection_context(req('8.8.8.8',**{'CF-Connecting-IP':'192.168.1.1','X-ControlDeck-Peer-IP':'192.168.1.1'}))['isLocal']
    assert connection_context(req('127.0.0.1'))['scope']=='unknown'
    assert connection_context(req('bad-ip'))['scope']=='unknown'
    assert networks('0.0.0.0/0')==[] and networks('invalid')==[]
    monkeypatch.setenv('CONTROLDECK_LOCAL_NETWORKS','invalid')
    assert connection_context(req('192.168.1.1'))['scope']=='unknown'


def test_preference_normal_boundary_failure_and_owner_isolation(app):
    one,two=app.test_client(),app.test_client()
    login(app,one);login(app,two,'user@example.test','second')
    headers={'X-CSRF-Token':'valid-csrf'}
    assert 'hideHomeLinksOutsideLocal' not in one.get('/api/preferences').json
    for value in [False,True]:
        assert one.put('/api/preferences',headers=headers,json={'hideHomeLinksOutsideLocal':value}).status_code==200
        assert one.get('/api/preferences').json['hideHomeLinksOutsideLocal'] is value
    assert 'hideHomeLinksOutsideLocal' not in two.get('/api/preferences').json
    for value in [None,1,'false',[]]:
        assert one.put('/api/preferences',headers=headers,json={'hideHomeLinksOutsideLocal':value}).status_code==400
    assert one.put('/api/preferences',json={'hideHomeLinksOutsideLocal':False}).status_code==403
    assert app.test_client().get('/api/preferences').status_code==401
    assert one.get('/api/session',environ_overrides={'REMOTE_ADDR':'8.8.8.8'}).json['network']=={'isLocal':False,'scope':'external'}
