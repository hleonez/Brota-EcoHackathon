"""Archivos de evidencia e IA de operación: tiquete en disco y dictado sin audio."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "archivo",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("proposito", sa.String(length=30), nullable=False),
        sa.Column("mime", sa.String(length=80), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=80), nullable=False),
        sa.Column("expira_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eliminado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("proposito IN ('tiquete','video_educativo')", name=op.f("ck_archivo_proposito")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_archivo")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_archivo_storage_key")),
    )
    op.create_table(
        "procesamiento_ia",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("archivo_id", sa.Uuid(), nullable=True),
        sa.Column("pesaje_id", sa.Uuid(), nullable=True),
        sa.Column("tarea", sa.String(length=30), nullable=False),
        sa.Column("proveedor", sa.String(length=40), nullable=False),
        sa.Column("modelo", sa.String(length=120), nullable=False),
        sa.Column("propuesta", JSONB(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("tarea IN ('leer_tiquete','dictado')", name=op.f("ck_procesamiento_ia_tarea")),
        sa.CheckConstraint("estado IN ('propuesto','confirmado','descartado')", name=op.f("ck_procesamiento_ia_estado")),
        sa.ForeignKeyConstraint(
            ["archivo_id"], ["archivo.id"], name=op.f("fk_procesamiento_ia_archivo_id_archivo")
        ),
        sa.ForeignKeyConstraint(
            ["pesaje_id"], ["pesaje.id"], name=op.f("fk_procesamiento_ia_pesaje_id_pesaje")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_procesamiento_ia")),
    )
    op.create_index(op.f("ix_procesamiento_ia_archivo_id"), "procesamiento_ia", ["archivo_id"])
    op.create_index(op.f("ix_procesamiento_ia_pesaje_id"), "procesamiento_ia", ["pesaje_id"])
    op.create_table(
        "pesaje_archivo",
        sa.Column("pesaje_id", sa.Uuid(), nullable=False),
        sa.Column("archivo_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["pesaje_id"], ["pesaje.id"],
            name=op.f("fk_pesaje_archivo_pesaje_id_pesaje"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["archivo_id"], ["archivo.id"], name=op.f("fk_pesaje_archivo_archivo_id_archivo")
        ),
        sa.PrimaryKeyConstraint("pesaje_id", "archivo_id", name=op.f("pk_pesaje_archivo")),
    )
    op.create_index(op.f("ix_pesaje_archivo_archivo_id"), "pesaje_archivo", ["archivo_id"])


def downgrade():
    op.drop_index(op.f("ix_pesaje_archivo_archivo_id"), table_name="pesaje_archivo")
    op.drop_table("pesaje_archivo")
    op.drop_index(op.f("ix_procesamiento_ia_pesaje_id"), table_name="procesamiento_ia")
    op.drop_index(op.f("ix_procesamiento_ia_archivo_id"), table_name="procesamiento_ia")
    op.drop_table("procesamiento_ia")
    op.drop_table("archivo")
