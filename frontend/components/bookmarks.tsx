"use client";
import {HomepageLinks} from './homepage-links';
import {LinkwardenModule} from '../modules/linkwarden/view';

/** The full module page composes the same features used on personal dashboards. */
export function Bookmarks({csrfToken,isAdmin=false}:{csrfToken:string;isAdmin?:boolean}) {
  return <section className="bookmarks-panel"><HomepageLinks csrfToken={csrfToken} isAdmin={isAdmin}/><LinkwardenModule csrfToken={csrfToken}/></section>;
}
