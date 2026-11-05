import unittest

from flask import jsonify

from app import create_app


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
        self.app.view_functions[
            "generic_resources.afectacion_variable_registros_list"
        ] = lambda: jsonify([{"id": 1, "valor": "dato de prueba"}])

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

    def test_looker_studio_report_returns_dashboard_data(self):
        response = self.client.get(
            "/api/reportes/looker-studio/afectacion-variable-registros",
            query_string={"api_key": "test-looker-api-key"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [{"id": 1, "valor": "dato de prueba"}])

    def test_looker_studio_report_returns_503_without_server_configuration(self):
        self.app.config["LOOKER_STUDIO_API_KEY"] = ""

        response = self.client.get(
            "/api/reportes/looker-studio/afectacion-variable-registros",
            query_string={"api_key": "cualquier-clave"},
        )

        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
