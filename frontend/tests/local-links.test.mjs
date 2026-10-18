import test from 'node:test';
import assert from 'node:assert/strict';
import {isHomeLink,hideLocalLinks,applyLocalLinkVisibility} from '../lib/local-links.ts';

test('local link policy normal: all home hosts, ports, case, trailing dot and default on',()=>{
 for(const url of ['https://plex.home/','http://Plex.HOME:32400/web','//ha.home/path','https://home./'])assert.equal(isHomeLink(url,'https://deck.example.test'),true);
 assert.equal(hideLocalLinks(undefined,false),true);assert.equal(hideLocalLinks(true,true),false);assert.equal(hideLocalLinks(false,false),false);
});
test('local link policy boundary and failure: internal navigation, public lookalikes and unknown network',()=>{
 for(const url of ['#settings','/api/settings','https://service.home.example.test','https://example.test/path/service.home','https://example.test/?url=service.home','javascript:alert(1)','http://[bad',''])assert.equal(isHomeLink(url,'https://deck.example.test'),false);
 assert.equal(hideLocalLinks(undefined,undefined),true);
});
test('site-wide visibility hides rows and standalone anchors without changing URLs, and restores them',()=>{
 const attrs=new Map();
 const row={setAttribute:k=>attrs.set(k,''),removeAttribute:k=>attrs.delete(k)};
 const local={tagName:'A',getAttribute:()=> 'https://ha.home/',closest:selector=>selector==='li'?row:null};
 const publicLink={tagName:'A',getAttribute:()=> 'https://public.example.test/',closest:()=>null,setAttribute:()=>assert.fail('public link hidden')};
 const root={baseURI:'https://deck.example.test',querySelectorAll:selector=>selector==='[data-cd-local-link-hidden]'?(attrs.size?[row]:[]):[local,publicLink]};
 applyLocalLinkVisibility(root,true);assert.equal(attrs.has('data-cd-local-link-hidden'),true);assert.equal(local.getAttribute('href'),'https://ha.home/');
 applyLocalLinkVisibility(root,false);assert.equal(attrs.size,0);
});
