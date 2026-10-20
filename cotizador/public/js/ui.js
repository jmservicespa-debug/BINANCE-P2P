// Piezas de interfaz compartidas: banderas y logo.

// Banderas simplificadas en SVG (los emojis de bandera no se ven en Windows).
const FLAGS = {
  CL: '<rect width="30" height="15" fill="#fff"/><rect y="15" width="30" height="15" fill="#D52B1E"/><rect width="12" height="15" fill="#0039A6"/><circle cx="6" cy="7.5" r="2.2" fill="#fff"/>',
  CO: '<rect width="30" height="15" fill="#FCD116"/><rect y="15" width="30" height="7.5" fill="#003893"/><rect y="22.5" width="30" height="7.5" fill="#CE1126"/>',
  VE: '<rect width="30" height="10" fill="#FCE300"/><rect y="10" width="30" height="10" fill="#0033A0"/><rect y="20" width="30" height="10" fill="#EF3340"/>'
    + [0, 1, 2, 3, 4, 5, 6, 7].map((i) => { const a = Math.PI * (0.15 + 0.7 * i / 7); return `<circle cx="${(15 - 6 * Math.cos(a)).toFixed(1)}" cy="${(17 - 5 * Math.sin(a)).toFixed(1)}" r=".9" fill="#fff"/>`; }).join(''),
  PE: '<rect width="30" height="30" fill="#fff"/><rect width="10" height="30" fill="#D91023"/><rect x="20" width="10" height="30" fill="#D91023"/>',
  US: Array.from({ length: 7 }, (_, i) => `<rect y="${i * 4.6}" width="30" height="2.3" fill="#B22234"/>`).join('') + '<rect width="14" height="14" fill="#3C3B6E"/>',
  BR: '<rect width="30" height="30" fill="#009C3B"/><polygon points="15,5 27,15 15,25 3,15" fill="#FFDF00"/><circle cx="15" cy="15" r="5.5" fill="#002776"/>',
  PA: '<rect width="30" height="30" fill="#fff"/><rect x="15" width="15" height="15" fill="#D21034"/><rect y="15" width="15" height="15" fill="#005293"/><circle cx="7.5" cy="7.5" r="2.5" fill="#005293"/><circle cx="22.5" cy="22.5" r="2.5" fill="#D21034"/>',
  EC: '<rect width="30" height="15" fill="#FFDD00"/><rect y="15" width="30" height="7.5" fill="#034EA2"/><rect y="22.5" width="30" height="7.5" fill="#ED1C24"/><circle cx="15" cy="15" r="3" fill="#8B5A2B"/>',
};

export const flag = (c) => `<svg class="flag" viewBox="0 0 30 30" aria-hidden="true"><rect width="30" height="30" fill="#fff"/>${FLAGS[c] || ''}</svg>`;
export const flags = (cs) => `<span class="flags">${cs.map(flag).join('')}</span>`;
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
