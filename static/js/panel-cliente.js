// Portada del cliente: el buscador y las pestañas filtran las tarjetas de mascotas en el navegador.
// (Son pocas mascotas por dueño: no hace falta ir al servidor.) Sin JavaScript se ven todas.
(function () {
  const fichas = [...document.querySelectorAll('[data-fichas] > li')];
  if (!fichas.length) return;

  const buscador = document.querySelector('[data-buscar-mascota]');
  const pestanas = [...document.querySelectorAll('[data-pestanas] [data-especie]')];
  const sinResultados = document.querySelector('[data-sin-resultados]');
  let especie = '';

  function filtrar() {
    const texto = (buscador.value || '').trim().toLowerCase();
    let visibles = 0;
    fichas.forEach((ficha) => {
      const coincide = (!especie || ficha.dataset.especie === especie) && ficha.dataset.buscar.includes(texto);
      ficha.hidden = !coincide;
      if (coincide) visibles += 1;
    });
    sinResultados.hidden = visibles > 0;
  }

  buscador.addEventListener('input', filtrar);
  pestanas.forEach((pestana) => {
    pestana.addEventListener('click', () => {
      pestanas.forEach((otra) => {
        otra.classList.toggle('es-activo', otra === pestana);
        otra.setAttribute('aria-selected', String(otra === pestana));
      });
      especie = pestana.dataset.especie;
      filtrar();
    });
  });
})();
