from datetime import datetime, timezone

from extensions import db


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    institucion_id = db.Column(db.Integer, nullable=False)
    usuario = db.Column(db.String(100), nullable=False)
    clave = db.Column(db.String(255), nullable=True)
    descripcion = db.Column(db.Text, nullable=True)
    celular = db.Column(db.String(20), nullable=True)
    correo = db.Column(db.String(150), nullable=True)
    nombres = db.Column(db.String(100), nullable=True)
    apellidos = db.Column(db.String(100), nullable=True)
    cedula = db.Column(db.String(20), nullable=True)
    aprobado = db.Column(db.Boolean, nullable=True, default=False)
    activo = db.Column(db.Boolean, nullable=True, default=True)
    creador = db.Column(db.String(100), nullable=True)
    creacion = db.Column(db.DateTime, nullable=True, default=utc_now)
    modificador = db.Column(db.String(100), nullable=True)
    modificacion = db.Column(db.DateTime, nullable=True, default=utc_now, onupdate=utc_now)

    @property
    def nombre_completo(self) -> str:
        return " ".join(
            part.strip() for part in (self.nombres, self.apellidos) if part and part.strip()
        )


class InstitucionCategoria(db.Model):
    __tablename__ = "institucion_categorias"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    activo = db.Column(db.Boolean, nullable=True, default=True)
    creador = db.Column(db.String(100), nullable=True)
    creacion = db.Column(db.DateTime, nullable=True, default=utc_now)
    modificador = db.Column(db.String(100), nullable=True)
    modificacion = db.Column(db.DateTime, nullable=True, default=utc_now, onupdate=utc_now)

    instituciones = db.relationship("Institucion", back_populates="categoria")


class Institucion(db.Model):
    __tablename__ = "instituciones"

    id = db.Column(db.Integer, primary_key=True)
    institucion_categoria_id = db.Column(
        db.Integer, db.ForeignKey("institucion_categorias.id"), nullable=True
    )
    nombre = db.Column(db.String(200), nullable=False)
    siglas = db.Column(db.String(50), nullable=True)
    observaciones = db.Column(db.Text, nullable=True)
    activo = db.Column(db.Boolean, nullable=True, default=True)
    creador = db.Column(db.String(100), nullable=True)
    creacion = db.Column(db.DateTime, nullable=True, default=utc_now)
    modificador = db.Column(db.String(100), nullable=True)
    modificacion = db.Column(db.DateTime, nullable=True, default=utc_now, onupdate=utc_now)

    categoria = db.relationship("InstitucionCategoria", back_populates="instituciones")
