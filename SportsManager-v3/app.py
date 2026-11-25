from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import Functions

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect("test.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS players (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player1 TEXT NOT NULL,
            player2 TEXT NOT NULL,
            winner TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_all_players():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM players ORDER BY id ASC")
    players = [row["name"] for row in cursor.fetchall()]
    conn.close()
    return players

@app.route("/", methods=["GET", "POST"])
def home():
    init_db()
    error = None

    if request.method == "POST":
        raw_name = request.form.get("name", "")
        name = " ".join(raw_name.split())

        if not name:
            error = "Player name cannot be empty or just spaces."
        elif len(name) > 30:
            error = "Player name must be 30 characters or fewer."
        else:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM players WHERE LOWER(name) = LOWER(?)", (name,))
            existing = cursor.fetchone()

            if existing:
                error = f"'{name}' is already registered in the player list."
            else:
                cursor.execute("INSERT INTO players (name) VALUES (?)", (name,))
                # Clear any stale tournament matches when roster changes
                cursor.execute("DELETE FROM matches")
                conn.commit()
                conn.close()
                return redirect(url_for("home"))
            conn.close()

    players = get_all_players()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM matches")
    has_active_matches = cursor.fetchone()["cnt"] > 0
    conn.close()

    return render_template("index.html", players=players, error=error, has_active_matches=has_active_matches)

@app.route("/delete", methods=["POST"])
def delete():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM players")
    cursor.execute("DELETE FROM matches")
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

@app.route("/delete/<name>", methods=["POST"])
def delete_player(name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM players WHERE name = ?", (name,))
    cursor.execute("DELETE FROM matches")
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

@app.route("/match", methods=["GET", "POST"])
def matches():
    init_db()
    players = get_all_players()

    if len(players) < 2:
        return render_template("index.html", players=players, error="You need at least 2 players to generate matches.", has_active_matches=False)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, player1, player2, winner FROM matches ORDER BY id ASC")
    existing_matches = cursor.fetchall()

    # Generate and persist schedule if not already created
    if not existing_matches:
        pairs = Functions.generate_pairs(players)
        for p1, p2 in pairs:
            cursor.execute("INSERT INTO matches (player1, player2, winner) VALUES (?, ?, NULL)", (p1, p2))
        conn.commit()
        cursor.execute("SELECT id, player1, player2, winner FROM matches ORDER BY id ASC")
        existing_matches = cursor.fetchall()

    conn.close()
    return render_template("matches.html", matches=existing_matches)

@app.route("/play", methods=["GET", "POST"])
def play():
    init_db()
    players = get_all_players()

    if len(players) < 2:
        return redirect(url_for("home"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Ensure matches exist if user jumped straight here
    cursor.execute("SELECT COUNT(*) as cnt FROM matches")
    if cursor.fetchone()["cnt"] == 0:
        pairs = Functions.generate_pairs(players)
        for p1, p2 in pairs:
            cursor.execute("INSERT INTO matches (player1, player2, winner) VALUES (?, ?, NULL)", (p1, p2))
        conn.commit()

    cursor.execute("SELECT COUNT(*) as total FROM matches")
    total_matches = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as played FROM matches WHERE winner IS NOT NULL")
    played_matches = cursor.fetchone()["played"]

    cursor.execute("SELECT id, player1, player2 FROM matches WHERE winner IS NULL ORDER BY id ASC LIMIT 1")
    current_match = cursor.fetchone()
    conn.close()

    # All matches completed -> show final results
    if not current_match:
        return redirect(url_for("results"))

    current_number = played_matches + 1
    return render_template(
        "play.html",
        match=current_match,
        current_number=current_number,
        total_matches=total_matches,
        can_undo=(played_matches > 0)
    )

@app.route("/record/<int:match_id>", methods=["POST"])
def record_winner(match_id):
    winner = request.form.get("winner", "").strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT player1, player2 FROM matches WHERE id = ?", (match_id,))
    match = cursor.fetchone()

    if match and winner in (match["player1"], match["player2"], "DRAW"):
        cursor.execute("UPDATE matches SET winner = ? WHERE id = ?", (winner, match_id))
        conn.commit()

    conn.close()
    return redirect(url_for("play"))

@app.route("/undo", methods=["POST"])
def undo_last():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM matches WHERE winner IS NOT NULL ORDER BY id DESC LIMIT 1")
    last_played = cursor.fetchone()
    if last_played:
        cursor.execute("UPDATE matches SET winner = NULL WHERE id = ?", (last_played["id"],))
        conn.commit()
    conn.close()
    return redirect(url_for("play"))

@app.route("/results", methods=["GET"])
def results():
    init_db()
    players = get_all_players()
    if len(players) < 2:
        return redirect(url_for("home"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT player1, player2, winner FROM matches ORDER BY id ASC")
    all_matches = cursor.fetchall()
    conn.close()

    if not all_matches:
        return redirect(url_for("matches"))

    # Initialize every registered player with 0 points so 0-win players still appear
    scores = {p: 0 for p in players}
    for m in all_matches:
        w = m["winner"]
        if w in scores:
            scores[w] += 1
        elif w == "DRAW":
            scores[m["player1"]] += 0.5
            scores[m["player2"]] += 0.5

    results_list = Functions.announce(scores)
    return render_template("results.html", results=results_list, matches=all_matches)

@app.route("/reset", methods=["POST"])
def reset():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM players")
    cursor.execute("DELETE FROM matches")
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

@app.route("/rematch", methods=["POST"])
def rematch():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE matches SET winner = NULL")
    conn.commit()
    conn.close()
    return redirect(url_for("play"))

@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", code=404, message="That page does not exist."), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
