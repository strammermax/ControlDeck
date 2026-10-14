"use client";
import {groupBookmarks} from '../lib/bookmark-layout';
import {AppIcon} from './app-icon';
import type {Bookmark} from '../lib/linkwarden';

export function BookmarkGroups({links,onEdit}:{links:(Bookmark&{icon?:string})[];onEdit?:(item:Bookmark&{icon?:string})=>void}) {
  const groups=groupBookmarks(links);
  return <div className="bookmark-columns">{groups.map(group=><section className="bookmark-group" key={group.name} aria-label={group.name}>
    <h3 className="bookmark-group-title">{group.name}<span>{group.links.length}</span></h3><ul>{group.links.map(item=>{
      const explicit=(item as Bookmark&{icon?:string}).icon;
      return <li key={item.id}><a className="bookmark-tile" href={item.url} target="_blank" rel="noopener noreferrer">
        <span className="bookmark-monogram" aria-hidden="true"><AppIcon key={`${item.url}:${explicit}`} name={item.name} url={item.url} icon={explicit} size={32}/></span>
        <span className="bookmark-tile-content"><strong>{item.name}</strong><span className="bookmark-tile-description">{item.description||item.hostname}</span>{item.description&&<span className="bookmark-host">{item.hostname}</span>}{item.tags.length>0&&<span className="bookmark-tile-tags">{item.tags.map((tag,index)=><span key={`${tag}-${index}`}>{tag}</span>)}</span>}</span>
        <span className="bookmark-open" aria-hidden="true">↗</span><span className="sr-only"> (opent in een nieuw tabblad)</span>
      </a>{onEdit&&<button className="bookmark-edit" aria-label={`Aanpassen: ${item.name}`} onClick={()=>onEdit(item)}>Aanpassen</button>}</li>;
    })}</ul></section>)}</div>;
}
