// Funciones para veterinarios: avanzan solas, y al hacer clic se despliega la descripción
// y cambia la imagen. La barra de progreso de cada punto es una animación CSS: cuando termina,
// se pasa al siguiente. Así el tiempo se pausa solo (al pasar el mouse o fuera de pantalla).
const funciones = document.getElementById('funciones');

if (funciones) {
  const items = [...funciones.querySelectorAll('.funciones__item')];
  const imagenes = [...funciones.querySelectorAll('.funciones__imagen')];
  const reducirMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let actual = 0;

  function mostrar(indice) {
    actual = (indice + items.length) % items.length;
    items.forEach((item, i) => {
      const activa = i === actual;
      item.classList.toggle('es-activa', activa);
      item.querySelector('.funciones__boton').setAttribute('aria-expanded', String(activa));
      // Reinicia la barra de progreso: se quita la animación y se vuelve a poner en el siguiente cuadro
      const barra = item.querySelector('.funciones__progreso');
      barra.style.animation = 'none';
      void barra.offsetWidth;
      barra.style.animation = '';
    });
    imagenes.forEach((imagen, i) => imagen.classList.toggle('es-activa', i === actual));
  }

  items.forEach((item, i) => {
    item.querySelector('.funciones__boton').addEventListener('click', () => mostrar(i));
    // Cuando la barra del punto activo se llena, avanza al siguiente (no ocurre con "reducir movimiento")
    item.querySelector('.funciones__progreso').addEventListener('animationend', () => {
      if (!reducirMovimiento && i === actual) mostrar(actual + 1);
    });
  });

  // Fuera de pantalla, el avance automático se pausa
  new IntersectionObserver(([entrada]) => {
    funciones.classList.toggle('funciones--pausada', !entrada.isIntersecting);
  }, { threshold: 0.3 }).observe(funciones);
}
