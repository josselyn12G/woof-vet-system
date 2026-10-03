# Modelo de datos — Woof

> **Borrador para revisar con Adrián.** Lo marcado *Entrega 1* es lo mínimo para el lunes; lo demás es la proyección para las fases siguientes (no se programa todavía, pero conviene que el diseño ya lo contemple).

GitHub y VS Code muestran este diagrama directamente (mermaid). Si el profe pide imagen, cópienlo en https://mermaid.live y exporten PNG.

```mermaid
erDiagram
    USUARIO ||--o{ MASCOTA : "es dueño de"
    MASCOTA ||--o{ CITA : "tiene"
    USUARIO ||--o{ CITA : "atiende (veterinario)"
    MASCOTA ||--o{ CONSULTA : "tiene"
    CITA |o--o| CONSULTA : "genera"
    MASCOTA ||--o{ VACUNA_APLICADA : "recibe"

    USUARIO {
        bigint id PK
        string username UK
        string email UK
        string password "hash"
        string first_name
        string last_name
        string rol "cliente | veterinario | admin"
        string telefono "+593..., para el SMS 2FA"
        datetime date_joined
    }
    MASCOTA {
        bigint id PK
        bigint dueno_id FK
        string nombre
        string especie "perro | gato | otro"
        string raza
        string sexo "M | H"
        date fecha_nacimiento
        decimal peso_kg
        image foto "opcional"
        datetime creado
        datetime actualizado
    }
    CITA {
        bigint id PK
        bigint mascota_id FK
        bigint veterinario_id FK
        datetime fecha_hora
        string motivo
        string estado "pendiente | confirmada | atendida | cancelada"
    }
    CONSULTA {
        bigint id PK
        bigint mascota_id FK
        bigint cita_id FK "opcional"
        date fecha
        text diagnostico
        text tratamiento
        decimal peso_kg
    }
    VACUNA_APLICADA {
        bigint id PK
        bigint mascota_id FK
        string nombre
        date fecha_aplicacion
        date proxima_dosis
    }
```

## Entrega 1: tablas que se programan ahora

### `cuentas.Usuario` (hereda de `AbstractUser`)
Ya trae username, email, password (con hash), first_name, last_name, is_active, is_staff, date_joined. Solo agregamos:

| Campo | Tipo Django | Notas |
|---|---|---|
| rol | `CharField(choices=...)` | `cliente` por defecto |
| telefono | `CharField(max_length=16)` | obligatorio, formato internacional `+593...`: ahí llega el código SMS del doble factor |
| email | `EmailField(unique=True)` | lo redefinimos para que sea único (lo necesitaremos para Google y 2FA) |

En `settings.py`: `AUTH_USER_MODEL = "cuentas.Usuario"` **antes de la primera migración propia**.

### `mascotas.Mascota`

| Campo | Tipo Django | Notas |
|---|---|---|
| dueno | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mascotas")` | se asigna solo en la vista |
| nombre | `CharField(max_length=60)` | obligatorio |
| especie | `CharField(max_length=10, choices=...)` | obligatorio |
| raza | `CharField(max_length=60, blank=True)` | |
| sexo | `CharField(max_length=1, choices=...)` | |
| fecha_nacimiento | `DateField(null=True, blank=True)` | no futura |
| peso_kg | `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)` | > 0 |
| foto | `ImageField(upload_to="mascotas/", blank=True)` | requiere Pillow; se puede dejar para después |
| creado / actualizado | `DateTimeField(auto_now_add / auto_now)` | |

## Decisiones de diseño
- **Usuario personalizado desde el inicio:** cambiar el modelo de usuario cuando ya hay migraciones obliga a borrar la base.
- **El dueño no viaja en el formulario:** la vista lo toma de `request.user`, así nadie puede crear mascotas a nombre de otro.
- **Todas las consultas filtran por dueño** (`Mascota.objects.filter(dueno=request.user)`), por eso la mascota de otro da 404.
- **Veterinario = Usuario con rol `veterinario`**, no otra tabla, para que todos usen el mismo login.
