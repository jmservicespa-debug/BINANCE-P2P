// Indicador "Atendiendo ahora" según la hora de Chile (lunes a domingo, 10:00 a 22:30).
function update() {
  const parts = new Intl.DateTimeFormat('es-CL', { timeZone: 'America/Santiago', hour: '2-digit', minute: '2-digit', hour12: false }).formatToParts(new Date());
  const h = Number(parts.find((p) => p.type === 'hour')?.value), m = Number(parts.find((p) => p.type === 'minute')?.value);
  const mins = h * 60 + m, open = mins >= 600 && mins < 1350;
  const box = document.getElementById('live');
  if (!box) return;
  box.hidden = false;
  box.classList.toggle('off', !open);
  document.getElementById('live-t').textContent = open
    ? 'Atendiendo ahora · te respondemos en minutos'
    : 'Fuera de horario · te respondemos desde las 10:00 (hora de Chile)';
}
update();
setInterval(update, 60000);
