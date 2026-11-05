// Botón "JM Rewards" de la barra superior: dice "Próximamente" hasta que se publica Rewards desde el panel
// (el mismo interruptor que muestra el recuadro bajo el cotizador). Publicado: pasa a "Entrar" y lleva a la billetera.
export function setRewardsNav(url) {
  const el = document.getElementById('tb-rw');
  if (!el || !url) return;
  const a = document.createElement('a');
  a.className = 'tb-rw on'; a.id = 'tb-rw'; a.href = url; a.target = '_blank'; a.rel = 'noopener';
  a.innerHTML = 'JM Rewards <em>Entrar</em>';
  el.replaceWith(a);
}
// Páginas por país (no cargan el cotizador): consultan si Rewards está publicado.
export async function checkRewardsNav() {
  try {
    const res = await fetch('/api/tasas', { cache: 'no-store' });
    if (res.ok) setRewardsNav((await res.json())?.rewards?.url);
  } catch { /* queda "Próximamente" */ }
}
