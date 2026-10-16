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
  ],
};
