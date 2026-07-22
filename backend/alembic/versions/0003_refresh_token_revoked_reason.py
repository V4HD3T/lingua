"""refresh token revoked reason

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-22 23:40:00.000000

Adds refreshtoken.revoked_reason, which /auth/refresh uses to tell a
rotation apart from a deliberate revocation. Nullable with no default on
purpose: existing rows are already-revoked or already-expired tokens, and
a NULL reason reads as "not a rotation", so none of them can take the
grace path added in v0.1.8.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('refreshtoken', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('revoked_reason', sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('refreshtoken', schema=None) as batch_op:
        batch_op.drop_column('revoked_reason')
