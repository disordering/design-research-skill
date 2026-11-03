const key = 'campus-d-v02:' + location.pathname;
if (new URL(location.href).searchParams.get('reset') === '1') {
  sessionStorage.removeItem(key);
  history.replaceState(null, '', location.pathname);
}
export function readSaved() { return JSON.parse(sessionStorage.getItem(key) || 'null'); }
export function save(data) { sessionStorage.setItem(key, JSON.stringify(data)); }
export function esc(value) {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
export function shell(brand, heading, body) {
  document.title = heading + ' · ' + brand;
  const app = document.getElementById('app');
  app.innerHTML = `<header><p>${esc(brand)}</p><h1>${esc(heading)}</h1></header>${body}`;
  app.focus({preventScroll:true});
}
export function press(id, fn) { document.getElementById(id).addEventListener('click', fn); }
export function button(id, text, primary=false) { return `<button id="${id}" type="button" class="${primary?'primary':''}">${esc(text)}</button>`; }
export function feedback(message, role='alert') { return message ? `<p role="${role}">${esc(message)}</p>` : ''; }
