import {offerLink,safeEmbed,widgetDate,type WidgetData} from "../../lib/service-widgets";
export function ServiceCards({data}:{data:WidgetData}) {
  if(data.embedUrl){
    const url=safeEmbed(data.embedUrl);
    return <div className="cd-ha-dashboard"><a href={url} target="_blank" rel="noopener noreferrer">Dashboard openen ↗</a><p>Home Assistant gebruikt zijn eigen aanmelding. Wordt het dashboard niet geladen, open het dan apart.</p><iframe src={url} title={data.title||"Home Assistant-dashboard"} sandbox="allow-scripts allow-same-origin allow-forms allow-popups" referrerPolicy="no-referrer" loading="lazy"/></div>;
  }
  return <>
    {data.stale&&<p role="status" className="cd-widget-warning">Deze gegevens zijn verouderd.</p>}
    {data.stats.length>0&&<dl className="cd-widget-stats">{data.stats.map((stat,i)=><div key={i}><dt>{stat.label}</dt><dd>{stat.value}</dd></div>)}</dl>}
    {data.pending&&<p role="status">Nog geen statistieken aangeleverd.</p>}
    {!data.pending&&data.items.length===0&&data.stats.length===0&&<p>Geen items op dit moment.</p>}
    <ul className="cd-widget-items">{data.items.map((item,i)=><li key={`${item.id}-${i}`}><div><strong>{item.url?<a href={offerLink(item.url)} target="_blank" rel="noopener noreferrer">{item.title} ↗</a>:item.title}</strong>{item.priceCents!==undefined&&<span>{item.priceCents===null?"Prijs niet vermeld":(item.priceCents/100).toLocaleString("nl-NL",{style:"currency",currency:item.currency||"EUR"})}</span>}{item.subtitle&&<span>{item.subtitle}</span>}{item.date&&<time dateTime={item.date}>{widgetDate(item.date,item.allDay)}</time>}</div>{item.status&&<span className="cd-widget-badge">{item.status}</span>}{item.progress!==undefined&&<div className="cd-widget-progress"><progress max={100} value={item.progress} aria-label={`Voortgang ${item.title}`}/><span>{item.progress.toLocaleString("nl-NL",{maximumFractionDigits:1})}%</span></div>}</li>)}</ul>
    {data.truncated&&<p>De eerste 50 items worden getoond. Open de toepassing voor het volledige overzicht.</p>}
    {data.updatedAt!==null&&<p className="cd-widget-time">Bron bijgewerkt: {new Date(data.updatedAt*1000).toLocaleTimeString("nl-NL")}</p>}
  </>;
}
