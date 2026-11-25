import logging
from datetime import date, time, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .consultas import ocupacion
from .middleware import RegistroPeticionesMiddleware
from .models import Espacio, Reserva


class PaginasReservasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.espacio = Espacio.objects.create(
            nombre="Aula de pruebas",
            tipo=Espacio.Tipo.AULA,
            aforo=30,
        )

    def test_permite_espacios_con_el_mismo_nombre(self):
        otro_espacio = Espacio.objects.create(
            nombre=self.espacio.nombre,
            tipo=Espacio.Tipo.AULA,
            aforo=25,
        )

        self.assertNotEqual(self.espacio.pk, otro_espacio.pk)

    def test_listado_usa_la_plantilla_lista(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reservas/lista.html")
        self.assertContains(response, "Espacios disponibles")

    def test_detalle_muestra_un_espacio(self):
        response = self.client.get(self.espacio.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reservas/detalle.html")
        self.assertContains(response, "Aula de pruebas")
        self.assertContains(response, "Próximas reservas confirmadas")
        self.assertContains(response, "No hay reservas confirmadas.")

    def test_listado_no_muestra_espacios_inactivos(self):
        Espacio.objects.create(
            nombre="Pista cerrada",
            tipo=Espacio.Tipo.PISTA,
            aforo=10,
            activo=False,
        )

        response = self.client.get("/")

        self.assertContains(response, "Aula de pruebas")
        self.assertNotContains(response, "Pista cerrada")

    def test_detalle_muestra_solo_reservas_confirmadas_futuras(self):
        usuario = get_user_model().objects.create_user(username="profe1")
        fecha = timezone.localdate() + timedelta(days=1)
        Reserva.objects.create(
            espacio=self.espacio,
            usuario=usuario,
            fecha=fecha,
            hora_inicio=time(9, 0),
            hora_fin=time(10, 0),
            motivo="Clase confirmada",
            estado=Reserva.Estado.CONFIRMADA,
        )
        Reserva.objects.create(
            espacio=self.espacio,
            usuario=usuario,
            fecha=fecha,
            hora_inicio=time(10, 0),
            hora_fin=time(11, 0),
            motivo="Clase pendiente",
        )

        response = self.client.get(self.espacio.get_absolute_url())

        self.assertContains(response, f"{fecha:%d/%m/%Y} de 09:00 a 10:00 (profe1)")
        self.assertNotContains(response, "de 10:00 a 11:00")


class OcupacionTests(TestCase):
    def test_anota_reservas_confirmadas_y_ordena_con_una_consulta(self):
        usuario = get_user_model().objects.create_user(username="profe1")
        fecha = timezone.localdate()
        con_reservas = Espacio.objects.create(
            nombre="Aula B",
            tipo=Espacio.Tipo.AULA,
            aforo=20,
        )
        empatado = Espacio.objects.create(
            nombre="Aula A",
            tipo=Espacio.Tipo.AULA,
            aforo=20,
        )
        sin_reservas = Espacio.objects.create(
            nombre="Aula Cero",
            tipo=Espacio.Tipo.AULA,
            aforo=20,
        )
        inactivo = Espacio.objects.create(
            nombre="Aula inactiva",
            tipo=Espacio.Tipo.AULA,
            aforo=20,
            activo=False,
        )
        for inicio in (time(9, 0), time(10, 0)):
            Reserva.objects.create(
                espacio=con_reservas,
                usuario=usuario,
                fecha=fecha,
                hora_inicio=inicio,
                hora_fin=time(inicio.hour + 1, 0),
                motivo="Clase",
                estado=Reserva.Estado.CONFIRMADA,
            )
        Reserva.objects.create(
            espacio=empatado,
            usuario=usuario,
            fecha=fecha,
            hora_inicio=time(9, 0),
            hora_fin=time(10, 0),
            motivo="Clase",
            estado=Reserva.Estado.CONFIRMADA,
        )

        with self.assertNumQueries(1):
            resultados = list(ocupacion(fecha))

        resultados_con_conteo = [
            (espacio.nombre, espacio.reservas_confirmadas)
            for espacio in resultados
        ]
        self.assertEqual(
            resultados_con_conteo[:2],
            [("Aula B", 2), ("Aula A", 1)],
        )
        sin_confirmadas = [nombre for nombre, conteo in resultados_con_conteo[2:]]
        self.assertEqual(sin_confirmadas, sorted(sin_confirmadas))
        self.assertTrue(
            all(conteo == 0 for _, conteo in resultados_con_conteo[2:])
        )
        self.assertNotIn(inactivo, resultados)
        self.assertIn(sin_reservas, resultados)


class ReservaValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.espacio = Espacio.objects.create(
            nombre="Sala de estudio",
            tipo=Espacio.Tipo.AULA,
            aforo=20,
        )
        cls.usuario = get_user_model().objects.create_user(username="sergio")

    def crear_reserva(self, **kwargs):
        valores = {
            "espacio": self.espacio,
            "usuario": self.usuario,
            "fecha": date(2026, 11, 6),
            "hora_inicio": time(10, 0),
            "hora_fin": time(11, 0),
            "motivo": "Clase",
        }
        valores.update(kwargs)
        return Reserva(**valores)

    def test_rechaza_hora_fin_no_posterior(self):
        reserva = self.crear_reserva(hora_fin=time(10, 0))

        with self.assertRaises(ValidationError) as error:
            reserva.full_clean()

        self.assertIn("hora_fin", error.exception.message_dict)

    def test_rechaza_espacio_inactivo(self):
        self.espacio.activo = False
        self.espacio.save()

        with self.assertRaises(ValidationError) as error:
            self.crear_reserva().full_clean()

        self.assertIn("espacio", error.exception.message_dict)

    def test_rechaza_solape_y_permite_horarios_contiguos(self):
        Reserva.objects.create(
            espacio=self.espacio,
            usuario=self.usuario,
            fecha=date(2026, 11, 6),
            hora_inicio=time(10, 0),
            hora_fin=time(11, 0),
            motivo="Clase",
        )

        with self.assertRaises(ValidationError):
            self.crear_reserva(hora_inicio=time(10, 30), hora_fin=time(11, 30)).full_clean()

        self.crear_reserva(hora_inicio=time(11, 0), hora_fin=time(12, 0)).full_clean()

    def test_ignora_reservas_canceladas_al_comprobar_solapes(self):
        Reserva.objects.create(
            espacio=self.espacio,
            usuario=self.usuario,
            fecha=date(2026, 11, 6),
            hora_inicio=time(10, 0),
            hora_fin=time(11, 0),
            motivo="Clase cancelada",
            estado=Reserva.Estado.CANCELADA,
        )

        self.crear_reserva().full_clean()

    def test_permite_reserva_cancelada_solapada(self):
        Reserva.objects.create(
            espacio=self.espacio,
            usuario=self.usuario,
            fecha=date(2026, 11, 6),
            hora_inicio=time(10, 0),
            hora_fin=time(11, 0),
            motivo="Clase",
        )

        self.crear_reserva(estado=Reserva.Estado.CANCELADA).full_clean()


class ReservaViewsTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="reservista",
            password="clave-de-prueba",
        )
        self.espacio = Espacio.objects.create(
            nombre="Sala de reservas",
            tipo=Espacio.Tipo.AULA,
            aforo=20,
        )

    def test_vistas_de_reservas_requieren_autenticacion(self):
        for ruta in ("/reservas/nueva/", "/reservas/mias/"):
            with self.subTest(ruta=ruta):
                response = self.client.get(ruta)

                self.assertRedirects(
                    response,
                    f"/cuentas/login/?next={ruta}",
                    fetch_redirect_response=False,
                )

    def test_crea_reserva_para_usuario_autenticado(self):
        self.client.force_login(self.usuario)
        fecha = timezone.localdate() + timedelta(days=1)

        response = self.client.post(
            "/reservas/nueva/",
            {
                "espacio": self.espacio.pk,
                "fecha": fecha.isoformat(),
                "hora_inicio": "09:00",
                "hora_fin": "10:00",
                "motivo": "Clase de prueba",
            },
        )

        self.assertRedirects(response, "/reservas/mias/")
        reserva = Reserva.objects.get()
        self.assertEqual(reserva.usuario, self.usuario)
        self.assertEqual(reserva.espacio, self.espacio)

    def test_formulario_reutiliza_validacion_de_solapamiento_del_modelo(self):
        self.client.force_login(self.usuario)
        fecha = timezone.localdate() + timedelta(days=1)
        Reserva.objects.create(
            espacio=self.espacio,
            usuario=self.usuario,
            fecha=fecha,
            hora_inicio=time(9, 0),
            hora_fin=time(10, 0),
            motivo="Reserva existente",
        )

        response = self.client.post(
            "/reservas/nueva/",
            {
                "espacio": self.espacio.pk,
                "fecha": fecha.isoformat(),
                "hora_inicio": "09:30",
                "hora_fin": "10:30",
                "motivo": "Reserva solapada",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "El espacio ya tiene una reserva en ese horario.")
        self.assertEqual(Reserva.objects.count(), 1)

    def test_formulario_no_ofrece_espacios_inactivos(self):
        self.client.force_login(self.usuario)
        inactivo = Espacio.objects.create(
            nombre="Sala cerrada",
            tipo=Espacio.Tipo.AULA,
            aforo=20,
            activo=False,
        )

        response = self.client.get("/reservas/nueva/")

        self.assertContains(response, "Sala de reservas")
        self.assertNotContains(response, inactivo.nombre)

    def test_mis_reservas_solo_muestra_reservas_del_usuario(self):
        otro_usuario = get_user_model().objects.create_user(username="otro")
        Reserva.objects.create(
            espacio=self.espacio,
            usuario=self.usuario,
            fecha=timezone.localdate(),
            hora_inicio=time(9, 0),
            hora_fin=time(10, 0),
            motivo="Mi reserva",
        )
        Reserva.objects.create(
            espacio=self.espacio,
            usuario=otro_usuario,
            fecha=timezone.localdate(),
            hora_inicio=time(10, 0),
            hora_fin=time(11, 0),
            motivo="Reserva ajena",
        )
        self.client.force_login(self.usuario)

        response = self.client.get("/reservas/mias/")

        self.assertContains(response, "Mis reservas")
        self.assertContains(response, "Mi reserva")
        self.assertNotContains(response, "Reserva ajena")


class CargarDatosCommandTests(TestCase):
    def test_carga_reemplaza_reservas_y_es_idempotente(self):
        usuario = get_user_model().objects.create_user(username="temporal")
        usuario_existente = get_user_model().objects.create_user(
            username="profe1",
            password="old-test-password",
            is_staff=True,
            is_active=False,
        )
        espacio = Espacio.objects.create(
            nombre="Espacio temporal",
            tipo=Espacio.Tipo.AULA,
            aforo=10,
        )
        Reserva.objects.create(
            espacio=espacio,
            usuario=usuario,
            fecha=date(2027, 5, 20),
            hora_inicio=time(15, 0),
            hora_fin=time(16, 0),
            motivo="Debe ser eliminada",
        )

        salida = StringIO()
        with patch.dict(
            "os.environ",
            {"RESERVAS_DEFAULT_PASSWORD": "test-password"},
        ):
            call_command("cargar_datos", stdout=salida)

        self.assertEqual(salida.getvalue(), "Cargados 5 espacios y 6 reservas\n")
        self.assertEqual(Reserva.objects.count(), 6)
        self.assertFalse(Reserva.objects.filter(motivo="Debe ser eliminada").exists())

        nombres_espacios = [
            "Aula 12",
            "Laboratorio de Física",
            "Salón de actos",
            "Pista polideportiva",
            "Aula 3",
        ]
        espacios_cargados = list(
            Espacio.objects.filter(nombre__in=nombres_espacios).order_by("pk")
        )
        self.assertEqual(
            [espacio.nombre for espacio in espacios_cargados],
            nombres_espacios,
        )
        self.assertEqual(
            [
                (espacio.tipo, espacio.aforo, espacio.activo)
                for espacio in espacios_cargados
            ],
            [
                (Espacio.Tipo.AULA, 30, True),
                (Espacio.Tipo.LABORATORIO, 24, True),
                (Espacio.Tipo.SALON, 200, True),
                (Espacio.Tipo.PISTA, 60, True),
                (Espacio.Tipo.AULA, 25, False),
            ],
        )

        usuarios = get_user_model().objects
        self.assertTrue(
            usuarios.get(username="profe1").check_password("test-password")
        )
        self.assertFalse(usuarios.get(username="profe1").is_staff)
        self.assertTrue(
            usuarios.get(username="profe2").check_password("test-password")
        )
        self.assertFalse(usuarios.get(username="profe2").is_staff)
        self.assertTrue(
            usuarios.get(username="conserje").check_password("test-password")
        )
        self.assertTrue(usuarios.get(username="conserje").is_staff)
        usuario_existente.refresh_from_db()
        self.assertTrue(usuario_existente.check_password("test-password"))
        self.assertFalse(usuario_existente.is_staff)
        self.assertTrue(usuario_existente.is_active)

        reservas_cargadas = [
            (
                reserva.espacio.nombre,
                reserva.fecha,
                reserva.hora_inicio,
                reserva.hora_fin,
                reserva.usuario.username,
                reserva.estado,
                reserva.motivo,
            )
            for reserva in Reserva.objects.select_related(
                "espacio", "usuario"
            ).order_by("pk")
        ]
        self.assertEqual(
            reservas_cargadas,
            [
                (
                    "Aula 12",
                    date(2027, 5, 20),
                    time(9, 0),
                    time(10, 0),
                    "profe1",
                    Reserva.Estado.CONFIRMADA,
                    "Examen de Matemáticas",
                ),
                (
                    "Aula 12",
                    date(2027, 5, 20),
                    time(10, 0),
                    time(11, 0),
                    "profe2",
                    Reserva.Estado.CONFIRMADA,
                    "Tutoría de 2.º DAW",
                ),
                (
                    "Salón de actos",
                    date(2027, 5, 20),
                    time(12, 0),
                    time(14, 0),
                    "profe1",
                    Reserva.Estado.PENDIENTE,
                    "Charla de orientación",
                ),
                (
                    "Laboratorio de Física",
                    date(2027, 5, 24),
                    time(8, 30),
                    time(10, 20),
                    "profe2",
                    Reserva.Estado.CONFIRMADA,
                    "Práctica de óptica",
                ),
                (
                    "Pista polideportiva",
                    date(2027, 5, 24),
                    time(11, 15),
                    time(12, 10),
                    "profe1",
                    Reserva.Estado.CANCELADA,
                    "Torneo de recreo",
                ),
                (
                    "Aula 12",
                    date(2027, 5, 24),
                    time(9, 0),
                    time(10, 0),
                    "profe1",
                    Reserva.Estado.PENDIENTE,
                    "Recuperación",
                ),
            ],
        )

        salida = StringIO()
        with patch.dict(
            "os.environ",
            {"RESERVAS_DEFAULT_PASSWORD": "test-password"},
        ):
            call_command("cargar_datos", stdout=salida)

        self.assertEqual(salida.getvalue(), "Cargados 5 espacios y 6 reservas\n")
        self.assertEqual(Reserva.objects.count(), 6)

    def test_sin_contrasena_configurada_no_borra_reservas(self):
        usuario = get_user_model().objects.create_user(username="temporal")
        espacio = Espacio.objects.create(
            nombre="Espacio temporal",
            tipo=Espacio.Tipo.AULA,
            aforo=10,
        )
        Reserva.objects.create(
            espacio=espacio,
            usuario=usuario,
            fecha=date(2027, 5, 20),
            hora_inicio=time(15, 0),
            hora_fin=time(16, 0),
            motivo="Debe conservarse",
        )

        with patch.dict("os.environ", {"RESERVAS_DEFAULT_PASSWORD": ""}):
            with self.assertRaises(CommandError):
                call_command("cargar_datos", stdout=StringIO())

        self.assertTrue(Reserva.objects.filter(motivo="Debe conservarse").exists())


class ReservasApiTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="apiuser",
            password="test-password",
        )
        self.espacio = Espacio.objects.create(
            nombre="Espacio API",
            tipo=Espacio.Tipo.AULA,
            aforo=25,
        )
        self.client = APIClient()

    def test_lista_de_espacios_filtra_por_tipo_y_activo(self):
        inactivo = Espacio.objects.create(
            nombre="Aula inactiva API",
            tipo=Espacio.Tipo.AULA,
            aforo=15,
            activo=False,
        )
        Espacio.objects.create(
            nombre="Laboratorio API",
            tipo=Espacio.Tipo.LABORATORIO,
            aforo=15,
        )

        response = self.client.get(
            "/api/espacios/",
            {"tipo": "aula", "activo": "true"},
        )

        self.assertEqual(response.status_code, 200)
        nombres = [item["nombre"] for item in response.data]
        self.assertIn(self.espacio.nombre, nombres)
        self.assertNotIn(inactivo.nombre, nombres)
        self.assertNotIn("Laboratorio API", nombres)

    def test_ocupacion_requiere_fecha_iso_y_devuelve_conteo(self):
        response_sin_fecha = self.client.get("/api/espacios/ocupacion/")

        self.assertEqual(response_sin_fecha.status_code, 400)
        self.assertEqual(
            response_sin_fecha.data["detail"],
            "Falta el parámetro fecha (AAAA-MM-DD).",
        )

        response_mal_fecha = self.client.get(
            "/api/espacios/ocupacion/",
            {"fecha": "20-05-2027"},
        )
        self.assertEqual(response_mal_fecha.status_code, 400)
        self.assertEqual(
            str(response_mal_fecha.data["fecha"]),
            "Formato de fecha no válido (AAAA-MM-DD).",
        )

        response = self.client.get(
            "/api/espacios/ocupacion/",
            {"fecha": "2027-05-20"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            all(
                set(item) == {"id", "nombre", "reservas_confirmadas"}
                for item in response.data
            )
        )

    def test_reservas_filtran_por_fecha_espacio_y_estado(self):
        fecha = date(2027, 5, 20)
        Reserva.objects.create(
            espacio=self.espacio,
            usuario=self.usuario,
            fecha=fecha,
            hora_inicio=time(9, 0),
            hora_fin=time(10, 0),
            motivo="Filtro API",
            estado=Reserva.Estado.CONFIRMADA,
        )
        self.client.force_authenticate(self.usuario)

        response = self.client.get(
            "/api/reservas/",
            {
                "fecha": "2027-05-20",
                "espacio": str(self.espacio.pk),
                "estado": Reserva.Estado.CONFIRMADA,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["motivo"], "Filtro API")
        self.assertEqual(response.data[0]["usuario"], "apiuser")
        self.assertEqual(response.data[0]["espacio_nombre"], self.espacio.nombre)

    def test_reservas_rechazan_filtros_invalidos(self):
        self.client.force_authenticate(self.usuario)
        for filtros, campo in (
            ({"fecha": "20-05-2027"}, "fecha"),
            ({"fecha": ""}, "fecha"),
            ({"espacio": "uno"}, "espacio"),
            ({"espacio": ""}, "espacio"),
        ):
            with self.subTest(filtros=filtros):
                response = self.client.get("/api/reservas/", filtros)

                self.assertEqual(response.status_code, 400)
                self.assertIn(campo, response.data)

    def test_crear_reserva_usa_usuario_autenticado_y_clean_modelo(self):
        self.client.force_authenticate(self.usuario)
        datos = {
            "espacio": self.espacio.pk,
            "fecha": "2027-05-20",
            "hora_inicio": "09:00",
            "hora_fin": "10:00",
            "motivo": "Creada por API",
        }

        response = self.client.post("/api/reservas/", datos, format="json")

        self.assertEqual(response.status_code, 201)
        reserva = Reserva.objects.get(motivo="Creada por API")
        self.assertEqual(reserva.usuario, self.usuario)
        self.assertEqual(response.data["usuario"], self.usuario.username)
        self.assertEqual(response.data["estado"], Reserva.Estado.PENDIENTE)

        datos.update(
            {
                "hora_inicio": "09:30",
                "hora_fin": "10:30",
                "motivo": "Solapada por API",
            }
        )
        response_solapada = self.client.post(
            "/api/reservas/",
            datos,
            format="json",
        )

        self.assertEqual(response_solapada.status_code, 400)
        self.assertIn("non_field_errors", response_solapada.data)

    def test_borrar_espacio_protegido_devuelve_409(self):
        personal = get_user_model().objects.create_user(
            username="personal-borrado",
            is_staff=True,
        )
        Reserva.objects.create(
            espacio=self.espacio,
            usuario=self.usuario,
            fecha=date(2027, 5, 20),
            hora_inicio=time(9, 0),
            hora_fin=time(10, 0),
            motivo="Protege el espacio",
        )
        self.client.force_authenticate(personal)

        response = self.client.delete(f"/api/espacios/{self.espacio.pk}/")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.data["detail"],
            "El espacio tiene reservas y no se puede borrar.",
        )

    def test_token_endpoint_autentica_y_token_permite_escritura(self):
        response = self.client.post(
            "/api/token/",
            {"username": "apiuser", "password": "test-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {response.data['token']}"
        )
        response_creacion = self.client.post(
            "/api/reservas/",
            {
                "espacio": self.espacio.pk,
                "fecha": "2027-05-20",
                "hora_inicio": "09:00",
                "hora_fin": "10:00",
                "motivo": "Creada con token",
            },
            format="json",
        )

        self.assertEqual(response_creacion.status_code, 201)
        self.assertEqual(
            Reserva.objects.get(motivo="Creada con token").usuario,
            self.usuario,
        )

    def test_cors_permite_preflight_desde_frontend_local(self):
        response = self.client.options(
            "/api/espacios/",
            HTTP_ORIGIN="http://localhost:5173",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Access-Control-Allow-Origin"],
            "http://localhost:5173",
        )

    def test_solo_personal_puede_escribir_espacios(self):
        self.client.force_authenticate(self.usuario)
        response_usuario = self.client.post(
            "/api/espacios/",
            {
                "nombre": "Espacio no permitido",
                "tipo": Espacio.Tipo.AULA,
                "aforo": 20,
                "activo": True,
            },
            format="json",
        )

        self.assertEqual(response_usuario.status_code, 403)

        personal = get_user_model().objects.create_user(
            username="personal",
            is_staff=True,
        )
        self.client.force_authenticate(personal)
        response_personal = self.client.post(
            "/api/espacios/",
            {
                "nombre": "Espacio de personal",
                "tipo": Espacio.Tipo.AULA,
                "aforo": 20,
                "activo": True,
            },
            format="json",
        )

        self.assertEqual(response_personal.status_code, 201)

    def test_solo_propietario_puede_modificar_o_borrar_reserva(self):
        reserva = Reserva.objects.create(
            espacio=self.espacio,
            usuario=self.usuario,
            fecha=date(2027, 5, 20),
            hora_inicio=time(9, 0),
            hora_fin=time(10, 0),
            motivo="Reserva propietaria",
        )
        otro_usuario = get_user_model().objects.create_user(username="otro-api")
        self.client.force_authenticate(otro_usuario)

        response_ajeno = self.client.patch(
            f"/api/reservas/{reserva.pk}/",
            {"motivo": "Cambio ajeno"},
            format="json",
        )
        self.assertEqual(response_ajeno.status_code, 403)

        personal = get_user_model().objects.create_user(
            username="personal-api",
            is_staff=True,
        )
        self.client.force_authenticate(personal)
        response_personal = self.client.delete(f"/api/reservas/{reserva.pk}/")
        self.assertEqual(response_personal.status_code, 403)

        self.client.force_authenticate(self.usuario)
        response_propietario = self.client.patch(
            f"/api/reservas/{reserva.pk}/",
            {"motivo": "Cambio del propietario"},
            format="json",
        )
        self.assertEqual(response_propietario.status_code, 200)
        reserva.refresh_from_db()
        self.assertEqual(reserva.motivo, "Cambio del propietario")


class RegistroPeticionesMiddlewareTests(TestCase):
    def test_registra_metodo_ruta_y_estado(self):
        middleware = RegistroPeticionesMiddleware(
            lambda _: HttpResponse(status=201)
        )
        request = RequestFactory().get("/peticion-de-prueba/")

        with self.assertLogs("reservas.peticiones", level=logging.INFO) as logs:
            response = middleware(request)

        self.assertEqual(response.status_code, 201)
        self.assertIn("GET /peticion-de-prueba/ 201", logs.output[0])
