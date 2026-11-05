
from flask import Flask, request, jsonify
from pathlib import Path
from contextlib import closing
import sqlite3
import subprocess
import json

app = Flask(__name__)

# ---------------- PATHS ----------------

BASE_DIR = Path(__file__).resolve().parent
CPP_ENGINE = BASE_DIR / "cpp_engine" / "phase1_6.exe"
DATABASE = BASE_DIR / "cricket_tournament.db"

PLAYER_ROLES = {
    "Batter",
    "Bowler",
    "All-rounder",
    "Wicketkeeper"
}

BATTING_STYLES = {
    "Right-hand",
    "Left-hand"
}


# ---------------- DATABASE CONNECTION ----------------

def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


# ---------------- DATABASE INITIALIZATION ----------------

def initialize_database():
    with closing(get_db_connection()) as conn:

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team1_id INTEGER NOT NULL,
                team2_id INTEGER NOT NULL,
                runs1 INTEGER NOT NULL CHECK(runs1 >= 0),
                runs2 INTEGER NOT NULL CHECK(runs2 >= 0),
                winner TEXT NOT NULL,
                result TEXT NOT NULL,
                played_at TEXT DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(team1_id) REFERENCES teams(id),
                FOREIGN KEY(team2_id) REFERENCES teams(id),

                CHECK(team1_id != team2_id)
            );

            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                name TEXT NOT NULL COLLATE NOCASE,
                role TEXT NOT NULL,
                jersey_number INTEGER,
                batting_style TEXT,
                bowling_style TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(team_id) REFERENCES teams(id)
                    ON DELETE CASCADE,

                UNIQUE(team_id, name),
                UNIQUE(team_id, jersey_number),

                CHECK(role IN (
                    'Batter',
                    'Bowler',
                    'All-rounder',
                    'Wicketkeeper'
                )),

                CHECK(
                    jersey_number IS NULL OR jersey_number > 0
                )
            );
        """)

        conn.commit()


# ---------------- HOME ----------------

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "success",
        "message": "Cricket Tournament Manager API is running",
        "database": DATABASE.name,
        "phase": "1.8 - Player and Squad Management"
    })


# ---------------- REGISTER TEAM ----------------

@app.route("/api/teams", methods=["POST"])
def register_team():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Send a valid JSON object."
        }), 400

    name = data.get("name")

    if not isinstance(name, str) or not name.strip():
        return jsonify({
            "status": "error",
            "message": "Team name is required."
        }), 400

    name = name.strip()

    try:
        with closing(get_db_connection()) as conn:

            cursor = conn.execute(
                "INSERT INTO teams (name) VALUES (?)",
                (name,)
            )

            conn.commit()

            return jsonify({
                "status": "success",
                "message": "Team registered successfully.",
                "team": {
                    "id": cursor.lastrowid,
                    "name": name
                }
            }), 201

    except sqlite3.IntegrityError:
        return jsonify({
            "status": "error",
            "message": "A team with this name already exists."
        }), 409


# ---------------- GET ALL TEAMS ----------------

@app.route("/api/teams", methods=["GET"])
def get_teams():

    with closing(get_db_connection()) as conn:

        rows = conn.execute("""
            SELECT id, name, created_at
            FROM teams
            ORDER BY id
        """).fetchall()

        return jsonify({
            "status": "success",
            "teams": [dict(row) for row in rows]
        })


# ---------------- REGISTER PLAYER ----------------

@app.route("/api/teams/<int:team_id>/players", methods=["POST"])
def register_player(team_id):

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Send a valid JSON object."
        }), 400

    name = data.get("name")
    role = data.get("role")
    jersey_number = data.get("jersey_number")
    batting_style = data.get("batting_style")
    bowling_style = data.get("bowling_style")

    # Validate player name
    if not isinstance(name, str) or not name.strip():
        return jsonify({
            "status": "error",
            "message": "Player name is required."
        }), 400

    name = name.strip()

    # Validate role
    if role not in PLAYER_ROLES:
        return jsonify({
            "status": "error",
            "message": "Role must be Batter, Bowler, All-rounder or Wicketkeeper."
        }), 400

    # Validate jersey number
    if jersey_number is not None:
        if type(jersey_number) is not int or jersey_number <= 0:
            return jsonify({
                "status": "error",
                "message": "Jersey number must be a positive integer."
            }), 400

    # Validate batting style
    if batting_style is not None:
        if batting_style not in BATTING_STYLES:
            return jsonify({
                "status": "error",
                "message": "Batting style must be Right-hand or Left-hand."
            }), 400

    # Validate bowling style
    if bowling_style is not None:
        if not isinstance(bowling_style, str) or not bowling_style.strip():
            return jsonify({
                "status": "error",
                "message": "Bowling style must be a non-empty string."
            }), 400

        bowling_style = bowling_style.strip()

    with closing(get_db_connection()) as conn:

        # Check whether the team exists
        team = conn.execute(
            "SELECT id, name FROM teams WHERE id = ?",
            (team_id,)
        ).fetchone()

        if team is None:
            return jsonify({
                "status": "error",
                "message": "Team not found."
            }), 404

        try:
            cursor = conn.execute("""
                INSERT INTO players (
                    team_id,
                    name,
                    role,
                    jersey_number,
                    batting_style,
                    bowling_style
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                team_id,
                name,
                role,
                jersey_number,
                batting_style,
                bowling_style
            ))

            conn.commit()

            return jsonify({
                "status": "success",
                "message": "Player registered successfully.",
                "player": {
                    "id": cursor.lastrowid,
                    "team_id": team_id,
                    "team_name": team["name"],
                    "name": name,
                    "role": role,
                    "jersey_number": jersey_number,
                    "batting_style": batting_style,
                    "bowling_style": bowling_style
                }
            }), 201

        except sqlite3.IntegrityError as error:

            if "players.team_id, players.name" in str(error):
                message = "This player is already registered in this team."

            elif "players.team_id, players.jersey_number" in str(error):
                message = "This jersey number is already used by this team."

            else:
                message = "Could not register player. Check the player details."

            return jsonify({
                "status": "error",
                "message": message
            }), 409


# ---------------- GET TEAM SQUAD ----------------

@app.route("/api/teams/<int:team_id>/players", methods=["GET"])
def get_team_squad(team_id):

    with closing(get_db_connection()) as conn:

        team = conn.execute(
            "SELECT id, name FROM teams WHERE id = ?",
            (team_id,)
        ).fetchone()

        if team is None:
            return jsonify({
                "status": "error",
                "message": "Team not found."
            }), 404

        players = conn.execute("""
            SELECT
                id,
                team_id,
                name,
                role,
                jersey_number,
                batting_style,
                bowling_style,
                created_at
            FROM players
            WHERE team_id = ?
            ORDER BY
                CASE role
                    WHEN 'Wicketkeeper' THEN 1
                    WHEN 'Batter' THEN 2
                    WHEN 'All-rounder' THEN 3
                    WHEN 'Bowler' THEN 4
                END,
                name
        """, (team_id,)).fetchall()

        return jsonify({
            "status": "success",
            "team": dict(team),
            "player_count": len(players),
            "players": [dict(player) for player in players]
        })


# ---------------- GET ALL PLAYERS ----------------

@app.route("/api/players", methods=["GET"])
def get_all_players():

    with closing(get_db_connection()) as conn:

        players = conn.execute("""
            SELECT
                p.id,
                p.name,
                p.role,
                p.jersey_number,
                p.batting_style,
                p.bowling_style,
                t.id AS team_id,
                t.name AS team_name
            FROM players p
            JOIN teams t ON p.team_id = t.id
            ORDER BY t.name, p.name
        """).fetchall()

        return jsonify({
            "status": "success",
            "total_players": len(players),
            "players": [dict(player) for player in players]
        })


# ---------------- GET ONE PLAYER ----------------

@app.route("/api/players/<int:player_id>", methods=["GET"])
def get_player(player_id):

    with closing(get_db_connection()) as conn:

        player = conn.execute("""
            SELECT
                p.id,
                p.name,
                p.role,
                p.jersey_number,
                p.batting_style,
                p.bowling_style,
                p.created_at,
                t.id AS team_id,
                t.name AS team_name
            FROM players p
            JOIN teams t ON p.team_id = t.id
            WHERE p.id = ?
        """, (player_id,)).fetchone()

        if player is None:
            return jsonify({
                "status": "error",
                "message": "Player not found."
            }), 404

        return jsonify({
            "status": "success",
            "player": dict(player)
        })


# ---------------- CREATE MATCH ----------------

@app.route("/api/matches", methods=["POST"])
def create_match():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Send a valid JSON object."
        }), 400

    required_fields = [
        "team1_id", "team2_id", "runs1", "runs2"
    ]

    if not all(field in data for field in required_fields):
        return jsonify({
            "status": "error",
            "message": "Required: team1_id, team2_id, runs1, runs2."
        }), 400

    values = [data[field] for field in required_fields]

    if any(type(value) is not int for value in values):
        return jsonify({
            "status": "error",
            "message": "Team IDs and scores must be integers."
        }), 400

    team1_id = data["team1_id"]
    team2_id = data["team2_id"]
    runs1 = data["runs1"]
    runs2 = data["runs2"]

    if team1_id <= 0 or team2_id <= 0:
        return jsonify({
            "status": "error",
            "message": "Team IDs must be positive."
        }), 400

    if team1_id == team2_id:
        return jsonify({
            "status": "error",
            "message": "A team cannot play against itself."
        }), 400

    if runs1 < 0 or runs2 < 0:
        return jsonify({
            "status": "error",
            "message": "Runs cannot be negative."
        }), 400

    with closing(get_db_connection()) as conn:

        teams = conn.execute(
            "SELECT id, name FROM teams WHERE id IN (?, ?)",
            (team1_id, team2_id)
        ).fetchall()

        team_lookup = {
            team["id"]: team["name"] for team in teams
        }

        if team1_id not in team_lookup or team2_id not in team_lookup:
            return jsonify({
                "status": "error",
                "message": "One or both teams do not exist."
            }), 404

        if not CPP_ENGINE.exists():
            return jsonify({
                "status": "error",
                "message": f"C++ executable not found: {CPP_ENGINE}"
            }), 500

        cpp_request = {
            "action": "calculate_match_result",
            "team1": team_lookup[team1_id],
            "team2": team_lookup[team2_id],
            "runs1": runs1,
            "runs2": runs2
        }

        try:
            process = subprocess.run(
                [str(CPP_ENGINE)],
                input=json.dumps(cpp_request),
                capture_output=True,
                text=True,
                timeout=5
            )

            if process.returncode != 0:
                return jsonify({
                    "status": "error",
                    "message": "C++ engine execution failed.",
                    "details": process.stderr
                }), 500

            cpp_response = json.loads(process.stdout)

        except subprocess.TimeoutExpired:
            return jsonify({
                "status": "error",
                "message": "C++ engine timed out."
            }), 504

        except (OSError, json.JSONDecodeError) as error:
            return jsonify({
                "status": "error",
                "message": f"C++ engine error: {error}"
            }), 500

        if cpp_response.get("status") != "success":
            return jsonify(cpp_response), 400

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
            team1_id,
            team2_id,
            runs1,
            runs2,
            cpp_response["winner"],
            cpp_response["result"]
        ))

        conn.commit()

        return jsonify({
            "status": "success",
            "message": "Match calculated and saved successfully.",
            "match_id": cursor.lastrowid,
            "match_result": cpp_response
        }), 201


# ---------------- GET ALL MATCHES ----------------

@app.route("/api/matches", methods=["GET"])
def get_matches():

    with closing(get_db_connection()) as conn:

        rows = conn.execute("""
            SELECT
                m.id,
                t1.name AS team1,
                t2.name AS team2,
                m.runs1,
                m.runs2,
                m.winner,
                m.result,
                m.played_at
            FROM matches m
            JOIN teams t1 ON m.team1_id = t1.id
            JOIN teams t2 ON m.team2_id = t2.id
            ORDER BY m.id DESC
        """).fetchall()

        return jsonify({
            "status": "success",
            "matches": [dict(row) for row in rows]
        })


# ---------------- POINTS TABLE ----------------

@app.route("/api/standings", methods=["GET"])
def get_standings():

    with closing(get_db_connection()) as conn:

        rows = conn.execute("""
            WITH team_results AS (
                SELECT
                    team1_id AS team_id,
                    1 AS played,
                    CASE WHEN runs1 > runs2 THEN 1 ELSE 0 END AS won,
                    CASE WHEN runs1 < runs2 THEN 1 ELSE 0 END AS lost,
                    CASE WHEN runs1 = runs2 THEN 1 ELSE 0 END AS tied,
                    CASE
                        WHEN runs1 > runs2 THEN 2
                        WHEN runs1 = runs2 THEN 1
                        ELSE 0
                    END AS points
                FROM matches

                UNION ALL

                SELECT
                    team2_id AS team_id,
                    1 AS played,
                    CASE WHEN runs2 > runs1 THEN 1 ELSE 0 END AS won,
                    CASE WHEN runs2 < runs1 THEN 1 ELSE 0 END AS lost,
                    CASE WHEN runs2 = runs1 THEN 1 ELSE 0 END AS tied,
                    CASE
                        WHEN runs2 > runs1 THEN 2
                        WHEN runs2 = runs1 THEN 1
                        ELSE 0
                    END AS points
                FROM matches
            )

            SELECT
                t.id AS team_id,
                t.name AS team,
                COALESCE(SUM(r.played), 0) AS played,
                COALESCE(SUM(r.won), 0) AS won,
                COALESCE(SUM(r.lost), 0) AS lost,
                COALESCE(SUM(r.tied), 0) AS tied,
                COALESCE(SUM(r.points), 0) AS points
            FROM teams t
            LEFT JOIN team_results r ON t.id = r.team_id
            GROUP BY t.id, t.name
            ORDER BY points DESC, won DESC, t.name COLLATE NOCASE
        """).fetchall()

        standings = []

        for position, row in enumerate(rows, start=1):
            item = dict(row)
            item["position"] = position
            standings.append(item)

        return jsonify({
            "status": "success",
            "standings": standings
        })


# ---------------- START APPLICATION ----------------

if __name__ == "__main__":
    initialize_database()

    print("SQLite database initialized.")
    print(f"Database: {DATABASE}")
    print("Player and Squad Management API is ready.")

    app.run(debug=True, port=5000)

