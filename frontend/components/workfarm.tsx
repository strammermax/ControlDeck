/** Apps → Workfarm: the Prefect worker dashboard, proxied by ControlDeck under /workfarm/. */
import {EmbeddedApp} from './embedded-app';
import {workfarmUrl} from '../lib/workfarm';
export function Workfarm({theme}:{theme:'dark'|'light'}) {
  return <EmbeddedApp title="Workfarm" src={workfarmUrl(theme)} openSrc={workfarmUrl(theme,false)}/>;
}
