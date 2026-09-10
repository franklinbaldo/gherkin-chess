from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .corpus import CorpusManager
from .game import ChessGame
from . import __version__


class SessionManager:
    """Manages persistent games and shared corpus across sessions."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.games_dir = self.data_dir / "games"
        self.games_dir.mkdir(parents=True, exist_ok=True)
        self.corpus = CorpusManager(self.data_dir / "corpus")
        self.active_games: Dict[str, ChessGame] = {}

    def start_game(self, game_id: str = "game_default", starting_fen: Optional[str] = None) -> ChessGame:
        game = ChessGame(game_id=game_id, corpus=self.corpus, starting_fen=starting_fen)
        self.active_games[game_id] = game
        self.save_game(game)
        return game

    def save_game(self, game: ChessGame):
        """Persist game state to disk."""
        data = {
            "game_id": game.game_id,
            "app_version": __version__,
            "created_at": game.created_at,
            "fen": game.board.fen(),
            "turn": "white" if game.board.turn else "black",
            "fullmove_number": game.board.fullmove_number,
            "is_game_over": game.board.is_game_over(),
            "result": game.board.result() if game.board.is_game_over() else None,
            "history": [
                {
                    "move_number": m.move_number,
                    "turn": m.turn,
                    "uci": m.uci,
                    "san": m.san,
                    "pre_fen": m.pre_fen,
                    "post_fen": m.post_fen,
                    "timestamp": m.timestamp,
                    "gherkin": m.gherkin,
                    "epistemic_mode": m.epistemic_mode,
                    "applied_scenario": m.applied_scenario,
                    "origin_fen": m.origin_fen,
                    "diverged_from": m.diverged_from,
                    "divergence_reason": m.divergence_reason,
                }
                for m in game.history
            ],
        }
        file_path = self.games_dir / f"{game.game_id}.json"
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_game(self, game_id: str = "game_default") -> ChessGame:
        if game_id in self.active_games:
            return self.active_games[game_id]
        file_path = self.games_dir / f"{game_id}.json"
        if file_path.exists():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                game = ChessGame(game_id=game_id, corpus=self.corpus, starting_fen=data.get("fen"))
                self.active_games[game_id] = game
                return game
            except Exception:
                pass
        return self.start_game(game_id=game_id)

    def list_saved_games(self) -> List[Dict[str, Any]]:
        """List all saved games ordered by most recently modified."""
        games = []
        for p in sorted(self.games_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                games.append(data)
            except Exception:
                pass
        return games