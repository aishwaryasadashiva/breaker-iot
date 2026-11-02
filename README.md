# Smart Circuit Breaker Endurance Monitoring & IoT Dashboard

An embedded-software IoT project: ESP32 firmware reads current and voltage, drives a relay that stands in
for a breaker contact, trips on overload and counts operations. It streams real-time data over Wi-Fi to a
FastAPI + SQLite server with a live web dashboard and an automated endurance (open/close cycle) test.

## Architecture
```
ESP32 (firmware/breaker_monitor.ino) --Wi-Fi, HTTP/JSON--> FastAPI server (server/app.py, SQLite)
                                                           --> live dashboard (server/static/index.html)
```
The server also sends open/close commands back to the ESP32 in its reply to each telemetry post.

## Features
- Live current and voltage chart, breaker state, operation count and overload-trip count
- Manual open/close from the dashboard
- Automated endurance test: configurable number of cycles and interval (one cycle = open then close);
  the test ends with the breaker closed
- Event log (trips, test start/end, manual commands) and CSV export of all telemetry

## Run it (no hardware needed)
```
cd server
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 -m uvicorn app:app --port 8000
```
In a second terminal (activate the same venv):
```
cd server
python3 simulator.py              # stands in for the ESP32
```
Open http://localhost:8000. Note: the simulator trips the breaker occasionally; use "Close breaker" to reset.

## Run it with the ESP32
Edit the Wi-Fi name, password and `SERVER` (your PC's IP address) in `firmware/breaker_monitor.ino`, then flash
it with the Arduino IDE (ESP32 board package). `USE_SENSORS` is `false` by default (simulated readings); set it
to `true` once a current sensor (e.g. ACS712) and a voltage sensor are wired. A relay on GPIO 26 stands in for the
breaker contact.

## Status
- Server, dashboard and endurance test: verified end to end using the simulator.
- ESP32 firmware: written for the Arduino framework; not yet tested on a physical board or with real sensors.
- The relay is a stand-in for a breaker; this is not a test rig for a real circuit breaker.
