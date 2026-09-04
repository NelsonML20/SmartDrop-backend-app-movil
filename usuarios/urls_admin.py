from django.urls import path
from .views_dashboard import GraficasView, ResumenDashboardView
from .views_valvula import ValvulaAbrirTemporizadorView, ValvulaEstadoView, ValvulaAbrirRemotoView, ValvulaCerrarRemotoView


urlpatterns = [
    path('graficas/', GraficasView.as_view(), name='api_graficas'),
    path('resumen/', ResumenDashboardView.as_view(), name='api_resumen'),
    path('valvula/<int:id_valvula>/estado/', ValvulaEstadoView.as_view(), name='valvula_estado'),
    path('valvula/<int:id_valvula>/abrir-temporizador/', ValvulaAbrirTemporizadorView.as_view(), name='valvula_abrir'),
    path('valvula/<int:id_valvula>/cancelar/', ValvulaEstadoView.as_view(), name='valvula_cancelar'),
    path('valvula/<int:id_valvula>/abrir-remoto/', ValvulaAbrirRemotoView.as_view(), name='valvula_abrir_remoto'),
    path('valvula/<int:id_valvula>/cerrar-remoto/', ValvulaCerrarRemotoView.as_view(), name='valvula_cerrar_remoto'),
]