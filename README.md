# 🏏 Cricket Tournament Management System 

A full-stack **Cricket Tournament Management System** built as an Object-Oriented Programming project. The system uses **C++ engines** for core cricket logic, **Python Flask** microservices for the REST API layer, **SQLite** for persistence, and an **HTML/CSS/JS** frontend for the management dashboard.

---

## 📑 Table of Contents

- [System Architecture](#-system-architecture)
- [OOP Concepts Used](#-oop-concepts-used)
- [Project Structure](#-project-structure)
- [C++ Engine Layer](#-c-engine-layer)
- [Python Backend Layer](#-python-backend-layer)
- [Database Design](#-database-design)
- [REST API Reference](#-rest-api-reference)
- [Frontend Layer](#-frontend-layer)
- [How to Run](#-how-to-run)
- [Tech Stack](#-tech-stack)

---

## 🏗 System Architecture

The system follows a **layered microservice architecture** with four independently running services connected through an API gateway.

```
┌──────────────────────────────────────────────────────────┐
│                     BROWSER (User)                       │
│                   http://127.0.0.1:5003                  │
└──────────────────────┬───────────────────────────────────┘
                       │
         ┌─────────────▼──────────────┐
         │    API GATEWAY (Phase 2)   │
         │    phase2_app.py :5003     │
         │                            │
         │  • Serves frontend files   │
         │  • Reverse-proxies /api/*  │
         └────┬──────────┬────────────┘
              │          │
   ┌──────────▼──┐  ┌────▼────────────┐
   │  /api/core  │  │ /api/tournament │
   │             │  │                 │
   ▼             │  ▼                 │
┌────────────┐   │ ┌──────────────┐   │
│ Core API   │   │ │ Tournament   │   │
│ app.py     │   │ │ API          │   │
│ :5000      │   │ │ phase1_10_   │   │
│            │   │ │ app.py :5002 │   │
│ • Teams    │   │ │              │   │
│ • Players  │   │ │ • Create     │   │
│ • Matches  │   │ │   tournament │   │
│ • Points   │   │ │ • Fixtures   │   │
│   table    │   │ │ • Standings  │   │
└──────┬─────┘   │ └──────┬───────┘   │
       │         │        │           │
       │         │ ┌──────▼────────┐  │
       │         │ │ Scoring API   │  │
       │         │ │ phase1_9_     │  │
       │         │ │ app.py :5001  │  │
       │         │ │               │  │
       │         │ │ • Ball-by-ball│  │
       │         │ │ • Scorecards  │  │
       │         │ │ • Deliveries  │  │
       │         │ └──────┬────────┘  │
       │         │        │           │
       ▼         ▼        ▼           │
  ┌───────────────────────────┐       │
  │   C++ ENGINE LAYER        │       │
  │                           │       │
  │  phase1_6.exe             │◄──────┘
  │  • Match result calc      │
  │  • Points table calc      │
  │                           │
  │  phase1_9_engine.exe      │
  │  • Ball-by-ball scoring   │
  │  • Batting/bowling cards  │
  └───────────────────────────┘
              │
              ▼
  ┌───────────────────────────┐
  │   SQLite Database         │
  │   cricket_tournament.db   │
  │                           │
  │   Shared by all Python    │
  │   microservices           │
  └───────────────────────────┘
```

### Data Flow

1. **User** interacts with the frontend dashboard at `http://127.0.0.1:5003`.
2. **API Gateway** (`phase2_app.py`) serves static files and reverse-proxies API calls to the correct backend service.
3. **Python Flask services** validate input, manage the SQLite database, and delegate cricket-specific calculations to C++ engines via `subprocess` (JSON over stdin/stdout).
4. **C++ engines** receive a JSON request on stdin, perform the computation, and return a JSON response on stdout.
5. **SQLite** persists all teams, players, matches, innings, deliveries, and scorecards.

---

## 🎓 OOP Concepts Used

### C++ Engine — `main.cpp` (OOP Demonstration)

| Concept                   | Where It's Used                                                                                   |
| ------------------------- | ------------------------------------------------------------------------------------------------- |
| **Abstract Base Class**   | `Person` is an abstract class with `virtual void displayDetails() = 0`                            |
| **Inheritance**           | `Player` inherits from `Person`                                                                   |
| **Polymorphism**          | `Match` is abstract; `T20Match`, `ODIMatch`, `TestMatch` override `getFormat()`, `getMaxOvers()`  |
| **Encapsulation**         | Private data members with public getters in `Player`, `Team`, `Innings`                           |
| **Composition**           | `Team` contains a `vector<Player>`, `Tournament` contains `vector<Team>` and `vector<Match>`      |
| **Smart Pointers**        | `Tournament::matches` uses `vector<unique_ptr<Match>>` for polymorphic ownership                  |
| **Exception Handling**    | `try-catch` blocks with `invalid_argument` and `runtime_error` throughout                         |
| **STL Containers**        | `vector`, `find_if`, `any_of` used for collections and searching                                  |

### C++ Engine — `scoring_engine.cpp` (Scoring Engine Demo)

| Concept                   | Where It's Used                                                                                   |
| ------------------------- | ------------------------------------------------------------------------------------------------- |
| **Enumerations**          | `enum class Dismissal` with BOWLED, CAUGHT, LBW, STUMPED, HIT_WICKET, RUN_OUT, RETIRED_HURT      |
| **Structs**               | `BallEvent` struct encapsulates a single delivery's data                                          |
| **Encapsulation**         | `BattingStats`, `BowlingStats`, `Innings` classes with private members                            |
| **Data Hiding**           | Private validation methods like `validateEvent()`, `calculateExtras()`                            |
| **Composition**           | `Innings` contains `unordered_map<string, BattingStats>` and `unordered_map<string, BowlingStats>`|
| **Operator Overloading**  | Uses `swap()` for strike rotation                                                                 |
| **Const Correctness**     | Methods like `displayScore()`, `getStrikeRate()` are `const`                                      |

### C++ Engine — `phase1_6.cpp` (Match Result Engine — Production)

| Concept                   | Where It's Used                                                                                   |
| ------------------------- | ------------------------------------------------------------------------------------------------- |
| **Class Design**          | `Match` class with validation, result computation, and getter methods                             |
| **Data Structures**       | `map<string, TeamRecord>` in `PointsTable` for efficient team lookup                              |
| **Composition**           | `CommandProcessor` composes `Match` and `PointsTable` to process commands                         |
| **JSON Integration**      | Uses `nlohmann/json` library for stdin/stdout IPC with Python                                     |
| **Command Pattern**       | `CommandProcessor::process()` dispatches `get_formats`, `calculate_match_result`, `calculate_points` |
| **Lambda Functions**      | Used in `sort()` for custom ranking logic                                                         |

### C++ Engine — `phase1_9_engine.cpp` (Scoring Engine — Production)

| Concept                   | Where It's Used                                                                                   |
| ------------------------- | ------------------------------------------------------------------------------------------------- |
| **Encapsulation**         | `ScoringEngine` class with private state and a single public `calculate()` method                 |
| **Structs**               | `BattingStats` and `BowlingStats` for per-player statistics                                       |
| **Static Methods**        | `getInteger()` static helper for JSON field extraction                                            |
| **Validation**            | Comprehensive validation of extras types, wicket types, and scoring combinations                  |
| **JSON Serialization**    | Builds structured JSON response with batting cards, bowling cards, and delivery log                |

### Python Backend — OOP in Flask Services

| Concept                   | Where It's Used                                                                                   |
| ------------------------- | ------------------------------------------------------------------------------------------------- |
| **Modular Design**        | Each service is a self-contained Flask application with clear responsibilities                     |
| **Separation of Concerns**| Database access, validation, business logic, and C++ delegation are in separate functions          |
| **Factory Pattern**       | `get_db()` / `get_db_connection()` create database connections with consistent configuration      |
| **Context Management**    | `closing()` context manager ensures database connections are properly closed                       |
| **Error Handling**        | Structured error responses with appropriate HTTP status codes                                     |

---

## 📁 Project Structure

```
opps/
│
├── README.md                        # This file
├── requirement.txt                  # Python dependencies (flask)
├── cricket_tournament.db            # SQLite database (auto-created)
│
├── app.py                           # Core API — Teams, Players, Matches (port 5000)
├── phase1_9_app.py                  # Scoring API — Ball-by-ball scoring (port 5001)
├── phase1_10_app.py                 # Tournament API — Tournaments, Fixtures (port 5002)
├── phase2_app.py                    # API Gateway + Frontend server (port 5003)
│
└── cpp_engine/
    │
    ├── main.cpp                     # OOP demonstration — class hierarchy
    ├── scoring_engine.cpp           # OOP demonstration — scoring engine
    │
    ├── phase1_6.cpp                 # Production C++ engine — match results
    ├── phase1_6.exe                 # Compiled match result engine
    │
    ├── phase1_9_engine.cpp          # Production C++ engine — ball-by-ball scoring
    │
    ├── include/
    │   └── json.hpp                 # nlohmann/json header-only library
    │
    └── frontend/
        ├── index.html               # Single-page application HTML
        ├── style.css                # Dashboard styles
        └── app.js                   # Frontend JavaScript (API calls, routing, rendering)
```

---

## ⚙ C++ Engine Layer

The C++ engines communicate with Python via **JSON over stdin/stdout**. Python calls them using `subprocess.run()`, sends a JSON request as stdin, and reads the JSON response from stdout.

### Match Result Engine (`phase1_6.cpp` → `phase1_6.exe`)

**Purpose:** Calculate match results and points tables.

**Supported Actions:**

| Action                      | Input                                    | Output                                      |
| --------------------------- | ---------------------------------------- | ------------------------------------------- |
| `get_formats`               | `{}`                                     | List of supported formats (T20, ODI, TEST)  |
| `calculate_match_result`    | team1, team2, runs1, runs2               | Winner, result string, scores               |
| `calculate_points`          | Array of matches                         | Ranked standings with points                 |

**Classes:**
- `Match` — Validates teams and scores, determines winner and margin.
- `PointsTable` — Tracks wins, losses, ties; computes ranked standings.
- `CommandProcessor` — Parses JSON action and dispatches to the correct handler.

### Scoring Engine (`phase1_9_engine.cpp`)

**Purpose:** Process ball-by-ball delivery data and compute scorecards.

**Input:** `{ "overs_limit": 20, "deliveries": [...] }`

**Output:**
```json
{
  "status": "success",
  "total_runs": 156,
  "wickets": 6,
  "legal_balls": 120,
  "overs": "20.0",
  "extras": 12,
  "batting_card": [ ... ],
  "bowling_card": [ ... ],
  "deliveries": [ ... ]
}
```

**Classes:**
- `ScoringEngine` — Processes each delivery, updates batting/bowling stats, validates extras and dismissals, and builds the complete scorecard.

**Supported Extras:** `none`, `wide`, `no_ball`, `bye`, `leg_bye`

**Supported Dismissals:** `none`, `bowled`, `caught`, `lbw`, `stumped`, `hit_wicket`, `run_out`, `retired_hurt`

---

## 🐍 Python Backend Layer

### Service 1: Core API (`app.py` — Port 5000)

Manages the foundational entities: teams, players, and match records.

**Responsibilities:**
- CRUD operations for teams and players
- Match creation with C++ engine integration for result calculation
- Points table / league standings
- Player role validation (Batter, Bowler, All-rounder, Wicketkeeper)

### Service 2: Scoring API (`phase1_9_app.py` — Port 5001)

Handles detailed ball-by-ball scoring and scorecard persistence.

**Responsibilities:**
- Accept full innings data with deliveries
- Delegate scoring computation to the C++ scoring engine
- Persist innings, deliveries, batting scorecards, and bowling scorecards
- Retrieve complete match scorecards and ball-by-ball details

### Service 3: Tournament API (`phase1_10_app.py` — Port 5002)

Manages tournament lifecycle: creation, team registration, fixture generation, and standings.

**Responsibilities:**
- Create tournaments with format (T20/ODI) and over limits
- Register teams into tournaments
- Generate round-robin fixtures using the circle method algorithm
- Record fixture results via the C++ match engine
- Compute tournament-specific standings
- Mark tournaments as completed

### Service 4: API Gateway (`phase2_app.py` — Port 5003)

Serves the frontend and proxies API requests to backend services.

**Routing:**

| Frontend Request             | Proxied To                              |
| ---------------------------- | --------------------------------------- |
| `/api/core/<endpoint>`       | `http://127.0.0.1:5000/api/<endpoint>`  |
| `/api/scoring/<endpoint>`    | `http://127.0.0.1:5001/api/<endpoint>`  |
| `/api/tournament/<endpoint>` | `http://127.0.0.1:5002/api/<endpoint>`  |

---

## 🗄 Database Design

All services share a single SQLite database: `cricket_tournament.db`.

```
┌─────────────┐       ┌──────────────────┐       ┌────────────────────┐
│   teams     │       │     players      │       │    tournaments     │
├─────────────┤       ├──────────────────┤       ├────────────────────┤
│ id (PK)     │◄──┐   │ id (PK)          │       │ id (PK)            │
│ name        │   ├───│ team_id (FK)     │       │ name               │
│ created_at  │   │   │ name             │       │ format             │
└─────────────┘   │   │ role             │       │ overs_per_innings  │
                  │   │ jersey_number    │       │ status             │
                  │   │ batting_style    │       │ created_at         │
                  │   │ bowling_style    │       └────────┬───────────┘
                  │   │ created_at       │                │
                  │   └──────────────────┘                │
                  │                                       │
                  │   ┌──────────────────┐   ┌────────────▼───────────┐
                  │   │    matches       │   │  tournament_teams      │
                  │   ├──────────────────┤   ├────────────────────────┤
                  ├───│ team1_id (FK)    │   │ tournament_id (FK, PK) │
                  ├───│ team2_id (FK)    │   │ team_id (FK, PK)       │
                  │   │ id (PK)          │   └────────────────────────┘
                  │   │ runs1            │
                  │   │ runs2            │   ┌────────────────────────┐
                  │   │ winner           │   │  tournament_fixtures   │
                  │   │ result           │   ├────────────────────────┤
                  │   │ played_at        │   │ id (PK)                │
                  │   └──────┬───────────┘   │ tournament_id (FK)     │
                  │          │               │ round_number           │
                  │          │               │ team1_id (FK)          │
                  │   ┌──────▼───────────┐   │ team2_id (FK)          │
                  │   │    innings       │   │ status                 │
                  │   ├──────────────────┤   │ match_id (FK)          │
                  │   │ id (PK)          │   │ created_at             │
                  │   │ match_id (FK)    │   └────────────────────────┘
                  │   │ innings_number   │
                  ├───│ batting_team_id  │
                  ├───│ bowling_team_id  │
                  │   │ total_runs       │
                  │   │ wickets          │
                  │   │ legal_balls      │
                  │   │ extras           │
                  │   │ overs            │
                  │   └──────┬───────────┘
                  │          │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌────────────────┐ ┌─────────────────┐
│   deliveries    │ │ batting_       │ │ bowling_        │
│                 │ │ scorecards     │ │ scorecards      │
├─────────────────┤ ├────────────────┤ ├─────────────────┤
│ id (PK)         │ │ id (PK)        │ │ id (PK)         │
│ innings_id (FK) │ │ innings_id(FK) │ │ innings_id (FK) │
│ sequence        │ │ player_id (FK) │ │ player_id (FK)  │
│ over_number     │ │ runs           │ │ legal_balls     │
│ legal_ball_no   │ │ balls          │ │ runs_conceded   │
│ batter_id (FK)  │ │ fours          │ │ wickets         │
│ bowler_id (FK)  │ │ sixes          │ │ wides           │
│ batter_runs     │ └────────────────┘ │ no_balls        │
│ extras_type     │                    │ economy         │
│ extras_runs     │                    └─────────────────┘
│ total_runs      │
│ is_legal        │
│ wicket_type     │
│ dismissed_id    │
└─────────────────┘
```

### Table Summary

| Table                  | Purpose                                    | Created By        |
| ---------------------- | ------------------------------------------ | ----------------- |
| `teams`                | Registered cricket teams                   | `app.py`          |
| `players`              | Player profiles with role and style info   | `app.py`          |
| `matches`              | Completed match records with results       | `app.py`          |
| `tournaments`          | Tournament definitions (name, format)      | `phase1_10_app.py`|
| `tournament_teams`     | Teams registered in each tournament        | `phase1_10_app.py`|
| `tournament_fixtures`  | Round-robin fixture schedule               | `phase1_10_app.py`|
| `innings`              | Innings summary per match                  | `phase1_9_app.py` |
| `deliveries`           | Ball-by-ball delivery records              | `phase1_9_app.py` |
| `batting_scorecards`   | Batting stats per player per innings       | `phase1_9_app.py` |
| `bowling_scorecards`   | Bowling stats per player per innings       | `phase1_9_app.py` |

---

## 🌐 REST API Reference

### Core API (Port 5000)

| Method | Endpoint                             | Description              |
| ------ | ------------------------------------ | ------------------------ |
| GET    | `/`                                  | Health check             |
| POST   | `/api/teams`                         | Register a new team      |
| GET    | `/api/teams`                         | List all teams           |
| POST   | `/api/teams/<id>/players`            | Add player to team       |
| GET    | `/api/teams/<id>/players`            | Get team squad           |
| GET    | `/api/players`                       | List all players         |
| GET    | `/api/players/<id>`                  | Get player details       |
| POST   | `/api/matches`                       | Create match with result |
| GET    | `/api/matches`                       | List all matches         |
| GET    | `/api/standings`                     | Get points table         |

### Scoring API (Port 5001)

| Method | Endpoint                             | Description                        |
| ------ | ------------------------------------ | ---------------------------------- |
| GET    | `/`                                  | Health check                       |
| POST   | `/api/scorecard`                     | Save complete match with deliveries|
| GET    | `/api/scorecard/<match_id>`          | Get full scorecard                 |
| GET    | `/api/innings/<id>/deliveries`       | Get ball-by-ball data              |

### Tournament API (Port 5002)

| Method | Endpoint                                                  | Description                |
| ------ | --------------------------------------------------------- | -------------------------- |
| GET    | `/`                                                       | Health check               |
| POST   | `/api/tournaments`                                        | Create tournament          |
| GET    | `/api/tournaments`                                        | List tournaments           |
| POST   | `/api/tournaments/<id>/teams`                             | Add team to tournament     |
| GET    | `/api/tournaments/<id>/teams`                             | Get tournament teams       |
| POST   | `/api/tournaments/<id>/generate-fixtures`                 | Generate round-robin schedule |
| GET    | `/api/tournaments/<id>/fixtures`                          | Get fixtures               |
| POST   | `/api/tournaments/<id>/fixtures/<fid>/result`             | Record fixture result      |
| GET    | `/api/tournaments/<id>/standings`                         | Get tournament standings   |
| POST   | `/api/tournaments/<id>/complete`                          | Mark tournament completed  |

---

## 🖥 Frontend Layer

The frontend is a **single-page application** (SPA) built with vanilla HTML, CSS, and JavaScript — no frameworks.

### Pages

| Page              | Description                                                       |
| ----------------- | ----------------------------------------------------------------- |
| **Dashboard**     | Overview with stats cards (tournaments, teams, players, matches)  |
| **Tournaments**   | Create tournaments, select active tournament                      |
| **Teams & Players** | Register teams, add teams to tournaments, manage player squads  |
| **Fixtures & Results** | Generate round-robin fixtures, record match results           |
| **Points Table**  | Live standings with rank, played, won, lost, tied, points         |

### Key Features

- Sidebar navigation with active page highlighting
- Toast notifications for success/error feedback
- Backend connection status indicator
- Responsive layout with mobile sidebar toggle
- XSS-safe HTML rendering with `esc()` helper
- Async API calls with structured error handling

---

## 🚀 How to Run

### Prerequisites

- **Python 3.8+** with Flask installed
- **C++ compiler** (g++ / MinGW) — only if you need to recompile the C++ engines
- Pre-compiled `phase1_6.exe` is included

### Step 1: Install Python Dependencies

```bash
pip install flask
```

### Step 2: Compile C++ Engines (if needed)

```bash
cd cpp_engine

g++ -o phase1_6.exe phase1_6.cpp -std=c++17

g++ -o phase1_9_engine.exe phase1_9_engine.cpp -std=c++17
```

### Step 3: Start All Backend Services

Open **four separate terminals** and run:

```bash
# Terminal 1 — Core API (port 5000)
python app.py

# Terminal 2 — Scoring API (port 5001)
python phase1_9_app.py

# Terminal 3 — Tournament API (port 5002)
python phase1_10_app.py

# Terminal 4 — API Gateway + Frontend (port 5003)
python phase2_app.py
```

### Step 4: Open the Dashboard

Open your browser and navigate to:

```
http://127.0.0.1:5003
```

---

## 🛠 Tech Stack

| Layer          | Technology                                        |
| -------------- | ------------------------------------------------- |
| **Frontend**   | HTML5, CSS3, Vanilla JavaScript (SPA)             |
| **Backend**    | Python 3, Flask (4 microservices)                 |
| **Database**   | SQLite 3 (with foreign keys and constraints)      |
| **Engine**     | C++ 17 with nlohmann/json header-only library     |
| **IPC**        | JSON over stdin/stdout via `subprocess`           |
| **Gateway**    | Python `urllib` reverse proxy                     |

---

## 📝 OOP Demonstration Files

The project includes two standalone C++ demonstration files that showcase OOP concepts without any backend integration:

| File                   | Concepts Demonstrated                                                  |
| ---------------------- | ---------------------------------------------------------------------- |
| `main.cpp`             | Abstract classes, inheritance, polymorphism, smart pointers, templates |
| `scoring_engine.cpp`   | Enums, structs, encapsulation, validation, state management            |

These can be compiled and run independently:

```bash
cd cpp_engine

g++ -o main.exe main.cpp -std=c++17
./main.exe

g++ -o scoring_engine.exe scoring_engine.cpp -std=c++17
./scoring_engine.exe
```

---

#   o p p s p r o j e c t 
 
 