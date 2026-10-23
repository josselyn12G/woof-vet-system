// Abre el carnet como pop-up. Es liviano: Three.js y el librito 3D (carnet-3d.js) se cargan
// recién la primera vez que se abre un carnet.
// - En la página del carnet, el pop-up ya está en el HTML (y se abre solo al cargar).
// - En la lista y en la ficha, el enlace "Carnet" trae ese pop-up con fetch. Si algo falla, el enlace navega normal.
let modulo = null;

async function abrir(dialogo) {
  modulo = modulo || await import(new URL('./carnet-3d.js', import.meta.url));
  modulo.abrirCarnet(dialogo);
}

const propio = document.querySelector('dialog[data-carnet]');
if (propio) {
  document.querySelectorAll('[data-abrir-carnet-aqui]').forEach((boton) => {
    boton.addEventListener('click', () => abrir(propio));
  });
  if ('abrirAlCargar' in propio.dataset) abrir(propio);
}

document.querySelectorAll('a[data-abrir-carnet]').forEach((enlace) => {
  enlace.addEventListener('click', async (evento) => {
    evento.preventDefault();
    try {
      const respuesta = await fetch(enlace.href, { headers: { 'X-Requested-With': 'fetch' } });
      if (!respuesta.ok) throw new Error(respuesta.status);
      const pagina = new DOMParser().parseFromString(await respuesta.text(), 'text/html');
      const dialogo = pagina.querySelector('dialog[data-carnet]');
      if (!dialogo) throw new Error('sin carnet');
      delete dialogo.dataset.abrirAlCargar;
      document.querySelectorAll('dialog[data-carnet].es-traido').forEach((viejo) => viejo.remove());
      dialogo.classList.add('es-traido');
      document.body.append(dialogo);
      await abrir(dialogo);
    } catch (error) {
      window.location.href = enlace.href;
    }
  });
});
