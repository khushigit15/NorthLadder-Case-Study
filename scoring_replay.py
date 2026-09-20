# NorthLadder - quick scoring backtest
# match_score = bid * P(completion) - logistics_cost
# builds a fake set of past auctions and checks this against just
# picking whoever bid highest (today's rule)

import csv, random
from pathlib import Path

random.seed(7)

MODELS = [
    ("iPhone 14 128GB", "B"), ("iPhone 13 128GB", "A"), ("MacBook Air M1", "A"),
    ("Galaxy S23", "B"), ("iPad 9th gen", "C"), ("Galaxy Tab S9", "C"), ("Pixel 7", "B"),
]

# buyer_id, on_time_pay_pct, pickup_days, cancel_rate, distance_km
BUYERS = [
    ("BUYER_A", 0.96, 0.5, 0.02, 4),
    ("BUYER_B", 0.78, 5.0, 0.11, 38),
    ("BUYER_C", 0.97, 0.5, 0.01, 6),
    ("BUYER_D", 0.65, 6.5, 0.18, 55),
    ("BUYER_E", 0.90, 1.5, 0.05, 12),
    ("BUYER_F", 0.55, 8.0, 0.25, 70),  # new / unreliable
]

CSV_PATH = Path(__file__).parent / "past_clears.csv"


def make_past_clears(n=25):
    rows = []
    for i in range(1, n + 1):
        model, grade = random.choice(MODELS)
        base = random.randint(8000, 45000)
        for buyer_id, on_time, pickup, cancel, dist in random.sample(BUYERS, random.randint(2, 4)):
            noise = random.uniform(-0.06, 0.06)
            push = 0.05 if on_time < 0.8 else 0  # flaky buyers tend to overbid to win
            bid = int(round(base * (1 + noise + push), -2))
            rows.append(dict(device_id=f"D{i:03d}", model=model, grade=grade, buyer_id=buyer_id,
                              bid=bid, on_time=on_time, pickup_days=pickup, cancel_rate=cancel, distance_km=dist))
    return rows


def p_complete(on_time, cancel_rate, pickup_days):
    p = on_time * (1 - cancel_rate) - min(pickup_days / 40, 0.15)
    return max(0.05, min(0.99, round(p, 3)))


def logistics_cost(pickup_days, distance_km):
    return pickup_days * 25 + distance_km * 4


def score(bid, on_time, cancel_rate, pickup_days, distance_km):
    p = p_complete(on_time, cancel_rate, pickup_days)
    cost = logistics_cost(pickup_days, distance_km)
    return bid * p - cost, p


def did_it_complete(p):
    return random.random() < p


def replay(rows):
    by_device = {}
    for r in rows:
        by_device.setdefault(r["device_id"], []).append(r)

    out = []
    for device_id, bids in by_device.items():
        for b in bids:
            b["score"], b["p"] = score(b["bid"], b["on_time"], b["cancel_rate"], b["pickup_days"], b["distance_km"])

        baseline = max(bids, key=lambda b: b["bid"])
        model = max(bids, key=lambda b: b["score"])

        baseline_ok = did_it_complete(baseline["p"])
        # if both rules land on the same buyer, don't re-roll the dice
        model_ok = baseline_ok if model["buyer_id"] == baseline["buyer_id"] else did_it_complete(model["p"])

        out.append({
            "device_id": device_id, "model": bids[0]["model"], "grade": bids[0]["grade"],
            "baseline_buyer": baseline["buyer_id"], "baseline_bid": baseline["bid"], "baseline_ok": baseline_ok,
            "model_buyer": model["buyer_id"], "model_bid": model["bid"], "model_p": model["p"], "model_ok": model_ok,
            "changed": model["buyer_id"] != baseline["buyer_id"],
        })
    return out


def report(results):
    for r in results:
        b = f"{r['baseline_buyer']} @ {r['baseline_bid']} ({'ok' if r['baseline_ok'] else 'fail'})"
        m = f"{r['model_buyer']} @ {r['model_bid']}, p={r['model_p']:.2f} ({'ok' if r['model_ok'] else 'fail'})"
        print(f"{r['device_id']}  {r['model']} {r['grade']:<3} | baseline: {b:<28} | model: {m:<32} | changed: {r['changed']}")

    n = len(results)
    changed = sum(r["changed"] for r in results)
    base_val = sum(r["baseline_bid"] for r in results if r["baseline_ok"])
    model_val = sum(r["model_bid"] for r in results if r["model_ok"])
    base_fails = sum(1 for r in results if not r["baseline_ok"])
    model_fails = sum(1 for r in results if not r["model_ok"])

    print()
    print(f"{n} auctions, model picked a different buyer on {changed} of them ({changed/n:.0%})")
    print(f"realized value   baseline={base_val:,}   model={model_val:,}   ({(model_val-base_val)/base_val:+.0%})")
    print(f"failed pickups   baseline={base_fails}/{n}   model={model_fails}/{n}")
    print("\n(numbers come from simulated outcomes on made-up data - the mechanism is real, the % isn't)")


if __name__ == "__main__":
    rows = make_past_clears()
    with open(CSV_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {CSV_PATH.name}\n")
    report(replay(rows))
