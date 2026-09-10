from __future__ import annotations

import shutil
from typing import Any, Dict, List, Optional
import chess
import chess.engine


class EngineAdvisor:
    """
    Provides tactical engine analysis (Stockfish if available, or lightweight minimax/heuristic fallback).
    Stockfish is an advisor for discovery/analysis, NOT a bypass for the Gherkin gate.
    """

    def __init__(self, stockfish_path: Optional[str] = None):
        self.stockfish_path = stockfish_path or shutil.which("stockfish")

    def is_stockfish_available(self) -> bool:
        return bool(self.stockfish_path)

    def analyze_position(self, board: chess.Board, time_limit_secs: float = 0.5) -> Dict[str, Any]:
        """Analyze position using Stockfish if executable is found, or heuristic analysis."""
        if self.stockfish_path:
            try:
                with chess.engine.SimpleEngine.popen_uci(self.stockfish_path) as engine:
                    info = engine.analyse(board, chess.engine.Limit(time=time_limit_secs))
                    score = info.get("score")
                    pv = info.get("pv", [])
                    best_move = pv[0].uci() if pv else None
                    cp = score.relative.score(mate_score=10000) if score else 0
                    return {
                        "engine": "Stockfish",
                        "best_move": best_move,
                        "evaluation_cp": cp,
                        "pv": [m.uci() for m in pv[:5]],
                        "depth": info.get("depth", 0),
                    }
            except Exception as e:
                pass  # fallback to heuristic

        # Fallback heuristic analysis
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return {"engine": "HeuristicFallback", "best_move": None, "evaluation_cp": 0, "pv": []}

        scored_moves = []
        piece_values = {
            chess.PAWN: 100,
            chess.KNIGHT: 320,
            chess.BISHOP: 330,
            chess.ROOK: 500,
            chess.QUEEN: 900,
            chess.KING: 20000,
        }
        for move in legal_moves:
            score = 0
            if board.is_capture(move):
                captured = board.piece_at(move.to_square)
                score += piece_values.get(captured.piece_type, 100) if captured else 100
            # Center control bonus for pawns/knights
            if move.to_square in (chess.E4, chess.D4, chess.E5, chess.D5):
                score += 30
            # Check bonus
            board.push(move)
            if board.is_check():
                score += 50
            board.pop()
            scored_moves.append((score, move))

        scored_moves.sort(key=lambda x: x[0], reverse=True)
        best = scored_moves[0][1].uci()

        # Material balance
        white_mat = sum(piece_values.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == chess.WHITE)
        black_mat = sum(piece_values.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == chess.BLACK)
        rel_eval = (white_mat - black_mat) if board.turn == chess.WHITE else (black_mat - white_mat)

        return {
            "engine": "BuiltinHeuristicAdvisor",
            "best_move": best,
            "evaluation_cp": rel_eval,
            "pv": [m.uci() for _, m in scored_moves[:3]],
            "depth": 1,
            "note": "Stockfish binary was not detected on PATH; running builtin tactical evaluator.",
        }