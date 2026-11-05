
#include <algorithm>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;

// ========================================
// 1. ABSTRACT BASE CLASS: PERSON
// ========================================

class Person {
protected:
  string name;
  int age;

public:
  Person(string n, int a) : name(n), age(a) {}

  virtual void displayDetails() const = 0;

  virtual ~Person() = default;
};

// ========================================
// 2. PLAYER CLASS
// ========================================

class Player : public Person {
private:
  string playerId;
  int runs;
  int wickets;
  int matches;

public:
  Player(string id, string n, int a)
      : Person(n, a), playerId(id), runs(0), wickets(0), matches(0) {}

  void addRuns(int value) {
    if (value < 0)
      throw invalid_argument("Invalid runs");

    runs += value;
  }

  void addWicket() { wickets++; }

  void addMatch() { matches++; }

  string getId() const { return playerId; }

  int getRuns() const { return runs; }

  int getWickets() const { return wickets; }

  void displayDetails() const override {
    cout << "Player: " << name << " | Runs: " << runs
         << " | Wickets: " << wickets << endl;
  }
};

// ========================================
// 3. TEAM CLASS
// ========================================

class Team {
private:
  string teamId;
  string teamName;
  vector<Player> players;

public:
  Team(string id, string name) : teamId(id), teamName(name) {}

  void addPlayer(const Player &player) {

    auto it = find_if(players.begin(), players.end(), [&](const Player &p) {
      return p.getId() == player.getId();
    });

    if (it != players.end())
      throw invalid_argument("Duplicate player");

    players.push_back(player);
  }

  string getId() const { return teamId; }

  string getName() const { return teamName; }

  const vector<Player> &getPlayers() const { return players; }

  void displayTeam() const {
    cout << "\nTeam: " << teamName << endl;

    for (const auto &player : players) {
      player.displayDetails();
    }
  }
};

// ========================================
// 4. INNINGS CLASS
// ========================================

class Innings {
private:
  string battingTeamId;
  int runs = 0;
  int wickets = 0;
  int legalBalls = 0;

public:
  explicit Innings(string teamId) : battingTeamId(teamId) {}

  void addBall(int scoredRuns, bool wicket, bool legalDelivery = true) {
    if (scoredRuns < 0)
      throw invalid_argument("Invalid runs");

    runs += scoredRuns;

    if (wicket) {
      if (wickets < 10)
        wickets++;
    }

    if (legalDelivery)
      legalBalls++;
  }

  string getBattingTeamId() const { return battingTeamId; }

  int getRuns() const { return runs; }

  int getWickets() const { return wickets; }

  int getLegalBalls() const { return legalBalls; }

  void displayScore() const {
    cout << battingTeamId << ": " << runs << "/" << wickets << " ("
         << legalBalls / 6 << "." << legalBalls % 6 << " overs)" << endl;
  }
};

// ========================================
// 5. ABSTRACT MATCH CLASS
// ========================================

class Match {
protected:
  string matchId;
  string team1Id;
  string team2Id;

  vector<Innings> innings;

public:
  Match(string id, string t1, string t2)
      : matchId(id), team1Id(t1), team2Id(t2) {

    if (t1 == t2)
      throw invalid_argument("Teams must be different");
  }

  virtual string getFormat() const = 0;

  virtual int getMaxOvers() const = 0;

  virtual int getMaxInnings() const = 0;

  void addInnings(const Innings &newInnings) {

    if (innings.size() >= static_cast<size_t>(getMaxInnings())) {
      throw invalid_argument("Innings limit reached");
    }

    string battingTeam = newInnings.getBattingTeamId();

    if (battingTeam != team1Id && battingTeam != team2Id) {
      throw invalid_argument("Invalid batting team");
    }

    innings.push_back(newInnings);
  }

  void displayMatch() const {

    cout << "\nMatch ID: " << matchId << endl;
    cout << "Format: " << getFormat() << endl;

    for (const auto &inning : innings) {
      inning.displayScore();
    }
  }

  virtual ~Match() = default;
};

// ========================================
// 6. T20 MATCH
// ========================================

class T20Match : public Match {
public:
  using Match::Match;

  string getFormat() const override { return "T20"; }

  int getMaxOvers() const override { return 20; }

  int getMaxInnings() const override { return 2; }
};

// ========================================
// 7. ODI MATCH
// ========================================

class ODIMatch : public Match {
public:
  using Match::Match;

  string getFormat() const override { return "ODI"; }

  int getMaxOvers() const override { return 50; }

  int getMaxInnings() const override { return 2; }
};

// ========================================
// 8. TEST MATCH
// ========================================

class TestMatch : public Match {
public:
  using Match::Match;

  string getFormat() const override { return "TEST"; }

  int getMaxOvers() const override {
    return -1; // No fixed over limit
  }

  int getMaxInnings() const override { return 4; }
};

// ========================================
// 9. TOURNAMENT CLASS
// ========================================

class Tournament {
private:
  string tournamentId;
  string tournamentName;

  vector<Team> teams;

  vector<unique_ptr<Match>> matches;

public:
  Tournament(string id, string name) : tournamentId(id), tournamentName(name) {}

  void addTeam(const Team &team) {

    auto it = find_if(teams.begin(), teams.end(),
                      [&](const Team &t) { return t.getId() == team.getId(); });

    if (it != teams.end())
      throw invalid_argument("Duplicate team");

    teams.push_back(team);
  }

  bool hasTeam(const string &id) const {

    return any_of(teams.begin(), teams.end(),
                  [&](const Team &team) { return team.getId() == id; });
  }

  void addMatch(unique_ptr<Match> match) {

    if (!match)
      throw invalid_argument("Invalid match");

    // Validate that both teams exist
    // before scheduling the match.

    // Match will expose team IDs through getters
    // in the next implementation iteration.

    matches.push_back(move(match));
  }

  void displayTournament() const {

    cout << "\nTournament: " << tournamentName << endl;

    cout << "Total Teams: " << teams.size() << endl;

    cout << "Total Matches: " << matches.size() << endl;

    for (const auto &team : teams) {
      team.displayTeam();
    }

    for (const auto &match : matches) {
      match->displayMatch();
    }
  }
};

// ========================================
// 10. MAIN FUNCTION
// ========================================

int main() {

  try {

    Tournament tournament("T001", "College Cricket Championship");

    // Create teams

    Team india("T01", "India");
    Team australia("T02", "Australia");

    // Create players

    Player p1("P01", "Virat Kohli", 37);
    Player p2("P02", "Rohit Sharma", 39);

    Player p3("P03", "Steve Smith", 37);
    Player p4("P04", "David Warner", 39);

    // Add players to teams

    india.addPlayer(p1);
    india.addPlayer(p2);

    australia.addPlayer(p3);
    australia.addPlayer(p4);

    // Register teams

    tournament.addTeam(india);
    tournament.addTeam(australia);

    // Create T20 match

    auto match = make_unique<T20Match>("M001", "T01", "T02");

    // First innings

    Innings first("T01");

    first.addBall(4, false);
    first.addBall(6, false);
    first.addBall(1, false);
    first.addBall(0, false);
    first.addBall(2, false);
    first.addBall(1, false);

    match->addInnings(first);

    // Second innings

    Innings second("T02");

    second.addBall(1, false);
    second.addBall(4, false);
    second.addBall(0, false);

    match->addInnings(second);

    // Register match

    tournament.addMatch(move(match));

    // Display everything

    tournament.displayTournament();

  } catch (const exception &e) {
    cerr << "Error: " << e.what() << endl;
    return 1;
  }

  return 0;
}
