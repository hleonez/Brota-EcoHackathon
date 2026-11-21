"""Material declarado como confirmado y explicación histórica del abono."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("resultado_orden", sa.Column("materiales_confirmados", JSONB(), nullable=True))
    op.add_column("movimiento_puntos", sa.Column("detalle_calculo", JSONB(), nullable=True))

def downgrade():
    op.drop_column("movimiento_puntos", "detalle_calculo")
    op.drop_column("resultado_orden", "materiales_confirmados")
