// Reglas de Conventional Commits que valida .github/workflows/commits.yml
export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'subject-case': [0],
  },
};
