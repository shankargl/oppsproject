
#include "include/json.hpp"
#include <algorithm>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>


using namespace std;
using json = nlohmann::json;

struct BattingStats {
  int runs = 0, balls = 0, fours = 0, sixes = 0;
};

struct BowlingStats {
  int legalBalls = 0, runsConceded = 0, wickets = 0;
  int wides = 0, noBalls = 0;
};

class ScoringEngine {
private:
  map<int, BattingStats> batting;
  map<int, BowlingStats> bowling;
  int totalRuns = 0, wickets = 0, legalBalls = 0, totalExtras = 0;
  json deliveryLog = json::array();

  static int getInteger(const json &item, const string &key) {
    if (!item.contains(key) || !item[key].is_number_integer())
      throw invalid_argument("Missing or invalid field: " + key);
    return item[key].get<int>();
  }

public:
  json calculate(const json &request) {
    if (!request.contains("deliveries") || !request["deliveries"].is_array())
      throw invalid_argument("deliveries must be a JSON array.");

    if (!request.contains("overs_limit") ||
        !request["overs_limit"].is_number_integer())
      throw invalid_argument("overs_limit must be an integer.");

    int oversLimit = request["overs_limit"].get<int>();

    if (oversLimit <= 0 || oversLimit > 90)
      throw invalid_argument("overs_limit must be between 1 and 90.");

    int sequence = 0;

    for (const auto &event : request["deliveries"]) {
      sequence++;

      int batterId = getInteger(event, "batter_id");
      int bowlerId = getInteger(event, "bowler_id");
      int batterRuns = getInteger(event, "batter_runs");
      int extrasRuns = getInteger(event, "extras_runs");

      if (batterId <= 0 || bowlerId <= 0 || batterRuns < 0 || extrasRuns < 0)
        throw invalid_argument("Invalid player ID or run value.");

      string extrasType = event.value("extras_type", "none");
      string wicketType = event.value("wicket_type", "none");

      const vector<string> validExtras = {"none", "wide", "no_ball", "bye",
                                          "leg_bye"};

      const vector<string> validWickets = {
          "none",    "bowled",     "caught",  "lbw",
          "stumped", "hit_wicket", "run_out", "retired_hurt"};

      if (find(validExtras.begin(), validExtras.end(), extrasType) ==
          validExtras.end())
        throw invalid_argument("Invalid extras_type.");

      if (find(validWickets.begin(), validWickets.end(), wicketType) ==
          validWickets.end())
        throw invalid_argument("Invalid wicket_type.");

      if (extrasType == "none" && extrasRuns != 0)
        throw invalid_argument("No extras are allowed for extras_type none.");

      if ((extrasType == "wide" || extrasType == "no_ball") && extrasRuns < 1)
        throw invalid_argument(
            "Wide/no-ball must include at least one extra run.");

      if ((extrasType == "bye" || extrasType == "leg_bye") && batterRuns != 0)
        throw invalid_argument("Byes and leg-byes cannot be batter runs.");

      int dismissedPlayerId = 0;

      if (wicketType != "none") {
        dismissedPlayerId = getInteger(event, "dismissed_player_id");

        if (dismissedPlayerId <= 0)
          throw invalid_argument("Dismissed player ID must be positive.");
      }

      bool isWide = extrasType == "wide";
      bool isNoBall = extrasType == "no_ball";
      bool isLegal = !isWide && !isNoBall;

      int ballRuns = batterRuns + extrasRuns;

      totalRuns += ballRuns;
      totalExtras += extrasRuns;

      BattingStats &bat = batting[batterId];
      BowlingStats &bowl = bowling[bowlerId];

      bat.runs += batterRuns;

      if (!isWide)
        bat.balls++;

      if (batterRuns == 4)
        bat.fours++;
      if (batterRuns == 6)
        bat.sixes++;

      if (isLegal) {
        legalBalls++;
        bowl.legalBalls++;
      }

      if (isWide)
        bowl.wides += extrasRuns;
      if (isNoBall)
        bowl.noBalls += extrasRuns;

      // Byes and leg-byes are not charged to the bowler.
      if (extrasType == "wide" || extrasType == "no_ball" ||
          extrasType == "none")
        bowl.runsConceded += ballRuns;

      bool isWicket = wicketType != "none" && wicketType != "retired_hurt";

      if (isWicket) {
        wickets++;

        if (wicketType != "run_out")
          bowl.wickets++;
      }

      if (legalBalls > oversLimit * 6)
        throw invalid_argument("Deliveries exceed the overs limit.");

      deliveryLog.push_back(
          {{"sequence", sequence},
           {"over_number", legalBalls == 0 ? 0 : (legalBalls - 1) / 6},
           {"legal_ball_number", legalBalls},
           {"batter_id", batterId},
           {"bowler_id", bowlerId},
           {"batter_runs", batterRuns},
           {"extras_type", extrasType},
           {"extras_runs", extrasRuns},
           {"total_runs", ballRuns},
           {"is_legal", isLegal},
           {"wicket_type", wicketType},
           {"dismissed_player_id",
            dismissedPlayerId == 0 ? json(nullptr) : json(dismissedPlayerId)}});
    }

    json battingCard = json::array();

    for (const auto &item : batting) {
      battingCard.push_back({{"player_id", item.first},
                             {"runs", item.second.runs},
                             {"balls", item.second.balls},
                             {"fours", item.second.fours},
                             {"sixes", item.second.sixes}});
    }

    json bowlingCard = json::array();

    for (const auto &item : bowling) {
      const BowlingStats &stats = item.second;
      double overs = stats.legalBalls / 6.0;
      double economy = stats.legalBalls == 0 ? 0.0 : stats.runsConceded / overs;

      bowlingCard.push_back({{"player_id", item.first},
                             {"legal_balls", stats.legalBalls},
                             {"runs_conceded", stats.runsConceded},
                             {"wickets", stats.wickets},
                             {"wides", stats.wides},
                             {"no_balls", stats.noBalls},
                             {"economy", economy}});
    }

    return {
        {"status", "success"},
        {"total_runs", totalRuns},
        {"wickets", wickets},
        {"legal_balls", legalBalls},
        {"overs", to_string(legalBalls / 6) + "." + to_string(legalBalls % 6)},
        {"extras", totalExtras},
        {"batting_card", battingCard},
        {"bowling_card", bowlingCard},
        {"deliveries", deliveryLog}};
  }
};

int main() {
  string input;
  getline(cin, input);

  try {
    json request = json::parse(input);
    ScoringEngine engine;
    cout << engine.calculate(request).dump() << endl;
  } catch (const exception &error) {
    cout << json({{"status", "error"}, {"message", error.what()}}).dump()
         << endl;
    return 1;
  }

  return 0;
}
