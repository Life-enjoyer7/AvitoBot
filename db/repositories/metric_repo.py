"""Recording and aggregation of product-metrics events (KPIs)."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AlertLog, MetricEvent, Track, User


async def record_event(
    session: AsyncSession,
    event_type: str,
    user_id: int | None = None,
    track_id: int | None = None,
    marketplace: str | None = None,
) -> None:
    """Append a metric event. Caller is responsible for `session.commit()`."""
    session.add(
        MetricEvent(
            event_type=event_type,
            user_id=user_id,
            track_id=track_id,
            marketplace=marketplace,
        )
    )


async def _scalar(session: AsyncSession, stmt) -> int:
    return (await session.execute(stmt)).scalar() or 0


def _pct(num: float, den: float) -> float:
    return round(num / den * 100.0, 1) if den else 0.0


async def _avg_tracks_for_cohort(session: AsyncSession, now: datetime, days: int) -> float:
    """Avg active tracks per active user among users registered >= `days` ago."""
    since = now - timedelta(days=days)
    active_users = await _scalar(
        session,
        select(func.count(func.distinct(Track.user_id)))
        .join(User, User.id == Track.user_id)
        .where(Track.is_active.is_(True), User.created_at <= since),
    )
    if not active_users:
        return 0.0
    active_tracks = await _scalar(
        session,
        select(func.count(Track.id))
        .join(User, User.id == Track.user_id)
        .where(Track.is_active.is_(True), User.created_at <= since),
    )
    return round(active_tracks / active_users, 1)


async def compute_metrics(session: AsyncSession) -> dict:
    """Compute the five MVP KPIs as a JSON-friendly dict."""
    now = datetime.now()

    # KPI 1 — Activation Rate
    started_users = await _scalar(
        session,
        select(func.count(func.distinct(MetricEvent.user_id))).where(
            MetricEvent.event_type == "start"
        ),
    )
    activated_users = await _scalar(
        session,
        select(func.count(func.distinct(Track.user_id))).where(Track.is_active.is_(True)),
    )

    # KPI 2 — Average active tracks per user (overall + 3/7-day cohorts)
    active_tracks = await _scalar(
        session, select(func.count(Track.id)).where(Track.is_active.is_(True))
    )
    active_users = await _scalar(
        session,
        select(func.count(func.distinct(Track.user_id))).where(Track.is_active.is_(True)),
    )
    avg_all = round(active_tracks / active_users, 1) if active_users else 0.0

    # KPI 3 — Feature adoption (history/chart views)
    history_users = await _scalar(
        session,
        select(func.count(func.distinct(MetricEvent.user_id))).where(
            MetricEvent.event_type == "history_view"
        ),
    )

    # KPI 4 — Alert CTR
    clicks = await _scalar(
        session,
        select(func.count(MetricEvent.id)).where(MetricEvent.event_type == "alert_click"),
    )
    delivered = await _scalar(session, select(func.count(AlertLog.id)))

    # KPI 5 — Parser success rate
    parse_ok = await _scalar(
        session,
        select(func.count(MetricEvent.id)).where(MetricEvent.event_type == "parse_ok"),
    )
    parse_fail = await _scalar(
        session,
        select(func.count(MetricEvent.id)).where(MetricEvent.event_type == "parse_fail"),
    )
    parse_total = parse_ok + parse_fail

    return {
        "activation": {
            "started_users": started_users,
            "activated_users": activated_users,
            "rate": _pct(activated_users, started_users),
        },
        "avg_active_tracks": {
            "all": avg_all,
            "cohort_3d": await _avg_tracks_for_cohort(session, now, 3),
            "cohort_7d": await _avg_tracks_for_cohort(session, now, 7),
        },
        "feature_adoption": {
            "history_users": history_users,
            "rate": _pct(history_users, started_users),
        },
        "alert_ctr": {
            "clicks": clicks,
            "delivered": delivered,
            "rate": _pct(clicks, delivered),
        },
        "parser_success": {
            "ok": parse_ok,
            "fail": parse_fail,
            "total": parse_total,
            "rate": _pct(parse_ok, parse_total),
        },
    }
