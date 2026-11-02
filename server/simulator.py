"""Stand-in for the ESP32 (no hardware needed): posts telemetry once per second and obeys breaker commands."""
import random, time, requests, sys
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
state, ops, trips = "closed", 0, 0
while True:
    load = random.gauss(5.0, 0.4)
    if random.random() < 0.01: load = random.uniform(16, 22)      # occasional overload spike
    current = load if state == "closed" else 0.0
    if current > 15:                                               # protection: trip open on overload
        state, ops, trips = "open", ops + 1, trips + 1
        current = 0.0
    voltage = random.gauss(230, 1.5)
    r = requests.post(f"{URL}/api/telemetry", json=dict(current=round(current, 2), voltage=round(voltage, 1),
                      state=state, op_count=ops, trips=trips), timeout=3).json()
    if r.get("command") == "open" and state == "closed": state, ops = "open", ops + 1
    elif r.get("command") == "close" and state == "open": state, ops = "closed", ops + 1
    time.sleep(1)
