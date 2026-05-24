# Start of HEAD
import json
import sys
import math

input_data = json.loads(sys.stdin.read())

map_size = input_data['map_size']
warehouse = [map_size[0] / 2, map_size[1] / 2]
drones = input_data['drones']
deliveries = input_data['deliveries']
no_fly_zones = input_data.get('no_fly_zones', [])
charging_stations = input_data.get('charging_stations', [])
# End of HEAD


# Start of BODY
def solve(warehouse, drones, deliveries, no_fly_zones, charging_stations):

    # ------------------------------------------------------------
    # 1. geometry and time helpers (NFZ-aware)
    # ------------------------------------------------------------
    def dist(a, b):
        return math.hypot(a[0]-b[0], a[1]-b[1])

    def point_in_circle(x, y, cx, cy, r):
        return (x-cx)**2 + (y-cy)**2 <= r**2

    def point_in_rect(x, y, xmin, ymin, xmax, ymax):
        return xmin <= x <= xmax and ymin <= y <= ymax

    def is_nfz_active(nfz, t):
        return nfz['T_start'] <= t <= nfz['T_end']

    def time_until_safe(x, y, t, nfzs):
        dt = 0.0
        for nfz in nfzs:
            inside = False
            if nfz['shape'] == 'circle':
                cx, cy, r = nfz['center'][0], nfz['center'][1], nfz['radius']
                if point_in_circle(x, y, cx, cy, r):
                    inside = True
            else:  # rectangle
                xmin, ymin = nfz['corners'][0]
                xmax, ymax = nfz['corners'][1]
                if point_in_rect(x, y, xmin, ymin, xmax, ymax):
                    inside = True
            if inside and t+dt < nfz['T_end']:
                dt = max(dt, nfz['T_end'] - t)
        return dt if dt >= 0 else None

    def is_point_safe(x, y, t, nfzs):
        for nfz in nfzs:
            if not is_nfz_active(nfz, t):
                continue
            if nfz['shape'] == 'circle':
                if point_in_circle(x, y, nfz['center'][0], nfz['center'][1], nfz['radius']):
                    return False
            else:
                xmin, ymin = nfz['corners'][0]
                xmax, ymax = nfz['corners'][1]
                if point_in_rect(x, y, xmin, ymin, xmax, ymax):
                    return False
        return True

    def line_circle_intersect(ax, ay, bx, by, cx, cy, r):
        dx, dy = bx-ax, by-ay
        fx, fy = ax-cx, ay-cy
        a = dx*dx + dy*dy
        b = 2*(fx*dx + fy*dy)
        c = fx*fx + fy*fy - r*r
        disc = b*b - 4*a*c
        if disc < 0:
            return None
        sqrt_disc = math.sqrt(disc)
        t1 = (-b - sqrt_disc) / (2*a)
        t2 = (-b + sqrt_disc) / (2*a)
        if t1 > t2:
            t1, t2 = t2, t1
        length = math.sqrt(a)
        if t2 < 0 or t1 > length:
            return None
        t_enter = max(0.0, t1)
        t_exit = min(length, t2)
        if t_enter > t_exit:
            return None
        return (t_enter, t_exit)

    def line_rect_intersect(ax, ay, bx, by, xmin, ymin, xmax, ymax):
        dx, dy = bx-ax, by-ay
        p = [-dx, dx, -dy, dy]
        q = [ax-xmin, xmax-ax, ay-ymin, ymax-ay]
        t_enter, t_exit = 0.0, 1.0
        for i in range(4):
            if p[i] == 0:
                if q[i] < 0:
                    return None
            else:
                t = q[i] / p[i]
                if p[i] < 0:
                    if t > t_enter:
                        t_enter = t
                else:
                    if t < t_exit:
                        t_exit = t
        if t_enter > t_exit:
            return None
        length = math.hypot(dx, dy)
        d_enter = t_enter * length
        d_exit = t_exit * length
        return (d_enter, d_exit)

    def can_travel(ax, ay, bx, by, t_depart, nfzs):
        d = math.hypot(bx-ax, by-ay)
        if d == 0:
            if is_point_safe(ax, ay, t_depart, nfzs):
                return (True, t_depart, 0.0, 0.0)
            wait = time_until_safe(ax, ay, t_depart, nfzs)
            if wait is None:
                return (False, None, None, None)
            return (True, t_depart+wait, wait, 0.0)

        max_wait = 0.0
        for nfz in nfzs:
            if nfz['T_end'] < t_depart:
                continue
            if nfz['T_start'] > t_depart + d:
                continue
            if nfz['shape'] == 'circle':
                inter = line_circle_intersect(ax, ay, bx, by, nfz['center'][0], nfz['center'][1], nfz['radius'])
            else:
                xmin, ymin = nfz['corners'][0]
                xmax, ymax = nfz['corners'][1]
                inter = line_rect_intersect(ax, ay, bx, by, xmin, ymin, xmax, ymax)
            if inter is None:
                continue
            d_enter, d_exit = inter
            t_enter = t_depart + d_enter
            t_exit = t_depart + d_exit
            if t_enter < nfz['T_end'] and t_exit > nfz['T_start']:
                wait_needed = max(0.0, nfz['T_end'] - t_enter)
                max_wait = max(max_wait, wait_needed)

        new_t_depart = t_depart + max_wait
        arrival = new_t_depart + d

        if not is_point_safe(bx, by, arrival, nfzs):
            wait_goal = time_until_safe(bx, by, arrival, nfzs)
            if wait_goal is None:
                return (False, None, None, None)
            new_t_depart += wait_goal
            arrival += wait_goal
            max_wait += wait_goal

        if max_wait > 0 and not is_point_safe(ax, ay, t_depart, nfzs):
            return (False, None, None, None)

        total_wait = max_wait
        return (True, arrival, total_wait, d)

    # ------------------------------------------------------------
    # 2. charging station slot booking
    # ------------------------------------------------------------
    station_schedule = {}

    def book_charge(station_coord, t_arrive, duration, drone_id):
        sched = station_schedule.setdefault(station_coord, [])
        station_obj = next((cs for cs in charging_stations
                            if cs['x'] == station_coord[0] and cs['y'] == station_coord[1]), None)
        max_slots = station_obj.get('slots', 1) if station_obj else 1
        t = t_arrive
        changed = True
        while changed:
            changed = False
            for (s, e, _) in sched:
                if e > t and s < t+duration:
                    t = e
                    changed = True
                    break
        sched.append((t, t+duration, drone_id))
        return t

    # ------------------------------------------------------------
    # 3. single trip planner
    # ------------------------------------------------------------
    def plan_trip(sequence, drone, start_time):
        steps = []
        cur_x, cur_y = warehouse[0], warehouse[1]
        cur_t = start_time
        cur_bat = 500.0
        cur_payload = sum(d['weight'] for d in sequence)

        steps.append({'x': cur_x, 'y': cur_y, 't': cur_t,
                      'action': 'PICKUP', 'delivery_ids': [d['id'] for d in sequence]})

        for delivery in sequence:
            tx, ty = delivery['x'], delivery['y']
            ok, arr, wait, d = can_travel(cur_x, cur_y, tx, ty, cur_t, no_fly_zones)
            if not ok:
                return None
            if wait > 0:
                steps.append({'x': cur_x, 'y': cur_y, 't': cur_t, 'action': 'WAIT'})
                cur_t += wait
            energy = d * (1.0 + cur_payload)
            if cur_bat < energy:
                return None
            cur_bat -= energy
            cur_t = arr
            cur_x, cur_y = tx, ty
            if cur_t > delivery['deadline']:
                return None
            steps.append({'x': cur_x, 'y': cur_y, 't': cur_t,
                          'action': 'DELIVER', 'delivery_id': delivery['id']})
            cur_payload -= delivery['weight']

        # RETURN
        ok, arr, wait, d = can_travel(cur_x, cur_y, warehouse[0], warehouse[1], cur_t, no_fly_zones)
        if ok and cur_bat >= d:
            if wait > 0:
                steps.append({'x': cur_x, 'y': cur_y, 't': cur_t, 'action': 'WAIT'})
                cur_t += wait
            cur_t = arr
            steps.append({'x': warehouse[0], 'y': warehouse[1], 't': cur_t, 'action': 'RETURN'})
            return steps, cur_t

        # try charging stations
        best_finish = float('inf')
        best_steps = None
        for st in charging_stations:
            sx, sy = st['x'], st['y']
            ok1, arr1, w1, d1 = can_travel(cur_x, cur_y, sx, sy, cur_t, no_fly_zones)
            if not ok1 or cur_bat < d1:
                continue
            bat_after = cur_bat - d1
            ok2, arr2, w2, d2 = can_travel(sx, sy, warehouse[0], warehouse[1], arr1, no_fly_zones)
            if not ok2:
                continue
            need = max(0.0, d2 - bat_after)
            charge_dur = math.ceil(need / 2.0)
            charge_start = book_charge((sx, sy), arr1, charge_dur, drone['id'])

            tmp = list(steps)
            t_now = cur_t
            if w1 > 0:
                tmp.append({'x': cur_x, 'y': cur_y, 't': t_now, 'action': 'WAIT'})
                t_now += w1
            tmp.append({'x': sx, 'y': sy, 't': arr1, 'action': 'WAYPOINT'})
            t_now = arr1
            if charge_start > t_now:
                tmp.append({'x': sx, 'y': sy, 't': t_now, 'action': 'WAIT'})
                t_now = charge_start
            tmp.append({'x': sx, 'y': sy, 't': t_now, 'action': 'CHARGE'})
            t_now += charge_dur
            tmp.append({'x': sx, 'y': sy, 't': t_now, 'action': 'CHARGE_COMPLETE'})
            ok2b, arr2b, w2b, _ = can_travel(sx, sy, warehouse[0], warehouse[1], t_now, no_fly_zones)
            if not ok2b:
                continue
            if w2b > 0:
                tmp.append({'x': sx, 'y': sy, 't': t_now, 'action': 'WAIT'})
                t_now += w2b
            t_now = arr2b
            tmp.append({'x': warehouse[0], 'y': warehouse[1], 't': t_now, 'action': 'RETURN'})
            if t_now < best_finish:
                best_finish = t_now
                best_steps = tmp

        if best_steps is None:
            return None
        return best_steps, best_finish

    # ------------------------------------------------------------
    # 4. multi-trip scheduler
    # ------------------------------------------------------------
    drone_pool = [(0.0, d) for d in sorted(drones, key=lambda x: x['max_payload'], reverse=True)]
    unassigned = sorted(deliveries, key=lambda d: d['deadline'])
    manifest = []

    while unassigned and drone_pool:
        drone_pool.sort(key=lambda x: x[0])
        avail_time, drone = drone_pool.pop(0)

        trip = []
        trip_weight = 0.0
        for deliv in unassigned[:]:
            if trip_weight + deliv['weight'] > drone['max_payload']:
                continue
            new_trip = trip + [deliv]
            sorted_trip = sorted(new_trip, key=lambda x: x['weight'], reverse=True)
            plan = plan_trip(sorted_trip, drone, avail_time)
            if plan is not None:
                trip = new_trip
                trip_weight += deliv['weight']
                unassigned.remove(deliv)

        if not trip:
            continue

        final_sorted = sorted(trip, key=lambda x: x['weight'], reverse=True)
        plan = plan_trip(final_sorted, drone, avail_time)
        if plan is None:
            unassigned.extend(trip)
            continue

        steps, fin_time = plan
        manifest.append({'drone_id': drone['id'], 'path': steps})
        drone_pool.append((fin_time, drone))

    return manifest
# End of BODY


# Start of TAIL
result = solve(warehouse, drones, deliveries, no_fly_zones, charging_stations)
output = {"flight_manifest": result}
print(json.dumps(output))
# End of TAIL
