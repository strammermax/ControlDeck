/** Title of the "Link toevoegen" popup for each step of the flow. */
export function homepageDialogTitle(state: { picking: boolean; integrationType: string | null; editing: number | null }): string {
  if (state.editing !== null) return "Link aanpassen";
  if (state.picking) return "Link toevoegen: kies een toepassing";
  if (state.integrationType) return "Link met API-koppeling instellen";
  return "Link toevoegen";
}
