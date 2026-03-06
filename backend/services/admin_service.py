"""
Team-scoped admin business logic with hierarchical visibility.

Every function accepts allowed_team_ids: list[int] — the set of team IDs
the calling manager is authorized to view/manage. This list is computed
by get_allowed_team_ids() and passed in by the blueprint layer.

No function in this module trusts any team_id from client input.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

from backend.models import (
    db, User, Team, Membership, Manager, TeamChangeRequest, TelemetryEvent,
)
from backend.audit import log_action
from backend.productivity import bucketize, summarize_buckets
from backend.utils import resolve_range

logger = logging.getLogger("backend.services.admin_service")


def _lan_ids_for_teams(team_ids: list[int]) -> list[str]:
    """Return LAN IDs of users with active membership in any of the given teams."""
    if not team_ids:
        return []
    rows = (
        db.session.query(User.lan_id)
        .join(Membership, Membership.user_id == User.id)
        .filter(Membership.team_id.in_(team_ids), Membership.active.is_(True))
        .all()
    )
    return [r[0] for r in rows]


def get_team_info(team_id: int | None, allowed_team_ids: list[int] | None = None) -> dict:
    """Return basic team metadata."""
    if team_id is None:
        return {"id": None, "name": "All Teams (Demo)", "member_count": 0}

    team = db.session.get(Team, team_id)
    if not team:
        return {"id": team_id, "name": "Unknown", "member_count": 0}

    scope = allowed_team_ids or [team_id]
    member_count = Membership.query.filter(
        Membership.team_id.in_(scope), Membership.active.is_(True),
    ).count()

    return {
        "id": team.id,
        "name": team.name,
        "member_count": member_count,
    }


def get_team_tree(allowed_team_ids: list[int]) -> list[dict]:
    """Return the team hierarchy restricted to the allowed subtree."""
    if not allowed_team_ids:
        teams = Team.query.order_by(Team.name).all()
    else:
        teams = Team.query.filter(Team.id.in_(allowed_team_ids)).order_by(Team.name).all()

    result = []
    for t in teams:
        member_count = Membership.query.filter_by(
            team_id=t.id, active=True,
        ).count()
        mgr = Manager.query.filter_by(team_id=t.id).first()
        result.append({
            "id": t.id,
            "name": t.name,
            "parent_team_id": t.parent_team_id,
            "member_count": member_count,
            "manager_name": mgr.user.display_name if mgr and mgr.user else None,
        })
    return result


def list_team_users(allowed_team_ids: list[int]) -> list[User]:
    """Return all users with active membership in the allowed teams."""
    if not allowed_team_ids:
        return User.query.order_by(User.display_name).all()

    return (
        User.query
        .join(Membership, Membership.user_id == User.id)
        .filter(Membership.team_id.in_(allowed_team_ids), Membership.active.is_(True))
        .order_by(User.display_name)
        .all()
    )


def get_team_leaderboard(allowed_team_ids: list[int], config) -> list[dict]:
    """Leaderboard scoped to the manager's allowed team subtree."""
    start, end = resolve_range(config)

    q = TelemetryEvent.query.filter(
        TelemetryEvent.timestamp >= start,
        TelemetryEvent.timestamp < end,
    )

    if allowed_team_ids:
        lan_ids = _lan_ids_for_teams(allowed_team_ids)
        if not lan_ids:
            return []
        q = q.filter(TelemetryEvent.user_id.in_(lan_ids))

    all_events = q.order_by(TelemetryEvent.timestamp.asc()).all()

    user_events: dict[str, list] = defaultdict(list)
    for ev in all_events:
        user_events[ev.user_id].append(ev)

    rows: list[dict] = []
    for uid, events in user_events.items():
        buckets = bucketize(events, config)
        summary = summarize_buckets(buckets)
        total = summary.get("total_seconds", 0)
        prod = summary.get("productive", 0)
        non_prod = summary.get("non_productive", 0)
        rows.append({
            "user_id": uid,
            "productive_sec": prod,
            "non_productive_sec": non_prod,
            "total_sec": total,
            "productive_pct": round(prod / total * 100, 1) if total else 0.0,
            "non_productive_pct": round(non_prod / total * 100, 1) if total else 0.0,
        })

    rows.sort(key=lambda r: r["non_productive_pct"], reverse=True)
    return rows


def assign_user_to_team(
    user_id: int, team_id: int, actor_id: int | None,
) -> dict:
    """
    Assign a user to a team within the manager's subtree.
    If the user is already in another team, create a TeamChangeRequest.
    """
    user = db.session.get(User, user_id)
    if not user:
        return {"error": "User not found", "status_code": 404}

    existing = Membership.query.filter_by(user_id=user_id, active=True).first()

    if existing and existing.team_id == team_id:
        return {"message": "User is already in this team", "status_code": 200}

    if existing and existing.team_id != team_id:
        pending = TeamChangeRequest.query.filter_by(
            user_id=user_id, to_team_id=team_id, status="pending",
        ).first()
        if pending:
            return {"message": "A transfer request already exists", "request_id": pending.id, "status_code": 200}

        change_req = TeamChangeRequest(
            user_id=user_id,
            from_team_id=existing.team_id,
            to_team_id=team_id,
            requested_by=actor_id or 0,
            status="pending",
        )
        db.session.add(change_req)
        db.session.commit()

        log_action(
            str(actor_id), "team_move_requested",
            target_user=user.lan_id,
            detail=f"from_team={existing.team_id} to_team={team_id} request_id={change_req.id}",
        )
        return {
            "message": "User is in another team. A transfer request has been created.",
            "request_id": change_req.id,
            "status_code": 202,
        }

    membership = Membership(user_id=user_id, team_id=team_id, active=True)
    db.session.add(membership)
    db.session.commit()

    log_action(
        str(actor_id), "user_assigned_to_team",
        target_user=user.lan_id,
        detail=f"team_id={team_id}",
    )
    return {"message": "User assigned to team", "status_code": 200}


def remove_user_from_team(
    user_id: int, team_id: int, actor_id: int | None,
) -> dict:
    """Remove a user from a team by deactivating their membership."""
    user = db.session.get(User, user_id)
    if not user:
        return {"error": "User not found", "status_code": 404}

    membership = Membership.query.filter_by(
        user_id=user_id, team_id=team_id, active=True,
    ).first()
    if not membership:
        return {"error": "User is not an active member of this team", "status_code": 404}

    membership.active = False
    membership.end_at = datetime.now(timezone.utc)
    db.session.commit()

    log_action(
        str(actor_id), "user_removed_from_team",
        target_user=user.lan_id,
        detail=f"team_id={team_id}",
    )
    return {"message": "User removed from team", "status_code": 200}


def request_move_to_team(
    user_id: int, to_team_id: int, actor_id: int | None,
) -> dict:
    """Create a pending team change request."""
    user = db.session.get(User, user_id)
    if not user:
        return {"error": "User not found", "status_code": 404}

    existing = Membership.query.filter_by(user_id=user_id, active=True).first()
    from_team_id = existing.team_id if existing else None

    if from_team_id == to_team_id:
        return {"message": "User is already in the target team", "status_code": 200}

    pending = TeamChangeRequest.query.filter_by(
        user_id=user_id, to_team_id=to_team_id, status="pending",
    ).first()
    if pending:
        return {"message": "A transfer request already exists", "request_id": pending.id, "status_code": 200}

    change_req = TeamChangeRequest(
        user_id=user_id,
        from_team_id=from_team_id,
        to_team_id=to_team_id,
        requested_by=actor_id or 0,
        status="pending",
    )
    db.session.add(change_req)
    db.session.commit()

    log_action(
        str(actor_id), "team_move_requested",
        target_user=user.lan_id,
        detail=f"from_team={from_team_id} to_team={to_team_id} request_id={change_req.id}",
    )
    return {
        "message": "Transfer request created",
        "request_id": change_req.id,
        "status_code": 202,
    }


def approve_team_change(
    request_id: int, approver_id: int | None, approver_allowed_team_ids: list[int],
) -> dict:
    """Approve a team change request. Approver must have scope over source team."""
    change_req = db.session.get(TeamChangeRequest, request_id)
    if not change_req:
        return {"error": "Request not found", "status_code": 404}

    if change_req.status != "pending":
        return {"error": f"Request is already {change_req.status}", "status_code": 400}

    if approver_allowed_team_ids:
        if change_req.from_team_id not in approver_allowed_team_ids:
            approver_user = db.session.get(User, approver_id) if approver_id else None
            if not (approver_user and approver_user.role == "superadmin"):
                return {"error": "Source team is outside your scope", "status_code": 403}

    old_membership = Membership.query.filter_by(
        user_id=change_req.user_id, active=True,
    ).first()
    if old_membership:
        old_membership.active = False
        old_membership.end_at = datetime.now(timezone.utc)

    new_membership = Membership(
        user_id=change_req.user_id,
        team_id=change_req.to_team_id,
        active=True,
    )
    db.session.add(new_membership)

    change_req.status = "approved"
    change_req.approved_by = approver_id
    change_req.resolved_at = datetime.now(timezone.utc)
    db.session.commit()

    user = db.session.get(User, change_req.user_id)
    log_action(
        str(approver_id), "team_move_approved",
        target_user=user.lan_id if user else str(change_req.user_id),
        detail=f"request_id={request_id} from={change_req.from_team_id} to={change_req.to_team_id}",
    )
    return {"message": "Transfer approved", "status_code": 200}
