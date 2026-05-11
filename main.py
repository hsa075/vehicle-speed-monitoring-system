# ============================================================
#  IoT Vehicle Speed Monitor
#  Platform  : Raspberry Pi Pico W (Wokwi)
#  Input     : 2x Pushbuttons (PB1 = start, PB2 = stop)
#  Cloud     : ThingSpeak via WiFi (urequests)
#  Language  : MicroPython
# ============================================================

import network
import urequests
import utime
from machine import Pin

# ── Configuration ────────────────────────────────────────────
WIFI_SSID     = "Wokwi-GUEST"
WIFI_PASSWORD = ""
TS_API_KEY    = "WP8O6WZFCP9CW1BB"   # ← update this
TS_CHANNEL_ID = "3366731"
TS_URL        = "http://api.thingspeak.com/update"

DISTANCE_CM   = 20.0
DISTANCE_M    = DISTANCE_CM / 100.0

# ── GPIO Pins ────────────────────────────────────────────────
pb1 = Pin(17, Pin.IN, Pin.PULL_UP)   # PB1 → GP17 (start timing)
pb2 = Pin(22, Pin.IN, Pin.PULL_UP)   # PB2 → GP22 (stop timing)
led = Pin("LED", Pin.OUT)            # Onboard LED

# ── State ────────────────────────────────────────────────────
t1             = None
waiting        = False
last_upload    = 0
upload_count   = 0

# ============================================================
#  HELPERS
# ============================================================

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    print("Connecting to WiFi", end="")
    timeout = 15
    while not wlan.isconnected() and timeout > 0:
        print(".", end="")
        utime.sleep(1)
        timeout -= 1
    if wlan.isconnected():
        print("\nWiFi OK →", wlan.ifconfig()[0])
        return True
    else:
        print("\nWiFi FAILED — offline mode")
        return False


def compute_speed(t_start, t_end):
    elapsed_ms = utime.ticks_diff(t_end, t_start)
    if elapsed_ms <= 0:
        return 0.0
    return round((DISTANCE_M / (elapsed_ms / 1000.0)) * 3.6, 2)


def upload_speed(speed_kmh):
    global last_upload, upload_count

    # ThingSpeak free tier: min 15 seconds between uploads
    now = utime.time()
    gap = now - last_upload
    if gap < 15 and last_upload != 0:
        print(f"[ThingSpeak] Waiting {15 - gap}s before next upload...")
        utime.sleep(15 - gap)

    try:
        url = (
            f"http://api.thingspeak.com/update"
            f"?api_key={TS_API_KEY}"
            f"&field1={speed_kmh}"
        )
        print(f"[ThingSpeak] Sending → {url}")
        r = urequests.get(url, timeout=10)

        # ThingSpeak returns the entry ID (1, 2, 3...) on success
        # Returns 0 if the update was rejected
        entry_id = r.text.strip()
        r.close()

        if entry_id != "0" and entry_id != "":
            upload_count += 1
            last_upload = utime.time()
            print(f"[ThingSpeak] ✓ OK — Entry ID: {entry_id}  "
                  f"(total uploads: {upload_count})")
            print(f"[ThingSpeak] View → "
                  f"https://thingspeak.com/channels/{TS_CHANNEL_ID}")
        else:
            print("[ThingSpeak] ✗ Rejected — entry_id=0")
            print("  → Check: API key correct? Channel field1 enabled?")

    except Exception as e:
        print(f"[ThingSpeak] ✗ Error → {e}")


def blink(times=1):
    for _ in range(times):
        led.on();  utime.sleep_ms(80)
        led.off(); utime.sleep_ms(80)


# ============================================================
#  MAIN
# ============================================================

print("=" * 45)
print("  IoT Vehicle Speed Monitor")
print("  Raspberry Pi Pico W — Wokwi Simulation")
print(f"  Sensor gap   : {DISTANCE_CM} cm")
print(f"  ThingSpeak   : channel {TS_CHANNEL_ID}")
print("  Keyboard     : Q = PB1 (Start) | E = PB2 (Stop)")
print("=" * 45)

wifi_ok = connect_wifi()
if not wifi_ok:
    print("WARNING: No WiFi — speed computed but not uploaded")

print("\nReady → press Q (PB1) to start timing...\n")

prev_pb1 = 1
prev_pb2 = 1

while True:
    p1 = pb1.value()
    p2 = pb2.value()

    # ── PB1 pressed → start timer ────────────────────────────
    if prev_pb1 == 1 and p1 == 0:
        if not waiting:
            t1      = utime.ticks_ms()
            waiting = True
            blink(1)
            print("● PB1 pressed — timer started")
            print("  Now press E (PB2) to stop...")

    # ── PB2 pressed → stop timer, compute, upload ────────────
    if prev_pb2 == 1 and p2 == 0:
        if waiting and t1 is not None:
            t2      = utime.ticks_ms()
            elapsed = utime.ticks_diff(t2, t1)
            speed   = compute_speed(t1, t2)
            waiting = False
            t1      = None

            blink(2)
            print(f"● PB2 pressed — timer stopped")
            print(f"  Elapsed  : {elapsed} ms")
            print(f"  Distance : {DISTANCE_CM} cm")
            print(f"━━ Speed   : {speed} km/h")

            if wifi_ok:
                upload_speed(speed)
            else:
                print("[ThingSpeak] Skipped — no WiFi")

            print("\nReady → press Q (PB1) to start timing...\n")

        elif not waiting:
            print("⚠ Press PB1 first to start the timer!")

    prev_pb1 = p1
    prev_pb2 = p2
    utime.sleep_ms(10)