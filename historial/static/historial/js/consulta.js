/*
 * Registrar consulta: "Agregar medicamento" y "Agregar vacuna" clonan la fila modelo del formset
 * (empty_form, con __prefix__) y suben TOTAL_FORMS; en la receta, muestra cuántas tomas salen.
 * Sin JavaScript igual funciona: hay una fila vacía en cada grupo y el servidor valida todo.
 */
(function () {
  document.querySelectorAll('[data-formset]').forEach((grupo) => {
    const prefijo = grupo.dataset.formset;
    const total = grupo.querySelector(`#id_${prefijo}-TOTAL_FORMS`);
    const filas = grupo.querySelector('[data-filas]');
    const modelo = grupo.querySelector('template[data-modelo]');
    const agregar = grupo.querySelector('[data-agregar]');
    if (!total || !filas || !modelo || !agregar) return;

    agregar.hidden = false;
    agregar.addEventListener('click', () => {
      const indice = Number(total.value);
      const html = modelo.innerHTML.replace(/__prefix__/g, String(indice));
      filas.insertAdjacentHTML('beforeend', html);
      total.value = String(indice + 1);
      const nueva = filas.lastElementChild;
      nueva.querySelector('input:not([type="hidden"]), select')?.focus();
    });
  });

  // Tomas = días × 24 ÷ cada cuántas horas (lo mismo que Prescripcion.tomas en el servidor)
  document.addEventListener('input', (evento) => {
    const fila = evento.target.closest('[data-fila]');
    if (!fila) return;
    const frecuencia = fila.querySelector('[data-frecuencia]');
    const duracion = fila.querySelector('[data-duracion]');
    const salida = fila.querySelector('[data-tomas]');
    if (!frecuencia || !duracion || !salida) return;
    const horas = Number(frecuencia.value);
    const dias = Number(duracion.value);
    if (horas > 0 && dias > 0) {
      const tomas = Math.floor((dias * 24) / horas);
      salida.textContent = `Se generarán ${tomas} toma${tomas === 1 ? '' : 's'}`;
    } else {
      salida.textContent = '';
    }
  });
})();
