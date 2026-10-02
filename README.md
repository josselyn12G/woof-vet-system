# Woof sistema veterinario

Proyecto web con **Django 5.2 LTS** usando el patrón MVC (Model–Template–View), el ORM de Django y plantillas HTML.

```
woof-vet-system/
├── manage.py            comandos de Django
├── requirements.txt     dependencias de Python
├── config/              configuración del proyecto (settings.py, urls.py…)
├── templates/           plantillas comunes (base.html)
├── docs/                guías del equipo (Word)
└── .github/             CI/CD con GitHub Actions
```

## Requisitos

- Python **3.12** (o 3.10+)
- Git

## Cómo ejecutarlo

```bash
git clone https://github.com/josselyn12G/woof-vet-system.git
cd woof-vet-system
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # opcional: usuario para /admin/
python manage.py runserver
```

Abre http://127.0.0.1:8000/ · Admin: http://127.0.0.1:8000/admin/

Pruebas: `python manage.py test`

## Documentación (`docs/`)

| Documento | Contenido |
|---|---|
| `Guia_Git_y_CI_CD.docx` · [GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md) | Ramas, commits y el trabajo diario paso a paso |
| `Arquitectura_del_Proyecto.docx` | Qué es cada archivo y cómo crear un módulo nuevo con MVC y plantillas |
| `Crear_un_Modulo_Mascotas.docx` | Tutorial paso a paso: módulo de mascotas completo (modelo, vistas, URLs, plantillas y pruebas) |
| `Entorno_Virtual_Python.docx` | Qué es el `.venv`, para qué sirve y cómo usarlo |
| `Pruebas_y_CI_CD.docx` · [CI_CD.md](docs/CI_CD.md) | Cómo escribir pruebas por módulo y cómo las valida GitHub Actions |

## Flujo de trabajo

Ramas `main` (estable) y `develop` (integración). Cada tarea en su rama `feat/<issue>-<nombre>` creada desde `develop`, con Pull Request hacia `develop`. Commits con [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/).

## Equipo
Josselyn Guevara
Adrian Freire