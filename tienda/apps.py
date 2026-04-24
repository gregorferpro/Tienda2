from django.apps import AppConfig


class TiendaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tienda'

    def ready(self):
        # Importar signals si es necesario
        try:
            import tienda.signals
        except ImportError:
            pass
