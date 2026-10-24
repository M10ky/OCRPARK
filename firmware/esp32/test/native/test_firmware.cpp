// =========================================================================
// SM-Park - Tests natifs du firmware (machine hôte, sans ESP32)
// -------------------------------------------------------------------------
// Couvre les corrections du contrat MQTT qui sont vérifiables sans matériel :
//   - F-05 / F-06 / F-07 : validation stricte de la commande, aucun servo
//     déclenché et AUCUN ACK sur une commande invalide ;
//   - F-08 : un état distinct par barrière (entry / exit) ;
//   - contrat §D.4 : l'ACK porte le correlation_id, une seule fois.
//
// Compilation : scripts/test_firmware_logic.sh
// =========================================================================
#include <cstdio>
#include <string>
#include <vector>

#include "Arduino.h"
#include "barrier.h"
#include "command.h"
#include "config.h"
#include "hardware.h"

uint64_t g_mockMillis = 0;
MockSerial Serial;

// --- Stub de la couche matérielle ------------------------------------------
// On enregistre les appels au servo pour prouver qu'une commande invalide
// ne déclenche AUCUN mouvement.
namespace {
struct ServoCall {
  std::string gate;
  bool open;
};
std::vector<ServoCall> g_servoCalls;
}  // namespace

namespace smpark::hw {
void setBarrier(const char* gate, bool open) {
  g_servoCalls.push_back({gate ? gate : "", open});
}
}  // namespace smpark::hw

// --- Micro-harnais de test -------------------------------------------------
static int g_checks = 0;
static int g_failures = 0;

#define CHECK(condition, label)                                             \
  do {                                                                      \
    g_checks++;                                                             \
    if (condition) {                                                        \
      printf("  [OK]   %s\n", label);                                       \
    } else {                                                                \
      g_failures++;                                                         \
      printf("  [FAIL] %s\n", label);                                       \
    }                                                                       \
  } while (0)

static void section(const char* title) { printf("\n%s\n", title); }

// --- Tests -----------------------------------------------------------------
static void testValidation() {
  section("Validation des commandes (F-05 / F-06 / F-07)");

  CHECK(smpark::validateCommand("entry", "open", "cid-1") ==
            smpark::CommandReject::None,
        "commande valide (entry/open) acceptee");
  CHECK(smpark::validateCommand("exit", "close", "cid-2") ==
            smpark::CommandReject::None,
        "commande valide (exit/close) acceptee");

  CHECK(smpark::validateCommand("north", "open", "cid-3") ==
            smpark::CommandReject::InvalidGate,
        "gate inconnu -> invalid_gate");
  CHECK(smpark::validateCommand(nullptr, "open", "cid-4") ==
            smpark::CommandReject::InvalidGate,
        "gate null -> invalid_gate");

  CHECK(smpark::validateCommand("entry", "open_button", "cid-5") ==
            smpark::CommandReject::UnknownAction,
        "action inconnue -> unknown_action");

  CHECK(smpark::validateCommand("entry", "open", "") ==
            smpark::CommandReject::MissingCorrelationId,
        "correlation_id vide -> missing_correlation_id");
  CHECK(smpark::validateCommand("entry", "open", nullptr) ==
            smpark::CommandReject::MissingCorrelationId,
        "correlation_id null -> missing_correlation_id");

  CHECK(std::string(smpark::commandRejectReason(smpark::CommandReject::InvalidJson)) ==
            "invalid_json",
        "raison invalid_json conforme au contrat");
  CHECK(std::string(smpark::commandRejectReason(smpark::CommandReject::UnknownAction)) ==
            "unknown_action",
        "raison unknown_action conforme au contrat");
}

static void testRejectedCommandDoesNotMoveServo() {
  section("Commande invalide : aucun mouvement de servo, aucun ACK");

  smpark::BarrierController controller;
  controller.begin();
  g_servoCalls.clear();

  CHECK(!controller.request("entry", "open_button", "cid-bad"),
        "commande invalide refusee");
  CHECK(g_servoCalls.empty(), "aucun servo declenche par une commande invalide");
  CHECK(controller.state("entry").phase == smpark::BarrierPhase::Idle,
        "phase reste idle apres une commande invalide");
  CHECK(controller.state("entry").correlationId.length() == 0,
        "aucun correlation_id memorise sur une commande invalide");
}

static void testValidCommandSequence() {
  section("Commande valide : sequence opening -> open -> closing -> closed");

  smpark::BarrierController controller;
  controller.begin();
  g_servoCalls.clear();

  CHECK(controller.request("entry", "open", "cid-ok"),
        "commande open acceptee");
  CHECK(controller.state("entry").phase == smpark::BarrierPhase::Opening,
        "phase immediate = opening");
  CHECK(!g_servoCalls.empty() && g_servoCalls.back().open,
        "servo entry ouvert");

  std::string correlationId = controller.takeCorrelationId("entry").c_str();
  CHECK(correlationId == "cid-ok", "ACK : correlation_id repris a l'identique");
  CHECK(controller.takeCorrelationId("entry").length() == 0,
        "ACK : correlation_id consomme (un seul ACK par commande)");

  mockAdvanceMillis(OPENING_DURATION_MS + 1);
  CHECK(controller.update(), "update() signale la transition opening -> open");
  CHECK(controller.state("entry").phase == smpark::BarrierPhase::Open,
        "phase = open");

  mockAdvanceMillis(OPEN_HOLD_MS + 1);
  CHECK(controller.update(), "update() signale la transition open -> closing");
  CHECK(controller.state("entry").phase == smpark::BarrierPhase::Closing,
        "phase = closing");

  mockAdvanceMillis(CLOSING_DURATION_MS + 1);
  CHECK(controller.update(), "update() signale la transition closing -> closed");
  CHECK(controller.state("entry").phase == smpark::BarrierPhase::Closed,
        "phase = closed");
  CHECK(!g_servoCalls.empty() && !g_servoCalls.back().open,
        "servo entry referme en fin de sequence");
}

static void testPerGateIsolation() {
  section("Un etat distinct par barriere (F-08)");

  smpark::BarrierController controller;
  controller.begin();
  g_servoCalls.clear();

  CHECK(controller.request("exit", "open", "cid-exit"), "commande exit acceptee");
  CHECK(controller.state("exit").phase == smpark::BarrierPhase::Opening,
        "phase exit = opening");
  CHECK(controller.state("entry").phase == smpark::BarrierPhase::Idle,
        "phase entry inchangee par une commande exit");
  CHECK(std::string(controller.activeGate()) == "exit",
        "porte active = exit");

  bool exitOpen = false;
  bool entryTouched = false;
  for (const ServoCall& call : g_servoCalls) {
    if (call.gate == "exit") exitOpen = call.open;
    if (call.gate == "entry") entryTouched = true;
  }
  CHECK(exitOpen, "servo exit ouvert");
  CHECK(!entryTouched, "servo entry non touche par une commande exit");
}

static void testPhaseNames() {
  section("Noms de phases conformes au contrat");

  CHECK(std::string(smpark::barrierPhaseName(smpark::BarrierPhase::Idle)) == "idle",
        "idle");
  CHECK(std::string(smpark::barrierPhaseName(smpark::BarrierPhase::Opening)) ==
            "opening",
        "opening");
  CHECK(std::string(smpark::barrierPhaseName(smpark::BarrierPhase::Open)) == "open",
        "open");
  CHECK(std::string(smpark::barrierPhaseName(smpark::BarrierPhase::Closing)) ==
            "closing",
        "closing");
  CHECK(std::string(smpark::barrierPhaseName(smpark::BarrierPhase::Closed)) ==
            "closed",
        "closed");
}

int main() {
  printf("SM-Park - tests natifs du firmware\n");
  mockResetMillis();

  testValidation();
  testRejectedCommandDoesNotMoveServo();
  testValidCommandSequence();
  testPerGateIsolation();
  testPhaseNames();

  printf("\n%d verifications, %d echec(s)\n", g_checks, g_failures);
  if (g_failures == 0) {
    printf("RESULTAT: OK\n");
    return 0;
  }
  printf("RESULTAT: ECHEC\n");
  return 1;
}
