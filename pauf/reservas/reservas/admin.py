from django.contrib import admin

from .models import Espacio, Reserva


@admin.register(Espacio)
class EspacioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "aforo", "activo")
    list_filter = ("tipo", "activo")
    search_fields = ("nombre",)


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = (
        "espacio",
        "fecha",
        "hora_inicio",
        "hora_fin",
        "usuario",
        "estado",
    )
    list_filter = ("estado", "espacio", "fecha")
    search_fields = ("motivo", "usuario__username")
    list_select_related = ("espacio", "usuario")
    readonly_fields = ("creada",)
