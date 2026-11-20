"""Preferencia, materiales confirmados y evidencia que no inventa historia."""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("solicitud", sa.Column("preferencia_inicio", sa.DateTime(timezone=True), nullable=True))
    op.add_column("solicitud", sa.Column("preferencia_fin", sa.DateTime(timezone=True), nullable=True))
    op.add_column("solicitud", sa.Column("preferencia_sin_restriccion", sa.Boolean(), nullable=True))
    op.add_column("solicitud", sa.Column("tipo_generador", sa.String(20), nullable=True))
    op.create_check_constraint(
        op.f("ck_solicitud_preferencia"),
        "solicitud",
        "(preferencia_inicio IS NULL AND preferencia_fin IS NULL AND preferencia_sin_restriccion IS NULL) OR "
        "(preferencia_sin_restriccion IS TRUE AND preferencia_inicio IS NULL AND preferencia_fin IS NULL) OR "
        "(preferencia_sin_restriccion IS FALSE AND preferencia_inicio IS NOT NULL AND preferencia_fin IS NOT NULL "
        "AND preferencia_fin > preferencia_inicio)",
    )
    op.create_check_constraint(
        op.f("ck_solicitud_tipo_generador"),
        "solicitud",
        "tipo_generador IS NULL OR tipo_generador IN ('hogar','negocio')",
    )
    op.add_column("asignacion", sa.Column("acuerdo_observacion", sa.String(300), nullable=True))
    op.add_column("asignacion", sa.Column("programada_por", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_asignacion_programada_por_cuenta_operadora"),
        "asignacion",
        "cuenta_operadora",
        ["programada_por"],
        ["id"],
    )
    op.create_check_constraint(
        op.f("ck_asignacion_acuerdo_canal"),
        "asignacion",
        "acuerdo_canal IS NULL OR acuerdo_canal IN ('whatsapp','llamada','presencial')",
    )
    op.create_table(
        "resultado_material",
        sa.Column("resultado_orden_id", sa.Uuid(), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["resultado_orden_id"], ["resultado_orden.id"],
            name=op.f("fk_resultado_material_resultado_orden_id_resultado_orden"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["material_id"], ["material.id"],
            name=op.f("fk_resultado_material_material_id_material"),
        ),
        sa.PrimaryKeyConstraint("resultado_orden_id", "material_id", name=op.f("pk_resultado_material")),
    )
    op.create_index(op.f("ix_resultado_material_material_id"), "resultado_material", ["material_id"])
    op.execute("""
        INSERT INTO resultado_material (resultado_orden_id, material_id)
        SELECT origen.id, origen.elem::uuid
        FROM (
            SELECT r.id, elem
            FROM resultado_orden r
            CROSS JOIN LATERAL jsonb_array_elements_text(r.materiales_confirmados) AS elem
            WHERE jsonb_typeof(r.materiales_confirmados) = 'array'
              AND elem ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        ) AS origen
        JOIN material m ON m.id = origen.elem::uuid
        ON CONFLICT DO NOTHING
    """)
    op.add_column("habilitacion_piloto", sa.Column("revocada_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contenido_educativo", sa.Column("gremio_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_contenido_educativo_gremio_id_gremio"),
        "contenido_educativo",
        "gremio",
        ["gremio_id"],
        ["id"],
    )
    op.create_index(op.f("ix_contenido_educativo_gremio_id"), "contenido_educativo", ["gremio_id"])
    op.add_column("contenido_educativo", sa.Column("vigente_desde", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contenido_educativo", sa.Column("vigente_hasta", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        op.f("ck_contenido_educativo_tema"),
        "contenido_educativo",
        "tema IN ('separacion','huerta','horarios_rutas','servicio')",
    )
    op.create_check_constraint(
        op.f("ck_contenido_educativo_vigencia"),
        "contenido_educativo",
        "(vigente_desde IS NULL AND vigente_hasta IS NULL) OR "
        "(vigente_desde IS NOT NULL AND (vigente_hasta IS NULL OR vigente_hasta > vigente_desde))",
    )
    op.execute("UPDATE contenido_educativo SET tema = 'huerta' WHERE titulo = 'Qué va a la huerta'")
    op.drop_constraint("fk_cuenta_trabajador", "cuenta_operadora", type_="foreignkey")
    op.create_foreign_key(
        op.f("fk_cuenta_operadora_trabajador_id_recolector"),
        "cuenta_operadora",
        "recolector",
        ["trabajador_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint(op.f("fk_cuenta_operadora_trabajador_id_recolector"), "cuenta_operadora", type_="foreignkey")
    op.create_foreign_key("fk_cuenta_trabajador", "cuenta_operadora", "recolector", ["trabajador_id"], ["id"])
    op.drop_constraint(op.f("ck_contenido_educativo_vigencia"), "contenido_educativo", type_="check")
    op.drop_constraint(op.f("ck_contenido_educativo_tema"), "contenido_educativo", type_="check")
    op.drop_index(op.f("ix_contenido_educativo_gremio_id"), table_name="contenido_educativo")
    op.drop_constraint(op.f("fk_contenido_educativo_gremio_id_gremio"), "contenido_educativo", type_="foreignkey")
    for column in ("vigente_hasta", "vigente_desde", "gremio_id"):
        op.drop_column("contenido_educativo", column)
    op.drop_column("habilitacion_piloto", "revocada_at")
    op.drop_index(op.f("ix_resultado_material_material_id"), table_name="resultado_material")
    op.drop_table("resultado_material")
    op.drop_constraint(op.f("ck_asignacion_acuerdo_canal"), "asignacion", type_="check")
    op.drop_constraint(op.f("fk_asignacion_programada_por_cuenta_operadora"), "asignacion", type_="foreignkey")
    op.drop_column("asignacion", "programada_por")
    op.drop_column("asignacion", "acuerdo_observacion")
    op.drop_constraint(op.f("ck_solicitud_tipo_generador"), "solicitud", type_="check")
    op.drop_constraint(op.f("ck_solicitud_preferencia"), "solicitud", type_="check")
    for column in ("tipo_generador", "preferencia_sin_restriccion", "preferencia_fin", "preferencia_inicio"):
        op.drop_column("solicitud", column)
