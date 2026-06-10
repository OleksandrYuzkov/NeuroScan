from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_users_email", "users", ["email"], unique=True)


    op.create_table(
        "scan_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("file_name", sa.String(512), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("predicted_label", sa.String(100), nullable=False),
        sa.Column("risk_score", sa.Float, nullable=False),
        sa.Column("probabilities", JSONB, nullable=False),
        sa.Column("image_features", JSONB, nullable=True),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("model_architecture", sa.String(100), nullable=True),
        sa.Column("glioma_margin", sa.Float, nullable=True),
        sa.Column("gradcam_generated", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_scan_results_user_id", "scan_results", ["user_id"])
    op.create_index("idx_scan_results_session_id", "scan_results", ["session_id"])
    op.create_index("idx_scan_results_sha256", "scan_results", ["file_sha256"])
    op.create_index("idx_scan_results_created_at", "scan_results", [sa.text("created_at DESC")])


    op.create_table(
        "scan_images",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("scan_result_id", UUID(as_uuid=True), sa.ForeignKey("scan_results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_type", sa.String(50), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_scan_images_result_id", "scan_images", ["scan_result_id"])


    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("idx_audit_log_created_at", "audit_log", [sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("scan_images")
    op.drop_table("scan_results")
    op.drop_table("users")
