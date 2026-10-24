#include "command.h"

#include <string.h>

namespace smpark {

const char* commandRejectReason(CommandReject reject) {
  switch (reject) {
    case CommandReject::None:                return "none";
    case CommandReject::InvalidJson:         return "invalid_json";
    case CommandReject::InvalidGate:         return "invalid_gate";
    case CommandReject::UnknownAction:       return "unknown_action";
    case CommandReject::MissingCorrelationId: return "missing_correlation_id";
  }
  return "invalid_command";
}

bool isValidGate(const char* gate) {
  return gate != nullptr &&
         (strcmp(gate, "entry") == 0 || strcmp(gate, "exit") == 0);
}

bool isValidAction(const char* action) {
  return action != nullptr &&
         (strcmp(action, "open") == 0 || strcmp(action, "close") == 0);
}

CommandReject validateCommand(const char* gate, const char* action,
                               const char* correlationId) {
  if (!isValidGate(gate)) return CommandReject::InvalidGate;
  if (!isValidAction(action)) return CommandReject::UnknownAction;
  if (correlationId == nullptr || correlationId[0] == '\0') {
    return CommandReject::MissingCorrelationId;
  }
  return CommandReject::None;
}

}  // namespace smpark
