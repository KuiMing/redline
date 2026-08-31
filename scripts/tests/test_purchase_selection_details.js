const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('static/app.js', 'utf8');
const start = source.indexOf('function purchaseSelectionDetails(');
const end = source.indexOf('\nfunction purchaseCostText(', start);
assert.ok(start >= 0 && end > start, 'purchaseSelectionDetails source must exist');

const context = {
  selectedPurchaseIndices: new Set([1, 0]),
  playerId: 'p1',
  window: {lastGameState: null},
};
vm.createContext(context);
vm.runInContext(`${source.slice(start, end)}\nthis.purchaseSelectionDetails = purchaseSelectionDetails;`, context);

const state = {
  purchase_area: ['甲', '乙'],
  purchase_area_costs: [
    {money: 0, propaganda: 3},
    {money: 0, propaganda: 3},
  ],

  purchase_area_payments: [
    {money: 0, propaganda: 3},
    {money: 0, propaganda: 3},
  ],
  purchase_payment_policy: {
    type: 'propaganda_then_money_shortfall',
    active: true,
    eligible_cost: 'propaganda',
    allocation_scope: 'batch',
  },
  players: [{id: 'p1', resources: {money: 3, propaganda: 3}}],
};

const normalize = value => JSON.parse(JSON.stringify(value));
const flexible = context.purchaseSelectionDetails(state);
assert.deepEqual(normalize(flexible.indices), [1, 0]);
assert.deepEqual(
  normalize(flexible.cards.map(card => ({money: card.money, propaganda: card.propaganda}))),
  [{money: 0, propaganda: 3}, {money: 3, propaganda: 0}],
);
assert.deepEqual({...flexible.total}, {money: 3, propaganda: 3});
assert.equal(flexible.affordable, true);

state.purchase_payment_policy.active = false;
state.players[0].resources = {money: 3, propaganda: 3};
const ordinary = context.purchaseSelectionDetails(state);
assert.deepEqual(
  normalize(ordinary.cards.map(card => ({money: card.money, propaganda: card.propaganda}))),
  [{money: 0, propaganda: 3}, {money: 0, propaganda: 3}],
);
assert.deepEqual({...ordinary.total}, {money: 0, propaganda: 6});
assert.equal(ordinary.affordable, false);

state.purchase_payment_policy.active = true;
state.purchase_area = ['混合'];
state.purchase_area_costs = [{money: 2, propaganda: 3}];
state.players[0].resources = {money: 4, propaganda: 1};
context.selectedPurchaseIndices = new Set([0]);
const mixed = context.purchaseSelectionDetails(state);
assert.deepEqual(normalize(mixed.cards.map(card => ({money: card.money, propaganda: card.propaganda}))), [
  {money: 4, propaganda: 1},
]);
assert.deepEqual({...mixed.total}, {money: 4, propaganda: 1});
assert.equal(mixed.affordable, true);

console.log('purchaseSelectionDetails allocation tests passed');
