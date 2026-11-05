
const API = {
    core: "/api/core",
    tournament: "/api/tournament"
};

const $ = (id) => document.getElementById(id);

let tournaments = [];
let teams = [];
let activeTournamentId = "";
let tournamentTeams = [];
let fixtures = [];
let toastTimer;

// -------------------- COMMON HELPERS --------------------

function notify(message, isError = false) {
    const el = $("toast");
    el.textContent = message;
    el.className = `toast show${isError ? " error" : ""}`;

    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        el.className = "toast";
    }, 3200);
}

function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    }[c]));
}

async function request(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        }
    });

    const text = await response.text();
    let data = {};

    try {
        data = text ? JSON.parse(text) : {};
    } catch {
        data = { message: text };
    }

    if (!response.ok) {
        throw new Error(
            data.error || data.message || `Request failed (${response.status})`
        );
    }

    return data;
}

const post = (url, body) =>
    request(url, {
        method: "POST",
        body: JSON.stringify(body)
    });

// -------------------- NAVIGATION --------------------

function showPage(page) {
    document.querySelectorAll(".page").forEach(p => {
        p.classList.toggle("active", p.id === `page-${page}`);
    });

    document.querySelectorAll(".nav-link").forEach(button => {
        button.classList.toggle("active", button.dataset.page === page);
    });

    const titles = {
        dashboard: "Dashboard",
        tournaments: "Tournaments",
        teams: "Teams & Players",
        fixtures: "Fixtures & Results",
        standings: "Points Table"
    };

    $("pageTitle").textContent = titles[page] || "Dashboard";
    $("sidebar").classList.remove("open");

    if (page === "teams") loadTournamentTeams();
    if (page === "fixtures") loadFixtures();
    if (page === "standings") loadStandings();
}

function activeTournament() {
    return tournaments.find(
        t => String(t.id) === String(activeTournamentId)
    );
}

function tournamentName() {
    return activeTournament()?.name || "No tournament selected";
}

function updateActiveLabels() {
    ["teamsActiveName", "fixturesActiveName", "standingsActiveName"].forEach(id => {
        $(id).textContent = tournamentName();
    });

    $("openTeamsFromTournament").disabled = !activeTournamentId;

    $("addTeamToTournament").disabled =
        !activeTournamentId || !$("availableTeam").value;

    $("generateFixtures").disabled =
        !activeTournamentId || tournamentTeams.length < 2;
}

function setActiveTournament(id) {
    activeTournamentId = id ? String(id) : "";
    $("activeTournament").value = activeTournamentId;

    updateActiveLabels();
    renderActiveSummary();

    if (activeTournamentId) {
        loadTournamentTeams();
        loadFixtures();
        loadStandings();
    } else {
        tournamentTeams = [];
        fixtures = [];
        renderTournamentTeams();
    }
}

// -------------------- TOURNAMENTS --------------------

function renderActiveSummary() {
    const tournament = activeTournament();
    const box = $("activeTournamentSummary");

    if (!tournament) {
        box.className = "selection-summary empty-state";
        box.textContent = "Select a tournament to begin managing it.";
        return;
    }

    box.className = "selection-summary";
    box.innerHTML = `
    <strong>${esc(tournament.name)}</strong>
    <span>
      ${esc(tournament.format || "Format not set")}
      · ${esc(tournament.overs_per_innings ?? "—")} overs
      · ID ${esc(tournament.id)}
    </span>
  `;
}

function renderTournamentSelect() {
    const select = $("activeTournament");
    const previous = activeTournamentId;

    select.innerHTML = `
    <option value="">Choose a tournament</option>
    ${tournaments.map(t => `
      <option value="${esc(t.id)}">
        ${esc(t.name)} (${esc(t.format || "Format")})
      </option>
    `).join("")}
  `;

    const keep = tournaments.some(t => String(t.id) === previous);

    setActiveTournament(
        keep ? previous : (tournaments[0] ? String(tournaments[0].id) : "")
    );
}

function renderTournamentCards(targetId) {
    const target = $(targetId);

    if (!tournaments.length) {
        target.innerHTML = `
      <div class="empty-state">
        No tournaments yet. Create your first tournament above.
      </div>
    `;
        return;
    }

    target.innerHTML = tournaments.map(t => `
    <article class="tournament-card">
      <h3>${esc(t.name)}</h3>

      <div class="tournament-meta">
        <span class="pill">${esc(t.format || "Format")}</span>
        <span class="pill">${esc(t.overs_per_innings ?? "—")} overs</span>
        <span class="pill">ID ${esc(t.id)}</span>
      </div>

      <button class="btn btn-secondary btn-small"
              data-select-tournament="${esc(t.id)}">
        Open tournament →
      </button>
    </article>
  `).join("");

    target.querySelectorAll("[data-select-tournament]").forEach(button => {
        button.addEventListener("click", () => {
            setActiveTournament(button.dataset.selectTournament);
            showPage("teams");
        });
    });
}

async function loadTournaments() {
    const data = await request(`${API.tournament}/tournaments`);

    tournaments = Array.isArray(data)
        ? data
        : (data.tournaments || data.data || []);

    renderTournamentSelect();
    renderTournamentCards("tournamentList");
    renderTournamentCards("dashboardTournamentList");

    $("dashTournamentCount").textContent = tournaments.length;
}

// -------------------- TEAMS --------------------

async function loadTeams() {
    const data = await request(`${API.core}/teams`);

    teams = Array.isArray(data)
        ? data
        : (data.teams || data.data || []);

    $("dashTeamCount").textContent = teams.length;

    $("availableTeam").innerHTML = `
    <option value="">Choose a registered team</option>
    ${teams.map(t => `
      <option value="${esc(t.id)}">${esc(t.name)}</option>
    `).join("")}
  `;

    updateActiveLabels();
}

async function loadDashboard() {
    try {
        const [playersData, matchesData] = await Promise.all([
            request(`${API.core}/players`),
            request(`${API.core}/matches`)
        ]);

        const players = Array.isArray(playersData)
            ? playersData
            : (playersData.players || playersData.data || []);

        const matches = Array.isArray(matchesData)
            ? matchesData
            : (matchesData.matches || matchesData.data || []);

        $("dashPlayerCount").textContent = players.length;
        $("dashMatchCount").textContent = matches.length;
    } catch {
        $("dashPlayerCount").textContent = "—";
        $("dashMatchCount").textContent = "—";
    }
}

async function refreshAll() {
    try {
        await Promise.all([
            loadTournaments(),
            loadTeams()
        ]);

        await loadDashboard();

        $("connectionDot").classList.add("online");
        $("connectionText").textContent = "Backend connected";
    } catch (error) {
        $("connectionDot").classList.remove("online");
        $("connectionText").textContent = "Backend connection issue";
        notify(error.message, true);
    }
}

// -------------------- CREATE TOURNAMENT --------------------

$("tournamentFormat").addEventListener("change", () => {
    $("tournamentOvers").value =
        $("tournamentFormat").value === "ODI" ? 50 : 20;
});

$("tournamentForm").addEventListener("submit", async event => {
    event.preventDefault();

    const format = $("tournamentFormat").value;

    const body = {
        name: $("tournamentName").value.trim(),
        format,
        overs_per_innings: Number($("tournamentOvers").value)
    };

    try {
        const result = await post(`${API.tournament}/tournaments`, body);

        $("tournamentName").value = "";

        await loadTournaments();

        const createdId =
            result.id ||
            result.tournament_id ||
            result.tournament?.id;

        if (createdId) {
            setActiveTournament(createdId);
        }

        notify("Tournament created. Now add teams to it.");
        showPage("teams");
    } catch (error) {
        notify(error.message, true);
    }
});

$("activeTournament").addEventListener("change", event => {
    setActiveTournament(event.target.value);
});

$("openTeamsFromTournament").addEventListener("click", () => {
    showPage("teams");
});

$("refreshTournaments").addEventListener("click", async () => {
    try {
        await loadTournaments();
        notify("Tournament list refreshed.");
    } catch (error) {
        notify(error.message, true);
    }
});

// -------------------- CREATE TEAM --------------------

$("teamForm").addEventListener("submit", async event => {
    event.preventDefault();

    const name = $("teamName").value.trim();

    if (!name) return;

    try {
        await post(`${API.core}/teams`, { name });

        $("teamName").value = "";

        await loadTeams();

        notify("Team registered. Select it and add it to the tournament.");
    } catch (error) {
        notify(error.message, true);
    }
});

$("availableTeam").addEventListener("change", updateActiveLabels);

$("addTeamToTournament").addEventListener("click", async () => {
    if (!activeTournamentId) {
        return notify("Create or select a tournament first.", true);
    }

    const teamId = $("availableTeam").value;

    if (!teamId) {
        return notify("Choose a team first.", true);
    }

    try {
        await post(
            `${API.tournament}/tournaments/${activeTournamentId}/teams`,
            { team_id: Number(teamId) }
        );

        await loadTournamentTeams();

        notify("Team added to this tournament.");
    } catch (error) {
        notify(error.message, true);
    }
});

// -------------------- TOURNAMENT TEAMS --------------------

async function loadTournamentTeams() {
    if (!activeTournamentId) {
        tournamentTeams = [];
        renderTournamentTeams();
        return;
    }

    try {
        const data = await request(
            `${API.tournament}/tournaments/${activeTournamentId}/teams`
        );

        tournamentTeams = Array.isArray(data)
            ? data
            : (data.teams || data.data || []);

        renderTournamentTeams();
    } catch (error) {
        $("tournamentTeamList").innerHTML = `
      <div class="empty-state">
        Could not load tournament teams: ${esc(error.message)}
      </div>
    `;

        tournamentTeams = [];
        updateActiveLabels();
    }
}

function renderTournamentTeams() {
    const box = $("tournamentTeamList");

    if (!activeTournamentId) {
        box.innerHTML = `
      <div class="empty-state">Select a tournament first.</div>
    `;
    } else if (!tournamentTeams.length) {
        box.innerHTML = `
      <div class="empty-state">
        No teams added yet. Register a team or choose one above,
        then add it to the tournament.
      </div>
    `;
    } else {
        box.innerHTML = tournamentTeams.map(t => {
            const teamId = t.team_id ?? t.id;

            return `
        <div class="team-row">
          <div>
            <strong>${esc(t.name || t.team_name || `Team ${teamId}`)}</strong>
            <small>Team ID: ${esc(teamId ?? "—")}</small>
          </div>
          <span class="pill">Added</span>
        </div>
      `;
        }).join("");
    }

    const select = $("squadTeam");

    select.innerHTML = tournamentTeams.length
        ? `
      <option value="">Choose a tournament team</option>
      ${tournamentTeams.map(t => {
            const id = t.team_id ?? t.id;

            return `
          <option value="${esc(id)}">
            ${esc(t.name || t.team_name || `Team ${id}`)}
          </option>
        `;
        }).join("")}
    `
        : `<option value="">Add a team to the tournament first</option>`;

    $("addPlayerButton").disabled = true;
    $("squadCount").textContent = "0 players";

    $("squadTable").innerHTML = `
    <tr>
      <td colspan="6" class="table-empty">
        Choose a team to view its squad.
      </td>
    </tr>
  `;

    updateActiveLabels();
}

// -------------------- PLAYERS --------------------

$("squadTeam").addEventListener("change", async () => {
    $("addPlayerButton").disabled = !$("squadTeam").value;
    await loadSquad();
});

async function loadSquad() {
    const teamId = $("squadTeam").value;

    if (!teamId) return;

    try {
        const data = await request(`${API.core}/teams/${teamId}/players`);

        const players = Array.isArray(data)
            ? data
            : (data.players || data.data || []);

        $("squadCount").textContent =
            `${players.length} player${players.length === 1 ? "" : "s"}`;

        $("squadTable").innerHTML = players.length
            ? players.map((p, index) => `
          <tr>
            <td>${index + 1}</td>
            <td><strong>${esc(p.name)}</strong></td>
            <td>${esc(p.role || "—")}</td>
            <td>${esc(p.jersey_number ?? "—")}</td>
            <td>${esc(p.batting_style || "—")}</td>
            <td>${esc(p.bowling_style || "—")}</td>
          </tr>
        `).join("")
            : `
          <tr>
            <td colspan="6" class="table-empty">
              No players in this squad yet. Add the first player above.
            </td>
          </tr>
        `;
    } catch (error) {
        $("squadTable").innerHTML = `
      <tr>
        <td colspan="6" class="table-empty">${esc(error.message)}</td>
      </tr>
    `;
    }
}

$("playerForm").addEventListener("submit", async event => {
    event.preventDefault();

    const teamId = $("squadTeam").value;

    if (!teamId) {
        return notify("Choose a tournament team first.", true);
    }

    const jersey = $("jerseyNumber").value;

    const body = {
        name: $("playerName").value.trim(),
        role: $("playerRole").value,
        jersey_number: jersey ? Number(jersey) : null,
        batting_style: $("battingStyle").value,
        bowling_style: $("bowlingStyle").value.trim()
    };

    try {
        await post(`${API.core}/teams/${teamId}/players`, body);

        $("playerForm").reset();

        await loadSquad();

        notify("Player added to the selected team's squad.");
    } catch (error) {
        notify(error.message, true);
    }
});

// -------------------- FIXTURES --------------------

$("generateFixtures").addEventListener("click", async () => {
    if (!activeTournamentId) {
        return notify("Select a tournament first.", true);
    }

    if (tournamentTeams.length < 2) {
        return notify("Add at least two teams before generating fixtures.", true);
    }

    if (!confirm("Generate the round-robin fixtures for this tournament?")) {
        return;
    }

    try {
        await post(
            `${API.tournament}/tournaments/${activeTournamentId}/generate-fixtures`,
            {}
        );

        await loadFixtures();

        notify("Fixtures generated successfully.");
    } catch (error) {
        notify(error.message, true);
    }
});

async function loadFixtures() {
    if (!activeTournamentId) {
        $("fixtureList").innerHTML = `
      <div class="empty-state">
        Select a tournament to view fixtures.
      </div>
    `;

        $("resultFixture").innerHTML =
            `<option value="">Choose a fixture</option>`;

        $("saveResult").disabled = true;
        return;
    }

    try {
        const data = await request(
            `${API.tournament}/tournaments/${activeTournamentId}/fixtures`
        );

        fixtures = Array.isArray(data)
            ? data
            : (data.fixtures || data.data || []);

        renderFixtures();
    } catch (error) {
        $("fixtureList").innerHTML = `
      <div class="empty-state">${esc(error.message)}</div>
    `;
    }
}

function renderFixtures() {
    const box = $("fixtureList");

    if (!fixtures.length) {
        box.innerHTML = `
      <div class="empty-state">
        No fixtures yet. Add at least two teams, then generate fixtures.
      </div>
    `;
    } else {
        box.innerHTML = fixtures.map(f => {
            const completed = String(f.status || "").toLowerCase() === "completed";

            return `
        <div class="fixture-row">
          <div>
            <div class="fixture-teams">
              ${esc(f.team1)}
              <span style="color:#9aa4b4">vs</span>
              ${esc(f.team2)}
            </div>
            <div class="fixture-sub">
              Round ${esc(f.round_number ?? "—")}
              · Fixture ${esc(f.fixture_id)}
            </div>
          </div>

          <span class="status ${completed ? "completed" : ""}">
            ${completed ? "Completed" : "Upcoming"}
          </span>
        </div>
      `;
        }).join("");
    }

    const pending = fixtures.filter(
        f => String(f.status || "").toLowerCase() !== "completed"
    );

    $("resultFixture").innerHTML = `
    <option value="">Choose an upcoming fixture</option>
    ${pending.map(f => `
      <option value="${esc(f.fixture_id)}">
        ${esc(f.team1)} vs ${esc(f.team2)} · #${esc(f.fixture_id)}
      </option>
    `).join("")}
  `;

    $("saveResult").disabled = pending.length === 0;
}

$("refreshFixtures").addEventListener("click", loadFixtures);

$("resultFixture").addEventListener("change", () => {
    $("saveResult").disabled = !$("resultFixture").value;
});

// -------------------- SAVE MATCH RESULT --------------------

$("resultForm").addEventListener("submit", async event => {
    event.preventDefault();

    const fixtureId = $("resultFixture").value;

    if (!fixtureId) {
        return notify("Choose a fixture first.", true);
    }

    const body = {
        runs1: Number($("runs1").value),
        runs2: Number($("runs2").value)
    };

    try {
        await post(
            `${API.tournament}/tournaments/${activeTournamentId}/fixtures/${fixtureId}/result`,
            body
        );

        $("resultForm").reset();

        await Promise.all([
            loadFixtures(),
            loadStandings()
        ]);

        notify("Match result saved.");
    } catch (error) {
        notify(error.message, true);
    }
});

// -------------------- POINTS TABLE --------------------

async function loadStandings() {
    if (!activeTournamentId) {
        $("standingsTable").innerHTML = `
      <tr>
        <td colspan="7" class="table-empty">
          Select a tournament to view standings.
        </td>
      </tr>
    `;
        return;
    }

    try {
        const data = await request(
            `${API.tournament}/tournaments/${activeTournamentId}/standings`
        );

        const rows = data.standings || [];

        $("standingsTable").innerHTML = rows.length
            ? rows.map(r => `
          <tr>
            <td><strong>${esc(r.position)}</strong></td>
            <td><strong>${esc(r.team)}</strong></td>
            <td>${esc(r.played ?? 0)}</td>
            <td>${esc(r.won ?? 0)}</td>
            <td>${esc(r.lost ?? 0)}</td>
            <td>${esc(r.tied ?? 0)}</td>
            <td><strong>${esc(r.points ?? 0)}</strong></td>
          </tr>
        `).join("")
            : `
          <tr>
            <td colspan="7" class="table-empty">
              No standings yet. Record match results to populate the table.
            </td>
          </tr>
        `;
    } catch (error) {
        $("standingsTable").innerHTML = `
      <tr>
        <td colspan="7" class="table-empty">
          ${esc(error.message)}
        </td>
      </tr>
    `;
    }
}

$("refreshStandings").addEventListener("click", loadStandings);

// -------------------- BUTTON EVENTS --------------------

document.querySelectorAll(".nav-link").forEach(button => {
    button.addEventListener("click", () => {
        showPage(button.dataset.page);
    });
});

document.querySelectorAll("[data-goto]").forEach(button => {
    button.addEventListener("click", () => {
        showPage(button.dataset.goto);
    });
});

$("menuButton").addEventListener("click", () => {
    $("sidebar").classList.toggle("open");
});

// -------------------- START APPLICATION --------------------

document.addEventListener("DOMContentLoaded", async () => {
    await refreshAll();
});
