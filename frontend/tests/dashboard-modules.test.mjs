import test from 'node:test';
import assert from 'node:assert/strict';
import {moduleOptions, collectionSetting} from '../lib/dashboard-modules.ts';
import {dashboardItemView, placeItem} from '../lib/dashboards.ts';

test('module catalog normal: Linkwarden uses Bookmarks permission and reusable feature identity',()=>{
 const module=moduleOptions(['dashboard','bookmarks'])[0];assert.equal(module.id,'linkwarden');assert.equal(module.permission,'bookmarks');
 const item={id:'links',type:'module',moduleId:module.id,settings:{collectionId:12},sectionId:'apps',x:0,y:0,width:module.width,height:module.height};
 const board={id:'work',revision:1,title:'Werk',sections:[{id:'apps',title:'Apps',lane:'main',collapsed:false}],items:[]};
 assert.equal(placeItem(board,item).items[0].settings.collectionId,12);
 assert.equal(dashboardItemView(item,[]).title,'Linkwarden');
});
test('module catalog boundary and authorization: no Bookmarks access means no Linkwarden option',()=>{
 assert.deepEqual(moduleOptions([]),[]);assert.deepEqual(moduleOptions(['dashboard']),[]);
 assert.equal(moduleOptions(['bookmarks','bookmarks']).length,1);
});
test('module settings normal and boundary: all collections and maximum ID',()=>{
 assert.equal(collectionSetting(''),null);assert.equal(collectionSetting('1'),1);assert.equal(collectionSetting('9999999999'),9999999999);
});
test('module settings failure: reject malformed, negative, decimal and excessive collection IDs',()=>{
 for(const value of ['0','-1','1.5','01','10000000000','token=x'])assert.throws(()=>collectionSetting(value));
});
