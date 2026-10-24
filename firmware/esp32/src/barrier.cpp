#include "barrier.h"

#include "command.h"
#include "config.h"
#include "hardware.h"

namespace smpark {
namespace {

}  // namespace

const char* barrierPhaseName(BarrierPhase phase) {
  switch (phase) {
    case BarrierPhase::Opening: return "opening";
    case BarrierPhase::Open:    return "open";
    case BarrierPhase::Closing: return "closing";
    case BarrierPhase::Closed:  return "closed";
    case BarrierPhase::Idle:    break;
  }
  return "idle";
}

void BarrierController::begin() {
  g_entry = BarrierGate();
  g_exit = BarrierGate();
  g_activeGate = "entry";
  hw::setBarrier("entry", false);
  hw::setBarrier("exit", false);
}

BarrierGate& BarrierController::mutableGate(const char* gate) {
  if (gate != nullptr && strcmp(gate, "exit") == 0) return g_exit;
  return g_entry;
}

const BarrierGate& BarrierController::state(const char* gate) const {
  if (gate != nullptr && strcmp(gate, "exit") == 0) return g_exit;
  return g_entry;
}

const char* BarrierController::activeGate() const {
  return g_activeGate;
}

const BarrierGate& BarrierController::activeState() const {
  return state(g_activeGate);
}

void BarrierController::enterPhase(BarrierGate& gateState, BarrierPhase phase,
                                   const char* reason) {
  gateState.phase = phase;
  gateState.phaseSince = millis();
  if (reason != nullptr) gateState.reason = reason;

  if (phase == BarrierPhase::Opening || phase == BarrierPhase::Open) {
    hw::setBarrier(g_activeGate, true);
  } else if (phase == BarrierPhase::Closing || phase == BarrierPhase::Closed ||
             phase == BarrierPhase::Idle) {
    hw::setBarrier(g_activeGate, false);
  }
}

bool BarrierController::request(const char* gate, const char* action,
                                const String& correlationId) {
  // Validation STRICTE (F-05 / F-07) : une commande invalide ne doit jamais
  // déclencher un servo.
  if (validateCommand(gate, action, correlationId.c_str()) != CommandReject::None) {
    return false;
  }

  g_activeGate = gate;
  BarrierGate& gateState = mutableGate(gate);
  gateState.correlationId = correlationId;

  if (strcmp(action, "open") == 0) {
    enterPhase(gateState, BarrierPhase::Opening, "command");
  } else {
    enterPhase(gateState, BarrierPhase::Closing, "command");
  }
  return true;
}

bool BarrierController::update() {
  unsigned long now = millis();
  const BarrierPhase before = activeState().phase;

  BarrierGate* gates[2] = {&g_entry, &g_exit};
  for (BarrierGate* gateState : gates) {
    const unsigned long elapsed = now - gateState->phaseSince;
    const bool isActive =
        (gateState == &g_entry) ? strcmp(g_activeGate, "entry") == 0
                                : strcmp(g_activeGate, "exit") == 0;
    switch (gateState->phase) {
      case BarrierPhase::Opening:
        if (elapsed >= OPENING_DURATION_MS) {
          gateState->phase = BarrierPhase::Open;
          gateState->phaseSince = now;
          if (isActive) hw::setBarrier(g_activeGate, true);
        }
        break;
      case BarrierPhase::Open:
        if (elapsed >= OPEN_HOLD_MS) {
          gateState->phase = BarrierPhase::Closing;
          gateState->phaseSince = now;
          if (isActive) hw::setBarrier(g_activeGate, false);
        }
        break;
      case BarrierPhase::Closing:
        if (elapsed >= CLOSING_DURATION_MS) {
          gateState->phase = BarrierPhase::Closed;
          gateState->phaseSince = now;
          if (isActive) hw::setBarrier(g_activeGate, false);
        }
        break;
      default:
        break;
    }
  }

  return before != activeState().phase;
}

String BarrierController::takeCorrelationId(const char* gate) {
  BarrierGate& gateState = mutableGate(gate);
  String id = gateState.correlationId;
  gateState.correlationId = "";
  return id;
}

}  // namespace smpark
