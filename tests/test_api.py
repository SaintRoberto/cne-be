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

    def test_list_event_subtypes_by_event_type(self):
        with self.app.app_context():
            db.session.execute(
                text(
                    """
                    CREATE TABLE evento_subtipos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        evento_tipo_id INTEGER NOT NULL,
                        nombre VARCHAR(100) NOT NULL
                    )
                    """
                )
            )
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
                        sector VARCHAR(1000) NOT NULL,
                        evento_fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        evento_tipo_id INTEGER NOT NULL,
                        evento_subtipo_id INTEGER,
                        evento_causa_id INTEGER NOT NULL,
                        evento_origen_id INTEGER NOT NULL,
                        evento_atencion_estado_id INTEGER,
                        alto_impacto BOOLEAN NOT NULL DEFAULT 0,
                        situacion VARCHAR(12000),
                        descripcion VARCHAR(5000)
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
                "sector": "Norte",
                "evento_tipo_id": 1,
                "evento_subtipo_id": 1,
                "evento_causa_id": 3,
                "evento_origen_id": 2,
                "evento_atencion_estado_id": None,
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.get_json()["evento_atencion_estado_id"])

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
