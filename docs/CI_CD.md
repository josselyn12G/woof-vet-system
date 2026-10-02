# CI/CD con GitHub Actions

Los workflows están en [.github/workflows/](../.github/workflows/) y se ejecutan solos en GitHub.

- **CI (Integración Continua)**: cada vez que subes código o abres un Pull Request, GitHub lo revisa automáticamente (lint, migraciones, tests).
- **CD (Entrega Continua)**: cuando publicas una versión (tag `vX.Y.Z`), GitHub crea el Release.

Guía detallada de pruebas: `docs/Pruebas_y_CI_CD.docx`.

## 1. Qué hace cada workflow

| Workflow | Cuándo corre | Qué revisa / hace |
|---|---|---|
| `django-ci.yml` | push a `main`/`develop` y cada PR | ruff → migraciones al día → `manage.py check` → `manage.py test` |
| `commits.yml` | cada PR | Título del PR y commits en formato Conventional Commits |
| `release.yml` | al subir un tag `v1.0.0` | Crea el GitHub Release con notas automáticas |

```
feat/* ──PR──► develop ──PR──► main ──tag v1.0.0──► Release
          ▲ aquí corre el CI (django-ci, commits)
```

`python manage.py test` encuentra solo el `tests.py` de cada app en `INSTALLED_APPS`: al crear un módulo nuevo con pruebas, el CI las incluye sin tocar el workflow.

## 2. Activarlo (una sola vez, después del primer push)

1. **Actions**: `Settings → Actions → General` → *Allow all actions*.
2. **Permisos**: en la misma página, *Workflow permissions* → **Read and write permissions** (para crear Releases).
3. Abre un PR de prueba para que los checks corran por primera vez.
4. **Proteger ramas**: `Settings → Rules → Rulesets → New branch ruleset` para `main` y `develop`:
   - Require a pull request before merging (1 aprobación)
   - Require status checks to pass: `test`, `pr-title`, `commits`
   - Block force pushes
5. `Settings → General`: rama por defecto **develop**, permitir **Squash merging** y activar **Automatically delete head branches**.

## 3. Validar antes de subir (en tu PC)

Con el entorno virtual activo, en la raíz del proyecto:

```bash
pip install ruff                                                 # solo la primera vez
ruff check . --select E4,E7,E9,F --extend-exclude migrations
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test
```

## 4. Ver el resultado en GitHub

1. En el Pull Request, sección **Checks**: ✔ pasó · ✖ falló · ● ejecutándose.
2. Pestaña **Actions**: historial de todas las ejecuciones.
3. Clic en el job con ✖ → abre el paso en rojo → ahí está el error.
4. Corriges en tu rama, haces commit y push → el CI vuelve a correr solo.

## 5. Publicar una versión

```bash
git switch main && git pull
git tag -a v1.0.0 -m "Release 1.0.0"
git push origin v1.0.0            # dispara release.yml
```

## 6. Desplegar (cuando lo necesiten)

Aún no hay despliegue automático. Opción sencilla: **Render** o **Railway**. Conectas el repo, comando de inicio `gunicorn woof.wsgi` (agrega `gunicorn` a `requirements.txt`), y en producción configuras `DEBUG = False`, `ALLOWED_HOSTS` y un `SECRET_KEY` propio fuera del código.

## 7. Errores frecuentes

| Error | Solución |
|---|---|
| ruff falla | `ruff check --fix .` y corrige lo que quede |
| `makemigrations --check` falla | `python manage.py makemigrations` y commitea la migración |
| Tests fallan solo en el CI | Falta subir un archivo o una migración (`git status`) |
| `commits` / `pr-title` falla | El título del PR o algún commit no sigue `tipo(ámbito): descripción` |
| Check requerido queda "Expected" | El workflow aún no corrió nunca: abre un PR de prueba |
