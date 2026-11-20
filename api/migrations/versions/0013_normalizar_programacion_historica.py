"""Reconoce franjas ya registradas por versiones anteriores de la API."""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE orden
        SET estado = 'programada', version = version + 1
        WHERE estado = 'asignada'
          AND EXISTS (
              SELECT 1
              FROM asignacion
              WHERE asignacion.orden_id = orden.id
                AND asignacion.vigente_hasta IS NULL
                AND asignacion.inicio IS NOT NULL
                AND asignacion.fin > asignacion.inicio
          )
    """)


def downgrade():
    # 0012 ya admite programada. No se puede distinguir una programación
    # histórica normalizada de una registrada después de aplicar 0013.
    pass
