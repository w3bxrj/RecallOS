"""add_is_vision_and_notice_to_jobs

Revision ID: 7a8b9c0d1e2f
Revises: 513a4776015a
Create Date: 2026-10-27 13:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a8b9c0d1e2f'
down_revision: Union[str, None] = '513a4776015a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_vision', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('notice', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_column('notice')
        batch_op.drop_column('is_vision')
