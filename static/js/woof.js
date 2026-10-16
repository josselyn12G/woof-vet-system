// Comportamiento común a todas las páginas de Woof.

// 1. Menú: al bajar, el vidrio se vuelve un poco más opaco y aparece una sombra suave
//    (en lugar de una línea divisoria fija).
const menu = document.getElementById('menu');
if (menu) {
  const actualizarMenu = () => menu.classList.toggle('menu--scroll', window.scrollY > 8);
  window.addEventListener('scroll', actualizarMenu, { passive: true });
  actualizarMenu();
}

// 2. Aparición al hacer scroll: todo elemento con data-revelar aparece cuando entra en pantalla.
//    data-revelar-retraso="1", "2"... escalona varios elementos que entran juntos.
const elementos = document.querySelectorAll('[data-revelar]');
if ('IntersectionObserver' in window) {
  const observador = new IntersectionObserver((entradas) => {
    for (const entrada of entradas) {
      if (entrada.isIntersecting) {
        entrada.target.classList.add('es-visible');
        observador.unobserve(entrada.target); // aparece una sola vez
      }
    }
  }, { threshold: 0.15, rootMargin: '0px 0px -8% 0px' });
  elementos.forEach((elemento) => observador.observe(elemento));
} else {
  elementos.forEach((elemento) => elemento.classList.add('es-visible'));
}
