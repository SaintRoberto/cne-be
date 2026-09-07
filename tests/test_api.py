import unittest

from sqlalchemy import text

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
                    CREATE TABLE provincias (
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
            json={"dpa": "01", "nombre": "AZUAY", "abreviatura": "AZU"},
        )
        self.assertEqual(created.status_code, 201)
        provincia = created.get_json()
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


if __name__ == "__main__":
    unittest.main()
