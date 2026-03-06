"""
Backfill script — populate User, Team, Membership, and Manager records
from existing telemetry data.

Steps:
  1. Create a 'default' team if it doesn't exist.
  2. Scan distinct user_id values from telemetry_events.
  3. For each, create a User record (lan_id = user_id) if missing.
  4. Create an active Membership in the default team if the user has none.
  5. If ADMIN_USERNAME env var is set, create/update that user as manager
     of the default team.
  6. Report orphan users (users with no telemetry data).

Usage:
    python -m scripts.backfill_teams
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app import create_app
from backend.config import Config
from backend.models import db, User, Team, Membership, Manager, TelemetryEvent


def backfill():
    config = Config()
    app = create_app(config)

    with app.app_context():
        # 1. Ensure default team exists
        default_team = Team.query.filter_by(name="Default").first()
        if not default_team:
            default_team = Team(name="Default")
            db.session.add(default_team)
            db.session.commit()
            print(f"Created 'Default' team (id={default_team.id})")
        else:
            print(f"Default team already exists (id={default_team.id})")

        # 2. Scan distinct user_ids from telemetry
        distinct_user_ids = [
            r[0] for r in
            db.session.query(TelemetryEvent.user_id).distinct().all()
        ]
        print(f"Found {len(distinct_user_ids)} distinct user_ids in telemetry_events")

        created_users = 0
        created_memberships = 0

        for uid in distinct_user_ids:
            # 3. Create User record if missing
            user = User.query.filter_by(lan_id=uid).first()
            if not user:
                user = User(
                    lan_id=uid,
                    display_name=uid,
                    role="user",
                )
                db.session.add(user)
                db.session.flush()
                created_users += 1

            # 4. Create active membership if missing
            active = Membership.query.filter_by(user_id=user.id, active=True).first()
            if not active:
                membership = Membership(
                    user_id=user.id,
                    team_id=default_team.id,
                    active=True,
                )
                db.session.add(membership)
                created_memberships += 1

        db.session.commit()
        print(f"Created {created_users} user records, {created_memberships} memberships")

        # 5. Set up admin manager
        admin_username = os.getenv("ADMIN_USERNAME", "admin")
        admin_email = os.getenv("ADMIN_EMAIL", "")

        admin_user = User.query.filter_by(lan_id=admin_username).first()
        if not admin_user and admin_email:
            admin_user = User.query.filter_by(email=admin_email).first()

        if not admin_user:
            admin_user = User(
                lan_id=admin_username,
                email=admin_email or f"{admin_username}@local",
                display_name=admin_username.title(),
                role="manager",
            )
            db.session.add(admin_user)
            db.session.flush()
            print(f"Created admin user: {admin_username} (id={admin_user.id})")
        else:
            if admin_user.role not in ("manager", "superadmin"):
                admin_user.role = "manager"
                print(f"Updated {admin_username} role to 'manager'")

        # Ensure admin has active membership
        admin_membership = Membership.query.filter_by(
            user_id=admin_user.id, active=True
        ).first()
        if not admin_membership:
            admin_membership = Membership(
                user_id=admin_user.id,
                team_id=default_team.id,
                active=True,
            )
            db.session.add(admin_membership)

        # Ensure manager record exists
        manager_record = Manager.query.filter_by(user_id=admin_user.id).first()
        if not manager_record:
            manager_record = Manager(
                user_id=admin_user.id,
                team_id=default_team.id,
            )
            db.session.add(manager_record)
            print(f"Created manager record for {admin_username} -> Default team")

        db.session.commit()

        # 6. Report summary
        total_users = User.query.count()
        total_memberships = Membership.query.filter_by(active=True).count()
        orphan_users = (
            User.query
            .outerjoin(Membership, (Membership.user_id == User.id) & Membership.active.is_(True))
            .filter(Membership.id.is_(None))
            .count()
        )

        print(f"\n--- Backfill Summary ---")
        print(f"Total users:            {total_users}")
        print(f"Active memberships:     {total_memberships}")
        print(f"Orphan users (no team): {orphan_users}")
        print(f"Teams:                  {Team.query.count()}")
        print(f"Managers:               {Manager.query.count()}")
        print(f"Done.")


if __name__ == "__main__":
    backfill()
