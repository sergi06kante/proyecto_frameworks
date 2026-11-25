from django.urls import path
from . import views

app_name = "reservas"

urlpatterns = [
    path("", views.EspacioListView.as_view(), name="lista"),
    path("espacios/<int:pk>/", views.EspacioDetailView.as_view(), name="detalle"),
    path("reservas/nueva/", views.ReservaCreateView.as_view(), name="nueva"),
    path("reservas/mias/", views.MisReservasView.as_view(), name="mias"),
]