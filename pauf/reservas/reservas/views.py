from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView

from .forms import ReservaForm
from .models import Espacio, Reserva


class EspacioListView(ListView):
    model = Espacio
    template_name = "reservas/lista.html"
    context_object_name = "espacios"

    def get_queryset(self):
        return Espacio.objects.filter(activo=True)


class EspacioDetailView(DetailView):
    model = Espacio
    template_name = "reservas/detalle.html"
    context_object_name = "espacio"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reservas"] = (
            self.object.reservas.filter(
                estado=Reserva.Estado.CONFIRMADA,
                fecha__gte=timezone.localdate(),
            )
            .select_related("usuario")
        )
        return context


class ReservaCreateView(LoginRequiredMixin, CreateView):
    model = Reserva
    form_class = ReservaForm
    template_name = "reservas/reserva_form.html"
    success_url = reverse_lazy("reservas:mias")

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        return super().form_valid(form)


class MisReservasView(LoginRequiredMixin, ListView):
    model = Reserva
    template_name = "reservas/mis_reservas.html"
    context_object_name = "reservas"

    def get_queryset(self):
        return (
            Reserva.objects.filter(usuario=self.request.user)
            .select_related("espacio")
        )