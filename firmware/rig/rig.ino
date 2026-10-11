// Second Opinion — servo winch rig
// Hardware: micro servo on D9 (drives the spools), HC-SR04 ultrasonic Trig D7 / Echo D8.
//
// ---------- TESTING BY HAND (Arduino IDE: Tools > Serial Monitor, 115200 baud, "Newline") ----------
//   ?        help + current status
//   p        toggle printing range in plain words (cm) — wave your hand under the sensor
//   t        self-test: sensor check, then sweep the servo top -> bottom -> top slowly
//   d        demo descend: lower slowly, stop when the sensor reads < STOP_MM (legs on the ground)
//   u        go back up to the top
//   +  /  -  nudge the spools 5 degrees down / up (find which way is "down")
//   c        engine cut: jump to the bottom angle instantly (the crash drop)
//   s        stop where you are
//
// ---------- USED BY THE PYTHON ENGINE ----------
//   A<tenths>  move to an absolute angle, in tenths of a degree from the top (A0 .. A1800)
//   Z          back to the top (same as u)
//   C          engine cut (same as c)
// Every 50 ms the board prints:  R,<millis>,<range_mm or -1>,<angle_tenths>
// Human-readable lines start with '#', so the Python side ignores them.

#include <Servo.h>

// ---- pins ----
const int SERVO_PIN = 9;
const int TRIG_PIN = 7;
const int ECHO_PIN = 8;

// ---- servo calibration (change these if needed) ----
const int  US_AT_0   = 500;     // pulse width at 0 degrees (most micro servos: 500-600)
const int  US_AT_180 = 2400;    // pulse width at 180 degrees (most micro servos: 2300-2500)
const int  DIR       = 1;       // set to -1 if "+" makes the sled go UP instead of down
const int  MAX_TENTHS = 1800;   // 180 degrees of travel
const int  SLEW_TENTHS_PER_S = 600;   // smooth moves: 60 degrees per second max (not for cut)

// ---- safety / demo ----
const int  STOP_MM = 45;        // demo descend stops when the sensor reads closer than this
const int  DEMO_TENTHS_PER_S = 100;   // demo descend speed: 10 degrees per second (~10 mm/s)

Servo servo;
long targetTenths = 0;      // where we want to be
float posTenths = 0;        // where we are commanding now (slewed toward target)
bool instant = false;       // true for engine cut: skip slewing
bool demo = false;          // demo descend running
bool talk = false;          // plain-words range printing
long lastRange = -1;
unsigned long lastTick = 0, lastPing = 0, lastTalk = 0;
String line = "";

long readRangeMm() {
  digitalWrite(TRIG_PIN, LOW);  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long us = pulseIn(ECHO_PIN, HIGH, 12000UL);   // 12 ms cap (~2 m) keeps motion smooth
  if (us == 0) return -1;                                // no echo
  return (long)(us * 0.1715);                            // mm, speed of sound 343 m/s, round trip
}

void writeServo(float tenths) {
  // tenths of a degree from the top -> servo angle -> pulse width
  float deg = tenths / 10.0;
  if (DIR < 0) deg = 180.0 - deg;
  int us = US_AT_0 + (int)((US_AT_180 - US_AT_0) * deg / 180.0);
  servo.writeMicroseconds(us);
}

void setTarget(long t, bool jump) {
  targetTenths = constrain(t, 0, MAX_TENTHS);
  instant = jump;
}

void help() {
  Serial.println(F("# commands: ? p t d u + - c s | engine: A<tenths> Z C"));
  Serial.print(F("# angle (tenths from top): ")); Serial.print((long)posTenths);
  Serial.print(F("  target: ")); Serial.print(targetTenths);
  Serial.print(F("  range mm: ")); Serial.println(lastRange);
}

void selfTest() {
  Serial.println(F("# --- self-test ---"));
  int good = 0;
  for (int i = 0; i < 10; i++) {
    long r = readRangeMm();
    Serial.print(F("# range ")); Serial.print(i); Serial.print(F(": "));
    if (r < 0) Serial.println(F("no echo")); else { Serial.print(r); Serial.println(F(" mm")); good++; }
    delay(60);
  }
  Serial.println(good >= 8 ? F("# sensor OK") : F("# sensor PROBLEM: check VCC/GND, Trig->D7, Echo->D8, and aim it at something within 2 m"));
  Serial.println(F("# sweeping servo: top -> bottom -> top (watch which way the sled moves)"));
  for (int t = 0; t <= MAX_TENTHS; t += 20) { writeServo(t); delay(15); }
  delay(400);
  for (int t = MAX_TENTHS; t >= 0; t -= 20) { writeServo(t); delay(15); }
  posTenths = 0; setTarget(0, false);
  Serial.println(F("# sweep done. If the sled went UP first, set DIR = -1 and re-upload."));
}

void handle(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;
  char c = cmd.charAt(0);
  if (c == 'A') { demo = false; setTarget(cmd.substring(1).toInt(), false); return; }
  switch (c) {
    case '?': help(); break;
    case 'p': talk = !talk; Serial.println(talk ? F("# range printing ON") : F("# range printing OFF")); break;
    case 't': demo = false; selfTest(); break;
    case 'd': demo = true; Serial.println(F("# demo descend: lowering until the legs touch")); break;
    case 'u': case 'Z': demo = false; setTarget(0, false); Serial.println(F("# going to top")); break;
    case '+': demo = false; setTarget(targetTenths + 50, false); break;
    case '-': demo = false; setTarget(targetTenths - 50, false); break;
    case 'c': case 'C': demo = false; setTarget(MAX_TENTHS, true); Serial.println(F("# ENGINE CUT")); break;
    case 's': demo = false; setTarget((long)posTenths, false); Serial.println(F("# stopped")); break;
    default: Serial.println(F("# unknown command, type ? for help"));
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  servo.attach(SERVO_PIN);
  writeServo(0);
  lastTick = millis();
  Serial.println(F("# Second Opinion servo rig ready. Type ? for help, t for self-test."));
}

void loop() {
  // read commands (newline-terminated; single letters also work without newline)
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n' || ch == '\r') { handle(line); line = ""; }
    else if (line.length() == 0 && ch != 'A' && ch != ' ') { handle(String(ch)); }
    else line += ch;
  }

  unsigned long now = millis();
  float dt = (now - lastTick) / 1000.0;
  lastTick = now;

  // demo descend: creep down until the sensor says the legs are on the ground
  if (demo) {
    if (lastRange > 0 && lastRange < STOP_MM) { demo = false; setTarget((long)posTenths, false); Serial.println(F("# touchdown (sensor)")); }
    else if (targetTenths >= MAX_TENTHS) { demo = false; Serial.println(F("# reached bottom of travel")); }
    else setTarget(targetTenths + max(1L, (long)(DEMO_TENTHS_PER_S * dt + 0.5)), false);
  }

  // move toward the target: instantly for an engine cut, otherwise slew-limited
  if (instant) { posTenths = targetTenths; instant = false; }
  else {
    float step = SLEW_TENTHS_PER_S * dt;
    if (posTenths < targetTenths) posTenths = min((float)targetTenths, posTenths + step);
    else if (posTenths > targetTenths) posTenths = max((float)targetTenths, posTenths - step);
  }
  writeServo(posTenths);

  // telemetry for the engine, 20 Hz
  if (now - lastPing >= 50) {
    lastPing = now;
    lastRange = readRangeMm();
    Serial.print(F("R,")); Serial.print(now); Serial.print(',');
    Serial.print(lastRange); Serial.print(','); Serial.println((long)posTenths);
  }
  if (talk && now - lastTalk >= 300) {
    lastTalk = now;
    Serial.print(F("# range: "));
    if (lastRange < 0) Serial.println(F("no echo")); else { Serial.print(lastRange / 10.0, 1); Serial.println(F(" cm")); }
  }
}
