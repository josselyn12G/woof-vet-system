"""
Datos de los gráficos de los paneles, armados en el servidor (sin librerías de JavaScript): la plantilla
solo dibuja. Colores en tonos de naranja y el marrón de la marca, sin degradados.

- dona(partes): un anillo repartido (citas por estado, cuentas por rol...). El círculo tiene radio 15.915,
  así su perímetro mide 100 y cada parte se dibuja con stroke-dasharray = su porcentaje.
- columnas(partes): barras verticales con su alto relativo a la más alta.
"""

# Del más fuerte al más suave; el marrón y el gris cierran para los últimos
COLORES = ['#ee9a35', '#c26a12', '#f7c27a', '#7a3c0a', '#fbd9a8', '#3b2a22', '#d6d6db']


def dona(partes):
    """partes: [(etiqueta, valor)] → {total, segmentos: [{etiqueta, valor, porcentaje, color, largo, desde}]}."""
    total = sum(valor for _, valor in partes)
    segmentos = []
    acumulado = 0
    for i, (etiqueta, valor) in enumerate(partes):
        porcentaje = valor * 100 / total if total else 0
        segmentos.append({
            'etiqueta': etiqueta, 'valor': valor, 'porcentaje': round(porcentaje),
            'color': COLORES[i % len(COLORES)],
            # El trazo empieza arriba (offset 25) y cada parte arranca donde terminó la anterior
            'largo': round(porcentaje, 2), 'desde': round(25 - acumulado, 2),
        })
        acumulado += porcentaje
    return {'total': total, 'segmentos': segmentos}


def columnas(partes):
    """partes: [(etiqueta, valor)] → [{etiqueta, valor, alto (0-100), color}], el más alto llega a 100."""
    mayor = max((valor for _, valor in partes), default=0)
    return [
        {'etiqueta': etiqueta, 'valor': valor, 'alto': round(valor * 100 / mayor) if mayor else 0,
         'color': COLORES[0] if i == 0 else COLORES[2] if valor else COLORES[6]}
        for i, (etiqueta, valor) in enumerate(sorted(partes, key=lambda parte: -parte[1]))
    ]
