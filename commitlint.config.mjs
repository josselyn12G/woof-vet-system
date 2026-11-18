// Reglas de Conventional Commits que valida .github/workflows/commits.yml
export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'subject-case': [0],
  },
  // Commits que ya están en develop y no se pueden reescribir (la rama es compartida).
  // El squash merge del PR #14 quedó con un espacio al final del título (regla header-trim).
  ignores: [
    (mensaje) => mensaje.startsWith('feat(mascotas): agrega el CRUD de mascotas con foto y acceso con sesión \n'),
    // El squash merge del PR #22 quedó con una línea de 183 caracteres en la descripción (regla body-max-line-length).
    (mensaje) => mensaje.startsWith('feat(cuentas): agrega la cédula validada en el servidor con el módulo 10 (#22)'),
    // Release 0.3.0: el título del PR #39 mide 101 caracteres (header-max-length) y las descripciones
    // de los PR #71 y #72 tienen líneas de más de 100 (body-max-line-length y footer-max-line-length).
    (mensaje) => mensaje.startsWith('feat(citas): rediseña la agenda del veterinario con la foto de la mascota y una línea de tiempo (#39)'),
    (mensaje) => mensaje.startsWith('feat: historia clínica como reporte, Mis recetas por consulta y panel del veterinario (#71)'),
    (mensaje) => mensaje.startsWith('feat(panel): gráficos en Inicio, Indicadores y Citas del administrador (#72)'),
  ],
};
