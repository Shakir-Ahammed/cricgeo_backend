# CricGeo — Backend Development Plan

> **Prepared from:** `cricgeo_schema_v3_final.dbml` + `cricgeo_data_flow_diagrams.md`
> **Stack:** FastAPI · async SQLAlchemy · PostgreSQL (asyncpg) · Redis · WebSocket · Cloudflare R2
> **Core constraints (non-negotiable):**
> - `ball_by_ball` is **immutable** — never updated, never deleted
> - **PostgreSQL** is the single source of truth for all persistent data
> - **Redis** is cache / live-state layer only — never primary storage
> - Computed stats (avg, SR, economy, CRR, RRR) are always calculated **at application layer**

---

## Table of Contents
1. [Current State Audit](#1-current-state-audit)
2. [Module Implementation Order](#2-module-implementation-order)
3. [Complete Folder / Module Structure](#3-complete-folder--module-structure)
4. [API Architecture](#4-api-architecture)
5. [WebSocket Strategy](#5-websocket-strategy)
6. [Redis Usage Plan](#6-redis-usage-plan)
7. [Background Job Plan](#7-background-job-plan)
8. [Scoring Engine Flow](#8-scoring-engine-flow)
9. [Database Layer Map](#9-database-layer-map)
10. [Migration Strategy](#10-migration-strategy)
11. [Dependencies to Add](#11-dependencies-to-add)

---

## 1. Current State Audit

| Module | Status | Tables covered |
|---|---|---|
| `auth` | ✅ Complete | `users`, `user_auth_providers`, `user_sessions`, `otps` |
| `users` | ✅ Complete | `users` |
| `profiles` | ✅ Complete | `profiles`, `player_roles`, `batting_infos`, `bowling_infos` |
| `locations` | ✅ Complete | `countries`, `cities` |
| `cricket/teams` | ❌ Empty | — |
| `cricket/matches` | ❌ Empty | — |
| `cricket/scores` | ❌ Empty | — |
| venues | ❌ Missing | — |
| tournaments | ❌ Missing | — |
| scoring engine | ❌ Missing | — |
| notifications | ❌ Missing | — |
| subscriptions | ❌ Missing | — |
| WebSocket | ❌ Missing | — |
| Redis | ❌ Missing | — |
| Background jobs | ❌ Missing | — |

---

## 2. Module Implementation Order

Build in strict dependency order. Each phase depends on the previous.

### Phase 0 — Infrastructure (before any new module)
**Goal:** Wire Redis, WebSocket manager, and background job runner into the app core.

- `app/core/redis.py` — async Redis client (aioredis)
- `app/core/websocket.py` — ConnectionManager class (room-based)
- `app/core/jobs.py` — ARQ / background task dispatcher
- Add `REDIS_URL` to `Settings` in `config.py`
- Register WebSocket lifespan startup in `main.py`

### Phase 1 — Venues
**Depends on:** Locations (countries, cities)  
**Tables:** `venues`

- CRUD: create venue, search nearby (Haversine by lat/lon), get by city
- Public: `GET /venues/search?city_id=&lat=&lon=&q=`
- Protected: `POST /venues` (authenticated user creates venue)
- Venue `is_public=true` visible to all; `false` = creator only

### Phase 2 — Subscriptions
**Depends on:** Users  
**Tables:** `subscription_plans`, `user_subscriptions`

- `GET /subscriptions/plans` — public, list all active plans
- `GET /subscriptions/me` — current user's active subscription
- Admin: seed subscription_plans (free, pro, team) via migration data
- Business rule: Free plan auto-assigned on signup (triggered from auth service)

### Phase 3 — Teams
**Depends on:** Users, Profiles, Locations  
**Tables:** `teams`, `team_members`, `team_invitations`

- Team CRUD (owner-only mutations)
- Member management: add/remove/update role
- Invitation system: QR token, link, phone, email, whatsapp methods
- `GET /teams/{id}/qr` — generate QR join token
- `POST /teams/join/{token}` — validate and join team
- Captain approval flow for join requests
- Nearby teams: `GET /teams/nearby?city_id=`

### Phase 4 — Tournaments
**Depends on:** Teams, Venues  
**Tables:** `tournaments`, `tournament_teams`, `tournament_rounds`, `tournament_player_stats`, `tournament_awards`

- Tournament CRUD (organizer owns)
- Team registration flow with status transitions
- Round/group management
- Points table: `GET /tournaments/{id}/standings` — reads `tournament_teams` ordered by points DESC, NRR DESC
- Leaderboards: `GET /tournaments/{id}/stats/batting` / `bowling` — reads `tournament_player_stats`
- Awards: `POST /tournaments/{id}/awards`

### Phase 5 — Matches (creation side)
**Depends on:** Teams, Tournaments, Venues  
**Tables:** `matches`, `match_players`, `match_officials`, `match_powerplays`, `match_invitations`

- Match CRUD (created_by owns)
- Playing XI selection per team
- Official assignment (app user OR guest name+phone)
- PowerPlay configuration (PP1/PP2/PP3, from_over/to_over)
- Match invitation: `POST /matches/{id}/invite` — generates unique token
- `GET /matches/join/{token}` — validate QR/link join
- Match visibility: public = discoverable on Explore screen; private = invite only

### Phase 6 — Live Scoring Engine (core)
**Depends on:** Matches, Redis, WebSocket  
**Tables:** `match_innings`, `match_live_state`, `ball_by_ball`, `batting_scorecards`, `bowling_scorecards`, `fielding_scorecards`

- Toss endpoint → creates innings, initializes `match_live_state`
- Ball entry endpoint → immutable `ball_by_ball` insert → update scorecards → update `match_live_state` → push Redis → broadcast WebSocket
- Undo last ball → delete latest `ball_by_ball` row → recompute from remaining balls
- Innings break → calculate target, initialize 2nd innings
- Match complete → trigger background jobs → set status=completed

### Phase 7 — Background Jobs
**Depends on:** Scoring Engine  
**Updates:** `player_career_stats`, `tournament_player_stats`, `match_awards`, `tournament_awards`, `tournament_teams.nrr`

- Triggered async after match completion
- NRR recalculation for tournament standings
- Push notification dispatch

### Phase 8 — Notifications
**Depends on:** Background Jobs, Push tokens  
**Tables:** `notifications`, `push_tokens`

- `POST /notifications/push-token` — register FCM/APNs token
- `GET /notifications` — user's notification feed (paginated, unread first)
- `PUT /notifications/{id}/read` / `PUT /notifications/read-all`
- FCM integration for push delivery

### Phase 9 — OBS Streaming (future scope)
**Depends on:** Matches, Live Scoring  
**Tables:** `obs_stream_tokens`

- `POST /matches/{id}/obs-token` — generate overlay token
- `GET /obs/{token}/overlay` — public HTML overlay page (no auth)
- WebSocket subscription using obs token (unauthenticated)
- Auto-deactivate token via background job on match completion

---

## 3. Complete Folder / Module Structure

```
cricgeo_backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py          ✅ exists — add REDIS_URL
│   │   ├── db.py              ✅ exists
│   │   ├── security.py        ✅ exists
│   │   ├── mailer.py          ✅ exists
│   │   ├── sms.py             ✅ exists
│   │   ├── storage.py         ✅ exists
│   │   ├── redis.py           ➕ new — aioredis client + helpers
│   │   ├── websocket.py       ➕ new — ConnectionManager (room-based)
│   │   └── jobs.py            ➕ new — background task dispatcher
│   ├── helpers/
│   │   └── utils.py           ✅ exists
│   ├── middlewares/
│   │   └── auth_middleware.py ✅ exists
│   └── modules/
│       ├── auth/              ✅ complete
│       ├── users/             ✅ complete
│       ├── profiles/          ✅ complete
│       ├── locations/         ✅ complete
│       ├── venues/            ➕ Phase 1
│       │   ├── __init__.py
│       │   ├── model.py
│       │   ├── schema.py
│       │   ├── service.py
│       │   ├── controller.py
│       │   └── routes.py
│       ├── subscriptions/     ➕ Phase 2
│       │   ├── __init__.py
│       │   ├── model.py
│       │   ├── schema.py
│       │   ├── service.py
│       │   ├── controller.py
│       │   └── routes.py
│       ├── teams/             ➕ Phase 3
│       │   ├── __init__.py
│       │   ├── model.py        — Team, TeamMember, TeamInvitation
│       │   ├── schema.py
│       │   ├── service.py
│       │   ├── controller.py
│       │   └── routes.py
│       ├── tournaments/       ➕ Phase 4
│       │   ├── __init__.py
│       │   ├── model.py        — Tournament, TournamentTeam, TournamentRound,
│       │   │                     TournamentPlayerStats, TournamentAward
│       │   ├── schema.py
│       │   ├── service.py
│       │   ├── controller.py
│       │   └── routes.py
│       ├── matches/           ➕ Phase 5 (replaces empty cricket/matches)
│       │   ├── __init__.py
│       │   ├── model.py        — Match, MatchPlayer, MatchOfficial,
│       │   │                     MatchPowerplay, MatchInvitation, MatchInnings,
│       │   │                     MatchLiveState
│       │   ├── schema.py
│       │   ├── service.py
│       │   ├── controller.py
│       │   └── routes.py
│       ├── scoring/           ➕ Phase 6 (replaces empty cricket/scores)
│       │   ├── __init__.py
│       │   ├── model.py        — BallByBall, BattingScorecard,
│       │   │                     BowlingScorecard, FieldingScorecard,
│       │   │                     MatchAward
│       │   ├── schema.py
│       │   ├── engine.py       — core scoring logic (pure functions)
│       │   ├── service.py      — orchestrates DB + Redis + WebSocket
│       │   ├── controller.py
│       │   └── routes.py
│       ├── notifications/     ➕ Phase 8
│       │   ├── __init__.py
│       │   ├── model.py        — Notification, PushToken
│       │   ├── schema.py
│       │   ├── service.py
│       │   ├── controller.py
│       │   └── routes.py
│       └── streaming/         ➕ Phase 9
│           ├── __init__.py
│           ├── model.py        — ObsStreamToken
│           ├── schema.py
│           ├── service.py
│           ├── controller.py
│           └── routes.py
├── migrations/
│   └── versions/              ✅ existing migrations are HEAD
├── workers/
│   └── tasks.py               ➕ ARQ worker entry point (background jobs)
├── docs/
├── requirements.txt           — update with Redis, ARQ, WebSocket deps
├── alembic.ini
├── docker-compose.yml
└── Dockerfile
```

> **Note on `cricket/` directory:** The existing `app/modules/cricket/` with subdirs `matches/`, `scores/`, `teams/` is currently empty. New modules will be created at `app/modules/matches/`, `app/modules/scoring/`, `app/modules/teams/` (flat structure matching existing pattern). The `cricket/` directory can be removed or left empty.

---

## 4. API Architecture

### Conventions
- All responses: `{"success": bool, "message": str, "data": any}`
- Pagination: `{"items": [...], "total": int, "page": int, "per_page": int}`
- Auth header: `Authorization: Bearer <access_token>`
- Versioning: `/api/v1/` prefix (add to all new routes)
- Overs display: `balls_bowled` stored as `int`; convert to `X.Y` format at response layer — `f"{b // 6}.{b % 6}"`
- Computed fields (SR, avg, economy, CRR, RRR) — calculate in Pydantic response schema validators, never stored

### Route Map

#### Venues
```
GET    /venues/search              ?q=&city_id=&lat=&lon=&radius_km=   public
GET    /venues/{id}                                                     public
POST   /venues                                                          auth required
PUT    /venues/{id}                                                     owner only
```

#### Subscriptions
```
GET    /subscriptions/plans                                             public
GET    /subscriptions/me                                                auth required
```

#### Teams
```
POST   /teams                                                           auth required
GET    /teams/{id}                                                      public
PUT    /teams/{id}                                                      owner only
DELETE /teams/{id}                                                      owner only (soft delete)
GET    /teams/{id}/members                                              public
POST   /teams/{id}/members/invite                                       captain/owner
PUT    /teams/{id}/members/{user_id}/role                               captain/owner
DELETE /teams/{id}/members/{user_id}                                    captain/owner
GET    /teams/{id}/qr                                                   owner/captain
POST   /teams/join/{token}                                              auth required
GET    /teams/my                                                        auth required
GET    /teams/nearby                                                    ?city_id=   public
```

#### Tournaments
```
POST   /tournaments                                                     auth required
GET    /tournaments/{id}                                                public
PUT    /tournaments/{id}                                                organizer only
DELETE /tournaments/{id}                                                organizer only (soft delete)
POST   /tournaments/{id}/teams/register                                 team captain
PUT    /tournaments/{id}/teams/{team_id}/status                         organizer
GET    /tournaments/{id}/standings                                       public
GET    /tournaments/{id}/rounds                                          public
GET    /tournaments/{id}/matches                                         public
GET    /tournaments/{id}/stats/batting                                   public
GET    /tournaments/{id}/stats/bowling                                   public
POST   /tournaments/{id}/awards                                          organizer
GET    /tournaments/{id}/awards                                          public
```

#### Matches
```
POST   /matches                                                         auth required
GET    /matches/{id}                                                    public (if visibility=public)
PUT    /matches/{id}                                                    created_by only
DELETE /matches/{id}                                                    created_by only (soft delete)
GET    /matches/{id}/players                                            public
PUT    /matches/{id}/players                                            created_by — set Playing XI
POST   /matches/{id}/officials                                          created_by
GET    /matches/{id}/powerplays                                         public
PUT    /matches/{id}/powerplays                                         created_by
POST   /matches/{id}/invite                                             created_by
GET    /matches/join/{token}                                            public — preview
POST   /matches/join/{token}                                            auth required — accept
GET    /matches/live                                                    public — live matches explore
GET    /matches/my                                                      auth required — user's matches
```

#### Match Flow (state transitions)
```
POST   /matches/{id}/toss                                               created_by/umpire
POST   /matches/{id}/start                                              created_by/umpire
POST   /matches/{id}/innings/{innings_id}/complete                      created_by/umpire
POST   /matches/{id}/complete                                           created_by/umpire
```

#### Scoring (live engine)
```
POST   /matches/{id}/innings/{innings_id}/ball                          scorer only
DELETE /matches/{id}/innings/{innings_id}/ball/undo                     scorer only (undo last ball)
GET    /matches/{id}/scorecard                                          public
GET    /matches/{id}/innings/{innings_id}/balls                         public — full ball log
GET    /matches/{id}/live-state                                         public — current live state
```

#### WebSocket
```
WS     /ws/matches/{match_id}                                           public + auth optional
WS     /ws/obs/{token}                                                  public (no auth — OBS overlay)
```

#### Notifications
```
POST   /notifications/push-token                                        auth required
DELETE /notifications/push-token                                        auth required
GET    /notifications                                                    auth required
PUT    /notifications/{id}/read                                         auth required
PUT    /notifications/read-all                                          auth required
GET    /notifications/unread-count                                      auth required
```

#### OBS Streaming
```
POST   /matches/{id}/obs-token                                          created_by/live_streamer
GET    /obs/{token}/overlay                                             public — HTML page
GET    /obs/{token}/state                                               public — JSON live state
```

---

## 5. WebSocket Strategy

### Architecture: Room-Based Broadcasting

```
Client connects to: WS /ws/matches/{match_id}
          │
          ▼
ConnectionManager.connect(websocket, room=f"match:{match_id}")
          │
          ▼
Ball scored → service layer calls:
    await manager.broadcast(room=f"match:{match_id}", payload=event)
          │
          ▼
All clients in room receive JSON event instantly
```

### `app/core/websocket.py` — ConnectionManager

```python
class ConnectionManager:
    def __init__(self):
        # room_id → set of WebSocket connections
        self.rooms: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, ws: WebSocket, room: str): ...
    async def disconnect(self, ws: WebSocket, room: str): ...
    async def broadcast(self, room: str, payload: dict): ...
    async def send_personal(self, ws: WebSocket, payload: dict): ...
```

### WebSocket Event Payload Schema

```json
{
  "event": "ball_scored",
  "match_id": 42,
  "innings_id": 1,
  "data": {
    "over": 3,
    "ball": 4,
    "runs_off_bat": 4,
    "is_boundary": true,
    "is_wide": false,
    "is_wicket": false,
    "wicket_type": null,
    "dismissed_batsman_id": null,
    "total_runs": 78,
    "wickets": 2,
    "balls_bowled": 22,
    "crr": 21.27,
    "striker": {"user_id": 5, "runs": 34, "balls": 20},
    "non_striker": {"user_id": 7, "runs": 12, "balls": 9},
    "bowler": {"user_id": 11, "balls_bowled": 4, "runs_conceded": 18, "wickets": 1}
  }
}
```

### Event Types

| Event | Trigger |
|---|---|
| `ball_scored` | Every ball entry |
| `ball_undone` | Undo last ball |
| `wicket` | Ball with `is_wicket=true` |
| `innings_complete` | Innings status → completed |
| `innings_break` | Between innings |
| `match_complete` | Match ends |
| `toss_done` | Toss recorded |

### OBS Overlay WebSocket
- Route: `WS /ws/obs/{token}`
- Validates `obs_stream_tokens.token` on connect (no JWT required)
- Subscribes to same `match:{match_id}` room
- Sends same `ball_scored` event stream
- Read-only: OBS clients never send data

---

## 6. Redis Usage Plan

### Redis Key Schema

| Key pattern | Type | TTL | Purpose |
|---|---|---|---|
| `match:live:{match_id}` | Hash / JSON string | Duration of match + 1h | Full `match_live_state` snapshot for instant reads |
| `match:ws:{match_id}:count` | String (int) | Match duration | Active WebSocket connection count |
| `otp:rate:{identifier}` | String | 5 min | OTP request rate limiting (max 3/5min) |
| `session:revoked:{token_hash}` | String | Session TTL | Fast revocation check — avoids DB hit on every request |
| `venue:nearby:{city_id}` | String (JSON) | 1h | Nearby venue search cache |
| `tournament:standings:{id}` | String (JSON) | 5 min | Points table cache — invalidated on match completion |

### `app/core/redis.py` — Client Setup

```python
import aioredis
from app.core.config import settings

redis: aioredis.Redis = None

async def init_redis():
    global redis
    redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)

async def close_redis():
    if redis:
        await redis.close()

async def get_redis() -> aioredis.Redis:
    return redis
```

### Live State Cache Pattern

On every ball scored:
1. Insert `ball_by_ball` row (PostgreSQL — immutable, source of truth)
2. Update `match_live_state` row (PostgreSQL)
3. Serialize `match_live_state` → write to `match:live:{match_id}` in Redis
4. Broadcast WebSocket event

On `GET /matches/{id}/live-state`:
1. Try Redis `match:live:{match_id}` → return if hit
2. Cache miss → query `match_live_state` from PostgreSQL → cache → return

On match completion:
1. Delete `match:live:{match_id}` from Redis (match_live_state row can also be deleted — `ball_by_ball` is permanent)

### Rules
- Redis stores **only derived/cached data** — never the canonical version
- If Redis is unavailable, fall back to PostgreSQL reads gracefully
- Never write business-critical data exclusively to Redis

---

## 7. Background Job Plan

### Runner: ARQ (Async Redis Queue)

ARQ uses Redis as the job queue. Workers run as a separate process.

```
app startup → enqueue job → Redis queue → arq worker process → execute task
```

### Worker Entry Point: `workers/tasks.py`

```python
from arq import create_pool
from arq.connections import RedisSettings

async def update_player_career_stats(ctx, match_id: int): ...
async def update_tournament_stats(ctx, match_id: int): ...
async def send_push_notification(ctx, notification_id: int): ...
async def deactivate_obs_token(ctx, match_id: int): ...
async def cleanup_expired_otps(ctx): ...
async def recalculate_nrr(ctx, tournament_id: int): ...

class WorkerSettings:
    functions = [
        update_player_career_stats,
        update_tournament_stats,
        send_push_notification,
        deactivate_obs_token,
        cleanup_expired_otps,
        recalculate_nrr,
    ]
    # Cron: cleanup expired OTPs every hour
    cron_jobs = [cron(cleanup_expired_otps, hour={0})]
```

### Job Trigger Points

| Trigger | Jobs enqueued |
|---|---|
| Match status → `completed` | `update_player_career_stats(match_id)` → `update_tournament_stats(match_id)` → `recalculate_nrr(tournament_id)` → `deactivate_obs_token(match_id)` |
| Match status → `live` | — (Redis/WS are synchronous in request path) |
| Notification created | `send_push_notification(notification_id)` |
| Hourly cron | `cleanup_expired_otps()` |

### `update_player_career_stats` — Logic

```
For each player in match:
    SELECT SUM from batting_scorecards WHERE user_id = ?
    SELECT SUM from bowling_scorecards WHERE user_id = ?
    SELECT SUM from fielding_scorecards WHERE user_id = ?
    UPSERT player_career_stats (conflict on user_id → UPDATE all columns)
```

### `recalculate_nrr` — Logic
```
NRR = (Runs scored / Overs faced) - (Runs conceded / Overs bowled)
    → aggregate from match_innings for all matches in tournament
    → update tournament_teams.nrr
```

---

## 8. Scoring Engine Flow

> `ball_by_ball` is the immutable event log. Everything else is derived from it.

### Ball Entry Flow (happy path)

```
POST /matches/{id}/innings/{innings_id}/ball
  payload: { bowler_id, batsman_id, non_striker_id,
             runs_off_bat, is_wide, is_no_ball, is_bye,
             is_leg_bye, is_wicket, wicket_type,
             dismissed_batsman_id, fielder_id, ... }
  
  1. Permission check: caller is scorer/umpire of this match
  2. Validate match status = 'live'
  3. Validate innings status = 'live'
  4. Validate bowler overs_per_bowler constraint (if set)
  5. Compute derived fields:
       total_runs = runs_off_bat + extras
       is_boundary = (runs_off_bat == 4 and not wide/no-ball)
       is_six = (runs_off_bat == 6)
       is_dot_ball = (total_runs == 0 and not wide)
       ball_number = current legal ball count + 1  (legal = not wide/no-ball)
       over_number = current_over
       total_delivery_number = total_deliveries + 1
  6. INSERT ball_by_ball (immutable)
  7. UPDATE batting_scorecards (optimistic lock: version++)
  8. UPDATE bowling_scorecards (optimistic lock: version++)
  9. UPDATE fielding_scorecards (catches/run_outs/stumpings if applicable)
  10. UPDATE match_innings (total_runs, wickets, balls_bowled, extras breakdown)
  11. UPDATE match_live_state (striker/non-striker swap if run is odd,
       advance over if ball_number == 6)
  12. Advance over logic:
       if ball_number == 6:
           current_over++, current_ball = 0
           swap striker/non-striker at end of over
  13. Check innings-end conditions:
       all out (wickets == 10) OR overs complete (balls_bowled == overs_per_innings * 6)
       → auto-complete innings if conditions met
  14. SET Redis match:live:{match_id}
  15. BROADCAST WebSocket event to room match:{match_id}
  16. Return updated live state
```

### Undo Last Ball

```
DELETE /matches/{id}/innings/{innings_id}/ball/undo

  1. Permission: scorer only
  2. SELECT last ball_by_ball row for innings (ORDER BY id DESC LIMIT 1)
  3. DELETE that row
  4. Recompute from remaining ball_by_ball rows:
       - Re-aggregate batting_scorecards for affected players
       - Re-aggregate bowling_scorecards for affected bowler
       - Re-aggregate match_innings totals
       - Reconstruct match_live_state
  5. UPDATE Redis
  6. BROADCAST WebSocket event: { "event": "ball_undone", ... }
```

> The undo recompute is a full re-aggregate from `ball_by_ball`. It is heavier than a delta, but ensures correctness and avoids partial state bugs.

### Innings Completion

```
POST /matches/{id}/innings/{innings_id}/complete

  1. Match innings 1 → calculate target (total_runs + 1) → set match_innings 2 target_runs
  2. Initialize match_innings 2 (batting_team = bowling_team of innings 1, vice versa)
  3. Initialize batting_scorecards for innings 2 batting team
  4. Set match status = 'innings_break'
  5. Broadcast WebSocket: innings_complete event
```

### Match Completion

```
POST /matches/{id}/complete

  1. Determine winner:
       - 2nd innings chased target → winner = batting_team_2
       - All out / overs complete → winner = team with higher runs
       - Tie → result_type = 'tie'
       - No result → result_type = 'no_result'
  2. Set match.winner_team_id, result_type, result_margin
  3. Set match.status = 'completed', ended_at = now()
  4. Set match_innings 2 status = 'completed'
  5. CREATE match_awards (man_of_the_match, best_batsman, best_bowler)
  6. Delete Redis key match:live:{match_id}
  7. Enqueue background jobs: update_player_career_stats, update_tournament_stats
  8. Broadcast WebSocket: match_complete event
```

---

## 9. Database Layer Map

Matches schema design layers to implementation modules:

| Schema Layer | Tables | Module |
|---|---|---|
| Layer 1 — Location | `countries`, `cities`, `venues` | `locations`, `venues` |
| Layer 2 — User & Auth | `users`, `user_auth_providers`, `user_sessions`, `otps`, `subscription_plans`, `user_subscriptions` | `auth`, `users`, `subscriptions` |
| Layer 3 — Player Profile | `profiles`, `player_roles`, `batting_infos`, `bowling_infos`, `keeping_infos`, `player_career_stats` | `profiles` |
| Layer 4 — Team | `teams`, `team_members`, `team_invitations` | `teams` |
| Layer 5 — Tournament | `tournaments`, `tournament_teams`, `tournament_rounds`, `tournament_player_stats`, `tournament_awards` | `tournaments` |
| Layer 6 — Match | `matches`, `match_powerplays`, `match_officials`, `match_invitations`, `match_players`, `match_innings`, `match_live_state` | `matches` |
| Layer 7 — Scoring | `ball_by_ball`, `batting_scorecards`, `bowling_scorecards`, `fielding_scorecards`, `match_awards` | `scoring` |
| Layer 8 — Notifications | `notifications`, `push_tokens` | `notifications` |
| Layer 9 — OBS | `obs_stream_tokens` | `streaming` |

### Key Constraints to enforce at DB level (via migrations)

```sql
-- matches: teams must be different
ALTER TABLE matches ADD CONSTRAINT chk_different_teams
  CHECK (team_a_id != team_b_id);

-- match_powerplays: from_over < to_over
ALTER TABLE match_powerplays ADD CONSTRAINT chk_pp_range
  CHECK (from_over < to_over);

-- match_officials: must have user_id OR guest_name
ALTER TABLE match_officials ADD CONSTRAINT chk_official_identity
  CHECK (user_id IS NOT NULL OR guest_name IS NOT NULL);

-- profiles: case-insensitive unique username
CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_username_lower
  ON profiles (lower(username)) WHERE username IS NOT NULL;
```

---

## 10. Migration Strategy

All new tables added as a **single new migration** per phase:

| Migration | Phase | Contents |
|---|---|---|
| `v4_add_venues` | Phase 1 | `venues` table |
| `v5_add_subscriptions` | Phase 2 | `subscription_plans`, `user_subscriptions` |
| `v6_add_teams` | Phase 3 | `teams`, `team_members`, `team_invitations` |
| `v7_add_tournaments` | Phase 4 | `tournaments`, `tournament_teams`, `tournament_rounds`, `tournament_player_stats`, `tournament_awards` |
| `v8_add_matches` | Phase 5 | `matches`, `match_powerplays`, `match_officials`, `match_invitations`, `match_players`, `match_innings`, `match_live_state` |
| `v9_add_scoring` | Phase 6 | `ball_by_ball`, `batting_scorecards`, `bowling_scorecards`, `fielding_scorecards`, `match_awards` |
| `v10_add_notifications` | Phase 8 | `notifications`, `push_tokens` |
| `v11_add_streaming` | Phase 9 | `obs_stream_tokens` |
| `v12_add_constraints` | All | DB-level CHECK constraints + missing indexes |

> Always run `alembic revision --autogenerate -m "..."` after defining new SQLAlchemy models.

---

## 11. Dependencies to Add

Add to `requirements.txt`:

```
# Redis (async)
redis[hiredis]==5.0.1

# Background jobs
arq==0.25.0

# WebSocket support (already via fastapi/uvicorn[standard])
# websockets==12.0   ← included in uvicorn[standard]

# HTTP client (for FCM push notifications)
httpx==0.27.0

# QR code generation (for team/match QR tokens)
qrcode[pil]==7.4.2
Pillow==10.2.0
```

Config additions to `.env`:
```
REDIS_URL=redis://localhost:6379/0
FCM_SERVER_KEY=<firebase_server_key>
```

---

## Business Rules Summary

| Rule | Enforcement point |
|---|---|
| `ball_by_ball` never updated/deleted | Application layer guard + no UPDATE/DELETE in scoring service |
| Computed stats never stored | Pydantic `@computed_field` validators in response schemas |
| Legal ball count ignores wides/no-balls | `ball_number` only increments on legal deliveries |
| Overs stored as integer balls only | `balls_bowled int` — display as `f"{b//6}.{b%6}"` at response layer |
| Optimistic locking on scorecards | `version` column — check + increment on every UPDATE |
| Soft delete: users, teams, tournaments, matches | `deleted_at IS NOT NULL` filter in all list queries |
| Free subscription auto-assigned on signup | `auth/service.py` — after user creation, insert `user_subscriptions` with free plan |
| Max OTP attempts = 5, then block | `otps.attempts` — checked before verify, increment on failure |
| Redis unavailable → fallback to PostgreSQL | All Redis reads wrapped in try/except with DB fallback |
| Match visibility=private → invite only | `GET /matches/live` filters `WHERE visibility = 'public'` |
| OBS overlay is unauthenticated | Uses `obs_stream_tokens.token` — no JWT check |
