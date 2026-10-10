// Headless runner: plays each scenario with both landers and prints what
// happened. Usage: so_sim_cli [scenario-id] [--events]
#include <chrono>
#include <cstdio>
#include <cstring>
#include <string>

#include "sim/simulation.h"

using namespace so;
using namespace so::sim;

static const char* kindTag(FusionEvent::Kind k) {
  switch (k) {
    case FusionEvent::Kind::Info: return "info ";
    case FusionEvent::Kind::Good: return "good ";
    case FusionEvent::Kind::Warn: return "warn ";
    case FusionEvent::Kind::Fault: return "FAULT";
  }
  return "";
}

int main(int argc, char** argv) {
  std::string only;
  bool events = false;
  for (int i = 1; i < argc; i++) {
    if (!std::strcmp(argv[i], "--events")) events = true;
    else only = argv[i];
  }
  for (const Scenario& sc : builtinScenarios()) {
    if (!only.empty() && sc.id != only) continue;
    const auto t0 = std::chrono::steady_clock::now();
    Simulation sim(sc);
    while (!sim.finished() && sim.time() < 200) sim.step();
    const double wall = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    std::printf("\n== %s ==\n   real mission: %s\n", sc.title.c_str(), sc.realOutcome.c_str());
    for (const Lander* l : {&sim.baseline(), &sim.secondOpinion()}) {
      std::printf("   %-15s %-12s %s\n", l->brain == Brain::SecondOpinion ? "Second Opinion" : "Baseline",
                  toString(l->outcome.kind), l->outcome.text.c_str());
      if (events)
        for (const auto& e : l->events()) std::printf("      t=%5.2f [%s] %s\n", e.t, kindTag(e.kind), e.text.c_str());
    }
    std::printf("   (%.1f s simulated in %.2f s)\n", sim.time(), wall);
  }
}
