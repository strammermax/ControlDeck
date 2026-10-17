"""Object artwork and links respect source ACLs and never expose API credentials."""
import copy
from unittest.mock import Mock
import pytest
from backend.widgets.presentation import display_url, present, match_artwork
from backend.widgets.transport import Transport, ProviderError
from backend.widgets.adapters import statistics_payload
from test_service_widgets import setup, widget_env, source, FIXTURES, TOKEN


def test_display_urls_normal_boundary_and_rejection():
    assert display_url("https://images.example.test/a.jpg", image=True)
    assert display_url("http://app.example.test/item/1")
    for value in [None, 2, "javascript:alert(1)", "https://u:p@host/a", "https://host/a?apiKey=secret", "https://host/a?X-Plex-Token=secret", "https://host/a\n", "https://host:bad/a", "https://host/" + "a" * 2048]:
        assert display_url(value) is None
    assert display_url("http://images.example.test/a.jpg", image=True) is None


def test_present_normal_links_images_and_no_mutation():
    s=source("prefect");s["url"]="https://prefect.example.test/api"
    body={"items":[{"id":"run-1","title":"Run","subtitle":"","status":"Completed"}]}
    value=present(body,s,"prefect")
    assert value["items"][0]["url"]=="https://prefect.example.test/runs/flow-run/run-1"
    assert "url" not in body["items"][0]
    assert present({"items":[]},s,"prefect")["items"]==[]
    s=source("plex")
    value=present({"items":[{"id":"one","imageId":"123","imageUrl":"https://host/?token=secret"}]},s,"plex")
    assert value["items"][0]["imageUrl"]=="/api/widget-images/plex/123"
    assert "imageId" not in value["items"][0]
    assert TOKEN not in str(value)
    s=source("nextcloud-calendar")
    s["url"]="https://cloud.example.test/sub/remote.php/dav/calendars/user/personal"
    assert present(body,s,"calendar")["items"][0]["url"]=="https://cloud.example.test/sub/index.php/apps/calendar"


def test_presentation_boundary_unsafe_art_and_missing_provider_destination():
    s=source("statistics")
    s.pop("url")
    row={"id":"1","imageUrl":"http://host/art.jpg","url":"javascript:alert(1)"}
    value=present({"items":[row]},s,"offers")
    assert "imageUrl" not in value["items"][0] and "url" not in value["items"][0]


def test_artwork_normal_boundary_and_ambiguous_match_rejected():
    art={"title":"Poor Things","imageUrl":"https://images.example.test/poster.jpg","url":"https://seerr.example.test/movie/42"}
    rows=[{"title":"Poor.Things.2023.1080p"}]
    assert match_artwork(rows,[art])[0]["imageUrl"]==art["imageUrl"]
    assert match_artwork([],[])==[]
    assert "imageUrl" not in match_artwork([{"title":"Unknown Movie"}],[art])[0]
    assert "imageUrl" not in match_artwork([{"title":"Poor Things 2023"}],[art,{**art,"url":"https://seerr.example.test/movie/43"}])[0]
    assert "imageUrl" not in match_artwork([{"title":"It 2023"}],[{**art,"title":"It"}])[0]


def test_source_images_authorization_and_fixed_plex_path(widget_env,monkeypatch):
    clients,values,calls,replies,_=widget_env
    image=Mock(return_value=(b"synthetic-image", "image/png"))
    monkeypatch.setattr(Transport,"image",image)
    c=clients()
    assert clients(None).get("/api/widget-images/plex/123").status_code==401
    assert clients("other@example.test").get("/api/widget-images/plex/123").status_code==404
    assert c.get("/api/widget-images/tdarr/123").status_code==404
    assert c.get("/api/widget-images/plex/0").status_code==404
    response=c.get("/api/widget-images/plex/123")
    assert response.status_code==200 and response.content_type=="image/png"
    assert response.headers["Cache-Control"]=="no-store"
    assert image.call_args.args[0]=="/library/metadata/123/thumb"
    values["plex"]["users"]=["other@example.test"]
    assert c.get("/api/widget-images/plex/123").status_code==404
    values["plex"]["users"]=["user@example.test"]
    image.side_effect=ProviderError("private upstream error")
    assert c.get("/api/widget-images/plex/123").status_code==503
    assert b"private" not in c.get("/api/widget-images/plex/123").data


def test_download_artwork_does_not_bypass_seerr_access(widget_env):
    clients,values,calls,replies,_=widget_env
    replies.update({(kind,path):copy.deepcopy(value) for kind in ["qbittorrent","seerr"] for path,value in FIXTURES[kind].items()})
    replies[("qbittorrent","/api/v2/torrents/info")][0]["name"]="Poor.Things.2023"
    replies[("seerr","/api/v1/movie/42")]={"title":"Poor Things","posterPath":"/poster.jpg"}
    response=clients().get('/api/widgets/downloads/qbittorrent')
    assert response.json['items'][0]['imageUrl']=='https://image.tmdb.org/t/p/w185/poster.jpg'
    values['seerr']['users']=['other@example.test']
    assert 'imageUrl' not in clients().get('/api/widgets/downloads/qbittorrent').json['items'][0]


@pytest.mark.parametrize('case',['normal','empty','invalid','oversized','redirect'])
def test_image_transport_raster_limits_and_failures(monkeypatch,case):
    response=Mock(status_code=302 if case=='redirect' else 200,headers={'Content-Type':'image/svg+xml' if case=='invalid' else 'image/png'})
    response.iter_content.return_value=[b'\x89PNG\r\n\x1a\n' + b'0'*20] if case not in ['empty','oversized'] else ([] if case=='empty' else [b'0'*(1024*1024+1)])
    response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
    t=Transport(source('plex'));mock=Mock(return_value=response);monkeypatch.setattr(t.session,'request',mock)
    try:
        if case=='normal':
            data,mime=t.image('/library/metadata/1/thumb',{'X-Plex-Token':TOKEN});assert mime=='image/png' and data.startswith(b'\x89PNG')
            assert mock.call_args.kwargs['verify'] is True and mock.call_args.kwargs['allow_redirects'] is False
        else:
            with pytest.raises(ProviderError):t.image('/library/metadata/1/thumb',{})
    finally:t.close()


def test_seerr_object_links_and_posters_use_public_metadata_only(widget_env):
    clients,values,calls,replies,_=widget_env
    replies.update({('seerr',path):copy.deepcopy(value) for path,value in FIXTURES['seerr'].items()})
    replies[('seerr','/api/v1/movie/42')]={'title':'Poor Things','posterPath':'/safe.jpg'}
    values['seerr']['webUrl']='https://requests.example.test'
    row=clients().get('/api/widgets/media-widget/seerr').json['items'][0]
    assert row['url']=='https://requests.example.test/movie/42'
    assert row['imageUrl']=='https://image.tmdb.org/t/p/w185/safe.jpg'
    assert TOKEN not in str(row)


def test_plex_deep_link_includes_server_and_images_never_include_token(widget_env):
    clients,values,calls,replies,_=widget_env
    replies[('plex','/status/sessions')]={'MediaContainer':{'machineIdentifier':'server-1','Metadata':[{'sessionKey':'1','ratingKey':'42','title':'Film','duration':100,'viewOffset':0}]}}
    row=clients().get('/api/widgets/media-widget/plex').json['items'][0]
    assert row['imageUrl']=='/api/widget-images/plex/42'
    assert '#!/server/server-1/details?key=%2Flibrary%2Fmetadata%2F42' in row['url']
    assert TOKEN not in str(row)
