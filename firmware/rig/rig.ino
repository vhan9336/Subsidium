// Subsidium rig: winch stepper lowers the lander sled; Grove ultrasonic = the "laser rangefinder".
// Serial out (~20 Hz):  R,<millis>,<range_mm or -1>,<steps>
// Serial in (1 char):   d = descend, u = up, s = stop, z = zero step counter
//
// Wiring assumes a 28BYJ-48 stepper on a ULN2003 board (IN1..IN4 -> pins 8,9,10,11)
// and the Grove Ultrasonic Ranger signal on D7. If your kit's driver is different,
// only stepOnce() needs to change. No libraries needed.

const int RANGER_PIN = 7;
const int COIL[4] = {8, 9, 10, 11};
const unsigned long STEP_US = 1100;     // half-step period; ~1100 us is near the 28BYJ-48's max
const long MIN_STEPS = -2000;           // safety: don't unwind above the start point much
const long MAX_STEPS = 16000;           // safety: set after measuring your rig (stop before the sled hits the ground)
const int STOP_MM = 60;                 // safety: stop descending when the ranger reads below this

const uint8_t SEQ[8][4] = {{1,0,0,0},{1,1,0,0},{0,1,0,0},{0,1,1,0},{0,0,1,0},{0,0,1,1},{0,0,0,1},{1,0,0,1}};
int phase = 0;
long steps = 0;
int dir = 0;                            // +1 = descend (unwind), -1 = up, 0 = stop
unsigned long lastStep = 0, lastPing = 0;
long lastRange = -1;

void stepOnce(int d) {
  phase = (phase + d + 8) % 8;
  for (int i = 0; i < 4; i++) digitalWrite(COIL[i], SEQ[phase][i]);
  steps += d;
}

void coilsOff() { for (int i = 0; i < 4; i++) digitalWrite(COIL[i], LOW); }

long readRangeMm() {
  pinMode(RANGER_PIN, OUTPUT);
  digitalWrite(RANGER_PIN, LOW);  delayMicroseconds(2);
  digitalWrite(RANGER_PIN, HIGH); delayMicroseconds(10);
  digitalWrite(RANGER_PIN, LOW);
  pinMode(RANGER_PIN, INPUT);
  unsigned long us = pulseIn(RANGER_PIN, HIGH, 12000UL);  // 12 ms cap (~2 m) keeps the stepper smooth
  if (us == 0) return -1;
  return (long)(us * 0.1715);   // speed of sound 343 m/s, round trip
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 4; i++) pinMode(COIL[i], OUTPUT);
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'd') dir = 1;
    else if (c == 'u') dir = -1;
    else if (c == 's') dir = 0;
    else if (c == 'z') steps = 0;
  }
  unsigned long now = micros();
  if (dir != 0 && now - lastStep >= STEP_US) {
    lastStep = now;
    bool blocked = (dir > 0 && (steps >= MAX_STEPS || (lastRange > 0 && lastRange < STOP_MM))) ||
                   (dir < 0 && steps <= MIN_STEPS);
    if (blocked) { dir = 0; coilsOff(); }
    else stepOnce(dir);           // flip the sign here if your spool winds the other way
  }
  if (dir == 0) coilsOff();
  if (millis() - lastPing >= 50) {
    lastPing = millis();
    lastRange = readRangeMm();
    Serial.print("R,"); Serial.print(millis()); Serial.print(",");
    Serial.print(lastRange); Serial.print(","); Serial.println(steps);
  }
}
