import assert from 'node:assert/strict';
import { test } from 'node:test';
import { homepageDialogTitle } from '../lib/homepage-dialog.ts';

test('homepageDialogTitle / normaal: each step of the add-link flow has its own title', () => {
  assert.equal(homepageDialogTitle({picking:true, integrationType:null, editing:null}),'Link toevoegen: kies een toepassing');
  assert.equal(homepageDialogTitle({picking:false, integrationType:null, editing:null}),'Link toevoegen');
  assert.equal(homepageDialogTitle({picking:false, integrationType:'sonarr', editing:null}),'Link met API-koppeling instellen');
});
test('homepageDialogTitle / boundary: link id 0 still counts as editing', () => {
  assert.equal(homepageDialogTitle({picking:false, integrationType:null, editing:0}),'Link aanpassen');
});
test('homepageDialogTitle / faal: editing wins over stale picker or integration state', () => {
  assert.equal(homepageDialogTitle({picking:true, integrationType:'sonarr', editing:5}),'Link aanpassen');
});
