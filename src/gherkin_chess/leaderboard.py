from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from openskill.models import PlackettLuce


@dataclass
class PlayerStat:
    name: str
    model_id: str
    mu: float = 25.0
    sigma: float = 8.333333333333334
    matches: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0

    @property
    def ordinal(self) -> float:
        """Conservative skill rating (mu - 3*sigma)."""
        return max(0.0, self.mu - 3 * self.sigma)


class LeaderboardManager:
    """
    Manages Bayesian skill ratings (OpenSkill Plackett-Luce) and match history
    for agents playing in the tournament ladder.
    """

    def __init__(self, data_path: Path):
        self.data_path = Path(data_path)
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.model = PlackettLuce()
        self.players: Dict[str, PlayerStat] = {}
        self.matches: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if self.data_path.exists():
            try:
                data = json.loads(self.data_path.read_text(encoding="utf-8"))
                for p in data.get("players", []):
                    self.players[p["name"]] = PlayerStat(**p)
                self.matches = data.get("matches", [])
            except Exception:
                pass

    def save(self):
        data = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "players": [asdict(p) for p in self.players.values()],
            "matches": self.matches[-500:],  # preserve latest 500 matches
        }
        self.data_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_or_create_player(self, name: str, model_id: str) -> PlayerStat:
        if name not in self.players:
            self.players[name] = PlayerStat(name=name, model_id=model_id)
        return self.players[name]

    def record_match(
        self,
        player_white: str,
        player_black: str,
        model_white: str,
        model_black: str,
        outcome: str,  # "white" | "black" | "draw"
        game_id: str,
        plies: int,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Record match outcome and update OpenSkill Bayesian ratings.
        outcome: "white" -> White wins
                 "black" -> Black wins
                 "draw"  -> Tie
        """
        pw = self.get_or_create_player(player_white, model_white)
        pb = self.get_or_create_player(player_black, model_black)

        rw = self.model.rating(mu=pw.mu, sigma=pw.sigma)
        rb = self.model.rating(mu=pb.mu, sigma=pb.sigma)

        pw.matches += 1
        pb.matches += 1

        if outcome == "white":
            pw.wins += 1
            pb.losses += 1
            ranks = [1, 2]
        elif outcome == "black":
            pb.wins += 1
            pw.losses += 1
            ranks = [2, 1]
        else:
            pw.draws += 1
            pb.draws += 1
            ranks = [1, 1]

        # Update OpenSkill ratings
        [[new_rw], [new_rb]] = self.model.rate([[rw], [rb]], ranks=ranks)
        pw.mu, pw.sigma = new_rw.mu, new_rw.sigma
        pb.mu, pb.sigma = new_rb.mu, new_rb.sigma

        match_record = {
            "game_id": game_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "white": player_white,
            "black": player_black,
            "outcome": outcome,
            "plies": plies,
            "details": details or {},
        }
        self.matches.append(match_record)
        self.save()

    def get_standings(self) -> List[Dict[str, Any]]:
        """Return leaderboard ordered descending by conservative ordinal rating."""
        sorted_players = sorted(self.players.values(), key=lambda p: (p.ordinal, p.mu), reverse=True)
        standings = []
        for rank, p in enumerate(sorted_players, 1):
            standings.append({
                "rank": rank,
                "name": p.name,
                "model_id": p.model_id,
                "ordinal": round(p.ordinal, 2),
                "mu": round(p.mu, 2),
                "sigma": round(p.sigma, 2),
                "matches": p.matches,
                "wins": p.wins,
                "draws": p.draws,
                "losses": p.losses,
                "win_rate": round((p.wins / max(1, p.matches)) * 100, 1),
            })
        return standings