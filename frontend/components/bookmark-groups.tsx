"use client";
import {bookmarkGrid,groupBookmarks,moveBookmark,orderedLinks,personalGroups,type BookmarkTile} from '../lib/bookmark-layout';
import {groupCells,withGroupCells,type PageLayoutCell} from '../lib/page-layouts';
import {AppIcon} from './app-icon';
import {EditableGrid} from './editable-grid';
import type {Bookmark} from '../lib/linkwarden';

type Link=Bookmark&{icon?:string};
/** Optional personal layout: `cells` are complete (see bookmarkLayout); `grid` false keeps reading order only (search). */
export type BookmarkLayoutProps={cells:PageLayoutCell[];editing:boolean;grid:boolean;onChange:(cells:PageLayoutCell[])=>void};

function Tile({item,onEdit}:{item:BookmarkTile;onEdit?:(item:Link)=>void}) {
  const explicit=(item as Link).icon;
  return <><a className="bookmark-tile" href={item.url} target="_blank" rel="noopener noreferrer">
    <span className="bookmark-monogram" aria-hidden="true"><AppIcon key={`${item.url}:${explicit}`} name={item.name} url={item.url} icon={explicit} size={32}/></span>
    <span className="bookmark-tile-content"><strong>{item.name}</strong><span className="bookmark-tile-description">{item.description||item.hostname}</span>{item.description&&<span className="bookmark-host">{item.hostname}</span>}{item.tags.length>0&&<span className="bookmark-tile-tags">{item.tags.map((tag,index)=><span key={`${tag}-${index}`}>{tag}</span>)}</span>}</span>
    <span className="bookmark-open" aria-hidden="true">↗</span><span className="sr-only"> (opent in een nieuw tabblad)</span>
  </a>{onEdit&&<button className="bookmark-edit" aria-label={`Aanpassen: ${item.name}`} onClick={()=>onEdit(item)}>Aanpassen</button>}</>;
}

export function BookmarkGroups({links,onEdit,layout}:{links:Link[];onEdit?:(item:Link)=>void;layout?:BookmarkLayoutProps}) {
  // With a personal layout, links may be shown in another group; empty groups only show while editing (drop targets).
  const groups=(layout?personalGroups(groupBookmarks(links),layout.cells):groupBookmarks(links)).filter(group=>group.links.length||layout?.editing);
  return <div className="bookmark-columns" data-layout={layout?.grid?'grid':undefined}>{groups.map(group=>{
    const byId=new Map(group.links.map(item=>[String(item.id),item]));
    return <section className="bookmark-group" key={group.name} aria-label={group.name}>
      <h3 className="bookmark-group-title">{group.name}<span>{group.links.length}</span></h3>
      {layout?.grid
        ?<EditableGrid className="bookmark-grid" cells={groupCells(layout.cells,group.name)} bounds={bookmarkGrid} editing={layout.editing} rowHeight={76} gap={10} group={group.name}
          onTransfer={(id,target,at)=>{try{layout.onChange(moveBookmark(layout.cells,id,target,at));}catch{/* Keep the layout when the group is full. */}}}
          onChange={next=>layout.onChange(withGroupCells(layout.cells,group.name,next))} label={id=>byId.get(id)?.name??'Link'}
          render={id=>{const item=byId.get(id);return item?<div className="bookmark-cell"><Tile item={item} onEdit={layout.editing?undefined:onEdit}/></div>:null;}}/>
        :<ul>{(layout?orderedLinks(group,layout.cells):group.links).map(item=><li key={item.id}><Tile item={item} onEdit={onEdit}/></li>)}</ul>}
    </section>;})}</div>;
}
