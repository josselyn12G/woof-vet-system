// Reglas de Conventional Commits que valida .github/workflows/commits.yml
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'subject-case': [0],
  },
};
