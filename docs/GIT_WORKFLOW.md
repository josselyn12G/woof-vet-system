# Guía de Git: ramas, commits y flujo de trabajo

Versión resumida de `Guia_Git_y_CI_CD.docx` (que incluye diagramas y el ejemplo completo con lo que aparece en pantalla). Basada en [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) y [SemVer](https://semver.org/lang/es/).

## 1. Configuración inicial (una sola vez)

```bash
git config --global user.name "Tu Nombre"
git config --global user.email "tu@correo.com"
git config --global init.defaultBranch main
git config --global pull.rebase true          # evita commits de merge innecesarios al hacer pull
git config --global push.autoSetupRemote true # el primer push crea la rama remota solo

# Subir el proyecto por primera vez (solo quien crea el repo; el repo de GitHub debe estar VACÍO)
cd woof-vet-system
git init -b main
git add .
git commit -m "chore: initial django project"
git remote add origin https://github.com/TU_USUARIO/woof-vet-system.git
git push -u origin main
git switch -c develop && git push -u origin develop   # develop se crea UNA sola vez
```

El resto del equipo:

```bash
git clone https://github.com/TU_USUARIO/woof-vet-system.git
cd woof-vet-system
git switch develop
python3.12 -m venv .venv && source .venv/bin/activate   # ver Entorno_Virtual_Python.docx
pip install -r requirements.txt
python manage.py migrate
```

## 2. Estrategia de ramas

| Rama | Propósito | Se crea desde | Se integra en |
|---|---|---|---|
| `main` | Producción. Siempre estable. Cada merge = versión | — | — |
| `develop` | Integración de lo que viene en la próxima versión | `main` | `main` (vía release) |
| `feat/*` | Nueva funcionalidad | `develop` | `develop` |
| `fix/*` | Corrección de bug no urgente | `develop` | `develop` |
| `hotfix/*` | Bug urgente en producción | `main` | `main` **y** `develop` |
| `release/*` | Preparar una versión (QA, versionado) | `develop` | `main` **y** `develop` |
| `docs/*`, `chore/*`, `refactor/*`, `test/*`, `ci/*` | Igual que feat | `develop` | `develop` |

> Para equipos muy pequeños puedes omitir `develop` y `release/*` (GitHub Flow): ramas cortas desde `main` y PR a `main`. Si lo haces, cambia `develop` por `main` en esta guía.

### Nomenclatura de ramas

Formato: `<tipo>/<id-issue>-<descripcion-corta-en-kebab-case>`

```
feat/15-mascotas
fix/34-error-token-expirado
hotfix/58-caida-login-produccion
docs/21-guia-de-instalacion
chore/40-actualizar-dependencias
release/1.2.0
```

Reglas: minúsculas, guiones, sin espacios ni tildes, corta y descriptiva, vida corta (días, no semanas).

## 3. Commits (Conventional Commits)

### Estructura

```
<tipo>[ámbito opcional][!]: <descripción>

[cuerpo opcional]

[pie(s) opcional(es)]
```

### Tipos

| Tipo | Uso | SemVer |
|---|---|---|
| `feat` | Nueva funcionalidad | MINOR |
| `fix` | Corrección de bug | PATCH |
| `docs` | Solo documentación | — |
| `style` | Formato (espacios, comas); sin cambio de lógica | — |
| `refactor` | Cambio de código que no arregla bug ni añade feature | — |
| `perf` | Mejora de rendimiento | — |
| `test` | Añadir o corregir tests | — |
| `build` | Sistema de build, dependencias | — |
| `ci` | Configuración de CI/CD | — |
| `chore` | Tareas varias que no tocan src/tests | — |
| `revert` | Revierte un commit anterior | — |

Un `!` tras el tipo/ámbito o un pie `BREAKING CHANGE:` indica cambio incompatible → **MAJOR**, sin importar el tipo.

### Ejemplos

```bash
git commit -m "feat(auth): add JWT login endpoint"
git commit -m "fix(api): return 404 when user does not exist"
git commit -m "docs: add installation steps to README"
git commit -m "refactor(mascotas): extract pet form"
git commit -m "ci: cache pip dependencies in django workflow"
git commit -m "feat(api)!: rename /users/profile to /users/me"

# Con cuerpo y pie (usa dos -m o abre el editor con `git commit`)
git commit -m "fix(auth): refresh token was not rotated" \
           -m "The refresh endpoint reused the old token, allowing replay attacks." \
           -m "Closes #34"

# Breaking change explícito
git commit -m "feat(api): change pagination format" \
           -m "BREAKING CHANGE: responses now return {results, next} instead of a plain list"
```

### Buenas prácticas

- Descripción en **imperativo**, minúscula, sin punto final, ≤ 72 caracteres (`add`, no `added`/`adds`).
- Idioma: elige uno (inglés o español) y úsalo siempre; los **tipos** siempre en inglés.
- **Un commit = un cambio lógico.** No mezcles refactor con feature.
- Commitea seguido y en pequeño; usa el cuerpo para explicar el *por qué*, no el *qué*.
- Referencia issues en el pie: `Closes #12`, `Refs #20`.
- Nunca commitees secretos, `.env`, `node_modules`, `.venv`.
- No hagas commits tipo `fix`, `wip`, `cambios`, `asdf`.

## 4. Flujo completo, paso a paso

### 4.1 Nueva funcionalidad

```bash
# 0. ¿En qué rama estoy?  (el * marca la actual)
git branch

# 1. Entra a develop y actualízala
git switch develop
git pull

# 2. Crea tu rama
git switch -c feat/15-mascotas

# 3. Trabaja y commitea en pequeño
python manage.py startapp mascotas        # ... programar ...
git status                                # ver qué cambió
git add mascotas templates woof
git commit -m "feat(mascotas): add pet model, views and templates"
git add mascotas/tests.py
git commit -m "test(mascotas): cover pet list and creation"
python manage.py test                     # probar antes de subir

# 4. Mantén tu rama al día con develop (rebase = historial limpio)
git fetch origin
git rebase origin/develop
# si hay conflictos: edita archivos -> git add <archivo> -> git rebase --continue
# para abortar: git rebase --abort

# 5. Sube la rama
git push                    # tras un rebase ya publicado: git push --force-with-lease

# 6. Abre el Pull Request en GitHub: base=develop ← compare=feat/15-mascotas
#    Título en formato Conventional Commit: "feat(mascotas): add pets module"
#    Espera CI en verde + al menos 1 aprobación

# 7. Merge con "Squash and merge" (un commit limpio en develop)

# 8. Limpieza local
git switch develop && git pull
git branch -D feat/15-mascotas   # -D: tras un squash merge, -d dice "not fully merged" (es normal)
```

> **Squash and merge**: el título del PR se vuelve el mensaje del commit en `develop`, por eso debe cumplir Conventional Commits (el workflow `commits.yml` lo valida).

### 4.2 Release

```bash
git switch develop && git pull
git switch -c release/1.2.0
git commit --allow-empty -m "chore(release): prepare 1.2.0"
git push
# PR release/1.2.0 -> main  (merge commit), luego:
git switch main && git pull
git tag -a v1.2.0 -m "Release 1.2.0"
git push origin v1.2.0        # dispara .github/workflows/release.yml
# Devuelve los cambios a develop
git switch develop && git merge --no-ff main && git push
```

### 4.3 Hotfix (bug urgente en producción)

```bash
git switch main && git pull
git switch -c hotfix/58-caida-login-produccion
git commit -am "fix(auth): handle null email on login"
git push
# PR -> main, merge, luego tag:
git switch main && git pull
git tag -a v1.2.1 -m "Hotfix 1.2.1" && git push origin v1.2.1
# PR o merge de main -> develop para no perder el arreglo
git switch develop && git merge --no-ff main && git push
```

## 5. Comandos de referencia

### Estado e historial
```bash
git status                          # estado del working tree
git status -sb                      # versión corta con rama
git log --oneline --graph --all     # historial gráfico
git log -p -- ruta/archivo          # historial de un archivo con diffs
git diff                            # cambios sin stage
git diff --staged                   # cambios en stage
git blame ruta/archivo              # quién cambió cada línea
```

### Ramas
```bash
git branch                          # listar locales
git branch -a                       # incluye remotas
git switch rama                     # cambiar de rama
git switch -c nueva                 # crear y cambiar
git branch -d rama                  # borrar (segura, solo si está mergeada)
git branch -D rama                  # borrar forzado
git branch -m nuevo-nombre          # renombrar la actual
git fetch --prune                   # actualizar remotas y limpiar ramas borradas
```

### Staging y commits
```bash
git add archivo                     # agregar archivo
git add -p                          # agregar por fragmentos (commits más atómicos)
git restore --staged archivo        # sacar de stage
git restore archivo                 # descartar cambios locales (¡irreversible!)
git commit --amend                  # editar el último commit (solo si NO lo has publicado)
git commit --amend --no-edit        # añadir cambios al último commit sin cambiar mensaje
```

### Sincronizar
```bash
git pull                            # fetch + rebase (según config)
git push
git push --force-with-lease         # force push seguro tras rebase (NUNCA --force a secas)
git remote -v                       # ver remotos
```

### Integrar cambios
```bash
git merge --no-ff rama              # merge conservando commit de merge
git rebase develop                  # reaplicar tu rama sobre develop
git cherry-pick <hash>              # traer un commit específico
```

### Deshacer
```bash
git revert <hash>                   # crea un commit que deshace otro (seguro en ramas compartidas)
git reset --soft HEAD~1             # deshace commit, deja cambios en stage
git reset --hard HEAD~1             # deshace commit Y descarta cambios (peligroso)
git reflog                          # historial de todo lo que hizo HEAD: salvavidas
git stash                           # guarda cambios temporalmente
git stash pop                       # los recupera
```

### Tags
```bash
git tag -a v1.0.0 -m "Release 1.0.0"
git push origin v1.0.0
git tag -l
git tag -d v1.0.0 && git push origin --delete v1.0.0
```

## 6. Reglas de oro

1. **Nunca** hagas push directo a `main` ni `develop`: todo por Pull Request.
2. **Nunca** reescribas historia compartida (`rebase`/`amend`/`force`) en `main` o `develop`.
3. Ramas cortas, PRs pequeños (< 400 líneas idealmente).
4. CI en verde antes de mergear.
5. Haz `git pull` antes de empezar a trabajar cada día.
6. Si te equivocas: `git reflog` casi siempre lo arregla.
7. Un secreto commiteado está comprometido aunque lo borres: **rota la credencial**.

## 7. Protección de ramas en GitHub

`Settings → Rules → Rulesets → New branch ruleset` para `main` y `develop`:

- Require a pull request before merging (≥ 1 aprobación)
- Require status checks to pass: `test`, `pr-title`, `commits`
- Require branches to be up to date
- Block force pushes
- Do not allow bypassing

En `Settings → General`: rama por defecto `develop`, permitir **Squash merging**, desactivar los otros si quieres uniformidad, y activar **Automatically delete head branches**.
