/** Only the two house themes cross into the same-origin embedded app. */
export function workfarmUrl(theme:string,embedded=true):string {
  if(theme!=='dark'&&theme!=='light')throw new Error('Ongeldig kleurthema.');
  return `/workfarm/?theme=${theme}${embedded?'&embedded=1':''}`;
}
