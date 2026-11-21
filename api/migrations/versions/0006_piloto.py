"""Habilitación explícita del piloto, sin activar usuarios existentes."""
from alembic import op
import sqlalchemy as sa
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("habilitacion_piloto",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("participante_id", sa.Uuid(), sa.ForeignKey("participante.id"), nullable=False),
        sa.Column("unidad_id", sa.Uuid(), sa.ForeignKey("unidad.id"), nullable=False),
        sa.Column("habilitada_por", sa.Uuid(), sa.ForeignKey("cuenta_operadora.id"), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("participante_id", "unidad_id"))
    for col in ("participante_id", "unidad_id", "habilitada_por"):
        op.create_index("ix_habilitacion_piloto_" + col, "habilitacion_piloto", [col])

def downgrade():
    op.drop_table("habilitacion_piloto")
