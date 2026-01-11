"""Add is_auto_generated and source_bom_name to purchase_orders

Revision ID: 001_add_po_auto_gen
Revises:
Create Date: 2025-01-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_add_po_auto_gen'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_auto_generated column with default False
    op.add_column(
        'purchase_orders',
        sa.Column('is_auto_generated', sa.Boolean(), nullable=True, server_default='false')
    )

    # Add source_bom_name column
    op.add_column(
        'purchase_orders',
        sa.Column('source_bom_name', sa.String(255), nullable=True)
    )

    # Update existing rows to have is_auto_generated = True if they have a bom_id
    op.execute("""
        UPDATE purchase_orders
        SET is_auto_generated = true
        WHERE bom_id IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_column('purchase_orders', 'source_bom_name')
    op.drop_column('purchase_orders', 'is_auto_generated')
