import io
import unittest

from sqlalchemy import inspect, text

from app import create_app
from extensions import db


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "SQLALCHEMY_ENGINE_OPTIONS": {},
                "JWT_SECRET_KEY": "test-secret",
                "CORS_ORIGINS": ["http://localhost"],
            }
        )
        self.client = self.app.test_client()
        for table_name in (
            "afectacion_variables",
            "afectacion_variable_registros",
            "afectacion_variable_registro_detalles",
            "afectaciones_registros",
            "afectaciones_variable_registros",
            "evento_subtipos",
            "evento_tipos",
            "eventos",
            "mesas",
        ):
            table = db.metadata.tables.get(table_name)
            if table is not None:
                db.metadata.remove(table)
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def register(self):
        return self.client.post(
            "/api/usuarios/register",
            json={
                "institucion_id": 999,
                "usuario": "admin",
                "correo": "admin@example.com",
                "clave": "ClaveSegura123",
                "nombres": "Usuario",
                "apellidos": "Administrador",
            },
        )

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["estado"], "OK")

    def test_swagger_spec_contains_api_routes(self):
        response = self.client.get("/apispec_1.json")
        self.assertEqual(response.status_code, 200)
        paths = response.get_json()["paths"]
        self.assertIn("/api/usuarios/login", paths)
        self.assertIn("/api/usuarios", paths)
        self.assertIn("/api/institucion-categorias", paths)
        self.assertIn("/api/instituciones", paths)
        self.assertIn("/api/ubicaciones/importar", paths)
        self.assertIn("/api/eventos/provincia/{provincia_id}", paths)
        self.assertIn("/api/provincias/provincia/{provincia_id}", paths)
        self.assertIn("/api/eventos/afectaciones/provincias", paths)
        self.assertIn(
            "provincia_id",
            [parameter["name"] for parameter in paths["/api/eventos"]["get"]["parameters"]],
        )
        self.assertIn(
            "provincia_id",
            [parameter["name"] for parameter in paths["/api/provincias"]["get"]["parameters"]],
        )
        self.assertNotIn("/api/riesgos", paths)

    def test_register_login_and_me(self):
        registered = self.register()
        self.assertEqual(registered.status_code, 201)
        token = registered.get_json()["token"]

        me = self.client.get(
            "/api/usuarios/me", headers={"Authorization": token}
        )
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.get_json()["usuario"], "admin")
        self.assertEqual(me.get_json()["nombre_completo"], "Usuario Administrador")
        self.assertNotIn("clave", me.get_json())

        me_with_bearer = self.client.get(
            "/api/usuarios/me", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(me_with_bearer.status_code, 200)

        login = self.client.post(
            "/api/usuarios/login",
            json={"usuario": "admin", "clave": "ClaveSegura123"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("token", login.get_json())

    def test_institution_tables_crud_requires_token(self):
        unauthorized = self.client.get("/api/instituciones")
        self.assertEqual(unauthorized.status_code, 401)

        token = self.register().get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        category_created = self.client.post(
            "/api/institucion-categorias",
            headers=headers,
            json={
                "nombre": "Gobierno central",
                "descripcion": "Entidades nacionales",
            },
        )
        self.assertEqual(category_created.status_code, 201)
        category = category_created.get_json()

        institution_created = self.client.post(
            "/api/instituciones",
            headers=headers,
            json={
                "institucion_categoria_id": category["id"],
                "nombre": "Consejo Nacional Electoral",
                "siglas": "CNE",
            },
        )
        self.assertEqual(institution_created.status_code, 201)
        institution = institution_created.get_json()

        category_list = self.client.get(
            "/api/institucion-categorias", headers=headers
        )
        self.assertEqual(category_list.status_code, 200)
        self.assertEqual(len(category_list.get_json()), 1)

        institution_get = self.client.get(
            f"/api/instituciones/{institution['id']}", headers=headers
        )
        self.assertEqual(institution_get.status_code, 200)

        updated = self.client.patch(
            f"/api/instituciones/{institution['id']}",
            headers=headers,
            json={"observaciones": "Actualizada"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["observaciones"], "Actualizada")

        category_in_use = self.client.delete(
            f"/api/institucion-categorias/{category['id']}", headers=headers
        )
        self.assertEqual(category_in_use.status_code, 409)

        institution_deleted = self.client.delete(
            f"/api/instituciones/{institution['id']}", headers=headers
        )
        self.assertEqual(institution_deleted.status_code, 204)

        category_deleted = self.client.delete(
            f"/api/institucion-categorias/{category['id']}", headers=headers
        )
        self.assertEqual(category_deleted.status_code, 204)

    def test_create_institution_rejects_unknown_category(self):
        token = self.register().get_json()["token"]
        response = self.client.post(
            "/api/instituciones",
            headers={"Authorization": token},
            json={"institucion_categoria_id": 999, "nombre": "Sin categoría"},
        )
        self.assertEqual(response.status_code, 404)

    def test_base_users_post_creates_user(self):
        response = self.client.post(
            "/api/usuarios",
            json={
                "institucion_id": 1,
                "usuario": "base-route",
                "clave": "ClaveSegura123",
            },
        )
        self.assertEqual(response.status_code, 201)

    def test_validation_errors_are_json(self):
        response = self.client.post(
            "/api/usuarios/register",
            json={"usuario": "a", "correo": "no-es-correo", "clave": "123"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("detalles", response.get_json())

    def test_generic_resource_crud_requires_token(self):
        with self.app.app_context():
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS provincias (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        dpa VARCHAR(10) NOT NULL UNIQUE,
                        nombre VARCHAR(100) NOT NULL,
                        abreviatura VARCHAR(10),
                        activo BOOLEAN DEFAULT 1,
                        creador VARCHAR(100),
                        creacion TIMESTAMP,
                        modificador VARCHAR(100),
                        modificacion TIMESTAMP
                    )
                    """
                )
            )
            db.session.commit()

        unauthorized = self.client.get("/api/provincias")
        self.assertEqual(unauthorized.status_code, 401)

        token = self.register().get_json()["token"]
        headers = {"Authorization": token}

        created = self.client.post(
            "/api/provincias",
            headers=headers,
            json={"dpa": "1", "nombre": "AZUAY", "abreviatura": "AZU"},
        )
        self.assertEqual(created.status_code, 201)
        provincia = created.get_json()
        self.assertEqual(provincia["dpa"], "01")
        self.assertEqual(provincia["creador"], "admin")

        listed = self.client.get("/api/provincias", headers=headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.get_json()), 1)

        updated = self.client.patch(
            f"/api/provincias/{provincia['id']}",
            headers=headers,
            json={"nombre": "Azuay"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["nombre"], "Azuay")

        deleted = self.client.delete(
            f"/api/provincias/{provincia['id']}",
            headers=headers,
        )
        self.assertEqual(deleted.status_code, 204)

    def test_list_provincias_by_provincia_id(self):
        with self.app.app_context():
            db.session.execute(
                text(
                    """
                    INSERT INTO provincias (id, dpa, nombre)
                    VALUES (13, '13', 'MANABI'), (9, '09', 'GUAYAS')
                    """
                )
            )
            db.session.commit()

        token = self.register().get_json()["token"]
        response = self.client.get(
            "/api/provincias/provincia/13",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        provincias = response.get_json()
        self.assertEqual(len(provincias), 1)
        self.assertEqual(provincias[0]["id"], 13)
        self.assertEqual(provincias[0]["nombre"], "MANABI")

        filtered_list = self.client.get(
            "/api/provincias?provincia_id=13",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(filtered_list.status_code, 200)
        self.assertEqual(filtered_list.get_json(), provincias)

    def test_list_eventos_by_provincia_id(self):
        with self.app.app_context():
            db.session.execute(
                text(
                    """
                    CREATE TABLE eventos (
                        id INTEGER PRIMARY KEY,
                        provincia_id INTEGER NOT NULL,
                        sector VARCHAR(1000)
                    )
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO provincias (id, dpa, nombre)
                    VALUES (13, '13', 'MANABI'), (9, '09', 'GUAYAS')
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO eventos (id, provincia_id, sector)
                    VALUES (1, 13, 'Norte'), (2, 9, 'Sur'), (3, 13, 'Centro')
                    """
                )
            )
            db.session.commit()

        token = self.register().get_json()["token"]
        response = self.client.get(
            "/api/eventos/provincia/13",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        eventos = response.get_json()
        self.assertEqual([evento["id"] for evento in eventos], [1, 3])
        self.assertEqual({evento["provincia_id"] for evento in eventos}, {13})
        self.assertEqual(eventos[0]["provincia_nombre"], "MANABI")

        filtered_list = self.client.get(
            "/api/eventos?provincia_id=13",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(filtered_list.status_code, 200)
        self.assertEqual(filtered_list.get_json(), eventos)

    def test_list_event_affectations_summary_by_province(self):
        with self.app.app_context():
            db.session.execute(
                text(
                    """
                    INSERT INTO provincias (id, dpa, nombre)
                    VALUES
                        (1, '01', 'AZUAY'),
                        (9, '09', 'GUAYAS'),
                        (13, '13', 'MANABI')
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    CREATE TABLE eventos (
                        id INTEGER PRIMARY KEY,
                        emergencia_id INTEGER NOT NULL,
                        provincia_id INTEGER NOT NULL,
                        canton_id INTEGER NOT NULL,
                        evento_fecha TIMESTAMP NOT NULL,
                        afectacion_variable_id INTEGER NOT NULL
                    )
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    CREATE TABLE afectacion_variables (
                        id INTEGER PRIMARY KEY,
                        nombre VARCHAR(255) NOT NULL
                    )
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO afectacion_variables (id, nombre)
                    VALUES
                        (1, 'Personas Fallecidas'),
                        (2, 'Personas heridas'),
                        (3, 'Personas afectadas'),
                        (4, 'Viviendas afectadas'),
                        (5, 'Viviendas destruidas'),
                        (6, 'Recintos afectados'),
                        (7, 'Puentes afectados'),
                        (8, 'Metros lineales de vias afectadas'),
                        (9, 'No debe salir'),
                        (10, 'Familias afectadas'),
                        (11, 'Recintos destruidos'),
                        (12, 'Bien publico afectado'),
                        (13, 'Bien publico destruido'),
                        (14, 'Bien privado afectado'),
                        (15, 'Bien privado destruido'),
                        (16, 'Puentes destruidos'),
                        (17, 'Vias de primer orden'),
                        (18, 'Vias de segundo orden'),
                        (19, 'Vias de tercer orden'),
                        (20, 'Ha Cultivos afectados'),
                        (21, 'Ha Cultivos perdidos'),
                        (22, 'Animales afectados'),
                        (23, 'Animales muertos')
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO eventos (
                        id,
                        emergencia_id,
                        provincia_id,
                        canton_id,
                        evento_fecha,
                        afectacion_variable_id
                    )
                    VALUES
                        (1, 8, 13, 1301, '2025-11-16 08:00:00', 1),
                        (2, 8, 13, 1301, '2025-11-16 09:00:00', 2),
                        (3, 8, 13, 1301, '2025-11-16 10:00:00', 3),
                        (4, 8, 13, 1301, '2025-11-16 11:00:00', 4),
                        (5, 8, 13, 1301, '2025-11-16 12:00:00', 5),
                        (6, 8, 13, 1301, '2025-11-16 13:00:00', 6),
                        (7, 8, 13, 1301, '2025-11-16 14:00:00', 7),
                        (8, 8, 13, 1301, '2025-11-16 15:00:00', 8),
                        (9, 8, 13, 1301, '2025-11-16 16:00:00', 9),
                        (10, 8, 13, 1301, '2025-11-16 17:00:00', 10),
                        (11, 8, 13, 1301, '2025-11-16 18:00:00', 11),
                        (12, 8, 13, 1301, '2025-11-16 19:00:00', 12),
                        (13, 8, 13, 1301, '2025-11-16 20:00:00', 13),
                        (14, 8, 13, 1301, '2025-11-16 21:00:00', 14),
                        (15, 8, 13, 1301, '2025-11-16 22:00:00', 15),
                        (16, 8, 13, 1301, '2025-11-16 23:00:00', 16),
                        (17, 8, 13, 1301, '2025-11-16 23:01:00', 17),
                        (18, 8, 13, 1301, '2025-11-16 23:02:00', 18),
                        (19, 8, 13, 1301, '2025-11-16 23:03:00', 19),
                        (20, 8, 13, 1301, '2025-11-16 23:04:00', 20),
                        (21, 8, 13, 1301, '2025-11-16 23:05:00', 21),
                        (22, 8, 13, 1301, '2025-11-16 23:06:00', 22),
                        (23, 8, 13, 1301, '2025-11-16 23:07:00', 23),
                        (24, 9, 13, 1301, '2025-11-18 11:00:00', 1),
                        (25, 8, 9, 901, '2025-11-17 10:00:00', 6),
                        (26, 8, 9, 901, '2025-11-17 11:00:00', 11),
                        (27, 8, 9, 901, '2025-11-17 12:00:00', 1)
                    """
                )
            )
            db.session.commit()

        token = self.register().get_json()["token"]
        response = self.client.get(
            "/api/eventos/afectaciones/provincias",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        summary = {row["provincia_id"]: row for row in response.get_json()}
        self.assertEqual(summary[1]["evento"], 0)
        self.assertEqual(summary[13]["provincia"], "MANABI")
        self.assertEqual(summary[13]["evento"], 24)
        self.assertEqual(summary[13]["personas_fallecidas"], 2)
        self.assertEqual(summary[13]["personas_heridas"], 1)
        self.assertEqual(summary[13]["personas_afectadas"], 1)
        self.assertEqual(summary[13]["viviendas_afectadas"], 1)
        self.assertEqual(summary[13]["viviendas_destruidas"], 1)
        self.assertEqual(summary[13]["recintos_electorales_afectados"], 1)
        self.assertEqual(summary[13]["recintos_electorales_destruidos"], 1)
        self.assertEqual(summary[13]["familias_afectadas"], 1)
        self.assertEqual(summary[13]["bien_publico_afectado"], 1)
        self.assertEqual(summary[13]["bien_publico_destruido"], 1)
        self.assertEqual(summary[13]["bien_privado_afectado"], 1)
        self.assertEqual(summary[13]["bien_privado_destruido"], 1)
        self.assertEqual(summary[13]["puentes_afectados"], 1)
        self.assertEqual(summary[13]["puentes_destruidos"], 1)
        self.assertEqual(summary[13]["vias_primer_orden"], 1)
        self.assertEqual(summary[13]["vias_segundo_orden"], 1)
        self.assertEqual(summary[13]["vias_tercer_orden"], 1)
        self.assertEqual(summary[13]["metros_lineales_vias_afectadas"], 1)
        self.assertEqual(summary[13]["hectareas_cultivos_afectados"], 1)
        self.assertEqual(summary[13]["hectareas_cultivos_perdidos"], 1)
        self.assertEqual(summary[13]["animales_afectados"], 1)
        self.assertEqual(summary[13]["animales_muertos"], 1)
        self.assertEqual(summary[9]["personas_fallecidas"], 1)
        self.assertEqual(summary[9]["recintos_electorales_afectados"], 1)
        self.assertEqual(summary[9]["recintos_electorales_destruidos"], 1)

        filtered = self.client.get(
            "/api/eventos/afectaciones/provincias?emergencia_id=8",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(filtered.status_code, 200)
        filtered_summary = {row["provincia_id"]: row for row in filtered.get_json()}
        self.assertEqual(filtered_summary[13]["evento"], 23)
        self.assertEqual(filtered_summary[13]["personas_fallecidas"], 1)
        self.assertEqual(filtered_summary[9]["evento"], 3)

        filtered_by_province = self.client.get(
            "/api/eventos/afectaciones/provincias?provincia_id=13",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(filtered_by_province.status_code, 200)
        province_rows = filtered_by_province.get_json()
        self.assertEqual(len(province_rows), 1)
        self.assertEqual(province_rows[0]["provincia_id"], 13)
        self.assertEqual(province_rows[0]["evento"], 24)

        filtered_by_guayas = self.client.get(
            "/api/eventos/afectaciones/provincias?provincia_id=9",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(filtered_by_guayas.status_code, 200)
        guayas_rows = filtered_by_guayas.get_json()
        self.assertEqual(len(guayas_rows), 1)
        self.assertEqual(guayas_rows[0]["provincia"], "GUAYAS")
        self.assertEqual(guayas_rows[0]["recintos_electorales_afectados"], 1)
        self.assertEqual(guayas_rows[0]["recintos_electorales_destruidos"], 1)

        filtered_by_canton = self.client.get(
            "/api/eventos/afectaciones/provincias?canton_id=1301",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(filtered_by_canton.status_code, 200)
        canton_summary = {row["provincia_id"]: row for row in filtered_by_canton.get_json()}
        self.assertEqual(canton_summary[13]["evento"], 24)
        self.assertEqual(canton_summary[13]["personas_fallecidas"], 2)

        filtered_by_date = self.client.get(
            "/api/eventos/afectaciones/provincias?fecha_inicio=2025-11-16&fecha_fin=2025-11-16",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(filtered_by_date.status_code, 200)
        date_summary = {row["provincia_id"]: row for row in filtered_by_date.get_json()}
        self.assertEqual(date_summary[13]["evento"], 23)
        self.assertEqual(date_summary[13]["personas_fallecidas"], 1)
        self.assertEqual(date_summary[13]["personas_heridas"], 1)

    def test_import_dpa_replaces_hierarchy_and_restarts_ids(self):
        csv_content = """COD_PROVINCIA;NOMBRE_PROVINCIA;COD_CANTON;NOMBRE_CANTON;COD_PARROQUIA;NOMBRE_PARROQUIA;COD_ZONA;NOMBRE_ZONA;Total_Recintos
1;AZUAY;260;CUENCA;285;BAÑOS;0;(en blanco);2
1;AZUAY;260;CUENCA;285;BAÑOS;1;BAÑOS;4
2;BOLIVAR;30;GUARANDA;15;ANGEL POLIBIO;1;CENTRO;3
""".encode("utf-8")
        token = self.register().get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = self.client.post(
            "/api/ubicaciones/importar",
            headers=headers,
            data={"archivo": (io.BytesIO(csv_content), "maestro_dpa.csv")},
        )
        self.assertEqual(response.status_code, 200)
        summary = response.get_json()
        self.assertEqual(summary["modo"], "reemplazo")
        self.assertEqual(summary["filas_procesadas"], 3)
        self.assertEqual(
            summary["provincias"],
            {"eliminados": 0, "creados": 2, "actualizados": 0},
        )
        self.assertEqual(summary["cantones"]["creados"], 2)
        self.assertEqual(summary["parroquias"]["creados"], 2)
        self.assertEqual(summary["zonas"]["creados"], 3)

        provinces = self.client.get("/api/provincias", headers=headers).get_json()
        azuay = next(province for province in provinces if province["dpa"] == "01")
        self.assertEqual(azuay["id"], 1)
        cantons = self.client.get(
            f"/api/cantones/provincia/{azuay['id']}", headers=headers
        ).get_json()
        parishes = self.client.get(
            f"/api/parroquias/canton/{cantons[0]['id']}", headers=headers
        ).get_json()
        self.assertEqual((cantons[0]["id"], cantons[0]["dpa"]), (1260, "01260"))
        self.assertEqual(
            (parishes[0]["id"], parishes[0]["dpa"], parishes[0]["canton_id"]),
            (12600285, "012600285", 1260),
        )
        zones = self.client.get(
            f"/api/zonas/parroquia/{parishes[0]['id']}", headers=headers
        ).get_json()
        self.assertEqual(
            [(zone["id"], zone["dpa"], zone["parroquia_id"]) for zone in zones],
            [
                (1260028500, "01260028500", 12600285),
                (1260028501, "01260028501", 12600285),
            ],
        )
        self.assertTrue(all("total_recintos" not in zone for zone in zones))
        self.assertTrue(all(zone["abreviatura"] is None for zone in zones))
        replacement_csv = """COD_PROVINCIA;NOMBRE_PROVINCIA;COD_CANTON;NOMBRE_CANTON;COD_PARROQUIA;NOMBRE_PARROQUIA;COD_ZONA;NOMBRE_ZONA;Total_Recintos
1;AZUAY;260;CUENCA;285;BANOS;1;BANOS ACTUALIZADO;4
1;AZUAY;260;CUENCA;285;BANOS;3;ZONA NUEVA;9
""".encode("utf-8")
        replaced = self.client.post(
            "/api/ubicaciones/importar",
            headers=headers,
            data={"archivo": (io.BytesIO(replacement_csv), "actualizacion.csv")},
        )
        self.assertEqual(replaced.status_code, 200)
        replacement_summary = replaced.get_json()
        self.assertEqual(replacement_summary["modo"], "reemplazo")
        self.assertEqual(
            replacement_summary["provincias"],
            {"eliminados": 2, "creados": 1, "actualizados": 0},
        )
        self.assertEqual(replacement_summary["zonas"]["eliminados"], 3)
        self.assertEqual(replacement_summary["zonas"]["creados"], 2)

        provinces = self.client.get("/api/provincias", headers=headers).get_json()
        self.assertEqual([(item["id"], item["dpa"]) for item in provinces], [(1, "01")])
        cantons = self.client.get(
            "/api/cantones/provincia/1", headers=headers
        ).get_json()
        self.assertEqual([(item["id"], item["dpa"]) for item in cantons], [(1260, "01260")])
        parishes = self.client.get(
            "/api/parroquias/canton/1260", headers=headers
        ).get_json()
        self.assertEqual(
            [(item["id"], item["dpa"]) for item in parishes],
            [(12600285, "012600285")],
        )
        zones = self.client.get(
            "/api/zonas/parroquia/12600285", headers=headers
        ).get_json()
        self.assertEqual(
            [(item["id"], item["dpa"], item["nombre"]) for item in zones],
            [
                (1260028501, "01260028501", "BANOS ACTUALIZADO"),
                (1260028503, "01260028503", "ZONA NUEVA"),
            ],
        )

    def test_import_dpa_rejects_invalid_csv_before_writing(self):
        with self.app.app_context():
            db.session.execute(
                text("INSERT INTO provincias (id, dpa, nombre) VALUES (25, '99', 'Anterior')")
            )
            db.session.commit()

        token = self.register().get_json()["token"]
        response = self.client.post(
            "/api/ubicaciones/importar",
            headers={"Authorization": f"Bearer {token}"},
            data={"archivo": (io.BytesIO(b"COD_PROVINCIA;NOMBRE_PROVINCIA\n1;AZUAY"), "invalido.csv")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Archivo CSV invalido")
        provinces = self.client.get(
            "/api/provincias",
            headers={"Authorization": f"Bearer {token}"},
        ).get_json()
        self.assertEqual([(item["id"], item["dpa"]) for item in provinces], [(25, "99")])

    def test_import_infrastructures_creates_updates_and_validates_geography(self):
        with self.app.app_context():
            db.session.execute(
                text("INSERT INTO provincias (id, dpa, nombre) VALUES (1, '01', 'AZUAY')")
            )
            db.session.execute(
                text(
                    "INSERT INTO cantones (id, provincia_id, dpa, nombre) "
                    "VALUES (1556, 1, '01556', 'CAMILO PONCE ENRIQUEZ')"
                )
            )
            db.session.execute(
                text(
                    "INSERT INTO parroquias (id, provincia_id, canton_id, dpa, nombre) "
                    "VALUES (15566875, 1, 1556, '015566875', 'CAMILO PONCE ENRIQUEZ')"
                )
            )
            db.session.execute(
                text(
                    "INSERT INTO zonas (id, provincia_id, canton_id, parroquia_id, dpa, nombre) "
                    "VALUES (1556687505, 1, 1556, 15566875, '01556687505', 'BELLA RICA')"
                )
            )
            db.session.commit()

        token = self.register().get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        csv_content = """CODIGO PROVINCIA;CODIGO CANTON;CODIGO PARROQUIA;CODIGO ZONA;CODIGO RECINTO;NOMBRE RECINTO;DIRECCION RECINTO;long;lat
1;556;6875;5;5021;ESCUELA EL DIAMANTE;ENTRADA A BELLA RICA;-79,70736392;-3,07881598
""".encode("utf-8")
        created = self.client.post(
            "/api/infraestructuras/importar",
            headers=headers,
            data={"archivo": (io.BytesIO(csv_content), "recintos.csv")},
        )
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.get_json()["creados"], 1)

        items = self.client.get("/api/infraestructuras", headers=headers).get_json()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], 15566875055021)
        self.assertEqual(items[0]["dpa"], "015566875055021")
        self.assertEqual(items[0]["provincia_id"], 1)
        self.assertEqual(items[0]["canton_id"], 1556)
        self.assertEqual(items[0]["parroquia_id"], 15566875)
        self.assertEqual(items[0]["zona_id"], 1556687505)

        updated_csv = csv_content.replace(
            b"ESCUELA EL DIAMANTE", b"ESCUELA EL DIAMANTE ACTUALIZADA"
        )
        updated = self.client.post(
            "/api/infraestructuras/importar",
            headers=headers,
            data={"archivo": (io.BytesIO(updated_csv), "recintos.csv")},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["actualizados"], 1)
        self.assertEqual(updated.get_json()["creados"], 0)

        invalid_geography = csv_content.replace(b";5;5021;", b";6;5021;")
        rejected = self.client.post(
            "/api/infraestructuras/importar",
            headers=headers,
            data={"archivo": (io.BytesIO(invalid_geography), "recintos.csv")},
        )
        self.assertEqual(rejected.status_code, 409)
        items = self.client.get("/api/infraestructuras", headers=headers).get_json()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["nombre"], "ESCUELA EL DIAMANTE ACTUALIZADA")

        item_id = items[0]["id"]
        patched = self.client.patch(
            f"/api/infraestructuras/{item_id}",
            headers=headers,
            json={"direccion": "DIRECCION ACTUALIZADA"},
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.get_json()["direccion"], "DIRECCION ACTUALIZADA")
        deleted = self.client.delete(
            f"/api/infraestructuras/{item_id}", headers=headers
        )
        self.assertEqual(deleted.status_code, 204)

    def test_list_infrastructures_by_parish_type_and_emergency(self):
        with self.app.app_context():
            db.session.execute(
                text(
                    """
                    DELETE FROM emergencias
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    CREATE TABLE afectacion_variable_registros (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        emergencia_id INTEGER NOT NULL
                    )
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    CREATE TABLE afectacion_variable_registro_detalles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        afectacion_variable_registro_id INTEGER NOT NULL,
                        infraestructura_id BIGINT NOT NULL
                    )
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO emergencias (id, nombre)
                    VALUES (99, 'Proceso Electoral'), (100, 'Otra emergencia')
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    DELETE FROM infraestructura_tipos
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO infraestructura_tipos (id, emergencia_id, nombre)
                    VALUES
                        (2, 99, 'Recinto electoral'),
                        (3, 100, 'Bodega')
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO infraestructuras (
                        id,
                        provincia_id,
                        canton_id,
                        parroquia_id,
                        zona_id,
                        dpa,
                        infraestructura_tipo_id,
                        nombre,
                        direccion,
                        longitud,
                        latitud
                    )
                    VALUES
                        (
                            130801010100001,
                            13,
                            1308,
                            130801,
                            1308010101,
                            '130801010100001',
                            2,
                            'Infraestructura disponible',
                            'Calle uno',
                            -79.5,
                            -1.5
                        ),
                        (
                            130801010100002,
                            13,
                            1308,
                            130801,
                            1308010101,
                            '130801010100002',
                            2,
                            'Infraestructura afectada',
                            'Calle dos',
                            0,
                            0
                        ),
                        (
                            130801010100003,
                            13,
                            1308,
                            130801,
                            1308010101,
                            '130801010100003',
                            3,
                            'Otro tipo',
                            'Calle tres',
                            -80,
                            -2
                        )
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO afectacion_variable_registros (id, emergencia_id)
                    VALUES (1, 99), (2, 100)
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO afectacion_variable_registro_detalles (
                        afectacion_variable_registro_id,
                        infraestructura_id
                    )
                    VALUES
                        (1, 130801010100002),
                        (2, 130801010100001)
                    """
                )
            )
            db.session.commit()

        token = self.register().get_json()["token"]
        response = self.client.get(
            (
                "/api/infraestructuras/parroquia/130801/"
                "infraestructura_tipo/2/emergencia/99"
            ),
            headers={"Authorization": token},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            [
                {
                    "direccion": "Calle uno",
                    "id": 130801010100001,
                    "institucion": None,
                    "latitud": -1.5,
                    "longitud": -79.5,
                    "nombre": "Infraestructura disponible",
                    "tipologia": "Recinto electoral",
                },
                {
                    "direccion": "Calle dos",
                    "id": 130801010100002,
                    "institucion": None,
                    "latitud": 0.0,
                    "longitud": 0.0,
                    "nombre": "Infraestructura afectada",
                    "tipologia": "Recinto electoral",
                }
            ],
        )

    def test_list_event_subtypes_by_event_type(self):
        with self.app.app_context():
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS evento_subtipos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        evento_tipo_id INTEGER NOT NULL,
                        nombre VARCHAR(100) NOT NULL
                    )
                    """
                )
            )
            db.session.execute(text("DELETE FROM evento_subtipos"))
            db.session.execute(
                text(
                    """
                    INSERT INTO evento_subtipos (evento_tipo_id, nombre)
                    VALUES (1, 'Subtipo uno'), (2, 'Subtipo dos'), (1, 'Subtipo tres')
                    """
                )
            )
            db.session.commit()

        token = self.register().get_json()["token"]
        response = self.client.get(
            "/api/evento-subtipos/tipo-evento/1",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [subtipo["nombre"] for subtipo in response.get_json()],
            ["Subtipo uno", "Subtipo tres"],
        )

    def test_list_event_types_by_institution(self):
        with self.app.app_context():
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS evento_tipos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        institucion_id INTEGER NOT NULL,
                        nombre VARCHAR(100) NOT NULL
                    )
                    """
                )
            )
            db.session.execute(text("DELETE FROM evento_tipos"))
            db.session.execute(
                text(
                    """
                    INSERT INTO evento_tipos (institucion_id, nombre)
                    VALUES
                        (10, 'Inundacion'),
                        (20, 'Incendio'),
                        (10, 'Deslizamiento')
                    """
                )
            )
            db.session.commit()

        token = self.register().get_json()["token"]
        response = self.client.get(
            "/api/evento-tipos/institucion/10",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [tipo["nombre"] for tipo in response.get_json()],
            ["Inundacion", "Deslizamiento"],
        )

    def test_list_affectation_variables_for_events(self):
        with self.app.app_context():
            db.session.execute(
                text(
                    """
                    INSERT INTO parroquias (id, provincia_id, canton_id, dpa, nombre)
                    VALUES (130801, 13, 1308, '130801', 'Los Esteros')
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS evento_tipos (
                        id INTEGER PRIMARY KEY,
                        institucion_id INTEGER,
                        nombre VARCHAR(100) NOT NULL
                    )
                    """
                )
            )
            db.session.execute(text("DELETE FROM evento_tipos"))
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS evento_subtipos (
                        id INTEGER PRIMARY KEY,
                        evento_tipo_id INTEGER,
                        nombre VARCHAR(100) NOT NULL
                    )
                    """
                )
            )
            db.session.execute(text("DELETE FROM evento_subtipos"))
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS eventos (
                        id INTEGER PRIMARY KEY,
                        emergencia_id INTEGER NOT NULL,
                        provincia_id INTEGER NOT NULL,
                        canton_id INTEGER NOT NULL,
                        parroquia_id INTEGER NOT NULL,
                        sector VARCHAR(1000) NOT NULL,
                        evento_tipo_id INTEGER NOT NULL,
                        evento_subtipo_id INTEGER NOT NULL
                    )
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS afectacion_variables (
                        id INTEGER PRIMARY KEY,
                        nombre VARCHAR(255) NOT NULL,
                        requiere_gis BOOLEAN NOT NULL DEFAULT 0,
                        coe_id INTEGER NOT NULL,
                        mesa_grupo_id INTEGER NOT NULL
                    )
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS afectaciones_registros (
                        id INTEGER PRIMARY KEY,
                        evento_id INTEGER NOT NULL,
                        afectacion_variable_id INTEGER NOT NULL,
                        cantidad NUMERIC DEFAULT 0,
                        costo NUMERIC DEFAULT 0
                    )
                    """
                )
            )
            db.session.commit()
            table_columns = {
                table_name: {
                    column["name"]
                    for column in inspect(db.engine).get_columns(table_name)
                }
                for table_name in (
                    "evento_tipos",
                    "evento_subtipos",
                    "eventos",
                )
            }
            event_type_values = {
                "id": 1,
                "institucion_id": 999,
                "nombre": "Inundacion",
            }
            event_type_values = {
                column: value
                for column, value in event_type_values.items()
                if column in table_columns["evento_tipos"]
            }
            db.session.execute(
                text(
                    "INSERT INTO evento_tipos "
                    f"({', '.join(event_type_values)}) "
                    f"VALUES ({', '.join(f':{column}' for column in event_type_values)})"
                ),
                event_type_values,
            )
            event_subtype_values = {
                "id": 2,
                "evento_tipo_id": 1,
                "nombre": "Inundacion pluvial",
            }
            event_subtype_values = {
                column: value
                for column, value in event_subtype_values.items()
                if column in table_columns["evento_subtipos"]
            }
            db.session.execute(
                text(
                    "INSERT INTO evento_subtipos "
                    f"({', '.join(event_subtype_values)}) "
                    f"VALUES ({', '.join(f':{column}' for column in event_subtype_values)})"
                ),
                event_subtype_values,
            )
            event_values = {
                "id": 6962,
                "emergencia_id": 8,
                "provincia_id": 13,
                "canton_id": 1308,
                "parroquia_id": 130801,
                "sector": "Villamarina",
                "evento_tipo_id": 1,
                "evento_subtipo_id": 2,
                "evento_causa_id": 1,
                "evento_origen_id": 1,
                "alto_impacto": False,
            }
            event_values = {
                column: value
                for column, value in event_values.items()
                if column in table_columns["eventos"]
            }
            db.session.execute(
                text(
                    "INSERT INTO eventos "
                    f"({', '.join(event_values)}) "
                    f"VALUES ({', '.join(f':{column}' for column in event_values)})"
                ),
                event_values,
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO afectacion_variables (
                        id, nombre, requiere_gis, coe_id, mesa_grupo_id
                    )
                    VALUES
                        (
                            1,
                            'Porcentaje de Servicio de Agua Potable Afectado (%)',
                            0,
                            3,
                            1
                        ),
                        (2, 'Viviendas afectadas', 1, 3, 1),
                        (3, 'No debe salir', 0, 4, 1)
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO afectaciones_registros (
                        id, evento_id, afectacion_variable_id, cantidad, costo
                    )
                    VALUES (77, 6962, 2, 5, 100)
                    """
                )
            )
            db.session.commit()

        token = self.register().get_json()["token"]
        response = self.client.get(
            "/api/afectaciones_registros/eventos/emergencia/8"
            "/provincia/13/canton/1308/coe/3/mesa_grupo/1/",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            [
                {
                    "afectacion_variable_id": 1,
                    "cantidad": 0,
                    "costo": 0,
                    "evento_id": 6962,
                    "evento_nombre": "Inundacion/Inundacion pluvial",
                    "evento_sector": "Villamarina",
                    "id": None,
                    "parroquia_id": 130801,
                    "parroquia_nombre": "Los Esteros",
                    "requiere_gis": False,
                    "variable_nombre": (
                        "Porcentaje de Servicio de Agua Potable Afectado (%)"
                    ),
                },
                {
                    "afectacion_variable_id": 2,
                    "cantidad": 5,
                    "costo": 100,
                    "evento_id": 6962,
                    "evento_nombre": "Inundacion/Inundacion pluvial",
                    "evento_sector": "Villamarina",
                    "id": 77,
                    "parroquia_id": 130801,
                    "parroquia_nombre": "Los Esteros",
                    "requiere_gis": True,
                    "variable_nombre": "Viviendas afectadas",
                },
            ],
        )

    def test_list_affectation_variables_for_events_without_direct_scope_columns(self):
        with self.app.app_context():
            for table_name in (
                "afectacion_variables",
                "afectacion_variable_registros",
                "mesas",
            ):
                db.session.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
                table = db.metadata.tables.get(table_name)
                if table is not None:
                    db.metadata.remove(table)
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS parroquias (
                        id INTEGER PRIMARY KEY,
                        nombre VARCHAR(100) NOT NULL
                    )
                    """
                )
            )
            db.session.execute(text("DELETE FROM parroquias"))
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS evento_tipos (
                        id INTEGER PRIMARY KEY,
                        nombre VARCHAR(100) NOT NULL
                    )
                    """
                )
            )
            db.session.execute(text("DELETE FROM evento_tipos"))
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS evento_subtipos (
                        id INTEGER PRIMARY KEY,
                        evento_tipo_id INTEGER,
                        nombre VARCHAR(100) NOT NULL
                    )
                    """
                )
            )
            db.session.execute(text("DELETE FROM evento_subtipos"))
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS eventos (
                        id INTEGER PRIMARY KEY,
                        emergencia_id INTEGER NOT NULL,
                        provincia_id INTEGER NOT NULL,
                        canton_id INTEGER NOT NULL,
                        parroquia_id INTEGER NOT NULL,
                        sector VARCHAR(1000) NOT NULL,
                        evento_tipo_id INTEGER NOT NULL,
                        evento_subtipo_id INTEGER NOT NULL
                    )
                    """
                )
            )
            db.session.execute(text("DELETE FROM eventos"))
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS afectacion_variables (
                        id INTEGER PRIMARY KEY,
                        nombre VARCHAR(255) NOT NULL,
                        requiere_gis BOOLEAN NOT NULL DEFAULT 0,
                        activo BOOLEAN DEFAULT 1
                    )
                    """
                )
            )
            db.session.execute(text("DELETE FROM afectacion_variables"))
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS afectacion_variable_registros (
                        id INTEGER PRIMARY KEY,
                        evento_id INTEGER NOT NULL,
                        afectacion_variable_id INTEGER NOT NULL,
                        cantidad NUMERIC DEFAULT 0,
                        costo NUMERIC DEFAULT 0
                    )
                    """
                )
            )
            db.session.execute(text("DELETE FROM afectacion_variable_registros"))
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS mesas (
                        id INTEGER PRIMARY KEY,
                        coe_id INTEGER NOT NULL,
                        mesa_grupo_id INTEGER NOT NULL,
                        nombre VARCHAR(100) NOT NULL
                    )
                    """
                )
            )
            db.session.execute(text("DELETE FROM mesas"))
            db.session.execute(
                text(
                    """
                    INSERT INTO parroquias (
                        id, provincia_id, canton_id, dpa, nombre
                    )
                    VALUES (130801, 13, 1308, '130801', 'Los Esteros')
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO evento_tipos (id, nombre)
                    VALUES (1, 'Inundacion')
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO evento_subtipos (id, evento_tipo_id, nombre)
                    VALUES (2, 1, 'Inundacion pluvial')
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO eventos (
                        id,
                        emergencia_id,
                        provincia_id,
                        canton_id,
                        parroquia_id,
                        sector,
                        evento_tipo_id,
                        evento_subtipo_id
                    )
                    VALUES (6962, 8, 13, 1308, 130801, 'Villamarina', 1, 2)
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO afectacion_variables (
                        id, nombre, requiere_gis, activo
                    )
                    VALUES
                        (1, 'Personas Fallecidas', 1, 1),
                        (2, 'Personas Heridas', 1, 1)
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO afectacion_variable_registros (
                        id, evento_id, afectacion_variable_id, cantidad, costo
                    )
                    VALUES (77, 6962, 2, 5, 100)
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO mesas (id, coe_id, mesa_grupo_id, nombre)
                    VALUES (2, 2, 2, 'Recinto Electoral')
                    """
                )
            )
            db.session.commit()

        token = self.register().get_json()["token"]
        response = self.client.get(
            "/api/afectaciones_registros/eventos/emergencia/8"
            "/provincia/13/canton/1308/coe/2/mesa_grupo/2/",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            [
                {
                    "afectacion_variable_id": 1,
                    "cantidad": 0,
                    "costo": 0,
                    "evento_id": 6962,
                    "evento_nombre": "Inundacion/Inundacion pluvial",
                    "evento_sector": "Villamarina",
                    "id": None,
                    "parroquia_id": 130801,
                    "parroquia_nombre": "Los Esteros",
                    "requiere_gis": True,
                    "variable_nombre": "Personas Fallecidas",
                },
                {
                    "afectacion_variable_id": 2,
                    "cantidad": 5,
                    "costo": 100,
                    "evento_id": 6962,
                    "evento_nombre": "Inundacion/Inundacion pluvial",
                    "evento_sector": "Villamarina",
                    "id": 77,
                    "parroquia_id": 130801,
                    "parroquia_nombre": "Los Esteros",
                    "requiere_gis": True,
                    "variable_nombre": "Personas Heridas",
                },
            ],
        )

    def test_list_affectation_variables_by_group_and_coe(self):
        with self.app.app_context():
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS afectacion_variables (
                        id INTEGER PRIMARY KEY,
                        activo BOOLEAN DEFAULT 1,
                        coe_id INTEGER NOT NULL,
                        creacion TIMESTAMP,
                        creador VARCHAR(100),
                        dato_tipo_id INTEGER,
                        infraestructura_tipo_id INTEGER,
                        mesa_grupo_id INTEGER NOT NULL,
                        modificacion TIMESTAMP,
                        modificador VARCHAR(100),
                        nombre VARCHAR(255) NOT NULL,
                        observaciones TEXT,
                        requiere_costo BOOLEAN DEFAULT 0,
                        requiere_gis BOOLEAN DEFAULT 0
                    )
                    """
                )
            )
            existing_columns = {
                column["name"]
                for column in inspect(db.engine).get_columns("afectacion_variables")
            }
            expected_columns = {
                "activo": "BOOLEAN DEFAULT 1",
                "creacion": "TIMESTAMP",
                "creador": "VARCHAR(100)",
                "dato_tipo_id": "INTEGER",
                "infraestructura_tipo_id": "INTEGER",
                "modificacion": "TIMESTAMP",
                "modificador": "VARCHAR(100)",
                "observaciones": "TEXT",
                "requiere_costo": "BOOLEAN DEFAULT 0",
            }
            for column_name, column_sql in expected_columns.items():
                if column_name not in existing_columns:
                    db.session.execute(
                        text(
                            "ALTER TABLE afectacion_variables "
                            f"ADD COLUMN {column_name} {column_sql}"
                        )
                    )
            db.session.execute(text("DELETE FROM afectacion_variables"))
            db.session.execute(
                text(
                    """
                    INSERT INTO afectacion_variables (
                        id,
                        activo,
                        coe_id,
                        creacion,
                        creador,
                        dato_tipo_id,
                        infraestructura_tipo_id,
                        mesa_grupo_id,
                        modificacion,
                        modificador,
                        nombre,
                        observaciones,
                        requiere_costo,
                        requiere_gis
                    )
                    VALUES
                        (
                            1,
                            1,
                            3,
                            '2025-09-30T12:56:00.515590',
                            'victorsan1972',
                            3,
                            -1,
                            1,
                            NULL,
                            NULL,
                            'Porcentaje de Servicio de Agua Potable Afectado (%)',
                            '',
                            1,
                            0
                        ),
                        (2, 1, 4, NULL, NULL, 3, -1, 1, NULL, NULL, 'Otro COE', '', 0, 0),
                        (3, 1, 3, NULL, NULL, 3, -1, 2, NULL, NULL, 'Otra mesa', '', 0, 0)
                    """
                )
            )
            db.session.commit()

        token = self.register().get_json()["token"]
        response = self.client.get(
            "/api/mesa_grupo/1/afectacion_varibles/coe/3",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            [
                {
                    "activo": True,
                    "coe_id": 3,
                    "creacion": "2025-09-30T12:56:00.515590",
                    "creador": "victorsan1972",
                    "dato_tipo_id": 3,
                    "id": 1,
                    "infraestructura_tipo_id": -1,
                    "mesa_grupo_id": 1,
                    "modificacion": None,
                    "modificador": None,
                    "nombre": (
                        "Porcentaje de Servicio de Agua Potable Afectado (%)"
                    ),
                    "observaciones": "",
                    "requiere_costo": True,
                    "requiere_gis": False,
                }
            ],
        )

    def test_list_affectation_variables_by_group_and_coe_without_direct_scope_columns(self):
        with self.app.app_context():
            for table_name in ("afectacion_variables", "mesas"):
                db.session.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
                table = db.metadata.tables.get(table_name)
                if table is not None:
                    db.metadata.remove(table)
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS afectacion_variables (
                        id INTEGER PRIMARY KEY,
                        nombre VARCHAR(255) NOT NULL,
                        requiere_gis BOOLEAN NOT NULL DEFAULT 0,
                        activo BOOLEAN DEFAULT 1
                    )
                    """
                )
            )
            db.session.execute(text("DELETE FROM afectacion_variables"))
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS mesas (
                        id INTEGER PRIMARY KEY,
                        coe_id INTEGER NOT NULL,
                        mesa_grupo_id INTEGER NOT NULL,
                        nombre VARCHAR(100) NOT NULL
                    )
                    """
                )
            )
            db.session.execute(text("DELETE FROM mesas"))
            db.session.execute(
                text(
                    """
                    INSERT INTO afectacion_variables (
                        id, nombre, requiere_gis, activo
                    )
                    VALUES
                        (1, 'Personas Fallecidas', 1, 1),
                        (2, 'Personas Heridas', 1, 1)
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO mesas (id, coe_id, mesa_grupo_id, nombre)
                    VALUES (2, 2, 2, 'Recinto Electoral')
                    """
                )
            )
            db.session.commit()

        token = self.register().get_json()["token"]
        response = self.client.get(
            "/api/mesa_grupo/2/afectacion_varibles/coe/2",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            [
                {
                    "activo": True,
                    "id": 1,
                    "nombre": "Personas Fallecidas",
                    "requiere_gis": True,
                },
                {
                    "activo": True,
                    "id": 2,
                    "nombre": "Personas Heridas",
                    "requiere_gis": True,
                },
            ],
        )

    def test_list_geographic_resources_by_parent(self):
        with self.app.app_context():
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS cantones (
                        id INTEGER PRIMARY KEY,
                        provincia_id INTEGER NOT NULL,
                        dpa VARCHAR(10) NOT NULL,
                        nombre VARCHAR(100) NOT NULL
                    )
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS parroquias (
                        id INTEGER PRIMARY KEY,
                        provincia_id INTEGER NOT NULL,
                        canton_id INTEGER NOT NULL,
                        dpa VARCHAR(10) NOT NULL,
                        nombre VARCHAR(100) NOT NULL
                    )
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO cantones (id, provincia_id, dpa, nombre)
                    VALUES (1, 1, '0101', 'Cuenca'), (2, 2, '0201', 'Guaranda')
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO parroquias (id, provincia_id, canton_id, dpa, nombre)
                    VALUES
                        (1, 1, 1, '010101', 'Bellavista'),
                        (2, 1, 1, '010102', 'El Vecino'),
                        (3, 2, 2, '020101', 'Angel Polibio Chavez')
                    """
                )
            )
            db.session.commit()

        token = self.register().get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        cantones = self.client.get("/api/cantones/provincia/1", headers=headers)
        parroquias_por_canton = self.client.get(
            "/api/parroquias/canton/1", headers=headers
        )

        self.assertEqual([item["nombre"] for item in cantones.get_json()], ["Cuenca"])
        self.assertEqual(len(parroquias_por_canton.get_json()), 2)

    def test_create_event_allows_null_attention_status(self):
        with self.app.app_context():
            db.session.execute(
                text(
                    """
                    CREATE TABLE eventos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        emergencia_id INTEGER NOT NULL,
                        provincia_id INTEGER NOT NULL,
                        canton_id INTEGER NOT NULL,
                        parroquia_id INTEGER NOT NULL,
                        infraestructura_id INTEGER NOT NULL DEFAULT 0,
                        afectacion_variable_id INTEGER NOT NULL DEFAULT 0,
                        sector VARCHAR(1000) NOT NULL,
                        evento_fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        longitud NUMERIC(15,12) DEFAULT 0,
                        latitud NUMERIC(15,12) DEFAULT 0,
                        evento_tipo_id INTEGER NOT NULL,
                        evento_subtipo_id INTEGER,
                        evento_causa_id INTEGER NOT NULL,
                        evento_origen_id INTEGER NOT NULL,
                        evento_atencion_estado_id INTEGER,
                        alto_impacto BOOLEAN NOT NULL DEFAULT 0,
                        situacion VARCHAR(12000),
                        descripcion VARCHAR(5000),
                        activo BOOLEAN DEFAULT 1,
                        evento_id_redm INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
            )
            db.session.commit()

        token = self.register().get_json()["token"]
        response = self.client.post(
            "/api/eventos",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "emergencia_id": 0,
                "provincia_id": 9,
                "canton_id": 901,
                "parroquia_id": 90101,
                "infraestructura_id": 9010100010001,
                "afectacion_variable_id": 2,
                "sector": "Norte",
                "longitud": -79.889054321123,
                "latitud": -2.189412345678,
                "evento_tipo_id": 1,
                "evento_subtipo_id": 1,
                "evento_causa_id": 3,
                "evento_origen_id": 2,
                "evento_atencion_estado_id": None,
            },
        )

        self.assertEqual(response.status_code, 201)
        created = response.get_json()
        self.assertIsNone(created["evento_atencion_estado_id"])
        self.assertEqual(created["infraestructura_id"], 9010100010001)
        self.assertEqual(created["afectacion_variable_id"], 2)

        updated = self.client.patch(
            f"/api/eventos/{created['id']}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "infraestructura_id": 0,
                "afectacion_variable_id": 5,
                "situacion": "Seguimiento actualizado",
            },
        )

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["infraestructura_id"], 0)
        self.assertEqual(updated.get_json()["afectacion_variable_id"], 5)
        self.assertEqual(updated.get_json()["situacion"], "Seguimiento actualizado")

    def test_eventos_swagger_body_includes_embedded_affectation_fields(self):
        paths = self.client.get("/apispec_1.json").get_json()["paths"]
        create_schema = paths["/api/eventos"]["post"]["parameters"][0]["schema"]
        update_schema = paths["/api/eventos/{item_id}"]["patch"]["parameters"][1]["schema"]

        self.assertEqual(
            create_schema["required"],
            [
                "emergencia_id",
                "provincia_id",
                "canton_id",
                "parroquia_id",
                "sector",
                "evento_tipo_id",
                "evento_causa_id",
                "evento_origen_id",
            ],
        )
        self.assertIn("infraestructura_id", create_schema["properties"])
        self.assertIn("afectacion_variable_id", create_schema["properties"])
        self.assertEqual(
            create_schema["example"]["infraestructura_id"],
            130801000100001,
        )
        self.assertEqual(create_schema["example"]["afectacion_variable_id"], 2)
        self.assertNotIn("required", update_schema)

    def test_affectation_variable_resources_crud(self):
        with self.app.app_context():
            db.session.execute(
                text(
                    """
                    CREATE TABLE afectacion_variable_registros (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        emergencia_id INTEGER NOT NULL,
                        provincia_id INTEGER NOT NULL,
                        canton_id INTEGER NOT NULL,
                        parroquia_id INTEGER NOT NULL,
                        evento_id INTEGER NOT NULL,
                        afectacion_variable_id INTEGER NOT NULL,
                        cantidad INTEGER NOT NULL,
                        costo INTEGER NOT NULL,
                        activo BOOLEAN DEFAULT 1,
                        creador TEXT,
                        creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        modificador TEXT,
                        modificacion TIMESTAMP,
                        evento_id_redm INTEGER NOT NULL DEFAULT 0,
                        afectacion_id_redm INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    CREATE TABLE afectacion_variable_registro_detalles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        afectacion_variable_registro_id INTEGER NOT NULL,
                        infraestructura_id BIGINT NOT NULL,
                        costo INTEGER NOT NULL,
                        activo BOOLEAN DEFAULT 1,
                        creador TEXT,
                        creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        modificador TEXT,
                        modificacion TIMESTAMP
                    )
                    """
                )
            )
            db.session.commit()

        self.assertEqual(self.client.get("/api/afectacion-variable-registros").status_code, 401)
        token = self.register().get_json()["token"]
        headers = {"Authorization": token}

        record_payload = {
            "emergencia_id": 8,
            "provincia_id": 13,
            "canton_id": 1308,
            "parroquia_id": 130801,
            "evento_id": 3,
            "afectacion_variable_id": 2,
            "cantidad": 5,
            "costo": 100,
        }
        created_record = self.client.post(
            "/api/afectacion-variable-registros",
            headers=headers,
            json=record_payload,
        )
        self.assertEqual(created_record.status_code, 201)
        record_id = created_record.get_json()["id"]
        created_other_event_record = self.client.post(
            "/api/afectacion-variable-registros",
            headers=headers,
            json={**record_payload, "evento_id": 4, "cantidad": 2},
        )
        self.assertEqual(created_other_event_record.status_code, 201)
        other_event_record_id = created_other_event_record.get_json()["id"]
        self.assertEqual(
            self.client.get(
                "/api/afectacion-variable-registros", headers=headers
            ).status_code,
            200,
        )
        records_by_event = self.client.get(
            f"/api/afectacion-variable-registros/evento/{record_payload['evento_id']}",
            headers=headers,
        )
        self.assertEqual(records_by_event.status_code, 200)
        self.assertEqual(
            [record["id"] for record in records_by_event.get_json()],
            [record_id],
        )

        detail = self.client.post(
            "/api/afectacion-variable-registro-detalles",
            headers=headers,
            json={
                "afectacion_variable_registro_id": record_id,
                "infraestructura_id": 170600030011402,
                "costo": 50,
            },
        )
        self.assertEqual(detail.status_code, 201)
        detail_id = detail.get_json()["id"]

        updated_record = self.client.put(
            f"/api/afectacion-variable-registros/{record_id}",
            headers=headers,
            json={"cantidad": 10, "costo": 0},
        )
        self.assertEqual(updated_record.status_code, 200)
        self.assertEqual(updated_record.get_json()["cantidad"], 10)
        self.assertEqual(updated_record.get_json()["costo"], 0)
        self.assertEqual(
            self.client.get(
                f"/api/afectacion-variable-registro-detalles/{detail_id}",
                headers=headers,
            ).status_code,
            200,
        )

        self.assertEqual(
            self.client.delete(
                f"/api/afectacion-variable-registro-detalles/{detail_id}",
                headers=headers,
            ).status_code,
            204,
        )
        self.assertEqual(
            self.client.delete(
                f"/api/afectacion-variable-registros/{other_event_record_id}",
                headers=headers,
            ).status_code,
            204,
        )
        self.assertEqual(
            self.client.delete(
                f"/api/afectacion-variable-registros/{record_id}",
                headers=headers,
            ).status_code,
            204,
        )

    def test_affectation_variable_swagger_paths_are_not_duplicated(self):
        paths = self.client.get("/apispec_1.json").get_json()["paths"]

        self.assertEqual(
            set(paths["/api/afectacion-variable-registros"]),
            {"get", "post"},
        )
        self.assertEqual(
            set(paths["/api/afectacion-variable-registros/{item_id}"]),
            {"delete", "get", "patch", "put"},
        )
        self.assertEqual(
            set(paths["/api/afectacion-variable-registros/evento/{evento_id}"]),
            {"get"},
        )
        self.assertNotIn("/api/afectacion_variable_registros/{item_id}", paths)
        self.assertEqual(
            set(paths["/api/afectacion-variable-registro-detalles"]),
            {"get", "post"},
        )
        self.assertEqual(
            set(paths["/api/afectacion-variable-registro-detalles/{item_id}"]),
            {"delete", "get", "patch", "put"},
        )
        self.assertNotIn("/api/afectacion_variable_registro_detalles", paths)
        self.assertNotIn(
            "/api/afectacion_variable_registro_detalles/{item_id}",
            paths,
        )
        record_create_schema = paths[
            "/api/afectacion-variable-registros"
        ]["post"]["parameters"][0]["schema"]
        self.assertEqual(
            record_create_schema["required"],
            [
                "emergencia_id",
                "provincia_id",
                "canton_id",
                "parroquia_id",
                "evento_id",
                "afectacion_variable_id",
                "cantidad",
                "costo",
            ],
        )
        self.assertEqual(
            record_create_schema["example"],
            {
                "emergencia_id": 8,
                "provincia_id": 13,
                "canton_id": 1308,
                "parroquia_id": 130801,
                "evento_id": 6962,
                "afectacion_variable_id": 2,
                "cantidad": 5,
                "costo": 100,
                "activo": True,
                "evento_id_redm": 0,
                "afectacion_id_redm": 0,
            },
        )
        detail_create_schema = paths[
            "/api/afectacion-variable-registro-detalles"
        ]["post"]["parameters"][0]["schema"]
        self.assertEqual(
            detail_create_schema["required"],
            [
                "afectacion_variable_registro_id",
                "infraestructura_id",
                "costo",
            ],
        )
        self.assertEqual(
            set(detail_create_schema["properties"]),
            {
                "afectacion_variable_registro_id",
                "infraestructura_id",
                "costo",
                "activo",
            },
        )
        self.assertEqual(
            detail_create_schema["example"],
            {
                "afectacion_variable_registro_id": 1,
                "infraestructura_id": 170600030011402,
                "costo": 50,
                "activo": True,
            },
        )

    def test_z_list_events_includes_related_names_and_descriptions(self):
        with self.app.app_context():
            for table_name in (
                "provincias",
                "cantones",
                "parroquias",
                "evento_tipos",
                "evento_subtipos",
                "evento_causas",
                "evento_origenes",
                "evento_atencion_estados",
            ):
                db.session.execute(
                    text(
                        f"""
                        CREATE TABLE IF NOT EXISTS {table_name} (
                            id INTEGER PRIMARY KEY,
                            nombre VARCHAR(100) NOT NULL,
                            descripcion VARCHAR(255)
                        )
                        """
                    )
                )
                existing_columns = {
                    column["name"] for column in inspect(db.engine).get_columns(table_name)
                }
                if "descripcion" not in existing_columns:
                    db.session.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN descripcion VARCHAR(255)")
                    )
            db.session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS eventos (
                        id INTEGER PRIMARY KEY,
                        emergencia_id INTEGER,
                        provincia_id INTEGER,
                        canton_id INTEGER,
                        parroquia_id INTEGER,
                        sector VARCHAR(1000),
                        evento_tipo_id INTEGER,
                        evento_subtipo_id INTEGER,
                        evento_causa_id INTEGER,
                        evento_origen_id INTEGER,
                        evento_atencion_estado_id INTEGER
                    )
                    """
                )
            )
            db.session.commit()
            related_rows = {
                "provincias": (99, "Guayas", None),
                "cantones": (9901, "Guayaquil", None),
                "parroquias": (990101, "Tarqui", None),
                "evento_tipos": (91, "Inundacion", "Desborde de agua"),
                "evento_subtipos": (92, "Urbana", "Afecta zonas urbanas"),
                "evento_causas": (93, "Lluvia intensa", "Precipitacion elevada"),
                "evento_origenes": (94, "Ciudadania", "Reporte ciudadano"),
                "evento_atencion_estados": (95, "Pendiente", "Sin atencion"),
            }
            related_table_columns = {
                table_name: {
                    column["name"]
                    for column in inspect(db.engine).get_columns(table_name)
                }
                for table_name in related_rows
            }
            event_columns = {
                column["name"] for column in inspect(db.engine).get_columns("eventos")
            }
            for table_name, (item_id, nombre, descripcion) in related_rows.items():
                values = {
                    "id": item_id,
                    "nombre": nombre,
                    "descripcion": descripcion,
                    "dpa": str(item_id),
                    "provincia_id": 99,
                    "canton_id": 9901,
                    "evento_tipo_id": 91,
                    "institucion_id": 999,
                }
                values = {
                    column_name: value
                    for column_name, value in values.items()
                    if column_name in related_table_columns[table_name]
                }
                column_names_sql = ", ".join(values)
                placeholders_sql = ", ".join(f":{column_name}" for column_name in values)
                db.session.execute(
                    text(
                        f"INSERT INTO {table_name} ({column_names_sql}) "
                        f"VALUES ({placeholders_sql})"
                    ),
                    values,
                )
            event_values = {
                "id": 999,
                "emergencia_id": 0,
                "provincia_id": 99,
                "canton_id": 9901,
                "parroquia_id": 990101,
                "sector": "Norte",
                "evento_tipo_id": 91,
                "evento_subtipo_id": 92,
                "evento_causa_id": 93,
                "evento_origen_id": 94,
                "evento_atencion_estado_id": 95,
                "alto_impacto": False,
                "situacion": "Prueba",
                "descripcion": "Prueba de joins",
                "evento_id_redm": 0,
            }
            event_values = {
                column_name: value
                for column_name, value in event_values.items()
                if column_name in event_columns
            }
            event_columns_sql = ", ".join(event_values)
            event_placeholders_sql = ", ".join(
                f":{column_name}" for column_name in event_values
            )
            db.session.execute(
                text(
                    f"INSERT INTO eventos ({event_columns_sql}) "
                    f"VALUES ({event_placeholders_sql})"
                ),
                event_values,
            )
            db.session.commit()

        token = self.register().get_json()["token"]
        response = self.client.get(
            "/api/eventos/999", headers={"Authorization": f"Bearer {token}"}
        )

        self.assertEqual(response.status_code, 200)
        event = response.get_json()
        self.assertEqual(event["provincia_id"], 99)
        self.assertEqual(event["provincia_nombre"], "Guayas")
        self.assertEqual(event["canton_nombre"], "Guayaquil")
        self.assertEqual(event["parroquia_nombre"], "Tarqui")
        self.assertEqual(event["evento_tipo_nombre"], "Inundacion")
        self.assertEqual(event["evento_tipo_descripcion"], "Desborde de agua")
        self.assertEqual(event["evento_subtipo_nombre"], "Urbana")
        self.assertEqual(event["evento_causa_nombre"], "Lluvia intensa")
        self.assertEqual(event["evento_origen_nombre"], "Ciudadania")
        self.assertEqual(event["evento_atencion_estado_nombre"], "Pendiente")


if __name__ == "__main__":
    unittest.main()
