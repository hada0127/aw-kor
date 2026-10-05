// Exercise actual shipped JS functions with mocked I/O, without a browser or ROM.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const sprite = fs.readFileSync(path.join(__dirname, 'sprite_editor/static/app.js'), 'utf8');
const scene = fs.readFileSync(path.join(__dirname, 'scene_editor/static/app.js'), 'utf8');
function fn(source, name) {
  const start = source.indexOf(`async function ${name}(`);
  assert(start >= 0, name);
  const tail = source.slice(start);
  const next = tail.indexOf('\nfunction ');
  const nextAsync = tail.indexOf('\nasync function ');
  const ends = [next, nextAsync].filter(x => x >= 0);
  return tail.slice(0, Math.min(...ends));
}
const STOP = new Error('stop after actual load-side state update');
async function stopAtState(action) {
  try { await action(); assert.fail('state boundary was not reached'); }
  catch (error) { assert.equal(error, STOP); }
}
const view = {ok: true, width: 8, height: 8, tile_cols: 1, indices: [[1]],
  palette: [[255,255,255]], type: 'lz77', power_title_binding: 'v1:loaded-map'};
(async () => {
  let posted;
  const button = {};
  const spriteContext = vm.createContext({S: {},
    jget: async () => view, resetUndo: () => {throw STOP;},
    $: () => button, setStatus: () => {},
    jpost: async (url, body) => {posted = body; return {ok:false, error:'mock response'};}});
  vm.runInContext(fn(sprite, 'selectSprite'), spriteContext);
  await stopAtState(() => spriteContext.selectSprite('lz77_005B3ECC'));
  assert.equal(spriteContext.S.powerTitleBinding, view.power_title_binding);
  const saveStart = sprite.indexOf('  $("#save").onclick =');
  const saveEnd = sprite.indexOf('  $("#revert").onclick =', saveStart);
  assert(saveStart >= 0 && saveEnd > saveStart);
  vm.runInContext(sprite.slice(saveStart, saveEnd), spriteContext);
  await button.onclick();
  assert.equal(posted.power_title_binding, view.power_title_binding);

  let currentView = view;
  const sceneContext = vm.createContext({S: {items:{sprites:[{id:'lz77_005B3ECC'}]}, _reqSeq:0}, SP:{},
    markSel: () => {}, resetSpriteUndo: () => {throw STOP;}, toast: () => {},
    api: async (url, options) => {
      if (url.includes('/save')) {posted = JSON.parse(options.body); return {ok:false, error:'mock response'};}
      if (url.includes('/revert')) return {ok:true};
      return currentView;
    }});
  vm.runInContext(fn(scene, 'selectSprite') + '\n' + fn(scene, 'saveSprite') + '\n' + fn(scene, 'revertSprite'), sceneContext);
  await stopAtState(() => sceneContext.selectSprite(0, {}));
  assert.equal(sceneContext.SP.powerTitleBinding, view.power_title_binding);
  await sceneContext.saveSprite();
  assert.equal(posted.power_title_binding, view.power_title_binding);
  currentView = {...view, power_title_binding: 'v1:reloaded-map'};
  await stopAtState(() => sceneContext.revertSprite());
  assert.equal(sceneContext.SP.powerTitleBinding, currentView.power_title_binding);
  console.log('5 transport checks PASS');
})().catch(error => {console.error(error); process.exitCode = 1;});
