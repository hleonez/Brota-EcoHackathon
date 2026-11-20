"""Huertas, vigencias y evidencia operativa sin inventar historia."""
from alembic import op
import sqlalchemy as sa
revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("huerta",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("ubicacion", sa.String(200), nullable=False),
        sa.Column("gremio_id", sa.Uuid(), sa.ForeignKey("gremio.id"), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_huerta_gremio_id", "huerta", ["gremio_id"])
    for table, column, target in (("recolector", "huerta_id", "huerta"), ("resultado_orden", "trabajador_id", "recolector"), ("resultado_orden", "asignacion_id", "asignacion")):
        op.add_column(table, sa.Column(column, sa.Uuid(), nullable=True))
        op.create_foreign_key(f"fk_{table}_{column}_{target}", table, target, [column], ["id"])
    op.add_column("asignacion", sa.Column("acuerdo_canal", sa.String(20), nullable=True))
    op.add_column("habilitacion_piloto", sa.Column("vigente_desde", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.add_column("habilitacion_piloto", sa.Column("vigente_hasta", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(op.f("ck_habilitacion_piloto_vigencia"), "habilitacion_piloto", "vigente_hasta IS NULL OR vigente_hasta > vigente_desde")

def downgrade():
    op.drop_constraint(op.f("ck_habilitacion_piloto_vigencia"), "habilitacion_piloto", type_="check")
    for table, column in (("habilitacion_piloto", "vigente_hasta"), ("habilitacion_piloto", "vigente_desde"), ("asignacion", "acuerdo_canal"), ("resultado_orden", "asignacion_id"), ("resultado_orden", "trabajador_id"), ("recolector", "huerta_id")):
        op.drop_column(table, column)
    op.drop_table("huerta")
