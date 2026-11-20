"""Distinguir recicladores y huerteros sin perder referencias históricas."""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("recolector", sa.Column("tipo", sa.String(20), nullable=False, server_default="reciclador"))
    op.execute("""UPDATE recolector SET tipo = 'huertero'
        WHERE gremio_id IN (SELECT gremio_id FROM tipo_servicio WHERE codigo = 'ORGANICOS')""")
    op.create_check_constraint(op.f("ck_recolector_tipo"), "recolector", "tipo IN ('reciclador','huertero')")


def downgrade():
    op.drop_constraint(op.f("ck_recolector_tipo"), "recolector", type_="check")
    op.drop_column("recolector", "tipo")
