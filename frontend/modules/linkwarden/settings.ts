export function collectionSetting(value: string): number | null {
  if(value === "") return null;
  if(!/^[1-9][0-9]{0,9}$/.test(value)) throw new Error("Kies een geldige collectie.");
  return Number(value);
}
