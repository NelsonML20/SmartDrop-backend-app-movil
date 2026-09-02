from django.urls import path
from .views_dashboard import GraficasView, ResumenDashboardView

urlpatterns = [
    path('graficas/', GraficasView.as_view(), name='api_graficas'),
    path('resumen/', ResumenDashboardView.as_view(), name='api_resumen'),
]