#include <algorithm>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>


#include "include/json.hpp"

using namespace std;
using json = nlohmann::json;

// -------------------- MATCH --------------------

class Match {
private:
  string team1;
  string team2;
  int runs1;
  int runs2;

public:
  Match(string t1, string t2, int r1, int r2)
      : team1(t1), team2(t2), runs1(r1), runs2(r2) {

    if (team1.empty() || team2.empty()) {
      throw invalid_argument("Team names cannot be empty.");
    }

    if (team1 == team2) {
      throw invalid_argument("A team cannot play against itself.");
    }

    if (runs1 < 0 || runs2 < 0) {
      throw invalid_argument("Runs cannot be negative.");
    }
  }

  string getTeam1() const { return team1; }
  string getTeam2() const { return team2; }
  int getRuns1() const { return runs1; }
  int getRuns2() const { return runs2; }

  string getWinner() const {
    if (runs1 > runs2)
      return team1;
    if (runs2 > runs1)
      return team2;
    return "Tie";
  }

  string getResult() const {
    if (runs1 > runs2) {
      return team1 + " won by " + to_string(runs1 - runs2) + " runs.";
    }

    if (runs2 > runs1) {
      return team2 + " won by " + to_string(runs2 - runs1) + " runs.";
    }

    return "Match tied.";
  }
};

// -------------------- POINTS TABLE --------------------

struct TeamRecord {
  string name;
  int played = 0;
  int won = 0;
  int lost = 0;
  int tied = 0;
  int points = 0;
};

class PointsTable {
private:
  map<string, TeamRecord> records;

public:
  void registerTeam(const string &name) {
    if (name.empty()) {
      throw invalid_argument("Team name cannot be empty.");
    }

    if (records.find(name) == records.end()) {
      TeamRecord record;
      record.name = name;
      records[name] = record;
    }
  }

  void recordMatch(const Match &match) {
    registerTeam(match.getTeam1());
    registerTeam(match.getTeam2());

    TeamRecord &first = records[match.getTeam1()];
    TeamRecord &second = records[match.getTeam2()];

    first.played++;
    second.played++;

    if (match.getRuns1() > match.getRuns2()) {
      first.won++;
      first.points += 2;
      second.lost++;
    } else if (match.getRuns2() > match.getRuns1()) {
      second.won++;
      second.points += 2;
      first.lost++;
    } else {
      first.tied++;
      second.tied++;
      first.points++;
      second.points++;
    }
  }

  json getStandings() const {
    vector<TeamRecord> table;

    for (const auto &item : records) {
      table.push_back(item.second);
    }

    sort(table.begin(), table.end(),
         [](const TeamRecord &a, const TeamRecord &b) {
           if (a.points != b.points) {
             return a.points > b.points;
           }

           if (a.won != b.won) {
             return a.won > b.won;
           }

           return a.name < b.name;
         });

    json result = json::array();

    for (size_t i = 0; i < table.size(); i++) {
      const TeamRecord &team = table[i];

      result.push_back({{"position", static_cast<int>(i + 1)},
                        {"team", team.name},
                        {"played", team.played},
                        {"won", team.won},
                        {"lost", team.lost},
                        {"tied", team.tied},
                        {"points", team.points}});
    }

    return result;
  }
};

// -------------------- COMMAND PROCESSOR --------------------

class CommandProcessor {
private:
  json getFormats() const {
    return {{"status", "success"}, {"formats", {"T20", "ODI", "TEST"}}};
  }

  Match createMatch(const json &request) const {
    if (!request.contains("team1") || !request.contains("team2") ||
        !request.contains("runs1") || !request.contains("runs2")) {
      throw invalid_argument("Required fields: team1, team2, runs1, runs2.");
    }

    if (!request["team1"].is_string() || !request["team2"].is_string() ||
        !request["runs1"].is_number_integer() ||
        !request["runs2"].is_number_integer()) {
      throw invalid_argument("Invalid field data types.");
    }

    return Match(request["team1"].get<string>(), request["team2"].get<string>(),
                 request["runs1"].get<int>(), request["runs2"].get<int>());
  }

public:
  json process(const json &request) const {
    try {
      if (!request.contains("action") || !request["action"].is_string()) {
        throw invalid_argument("Request must contain a string action.");
      }

      string action = request["action"].get<string>();

      if (action == "get_formats") {
        return getFormats();
      }

      if (action == "calculate_match_result") {
        Match match = createMatch(request);

        return {{"status", "success"},        {"team1", match.getTeam1()},
                {"team2", match.getTeam2()},  {"runs1", match.getRuns1()},
                {"runs2", match.getRuns2()},  {"winner", match.getWinner()},
                {"result", match.getResult()}};
      }

      if (action == "calculate_points") {
        if (!request.contains("matches") || !request["matches"].is_array()) {
          throw invalid_argument("The matches field must be a JSON array.");
        }

        PointsTable table;

        for (const auto &item : request["matches"]) {
          Match match = createMatch(item);
          table.recordMatch(match);
        }

        return {{"status", "success"}, {"standings", table.getStandings()}};
      }

      throw invalid_argument("Unknown action: " + action);
    } catch (const exception &error) {
      return {{"status", "error"}, {"message", error.what()}};
    }
  }
};

// -------------------- MAIN --------------------

int main() {
  string input;

  // Read one JSON request from standard input.
  getline(cin, input);

  try {
    json request = json::parse(input);

    CommandProcessor processor;
    json response = processor.process(request);

    // Print only JSON to standard output.
    cout << response.dump() << endl;
  } catch (const exception &error) {
    json response = {
        {"status", "error"},
        {"message", string("Invalid JSON request: ") + error.what()}};

    cout << response.dump() << endl;
    return 1;
  }

  return 0;
}