"""Temas y publicación de contenidos educativos."""
from alembic import op
import sqlalchemy as sa
revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("contenido_educativo", sa.Column("tema", sa.String(30), nullable=False, server_default="separacion"))
    op.add_column("contenido_educativo", sa.Column("publicado", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("contenido_educativo", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

def downgrade():
    for column in ("version", "publicado", "tema"):
        op.drop_column("contenido_educativo", column)
