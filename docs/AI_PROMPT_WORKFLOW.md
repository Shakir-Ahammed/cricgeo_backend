# CricGeo — AI Development Prompt Workflow

> Use these prompts sequentially with any AI coding assistant (GitHub Copilot, Claude, GPT-4).
> Each prompt is self-contained. Paste the prompt, review output, then move to the next.
> Never skip a phase — each phase depends on the previous.

---

## PROGRESS TRACKER

| Phase | Module | Status |
|-------|--------|--------|
| P0 | Infrastructure | ✅ Complete |
| P1 | Venues Module | ✅ Complete |
| P2 | Subscriptions Module | ✅ Complete |
| P3 | Teams Module (+ player search prerequisite) | ⬅️ **Next** |
| P4 | Matches Module | ⬜ Not started |
| P5 | Scoring Engine | ⬜ Not started |
| P6 | Background Jobs | ⬜ Not started |
| P7 | Notifications Module | ⬜ Not started |
| P8 | OBS Streaming | ⬜ Not started |
| P9 | Tournaments Module | ⏸️ **Deferred** |

> **Revised Execution Order (May 2026):** Tournaments deferred to P9.
> Priority path: Teams → Matches → Scoring → Background Jobs → Notifications → OBS → Tournaments.

---

## HOW TO USE THIS FILE

1. Open your AI assistant
2. Copy the prompt block exactly as written
3. Review generated code against the checklist below each prompt
4. Run the review/test prompt before moving to the next phase
5. Commit after each phase passes review

**Stack context to include at the start of every session:**
```
Stack: FastAPI + async SQLAlchemy 2.0 + PostgreSQL (asyncpg) + Redis (aioredis) + WebSocket
Auth: JWT Bearer tokens via app/middlewares/auth_middleware.py (current_user injected)
DB session: AsyncSession via Depends(get_db) from app/core/db.py
Response format: {"success": bool, "message": str, "data": any}
Pagination: {"items": [...], "total": int, "page": int, "per_page": int}
Soft delete: deleted_at timestamptz column — always filter WHERE deleted_at IS NULL
Computed stats (average, economy, strike rate, CRR, RRR): NEVER stored in DB — calculate in Pydantic response validators
Overs display: stored as integer balls only — display as f"{b//6}.{b%6}"
```

---

## PHASE 0 — INFRASTRUCTURE ✅

### [P0-1] Redis Client

```
In the CricGeo FastAPI backend, create app/core/redis.py.

Requirements:
- Use aioredis (redis[hiredis] package, async client)
- Export a module-level `redis` variable (aioredis.Redis instance)
- Functions: init_redis(), close_redis(), get_redis() -> aioredis.Redis
- get_redis() raises a clear RuntimeError if called before init_redis()
- All operations must be async

Also update app/core/config.py Settings class:
- Add REDIS_URL: str = "redis://localhost:6379/0"

Do not change any other existing files.
```

**Review checklist:**
- [ ] `init_redis` called before any endpoint touches Redis
- [ ] `close_redis` called on app shutdown
- [ ] No sync Redis calls anywhere

---

### [P0-2] WebSocket Connection Manager

```
In the CricGeo FastAPI backend, create app/core/websocket.py.

Requirements:
- Class ConnectionManager with a `rooms` dict: dict[str, set[WebSocket]]
- Methods:
    async connect(ws: WebSocket, room: str) — accept + add to room
    async disconnect(ws: WebSocket, room: str) — remove from room, ignore if not found
    async broadcast(room: str, payload: dict) — send JSON to all connections in room; silently drop dead connections
    async send_personal(ws: WebSocket, payload: dict) — send JSON to single connection
- Export a single module-level instance: manager = ConnectionManager()
- Thread-safe: use asyncio.Lock for rooms dict mutations

Do not create any routes yet. Just the manager class.
```

**Review checklist:**
- [ ] Dead connection handled in broadcast (catch WebSocketDisconnect, remove from room)
- [ ] `rooms` defaults to empty set for unknown room (use defaultdict)
- [ ] Module-level singleton pattern is correct

---

### [P0-3] Background Job Dispatcher

```
In the CricGeo FastAPI backend, create app/core/jobs.py.

Requirements:
- Use ARQ library for async job queuing (Redis-backed)
- Export: async enqueue(job_name: str, **kwargs) — enqueues job to Redis queue
- Export: get_arq_pool() — returns the ARQ Redis pool
- Add init_arq() and close_arq() lifecycle functions
- Job names are string constants — define them as module-level constants:
    JOB_UPDATE_PLAYER_CAREER_STATS = "update_player_career_stats"
    JOB_UPDATE_TOURNAMENT_STATS = "update_tournament_stats"
    JOB_SEND_PUSH_NOTIFICATION = "send_push_notification"
    JOB_DEACTIVATE_OBS_TOKEN = "deactivate_obs_token"
    JOB_RECALCULATE_NRR = "recalculate_nrr"
- Uses REDIS_URL from settings

Do not implement the actual job functions yet — just the dispatcher infrastructure.
```

**Review checklist:**
- [ ] ARQ pool initialized at startup, closed at shutdown
- [ ] `enqueue` is a thin wrapper — no business logic
- [ ] Constants used everywhere instead of raw strings

---

### [P0-4] Wire Infrastructure into main.py

```
Update app/main.py in the CricGeo backend.

Current file already has a lifespan context manager.
Add to lifespan startup (in order):
  1. await init_redis()
  2. await init_arq()
Add to lifespan shutdown (in order):
  1. await close_arq()
  2. await close_redis()

Import from:
  app.core.redis import init_redis, close_redis
  app.core.jobs import init_arq, close_arq

Do not change any routes, middleware, or other settings.
Show only the modified lifespan function and the new imports.
```

**Review checklist:**
- [ ] Redis init before ARQ init (ARQ depends on Redis)
- [ ] Shutdown order reversed from startup
- [ ] No other code changed

---

### [P0-REVIEW] Infrastructure Review

```
Review the following files from the CricGeo backend infrastructure layer:
- app/core/redis.py
- app/core/websocket.py
- app/core/jobs.py
- The updated lifespan section of app/main.py

Check for:
1. Missing error handling on Redis connection failure at startup
2. Any sync calls inside async functions
3. Memory leaks: WebSocket connections not removed on disconnect
4. ARQ pool not properly closed
5. Any hardcoded Redis URLs (must use settings.REDIS_URL)

Report each issue with file, line reference, and fix.
```

---

## PHASE 1 — VENUES MODULE ✅

### [P1-1] Venue Model

```
Create app/modules/venues/model.py for the CricGeo backend.

SQLAlchemy async model for the `venues` table:
Columns (match schema exactly):
  id: int PK autoincrement
  name: varchar(150) not null
  address: text nullable
  city_id: int FK → cities.id nullable
  country_id: int FK → countries.id nullable
  latitude: Numeric(9,6) nullable
  longitude: Numeric(9,6) nullable
  created_by: int FK → users.id not null
  is_public: bool not null default True
  status: varchar(20) not null default 'active'
  created_at: timestamptz default now()
  updated_at: timestamptz nullable

Use Base from app.core.db.
Add __tablename__ = "venues".
No relationships needed — use plain FK columns only.
```

---

### [P1-2] Venue Schema

```
Create app/modules/venues/schema.py for the CricGeo backend.

Pydantic v2 schemas:

VenueCreate:
  name: str (max 150)
  address: str | None
  city_id: int | None
  country_id: int | None
  latitude: float | None (validate: -90 to 90)
  longitude: float | None (validate: -180 to 180)
  is_public: bool = True

VenueResponse:
  id, name, address, city_id, country_id, latitude, longitude,
  created_by, is_public, status, created_at
  model_config = ConfigDict(from_attributes=True)

VenueSearchParams (query params):
  q: str | None = None
  city_id: int | None = None
  lat: float | None = None
  lon: float | None = None
  radius_km: float = 10.0
  page: int = 1
  per_page: int = 20
```

---

### [P1-3] Venue Service

```
Create app/modules/venues/service.py for the CricGeo backend.

Async functions using AsyncSession:

create_venue(db, user_id: int, data: VenueCreate) -> Venue
  — INSERT venue, created_by = user_id

get_venue(db, venue_id: int) -> Venue | None
  — SELECT by id WHERE status = 'active'

search_venues(db, params: VenueSearchParams, current_user_id: int | None) -> dict
  — Filter: status = 'active'
  — If is_public=false: only show to created_by = current_user_id
  — If q: ILIKE %q% on name or address
  — If city_id: filter by city_id
  — If lat + lon: ORDER BY Haversine distance (use SQL formula inline, no PostGIS):
      distance = 6371 * acos(cos(radians(lat)) * cos(radians(venues.latitude))
                 * cos(radians(venues.longitude) - radians(lon))
                 + sin(radians(lat)) * sin(radians(venues.latitude)))
      WHERE distance <= radius_km
  — Return paginated dict: {items, total, page, per_page}

Use SQLAlchemy select(), func, and literal_column for Haversine formula.
```

---

### [P1-4] Venue Controller + Routes

```
Create app/modules/venues/controller.py and app/modules/venues/routes.py
for the CricGeo backend.

Routes:
  GET  /venues/search  — public, query params: VenueSearchParams
  GET  /venues/{id}    — public
  POST /venues         — auth required (current_user from middleware)

Controller functions handle HTTP layer only:
  - Call service functions
  - Return {"success": True, "message": "...", "data": ...}
  - Raise HTTPException(404) if venue not found
  - Raise HTTPException(403) if private venue accessed by non-owner

Register router with prefix="/venues", tags=["Venues"] in routes.py.
Import and register this router in app/main.py.
```

---

### [P1-REVIEW] Venue Module Review

```
Review the complete venues module (model, schema, service, controller, routes).

Check:
1. Haversine formula is correct and uses radians conversion
2. Private venues (is_public=false) never leak to other users
3. Pagination is applied after all filters, not before
4. city_id/country_id FK constraints exist in model
5. created_by is taken from current_user, never from request body
6. No raw SQL strings — only SQLAlchemy ORM
7. All functions are async

List any issues found.
```

---

## PHASE 2 — SUBSCRIPTIONS MODULE ✅

### [P2-1] Subscription Models

```
Create app/modules/subscriptions/model.py for the CricGeo backend.

Two SQLAlchemy models:

SubscriptionPlan:
  __tablename__ = "subscription_plans"
  id: int PK
  name: varchar(100) not null
  slug: varchar(50) unique not null
  price_monthly: Numeric(10,2) not null default 0
  price_yearly: Numeric(10,2) not null default 0
  currency: varchar(3) not null default 'BDT'
  features: JSON nullable  (use sqlalchemy JSON type)
  max_matches_per_month: int nullable
  max_teams: int nullable
  is_active: bool not null default True
  created_at: timestamptz default now()

UserSubscription:
  __tablename__ = "user_subscriptions"
  id: int PK
  user_id: int FK → users.id not null
  plan_id: int FK → subscription_plans.id not null
  status: varchar(20) not null  (active, trial, expired, cancelled)
  starts_at: timestamptz nullable
  expires_at: timestamptz nullable
  trial_ends_at: timestamptz nullable
  created_at: timestamptz default now()
  updated_at: timestamptz nullable
```

---

### [P2-2] Subscription Service + Routes

```
Create app/modules/subscriptions/service.py, schema.py, controller.py, routes.py
for the CricGeo backend.

Service functions:
  get_active_plans(db) -> list[SubscriptionPlan]
    — SELECT WHERE is_active = true ORDER BY price_monthly ASC

  get_user_subscription(db, user_id: int) -> UserSubscription | None
    — SELECT WHERE user_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1

  assign_free_plan(db, user_id: int) -> UserSubscription
    — SELECT free plan (slug='free'), INSERT user_subscription with status='active'
    — Called from auth service after user creation

Routes:
  GET /subscriptions/plans    — public
  GET /subscriptions/me       — auth required

Schemas:
  SubscriptionPlanResponse: id, name, slug, price_monthly, price_yearly, currency, features, max_matches_per_month, max_teams
  UserSubscriptionResponse: id, user_id, plan_id, status, starts_at, expires_at, plan: SubscriptionPlanResponse

Register router in main.py.
```

---

### [P2-REVIEW] Subscription Review

```
Review the subscriptions module.

Check:
1. assign_free_plan is idempotent (won't create duplicate free subscriptions)
2. get_user_subscription uses partial index hint: status = 'active'
3. plan features JSON is properly serialized/deserialized
4. GET /subscriptions/me returns 404 if no active subscription found (not 500)
5. Free plan seed: confirm how the free plan row gets into subscription_plans
   (migration data, fixture, or admin endpoint — pick one and document it)
```

---

## PHASE 3 — TEAMS MODULE ⬅️ NEXT

> **Prerequisite:** Player search must exist before team creation UI can add members.
> P3-0 adds a search endpoint to the existing users module first.

### [P3-0] Player Search Endpoint (prerequisite for team member add)

```
Update app/modules/users/routes.py and service.py in the CricGeo backend.

Add a player search endpoint so the team creation flow can find users to add.

Service function (add to app/modules/users/service.py):

search_players(db, q: str, limit: int = 20) -> list[User]
  — Search by: name ILIKE %q%, OR phone = q (exact), OR profiles.username ILIKE %q%
  — JOIN profiles on users.id = profiles.user_id (LEFT JOIN — username may be null)
  — WHERE users.deleted_at IS NULL AND users.status = 'active'
  — LIMIT limit (max 20)
  — Return list of User ORM objects

Route (add to app/modules/users/routes.py):

  GET /users/search?q=&limit=20    — auth required
    — q: min 2 characters (raise 400 if shorter)
    — Returns list of PlayerSearchResult

Schema (add to app/modules/users/schema.py):

  PlayerSearchResult:
    id: int
    name: str
    phone: str | None   (masked: show only last 4 digits e.g. "****5978")
    username: str | None
    profile_image: str | None
    model_config = ConfigDict(from_attributes=True)

Security note:
  — Phone number must be masked in response (show only last 4 digits)
  — Do NOT expose full phone or email in this public search
  — Requires auth (token) to prevent scraping
```

**Review checklist:**
- [ ] Phone masked — never return full phone number
- [ ] Minimum 2 chars on `q` to prevent full table scan
- [ ] LIMIT enforced server-side (max 20)
- [ ] LEFT JOIN profiles so users without profile still appear in results
- [ ] Auth required (not public)

---

### [P3-1] Team Models

```
Create app/modules/teams/model.py for the CricGeo backend.

Three SQLAlchemy models:

Team:
  __tablename__ = "teams"
  id, owner_id (FK users), name varchar(150), short_name varchar(10),
  logo varchar(500), type varchar(30), country_id (FK), city_id (FK),
  description text, status varchar(20) default 'active',
  created_at, updated_at, deleted_at (soft delete)

TeamMember:
  __tablename__ = "team_members"
  id, team_id (FK), user_id (FK), role varchar(30),
  jersey_number int nullable, status varchar(20) default 'active',
  joined_at timestamptz, released_at timestamptz, created_at
  UniqueConstraint('team_id', 'user_id')

TeamInvitation:
  __tablename__ = "team_invitations"
  id, team_id (FK), invited_by (FK users), invitee_user_id (FK users nullable),
  invitee_identifier varchar(255) nullable, invitee_name varchar(150) nullable,
  role varchar(30), invite_method varchar(30) default 'link',
  token varchar(255) unique, status varchar(20) default 'pending',
  expires_at timestamptz, responded_at timestamptz, created_at
```

---

### [P3-2] Team Service — CRUD

```
Create app/modules/teams/service.py for the CricGeo backend.

Implement these async functions:

create_team(db, owner_id: int, data: TeamCreate) -> Team
  — INSERT team; also INSERT team_members row with role='captain', user_id=owner_id

get_team(db, team_id: int) -> Team | None
  — SELECT WHERE id=? AND deleted_at IS NULL

list_user_teams(db, user_id: int, page, per_page) -> dict
  — JOIN team_members WHERE user_id=? AND teams.deleted_at IS NULL
  — Paginated

list_nearby_teams(db, city_id: int, page, per_page) -> dict
  — WHERE city_id=? AND deleted_at IS NULL AND status='active'

update_team(db, team_id: int, owner_id: int, data: TeamUpdate) -> Team
  — Only owner can update (raise 403 if not)

soft_delete_team(db, team_id: int, owner_id: int) -> bool
  — Set deleted_at = now()

get_team_members(db, team_id: int) -> list[TeamMember]
```

---

### [P3-3] Team Service — Invitations & Join

```
Add to app/modules/teams/service.py for the CricGeo backend.

invite_member(db, team_id: int, invited_by: int, data: TeamInviteCreate) -> TeamInvitation
  — Validate invited_by is captain or owner of team
  — Generate secure random token: secrets.token_urlsafe(32)
  — Set expires_at = now() + 7 days
  — INSERT team_invitations

get_invitation_by_token(db, token: str) -> TeamInvitation | None
  — SELECT WHERE token=? AND status='pending' AND expires_at > now()

accept_invitation(db, token: str, user_id: int) -> TeamMember
  — Get invitation by token (raise 404 if not found/expired)
  — INSERT team_members with user_id and role from invitation
  — UPDATE invitation status='accepted', responded_at=now()
  — Return new TeamMember

generate_qr_token(db, team_id: int, owner_id: int) -> dict
  — Create or reuse a pending invitation with invite_method='qr'
  — Return {token, join_url, expires_at}

All token lookups must be O(1) — token column is unique indexed.
```

---

### [P3-4] Team Controller + Routes

```
Create app/modules/teams/controller.py and routes.py for the CricGeo backend.

Routes:
  POST   /teams                           auth required
  GET    /teams/my                        auth required
  GET    /teams/nearby?city_id=           public
  GET    /teams/{id}                      public (deleted → 404)
  PUT    /teams/{id}                      owner only
  DELETE /teams/{id}                      owner only
  GET    /teams/{id}/members              public
  POST   /teams/{id}/members/invite        owner only
  DELETE /teams/{id}/members/{user_id}    owner only
  GET    /teams/{id}/qr                   owner only
  POST   /teams/join/{token}              auth required

For DELETE /teams/{id}/members/{user_id}:
  — Cannot remove team owner
  — Update team_members.status='released', released_at=now()

Register router prefix="/teams" in main.py.
```

---

### [P3-REVIEW] Teams Module Review

```
Review the complete teams module.

Check:
1. Owner added as captain member on team creation (atomic — same transaction)
2. Invitation token is cryptographically secure (secrets.token_urlsafe, not uuid4)
3. Expired invitations not accepted (expires_at > now() check)
4. Cannot remove team owner from members
5. Soft-deleted teams not returned in any list or GET endpoint
6. Role check: only captain/owner can invite — enforced in service, not just controller
7. QR token reuses existing pending token instead of creating duplicates
8. No N+1 queries in get_team_members
```

---

## PHASE 9 — TOURNAMENTS MODULE ⏸️ DEFERRED

> **This phase has been deferred.** Complete Phases 3–8 first.
> Tournaments depend on Teams + Matches being fully functional.
> tournament_id on matches is nullable — friendly matches work without this phase.

### [P9-1] Tournament Models

```
Create app/modules/tournaments/model.py for the CricGeo backend.

SQLAlchemy models for these tables (match schema exactly):

Tournament — all columns from schema including venue_id FK, structure, tiebreaker,
  win_points, tie_points, loss_points, no_result_points, status varchar(30),
  soft delete (deleted_at)

TournamentTeam — tournament_id, team_id, group_name, seed, status,
  played, won, lost, tied, no_result, points, nrr Numeric(6,3) default 0
  UniqueConstraint('tournament_id', 'team_id')

TournamentRound — tournament_id, name, round_type, round_number, status, starts_at, ends_at

TournamentPlayerStats — tournament_id, user_id, team_id,
  all batting stats (runs, balls_faced, fours, sixes, highest_score, fifties, hundreds),
  all bowling stats (wickets, balls_bowled, runs_conceded, maidens, best_bowling_wickets, best_bowling_runs),
  all fielding stats (catches, run_outs, stumpings),
  updated_at
  UniqueConstraint('tournament_id', 'user_id')

TournamentAward — tournament_id, user_id, team_id nullable, award_type, stat_value, created_at
  UniqueConstraint('tournament_id', 'award_type')
```

---

### [P9-2] Tournament Service

```
Create app/modules/tournaments/service.py for the CricGeo backend.

Async service functions:

create_tournament(db, organizer_id, data) -> Tournament
get_tournament(db, tournament_id) -> Tournament | None  (deleted_at IS NULL)
update_tournament(db, tournament_id, organizer_id, data) -> Tournament  (organizer only)
soft_delete_tournament(db, tournament_id, organizer_id) -> bool

register_team(db, tournament_id, team_id, group_name, seed) -> TournamentTeam
update_team_status(db, tournament_id, team_id, organizer_id, new_status) -> TournamentTeam

get_standings(db, tournament_id) -> list[TournamentTeam]
  — ORDER BY points DESC, nrr DESC

get_batting_leaderboard(db, tournament_id, page, per_page) -> dict
  — ORDER BY runs DESC

get_bowling_leaderboard(db, tournament_id, page, per_page) -> dict
  — ORDER BY wickets DESC, runs_conceded ASC

list_tournament_matches(db, tournament_id, page, per_page) -> dict
  — SELECT matches WHERE tournament_id=? ORDER BY scheduled_at ASC

create_award(db, tournament_id, organizer_id, data) -> TournamentAward
get_awards(db, tournament_id) -> list[TournamentAward]
```

---

### [P9-3] Tournament Routes

```
Create app/modules/tournaments/controller.py and routes.py for CricGeo.

Routes:
  POST   /tournaments                               auth required
  GET    /tournaments/{id}                          public
  PUT    /tournaments/{id}                          organizer only
  DELETE /tournaments/{id}                          organizer only
  POST   /tournaments/{id}/teams/register           auth required (team captain)
  PUT    /tournaments/{id}/teams/{team_id}/status   organizer only
  GET    /tournaments/{id}/standings                public
  GET    /tournaments/{id}/rounds                   public
  GET    /tournaments/{id}/matches                  public
  GET    /tournaments/{id}/stats/batting            public
  GET    /tournaments/{id}/stats/bowling            public
  POST   /tournaments/{id}/awards                   organizer only
  GET    /tournaments/{id}/awards                   public

Computed fields in TournamentPlayerStats response:
  batting_average: runs / max(1, matches_played - not_outs) — but not_outs not stored here, so skip
  strike_rate: (runs / max(1, balls_faced)) * 100
  economy: (runs_conceded / max(1, balls_bowled)) * 6
Calculate these in Pydantic response schema using @computed_field.

Register router prefix="/tournaments" in main.py.
```

---

### [P9-REVIEW] Tournament Review

```
Review the tournaments module.

Check:
1. Standings query orders by points DESC then nrr DESC (tiebreaker)
2. Organizer-only endpoints verify organizer_id matches tournament.organizer_id
3. Deleted tournaments return 404, not 403
4. computed_field values in stats schemas don't divide by zero
5. TournamentTeam status transitions are logical (registered → confirmed → eliminated/qualified)
6. register_team checks tournament status allows registration (registration_open)
7. NRR column default is 0.000, not null
```

---

## PHASE 4 — MATCHES MODULE

### [P4-1] Match Models

```
Create app/modules/matches/model.py for the CricGeo backend.

SQLAlchemy models (match schema exactly):

Match — all columns: tournament_id nullable, round_id nullable, team_a_id, team_b_id,
  venue_id nullable, venue_name varchar(200) nullable, format, overs_per_innings,
  overs_per_bowler nullable, match_type default 'friendly', visibility default 'public',
  toss_winner_team_id nullable, toss_decision varchar(10) nullable,
  status varchar(30) default 'scheduled', winner_team_id nullable,
  result_type nullable, result_margin nullable, dls_applied bool default False,
  dls_target nullable, man_of_the_match_id nullable, created_by FK users,
  scheduled_at, started_at, ended_at, soft delete (deleted_at)

MatchPowerplay — match_id FK, pp_number int, from_over int, to_over int,
  fielding_restrictions text nullable
  UniqueConstraint('match_id', 'pp_number')

MatchOfficial — match_id FK, user_id FK nullable, guest_name varchar(150) nullable,
  guest_phone varchar(20) nullable, role varchar(30), position smallint nullable,
  status varchar(20) default 'invited'

MatchInvitation — match_id FK, invited_by FK, invitee_user_id FK nullable,
  invitee_identifier varchar(255) nullable, invite_method varchar(20),
  token varchar(255) unique not null, role varchar(20) default 'viewer',
  status varchar(20) default 'pending', expires_at, responded_at

MatchPlayer — match_id FK, team_id FK, user_id FK, batting_order nullable,
  is_playing_xi bool default True, is_captain bool default False,
  is_wicketkeeper bool default False, is_substitute bool default False
  UniqueConstraint('match_id', 'user_id')

MatchInnings — match_id FK, batting_team_id FK, bowling_team_id FK,
  innings_number int, total_runs int default 0, wickets int default 0,
  balls_bowled int default 0, extras int default 0, wide_balls int default 0,
  no_balls int default 0, byes int default 0, leg_byes int default 0,
  penalty_runs int default 0, target_runs nullable,
  status varchar(20) default 'upcoming', started_at, ended_at
  UniqueConstraint('match_id', 'innings_number')

MatchLiveState — match_id PK FK, current_innings_id FK, striker_id FK users,
  non_striker_id FK users, current_bowler_id FK users,
  current_over int default 1, current_ball int default 0,
  total_deliveries int default 0, current_runs int default 0,
  current_wickets int default 0, current_balls_bowled int default 0,
  last_ball_id bigint nullable, updated_at
```

---

### [P4-2] Match Service — Creation & Setup

```
Create app/modules/matches/service.py for the CricGeo backend (creation side only).

Async functions:

create_match(db, created_by: int, data: MatchCreate) -> Match
  — Validate team_a_id != team_b_id (raise 400 if same)
  — INSERT match

set_playing_xi(db, match_id: int, user_id: int, players: list[MatchPlayerInput]) -> list[MatchPlayer]
  — Only created_by can set (raise 403 if not)
  — Match status must be 'scheduled' or 'toss_done'
  — Upsert MatchPlayer rows (delete existing for match, re-insert)
  — Validate: max 11 per team is_playing_xi=True, exactly 1 captain per team

assign_official(db, match_id: int, user_id: int, data: MatchOfficialCreate) -> MatchOfficial
  — created_by only
  — Validate: user_id OR guest_name must be provided (not both null)

configure_powerplays(db, match_id: int, user_id: int, pps: list[PowerplayInput]) -> list[MatchPowerplay]
  — created_by only
  — Validate from_over < to_over for each PP
  — Upsert (delete existing, re-insert)

create_match_invitation(db, match_id: int, invited_by: int, data: MatchInviteCreate) -> MatchInvitation
  — Generate token: secrets.token_urlsafe(32)
  — expires_at = now() + 24h
  — INSERT

get_invitation_preview(db, token: str) -> dict
  — Validate token is pending and not expired
  — Return match details + role without accepting
```

---

### [P4-3] Match Service — State Transitions

```
Add match state transition functions to app/modules/matches/service.py.

record_toss(db, match_id: int, user_id: int, winner_team_id: int, decision: str) -> Match
  — Only created_by or match umpire
  — decision must be 'bat' or 'field'
  — UPDATE match: toss_winner_team_id, toss_decision, status='toss_done'

start_match(db, match_id: int, user_id: int) -> tuple[Match, MatchInnings, MatchLiveState]
  — Only created_by or umpire
  — Status must be 'toss_done'
  — Determine batting/bowling teams from toss
  — INSERT match_innings (innings_number=1, status='live')
  — INSERT match_live_state (match_id, current_innings_id, striker_id must be set)
  — UPDATE match: status='live', started_at=now()
  — Return match, innings, live_state

get_match(db, match_id: int) -> Match | None  (deleted_at IS NULL)
get_live_matches(db, page, per_page) -> dict  (status='live', visibility='public')
get_user_matches(db, user_id: int, page, per_page) -> dict  (created_by=user_id OR in match_players)
```

---

### [P4-4] Match Routes

```
Create app/modules/matches/controller.py and routes.py for CricGeo.

Routes:
  POST   /matches                                 auth required
  GET    /matches/live                            public
  GET    /matches/my                              auth required
  GET    /matches/{id}                            public if visibility=public, else auth+member
  PUT    /matches/{id}                            created_by only
  DELETE /matches/{id}                            created_by only (soft delete)
  PUT    /matches/{id}/players                    created_by only
  POST   /matches/{id}/officials                  created_by only
  PUT    /matches/{id}/powerplays                 created_by only
  POST   /matches/{id}/invite                     created_by only
  GET    /matches/invite/{token}                  public — preview
  POST   /matches/join/{token}                    auth required
  POST   /matches/{id}/toss                       created_by or umpire
  POST   /matches/{id}/start                      created_by or umpire
  GET    /matches/{id}/live-state                 public
    — Try Redis match:live:{match_id} first; fallback to DB

Register router prefix="/matches" in main.py.
```

---

### [P4-REVIEW] Match Module Review

```
Review the complete matches module.

Check:
1. team_a_id != team_b_id enforced in service (not just DB constraint)
2. Playing XI: exactly 11 is_playing_xi=True per team validated
3. Match start: batting/bowling team derived correctly from toss_decision
   (toss winner bats → batting_team = toss_winner; toss winner fields → batting_team = other team)
4. MatchLiveState inserted atomically with MatchInnings in start_match
5. Private match GET returns 403 (not 404) for non-members
6. Live state endpoint checks Redis first, falls back to DB gracefully
7. No match state mutation allowed after status='completed'
8. Invitation token generated with secrets.token_urlsafe, not uuid4
```

---

## PHASE 5 — SCORING ENGINE

### [P5-1] Scoring Models

```
Create app/modules/scoring/model.py for the CricGeo backend.

SQLAlchemy models:

BallByBall (immutable — no UPDATE/DELETE ever):
  __tablename__ = "ball_by_ball"
  id: bigint PK autoincrement
  innings_id FK, match_id FK (denormalized),
  over_number int, ball_number int, total_delivery_number int,
  bowler_id FK users, batsman_id FK users, non_striker_id FK users,
  runs_off_bat int default 0, extras int default 0, total_runs int default 0,
  is_wide bool default False, is_no_ball bool default False,
  is_bye bool default False, is_leg_bye bool default False,
  is_penalty bool default False,
  is_wicket bool default False, wicket_type varchar(30) nullable,
  dismissed_batsman_id FK users nullable, fielder_id FK users nullable,
  shot_type varchar(30) nullable, shot_direction int nullable,
  fielding_position varchar(30) nullable, delivery_type varchar(30) nullable,
  is_boundary bool default False, is_six bool default False,
  is_dot_ball bool default False,
  is_reviewed bool default False, review_result varchar(20) nullable,
  created_at timestamptz default now()

BattingScorecard:
  id, innings_id FK, match_id FK, user_id FK, team_id FK,
  batting_position int, runs int default 0, balls_faced int default 0,
  fours int default 0, sixes int default 0,
  dismissal_type varchar(30) nullable, dismissed_by_id FK nullable, fielded_by_id FK nullable,
  status varchar(20) default 'not_out',
  version int default 1,  (optimistic locking)
  created_at, updated_at
  UniqueConstraint('innings_id', 'user_id')

BowlingScorecard:
  id, innings_id FK, match_id FK, user_id FK, team_id FK,
  balls_bowled int default 0, maidens int default 0,
  runs_conceded int default 0, wickets int default 0,
  wides int default 0, no_balls int default 0,
  version int default 1,
  created_at, updated_at
  UniqueConstraint('innings_id', 'user_id')

FieldingScorecard:
  id, match_id FK, user_id FK, team_id FK,
  catches int default 0, run_outs int default 0, stumpings int default 0,
  dropped_catches int default 0, direct_hits int default 0,
  created_at, updated_at
  UniqueConstraint('match_id', 'user_id')

MatchAward:
  id, match_id FK, user_id FK, team_id FK,
  award_type varchar(50), reason text nullable, created_at
  UniqueConstraint('match_id', 'award_type')
```

---

### [P5-2] Scoring Engine — Pure Logic

```
Create app/modules/scoring/engine.py for the CricGeo backend.

Pure functions — no DB, no Redis, no async. All inputs/outputs are plain dicts or dataclasses.

def compute_ball_fields(payload: dict) -> dict:
  """
  Given raw scorer input, compute all derived ball fields.
  Input: runs_off_bat, is_wide, is_no_ball, is_bye, is_leg_bye, is_penalty, is_wicket, ...
  Output: total_runs, is_boundary, is_six, is_dot_ball, extras
  Rules:
    extras = (1 if is_wide else 0) + (1 if is_no_ball else 0) + runs if is_bye/leg_bye else 0
    total_runs = runs_off_bat + extras
    is_boundary = runs_off_bat == 4 and not is_wide and not is_no_ball
    is_six = runs_off_bat == 6 and not is_wide and not is_no_ball
    is_dot_ball = total_runs == 0 and not is_wide and not is_no_ball
  """

def is_legal_delivery(is_wide: bool, is_no_ball: bool) -> bool:
  return not is_wide and not is_no_ball

def should_advance_over(current_ball: int, is_wide: bool, is_no_ball: bool) -> bool:
  """Returns True if this delivery completes the over (6th legal ball)."""
  return is_legal_delivery(is_wide, is_no_ball) and current_ball == 5  # 0-indexed

def should_swap_on_run(runs_off_bat: int, is_wicket: bool, over_ended: bool) -> bool:
  """Striker/non-striker swap on odd runs off bat, and always on over end."""
  if over_ended:
    return True
  return runs_off_bat % 2 == 1 and not is_wicket

def compute_crr(total_runs: int, balls_bowled: int) -> float | None:
  if balls_bowled == 0:
    return None
  return round(total_runs / (balls_bowled / 6), 2)

def compute_rrr(target: int, current_runs: int, remaining_balls: int) -> float | None:
  if remaining_balls == 0:
    return None
  return round((target - current_runs) / (remaining_balls / 6), 2)

def format_overs(balls: int) -> str:
  return f"{balls // 6}.{balls % 6}"

Write unit-testable pure functions. No side effects.
```

---

### [P5-3] Scoring Service — Ball Entry

```
Create app/modules/scoring/service.py for the CricGeo backend.

This is the core live engine. Implement:

async def score_ball(db: AsyncSession, redis, manager: ConnectionManager,
                     match_id: int, innings_id: int,
                     scorer_user_id: int, payload: BallInput) -> dict:
  """
  Full ball scoring transaction. Steps:
  1. Verify scorer_user_id is scorer or umpire of this match
  2. Fetch match (status must be 'live'), innings (status must be 'live')
  3. Fetch match_live_state
  4. Call engine.compute_ball_fields(payload)
  5. Determine over_number, ball_number, total_delivery_number from live_state
  6. INSERT ball_by_ball (use db.add + await db.flush to get id)
  7. UPDATE batting_scorecards for batsman (optimistic lock: version check + increment)
  8. UPDATE bowling_scorecards for bowler (optimistic lock)
  9. If is_wicket: UPDATE batting_scorecards for dismissed_batsman (status='out', dismissal fields)
  10. If fielder_id and (is_wicket and wicket_type in ['caught','run_out','stumped']):
      UPSERT fielding_scorecards (increment relevant counter)
  11. UPDATE match_innings (total_runs, wickets, balls_bowled, extras breakdown)
  12. UPDATE match_live_state:
       - Increment current_ball if legal, else total_deliveries only
       - If over ends (should_advance_over): current_over++, current_ball=0
       - Swap striker/non_striker per engine.should_swap_on_run
       - Update current_runs, current_wickets, current_balls_bowled
       - last_ball_id = new ball.id
  13. await db.commit()
  14. Serialize live_state to dict; SET Redis "match:live:{match_id}" (JSON, TTL=14400)
  15. Build WebSocket event payload
  16. await manager.broadcast(f"match:{match_id}", event_payload)
  17. Check innings-end: wickets==10 OR balls_bowled==overs_per_innings*6
      → if ended: call complete_innings()
  18. Return event_payload

Raise OptimisticLockError (custom exception) if version mismatch on scorecard update.
All DB writes in a single transaction — commit once at step 13.
"""
```

---

### [P5-4] Scoring Service — Undo, Innings Complete, Match Complete

```
Add to app/modules/scoring/service.py for the CricGeo backend.

async def undo_last_ball(db, redis, manager, match_id, innings_id, scorer_user_id) -> dict:
  """
  1. Verify scorer permission
  2. SELECT last ball_by_ball WHERE innings_id=? ORDER BY id DESC LIMIT 1
  3. If none: raise 400 "No ball to undo"
  4. DELETE that ball row
  5. Recompute scorecards by re-aggregating remaining ball_by_ball rows:
     - BattingScorecard: SUM runs_off_bat, balls_faced, fours, sixes WHERE batsman_id
     - BowlingScorecard: SUM balls, runs_conceded, wickets, wides, no_balls WHERE bowler_id
     - MatchInnings: SUM all fields from ball_by_ball for innings
  6. Rebuild match_live_state from last remaining ball
  7. UPDATE Redis
  8. Broadcast WebSocket: {"event": "ball_undone", ...}
  9. Commit and return updated state
  """

async def complete_innings(db, redis, manager, match_id, innings_id) -> MatchInnings:
  """
  1. UPDATE match_innings: status='completed', ended_at=now()
  2. If innings_number == 1:
     - target = innings.total_runs + 1
     - INSERT match_innings 2 (batting/bowling teams swapped, target_runs=target, status='upcoming')
     - UPDATE match: status='innings_break'
     - Broadcast: innings_complete event with target
  3. If innings_number == 2:
     - Call complete_match()
  """

async def complete_match(db, redis, manager, match_id, awards: list | None = None) -> Match:
  """
  1. Fetch both innings to determine winner
  2. Compute winner, result_type, result_margin
  3. UPDATE match: status='completed', winner_team_id, result_type, result_margin, ended_at=now()
  4. INSERT match_awards if provided
  5. DELETE Redis key "match:live:{match_id}"
  6. Enqueue background jobs: update_player_career_stats, update_tournament_stats
  7. Broadcast: match_complete event
  8. Commit and return match
  """
```

---

### [P5-5] Scoring Routes + WebSocket Endpoint

```
Create app/modules/scoring/controller.py, routes.py for CricGeo.
Also add WebSocket routes to app/main.py.

HTTP Routes (prefix="/matches"):
  POST   /matches/{id}/innings/{innings_id}/ball             scorer only
  DELETE /matches/{id}/innings/{innings_id}/ball/undo        scorer only
  POST   /matches/{id}/innings/{innings_id}/complete         created_by or umpire
  POST   /matches/{id}/complete                              created_by or umpire
  GET    /matches/{id}/scorecard                             public
    — Returns: match info, both innings, batting_scorecards, bowling_scorecards
    — Computed fields: strike_rate, economy via @computed_field
  GET    /matches/{id}/innings/{innings_id}/balls            public (paginated)
  POST   /matches/{id}/awards                                created_by only

WebSocket Routes (add to main.py):
  WS /ws/matches/{match_id}
    — On connect: validate optional JWT (if provided), add to room "match:{match_id}"
    — Immediately send current live state (from Redis or DB) as first message
    — On disconnect: remove from room
    — Clients only receive — no input from clients processed

  WS /ws/obs/{token}
    — Validate obs_stream_tokens.token (no JWT)
    — Add to room "match:{match_id}" (get match_id from token row)
    — Same read-only behavior as above

Use manager from app.core.websocket.
```

---

### [P5-REVIEW] Scoring Engine Review

```
Review the complete scoring engine (engine.py, service.py, routes.py, model.py).

Check:
1. BallByBall model has NO update method and NO delete method anywhere — only INSERT
2. All DB writes (ball_by_ball + scorecards + innings + live_state) in single transaction
3. Optimistic locking: version is checked before UPDATE, incremented in same UPDATE
4. Redis write happens AFTER db.commit() — never before
5. WebSocket broadcast happens AFTER Redis write
6. over_number and ball_number are derived from live_state, never trusted from client
7. Wides and no-balls: do NOT increment ball_number (only total_delivery_number)
8. Striker/non-striker swap logic is correct (odd runs, end of over)
9. Undo recomputes from ball_by_ball completely — no delta math
10. innings-end check fires after every ball (wickets==10 OR over count complete)
11. WebSocket endpoint: dead connection silently dropped from room
12. OBS WebSocket: validates token exists and is_active=True before connecting
```

---

### [P5-TEST] Scoring Engine Unit Tests

```
Create tests/test_scoring_engine.py for the CricGeo backend.

Test the pure functions in app/modules/scoring/engine.py.
Use pytest — no DB, no async needed for these tests.

Test cases to cover:

test_wide_delivery:
  Input: is_wide=True, runs_off_bat=0 → extras=1, is_dot_ball=False, is_legal=False

test_no_ball_with_boundary:
  Input: is_no_ball=True, runs_off_bat=4 → is_boundary=False (no-ball boundaries don't count)

test_legal_boundary:
  Input: runs_off_bat=4, is_wide=False, is_no_ball=False → is_boundary=True, is_six=False

test_six:
  Input: runs_off_bat=6 → is_six=True, is_boundary=False (six != boundary)

test_dot_ball:
  Input: runs_off_bat=0, all extras False → is_dot_ball=True

test_over_advances_on_6th_legal:
  should_advance_over(current_ball=5, is_wide=False, is_no_ball=False) == True

test_over_does_not_advance_on_wide:
  should_advance_over(current_ball=5, is_wide=True, is_no_ball=False) == False

test_crr_calculation:
  compute_crr(total_runs=100, balls_bowled=60) == 10.0

test_rrr_calculation:
  compute_rrr(target=200, current_runs=100, remaining_balls=60) == 10.0

test_format_overs:
  format_overs(19) == "3.1"
  format_overs(120) == "20.0"

test_striker_swap_on_odd_runs:
  should_swap_on_run(runs_off_bat=1, is_wicket=False, over_ended=False) == True
  should_swap_on_run(runs_off_bat=2, is_wicket=False, over_ended=False) == False

test_no_swap_on_wicket:
  should_swap_on_run(runs_off_bat=1, is_wicket=True, over_ended=False) == False
```

---

## PHASE 6 — BACKGROUND JOBS

### [P6-1] ARQ Worker Tasks

```
Create workers/tasks.py for the CricGeo backend.

ARQ worker with these async job functions:

async def update_player_career_stats(ctx, match_id: int):
  """
  For each player who appeared in this match:
  - Aggregate from batting_scorecards WHERE match_id: SUM runs, balls_faced, fours, sixes, etc.
  - Aggregate from bowling_scorecards WHERE match_id
  - Aggregate from fielding_scorecards WHERE match_id
  - UPSERT player_career_stats (INSERT ... ON CONFLICT (user_id) DO UPDATE SET ...)
  - Update: total_matches, total_matches_won, batting totals, bowling totals, fielding totals
  - highest_score: use MAX(runs) across all batting_scorecards for that user
  """

async def update_tournament_stats(ctx, match_id: int):
  """
  If match has tournament_id:
  - For each player in match:
    UPSERT tournament_player_stats (same aggregation pattern as career stats)
  """

async def recalculate_nrr(ctx, tournament_id: int):
  """
  For each team in tournament:
  NRR = (total_runs_scored / total_overs_faced) - (total_runs_conceded / total_overs_bowled)
  Aggregate from match_innings for all completed matches in this tournament.
  UPDATE tournament_teams.nrr for each team.
  """

async def send_push_notification(ctx, notification_id: int):
  """
  SELECT notification, then push_tokens for that user (is_active=True)
  POST to FCM API for each active token
  UPDATE notification.sent_at = now()
  Handle invalid tokens: set push_tokens.is_active=False
  """

async def deactivate_obs_token(ctx, match_id: int):
  """
  UPDATE obs_stream_tokens SET is_active=False WHERE match_id=?
  """

async def cleanup_expired_otps(ctx):
  """
  DELETE FROM otps WHERE expires_at < now() - interval '1 day'
  """

class WorkerSettings:
  functions = [update_player_career_stats, update_tournament_stats, recalculate_nrr,
               send_push_notification, deactivate_obs_token, cleanup_expired_otps]
  redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
  cron_jobs = [cron(cleanup_expired_otps, hour={2})]  # 2am daily
```

---

### [P6-REVIEW] Background Jobs Review

```
Review workers/tasks.py.

Check:
1. Each job is idempotent — running twice produces same result (UPSERT not INSERT)
2. NRR formula is correct: (runs_scored/overs_faced) - (runs_conceded/overs_bowled)
   where overs are derived from balls: balls/6 (float division, not integer)
3. FCM failures don't crash the job — caught and logged per token
4. Invalid FCM tokens marked is_active=False (not deleted)
5. cleanup_expired_otps uses a grace period (not just expires_at < now())
6. Jobs use their own DB session (from ARQ context), not the FastAPI session
7. player_career_stats highest_score uses MAX across all matches, not just this match
```

---

## PHASE 7 — NOTIFICATIONS MODULE

### [P7-1] Notification Models + Service

```
Create app/modules/notifications/model.py and service.py for CricGeo.

Models:

Notification:
  __tablename__ = "notifications"
  id: bigint PK, user_id FK, type varchar(50), title varchar(200), body text,
  data JSON nullable, entity_type varchar(30) nullable, entity_id int nullable,
  is_read bool default False, read_at timestamptz nullable,
  sent_at timestamptz nullable, created_at timestamptz

PushToken:
  __tablename__ = "push_tokens"
  id, user_id FK, token varchar(500), platform varchar(10), is_active bool default True,
  created_at, updated_at
  UniqueConstraint('user_id', 'token')

Service functions:

create_notification(db, user_id, type, title, body, data=None, entity_type=None, entity_id=None) -> Notification
  — INSERT notification, then enqueue send_push_notification job

register_push_token(db, user_id, token, platform) -> PushToken
  — UPSERT: INSERT ON CONFLICT (user_id, token) DO UPDATE SET is_active=True, updated_at=now()

deregister_push_token(db, user_id, token) -> bool
  — UPDATE is_active=False WHERE user_id=? AND token=?

get_user_notifications(db, user_id, page, per_page, unread_only=False) -> dict
  — ORDER BY created_at DESC

mark_read(db, notification_id, user_id) -> Notification
  — UPDATE is_read=True, read_at=now() WHERE id=? AND user_id=? (user_id guard)

mark_all_read(db, user_id) -> int  (returns count updated)

get_unread_count(db, user_id) -> int
  — SELECT COUNT WHERE user_id=? AND is_read=False
```

---

### [P7-2] Notification Routes

```
Create app/modules/notifications/controller.py and routes.py for CricGeo.

Routes:
  POST   /notifications/push-token           auth required
    Body: {token: str, platform: "ios"|"android"}

  DELETE /notifications/push-token           auth required
    Body: {token: str}

  GET    /notifications                      auth required
    Query: ?page=1&per_page=20&unread_only=false

  GET    /notifications/unread-count         auth required
    Response: {"success": true, "data": {"count": 5}}

  PUT    /notifications/{id}/read            auth required
  PUT    /notifications/read-all             auth required

Register router prefix="/notifications" in main.py.

Also create a helper function notify_match_event(db, match_id, event_type) that:
  - Looks up all relevant users (match players, officials)
  - Creates a notification for each
  - Used internally by scoring service on toss_done, match_start, match_complete
```

---

### [P7-REVIEW] Notifications Review

```
Review the notifications module.

Check:
1. mark_read includes user_id in WHERE clause (user can't mark others' notifications read)
2. get_unread_count uses partial index WHERE is_read=false
3. UPSERT push token sets is_active=True (re-registration re-activates)
4. notify_match_event called for: match_invite, match_start, toss_done, innings_start, match_complete
5. Notification data JSON contains enough info for client deep-link (match_id, team_id etc)
6. Push delivery failure does not raise exception in the API request path (async job)
```

---

## PHASE 8 — OBS STREAMING

### [P8-1] OBS Streaming Module

```
Create app/modules/streaming/model.py, service.py, controller.py, routes.py for CricGeo.

Model ObsStreamToken:
  __tablename__ = "obs_stream_tokens"
  id, match_id FK unique, created_by FK users, token varchar(255) unique,
  overlay_theme varchar(20) default 'dark', is_active bool default True,
  last_accessed_at timestamptz nullable, created_at

Service:

create_obs_token(db, match_id, user_id) -> ObsStreamToken
  — Validate user is created_by or live_streamer official of match
  — token = secrets.token_urlsafe(48)
  — INSERT (or UPDATE if row exists: regenerate token, set is_active=True)

get_token_by_value(db, token: str) -> ObsStreamToken | None
  — SELECT WHERE token=? AND is_active=True

deactivate_token(db, match_id) -> bool

Routes:
  POST /matches/{id}/obs-token       auth required (created_by or live_streamer)
  GET  /obs/{token}/overlay          public — return HTML page
    — HTML: minimal overlay page with embedded JS that opens WS /ws/obs/{token}
    — Update score display on every WebSocket message
  GET  /obs/{token}/state            public — return current live state JSON
    — Updates last_accessed_at

Register router in main.py.
```

---

## CROSS-CUTTING PROMPTS

### [CC-1] Migration — Generate All New Tables

```
In the CricGeo backend, generate an Alembic migration for the following new tables
added since the last migration (e1f2a3b4c5d6_redesign_schema):

Tables to add (in dependency order):
  venues, subscription_plans, user_subscriptions,
  teams, team_members, team_invitations,
  tournaments, tournament_teams, tournament_rounds, tournament_player_stats, tournament_awards,
  matches, match_powerplays, match_officials, match_invitations, match_players,
  match_innings, match_live_state,
  ball_by_ball, batting_scorecards, bowling_scorecards, fielding_scorecards, match_awards,
  notifications, push_tokens, obs_stream_tokens,
  player_career_stats, keeping_infos

Also add these constraints (not in autogenerate output, add manually to migration):
  ALTER TABLE matches ADD CONSTRAINT chk_different_teams CHECK (team_a_id != team_b_id);
  ALTER TABLE match_powerplays ADD CONSTRAINT chk_pp_range CHECK (from_over < to_over);
  ALTER TABLE match_officials ADD CONSTRAINT chk_official_identity CHECK (user_id IS NOT NULL OR guest_name IS NOT NULL);
  CREATE UNIQUE INDEX idx_profiles_username_lower ON profiles (lower(username)) WHERE username IS NOT NULL;

Generate: alembic revision --autogenerate -m "add_all_v3_tables"
Then show the upgrade() function of the generated migration for review.
```

---

### [CC-2] Auth Integration — Free Plan on Signup

```
In app/modules/auth/service.py (CricGeo backend), update the user creation flow.

After a new user is successfully created (both OTP signup and Google OAuth signup):
  - Call subscriptions_service.assign_free_plan(db, user_id)
  - This must be in the same DB transaction as user creation

Find the exact location in service.py where the new user INSERT is committed,
and add the assign_free_plan call there.
Show only the changed function — do not rewrite the entire file.
```

---

### [CC-3] Permission Guard Helper

```
Create app/helpers/permissions.py for the CricGeo backend.

Reusable permission check functions (all async, all raise HTTPException):

async def require_match_owner(db, match_id: int, user_id: int):
  — Raise 403 if match.created_by != user_id

async def require_match_scorer(db, match_id: int, user_id: int):
  — Raise 403 if user is not scorer or umpire in match_officials for this match

async def require_team_owner_or_captain(db, team_id: int, user_id: int):
  — Raise 403 if user is not team owner AND not captain in team_members

async def require_tournament_organizer(db, tournament_id: int, user_id: int):
  — Raise 403 if tournament.organizer_id != user_id

Use these in controllers instead of repeating permission logic.
Each function fetches only the columns needed for the check — not the full row.
```

---

### [CC-4] Scorecard Response Schemas

```
Create app/modules/scoring/schema.py for the CricGeo backend.

Pydantic v2 response schemas for the full match scorecard:

BattingLineResponse:
  user_id, name (joined from users), batting_position,
  runs, balls_faced, fours, sixes, dismissal_type, status
  @computed_field strike_rate: float | None
    = round((runs / balls_faced) * 100, 2) if balls_faced > 0 else None

BowlingLineResponse:
  user_id, name (joined from users),
  balls_bowled, overs_display (format_overs(balls_bowled)),
  maidens, runs_conceded, wickets, wides, no_balls
  @computed_field economy: float | None
    = round((runs_conceded / balls_bowled) * 6, 2) if balls_bowled > 0 else None

InningsScorecardResponse:
  innings_id, innings_number, batting_team_id, total_runs, wickets,
  balls_bowled, overs_display, extras (with breakdown), status,
  target_runs, crr, rrr (computed via engine functions)
  batting: list[BattingLineResponse]
  bowling: list[BowlingLineResponse]

FullScorecardResponse:
  match_id, status, result_type, result_margin, winner_team_id,
  innings: list[InningsScorecardResponse]

Never store strike_rate, economy, crr, rrr in DB.
```

---

### [CC-5] Full Integration Review

```
Do a full integration review of the CricGeo backend across all modules.

Check the following cross-module concerns:

1. IMPORTS: No circular imports between modules
   (scoring imports from matches, matches imports from teams — not reverse)

2. TRANSACTIONS: Every service function that writes multiple tables uses
   a single transaction (commit once, rollback all on error)

3. REDIS CONSISTENCY: Redis is always written AFTER db.commit()
   Never written inside the try block before commit

4. WEBSOCKET: manager is imported from app.core.websocket (singleton)
   Not instantiated per-request

5. SOFT DELETE: Every list query has WHERE deleted_at IS NULL
   Check: teams, tournaments, matches, users

6. BACKGROUND JOBS: enqueue called AFTER db.commit()
   Background jobs use their own DB session

7. AUTH MIDDLEWARE: Public endpoints are listed in the skip list
   All scoring endpoints require auth (except scorecard GET)

8. PAGINATION: All list endpoints return {items, total, page, per_page}
   COUNT query runs before LIMIT/OFFSET

9. RESPONSE FORMAT: All endpoints return {success, message, data}
   Error responses also use this format

Report any violations found.
```

---

### [CC-6] Security Audit

```
Perform a security audit of the CricGeo FastAPI backend.

Check for OWASP Top 10 issues in these areas:

1. INJECTION: Any raw SQL strings? f-string queries? Use SQLAlchemy parameterized only.
2. BROKEN AUTH: JWT secret loaded from env (not hardcoded)? Token expiry enforced?
3. SENSITIVE DATA: Any plaintext passwords or OTP codes stored or logged?
4. IDOR (Broken Object Level Auth): Does every mutation endpoint verify the requesting
   user owns the resource? Check: team update, match update, score ball, undo ball.
5. SECURITY MISCONFIGURATION: DEBUG mode disabled in production? CORS restricted?
6. TOKEN SECURITY: Invitation tokens use secrets.token_urlsafe (not uuid4 or random.random)?
7. OTP BRUTE FORCE: attempts counter incremented and checked (max 5)?
8. RATE LIMITING: OTP requests rate limited per identifier?
9. FILE UPLOADS: If profile images are uploaded, MIME type validated? Size limited?
10. WEBSOCKET: OBS WebSocket validates token before accepting connection?

For each issue found: file path, line reference, severity (High/Med/Low), and fix.
```

---

### [CC-7] Performance Audit

```
Review the CricGeo backend for N+1 queries and missing index usage.

Check these specific areas:

1. Scorecard endpoint: Does it load all batting/bowling lines in 2 queries or N queries?
   (should use WHERE innings_id IN (...) not per-player SELECT)

2. Team members list: Single query with JOIN to users for names?

3. Standings query: Single ORDER BY query, no Python-side sorting?

4. Notifications feed: Does it use the (user_id, created_at) index?
   (ORDER BY created_at DESC — index exists for this)

5. Live state endpoint: Is Redis checked first before any DB query fires?

6. Ball log endpoint: Is it paginated? Does it use (innings_id, over_number, ball_number) index?

7. match_live_state: Is it a single-row PK lookup (match_id is PK)?

For each N+1 found: show the bad pattern and the fixed query using SQLAlchemy selectinload or explicit JOIN.
```

---

## FINAL CHECKLIST PROMPT

### [FINAL] Pre-Launch Verification

```
Before marking the CricGeo backend as production-ready, verify the following:

FUNCTIONAL:
[ ] All 9 phases implemented (P0 Infrastructure, P1 Venues, P2 Subscriptions,
    P3 Teams, P4 Matches, P5 Scoring, P6 Background Jobs, P7 Notifications, P8 OBS)
[ ] P9 Tournaments implemented (if required)
[ ] WebSocket connects and broadcasts ball events
[ ] Undo last ball produces identical state to re-computing from scratch
[ ] Match completion triggers background jobs correctly
[ ] OTP max attempts (5) blocks further attempts
[ ] Free plan assigned on every new user signup

DATA INTEGRITY:
[ ] ball_by_ball has no UPDATE or DELETE calls anywhere in codebase
  (grep for "DELETE" and "UPDATE" queries targeting ball_by_ball)
[ ] All optimistic locks (version column) checked before scorecard updates
[ ] Soft-deleted records (deleted_at IS NOT NULL) excluded from all queries

MIGRATIONS:
[ ] All new tables in a single migration per phase
[ ] DB constraints (CHECK, UNIQUE INDEX) added in migrations
[ ] Alembic heads are linear (no split heads)

REDIS:
[ ] Redis writes always come AFTER db.commit()
[ ] App starts without Redis (graceful degradation to DB reads)
[ ] match:live:{id} key deleted on match completion

SECURITY:
[ ] No credentials hardcoded in any Python file
[ ] JWT secret, Google client secret, FCM key from env only
[ ] OTP codes never logged
[ ] CORS restricted to known origins in production .env

DEPLOYMENT:
[ ] workers/tasks.py ARQ worker starts separately from FastAPI
[ ] docker-compose has: postgres, redis, api, worker services
[ ] requirements.txt includes: redis[hiredis], arq, httpx, qrcode[pil]
```

---

*End of AI Prompt Workflow — CricGeo Backend*
*Total prompts: 36 | Phases: 9 + Cross-cutting*
