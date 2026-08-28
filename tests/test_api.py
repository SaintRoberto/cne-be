import unittest

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
                "usuario": "admin",
                "correo": "admin@example.com",
                "clave": "ClaveSegura123",
                "nombre": "Administrador",
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
        self.assertIn("/api/riesgos", paths)

    def test_register_login_and_me(self):
        registered = self.register()
        self.assertEqual(registered.status_code, 201)
        token = registered.get_json()["token"]

        me = self.client.get(
            "/api/usuarios/me", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.get_json()["usuario"], "admin")
        self.assertNotIn("clave", me.get_json())

        login = self.client.post(
            "/api/usuarios/login",
            json={"usuario": "admin", "clave": "ClaveSegura123"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("token", login.get_json())

    def test_risk_crud_requires_token(self):
        unauthorized = self.client.get("/api/riesgos")
        self.assertEqual(unauthorized.status_code, 401)

        token = self.register().get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        created = self.client.post(
            "/api/riesgos",
            headers=headers,
            json={
                "titulo": "Pérdida de datos",
                "descripcion": "Falla del almacenamiento principal",
                "probabilidad": 0.4,
                "impacto": 0.9,
            },
        )
        self.assertEqual(created.status_code, 201)
        risk = created.get_json()
        self.assertEqual(risk["nivel"], 0.36)

        updated = self.client.patch(
            f"/api/riesgos/{risk['id']}",
            headers=headers,
            json={"estado": "mitigado"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["estado"], "mitigado")

        deleted = self.client.delete(f"/api/riesgos/{risk['id']}", headers=headers)
        self.assertEqual(deleted.status_code, 204)

    def test_validation_errors_are_json(self):
        response = self.client.post(
            "/api/usuarios/register",
            json={"usuario": "a", "correo": "no-es-correo", "clave": "123"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("detalles", response.get_json())


if __name__ == "__main__":
    unittest.main()
