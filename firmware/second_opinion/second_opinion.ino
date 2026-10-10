// Second Opinion demo rig firmware (Arduino Uno/Nano).
//
// Hardware:
//   HC-SR04 ultrasonic sensor  TRIG -> D7, ECHO -> D2 (interrupt pin)
//   Stepper driver (A4988 / DRV8825 / TMC2208)  STEP -> D3, DIR -> D4, EN -> D8
//   The carriage carries the webcam and the ultrasonic sensor, pointing down.
//
// Serial, 115200 baud. Every 50 ms the board sends
//   R,<millis>,<range_mm or -1>,<speed_mm_s>,<position_mm>
// speed is positive while descending; position is measured down from zero.
// Commands (newline-terminated):
//   D<mm/s>  descend      U<mm/s>  raise      S  stop      Z  set zero here
//
// Echo timing uses a pin-change interrupt instead of pulseIn(), so measuring
// distance never stalls the stepper and the reported speed stays honest.

// ---- Configure for your rig ------------------------------------------------
const float STEPS_PER_MM = 400.0;    // 200 steps * 16 microsteps / 8 mm lead screw
const float MAX_TRAVEL_MM = 300.0;   // soft limit below the zero position
const bool  DIR_DOWN_LEVEL = HIGH;   // flip if the carriage moves the wrong way
const float MAX_SPEED_MM_S = 80.0;
// ----------------------------------------------------------------------------

const uint8_t PIN_TRIG = 7, PIN_ECHO = 2, PIN_STEP = 3, PIN_DIR = 4, PIN_EN = 8;

volatile unsigned long echoStart = 0, echoWidth = 0;
volatile bool echoDone = false;

long positionSteps = 0;      // + = down
float speedMmS = 0;          // signed, + = down
unsigned long stepInterval = 0, lastStep = 0;
unsigned long lastPing = 0, lastReport = 0;
long rangeMm = -1;
char cmd[16];
uint8_t cmdLen = 0;

void echoIsr() {
  if (digitalRead(PIN_ECHO)) {
    echoStart = micros();
  } else {
    echoWidth = micros() - echoStart;
    echoDone = true;
  }
}

void setSpeed(float mmS) {
  mmS = constrain(mmS, -MAX_SPEED_MM_S, MAX_SPEED_MM_S);
  speedMmS = mmS;
  if (mmS == 0) {
    stepInterval = 0;
    return;
  }
  digitalWrite(PIN_DIR, mmS > 0 ? DIR_DOWN_LEVEL : !DIR_DOWN_LEVEL);
  stepInterval = (unsigned long)(1e6 / (fabs(mmS) * STEPS_PER_MM));
}

void handleCommand(const char* c) {
  switch (c[0]) {
    case 'D': setSpeed(atof(c + 1)); break;
    case 'U': setSpeed(-atof(c + 1)); break;
    case 'S': setSpeed(0); break;
    case 'Z': positionSteps = 0; break;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  pinMode(PIN_STEP, OUTPUT);
  pinMode(PIN_DIR, OUTPUT);
  pinMode(PIN_EN, OUTPUT);
  digitalWrite(PIN_EN, LOW);  // enable driver
  attachInterrupt(digitalPinToInterrupt(PIN_ECHO), echoIsr, CHANGE);
}

void loop() {
  const unsigned long now = micros();

  // Stepper: one step per interval, respecting the soft limits.
  if (stepInterval && now - lastStep >= stepInterval) {
    lastStep = now;
    const bool down = speedMmS > 0;
    const float posMm = positionSteps / STEPS_PER_MM;
    if ((down && posMm >= MAX_TRAVEL_MM) || (!down && positionSteps <= 0)) {
      setSpeed(0);
    } else {
      digitalWrite(PIN_STEP, HIGH);
      delayMicroseconds(2);
      digitalWrite(PIN_STEP, LOW);
      positionSteps += down ? 1 : -1;
    }
  }

  // Ultrasonic: trigger every 40 ms, read the result when the echo ends.
  if (now - lastPing >= 40000UL) {
    if (!echoDone) rangeMm = -1;  // previous ping never came back
    lastPing = now;
    echoDone = false;
    digitalWrite(PIN_TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(PIN_TRIG, LOW);
  }
  if (echoDone) {
    noInterrupts();
    const unsigned long w = echoWidth;
    interrupts();
    // Speed of sound: 0.343 mm/us, there and back. >25 ms means no echo.
    rangeMm = (w > 100 && w < 25000UL) ? (long)(w * 0.1715) : -1;
  }

  // Telemetry.
  if (now - lastReport >= 50000UL) {
    lastReport = now;
    Serial.print("R,");
    Serial.print(millis());
    Serial.print(',');
    Serial.print(rangeMm);
    Serial.print(',');
    Serial.print(speedMmS, 1);
    Serial.print(',');
    Serial.println(positionSteps / STEPS_PER_MM, 1);
  }

  // Commands.
  while (Serial.available()) {
    const char ch = Serial.read();
    if (ch == '\n' || ch == '\r') {
      if (cmdLen) {
        cmd[cmdLen] = 0;
        handleCommand(cmd);
        cmdLen = 0;
      }
    } else if (cmdLen < sizeof(cmd) - 1) {
      cmd[cmdLen++] = ch;
    }
  }
}
