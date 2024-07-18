"""add pending email

Revision ID: a49240e774e6
Revises: e7c2ca8b223a
Create Date: 2024-07-18 15:30:35.738353

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a49240e774e6'
down_revision = 'e7c2ca8b223a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pending_email',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nr_num', sa.String(length=30), nullable=False),
    sa.Column('decision', sa.String(length=30), nullable=False),
    )


def downgrade():
    op.drop_table('pending_email')
