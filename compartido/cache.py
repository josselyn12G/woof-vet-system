"""
El caché de los catálogos que casi no cambian: servicios, especies y razas, provincias y ciudades.

Patrón Cache-Aside (el «caché» de «Mining microservice design patterns», SoCC 2022):
- Acierto: el dato está en memoria y se devuelve sin consultar Neon.
- Fallo: se consulta la base, se guarda en memoria y se devuelve.
memorizar() se pone delante de la consulta real con la misma respuesta, como el Proxy de caché de
refactoring.guru: quien pide la lista no sabe si vino de la memoria o de la base.

Para que nadie vea una lista vieja, cada app conecta en su signals.py las señales post_save y post_delete de
sus modelos con olvidar() (patrón Observer: el modelo avisa que cambió y el caché se entera solo).

Qué NO va al caché: los turnos libres de la agenda ni nada que cambie con cada reserva. Además, el caché solo
arma las listas que se muestran; la validación de los formularios y AgendaService siempre consultan la base.
"""
from django.core.cache import cache
from django.db import transaction

# Por si un cambio no pasó por el ORM (o lo hizo otro proceso de gunicorn, que tiene su propia memoria),
# ninguna lista vive más de 10 minutos
DURACION = 10 * 60


def memorizar(clave, calcular, duracion=DURACION):
    """Devuelve lo guardado en la clave; si no está (fallo), llama a calcular(), lo guarda y lo devuelve."""
    return cache.get_or_set(clave, calcular, duracion)


def olvidar(*claves):
    """
    Borra las claves cuando la transacción termina bien (transaction.on_commit). Si se borraran antes, otra
    petición podría volver a guardar la lista vieja mientras el cambio todavía no se confirma.
    """
    transaction.on_commit(lambda: cache.delete_many(claves))
