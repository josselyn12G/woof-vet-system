// Vista previa de la foto en el formulario de mascotas: al elegir un archivo se muestra
// antes de guardar. Solo cambia lo que se ve; el archivo se envía igual con el formulario.
(function () {
  const entrada = document.querySelector('.subir-foto input[type="file"]');
  const imagen = document.querySelector('[data-foto-imagen]');
  if (!entrada || !imagen) return;

  const vacia = document.querySelector('[data-foto-vacia]');
  const nombre = document.querySelector('[data-foto-nombre]');
  const quitar = document.querySelector('.subir-foto__quitar input[type="checkbox"]');
  const fotoOriginal = imagen.getAttribute('src');
  let urlTemporal = null;

  entrada.addEventListener('change', function () {
    const archivo = entrada.files[0];
    if (urlTemporal) URL.revokeObjectURL(urlTemporal);
    if (!archivo) return;

    urlTemporal = URL.createObjectURL(archivo);
    imagen.src = urlTemporal;
    imagen.hidden = false;
    if (vacia) vacia.hidden = true;
    if (nombre) {
      nombre.textContent = archivo.name;
      nombre.hidden = false;
    }
    // Si elige una foto nueva, ya no tiene sentido "quitar la actual"
    if (quitar) quitar.checked = false;
  });

  // Al marcar "Quitar la foto actual" la vista previa se atenúa para indicar que se borrará
  if (quitar) {
    quitar.addEventListener('change', function () {
      imagen.closest('[data-foto-vista]').classList.toggle('subir-foto__vista--quitar', quitar.checked);
      if (quitar.checked && urlTemporal) {
        entrada.value = '';
        imagen.src = fotoOriginal;
        if (nombre) nombre.hidden = true;
      }
    });
  }
})();
