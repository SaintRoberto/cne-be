from datetime import datetime, timezone

from extensions import db


ZONE_ID_TYPE = db.BigInteger().with_variant(db.Integer, "sqlite")
INFRASTRUCTURE_ID_TYPE = db.BigInteger().with_variant(db.Integer, "sqlite")


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


class Provincia(db.Model):
    __tablename__ = "provincias"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    dpa = db.Column(db.String(2), nullable=False, unique=True)
    nombre = db.Column(db.String(100), nullable=False)
    abreviatura = db.Column(db.String(10), nullable=True)
    activo = db.Column(
        db.Boolean, nullable=False, default=True, server_default=db.text("true")
    )
    creador = db.Column(db.String(100), nullable=True)
    creacion = db.Column(db.DateTime, nullable=True, default=utc_now)
    modificador = db.Column(db.String(100), nullable=True)
    modificacion = db.Column(db.DateTime, nullable=True, default=utc_now, onupdate=utc_now)


class Canton(db.Model):
    __tablename__ = "cantones"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    provincia_id = db.Column(db.Integer, db.ForeignKey("provincias.id"), nullable=False)
    dpa = db.Column(db.String(5), nullable=False, unique=True)
    nombre = db.Column(db.String(100), nullable=False)
    activo = db.Column(
        db.Boolean, nullable=False, default=True, server_default=db.text("true")
    )
    creador = db.Column(db.String(100), nullable=True)
    creacion = db.Column(db.DateTime, nullable=True, default=utc_now)
    modificador = db.Column(db.String(100), nullable=True)
    modificacion = db.Column(db.DateTime, nullable=True, default=utc_now, onupdate=utc_now)


class Parroquia(db.Model):
    __tablename__ = "parroquias"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    provincia_id = db.Column(db.Integer, db.ForeignKey("provincias.id"), nullable=False)
    canton_id = db.Column(db.Integer, db.ForeignKey("cantones.id"), nullable=False)
    dpa = db.Column(db.String(9), nullable=False, unique=True)
    nombre = db.Column(db.String(100), nullable=False)
    activo = db.Column(
        db.Boolean, nullable=False, default=True, server_default=db.text("true")
    )
    creador = db.Column(db.String(100), nullable=True)
    creacion = db.Column(db.DateTime, nullable=True, default=utc_now)
    modificador = db.Column(db.String(100), nullable=True)
    modificacion = db.Column(db.DateTime, nullable=True, default=utc_now, onupdate=utc_now)


class Zona(db.Model):
    __tablename__ = "zonas"

    id = db.Column(ZONE_ID_TYPE, primary_key=True, autoincrement=False)
    provincia_id = db.Column(db.Integer, db.ForeignKey("provincias.id"), nullable=False)
    canton_id = db.Column(db.Integer, db.ForeignKey("cantones.id"), nullable=False)
    parroquia_id = db.Column(db.Integer, db.ForeignKey("parroquias.id"), nullable=False)
    dpa = db.Column(db.String(11), nullable=False, unique=True)
    nombre = db.Column(db.String(100), nullable=False)
    abreviatura = db.Column(db.String(10), nullable=True)
    activo = db.Column(
        db.Boolean, nullable=True, default=True, server_default=db.text("true")
    )
    creador = db.Column(db.String(100), nullable=True)
    creacion = db.Column(db.DateTime, nullable=True, default=utc_now)
    modificador = db.Column(db.String(100), nullable=True)
    modificacion = db.Column(db.DateTime, nullable=True, default=utc_now, onupdate=utc_now)


class Infraestructura(db.Model):
    __tablename__ = "infraestructuras"
    __table_args__ = (
        db.CheckConstraint(
            "id = CAST(dpa AS BIGINT)",
            name="ck_infraestructuras_id_dpa",
        ),
    )

    id = db.Column(INFRASTRUCTURE_ID_TYPE, primary_key=True, autoincrement=False)
    provincia_id = db.Column(db.Integer, db.ForeignKey("provincias.id"), nullable=False)
    canton_id = db.Column(db.Integer, db.ForeignKey("cantones.id"), nullable=False)
    parroquia_id = db.Column(db.Integer, db.ForeignKey("parroquias.id"), nullable=False)
    zona_id = db.Column(ZONE_ID_TYPE, db.ForeignKey("zonas.id"), nullable=False)
    dpa = db.Column(db.String(15), nullable=False, unique=True)
    infraestructura_tipo_id = db.Column(db.Integer, nullable=True)
    nombre = db.Column(db.Text, nullable=True)
    direccion = db.Column(db.Text, nullable=True)
    longitud = db.Column(db.Numeric(15, 12), nullable=True, default=0, server_default="0")
    latitud = db.Column(db.Numeric(15, 12), nullable=True, default=0, server_default="0")
    activo = db.Column(db.Boolean, nullable=True, default=True, server_default=db.text("true"))
    creador = db.Column(db.Text, nullable=True)
    creacion = db.Column(db.DateTime, nullable=True, default=utc_now)
    modificador = db.Column(db.Text, nullable=True)
    modificacion = db.Column(db.DateTime, nullable=True, onupdate=utc_now)
