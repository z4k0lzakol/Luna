// @world: main
// window.name-defuser: in the top-level frame only, clear window.name at document start. Spec 03a 6.9.
function (R, ...args) {
  if (!R.isTop()) return;
  try { R.win.name = ""; } catch (e) { /* ignore */ }
}
