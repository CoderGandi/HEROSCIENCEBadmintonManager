# Function 1a: Return structured (player1, player2) pairs
def generate_pairs(players):
    pairs = []
    for i in range(len(players)):
        for j in range(i + 1, len(players)):
            pairs.append((players[i], players[j]))
    return pairs


# Function 1b: Return formatted string matchups
def matchplayers(players):
    return [f"{p1} vs {p2}" for p1, p2 in generate_pairs(players)]


# Function 2: Tally winner occurrences
def pointcount(tallies):
    dct2 = {}
    for i in tallies:
        dct2[i] = dct2.get(i, 0) + 1
    return dct2


# Function 3: Format and sort final leaderboard results
def announce(result):
    sorted_results = sorted(result.items(), key=lambda item: item[1], reverse=True)
    results = []
    for idx, (player, points) in enumerate(sorted_results, start=1):
        # Format whole numbers cleanly (e.g. 2 instead of 2.0)
        display_pts = int(points) if points == int(points) else points
        unit = "point" if display_pts == 1 else "points"
        results.append(f"#{idx} — {player} ({display_pts} {unit})")
    return results
