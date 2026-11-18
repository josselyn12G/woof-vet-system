// País → provincia → ciudad: al elegir uno, pide al servidor las opciones del siguiente y lo llena.
// El servidor vuelve a revisar que la ciudad sea de la provincia y la provincia del país (UbicacionService).
// Sin JavaScript, el formulario vuelve del servidor con las listas filtradas por lo que se eligió.
const formUbicacion = document.querySelector('form[data-url-provincias]');   // el registro y Mi cuenta

if (formUbicacion) {
  const pais = formUbicacion.querySelector('[data-ubicacion="pais"]');
  const provincia = formUbicacion.querySelector('[data-ubicacion="provincia"]');
  const ciudad = formUbicacion.querySelector('[data-ubicacion="ciudad"]');

  // Deja solo la primera opción ("Elige...") y agrega las que llegan del servidor
  function llenar(select, opciones) {
    const primera = select.options[0];
    select.replaceChildren(primera, ...opciones.map(({ id, nombre }) => new Option(nombre, id)));
    select.value = '';
    select.disabled = opciones.length === 0;
  }

  async function pedir(url, parametro, valor) {
    if (!valor) return [];
    try {
      const respuesta = await fetch(`${url}?${parametro}=${encodeURIComponent(valor)}`, { headers: { Accept: 'application/json' } });
      return respuesta.ok ? (await respuesta.json()).opciones : [];
    } catch {
      return [];   // sin conexión: la lista queda vacía y el servidor avisará al enviar
    }
  }

  pais?.addEventListener('change', async () => {
    llenar(ciudad, []);
    llenar(provincia, await pedir(formUbicacion.dataset.urlProvincias, 'pais', pais.value));
  });

  provincia?.addEventListener('change', async () => {
    llenar(ciudad, await pedir(formUbicacion.dataset.urlCiudades, 'provincia', provincia.value));
  });

  // Al abrir: si todavía no hay provincia elegida, la ciudad espera
  if (ciudad && !provincia?.value) ciudad.disabled = true;
}
