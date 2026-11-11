import unittest

from sqlalchemy import text

from app import create_app
from extensions import db


class LookerStudioReportTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "SQLALCHEMY_ENGINE_OPTIONS": {},
                "CORS_ORIGINS": ["http://localhost"],
                "LOOKER_STUDIO_API_KEY": "test-looker-api-key",
            }
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            for table_name in (
                "eventos",
                "afectacion_variable_registros",
                "afectacion_variables",
            ):
                table = db.metadata.tables.get(table_name)
                if table is not None:
                    db.metadata.remove(table)
            db.session.execute(
                text(
                    """
                    CREATE TABLE eventos (
                        id INTEGER PRIMARY KEY,
                        evento_atencion_estado_id INTEGER,
                        evento_fecha TIMESTAMP,
                        latitud NUMERIC(15, 12),
                        longitud NUMERIC(15, 12),
                        modificacion TIMESTAMP
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
                    CREATE TABLE afectacion_variable_registros (
                        id INTEGER PRIMARY KEY,
                        evento_id INTEGER NOT NULL,
                        afectacion_variable_id INTEGER NOT NULL,
                        cantidad INTEGER NOT NULL,
                        creacion TIMESTAMP
                    )
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO eventos
                        (
                            id,
                            evento_atencion_estado_id,
                            evento_fecha,
                            latitud,
                            longitud,
                            modificacion
                        )
                    VALUES
                        (
                            10,
                            3,
                            '2026-11-01 00:00:00-05:00',
                            -0.250123,
                            -79.16583,
                            '2026-11-05 15:19:36.449466-05:00'
                        ),
                        (
                            20,
                            2,
                            '2026-11-02 11:30:00',
                            NULL,
                            NULL,
                            '2026-11-05 11:30:00'
                        )
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO afectacion_variables (id, nombre)
                    VALUES
                        (1, 'Personas afectadas'),
                        (2, 'Animales muertos'),
                        (23, 'Centros de Salud Destruidos')
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    INSERT INTO afectacion_variable_registros
                        (id, evento_id, afectacion_variable_id, cantidad, creacion)
                    VALUES
                        (1, 10, 1, 5, '2026-09-28 10:00:52.181237-05:00'),
                        (2, 20, 23, 90, NULL),
                        (3, 10, 1, 12, '2026-10-01 08:30:00-05:00')
                    """
                )
            )
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()

    def test_looker_studio_report_rejects_missing_api_key(self):
        response = self.client.get(
            "/api/reportes/looker-studio/afectacion-variable-registros"
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.get_json(), {"error": "API key de Looker Studio invalida"}
        )

    def test_looker_studio_report_rejects_invalid_api_key(self):
        response = self.client.get(
            "/api/reportes/looker-studio/afectacion-variable-registros",
            query_string={"api_key": "incorrecta"},
        )

        self.assertEqual(response.status_code, 401)

    def test_looker_studio_affectation_report_formats_creation_date_and_time(self):
        response = self.client.get(
            "/api/reportes/looker-studio/afectacion-variable-registros",
            query_string={"api_key": "test-looker-api-key"},
        )

        self.assertEqual(response.status_code, 200)
        records = response.get_json()
        self.assertEqual(
            records[0]["afectacion_variable_nombre"], "Personas afectadas"
        )
        self.assertEqual(records[0]["evento_id"], 10)
        self.assertEqual(records[0]["creacion"], "20260928")
        self.assertEqual(records[0]["hora_creacion"], "10:00:52.181237-05:00")
        self.assertIsNone(records[1]["creacion"])
        self.assertIsNone(records[1]["hora_creacion"])
        self.assertEqual(
            records[1]["afectacion_variable_nombre"],
            "Centros de Salud Destruidos",
        )
        self.assertEqual(records[1]["evento_id"], 20)
        self.assertNotIn("evento_atencion_estado_id", records[0])
        self.assertNotIn("fecha_cierre_evento", records[0])

    def test_looker_studio_events_format_dates_times_and_coordinate(self):
        response = self.client.get(
            "/api/reportes/looker-studio/eventos",
            query_string={"api_key": "test-looker-api-key"},
        )

        self.assertEqual(response.status_code, 200)
        records = response.get_json()
        self.assertEqual([record["id"] for record in records], [10, 20])
        self.assertEqual(next(iter(records[0])), "id")
        self.assertNotIn("es_total", records[0])
        self.assertEqual(
            list(records[0])[-3:],
            [
                "Personas_afectadas",
                "Animales_muertos",
                "Centros_de_Salud_Destruidos",
            ],
        )
        self.assertEqual(records[0]["evento_atencion_estado_id"], 3)
        self.assertEqual(records[0]["evento_fecha"], "20261101")
        self.assertEqual(records[0]["hora_evento"], "00:00:00-05:00")
        self.assertEqual(records[0]["fecha_fin_evento"], "20261105")
        self.assertEqual(records[0]["hora_fin_evento"], "15:19:36.449466-05:00")
        self.assertEqual(records[0]["coordenada"], "-0.250123,-79.16583")
        self.assertNotIn("Fecha fin del evento", records[0])
        self.assertNotIn("latitud", records[0])
        self.assertNotIn("longitud", records[0])
        self.assertEqual(records[0]["Personas_afectadas"], 17)
        self.assertEqual(records[0]["Animales_muertos"], 0)
        self.assertEqual(records[0]["Centros_de_Salud_Destruidos"], 0)
        self.assertNotIn("Total Afectaciones", records[0])
        self.assertNotIn("afectaciones", records[0])
        self.assertNotIn("costo", records[0])
        self.assertEqual(records[1]["evento_atencion_estado_id"], 2)
        self.assertIsNone(records[1]["fecha_fin_evento"])
        self.assertIsNone(records[1]["hora_fin_evento"])
        self.assertIsNone(records[1]["coordenada"])
        self.assertEqual(records[1]["Personas_afectadas"], 0)
        self.assertEqual(records[1]["Animales_muertos"], 0)
        self.assertEqual(records[1]["Centros_de_Salud_Destruidos"], 90)
        self.assertNotIn("afectaciones", records[1])
        self.assertNotIn("es_total", records[1])

    def test_looker_studio_report_returns_503_without_server_configuration(self):
        self.app.config["LOOKER_STUDIO_API_KEY"] = ""

        response = self.client.get(
            "/api/reportes/looker-studio/afectacion-variable-registros",
            query_string={"api_key": "cualquier-clave"},
        )

        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
