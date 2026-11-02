"""Smart Breaker monitoring server: receives telemetry from the ESP32 over Wi-Fi (HTTP),
stores it in SQLite, serves a live dashboard, and runs automated endurance tests."""
import csv, io, sqlite3, time
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

DB = Path(__file__).with_name("breaker.db")
app = FastAPI(title="Smart Breaker Monitor")

def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

with db() as c:
    c.execute("""CREATE TABLE IF NOT EXISTS telemetry(
        id INTEGER PRIMARY KEY, ts REAL, current REAL, voltage REAL,
        state TEXT, op_count INTEGER, trips INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY, ts REAL, kind TEXT, detail TEXT)""")

class Telemetry(BaseModel):
    current: float      # amps
    voltage: float      # volts
    state: str          # "closed" | "open"
    op_count: int       # breaker operations since boot
    trips: int          # overload trips since boot

class Command(BaseModel):
    state: str          # "open" | "close"

class EnduranceStart(BaseModel):
    cycles: int = 20
    interval_s: float = 2.0

pending = {"cmd": None}
test = {"running": False, "cycles": 0, "done": 0, "interval": 2.0, "last": 0.0, "started": 0.0, "opened": False}

def log_event(kind, detail=""):
    with db() as c:
        c.execute("INSERT INTO events(ts,kind,detail) VALUES(?,?,?)", (time.time(), kind, detail))

@app.post("/api/telemetry")
def post_telemetry(t: Telemetry):
    now = time.time()
    with db() as c:
        prev = c.execute("SELECT trips, current FROM telemetry ORDER BY id DESC LIMIT 1").fetchone()
        c.execute("INSERT INTO telemetry(ts,current,voltage,state,op_count,trips) VALUES(?,?,?,?,?,?)",
                  (now, t.current, t.voltage, t.state, t.op_count, t.trips))
    if prev and t.trips > prev["trips"]:
        log_event("trip", f"overload trip (last reading {prev['current']:.2f} A)")
    # endurance test: toggle the breaker every interval; one cycle = open then close.
    # The test ends right after the last close, so the breaker is left closed.
    if test["running"] and now - test["last"] >= test["interval"]:
        pending["cmd"] = "open" if t.state == "closed" else "close"
        test["last"] = now
        if pending["cmd"] == "open":
            test["opened"] = True
        elif test["opened"]:
            test["opened"] = False
            test["done"] += 1
            if test["done"] >= test["cycles"]:
                test["running"] = False
                log_event("endurance_end", f"{test['done']} cycles in {now - test['started']:.0f}s")
    cmd, pending["cmd"] = pending["cmd"], None
    return {"command": cmd}

@app.get("/api/latest")
def latest():
    with db() as c:
        r = c.execute("SELECT * FROM telemetry ORDER BY id DESC LIMIT 1").fetchone()
    return dict(r) if r else {}

@app.get("/api/history")
def history(limit: int = 120):
    with db() as c:
        rows = c.execute("SELECT ts,current,voltage,state,op_count,trips FROM telemetry ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in reversed(rows)]

@app.post("/api/command")
def command(c: Command):
    pending["cmd"] = c.state
    log_event("manual_command", c.state)
    return {"queued": c.state}

@app.post("/api/endurance/start")
def endurance_start(p: EnduranceStart):
    test.update(running=True, cycles=max(1, p.cycles), done=0, interval=max(1.0, p.interval_s), last=0.0,
                started=time.time(), opened=False)
    log_event("endurance_start", f"{p.cycles} cycles, {p.interval_s}s interval")
    return {"started": True}

@app.post("/api/endurance/stop")
def endurance_stop():
    test["running"] = False
    log_event("endurance_stop", f"stopped after {test['done']} cycles")
    return {"stopped": True}

@app.get("/api/endurance")
def endurance_status():
    return {k: test[k] for k in ("running", "cycles", "done", "interval")}

@app.get("/api/events")
def events(limit: int = 50):
    with db() as c:
        rows = c.execute("SELECT ts,kind,detail FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]

@app.get("/api/export.csv")
def export_csv():
    cols = ["ts", "current", "voltage", "state", "op_count", "trips"]
    with db() as c:
        rows = [dict(r) for r in c.execute(f"SELECT {','.join(cols)} FROM telemetry ORDER BY id").fetchall()]
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(["timestamp", "current_A", "voltage_V", "state", "op_count", "trips"])
    for r in rows:
        w.writerow([r[k] for k in cols])
    return Response(out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=breaker_telemetry.csv"})

app.mount("/static", StaticFiles(directory=Path(__file__).with_name("static")), name="static")

@app.get("/")
def index():
    return FileResponse(Path(__file__).with_name("static") / "index.html")
