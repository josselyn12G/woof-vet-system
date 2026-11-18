// La campana del panel: al tocarla se abre debajo un panel con los avisos (Hoy / Esta semana / Antes) y
// "Ver todas" para la página completa. Se pide con fetch cada vez que se abre (así siempre está al día) y,
// como en la página de avisos, quedan leídos: el número rojo desaparece. Sin JS, la campana es un enlace.
(function () {
  document.querySelectorAll('[data-campana]').forEach((campana) => {
    const boton = campana.querySelector('[data-campana-abrir]');
    const panel = campana.querySelector('[data-campana-panel]');
    if (!boton || !panel) return;

    function cerrar(devolverFoco) {
      if (panel.hidden) return;
      panel.hidden = true;
      boton.setAttribute('aria-expanded', 'false');
      if (devolverFoco) boton.focus();
    }

    function elegir(clave) {
      panel.querySelectorAll('[data-pestana]').forEach((p) => {
        const activa = p.dataset.pestana === clave;
        p.classList.toggle('es-activa', activa);
        p.setAttribute('aria-selected', String(activa));
      });
      panel.querySelectorAll('[data-lista]').forEach((lista) => { lista.hidden = lista.dataset.lista !== clave; });
    }

    // Mientras llegan los avisos: la misma forma del panel con bloques grises que laten (sin bloquear la pantalla)
    const ESQUELETO = `
      <div class="campana-panel__cabecera"><span class="campana-esqueleto campana-esqueleto--titulo"></span><span class="campana-esqueleto campana-esqueleto--boton"></span></div>
      <div class="campana-esqueleto campana-esqueleto--pestanas"></div>
      ${'<div class="campana-aviso"><span class="campana-esqueleto campana-esqueleto--icono"></span><div><span class="campana-esqueleto campana-esqueleto--linea"></span><span class="campana-esqueleto campana-esqueleto--linea campana-esqueleto--corta"></span></div></div>'.repeat(3)}`;

    async function abrir() {
      panel.hidden = false;
      boton.setAttribute('aria-expanded', 'true');
      panel.setAttribute('aria-busy', 'true');
      panel.innerHTML = ESQUELETO;
      try {
        const respuesta = await fetch(campana.dataset.panelUrl, { headers: { 'X-Requested-With': 'fetch' } });
        if (!respuesta.ok) throw new Error(respuesta.status);
        panel.innerHTML = await respuesta.text();
        panel.removeAttribute('aria-busy');
        // Ya se vieron: fuera el número rojo
        boton.querySelector('.panel-campana__numero')?.remove();
        boton.setAttribute('aria-label', 'Notificaciones');
      } catch (error) {
        window.location.href = boton.href;   // sin red para fetch: la página completa
      }
    }

    boton.addEventListener('click', (evento) => {
      evento.preventDefault();
      if (panel.hidden) abrir(); else cerrar(false);
    });
    panel.addEventListener('click', (evento) => {
      const pestana = evento.target.closest('[data-pestana]');
      if (pestana) elegir(pestana.dataset.pestana);
    });
    document.addEventListener('click', (evento) => { if (!campana.contains(evento.target)) cerrar(false); });
    document.addEventListener('keydown', (evento) => { if (evento.key === 'Escape') cerrar(true); });
  });
})();
