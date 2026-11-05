
from flask import Flask, request, jsonify
from pathlib import Path
from contextlib import closing
import sqlite3
import subprocess
import json

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "cricket_tournament.db"
SCORING_ENGINE = BASE_DIR / "cpp_engine" / "phase1_9_engine.exe"
MATCH_ENGINE = BASE_DIR / "cpp_engine" / "phase1_6.exe"


# ---------------- DATABASE ----------------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database():
    with closing(get_db()) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS innings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                innings_number INTEGER NOT NULL,
                batting_team_id INTEGER NOT NULL,
                bowling_team_id INTEGER NOT NULL,
                total_runs INTEGER NOT NULL,
                wickets INTEGER NOT NULL,
                legal_balls INTEGER NOT NULL,
                extras INTEGER NOT NULL,
                overs TEXT NOT NULL,

                FOREIGN KEY(match_id) REFERENCES matches(id),
                FOREIGN KEY(batting_team_id) REFERENCES teams(id),
                FOREIGN KEY(bowling_team_id) REFERENCES teams(id),

                UNIQUE(match_id, innings_number)
            );

            CREATE TABLE IF NOT EXISTS deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                innings_id INTEGER NOT NULL,
                sequence INTEGER NOT NULL,
                over_number INTEGER NOT NULL,
                legal_ball_number INTEGER NOT NULL,
                batter_id INTEGER NOT NULL,
                bowler_id INTEGER NOT NULL,
                batter_runs INTEGER NOT NULL,
                extras_type TEXT NOT NULL,
                extras_runs INTEGER NOT NULL,
                total_runs INTEGER NOT NULL,
                is_legal INTEGER NOT NULL,
                wicket_type TEXT NOT NULL,
                dismissed_player_id INTEGER,

                FOREIGN KEY(innings_id) REFERENCES innings(id),
                FOREIGN KEY(batter_id) REFERENCES players(id),
                FOREIGN KEY(bowler_id) REFERENCES players(id),
                FOREIGN KEY(dismissed_player_id) REFERENCES players(id),

                UNIQUE(innings_id, sequence)
            );

            CREATE TABLE IF NOT EXISTS batting_scorecards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                innings_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                runs INTEGER NOT NULL,
                balls INTEGER NOT NULL,
                fours INTEGER NOT NULL,
                sixes INTEGER NOT NULL,

                FOREIGN KEY(innings_id) REFERENCES innings(id),
                FOREIGN KEY(player_id) REFERENCES players(id),

                UNIQUE(innings_id, player_id)
            );

            CREATE TABLE IF NOT EXISTS bowling_scorecards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                innings_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                legal_balls INTEGER NOT NULL,
                runs_conceded INTEGER NOT NULL,
                wickets INTEGER NOT NULL,
                wides INTEGER NOT NULL,
                no_balls INTEGER NOT NULL,
                economy REAL NOT NULL,

                FOREIGN KEY(innings_id) REFERENCES innings(id),
                FOREIGN KEY(player_id) REFERENCES players(id),

                UNIQUE(innings_id, player_id)
            );
        """)
        conn.commit()


# ---------------- HELPERS ----------------

def error(message, status=400):
    return jsonify({
        "status": "error",
        "message": message
    }), status


def run_cpp(executable, payload):
    if not executable.exists():
        raise FileNotFoundError(
            f"C++ executable not found: {executable}"
        )

    process = subprocess.run(
        [str(executable)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10
    )

    try:
        response = json.loads(process.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(
            "C++ returned an invalid response. " + process.stderr
        )

    if process.returncode != 0 or response.get("status") != "success":
        raise ValueError(response.get("message", "C++ engine failed."))

    return response


def get_player_teams(conn, player_ids):
    if not player_ids:
        return {}

    placeholders = ",".join("?" for _ in player_ids)

    rows = conn.execute(
        f"SELECT id, team_id FROM players WHERE id IN ({placeholders})",
        tuple(player_ids)
    ).fetchall()

    return {row["id"]: row["team_id"] for row in rows}


# ---------------- HOME ----------------

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "success",
        "message": "Cricket Tournament Manager - Phase 1.9",
        "features": [
            "Ball-by-ball scoring",
            "Batting scorecards",
            "Bowling scorecards",
            "SQLite persistence"
        ]
    })


# ---------------- SAVE COMPLETE MATCH ----------------

@app.route("/api/scorecard", methods=["POST"])
def save_scorecard():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return error("Send a valid JSON object.")

    required = ["team1_id", "team2_id", "overs_limit", "innings"]

    if not all(field in data for field in required):
        return error(
            "Required fields: team1_id, team2_id, overs_limit, innings."
        )

    team1_id = data["team1_id"]
    team2_id = data["team2_id"]
    overs_limit = data["overs_limit"]
    innings_data = data["innings"]

    if any(type(value) is not int for value in
           [team1_id, team2_id, overs_limit]):
        return error("Team IDs and overs_limit must be integers.")

    if team1_id <= 0 or team2_id <= 0 or team1_id == team2_id:
        return error("Provide two different, positive team IDs.")

    if overs_limit <= 0 or overs_limit > 90:
        return error("overs_limit must be between 1 and 90.")

    if not isinstance(innings_data, list) or len(innings_data) != 2:
        return error("Exactly two innings are required.")

    try:
        with closing(get_db()) as conn:

            teams = conn.execute(
                "SELECT id, name FROM teams WHERE id IN (?, ?)",
                (team1_id, team2_id)
            ).fetchall()

            team_names = {row["id"]: row["name"] for row in teams}

            if team1_id not in team_names or team2_id not in team_names:
                return error("One or both teams do not exist.", 404)

            calculated_innings = []

            # Validate and calculate each innings.
            for index, inning in enumerate(innings_data, start=1):

                if not isinstance(inning, dict):
                    return error(f"Innings {index} must be an object.")

                batting_team_id = inning.get("batting_team_id")

                if type(batting_team_id) is not int:
                    return error(
                        f"Innings {index}: batting_team_id must be an integer."
                    )

                if batting_team_id not in (team1_id, team2_id):
                    return error(
                        f"Innings {index}: invalid batting team."
                    )

                expected_batting_team = (
                    team1_id if index == 1 else team2_id
                )

                if batting_team_id != expected_batting_team:
                    return error(
                        "Innings 1 must belong to team1_id and "
                        "innings 2 must belong to team2_id."
                    )

                bowling_team_id = (
                    team2_id if batting_team_id == team1_id else team1_id
                )

                deliveries = inning.get("deliveries")

                if not isinstance(deliveries, list) or not deliveries:
                    return error(
                        f"Innings {index} must contain at least one delivery."
                    )

                player_ids = set()

                for delivery in deliveries:
                    if not isinstance(delivery, dict):
                        return error("Each delivery must be a JSON object.")

                    batter_id = delivery.get("batter_id")
                    bowler_id = delivery.get("bowler_id")

                    if type(batter_id) is not int or type(bowler_id) is not int:
                        return error(
                            "Every delivery needs integer batter_id and bowler_id."
                        )

                    player_ids.add(batter_id)
                    player_ids.add(bowler_id)

                    dismissed_id = delivery.get("dismissed_player_id")

                    if dismissed_id is not None:
                        if type(dismissed_id) is not int:
                            return error(
                                "dismissed_player_id must be an integer."
                            )
                        player_ids.add(dismissed_id)

                player_teams = get_player_teams(conn, player_ids)

                if len(player_teams) != len(player_ids):
                    return error(
                        f"Innings {index}: one or more player IDs do not exist."
                    )

                for delivery in deliveries:
                    batter_id = delivery["batter_id"]
                    bowler_id = delivery["bowler_id"]
                    dismissed_id = delivery.get("dismissed_player_id")

                    if player_teams[batter_id] != batting_team_id:
                        return error(
                            "A batter does not belong to the batting team."
                        )

                    if player_teams[bowler_id] != bowling_team_id:
                        return error(
                            "A bowler does not belong to the bowling team."
                        )

                    if dismissed_id is not None:
                        if player_teams[dismissed_id] != batting_team_id:
                            return error(
                                "The dismissed player must belong to the batting team."
                            )

                cpp_request = {
                    "overs_limit": overs_limit,
                    "deliveries": deliveries
                }

                result = run_cpp(SCORING_ENGINE, cpp_request)

                calculated_innings.append({
                    "innings_number": index,
                    "batting_team_id": batting_team_id,
                    "bowling_team_id": bowling_team_id,
                    "result": result
                })

            first_score = calculated_innings[0]["result"]["total_runs"]
            second_score = calculated_innings[1]["result"]["total_runs"]

            # Use the original C++ match engine for the winner.
            match_result = run_cpp(MATCH_ENGINE, {
                "action": "calculate_match_result",
                "team1": team_names[team1_id],
                "team2": team_names[team2_id],
                "runs1": first_score,
                "runs2": second_score
            })

            # Save all records together.
            # If a database operation fails, the transaction is rolled back.
            with conn:

                match_cursor = conn.execute("""
                    INSERT INTO matches (
                        team1_id, team2_id, runs1, runs2, winner, result
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    team1_id,
                    team2_id,
                    first_score,
                    second_score,
                    match_result["winner"],
                    match_result["result"]
                ))

                match_id = match_cursor.lastrowid

                for inning in calculated_innings:

                    result = inning["result"]

                    inning_cursor = conn.execute("""
                        INSERT INTO innings (
                            match_id,
                            innings_number,
                            batting_team_id,
                            bowling_team_id,
                            total_runs,
                            wickets,
                            legal_balls,
                            extras,
                            overs
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        match_id,
                        inning["innings_number"],
                        inning["batting_team_id"],
                        inning["bowling_team_id"],
                        result["total_runs"],
                        result["wickets"],
                        result["legal_balls"],
                        result["extras"],
                        result["overs"]
                    ))

                    innings_id = inning_cursor.lastrowid

                    for delivery in result["deliveries"]:
                        conn.execute("""
                            INSERT INTO deliveries (
                                innings_id,
                                sequence,
                                over_number,
                                legal_ball_number,
                                batter_id,
                                bowler_id,
                                batter_runs,
                                extras_type,
                                extras_runs,
                                total_runs,
                                is_legal,
                                wicket_type,
                                dismissed_player_id
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            innings_id,
                            delivery["sequence"],
                            delivery["over_number"],
                            delivery["legal_ball_number"],
                            delivery["batter_id"],
                            delivery["bowler_id"],
                            delivery["batter_runs"],
                            delivery["extras_type"],
                            delivery["extras_runs"],
                            delivery["total_runs"],
                            int(delivery["is_legal"]),
                            delivery["wicket_type"],
                            delivery["dismissed_player_id"]
                        ))

                    for player in result["batting_card"]:
                        conn.execute("""
                            INSERT INTO batting_scorecards (
                                innings_id, player_id, runs, balls, fours, sixes
                            )
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            innings_id,
                            player["player_id"],
                            player["runs"],
                            player["balls"],
                            player["fours"],
                            player["sixes"]
                        ))

                    for player in result["bowling_card"]:
                        conn.execute("""
                            INSERT INTO bowling_scorecards (
                                innings_id,
                                player_id,
                                legal_balls,
                                runs_conceded,
                                wickets,
                                wides,
                                no_balls,
                                economy
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            innings_id,
                            player["player_id"],
                            player["legal_balls"],
                            player["runs_conceded"],
                            player["wickets"],
                            player["wides"],
                            player["no_balls"],
                            player["economy"]
                        ))

            return jsonify({
                "status": "success",
                "message": "Match and ball-by-ball scorecards saved.",
                "match_id": match_id,
                "match_result": match_result,
                "innings": [
                    {
                        "innings_number": item["innings_number"],
                        "batting_team": team_names[item["batting_team_id"]],
                        "score": (
                            f'{item["result"]["total_runs"]}/'
                            f'{item["result"]["wickets"]}'
                        ),
                        "overs": item["result"]["overs"],
                        "extras": item["result"]["extras"]
                    }
                    for item in calculated_innings
                ]
            }), 201

    except FileNotFoundError as exc:
        return error(str(exc), 500)

    except subprocess.TimeoutExpired:
        return error("C++ engine timed out.", 504)

    except ValueError as exc:
        return error(str(exc), 400)

    except (RuntimeError, sqlite3.Error, KeyError, TypeError) as exc:
        return error(f"Could not save match: {exc}", 500)


# ---------------- GET COMPLETE SCORECARD ----------------

@app.route("/api/scorecard/<int:match_id>", methods=["GET"])
def get_scorecard(match_id):

    with closing(get_db()) as conn:

        match = conn.execute("""
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
            WHERE m.id = ?
        """, (match_id,)).fetchone()

        if match is None:
            return error("Match not found.", 404)

        innings_rows = conn.execute("""
            SELECT
                i.*,
                t.name AS batting_team
            FROM innings i
            JOIN teams t ON i.batting_team_id = t.id
            WHERE i.match_id = ?
            ORDER BY i.innings_number
        """, (match_id,)).fetchall()

        innings_output = []

        for inning in innings_rows:
            innings_id = inning["id"]

            batting = conn.execute("""
                SELECT
                    p.name,
                    p.role,
                    b.runs,
                    b.balls,
                    b.fours,
                    b.sixes
                FROM batting_scorecards b
                JOIN players p ON p.id = b.player_id
                WHERE b.innings_id = ?
                ORDER BY b.runs DESC
            """, (innings_id,)).fetchall()

            bowling = conn.execute("""
                SELECT
                    p.name,
                    b.legal_balls,
                    b.runs_conceded,
                    b.wickets,
                    b.wides,
                    b.no_balls,
                    b.economy
                FROM bowling_scorecards b
                JOIN players p ON p.id = b.player_id
                WHERE b.innings_id = ?
                ORDER BY b.wickets DESC, b.runs_conceded
            """, (innings_id,)).fetchall()

            innings_output.append({
                "innings_number": inning["innings_number"],
                "batting_team": inning["batting_team"],
                "score": f'{inning["total_runs"]}/{inning["wickets"]}',
                "overs": inning["overs"],
                "extras": inning["extras"],
                "batting_card": [dict(row) for row in batting],
                "bowling_card": [dict(row) for row in bowling]
            })

        return jsonify({
            "status": "success",
            "match": dict(match),
            "innings": innings_output
        })


# ---------------- GET BALL-BY-BALL DETAILS ----------------

@app.route("/api/innings/<int:innings_id>/deliveries", methods=["GET"])
def get_deliveries(innings_id):

    with closing(get_db()) as conn:

        inning = conn.execute("""
            SELECT id, innings_number, total_runs, wickets, overs
            FROM innings
            WHERE id = ?
        """, (innings_id,)).fetchone()

        if inning is None:
            return error("Innings not found.", 404)

        rows = conn.execute("""
            SELECT
                d.sequence,
                d.over_number,
                d.legal_ball_number,
                batter.name AS batter,
                bowler.name AS bowler,
                d.batter_runs,
                d.extras_type,
                d.extras_runs,
                d.total_runs,
                d.is_legal,
                d.wicket_type,
                dismissed.name AS dismissed_player
            FROM deliveries d
            JOIN players batter ON batter.id = d.batter_id
            JOIN players bowler ON bowler.id = d.bowler_id
            LEFT JOIN players dismissed
                ON dismissed.id = d.dismissed_player_id
            WHERE d.innings_id = ?
            ORDER BY d.sequence
        """, (innings_id,)).fetchall()

        return jsonify({
            "status": "success",
            "innings": dict(inning),
            "deliveries": [dict(row) for row in rows]
        })


# ---------------- START SERVER ----------------

if __name__ == "__main__":
    initialize_database()

    print("Phase 1.9 database tables initialized.")
    print(f"Database: {DATABASE}")
    print("Scoring API: http://127.0.0.1:5001")

    app.run(debug=True, port=5001)
