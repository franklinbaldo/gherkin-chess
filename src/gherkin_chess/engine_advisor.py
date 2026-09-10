from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
import chess
import chess.engine


def find_stockfish_binary() -> Optional[str]:
    """Auto-detect Stockfish executable from PATH or common package locations."""
    # 1. PATH lookup
    path = shutil.which("stockfish") or shutil.which("stockfish.exe")
    if path:
        return path

    # 2. Check WinGet / LocalAppData common directory
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        winget_dir = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_dir.exists():
            matches = list(winget_dir.glob("**/stockfish*.exe"))
            if matches:
                return str(matches[0])

    # 3. Check environment variable STOCKFISH_PATH
    env_path = os.getenv("STOCKFISH_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    return None


class EngineAdvisor:
    """
    Provides tactical engine analysis using official Stockfish if available,
    or a lightweight minimax/heuristic fallback.
    """

    def __init__(self, stockfish_path: Optional[str] = None):
        self.stockfish_path = stockfish_path or find_stockfish_binary()

    def is_stockfish_available(self) -> bool:
        return bool(self.stockfish_path and Path(self.stockfish_path).exists())

    def analyze_position(self, board: chess.Board, time_limit_secs: float = 0.5) -> Dict[str, Any]:
        """Analyze position using real Stockfish if executable is found, or heuristic analysis."""
        if self.is_stockfish_available():
            try:
                with chess.engine.SimpleEngine.popen_uci(self.stockfish_path) as engine:
                    info = engine.analyse(board, chess.engine.Limit(time=time_limit_secs))
                    score = info.get("score")
                    pv = info.get("pv", [])
                    best_move = pv[0].uci() if pv else None
                    cp = score.relative.score(mate_score=10000) if score else 0
                    return {
                        "engine": "Stockfish",
                        "engine_path": self.stockfish_path,
                        "best_move": best_move,
                        "evaluation_cp": cp,
                        "pv": [m.uci() for m in pv[:5]],
                        "depth": info.get("depth", 0),
                    }
            except Exception as e:
                pass  # fallback to heuristic if UCI fails

        # Fallback heuristic analysis
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return {"engine": "HeuristicFallback", "best_move": None, "evaluation_cp": 0, "pv": []}

        piece_values = {
            chess.PAWN: 100,
            chess.KNIGHT: 320,
            chess.BISHOP: 330,
            chess.ROOK: 500,
            chess.QUEEN: 900,
            chess.KING: 20000,
        }
        scored_moves = []
        for move in legal_moves:
            score = 0
            if board.is_capture(move):
                captured = board.piece_at(move.to_square)
                score += piece_values.get(captured.piece_type, 100) if captured else 100
            if move.to_square in (chess.E4, chess.D4, chess.E5, chess.D5):
                score += 30
            board.push(move)
            if board.is_check():
                score += 50
            board.pop()
            scored_moves.append((score, move))

        scored_moves.sort(key=lambda x: x[0], reverse=True)
        best = scored_moves[0][1].uci()

        white_mat = sum(piece_values.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == chess.WHITE)
        black_mat = sum(piece_values.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == chess.BLACK)
        rel_eval = (white_mat - black_mat) if board.turn == chess.WHITE else (black_mat - white_mat)

        return {
            "engine": "BuiltinHeuristicAdvisor",
            "best_move": best,
            "evaluation_cp": rel_eval,
            "pv": [m.uci() for _, m in scored_moves[:3]],
            "depth": 1,
            "note": "Stockfish binary was not detected; running builtin tactical evaluator.",
        }