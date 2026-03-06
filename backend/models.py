"""
SQLAlchemy models for Zinnia Axion.

Core entities:
  TelemetryEvent  — raw sample from tracker agent
  AuditLog        — tamper-evident record of security-relevant actions

Enterprise entities:
  User            — employee record linked to LAN ID
  Team            — organizational team
  Membership      — user <-> team assignment (one active per user)
  Manager         — maps a manager-role user to their team
  TrackerDeviceToken — hashed API token for tracker auth
  TeamChangeRequest  — cross-team transfer workflow
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _utcnow():
    return datetime.now(timezone.utc)


# ─── Enterprise entities ────────────────────────────────────────────


class User(db.Model):
    __tablename__ = "users"

    id: int = db.Column(db.Integer, primary_key=True, autoincrement=True)
    lan_id: str = db.Column(db.String(128), unique=True, nullable=False, index=True)
    email: str = db.Column(db.String(256), nullable=True, index=True)
    display_name: str = db.Column(db.String(256), nullable=True)
    role: str = db.Column(
        db.String(32), nullable=False, default="user", server_default="user"
    )
    created_at: datetime = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at: datetime = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    memberships = db.relationship("Membership", back_populates="user", lazy="dynamic")
    manager_record = db.relationship("Manager", back_populates="user", uselist=False)

    @property
    def active_membership(self):
        return self.memberships.filter_by(active=True).first()

    @property
    def active_team_id(self):
        m = self.active_membership
        return m.team_id if m else None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "lan_id": self.lan_id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role,
            "active_team_id": self.active_team_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<User id={self.id} lan_id={self.lan_id!r} role={self.role!r}>"


class Team(db.Model):
    __tablename__ = "teams"

    id: int = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name: str = db.Column(db.String(128), unique=True, nullable=False)
    parent_team_id: int | None = db.Column(
        db.Integer,
        db.ForeignKey("teams.id"),
        nullable=True,
        index=True,
    )
    created_at: datetime = db.Column(db.DateTime, nullable=False, default=_utcnow)

    parent = db.relationship(
        "Team", remote_side="Team.id", backref=db.backref("children", lazy="dynamic"),
    )
    memberships = db.relationship("Membership", back_populates="team", lazy="dynamic")
    managers = db.relationship("Manager", back_populates="team", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "parent_team_id": self.parent_team_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Team id={self.id} name={self.name!r} parent={self.parent_team_id}>"


class Membership(db.Model):
    __tablename__ = "memberships"

    id: int = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id: int = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    team_id: int = db.Column(
        db.Integer, db.ForeignKey("teams.id"), nullable=False, index=True
    )
    active: bool = db.Column(
        db.Boolean, nullable=False, default=True, server_default=db.text("true")
    )
    start_at: datetime = db.Column(db.DateTime, nullable=False, default=_utcnow)
    end_at: datetime = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", back_populates="memberships")
    team = db.relationship("Team", back_populates="memberships")

    __table_args__ = (
        db.Index(
            "ix_memberships_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=db.text("active = true"),
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "team_id": self.team_id,
            "active": self.active,
            "start_at": self.start_at.isoformat() if self.start_at else None,
            "end_at": self.end_at.isoformat() if self.end_at else None,
        }

    def __repr__(self) -> str:
        state = "active" if self.active else "inactive"
        return f"<Membership id={self.id} user={self.user_id} team={self.team_id} {state}>"


class Manager(db.Model):
    __tablename__ = "managers"

    user_id: int = db.Column(
        db.Integer, db.ForeignKey("users.id"), primary_key=True
    )
    team_id: int = db.Column(
        db.Integer, db.ForeignKey("teams.id"), nullable=False, index=True
    )

    user = db.relationship("User", back_populates="manager_record")
    team = db.relationship("Team", back_populates="managers")

    def __repr__(self) -> str:
        return f"<Manager user_id={self.user_id} team_id={self.team_id}>"


class TrackerDeviceToken(db.Model):
    __tablename__ = "tracker_device_tokens"

    id: int = db.Column(db.Integer, primary_key=True, autoincrement=True)
    token_hash: str = db.Column(db.String(256), nullable=False, index=True)
    user_id: int = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True
    )
    team_id: int = db.Column(
        db.Integer, db.ForeignKey("teams.id"), nullable=False
    )
    description: str = db.Column(db.String(256), nullable=True)
    expires_at: datetime = db.Column(db.DateTime, nullable=True)
    revoked: bool = db.Column(
        db.Boolean, nullable=False, default=False, server_default=db.text("false")
    )
    created_at: datetime = db.Column(db.DateTime, nullable=False, default=_utcnow)
    rotated_from_id: int = db.Column(
        db.Integer, db.ForeignKey("tracker_device_tokens.id"), nullable=True
    )

    user = db.relationship("User", foreign_keys=[user_id])
    team = db.relationship("Team")
    rotated_from = db.relationship(
        "TrackerDeviceToken", remote_side=[id], foreign_keys=[rotated_from_id]
    )

    def is_valid(self) -> bool:
        if self.revoked:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "team_id": self.team_id,
            "user_id": self.user_id,
            "description": self.description,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked": self.revoked,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TeamChangeRequest(db.Model):
    __tablename__ = "team_change_requests"

    id: int = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id: int = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    from_team_id: int = db.Column(
        db.Integer, db.ForeignKey("teams.id"), nullable=True
    )
    to_team_id: int = db.Column(
        db.Integer, db.ForeignKey("teams.id"), nullable=False
    )
    requested_by: int = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    approved_by: int = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True
    )
    status: str = db.Column(
        db.String(32), nullable=False, default="pending", server_default="pending"
    )
    created_at: datetime = db.Column(db.DateTime, nullable=False, default=_utcnow)
    resolved_at: datetime = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", foreign_keys=[user_id])
    from_team = db.relationship("Team", foreign_keys=[from_team_id])
    to_team = db.relationship("Team", foreign_keys=[to_team_id])
    requester = db.relationship("User", foreign_keys=[requested_by])
    approver = db.relationship("User", foreign_keys=[approved_by])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "from_team_id": self.from_team_id,
            "to_team_id": self.to_team_id,
            "requested_by": self.requested_by,
            "approved_by": self.approved_by,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


# ─── Telemetry ──────────────────────────────────────────────────────


class TelemetryEvent(db.Model):
    """
    A single telemetry sample (~ 1-second granularity from the tracker).
    user_id is the employee's LAN ID string — linked to User.lan_id by value.
    """

    __tablename__ = "telemetry_events"

    id: int = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id: str = db.Column(
        db.String(128), nullable=False, default="default",
        server_default="default", index=True,
    )
    timestamp: datetime = db.Column(
        db.DateTime, nullable=False, default=_utcnow, index=True,
    )
    app_name: str = db.Column(db.String(256), nullable=False, default="unknown")
    window_title: str = db.Column(db.String(1024), nullable=False, default="")
    keystroke_count: int = db.Column(db.Integer, nullable=False, default=0)
    mouse_clicks: int = db.Column(db.Integer, nullable=False, default=0)
    mouse_distance: float = db.Column(db.Float, nullable=False, default=0.0)
    idle_seconds: float = db.Column(db.Float, nullable=False, default=0.0)
    distraction_visible: bool = db.Column(
        db.Boolean, nullable=False, default=False, server_default=db.text("false"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "app_name": self.app_name,
            "window_title": self.window_title,
            "keystroke_count": self.keystroke_count,
            "mouse_clicks": self.mouse_clicks,
            "mouse_distance": self.mouse_distance,
            "idle_seconds": self.idle_seconds,
            "distraction_visible": self.distraction_visible,
        }

    def __repr__(self) -> str:
        return (
            f"<TelemetryEvent id={self.id} user={self.user_id!r} app={self.app_name!r} "
            f"keys={self.keystroke_count} clicks={self.mouse_clicks} "
            f"idle={self.idle_seconds:.1f}s>"
        )


# ─── Audit Log ──────────────────────────────────────────────────────


class AuditLog(db.Model):
    """Immutable record of a security-relevant action."""

    __tablename__ = "audit_log"

    id: int = db.Column(db.Integer, primary_key=True, autoincrement=True)
    timestamp: datetime = db.Column(
        db.DateTime, nullable=False, default=_utcnow, index=True,
    )
    actor: str = db.Column(db.String(256), nullable=False, default="unknown")
    action: str = db.Column(db.String(128), nullable=False, index=True)
    target_user: str = db.Column(db.String(128), nullable=True)
    ip_address: str = db.Column(db.String(64), nullable=True)
    user_agent: str = db.Column(db.String(512), nullable=True)
    detail: str = db.Column(db.String(1024), nullable=True)

    # v2 fields for enterprise hardening
    actor_user_id: int = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True
    )
    actor_team_id: int = db.Column(
        db.Integer, db.ForeignKey("teams.id"), nullable=True
    )
    target_team_id: int = db.Column(
        db.Integer, db.ForeignKey("teams.id"), nullable=True
    )
    request_id: str = db.Column(db.String(64), nullable=True, index=True)
    extra_data: str = db.Column(db.Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "action": self.action,
            "target_user": self.target_user,
            "ip_address": self.ip_address,
            "detail": self.detail,
            "actor_user_id": self.actor_user_id,
            "actor_team_id": self.actor_team_id,
            "target_team_id": self.target_team_id,
            "request_id": self.request_id,
        }

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} action={self.action!r} "
            f"actor={self.actor!r} target={self.target_user!r}>"
        )
