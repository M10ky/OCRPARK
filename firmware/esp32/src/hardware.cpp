#include "hardware.h"

#include <ESP32Servo.h>

#include "config.h"

// =========================================================================
// SM-Park - Implémentation de la couche matérielle
// -------------------------------------------------------------------------
// Mesure HC-SR04 : machine à états NON BLOQUANTE.
//   IDLE -> TRIGGER -> TRIGGER_HOLD -> WAIT_RISE -> WAIT_FALL -> IDLE
// Un seul capteur est mesuré à la fois (round-robin) : pendant la fenêtre de
// mesure (~2 à 15 ms), la boucle ne fait QUE sonder la broche echo, ce qui
// donne une précision de l'ordre de 100 µs (≈ 0,3 cm).
// =========================================================================
namespace smpark::hw {
namespace {

// --- Mesure HC-SR04 -------------------------------------------------------
enum class UsState { Idle, Trigger, TriggerHold, WaitRise, WaitFall };

constexpr int US_HISTORY = 5;  // nombre de mesures conservées par place

struct SlotState {
  int trigPin = 0;
  int echoPin = 0;
  float history[US_HISTORY] = {0};
  int historyCount = 0;
  int historyIndex = 0;
  bool occupied = false;
  bool initialized = false;
  unsigned long lastMeasureMs = 0;
};

struct IrState {
  int pin = 0;
  bool lastRaw = false;
  bool stable = false;
  unsigned long lastChangeMs = 0;
};

SlotState g_slots[PARKING_SLOT_COUNT];
IrState g_irEntry;
IrState g_irExit;

Servo g_servoEntry;
Servo g_servoExit;
int g_angleEntry = -1;
int g_angleExit = -1;
bool g_movedEntry = false;
bool g_movedExit = false;

// État de la mesure en cours.
UsState g_usState = UsState::Idle;
int g_usSlot = 0;
unsigned long g_usTriggerUs = 0;
unsigned long g_usStartUs = 0;
unsigned long g_usRiseUs = 0;
unsigned long g_usNextSlotMs = 0;

// Distance courante de la mesure en cours (cm), < 0 si invalide.
float g_usLastDistance = -1.0f;

const int kTrigPins[PARKING_SLOT_COUNT] = {PIN_TRIG_1, PIN_TRIG_2, PIN_TRIG_3};
const int kEchoPins[PARKING_SLOT_COUNT] = {PIN_ECHO_1, PIN_ECHO_2, PIN_ECHO_3};

void slotsInit() {
  for (int i = 0; i < PARKING_SLOT_COUNT; i++) {
    g_slots[i].trigPin = kTrigPins[i];
    g_slots[i].echoPin = kEchoPins[i];
    g_slots[i].occupied = false;
    g_slots[i].historyCount = 0;
    g_slots[i].historyIndex = 0;
    g_slots[i].lastMeasureMs = 0;
    g_slots[i].initialized = false;
    pinMode(g_slots[i].trigPin, OUTPUT);
    digitalWrite(g_slots[i].trigPin, LOW);
    pinMode(g_slots[i].echoPin, INPUT);
  }
}

void irInit(IrState& state, int pin) {
  state.pin = pin;
  // GPIO 34/35 : entrées uniquement, sans pull-up/pull-down interne.
  // INPUT_PULLUP évite la lecture flottante quand la barrette est débranchée.
  pinMode(pin, INPUT_PULLUP);
  state.lastRaw = digitalRead(pin) == LOW;
  state.stable = state.lastRaw;
  state.lastChangeMs = millis();
}

/** Médiane de l'historique des mesures (robustesse aux valeurs aberrantes). */
float medianDistance(int slotIndex) {
  SlotState& slot = g_slots[slotIndex];
  if (slot.historyCount == 0) return -1.0f;

  float values[US_HISTORY];
  for (int i = 0; i < slot.historyCount; i++) values[i] = slot.history[i];
  for (int i = 0; i < slot.historyCount - 1; i++) {
    for (int j = i + 1; j < slot.historyCount; j++) {
      if (values[j] < values[i]) {
        float tmp = values[i];
        values[i] = values[j];
        values[j] = tmp;
      }
    }
  }
  return values[slot.historyCount / 2];
}

void pushHistory(int slotIndex, float distanceCm) {
  SlotState& slot = g_slots[slotIndex];
  slot.history[slot.historyIndex] = distanceCm;
  slot.historyIndex = (slot.historyIndex + 1) % US_HISTORY;
  if (slot.historyCount < US_HISTORY) slot.historyCount++;
}

/** Met à jour l'occupation avec hystérésis (évite le clignotement). */
void updateOccupied(int slotIndex, float medianCm) {
  if (medianCm < 0) return;
  SlotState& slot = g_slots[slotIndex];
  if (slot.occupied) {
    // Hystérésis : on libère la place plus loin que le seuil d'occupation.
    if (medianCm > OCCUPIED_DISTANCE_CM + OCCUPIED_HYSTERESIS_CM) slot.occupied = false;
  } else {
    if (medianCm < OCCUPIED_DISTANCE_CM) slot.occupied = true;
  }
  slot.initialized = true;
}

void finishMeasurement() {
  if (g_usState == UsState::WaitFall && g_usRiseUs > 0) {
    unsigned long durationUs = micros() - g_usRiseUs;
    // 58 µs par cm aller-retour (343 m/s).
    g_usLastDistance = durationUs / 58.0f;
  } else {
    g_usLastDistance = -1.0f;  // pas d'écho
  }

  if (g_usLastDistance >= 0.0f) {
    pushHistory(g_usSlot, g_usLastDistance);
    updateOccupied(g_usSlot, medianDistance(g_usSlot));
  }

  g_slots[g_usSlot].lastMeasureMs = millis();
  g_usState = UsState::Idle;
}

void pollUltrasonic() {
  unsigned long nowMs = millis();

  switch (g_usState) {
    case UsState::Idle: {
      if (nowMs < g_usNextSlotMs) return;
      // Round-robin : un capteur par fenêtre, on change de place à chaque
      // mesure terminée.
      g_usSlot = (g_usSlot + 1) % PARKING_SLOT_COUNT;
      g_usState = UsState::Trigger;
      break;
    }
    case UsState::Trigger: {
      digitalWrite(g_slots[g_usSlot].trigPin, HIGH);
      g_usTriggerUs = micros();
      g_usState = UsState::TriggerHold;
      break;
    }
    case UsState::TriggerHold: {
      if (micros() - g_usTriggerUs >= 10) {  // trigger de 10 µs
        digitalWrite(g_slots[g_usSlot].trigPin, LOW);
        g_usStartUs = micros();
        g_usState = UsState::WaitRise;
      }
      break;
    }
    case UsState::WaitRise: {
      if (digitalRead(g_slots[g_usSlot].echoPin) == HIGH) {
        g_usRiseUs = micros();
        g_usState = UsState::WaitFall;
      } else if (micros() - g_usStartUs > ULTRASONIC_ECHO_TIMEOUT_US) {
        finishMeasurement();
      }
      break;
    }
    case UsState::WaitFall: {
      if (digitalRead(g_slots[g_usSlot].echoPin) == LOW) {
        finishMeasurement();
      } else if (micros() - g_usRiseUs > ULTRASONIC_ECHO_TIMEOUT_US) {
        finishMeasurement();
      }
      break;
    }
  }
}

void pollIr(IrState& state) {
  bool raw = digitalRead(state.pin) == LOW;  // LOW = faisceau coupé = véhicule
  unsigned long now = millis();
  if (raw != state.lastRaw) {
    state.lastRaw = raw;
    state.lastChangeMs = now;
    return;
  }
  if (now - state.lastChangeMs >= IR_DEBOUNCE_MS) {
    state.stable = raw;
  }
}

}  // namespace

void begin() {
  slotsInit();
  irInit(g_irEntry, PIN_IR_ENTRY);
  irInit(g_irExit, PIN_IR_EXIT);

#if SMPARK_ENABLE_SERVOS == 1
  g_servoEntry.attach(PIN_SERVO_ENTRY);
  g_servoExit.attach(PIN_SERVO_EXIT);
  g_servoEntry.write(SERVO_CLOSED_ANGLE);
  g_servoExit.write(SERVO_CLOSED_ANGLE);
  g_angleEntry = SERVO_CLOSED_ANGLE;
  g_angleExit = SERVO_CLOSED_ANGLE;
#endif

  g_usState = UsState::Idle;
  g_usNextSlotMs = millis();
}

void poll() {
#if SMPARK_ENABLE_SENSORS == 1
  pollUltrasonic();
  pollIr(g_irEntry);
  pollIr(g_irExit);
#endif
}

float lastDistanceCm(int slotIndex) {
  if (slotIndex < 0 || slotIndex >= PARKING_SLOT_COUNT) return -1.0f;
  return medianDistance(slotIndex);
}

bool slotOccupied(int slotIndex) {
  if (slotIndex < 0 || slotIndex >= PARKING_SLOT_COUNT) return false;
  return g_slots[slotIndex].occupied;
}

void setSlotOccupied(int slotIndex, bool occupied) {
  if (slotIndex < 0 || slotIndex >= PARKING_SLOT_COUNT) return;
  g_slots[slotIndex].occupied = occupied;
  g_slots[slotIndex].initialized = true;
}

bool vehiclePresent(const char* gate) {
  if (gate == nullptr) return false;
  if (strcmp(gate, "exit") == 0) return g_irExit.stable;
  if (strcmp(gate, "entry") == 0) return g_irEntry.stable;
  return false;
}

void setBarrier(const char* gate, bool open) {
  if (gate == nullptr) return;
  const int angle = open ? SERVO_OPEN_ANGLE : SERVO_CLOSED_ANGLE;

#if SMPARK_ENABLE_SERVOS == 1
  if (strcmp(gate, "exit") == 0) {
    g_servoExit.write(angle);
    g_angleExit = angle;
    g_movedExit = true;
  } else if (strcmp(gate, "entry") == 0) {
    g_servoEntry.write(angle);
    g_angleEntry = angle;
    g_movedEntry = true;
  }
#else
  if (strcmp(gate, "exit") == 0) {
    g_angleExit = angle;
  } else if (strcmp(gate, "entry") == 0) {
    g_angleEntry = angle;
  }
#endif
}

int barrierAngle(const char* gate) {
  if (gate == nullptr) return -1;
  if (strcmp(gate, "exit") == 0) return g_angleExit;
  if (strcmp(gate, "entry") == 0) return g_angleEntry;
  return -1;
}

bool barrierMoved(const char* gate) {
  if (gate == nullptr) return false;
  if (strcmp(gate, "exit") == 0) return g_movedExit;
  if (strcmp(gate, "entry") == 0) return g_movedEntry;
  return false;
}

}  // namespace smpark::hw
