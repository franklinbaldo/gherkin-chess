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
def get_relevant_memory(
    game_id: str = "game_default",
    candidate_move: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    [READ FLOW] Retrieve relevant past Gherkin Scenarios from OKF corpus
    matched against the current board state and candidate move.
    """
    game = session_manager.get_game(game_id=game_id)
    return game.get_memory_insights(candidate_move=candidate_move, limit=limit)


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
    game_id: str = "game_default",
    gherkin: Optional[str] = None,
    reuse_scenario_name: Optional[str] = None,
    diverges_from: Optional[str] = None,
    divergence_reason: Optional[str] = None,
    explicit_origin_fen: Optional[str] = None,
    enforce_non_silent_substitution: bool = False,
) -> Dict[str, Any]:
    """
    [WRITE FLOW] Execute a move on the board through the mandatory Gherkin -> OKF gate.
    
    Epistemic Choices:
    1. REUSE: Provide `reuse_scenario_name` (e.g. 'Establish Central Pawn'). Reuses existing
       knowledge without re-materializing duplicates.
    2. DIVERGENCE: Provide new `gherkin` + `diverges_from` + `divergence_reason`. Explains why
       a past scenario does not apply to this context and materializes a refined rule.
    3. NEW KNOWLEDGE: Provide new `gherkin`.
    
    Arguments:
    - move: UCI or SAN string of the legal move (e.g., 'e4', 'e2e4', 'Nf3').
    - gherkin: Gherkin feature/scenario explaining and referencing the move.
    - reuse_scenario_name: Name of a past scenario to confirm/reuse.
    - diverges_from: Name of past scenario that was considered but rejected/refined.
    - divergence_reason: Explicit rationale for divergence.
    - explicit_origin_fen: Optional. Must match current board FEN if provided.
    - enforce_non_silent_substitution: If True, rejects new Gherkin if a strong matching scenario
      exists unless reuse or divergence is declared.
    """
    game = session_manager.get_game(game_id=game_id)
    return game.execute_move(
        move_str=move,
        gherkin_text=gherkin,
        reuse_scenario_name=reuse_scenario_name,
        diverges_from=diverges_from,
        divergence_reason=divergence_reason,
        explicit_origin_fen=explicit_origin_fen,
        enforce_non_silent_substitution=enforce_non_silent_substitution,
    )


@mcp.tool()
def get_corpus_metrics() -> Dict[str, Any]:
    """
    Inspect epistemic metrics: total applications, reuse count, divergence count,
    and scenario usage frequency.
    """
    return session_manager.corpus.get_application_metrics()


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