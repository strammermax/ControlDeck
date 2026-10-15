import {metricLabels,type Metric,type MetricRow} from "./metrics";
import {meter} from "../../lib/proxmox";

/** Present real readings without inventing chart history or a power maximum. */
export function SystemCards({metric,rows}:{metric:Metric;rows:MetricRow[]}) {
  const percent=metric==="cpu"||metric==="memory";
  const unit=percent?"%":metric==="temperature"?"°C":"W";
  return <div className="cd-system-grid">{rows.map(row=>{
    const level=row.value===null?"unknown":percent?meter(row.value).level:"normal";
    return <article key={row.name} className="cd-system-card" data-level={level}>
      <header><span className="cd-system-name">{row.name}</span><span className="cd-system-state">{row.stale?"Verouderd":row.unavailable?"Niet beschikbaar":row.value===null?"Onbekend":"Actueel"}</span></header>
      <div className="cd-system-reading">
        {percent&&<svg className="cd-system-ring" viewBox="0 0 120 120" aria-hidden="true"><circle className="cd-system-ring-track" cx="60" cy="60" r="50"/><circle className="cd-system-ring-value" cx="60" cy="60" r="50" pathLength="100" strokeDasharray={`${row.value??0} 100`}/></svg>}
        <div><strong>{row.value===null?"—":row.value.toLocaleString("nl-NL",{maximumFractionDigits:1})}<small>{row.value!==null?unit:""}</small></strong><span>{metricLabels[metric]}</span></div>
      </div>
      {percent&&row.value!==null&&level!=="normal"&&<p className="cd-system-level">{level==="critical"?"Zeer hoog gebruik":"Hoog gebruik"}</p>}
      {row.detail&&<p>{row.detail}</p>}
      {metric==="power"&&<p>Alleen CPU · geen totaalverbruik</p>}
    </article>;
  })}</div>;
}
