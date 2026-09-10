from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from .corpus import CorpusManager
from .game import ChessGame


class SessionManager:
    """Manages persistent games and shared corpus across sessions."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.corpus = CorpusManager(self.data_dir / "corpus")
        self.active_games: Dict[str, ChessGame] = {}

    def start_game(self, game_id: str = "game_default", starting_fen: Optional[str] = None) -> ChessGame:
        game = ChessGame(game_id=game_id, corpus=self.corpus, starting_fen=starting_fen)
        self.active_games[game_id] = game
        return game

    def get_game(self, game_id: str = "game_default") -> ChessGame:
        if game_id not in self.active_games:
            return self.start_game(game_id=game_id)
        return self.active_games[game_id]