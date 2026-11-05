
from flask import Flask, request, jsonify
from pathlib import Path
from contextlib import closing
import sqlite3
import subprocess
import json

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "cricket_tournament.db"
CPP_ENGINE = BASE_DIR / "cpp_engine" / "phase1_6.exe"


# ==================================================
# DATABASE
# ==================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database():
    with closing(get_db()) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tournaments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                format TEXT NOT NULL,
                overs_per_innings INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'registration',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                CHECK(format IN ('T20', 'ODI', 'TEST')),
                CHECK(overs_per_innings > 0),
                CHECK(status IN ('registration', 'scheduled', 'completed'))
            );

            CREATE TABLE IF NOT EXISTS tournament_teams (
                tournament_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,

                PRIMARY KEY(tournament_id, team_id),

                FOREIGN KEY(tournament_id)
                    REFERENCES tournaments(id) ON DELETE CASCADE,

                FOREIGN KEY(team_id)
                    REFERENCES teams(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tournament_fixtures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                round_number INTEGER NOT NULL,
                team1_id INTEGER NOT NULL,
                team2_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'scheduled',
                match_id INTEGER UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(tournament_id)
                    REFERENCES tournaments(id) ON DELETE CASCADE,

                FOREIGN KEY(team1_id)
                    REFERENCES teams(id),

                FOREIGN KEY(team2_id)
                    REFERENCES teams(id),

                FOREIGN KEY(match_id)
                    REFERENCES matches(id),

                CHECK(team1_id != team2_id),
                CHECK(status IN ('scheduled', 'completed'))
            );
        """)
        conn.commit()


# ==================================================
# HELPERS
# ==================================================

def error(message, status=400):
    return jsonify({
        "status": "error",
        "message": message
    }), status


def run_cpp_match(team1, team2, runs1, runs2):
    if not CPP_ENGINE.exists():
        raise FileNotFoundError(
            f"C++ executable not found: {CPP_ENGINE}"
        )

    payload = {
        "action": "calculate_match_result",
        "team1": team1,
        "team2": team2,
        "runs1": runs1,
        "runs2": runs2
    }

    process = subprocess.run(
        [str(CPP_ENGINE)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=5
    )

    try:
        response = json.loads(process.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(
            "Invalid response from C++ engine: " + process.stderr
        )

    if process.returncode != 0 or response.get("status") != "success":
        raise ValueError(response.get("message", "C++ engine failed."))

    return response


def generate_round_robin(team_ids):
    """
    Circle method for single round-robin scheduling.
    Every pair of teams plays exactly once.
    """

    teams = list(team_ids)

    if len(teams) < 2:
        raise ValueError("At least two teams are required.")

    # Add a bye position for an odd number of teams.
    if len(teams) % 2 != 0:
        teams.append(None)

    total_teams = len(teams)
    total_rounds = total_teams - 1
    matches_per_round = total_teams // 2

    fixtures = []
    rotating = teams[:]

    for round_number in range(1, total_rounds + 1):
        for index in range(matches_per_round):
            team1 = rotating[index]
            team2 = rotating[total_teams - 1 - index]

            if team1 is not None and team2 is not None:
                fixtures.append({
                    "round_number": round_number,
                    "team1_id": team1,
                    "team2_id": team2
                })

        # Keep first team fixed and rotate remaining teams.
        rotating = (
            [rotating[0]] +
            [rotating[-1]] +
            rotating[1:-1]
        )

    return fixtures


# ==================================================
# HOME
# ==================================================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "success",
        "message": "Cricket Tournament Manager - Phase 1.10",
        "features": [
            "Tournament creation",
            "Team registration",
            "Round-robin fixtures",
            "Match result recording",
            "Tournament standings"
        ]
    })


# ==================================================
# CREATE TOURNAMENT
# ==================================================

@app.route("/api/tournaments", methods=["POST"])
def create_tournament():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return error("Send a valid JSON object.")

    name = data.get("name")
    cricket_format = data.get("format")
    overs = data.get("overs_per_innings")

    if not isinstance(name, str) or not name.strip():
        return error("Tournament name is required.")

    if cricket_format not in ("T20", "ODI", "TEST"):
        return error("Format must be T20, ODI or TEST.")

    if type(overs) is not int or overs <= 0:
        return error("overs_per_innings must be a positive integer.")

    if cricket_format == "T20" and overs != 20:
        return error("T20 tournaments must use 20 overs.")

    if cricket_format == "ODI" and overs != 50:
        return error("ODI tournaments must use 50 overs.")

    if cricket_format == "TEST":
        return error(
            "Test match innings are not supported by this two-innings "
            "tournament prototype yet."
        )

    try:
        with closing(get_db()) as conn:
            cursor = conn.execute("""
                INSERT INTO tournaments (
                    name, format, overs_per_innings
                )
                VALUES (?, ?, ?)
            """, (name.strip(), cricket_format, overs))

            conn.commit()

            return jsonify({
                "status": "success",
                "message": "Tournament created successfully.",
                "tournament": {
                    "id": cursor.lastrowid,
                    "name": name.strip(),
                    "format": cricket_format,
                    "overs_per_innings": overs,
                    "status": "registration"
                }
            }), 201

    except sqlite3.IntegrityError:
        return error("Tournament name already exists.", 409)


# ==================================================
# GET TOURNAMENTS
# ==================================================

@app.route("/api/tournaments", methods=["GET"])
def get_tournaments():

    with closing(get_db()) as conn:
        rows = conn.execute("""
            SELECT
                t.*,
                COUNT(tt.team_id) AS team_count
            FROM tournaments t
            LEFT JOIN tournament_teams tt
                ON t.id = tt.tournament_id
            GROUP BY t.id
            ORDER BY t.id DESC
        """).fetchall()

        return jsonify({
            "status": "success",
            "tournaments": [dict(row) for row in rows]
        })


# ==================================================
# REGISTER TEAM IN TOURNAMENT
# ==================================================

@app.route("/api/tournaments/<int:tournament_id>/teams", methods=["POST"])
def add_team(tournament_id):

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return error("Send a valid JSON object.")

    team_id = data.get("team_id")

    if type(team_id) is not int or team_id <= 0:
        return error("A valid team_id is required.")

    with closing(get_db()) as conn:

        tournament = conn.execute(
            "SELECT * FROM tournaments WHERE id = ?",
            (tournament_id,)
        ).fetchone()

        if tournament is None:
            return error("Tournament not found.", 404)

        if tournament["status"] != "registration":
            return error("Team registration is closed.")

        team = conn.execute(
            "SELECT id, name FROM teams WHERE id = ?",
            (team_id,)
        ).fetchone()

        if team is None:
            return error("Team not found.", 404)

        try:
            conn.execute("""
                INSERT INTO tournament_teams (tournament_id, team_id)
                VALUES (?, ?)
            """, (tournament_id, team_id))

            conn.commit()

            return jsonify({
                "status": "success",
                "message": "Team added to tournament.",
                "team": dict(team)
            }), 201

        except sqlite3.IntegrityError:
            return error("Team is already registered in this tournament.", 409)


# ==================================================
# GET TOURNAMENT TEAMS
# ==================================================

@app.route("/api/tournaments/<int:tournament_id>/teams", methods=["GET"])
def get_tournament_teams(tournament_id):

    with closing(get_db()) as conn:

        tournament = conn.execute(
            "SELECT id, name FROM tournaments WHERE id = ?",
            (tournament_id,)
        ).fetchone()

        if tournament is None:
            return error("Tournament not found.", 404)

        rows = conn.execute("""
            SELECT t.id, t.name
            FROM tournament_teams tt
            JOIN teams t ON t.id = tt.team_id
            WHERE tt.tournament_id = ?
            ORDER BY t.name
        """, (tournament_id,)).fetchall()

        return jsonify({
            "status": "success",
            "tournament": dict(tournament),
            "teams": [dict(row) for row in rows]
        })


# ==================================================
# GENERATE FIXTURES
# ==================================================

@app.route(
    "/api/tournaments/<int:tournament_id>/generate-fixtures",
    methods=["POST"]
)
def create_fixtures(tournament_id):

    with closing(get_db()) as conn:

        tournament = conn.execute(
            "SELECT * FROM tournaments WHERE id = ?",
            (tournament_id,)
        ).fetchone()

        if tournament is None:
            return error("Tournament not found.", 404)

        if tournament["status"] != "registration":
            return error("Fixtures have already been generated.")

        teams = conn.execute("""
            SELECT team_id
            FROM tournament_teams
            WHERE tournament_id = ?
            ORDER BY team_id
        """, (tournament_id,)).fetchall()

        team_ids = [row["team_id"] for row in teams]

        if len(team_ids) < 2:
            return error("Register at least two teams first.")

        fixtures = generate_round_robin(team_ids)

        with conn:
            for fixture in fixtures:
                conn.execute("""
                    INSERT INTO tournament_fixtures (
                        tournament_id,
                        round_number,
                        team1_id,
                        team2_id
                    )
                    VALUES (?, ?, ?, ?)
                """, (
                    tournament_id,
                    fixture["round_number"],
                    fixture["team1_id"],
                    fixture["team2_id"]
                ))

            conn.execute("""
                UPDATE tournaments
                SET status = 'scheduled'
                WHERE id = ?
            """, (tournament_id,))

        return jsonify({
            "status": "success",
            "message": "Fixtures generated successfully.",
            "total_teams": len(team_ids),
            "total_fixtures": len(fixtures),
            "fixtures": fixtures
        }), 201


# ==================================================
# GET FIXTURES
# ==================================================

@app.route(
    "/api/tournaments/<int:tournament_id>/fixtures",
    methods=["GET"]
)
def get_fixtures(tournament_id):

    with closing(get_db()) as conn:

        tournament = conn.execute(
            "SELECT id, name FROM tournaments WHERE id = ?",
            (tournament_id,)
        ).fetchone()

        if tournament is None:
            return error("Tournament not found.", 404)

        rows = conn.execute("""
            SELECT
                f.id AS fixture_id,
                f.round_number,
                f.status,
                f.match_id,
                t1.id AS team1_id,
                t1.name AS team1,
                t2.id AS team2_id,
                t2.name AS team2,
                m.runs1,
                m.runs2,
                m.winner,
                m.result
            FROM tournament_fixtures f
            JOIN teams t1 ON t1.id = f.team1_id
            JOIN teams t2 ON t2.id = f.team2_id
            LEFT JOIN matches m ON m.id = f.match_id
            WHERE f.tournament_id = ?
            ORDER BY f.round_number, f.id
        """, (tournament_id,)).fetchall()

        return jsonify({
            "status": "success",
            "tournament": dict(tournament),
            "fixtures": [dict(row) for row in rows]
        })


# ==================================================
# RECORD FIXTURE RESULT
# ==================================================

@app.route(
    "/api/tournaments/<int:tournament_id>/fixtures/<int:fixture_id>/result",
    methods=["POST"]
)
def record_fixture_result(tournament_id, fixture_id):

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return error("Send a valid JSON object.")

    runs1 = data.get("runs1")
    runs2 = data.get("runs2")

    if type(runs1) is not int or type(runs2) is not int:
        return error("runs1 and runs2 must be integers.")

    if runs1 < 0 or runs2 < 0:
        return error("Runs cannot be negative.")

    with closing(get_db()) as conn:

        fixture = conn.execute("""
            SELECT
                f.*,
                t1.name AS team1,
                t2.name AS team2
            FROM tournament_fixtures f
            JOIN teams t1 ON t1.id = f.team1_id
            JOIN teams t2 ON t2.id = f.team2_id
            WHERE f.id = ? AND f.tournament_id = ?
        """, (fixture_id, tournament_id)).fetchone()

        if fixture is None:
            return error("Fixture not found.", 404)

        if fixture["status"] == "completed":
            return error("This fixture already has a result.")

        try:
            result = run_cpp_match(
                fixture["team1"],
                fixture["team2"],
                runs1,
                runs2
            )

            with conn:
                cursor = conn.execute("""
                    INSERT INTO matches (
                        team1_id,
                        team2_id,
                        runs1,
                        runs2,
                        winner,
                        result
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    fixture["team1_id"],
                    fixture["team2_id"],
                    runs1,
                    runs2,
                    result["winner"],
                    result["result"]
                ))

                match_id = cursor.lastrowid

                conn.execute("""
                    UPDATE tournament_fixtures
                    SET status = 'completed', match_id = ?
                    WHERE id = ? AND tournament_id = ?
                """, (match_id, fixture_id, tournament_id))

            return jsonify({
                "status": "success",
                "message": "Fixture result saved.",
                "fixture_id": fixture_id,
                "match_id": match_id,
                "result": result
            }), 201

        except FileNotFoundError as exc:
            return error(str(exc), 500)

        except subprocess.TimeoutExpired:
            return error("C++ engine timed out.", 504)

        except (ValueError, RuntimeError) as exc:
            return error(str(exc), 400)

        except sqlite3.Error as exc:
            return error(str(exc), 500)


# ==================================================
# TOURNAMENT STANDINGS
# ==================================================

@app.route(
    "/api/tournaments/<int:tournament_id>/standings",
    methods=["GET"]
)
def get_standings(tournament_id):

    with closing(get_db()) as conn:

        tournament = conn.execute(
            "SELECT id, name FROM tournaments WHERE id = ?",
            (tournament_id,)
        ).fetchone()

        if tournament is None:
            return error("Tournament not found.", 404)

        rows = conn.execute("""
            WITH results AS (

                SELECT
                    f.team1_id AS team_id,
                    CASE WHEN m.runs1 > m.runs2 THEN 1 ELSE 0 END AS won,
                    CASE WHEN m.runs1 < m.runs2 THEN 1 ELSE 0 END AS lost,
                    CASE WHEN m.runs1 = m.runs2 THEN 1 ELSE 0 END AS tied,
                    CASE
                        WHEN m.runs1 > m.runs2 THEN 2
                        WHEN m.runs1 = m.runs2 THEN 1
                        ELSE 0
                    END AS points
                FROM tournament_fixtures f
                JOIN matches m ON m.id = f.match_id
                WHERE f.tournament_id = ?
                  AND f.status = 'completed'

                UNION ALL

                SELECT
                    f.team2_id AS team_id,
                    CASE WHEN m.runs2 > m.runs1 THEN 1 ELSE 0 END AS won,
                    CASE WHEN m.runs2 < m.runs1 THEN 1 ELSE 0 END AS lost,
                    CASE WHEN m.runs2 = m.runs1 THEN 1 ELSE 0 END AS tied,
                    CASE
                        WHEN m.runs2 > m.runs1 THEN 2
                        WHEN m.runs2 = m.runs1 THEN 1
                        ELSE 0
                    END AS points
                FROM tournament_fixtures f
                JOIN matches m ON m.id = f.match_id
                WHERE f.tournament_id = ?
                  AND f.status = 'completed'
            )

            SELECT
                t.id AS team_id,
                t.name AS team,
                COUNT(r.team_id) AS played,
                COALESCE(SUM(r.won), 0) AS won,
                COALESCE(SUM(r.lost), 0) AS lost,
                COALESCE(SUM(r.tied), 0) AS tied,
                COALESCE(SUM(r.points), 0) AS points
            FROM tournament_teams tt
            JOIN teams t ON t.id = tt.team_id
            LEFT JOIN results r ON r.team_id = t.id
            WHERE tt.tournament_id = ?
            GROUP BY t.id, t.name
            ORDER BY points DESC, won DESC, t.name COLLATE NOCASE
        """, (tournament_id, tournament_id, tournament_id)).fetchall()

        standings = []

        for position, row in enumerate(rows, start=1):
            item = dict(row)
            item["position"] = position
            standings.append(item)

        return jsonify({
            "status": "success",
            "tournament": dict(tournament),
            "standings": standings
        })


# ==================================================
# COMPLETE TOURNAMENT
# ==================================================

@app.route(
    "/api/tournaments/<int:tournament_id>/complete",
    methods=["POST"]
)
def complete_tournament(tournament_id):

    with closing(get_db()) as conn:

        tournament = conn.execute(
            "SELECT * FROM tournaments WHERE id = ?",
            (tournament_id,)
        ).fetchone()

        if tournament is None:
            return error("Tournament not found.", 404)

        if tournament["status"] != "scheduled":
            return error("Tournament is not in the scheduled state.")

        pending = conn.execute("""
            SELECT COUNT(*) AS count
            FROM tournament_fixtures
            WHERE tournament_id = ? AND status != 'completed'
        """, (tournament_id,)).fetchone()["count"]

        if pending > 0:
            return error(
                f"{pending} fixtures are still incomplete."
            )

        conn.execute("""
            UPDATE tournaments
            SET status = 'completed'
            WHERE id = ?
        """, (tournament_id,))

        conn.commit()

        return jsonify({
            "status": "success",
            "message": "Tournament marked as completed."
        })


# ==================================================
# START SERVER
# ==================================================

if __name__ == "__main__":
    initialize_database()

    print("Phase 1.10 database initialized.")
    print("Tournament API: http://127.0.0.1:5002")

    app.run(debug=True, port=5002)
