"""
Hierarchical team subtree computation — the single source of truth
for determining which teams a manager can access.

get_allowed_team_ids(manager_team_id) -> list[int]

Returns the manager's own team plus all descendant teams.
Uses a recursive CTE on Postgres; falls back to iterative Python
traversal on SQLite (tests/demo).

Results are cached on flask.g for the request lifecycle.
"""

from __future__ import annotations

import logging
from flask import g
from backend.models import db, Team

logger = logging.getLogger("backend.auth.team_hierarchy")


def _is_postgres() -> bool:
    url = str(db.engine.url)
    return url.startswith("postgresql")


def _subtree_cte(root_id: int) -> list[int]:
    """Postgres recursive CTE — returns root_id + all descendant team IDs."""
    sql = db.text("""
        WITH RECURSIVE team_tree AS (
            SELECT id FROM teams WHERE id = :root_id
            UNION ALL
            SELECT t.id
            FROM teams t
            INNER JOIN team_tree tt ON t.parent_team_id = tt.id
        )
        SELECT id FROM team_tree
    """)
    rows = db.session.execute(sql, {"root_id": root_id}).fetchall()
    return [row[0] for row in rows]


def _subtree_python(root_id: int) -> list[int]:
    """Iterative BFS fallback for SQLite."""
    result = [root_id]
    queue = [root_id]
    while queue:
        parent_id = queue.pop(0)
        children = Team.query.filter_by(parent_team_id=parent_id).all()
        for child in children:
            result.append(child.id)
            queue.append(child.id)
    return result


def get_allowed_team_ids(manager_team_id: int) -> list[int]:
    """
    Return the list of team IDs the manager is allowed to access:
    their own team + all descendant teams in the hierarchy.

    Cached on flask.g so repeated calls within the same request are free.
    """
    cache_key = "_allowed_team_ids"
    cached = getattr(g, cache_key, None)
    if cached is not None:
        return cached

    if _is_postgres():
        ids = _subtree_cte(manager_team_id)
    else:
        ids = _subtree_python(manager_team_id)

    setattr(g, cache_key, ids)
    logger.debug(
        "Computed allowed_team_ids for team %s: %s", manager_team_id, ids
    )
    return ids
