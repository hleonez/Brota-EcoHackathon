"""Conversaciones de Brisa (con retención) y parámetros editables del programa."""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mensaje_conversacion",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("celular_normalizado", sa.String(20), nullable=False),
        sa.Column("participante_id", sa.Uuid(), nullable=True),
        sa.Column("direccion", sa.String(10), nullable=False),
        sa.Column("tipo", sa.String(15), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("wamid", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("direccion IN ('entrante','saliente')", name=op.f("ck_mensaje_conversacion_direccion")),
        sa.CheckConstraint(
            "tipo IN ('texto','audio','imagen','interactivo','plantilla','sistema')",
            name=op.f("ck_mensaje_conversacion_tipo"),
        ),
        sa.ForeignKeyConstraint(
            ["participante_id"], ["participante.id"],
            name=op.f("fk_mensaje_conversacion_participante_id_participante"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mensaje_conversacion")),
        sa.UniqueConstraint("wamid", name=op.f("uq_mensaje_conversacion_wamid")),
    )
    op.create_index(
        "ix_mensaje_conversacion_participante_id", "mensaje_conversacion", ["participante_id"]
    )
    op.create_index(
        "ix_mensaje_conversacion_celular_creado", "mensaje_conversacion", ["celular_normalizado", "created_at"]
    )

    op.create_table(
        "parametro_programa",
        sa.Column("clave", sa.String(40), nullable=False),
        sa.Column("valor", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("actualizado_por", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["actualizado_por"], ["cuenta_operadora.id"],
            name=op.f("fk_parametro_programa_actualizado_por_cuenta_operadora"),
        ),
        sa.PrimaryKeyConstraint("clave", name=op.f("pk_parametro_programa")),
    )


def downgrade():
    op.drop_table("parametro_programa")
    op.drop_index("ix_mensaje_conversacion_celular_creado", table_name="mensaje_conversacion")
    op.drop_index("ix_mensaje_conversacion_participante_id", table_name="mensaje_conversacion")
    op.drop_table("mensaje_conversacion")
