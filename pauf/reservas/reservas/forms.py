from django import forms

from .models import Espacio, Reserva


class ReservaForm(forms.ModelForm):
    class Meta:
        model = Reserva
        fields = ["espacio", "fecha", "hora_inicio", "hora_fin", "motivo"]
        labels = {
            "hora_inicio": "Hora de inicio",
            "hora_fin": "Hora de fin",
        }
        widgets = {
            "fecha": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "hora_inicio": forms.TimeInput(
                attrs={"type": "time"},
                format="%H:%M",
            ),
            "hora_fin": forms.TimeInput(
                attrs={"type": "time"},
                format="%H:%M",
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["espacio"].queryset = Espacio.objects.filter(activo=True)
