from .services.periodos import elegir_periodo, opciones_de_periodo


class PeriodoMixin:
    """Lee ?periodo= (un valor inventado vuelve al de siempre) y lo deja en el contexto para los segmentos."""
    periodos = {}
    periodo_por_defecto = ''

    def periodo(self):
        return elegir_periodo(self.request.GET.get('periodo', self.periodo_por_defecto), self.periodos,
                              self.periodo_por_defecto)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['periodos'] = opciones_de_periodo(self.periodos)
        contexto['periodo'] = self.periodo()[0]
        return contexto
