"""Preferencia horaria y estado programada."""
from alembic import op
import sqlalchemy as sa
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("solicitud", sa.Column("preferencia_horaria", sa.String(300), nullable=True))
    op.drop_constraint(op.f("ck_orden_estado"), "orden", type_="check")
    op.create_check_constraint(op.f("ck_orden_estado"), "orden", "estado IN ('nueva','asignada','programada','recogida','rechazada','cancelada')")

def downgrade():
    op.execute("UPDATE orden SET estado = 'asignada' WHERE estado = 'programada'")
    op.drop_constraint(op.f("ck_orden_estado"), "orden", type_="check")
    op.create_check_constraint(op.f("ck_orden_estado"), "orden", "estado IN ('nueva','asignada','recogida','rechazada','cancelada')")
    op.drop_column("solicitud", "preferencia_horaria")
