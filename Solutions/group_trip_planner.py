import sys

def solve():
    data = sys.stdin.read().split()
    it = iter(data)
    N = int(next(it))
    D = int(next(it))
    H = int(next(it))

    users = []
    for _ in range(N):
        name = next(it)
        budget = int(next(it))
        energy = int(next(it))
        k = int(next(it))
        tags = set(next(it) for _ in range(k))
        users.append({'name': name, 'budget': budget,
                      'energy': energy, 'tags': tags})

    A = int(next(it))
    activities = []
    act_id_to_idx = {}
    act_ids = []
    for idx in range(A):
        aid = int(next(it))
        aname = next(it)
        cost = int(next(it))
        dur = int(next(it))
        ec = int(next(it))
        tag = next(it)
        activities.append({'id': aid, 'name': aname, 'cost': cost,
                           'duration': dur, 'energy': ec, 'tag': tag})
        act_id_to_idx[aid] = idx
        act_ids.append(aid)

    E = int(next(it))
    events_str = []
    parsed_events = []
    for _ in range(E):
        etype = next(it)
        if etype == 'DROP':
            day = next(it)
            user = next(it)
            events_str.append(f"DROP {day} {user}")
            parsed_events.append({'type': 'DROP', 'day': int(day), 'user': user})
        elif etype == 'WEATHER':
            day = next(it)
            tag = next(it)
            events_str.append(f"WEATHER {day} {tag}")
            parsed_events.append({'type': 'WEATHER', 'day': int(day), 'tag': tag})
        elif etype == 'FATIGUE':
            day = next(it)
            user = next(it)
            ne = next(it)
            events_str.append(f"FATIGUE {day} {user} {ne}")
            parsed_events.append({'type': 'FATIGUE', 'day': int(day),
                                  'user': user, 'energy': int(ne)})
        elif etype == 'BUDGET':
            day = next(it)
            user = next(it)
            nb = next(it)
            events_str.append(f"BUDGET {day} {user} {nb}")
            parsed_events.append({'type': 'BUDGET', 'day': int(day),
                                  'user': user, 'budget': int(nb)})

    act_cost = [a['cost'] for a in activities]
    act_dur  = [a['duration'] for a in activities]
    act_energy = [a['energy'] for a in activities]
    act_tag  = [a['tag'] for a in activities]

    def get_active_names(day, events_applied):
        names = {u['name'] for u in users}
        for e in events_applied:
            if e['type'] == 'DROP' and e['day'] <= day:
                names.discard(e['user'])
        return names

    def best_subset_for_day(day, used_mask, events_applied):
        active_names = get_active_names(day, events_applied)
        if not active_names:
            return [], 0, 0

        budgets = {}
        energies = {}
        for u in users:
            if u['name'] not in active_names:
                continue
            bud = u['budget']
            eng = u['energy']
            for e in events_applied:
                if e['type'] == 'BUDGET' and e['user'] == u['name'] and e['day'] <= day:
                    bud = e['budget']
                if e['type'] == 'FATIGUE' and e['user'] == u['name'] and e['day'] <= day:
                    eng = e['energy']
            budgets[u['name']] = bud
            energies[u['name']] = eng

        min_budget = min(budgets.values())
        min_energy = min(energies.values())

        blocked_tags = {e['tag'] for e in events_applied
                        if e['type'] == 'WEATHER' and e['day'] == day}

        # Build list of eligible activities with their contribution
        elig = []
        for aid in act_ids:
            idx = act_id_to_idx[aid]
            if used_mask & (1 << idx):
                continue
            if activities[idx]['tag'] in blocked_tags:
                continue
            sat_val = sum(1 for u in users if u['name'] in active_names and activities[idx]['tag'] in u['tags'])
            elig.append((aid, activities[idx]['cost'], activities[idx]['duration'],
                         activities[idx]['energy'], sat_val))

        if not elig:
            return [], 0, 0

        # Sort by cost (heuristic for earlier pruning)
        elig.sort(key=lambda x: x[1])
        k = len(elig)

        best = None  # (-sat, cost, sorted_ids)

        # Use an iterative DFS stack to avoid recursion depth issues
        # stack entries: (pos, cur_cost, cur_dur, cur_energy, cur_sat, cur_ids)
        stack = [(0, 0, 0, 0, 0, [])]
        while stack:
            pos, cur_cost, cur_dur, cur_energy, cur_sat, cur_ids = stack.pop()
            if pos == k:
                # Leaf: evaluate the subset (including empty)
                key = (-cur_sat, cur_cost, sorted(cur_ids))
                if best is None or key < best:
                    best = key
                continue

            # Prune if already over any limit
            if cur_cost > min_budget or cur_dur > H or cur_energy > min_energy:
                continue

            # 1) Skip branch
            stack.append((pos + 1, cur_cost, cur_dur, cur_energy, cur_sat, cur_ids))

            # 2) Include branch
            a = elig[pos]
            new_cost = cur_cost + a[1]
            new_dur = cur_dur + a[2]
            new_energy = cur_energy + a[3]
            new_sat = cur_sat + a[4]
            if new_cost <= min_budget and new_dur <= H and new_energy <= min_energy:
                stack.append((pos + 1, new_cost, new_dur, new_energy, new_sat, cur_ids + [a[0]]))

        if best is None:
            return [], 0, 0
        best_sat = -best[0]
        best_cost = best[1]
        best_ids = best[2]
        return best_ids, best_cost, best_sat

    def fmt_day(day, ids, cost, sat):
        if not ids:
            return f"Day {day}: REST | cost=0 satisfaction=0"
        return f"Day {day}: {' '.join(str(i) for i in sorted(ids))} | cost={cost} satisfaction={sat}"

    lines = ["=== PLAN ==="]
    used_mask = 0
    day_plans = [None] * (D + 1)

    for day in range(1, D + 1):
        ids, cost, sat = best_subset_for_day(day, used_mask, [])
        day_plans[day] = (ids, cost, sat)
        lines.append(fmt_day(day, ids, cost, sat))
        for aid in ids:
            used_mask |= (1 << act_id_to_idx[aid])

    for i, (ev_str, ev_parsed) in enumerate(zip(events_str, parsed_events), 1):
        lines.append(f"=== EVENT {i}: {ev_str} ===")
        event_day = int(ev_str.split()[1])

        used_mask = 0
        for d in range(1, event_day):
            for aid in day_plans[d][0]:
                used_mask |= (1 << act_id_to_idx[aid])

        for d in range(event_day, D + 1):
            ids, cost, sat = best_subset_for_day(d, used_mask, parsed_events[:i])
            day_plans[d] = (ids, cost, sat)
            lines.append(fmt_day(d, ids, cost, sat))
            for aid in ids:
                used_mask |= (1 << act_id_to_idx[aid])

    sys.stdout.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    solve()
