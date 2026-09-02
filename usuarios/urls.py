from django.urls import path
from .views import RegistroView, LoginView, AdminOnlyView
from .views_vivienda import MisViviendasView, VincularViviendaView
from .views_estado_agua import EstadoAguaView
from .views_consumo import ConsumoView, RetroalimentacionView, RecomendacionesView


urlpatterns = [
    path('registro/', RegistroView.as_view(), name='registro'),
    path('login/', LoginView.as_view(), name='login'),
    path('admin-test/', AdminOnlyView.as_view(), name='admin_test'),
    path('mis-viviendas/', MisViviendasView.as_view(), name='mis_viviendas'),          
    path('vincular-vivienda/', VincularViviendaView.as_view(), name='vincular_vivienda'),
    path('estado-agua/', EstadoAguaView.as_view(), name='estado_agua'),
    path('consumo/', ConsumoView.as_view(), name='consumo'),
    path('retroalimentacion/', RetroalimentacionView.as_view(), name='retroalimentacion'),
    path('recomendaciones/', RecomendacionesView.as_view(), name='recomendaciones'),
]