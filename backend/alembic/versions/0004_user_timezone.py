"""user timezone

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-23 00:15:00.000000

Adds user.timezone, the IANA zone deciding where each learner's day
starts -- see app/services/user_time.py.

NOT NULL with server_default 'UTC': the column can't be null on a table
with existing rows without one, and 'UTC' is exactly the behaviour those
rows had before this migration, so nobody's streak shifts underneath them
on upgrade. The frontend reports the real zone on the next visit.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'timezone',
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default='UTC',
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('timezone')
