"""Acceso de recicladores y huerteros a sus asignaciones."""
from alembic import op
import sqlalchemy as sa
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("cuenta_operadora", sa.Column("trabajador_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_cuenta_trabajador", "cuenta_operadora", "recolector", ["trabajador_id"], ["id"])
    op.create_unique_constraint("uq_cuenta_operadora_trabajador_id", "cuenta_operadora", ["trabajador_id"])
    op.drop_constraint(op.f("ck_permiso_operador_rol"), "permiso_operador", type_="check")
    op.create_check_constraint(op.f("ck_permiso_operador_rol"), "permiso_operador", "rol IN ('coordinacion','fundacion','admin','reciclador','huertero')")

def downgrade():
    op.execute("DELETE FROM permiso_operador WHERE rol IN ('reciclador','huertero')")
    op.drop_constraint(op.f("ck_permiso_operador_rol"), "permiso_operador", type_="check")
    op.create_check_constraint(op.f("ck_permiso_operador_rol"), "permiso_operador", "rol IN ('coordinacion','fundacion','admin')")
    op.drop_column("cuenta_operadora", "trabajador_id")
