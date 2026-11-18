// Raza según la especie: en el formulario de la mascota, "Raza" muestra solo las razas de la especie elegida.
// Sin JavaScript se ven todas, agrupadas por especie (el servidor valida igual que la raza sea de esa especie).
// El pop-up de "Mis mascotas" vuelve a cargar este archivo con cada formulario: cada par se prepara una sola vez.
(function () {
  document.querySelectorAll('[data-elige-especie]').forEach(function (especie) {
    const formulario = especie.form;
    const raza = formulario && formulario.querySelector('[data-elige-raza]');
    if (!raza || raza.dataset.preparado) return;
    raza.dataset.preparado = '1';

    // Los grupos que mandó el servidor (uno por especie, con la etiqueta de su nombre)
    const vacia = raza.querySelector('option[value=""]');
    const grupos = Array.from(raza.querySelectorAll('optgroup')).map(function (grupo) {
      return { especie: grupo.label, opciones: Array.from(grupo.children) };
    });

    function filtrar() {
      const elegida = especie.selectedIndex > 0 ? especie.options[especie.selectedIndex].text : '';
      const grupo = grupos.find(function (g) { return g.especie === elegida; });
      const anterior = raza.value;

      raza.replaceChildren(vacia);
      if (grupo) grupo.opciones.forEach(function (opcion) { raza.appendChild(opcion); });
      // Si la raza que estaba elegida no es de esta especie, queda sin elegir
      raza.value = grupo && grupo.opciones.some(function (o) { return o.value === anterior; }) ? anterior : '';

      vacia.textContent = !elegida ? 'Elige primero la especie' : grupo ? 'Elige la raza' : 'Sin razas para esta especie';
      raza.disabled = !grupo;
    }

    especie.addEventListener('change', filtrar);
    filtrar();
  });
})();
