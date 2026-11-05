
#include <algorithm>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>

using namespace std;

// =============================================
// 1. DISMISSAL TYPES
// =============================================

enum class Dismissal {
  NONE,
  BOWLED,
  CAUGHT,
  LBW,
  STUMPED,
  HIT_WICKET,
  RUN_OUT,
  RETIRED_HURT
};

// =============================================
// 2. BALL EVENT
// Represents one delivery
// =============================================

struct BallEvent {

  int batterRuns = 0;

  bool wide = false;
  int wideRuns = 0;

  bool noBall = false;

  int byes = 0;
  int legByes = 0;

  Dismissal dismissal = Dismissal::NONE;

  string dismissedPlayerId;
};

// =============================================
// 3. BATTING STATISTICS
// =============================================

class BattingStats {

private:
  int runs = 0;
  int ballsFaced = 0;
  int fours = 0;
  int sixes = 0;
  int dismissals = 0;

public:
  void recordRuns(int value) {
    runs += value;

    if (value == 4)
      fours++;

    if (value == 6)
      sixes++;
  }

  void recordBall() { ballsFaced++; }

  void recordDismissal() { dismissals++; }

  int getRuns() const { return runs; }

  int getBallsFaced() const { return ballsFaced; }

  int getFours() const { return fours; }

  int getSixes() const { return sixes; }

  double getStrikeRate() const {

    if (ballsFaced == 0)
      return 0.0;

    return runs * 100.0 / ballsFaced;
  }
};

// =============================================
// 4. BOWLING STATISTICS
// =============================================

class BowlingStats {

private:
  int legalBalls = 0;
  int runsConceded = 0;
  int wickets = 0;

public:
  void recordLegalBall() { legalBalls++; }

  void recordRuns(int runs) { runsConceded += runs; }

  void recordWicket() { wickets++; }

  int getLegalBalls() const { return legalBalls; }

  int getRunsConceded() const { return runsConceded; }

  int getWickets() const { return wickets; }

  double getEconomy() const {

    if (legalBalls == 0)
      return 0.0;

    return runsConceded * 6.0 / legalBalls;
  }
};

// =============================================
// 5. INNINGS CLASS
// Main scoring engine
// =============================================

class Innings {

private:
  string battingTeamId;

  string striker;
  string nonStriker;

  int totalRuns = 0;
  int totalWickets = 0;
  int legalBalls = 0;

  int maxOvers;

  bool completed = false;

  unordered_map<string, BattingStats> battingStats;

  unordered_map<string, BowlingStats> bowlingStats;

  // Check whether a dismissal is credited to bowler

  bool isBowlerCreditedDismissal(Dismissal type) const {

    return type == Dismissal::BOWLED || type == Dismissal::CAUGHT ||
           type == Dismissal::LBW || type == Dismissal::STUMPED ||
           type == Dismissal::HIT_WICKET;
  }

  // Validate a delivery before changing the score

  void validateEvent(const BallEvent &event) const {

    if (event.batterRuns < 0 || event.wideRuns < 0 || event.byes < 0 ||
        event.legByes < 0) {

      throw invalid_argument("Negative runs are invalid");
    }

    if (event.wide && event.noBall) {
      throw invalid_argument("A delivery cannot be both wide and no-ball");
    }

    if (!event.wide && event.wideRuns != 0) {
      throw invalid_argument("Wide runs specified on a non-wide delivery");
    }

    if (event.wide && event.batterRuns != 0) {
      throw invalid_argument("Batter cannot score runs off a wide");
    }

    if (event.byes > 0 && event.legByes > 0) {
      throw invalid_argument("Byes and leg-byes cannot coexist");
    }

    if (event.wide && (event.byes > 0 || event.legByes > 0)) {

      throw invalid_argument("Wide cannot be combined with byes or leg-byes");
    }

    if ((event.byes > 0 || event.legByes > 0) && event.batterRuns > 0) {

      throw invalid_argument("Bat runs cannot be combined with byes");
    }

    if (event.dismissal == Dismissal::NONE &&
        !event.dismissedPlayerId.empty()) {

      throw invalid_argument("Dismissed player supplied without dismissal");
    }

    if (event.dismissal != Dismissal::NONE) {

      if (event.dismissedPlayerId.empty()) {
        throw invalid_argument("Dismissed player ID is required");
      }

      if (event.dismissedPlayerId != striker &&
          event.dismissedPlayerId != nonStriker) {

        throw invalid_argument("Dismissed player is not at the crease");
      }
    }

    if (event.wide && event.dismissal != Dismissal::NONE &&
        event.dismissal != Dismissal::RUN_OUT &&
        event.dismissal != Dismissal::STUMPED) {

      throw invalid_argument("Invalid dismissal on wide");
    }

    if (event.noBall && event.dismissal != Dismissal::NONE &&
        event.dismissal != Dismissal::RUN_OUT) {

      throw invalid_argument("Invalid dismissal on no-ball");
    }

    if (event.batterRuns > 0 && (event.byes > 0 || event.legByes > 0)) {

      throw invalid_argument("Invalid scoring combination");
    }

    if (event.dismissal != Dismissal::NONE && totalWickets >= 10 &&
        event.dismissal != Dismissal::RETIRED_HURT) {

      throw runtime_error("All wickets have already fallen");
    }
  }

  // Calculate total extras

  int calculateExtras(const BallEvent &event) const {

    return (event.wide ? 1 + event.wideRuns : 0) + (event.noBall ? 1 : 0) +
           event.byes + event.legByes;
  }

  // Calculate completed runs for strike rotation

  int calculateCompletedRuns(const BallEvent &event) const {

    return event.batterRuns + event.wideRuns + event.byes + event.legByes;
  }

public:
  // =========================================
  // CONSTRUCTOR
  // =========================================

  Innings(const string &teamId, const string &openingStriker,
          const string &openingNonStriker, int overs) {

    if (teamId.empty() || openingStriker.empty() || openingNonStriker.empty() ||
        openingStriker == openingNonStriker) {

      throw invalid_argument("Invalid innings initialization");
    }

    if (overs < -1 || overs == 0) {
      throw invalid_argument("Invalid over limit");
    }

    battingTeamId = teamId;
    striker = openingStriker;
    nonStriker = openingNonStriker;
    maxOvers = overs;
  }

  // =========================================
  // RECORD BALL
  // =========================================

  void recordDelivery(const BallEvent &event, const string &bowlerId) {

    if (completed) {
      throw runtime_error("Innings already completed");
    }

    if (bowlerId.empty()) {
      throw invalid_argument("Invalid bowler ID");
    }

    validateEvent(event);

    bool legalDelivery = !event.wide && !event.noBall;

    // Check over limit before recording

    if (legalDelivery && maxOvers != -1 && legalBalls >= maxOvers * 6) {

      throw runtime_error("Over limit reached");
    }

    // Identify the batter facing this delivery

    string facingBatter = striker;

    // Calculate runs

    int extras = calculateExtras(event);

    int teamRuns = event.batterRuns + extras;

    totalRuns += teamRuns;

    // -------------------------------------
    // UPDATE BATTING STATISTICS
    // -------------------------------------

    BattingStats &batter = battingStats[facingBatter];

    batter.recordRuns(event.batterRuns);

    // No-ball counts as a ball faced.
    // Wide does not count.

    if (!event.wide) {
      batter.recordBall();
    }

    // -------------------------------------
    // UPDATE BOWLING STATISTICS
    // -------------------------------------

    BowlingStats &bowler = bowlingStats[bowlerId];

    if (legalDelivery) {
      legalBalls++;
      bowler.recordLegalBall();
    }

    // Byes and leg-byes are not charged
    // to the bowler.

    int chargedRuns = event.batterRuns + (event.wide ? 1 + event.wideRuns : 0) +
                      (event.noBall ? 1 : 0);

    bowler.recordRuns(chargedRuns);

    // -------------------------------------
    // WICKET HANDLING
    // -------------------------------------

    bool wicketFalls = event.dismissal != Dismissal::NONE &&
                       event.dismissal != Dismissal::RETIRED_HURT;

    if (wicketFalls) {

      totalWickets++;

      battingStats[event.dismissedPlayerId].recordDismissal();

      if (isBowlerCreditedDismissal(event.dismissal)) {
        bowler.recordWicket();
      }
    }

    // -------------------------------------
    // STRIKE ROTATION
    // -------------------------------------

    int completedRuns = calculateCompletedRuns(event);

    if (completedRuns % 2 == 1) {
      swap(striker, nonStriker);
    }

    // Change strike after completion of an over.

    if (legalDelivery && legalBalls % 6 == 0) {
      swap(striker, nonStriker);
    }

    // -------------------------------------
    // REMOVE DISMISSED / RETIRED BATTER
    // -------------------------------------

    if (event.dismissal != Dismissal::NONE) {

      if (event.dismissedPlayerId == striker) {
        striker.clear();
      } else if (event.dismissedPlayerId == nonStriker) {
        nonStriker.clear();
      }
    }

    // -------------------------------------
    // CHECK INNINGS COMPLETION
    // -------------------------------------

    if (totalWickets >= 10) {
      completed = true;
    }

    if (maxOvers != -1 && legalBalls >= maxOvers * 6) {

      completed = true;
    }
  }

  // =========================================
  // ADD NEXT BATTER
  // =========================================

  void setNextBatter(const string &playerId) {

    if (completed) {
      throw runtime_error("Innings completed");
    }

    if (playerId.empty()) {
      throw invalid_argument("Invalid player ID");
    }

    if (playerId == striker || playerId == nonStriker) {
      throw invalid_argument("Player is already batting");
    }

    if (striker.empty()) {
      striker = playerId;
    } else if (nonStriker.empty()) {
      nonStriker = playerId;
    } else {
      throw runtime_error("No vacant batting position");
    }
  }

  // =========================================
  // DISPLAY SCOREBOARD
  // =========================================

  void displayScore() const {

    cout << "\n========== SCOREBOARD ==========\n";

    cout << "Team: " << battingTeamId << endl;

    cout << "Score: " << totalRuns << "/" << totalWickets << endl;

    cout << "Overs: " << legalBalls / 6 << "." << legalBalls % 6 << endl;

    cout << "Striker: " << (striker.empty() ? "Vacant" : striker) << endl;

    cout << "Non-striker: " << (nonStriker.empty() ? "Vacant" : nonStriker)
         << endl;

    cout << "Status: " << (completed ? "COMPLETED" : "IN PROGRESS") << endl;

    cout << "================================\n";
  }

  // =========================================
  // DISPLAY BATTING SCORECARD
  // =========================================

  void displayBattingStats() const {

    cout << "\n============== BATTING SCORECARD ==============\n";

    cout << left << setw(15) << "Player" << setw(8) << "Runs" << setw(8)
         << "Balls" << setw(8) << "4s" << setw(8) << "6s" << setw(10) << "SR"
         << endl;

    for (const auto &entry : battingStats) {

      const BattingStats &s = entry.second;

      cout << left << setw(15) << entry.first << setw(8) << s.getRuns()
           << setw(8) << s.getBallsFaced() << setw(8) << s.getFours() << setw(8)
           << s.getSixes() << fixed << setprecision(2) << s.getStrikeRate()
           << endl;
    }

    cout << "================================================\n";
  }

  // =========================================
  // DISPLAY BOWLING SCORECARD
  // =========================================

  void displayBowlingStats() const {

    cout << "\n============== BOWLING SCORECARD ==============\n";

    cout << left << setw(15) << "Bowler" << setw(10) << "Overs" << setw(10)
         << "Runs" << setw(10) << "Wickets" << setw(10) << "Economy" << endl;

    for (const auto &entry : bowlingStats) {

      const BowlingStats &s = entry.second;

      string overs = to_string(s.getLegalBalls() / 6) + "." +
                     to_string(s.getLegalBalls() % 6);

      cout << left << setw(15) << entry.first << setw(10) << overs << setw(10)
           << s.getRunsConceded() << setw(10) << s.getWickets() << fixed
           << setprecision(2) << s.getEconomy() << endl;
    }

    cout << "================================================\n";
  }

  // =========================================
  // GETTER FUNCTIONS
  // =========================================

  int getTotalRuns() const { return totalRuns; }

  int getTotalWickets() const { return totalWickets; }

  int getLegalBalls() const { return legalBalls; }

  bool isCompleted() const { return completed; }

  string getTeamId() const { return battingTeamId; }
};

// =============================================
// 6. MAIN FUNCTION
// =============================================

int main() {

  try {

    // Create an innings with two opening batters.
    // 20 means T20, 50 means ODI, -1 means
    // no fixed over limit (Test innings).

    Innings innings("IND", "Virat", "Rohit", 20);

    BallEvent ball;

    // Ball 1: Virat scores 1 run

    ball.batterRuns = 1;
    innings.recordDelivery(ball, "Bumrah");

    // Ball 2: Rohit scores four

    ball = BallEvent{};
    ball.batterRuns = 4;
    innings.recordDelivery(ball, "Bumrah");

    // Ball 3: Dot ball

    ball = BallEvent{};
    innings.recordDelivery(ball, "Bumrah");

    // Ball 4: Wide

    ball = BallEvent{};
    ball.wide = true;
    innings.recordDelivery(ball, "Bumrah");

    // Ball 5: No-ball + 2 batter runs

    ball = BallEvent{};
    ball.noBall = true;
    ball.batterRuns = 2;
    innings.recordDelivery(ball, "Bumrah");

    // Ball 6: Rohit gets bowled

    ball = BallEvent{};
    ball.dismissal = Dismissal::BOWLED;
    ball.dismissedPlayerId = "Rohit";

    innings.recordDelivery(ball, "Bumrah");

    // Replace dismissed batter

    innings.setNextBatter("Gill");

    // Ball 7: Gill scores six

    ball = BallEvent{};
    ball.batterRuns = 6;
    innings.recordDelivery(ball, "Bumrah");

    // Ball 8: Dot ball

    ball = BallEvent{};
    innings.recordDelivery(ball, "Bumrah");

    // Display final information

    innings.displayScore();

    innings.displayBattingStats();

    innings.displayBowlingStats();

  } catch (const exception &e) {

    cerr << "\nERROR: " << e.what() << endl;

    return 1;
  }

  return 0;
}
