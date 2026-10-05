"use client";
import {useState} from 'react';
import {groupBookmarks} from '../lib/bookmark-layout';
import {bookmarkIcon} from '../lib/bookmark-icons';
import type {Bookmark} from '../lib/linkwarden';

export function BookmarkGroups({links,onEdit}:{links:(Bookmark&{icon?:string})[];onEdit?:(item:Bookmark&{icon?:string})=>void}) {
  const groups=groupBookmarks(links);
  const [failed,setFailed]=useState<Record<string,boolean>>({});
  return <div className="bookmark-columns">{groups.map(group=><section className="bookmark-group" key={group.name} aria-label={group.name}>
    <h3 className="bookmark-group-title">{group.name}<span>{group.links.length}</span></h3><ul>{group.links.map(item=>{
      const explicit=(item as Bookmark&{icon?:string}).icon;
      const icon=bookmarkIcon(item.name,item.url,explicit);
      return <li key={item.id}><a className="bookmark-tile" href={item.url} target="_blank" rel="noopener noreferrer">
        <span className="bookmark-monogram" aria-hidden="true">{icon&&!failed[icon]?<img src={icon} alt="" width={32} height={32} loading="lazy" onError={()=>setFailed(value=>({...value,[icon]:true}))}/>:item.initials}</span>
        <span className="bookmark-tile-content"><strong>{item.name}</strong><span className="bookmark-tile-description">{item.description||item.hostname}</span>{item.description&&<span className="bookmark-host">{item.hostname}</span>}{item.tags.length>0&&<span className="bookmark-tile-tags">{item.tags.map((tag,index)=><span key={`${tag}-${index}`}>{tag}</span>)}</span>}</span>
        <span className="bookmark-open" aria-hidden="true">↗</span><span className="sr-only"> (opent in een nieuw tabblad)</span>
      </a>{onEdit&&<button className="bookmark-edit" aria-label={`Aanpassen: ${item.name}`} onClick={()=>onEdit(item)}>Aanpassen</button>}</li>;
    })}</ul></section>)}</div>;
}
