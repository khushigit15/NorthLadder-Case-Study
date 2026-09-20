import csv
from pathlib import Path

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------

CSV_PATH = Path(__file__).parent / "past_clears.csv"


# ---------------------------------------------------------
# COMPLETION + LOGISTICS MODEL
# ---------------------------------------------------------

def p_complete(on_time_pay_pct, cancellation_rate, pickup_days):
    """
    Estimated probability that the buyer completes the deal.
    """

    p = (
        on_time_pay_pct
        * (1 - cancellation_rate)
        - min(pickup_days / 40, 0.15)
    )

    return max(0.05, min(0.99, round(p, 3)))


def logistics_cost(pickup_days, distance_km):
    """
    Simple estimated operational/logistics cost.
    """

    return pickup_days * 25 + distance_km * 4


def match_score(
    bid,
    on_time_pay_pct,
    cancellation_rate,
    pickup_days,
    distance_km
):
    """
    Match score:

        bid * P(completion) - logistics cost
    """

    p = p_complete(
        on_time_pay_pct,
        cancellation_rate,
        pickup_days
    )

    cost = logistics_cost(
        pickup_days,
        distance_km
    )

    score = bid * p - cost

    return score, p, cost


# ---------------------------------------------------------
# LOAD CSV
# ---------------------------------------------------------

def load_data():
    rows = []

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            rows.append({
                "device_id": row["device_id"],
                "model": row["model"],
                "grade": row["grade"],
                "buyer_id": row["buyer_id"],
                "bid": int(row["bid"]),
                "on_time_pay_pct": float(row["on_time_pay_pct"]),
                "pickup_days": float(row["pickup_days"]),
                "cancellation_rate": float(row["cancellation_rate"]),
                "distance_km": float(row["distance_km"]),
            })

    return rows


# ---------------------------------------------------------
# REPLAY
# ---------------------------------------------------------

def replay(rows):

    # Group all bids belonging to the same device
    by_device = {}

    for row in rows:
        by_device.setdefault(row["device_id"], []).append(row)

    results = []

    for device_id, bids in by_device.items():

        # Calculate score for every buyer
        for buyer in bids:

            score, p, cost = match_score(
                buyer["bid"],
                buyer["on_time_pay_pct"],
                buyer["cancellation_rate"],
                buyer["pickup_days"],
                buyer["distance_km"]
            )

            buyer["score"] = score
            buyer["p_complete"] = p
            buyer["logistics_cost"] = cost

        # TODAY'S RULE:
        # Pick the buyer with the highest bid
        baseline = max(
            bids,
            key=lambda x: x["bid"]
        )

        # PROPOSED RULE:
        # Pick the buyer with the highest match score
        model = max(
            bids,
            key=lambda x: x["score"]
        )

        results.append({
            "device_id": device_id,
            "model": bids[0]["model"],
            "grade": bids[0]["grade"],

            "baseline_buyer": baseline["buyer_id"],
            "baseline_bid": baseline["bid"],

            "model_buyer": model["buyer_id"],
            "model_bid": model["bid"],
            "model_p": model["p_complete"],
            "model_cost": model["logistics_cost"],
            "model_score": model["score"],

            "changed": (
                model["buyer_id"]
                != baseline["buyer_id"]
            ),
        })

    return results


# ---------------------------------------------------------
# REPORT
# ---------------------------------------------------------

def report(results):

    print("\n" + "=" * 120)
    print("NORTHLADDER MATCHING SCORING REPLAY")
    print("=" * 120)

    for r in results:

        baseline = (
            f"{r['baseline_buyer']} @ "
            f"₹{r['baseline_bid']:,}"
        )

        model = (
            f"{r['model_buyer']} @ "
            f"₹{r['model_bid']:,} | "
            f"P={r['model_p']:.2f} | "
            f"Cost=₹{r['model_cost']:,.0f} | "
            f"Score=₹{r['model_score']:,.0f}"
        )

        print(
            f"{r['device_id']}  "
            f"{r['model']} {r['grade']} | "
            f"Highest bid: {baseline:<25} | "
            f"Model: {model:<55} | "
            f"Changed: {r['changed']}"
        )

    # -----------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------

    n = len(results)

    changed = sum(
        r["changed"]
        for r in results
    )

    baseline_total = sum(
        r["baseline_bid"]
        for r in results
    )

    model_total = sum(
        r["model_bid"]
        for r in results
    )

    baseline_expected_value = sum(
        r["baseline_bid"]
        for r in results
    )

    model_expected_value = sum(
        r["model_bid"] * r["model_p"] - r["model_cost"]
        for r in results
    )

    # Expected value if today's highest-bid buyer
    # had its own completion probability and logistics cost
    baseline_expected_value = 0

    for r in results:

        # Find baseline buyer's metrics again
        baseline_row = next(
            row
            for row in rows_global
            if row["device_id"] == r["device_id"]
            and row["buyer_id"] == r["baseline_buyer"]
        )

        _, baseline_p, baseline_cost = match_score(
            baseline_row["bid"],
            baseline_row["on_time_pay_pct"],
            baseline_row["cancellation_rate"],
            baseline_row["pickup_days"],
            baseline_row["distance_km"]
        )

        baseline_expected_value += (
            baseline_row["bid"] * baseline_p
            - baseline_cost
        )

    print("\n" + "-" * 120)
    print("SUMMARY")
    print("-" * 120)

    print(
        f"Auctions:                    {n}"
    )

    print(
        f"Different buyer selected:    "
        f"{changed}/{n} ({changed / n:.0%})"
    )

    print(
        f"Total bid value:             "
        f"highest-bid={baseline_total:,} | "
        f"model={model_total:,}"
    )

    print(
        f"Expected value:              "
        f"highest-bid=₹{baseline_expected_value:,.0f} | "
        f"model=₹{model_expected_value:,.0f}"
    )

    improvement = (
        (model_expected_value - baseline_expected_value)
        / baseline_expected_value
    )

    print(
        f"Expected value change:       "
        f"{improvement:+.1%}"
    )

    print("\n")
    print(
        "Note: This is a replay on synthetic/made-up data. "
        "The scoring mechanism is illustrative; the resulting "
        "percentage is not evidence of actual NorthLadder performance."
    )


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

if __name__ == "__main__":

    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Could not find {CSV_PATH.name}. "
            f"Make sure it is in the same folder as scoring_replay.py."
        )

    rows_global = load_data()

    results = replay(rows_global)

    report(results)
