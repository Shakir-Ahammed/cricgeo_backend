from __future__ import annotations

from typing import Optional

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings

# ---------------------------------------------------------------------------
# Job name constants — always use these; never raw strings
# ---------------------------------------------------------------------------
JOB_UPDATE_PLAYER_CAREER_STATS = "update_player_career_stats"
JOB_UPDATE_TOURNAMENT_STATS = "update_tournament_stats"
JOB_SEND_PUSH_NOTIFICATION = "send_push_notification"
JOB_DEACTIVATE_OBS_TOKEN = "deactivate_obs_token"
JOB_RECALCULATE_NRR = "recalculate_nrr"

# ---------------------------------------------------------------------------
# Pool singleton
# ---------------------------------------------------------------------------
_arq_pool: Optional[ArqRedis] = None


async def init_arq() -> None:
    """Create the ARQ Redis pool.  Call once at application startup."""
    global _arq_pool
    _arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))


async def close_arq() -> None:
    """Close the ARQ Redis pool.  Call once at application shutdown."""
    global _arq_pool
    if _arq_pool is not None:
        await _arq_pool.aclose()
        _arq_pool = None


def get_arq_pool() -> ArqRedis:
    """Return the ARQ Redis pool.  Raises if called before init_arq()."""
    if _arq_pool is None:
        raise RuntimeError(
            "ARQ pool is not initialized. Call init_arq() during application startup."
        )
    return _arq_pool


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
async def enqueue(job_name: str, **kwargs) -> None:
    """Thin wrapper — enqueue a named job with arbitrary keyword arguments."""
    pool = get_arq_pool()
    await pool.enqueue_job(job_name, **kwargs)
