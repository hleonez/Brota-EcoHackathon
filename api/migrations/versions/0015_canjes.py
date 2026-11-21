"""Canjes de Moneda Verde: aliado, ítem, reserva y libro de débito."""

from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "aliado",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("gremio_id", sa.Uuid(), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["gremio_id"], ["gremio.id"], name=op.f("fk_aliado_gremio_id_gremio")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_aliado")),
    )
    op.create_index("ix_aliado_gremio_id", "aliado", ["gremio_id"])
    op.create_table(
        "item_canje",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("aliado_id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("costo_puntos", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("existencias", sa.Integer(), nullable=True),
        sa.Column("activo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("costo_puntos > 0", name=op.f("ck_item_canje_costo_positivo")),
        sa.CheckConstraint("existencias IS NULL OR existencias >= 0", name=op.f("ck_item_canje_existencias")),
        sa.ForeignKeyConstraint(["aliado_id"], ["aliado.id"], name=op.f("fk_item_canje_aliado_id_aliado")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_item_canje")),
    )
    op.create_index("ix_item_canje_aliado_id", "item_canje", ["aliado_id"])
    op.create_table(
        "canje",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("participante_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("costo_unitario_aplicado", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("total_puntos", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="reservado", nullable=False),
        sa.Column("registrado_por", sa.Uuid(), nullable=True),
        sa.Column("entregado_por", sa.Uuid(), nullable=True),
        sa.Column("entregado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("estado IN ('reservado','entregado','cancelado')", name=op.f("ck_canje_estado")),
        sa.CheckConstraint("cantidad > 0", name=op.f("ck_canje_cantidad_positiva")),
        sa.CheckConstraint("costo_unitario_aplicado > 0", name=op.f("ck_canje_costo_positivo")),
        sa.CheckConstraint("total_puntos > 0", name=op.f("ck_canje_total_positivo")),
        sa.CheckConstraint(
            "total_puntos = costo_unitario_aplicado * cantidad", name=op.f("ck_canje_total")
        ),
        sa.ForeignKeyConstraint(
            ["participante_id"], ["participante.id"], name=op.f("fk_canje_participante_id_participante")
        ),
        sa.ForeignKeyConstraint(["item_id"], ["item_canje.id"], name=op.f("fk_canje_item_id_item_canje")),
        sa.ForeignKeyConstraint(
            ["registrado_por"], ["cuenta_operadora.id"], name=op.f("fk_canje_registrado_por_cuenta_operadora")
        ),
        sa.ForeignKeyConstraint(
            ["entregado_por"], ["cuenta_operadora.id"], name=op.f("fk_canje_entregado_por_cuenta_operadora")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_canje")),
    )
    op.create_index("ix_canje_participante_id", "canje", ["participante_id"])
    op.create_index("ix_canje_item_id", "canje", ["item_id"])
    op.add_column("movimiento_puntos", sa.Column("canje_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_movimiento_puntos_canje_id_canje"), "movimiento_puntos", "canje", ["canje_id"], ["id"]
    )
    op.create_index("ix_movimiento_puntos_canje_id", "movimiento_puntos", ["canje_id"])
    # Los abonos ya guardados tienen delta > 0 y otro tipo: estas reglas no los tocan.
    op.create_check_constraint(
        op.f("ck_movimiento_puntos_debito_canje_negativo"),
        "movimiento_puntos",
        "tipo <> 'debito_canje' OR delta < 0",
    )
    op.create_check_constraint(
        op.f("ck_movimiento_puntos_reintegro_positivo"),
        "movimiento_puntos",
        "tipo <> 'reintegro' OR delta > 0",
    )


def downgrade():
    op.drop_constraint(op.f("ck_movimiento_puntos_reintegro_positivo"), "movimiento_puntos", type_="check")
    op.drop_constraint(op.f("ck_movimiento_puntos_debito_canje_negativo"), "movimiento_puntos", type_="check")
    op.drop_index("ix_movimiento_puntos_canje_id", table_name="movimiento_puntos")
    op.drop_constraint(op.f("fk_movimiento_puntos_canje_id_canje"), "movimiento_puntos", type_="foreignkey")
    op.drop_column("movimiento_puntos", "canje_id")
    op.drop_table("canje")
    op.drop_table("item_canje")
    op.drop_table("aliado")
