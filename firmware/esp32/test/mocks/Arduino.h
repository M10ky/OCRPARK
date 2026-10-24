// =========================================================================
// SM-Park - Mock minimal d'Arduino pour les TESTS NATIFS (hôte)
// -------------------------------------------------------------------------
// Ce fichier n'est JAMAIS compilé pour l'ESP32 : il permet de tester la
// machine à états de la barrière sur la machine de développement, sans
// matériel et sans PlatformIO.
//
// Ce qu'il faut implémenter est volontairement minimal : `String`, `millis()`,
// `Serial`, `pinMode`/`digitalWrite` (utilisés par config.h).
// =========================================================================
#pragma once

#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>

// --- horloge simulée -------------------------------------------------------
extern uint64_t g_mockMillis;

inline void mockAdvanceMillis(uint64_t delta) { g_mockMillis += delta; }
inline void mockResetMillis() { g_mockMillis = 0; }

inline unsigned long millis() { return (unsigned long)g_mockMillis; }
inline unsigned long micros() { return (unsigned long)(g_mockMillis * 1000ULL); }
inline void delay(unsigned long) {}
inline void delayMicroseconds(unsigned int) {}

// --- String ----------------------------------------------------------------
class String {
 public:
  String() = default;
  String(const char* value) : value_(value ? value : "") {}
  String(const std::string& value) : value_(value) {}
  String(char c) : value_(1, c) {}

  const char* c_str() const { return value_.c_str(); }
  size_t length() const { return value_.size(); }
  bool isEmpty() const { return value_.empty(); }
  bool equals(const char* other) const { return value_ == (other ? other : ""); }
  bool equals(const String& other) const { return value_ == other.value_; }
  String& operator=(const char* other) {
    value_ = other ? other : "";
    return *this;
  }
  String& operator=(const std::string& other) {
    value_ = other;
    return *this;
  }
  bool operator==(const char* other) const { return value_ == (other ? other : ""); }
  bool operator==(const String& other) const { return value_ == other.value_; }
  bool operator!=(const String& other) const { return !(*this == other); }
  const std::string& str() const { return value_; }

 private:
  std::string value_;
};

// --- Serial ----------------------------------------------------------------
class MockSerial {
 public:
  void print(const char* message) { fputs(message ? message : "", stdout); }
  void print(const String& message) { fputs(message.c_str(), stdout); }
  void println() { fputc('\n', stdout); }
  void println(const char* message) {
    print(message);
    println();
  }
  void println(const String& message) {
    print(message);
    println();
  }
  void printf(const char* format, ...) {
    va_list args;
    va_start(args, format);
    vprintf(format, args);
    va_end(args);
  }
};

extern MockSerial Serial;

// --- GPIO (aucune effet réel en test natif) --------------------------------
inline void pinMode(uint8_t, uint8_t) {}
inline void digitalWrite(uint8_t, uint8_t) {}
inline int digitalRead(uint8_t) { return 0; }
inline int analogRead(uint8_t) { return 0; }
