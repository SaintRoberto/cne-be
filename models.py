from datetime import datetime, timezone

from extensions import db


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(80), unique=True, nullable=False, index=True)
    correo = db.Column(db.String(255), unique=True, nullable=False, index=True)
    clave = db.Column(db.String(255), nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    actualizado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    riesgos = db.relationship(
        "Riesgo", back_populates="propietario", cascade="all, delete-orphan"
    )


class Riesgo(db.Model):
    __tablename__ = "riesgos"
    __table_args__ = (
        db.CheckConstraint(
            "probabilidad >= 0 AND probabilidad <= 1",
            name="ck_riesgos_probabilidad",
        ),
        db.CheckConstraint(
            "impacto >= 0 AND impacto <= 1", name="ck_riesgos_impacto"
        ),
        db.CheckConstraint(
            "estado IN ('abierto', 'en_progreso', 'mitigado', 'cerrado')",
            name="ck_riesgos_estado",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(160), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    probabilidad = db.Column(db.Float, nullable=False)
    impacto = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String(30), nullable=False, default="abierto", index=True)
    propietario_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    creado_en = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    actualizado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    propietario = db.relationship("Usuario", back_populates="riesgos")

    @property
    def nivel(self) -> float:
        return round(self.probabilidad * self.impacto, 4)
