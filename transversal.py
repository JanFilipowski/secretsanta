#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import argparse
import random
from collections import deque

# =========================================
# GLOBAL SETTINGS – TWEAKABLE KNOBS
# =========================================

# How many attempts to find a valid matching
NUM_REPETITIONS = 50

# Randomness seed:
#   None  -> different draw every time
#   42 etc. -> repeatable draw (useful for tests)
RANDOM_SEED = None

# When True, stop at the first valid matching
# When False, collect multiple matchings and pick one at the end
STOP_ON_FIRST = True


# ============================
# Loading and validating data
# ============================

def load_people(path):
    with open(path, "r", encoding="utf-8") as f:
        people = json.load(f)

    # Add full_name for convenience
    for p in people:
        p["full_name"] = f'{p["first_name"]} {p["last_name"]}'
    return people


def validate_people(people):
    # Enforce unique full names
    names = [p["full_name"] for p in people]
    if len(names) != len(set(names)):
        raise ValueError("people.json contains duplicate full names (full_name).")

    # Mapping: full_name -> person
    people_by_name = {p["full_name"]: p for p in people}

    # Validate allowed lists: every entry must exist and cannot reference self
    for p in people:
        full_name = p["full_name"]
        for target in p.get("allowed", []):
            if target not in people_by_name:
                raise ValueError(
                    f'Person "{full_name}" lists a non-existing allowed recipient: "{target}".'
                )
            if target == full_name:
                raise ValueError(
                    f'Person "{full_name}" lists themselves in allowed, which is unsupported.'
                )

    return people_by_name


# ============================
# Hopcroft–Karp algorithm
# ============================

def hopcroft_karp_bipartite_matching(allowed, U_order=None):
    """
    allowed: dict giver_full_name -> list[receiver_full_name]
    U_order: opcjonalna kolejność przechodzenia dających

        Returns:
            dict giver -> receiver (perfect matching)
            or None if no matching exists.
    """
    if U_order is None:
        U = list(allowed.keys())
    else:
        U = list(U_order)

    # V = union of all allowed receivers
    Vset = set()
    for vs in allowed.values():
        Vset.update(vs)
    V = list(Vset)

    pair_U = {u: None for u in U}
    pair_V = {v: None for v in V}
    dist = {}
    NIL = None

    def bfs():
        q = deque()
        for u in U:
            if pair_U[u] is NIL:
                dist[u] = 0
                q.append(u)
            else:
                dist[u] = float("inf")
        dist[NIL] = float("inf")

        while q:
            u = q.popleft()
            if dist[u] < dist[NIL]:
                for v in allowed[u]:
                    pu = pair_V[v]
                    if dist.get(pu, float("inf")) == float("inf"):
                        dist[pu] = dist[u] + 1
                        q.append(pu)
        return dist[NIL] != float("inf")

    def dfs(u):
        if u is not NIL:
            for v in allowed[u]:
                pu = pair_V[v]
                if dist.get(pu, float("inf")) == dist[u] + 1:
                    if dfs(pu):
                        pair_U[u] = v
                        pair_V[v] = u
                        return True
            dist[u] = float("inf")
            return False
        return True

    matching = 0
    while bfs():
        for u in U:
            if pair_U[u] is NIL:
                if dfs(u):
                    matching += 1

    if matching == len(U):
        return pair_U
    else:
        return None


def random_secret_santa_matching(people_by_name):
    """
    people_by_name: dict full_name -> person_dict

    Buduje słownik allowed i próbuje znaleźć losowe dopasowanie.
    Używa globalnych:
      - NUM_REPETITIONS
      - RANDOM_SEED
      - STOP_ON_FIRST
    """
    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)

    givers = list(people_by_name.keys())

    # Build allowed: if someone has no explicit list,
    # they can draw anyone except themselves.
    allowed_base = {}
    all_names = set(givers)
    for name, person in people_by_name.items():
        if "allowed" in person and person["allowed"]:
            allowed_base[name] = list(person["allowed"])
        else:
            # default: everyone except themselves
            allowed_base[name] = list(all_names - {name})

    matchings = []
    seen = set()

    for _ in range(NUM_REPETITIONS):
        # Copy and shuffle the allowed lists
        allowed = {}
        for g in givers:
            vs = list(allowed_base[g])
            random.shuffle(vs)
            allowed[g] = vs

        # Random order of givers
        U_order = list(givers)
        random.shuffle(U_order)

        m = hopcroft_karp_bipartite_matching(allowed, U_order)
        if m is not None:
            key = tuple(sorted(m.items()))
            if key not in seen:
                seen.add(key)
                matchings.append(m)
            if STOP_ON_FIRST:
                break

    if not matchings:
        raise ValueError("No perfect matching found under the current constraints.")

    return random.choice(matchings)


def save_results(assignments, path):
    """
    Writes assignments to JSON in the shape:
    {
      "assignments": {
        "Imię Nazwisko": "Inne Imię Nazwisko",
        ...
      }
    }
    """
    data = {"assignments": assignments}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================
# CLI
# ============================

def main():
    parser = argparse.ArgumentParser(
        description="Constrained Secret Santa – generate assignments into results.json."
    )
    parser.add_argument(
        "--people",
        default="people.json",
        help="Path to people.json (default: people.json).",
    )
    parser.add_argument(
        "--results",
        default="results.json",
        help="Path to the output results.json (default: results.json).",
    )

    args = parser.parse_args()

    try:
        people = load_people(args.people)
        people_by_name = validate_people(people)

        print(f"Loaded {len(people_by_name)} participants.")
        print("Searching for a constrained Secret Santa matching...")

        assignments = random_secret_santa_matching(people_by_name)

        # NOTE: never print assignments to the console!
        save_results(assignments, args.results)
        print(f"Matching saved to: {args.results}")
        print("The operator never sees who drew whom. ✅")

    except Exception as e:
        # Surface the error without revealing assignments (which we never know anyway)
        print(f"Error while generating assignments: {e}")


if __name__ == "__main__":
    main()
