from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP

from .session import SessionManager

DATA_DIR = Path(os.getenv("GHERKIN_CHESS_DATA_DIR", ".gherkin_chess_data"))
session_manager = SessionManager(DATA_DIR)

mcp = FastMCP("GherkinChess")


@mcp.tool()
def start_game(game_id: str = "game_default", starting_fen: Optional[str] = None) -> Dict[str, Any]:
    """Start or reset a game with given game_id and optional starting FEN."""
    game = session_manager.start_game(game_id=game_id, starting_fen=starting_fen)
    return game.get_state()


@mcp.tool()
def get_game_state(game_id: str = "game_default") -> Dict[str, Any]:
    """Get the current board state, turn, move list, and legality flags."""
    game = session_manager.get_game(game_id=game_id)
    return game.get_state()


@mcp.tool()
def get_relevant_memory(game_id: str = "game_default", limit: int = 5) -> List[Dict[str, Any]]:
    """
    [READ FLOW] Retrieve relevant past Gherkin Scenarios from OKF corpus
    matched against the current board state and origin_fens.
    """
    game = session_manager.get_game(game_id=game_id)
    return game.get_memory_insights(limit=limit)


@mcp.tool()
def get_engine_advice(game_id: str = "game_default", time_limit_secs: float = 0.5) -> Dict[str, Any]:
    """
    Get tactical analysis from Stockfish (or tactical evaluator).
    Agents may use this freely for discovery, but engine moves MUST still pass
    the mandatory Gherkin -> OKF gate before execution.
    """
    game = session_manager.get_game(game_id=game_id)
    return game.get_engine_advice(time_limit_secs=time_limit_secs)


@mcp.tool()
def play_move(
    move: str,
    gherkin: str,
    game_id: str = "game_default",
    explicit_origin_fen: Optional[str] = None,
) -> Dict[str, Any]:
    """
    [WRITE FLOW] Execute a move on the board through the mandatory Gherkin -> OKF gate.
    
    Arguments:
    - move: UCI or SAN string of the legal move (e.g., 'e4', 'e2e4', 'Nf3').
    - gherkin: Gherkin feature/scenario explaining and referencing the move.
    - explicit_origin_fen: Optional. Must match current board FEN if provided.
    
    The move is rejected if:
    - Gherkin is missing or has invalid syntax.
    - Gherkin has an origin_fen conflicting with pre-move board.
    - Gherkin has no connection to the intended move.
    - okf-parser fails to materialize the document.
    - The move is illegal.
    """
    game = session_manager.get_game(game_id=game_id)
    return game.execute_move(move_str=move, gherkin_text=gherkin, explicit_origin_fen=explicit_origin_fen)


@mcp.tool()
def list_corpus_knowledge(limit: int = 50) -> List[Dict[str, Any]]:
    """Inspect all features and scenarios stored in the persistent OKF bundle."""
    features = session_manager.corpus.load_all_features()
    results = []
    for f in features[:limit]:
        results.append({
            "feature_name": f.name,
            "origin_fen": f.origin_fen,
            "tags": f.tags,
            "scenarios_count": len(f.scenarios),
            "scenarios": [s.name for s in f.scenarios],
            "gherkin": f.to_gherkin(),
        })
    return results