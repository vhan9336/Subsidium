// Second Opinion rig: ULTRASONIC ONLY (no motor).
// HC-SR04: VCC -> 5V, GND -> GND, Trig -> D7, Echo -> D8.
//
// Talks to the Python engine exactly like the old rig.ino did:
//   Arduino -> laptop, 20 Hz:   R,<millis>,<range_mm or -1>,<steps>
//   Laptop  -> Arduino, 1 char: d = descend, u = up, s = stop, z = zero
// There is no motor, so <steps> is always 0. The d/u/s/z commands are accepted so the
// Python side works unchanged; they only set a flag that is reported in '#' lines.
// Lines starting with '#' are for humans; Python ignores them.
//
// ---------- TESTING BY HAND (Serial Monitor, 115200 baud) ----------
//   ?   status
//   p   toggle range in plain words (cm), 3x per second. Wave your hand under the sensor.
//   t   self-test: 20 readings, reports how many echoed and the spread

const int TRIG_PIN = 7;
const int ECHO_PIN = 8;
const unsigned long PERIOD_MS = 50;       // 20 Hz telemetry
const unsigned long ECHO_TIMEOUT_US = 12000UL;   // ~2 m max range; keeps the loop fast

long lastRange = -1;
bool talk = false;
char mode = 's';                          // last motion command from Python (d/u/s), for status only
unsigned long lastPing = 0, lastTalk = 0;

long readRangeMm() {
  digitalWrite(TRIG_PIN, LOW);  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long us = pulseIn(ECHO_PIN, HIGH, ECHO_TIMEOUT_US);
  if (us == 0) return -1;                 // no echo
  return (long)(us * 0.1715);             // mm: speed of sound 343 m/s, round trip
}

void status() {
  Serial.print(F("# ultrasonic rig | range mm: ")); Serial.print(lastRange);
  Serial.print(F(" | mode: ")); Serial.print(mode);
  Serial.println(F(" | commands: ? p t (Python: d u s z)"));
}

void selfTest() {
  Serial.println(F("# --- self-test: 20 readings ---"));
  int good = 0; long lo = 100000, hi = -1;
  for (int i = 0; i < 20; i++) {
    long r = readRangeMm();
    if (r > 0) { good++; lo = min(lo, r); hi = max(hi, r); }
    delay(60);                            // HC-SR04 wants ~60 ms between pings
  }
  Serial.print(F("# echoes: ")); Serial.print(good); Serial.println(F("/20"));
  if (good > 0) {
    Serial.print(F("# min ")); Serial.print(lo); Serial.print(F(" mm, max ")); Serial.print(hi);
    Serial.print(F(" mm, spread ")); Serial.print(hi - lo); Serial.println(F(" mm (hold still: should be < 5)"));
  }
  Serial.println(good >= 18 ? F("# sensor OK")
                            : F("# sensor PROBLEM: check VCC/GND, Trig->D7, Echo->D8, aim at a flat surface 3-200 cm away"));
}

void handle(char c) {
  switch (c) {
    case 'd': case 'u': case 's': mode = c; break;      // from Python: no motor, just remember it
    case 'z': break;                                     // from Python: nothing to zero
    case '?': status(); break;
    case 'p': talk = !talk; Serial.println(talk ? F("# range printing ON") : F("# range printing OFF")); break;
    case 't': selfTest(); break;
    default: break;                                      // ignore newlines and anything else
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);
  Serial.println(F("# Second Opinion ultrasonic rig ready. Type ? for help, t for self-test."));
}

void loop() {
  while (Serial.available()) handle(Serial.read());

  unsigned long now = millis();
  if (now - lastPing >= PERIOD_MS) {
    lastPing = now;
    lastRange = readRangeMm();
    Serial.print(F("R,")); Serial.print(now); Serial.print(',');
    Serial.print(lastRange); Serial.println(F(",0"));     // steps = 0: no motor
  }
  if (talk && now - lastTalk >= 300) {
    lastTalk = now;
    Serial.print(F("# range: "));
    if (lastRange < 0) Serial.println(F("no echo"));
    else { Serial.print(lastRange / 10.0, 1); Serial.println(F(" cm")); }
  }
}
