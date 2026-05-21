# CricGeo — Simple Data Flow Documentation


============================================================
1. SYSTEM OVERVIEW
============================================================

Flutter Mobile App
        │
        │ HTTPS / WebSocket
        ▼
FastAPI Backend
        │
        ├── Auth Module
        ├── User/Profile Module
        ├── Team Module
        ├── Match Module
        ├── Tournament Module
        ├── Notification Module
        └── Live Scoring Engine
        │
        ▼
Data Layer
        ├── PostgreSQL → Main database
        ├── Redis → Live match cache
        └── S3/CDN → Images & QR


============================================================
2. AUTHENTICATION FLOW
============================================================


----------------------------
PHONE OTP LOGIN
----------------------------

User enters phone number
        ↓
Backend generates OTP
        ↓
SMS sent
        ↓
User enters OTP
        ↓
OTP verified
        ↓
JWT session created
        ↓
Profile completed?

    ├── Yes → Home
    └── No  → Profile Setup


----------------------------
EMAIL OTP LOGIN
----------------------------

User enters email
        ↓
Backend generates OTP
        ↓
OTP email sent
        ↓
User enters OTP
        ↓
OTP verified
        ↓
JWT session created
        ↓
Profile completed?

    ├── Yes → Home
    └── No  → Profile Setup


----------------------------
GOOGLE LOGIN
----------------------------

User selects Google account
        ↓
Google returns user info
        ↓
Backend checks existing account
        ↓
Create user if needed
        ↓
JWT session created
        ↓
Profile completed?

    ├── Yes → Home
    └── No  → Profile Setup


============================================================
3. TEAM CREATION FLOW
============================================================

User clicks Create Team
        ↓
Enter team info
        ↓
Upload logo
        ↓
Add players
        ↓
Save team
        ↓
Backend creates:
    - team
    - team_members
        ↓
Team ready


============================================================
4. MATCH CREATION FLOW
============================================================

User clicks Create Match
        ↓
Select Team A & Team B
        ↓
Select Playing XI
        ↓
Assign officials
        ↓
Configure overs & powerplay
        ↓
Set venue/date/time
        ↓
Save match
        ↓
Backend creates:
    - matches
    - match_players
    - match_officials
    - match_powerplays
        ↓
Match scheduled


============================================================
5. MATCH START FLOW
============================================================

Admin clicks Start Match
        ↓
Toss completed
        ↓
Backend creates innings
        ↓
Initialize live state
        ↓
Redis cache initialized
        ↓
Match status = LIVE


============================================================
6. LIVE SCORING FLOW (CORE)
============================================================

Scorer taps run/wicket/extra
        ↓
Backend validates ball
        ↓
Save ball event
        ↓
Update innings score
        ↓
Update batsman stats
        ↓
Update bowler stats
        ↓
Update live match state
        ↓
Send WebSocket event
        ↓
All users instantly see score update


============================================================
7. INNINGS BREAK FLOW
============================================================

1st innings completed
        ↓
Backend calculates target
        ↓
Required run rate calculated
        ↓
2nd innings initialized
        ↓
Match status = INNINGS BREAK


============================================================
8. MATCH COMPLETION FLOW
============================================================

Match ends
        ↓
Winner calculated
        ↓
Awards selected
        ↓
Final scorecard generated
        ↓
Match status = COMPLETED
        ↓
Background jobs triggered


============================================================
9. BACKGROUND JOBS FLOW
============================================================

Match completed
        ↓
Update player career stats
        ↓
Update tournament stats
        ↓
Update leaderboard
        ↓
Send notifications
        ↓
Deactivate OBS stream token


============================================================
10. NOTIFICATION FLOW
============================================================

Event occurs

    ├── Match invite
    ├── Match start
    ├── Toss complete
    ├── Innings start
    └── Match complete

        ↓

Notification service triggered
        ↓
Save notification
        ↓
Push notification sent via FCM


============================================================
11. TEAM QR JOIN FLOW
============================================================

User scans Team QR
        ↓
Backend validates token
        ↓
Team preview shown
        ↓
User sends join request
        ↓
Captain approves
        ↓
Player added to team


============================================================
12. MATCH QR JOIN FLOW
============================================================

User scans Match QR
        ↓
Backend validates token
        ↓
Match preview shown
        ↓
User joins/request joins
        ↓
Access granted


============================================================
13. OBS STREAMING FLOW
============================================================

Live match starts
        ↓
OBS token generated
        ↓
Overlay URL created
        ↓
OBS Browser Source loads URL
        ↓
WebSocket updates score live
        ↓
Overlay updates automatically


============================================================
14. CORE BACKEND RULES
============================================================

- PostgreSQL is primary database
- Redis is used for live state only
- ball_by_ball is immutable
- Every scored ball creates one event
- WebSocket handles real-time updates
- JWT used for authentication
- Background jobs handle heavy processing
- Live score always comes from match_live_state