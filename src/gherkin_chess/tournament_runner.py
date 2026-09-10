from __future__ import annotations

import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import chess

from .engine_advisor import EngineAdvisor
from .game import ChessGame
from .leaderboard import LeaderboardManager
from .llm_agent import LLMChessAgent
from .session import SessionManager

import urllib.request
import json

# Fallback free model pool on OpenRouter
FALLBACK_FREE_MODELS = [
    "google/gemma-4-26b-a4b-it:free",
    "liquid/lfm-2.5-2.6b:free",
    "openrouter/free",
    "cohere/north-mini-code:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
]

def fetch_openrouter_free_models() -> List[str]:
    """Fetch active free models dynamically from OpenRouter models API."""
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"User-Agent": "gherkin-chess/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        free_ids = [
            m["id"] for m in data.get("data", [])
            if m.get("id", "").endswith(":free") or (
                m.get("pricing", {}).get("prompt") == "0" and m.get("pricing", {}).get("completion") == "0"
            )
        ]
        if free_ids:
            return free_ids
    except Exception as exc:
        print(f"[Warning] Failed to fetch live OpenRouter models: {exc}. Using fallback free models.")
    return FALLBACK_FREE_MODELS

def get_tournament_roster() -> List[Dict[str, Any]]:
    """Build a balanced tournament roster using only OpenRouter free models."""
    available = fetch_openrouter_free_models()
    roster = []
    # Configure both MCP and Raw variants for available free models
    for m in available[:6]:
        short_name = m.split("/")[-1].replace(":free", "")
        # Variant with MCP (OKF memory + Gherkin-to-action gate)
        roster.append({
            "name": f"{short_name} (MCP)",
            "model": f"openrouter/{m}",
            "with_mcp": True,
        })
        # Variant without MCP (Raw direct move generator)
        roster.append({
            "name": f"{short_name} (Raw)",
            "model": f"openrouter/{m}",
            "with_mcp": False,
        })
    return roster

# Default roster of free models
DEFAULT_MODEL_ROSTER = get_tournament_roster()



def play_tournament_match(
    player1_config: Dict[str, Any],
    player2_config: Dict[str, Any],
    session: SessionManager,
    leaderboard: LeaderboardManager,
    max_plies: int = 40,
) -> Dict[str, Any]:
    """Play a single competitive match between two agents and update OpenSkill ladder."""
    game_id = f"match_{int(time.time())}_{random.randint(100, 999)}"
    game = session.start_game(game_id)
    advisor = EngineAdvisor()

    agent_white = LLMChessAgent(
        name=player1_config["name"],
        model=player1_config["model"],
        with_mcp=player1_config["with_mcp"],
    )
    agent_black = LLMChessAgent(
        name=player2_config["name"],
        model=player2_config["model"],
        with_mcp=player2_config["with_mcp"],
    )

    t0 = time.time()
    mcp_events = []
    plies_played = 0

    while not game.board.is_game_over() and plies_played < max_plies:
        current_agent = agent_white if game.board.turn == chess.WHITE else agent_black
        legal_sans = [game.board.san(m) for m in game.board.legal_moves]

        if not legal_sans:
            break

        # Deliberate
        decision = current_agent.deliberate_move(game)
        move_candidate = decision.get("move")

        # Fallback if LLM suggests an illegal move: pick best engine advice or first legal move
        if not move_candidate or move_candidate not in legal_sans:
            advice = game.get_engine_advice(time_limit_secs=0.04)
            if advice.get("best_move"):
                move_candidate = game.board.san(game.board.parse_uci(advice["best_move"]))
            else:
                move_candidate = legal_sans[0]

        if current_agent.with_mcp:
            # ── PASSAGEM OBRIGATÓRIA PELO GATE DO MCP ──
            reuse_sc = decision.get("reuse_scenario_name")
            gherkin_text = decision.get("gherkin")
            diverges_from = decision.get("diverges_from")
            divergence_reason = decision.get("divergence_reason")

            if not reuse_sc and not gherkin_text:
                gherkin_text = f"""Feature: Tournament Execution
  Scenario: Move {move_candidate} at Move {game.board.fullmove_number}
    Given position at move {game.board.fullmove_number}
    When {('white' if game.board.turn else 'black')} plays {move_candidate}
    Then fight for central space and piece coordination
"""
            try:
                res = game.execute_move(
                    move_str=move_candidate,
                    gherkin_text=gherkin_text,
                    reuse_scenario_name=reuse_sc,
                    diverges_from=diverges_from,
                    divergence_reason=divergence_reason,
                )
                mcp_events.append(res)
            except Exception:
                safe_gherkin = f"""Feature: Recovery
  Scenario: Safe Move {move_candidate}
    Given board at move {game.board.fullmove_number}
    When play {move_candidate}
    Then legal move
"""
                res = game.execute_move(move_candidate, gherkin_text=safe_gherkin)
                mcp_events.append(res)
        else:
            # ── AGENTE SEM MCP (APENAS MOVIMENTO DIRETO) ──
            move_obj = game.board.parse_san(move_candidate)
            game.board.push(move_obj)

        plies_played += 1

    duration = time.time() - t0

    # Determine outcome
    if game.board.is_checkmate():
        outcome = "white" if (game.board.turn == chess.BLACK) else "black"
        result_desc = f"Xeque-mate (Venceu {'Brancas' if outcome == 'white' else 'Pretas'})"
    elif game.board.is_stalemate() or game.board.is_insufficient_material() or game.board.can_claim_threefold_repetition():
        outcome = "draw"
        result_desc = "Empate de regras (Afogamento/Repetição)"
    else:
        # Positional evaluation
        eval_adv = advisor.analyze_position(game.board, time_limit_secs=0.08)
        cp = eval_adv["evaluation_cp"]
        if cp > 150:
            outcome = "white"
            result_desc = f"Vantagem Posicional Brancas (+{cp/100:.1f})"
        elif cp < -150:
            outcome = "black"
            result_desc = f"Vantagem Posicional Pretas ({cp/100:.1f})"
        else:
            outcome = "draw"
            result_desc = f"Empate Posicional ({cp/100:.1f})"

    # Update OpenSkill Leaderboard
    leaderboard.record_match(
        player_white=agent_white.name,
        player_black=agent_black.name,
        model_white=agent_white.model,
        model_black=agent_black.model,
        outcome=outcome,
        game_id=game_id,
        plies=plies_played,
        details={"result_desc": result_desc, "duration_s": round(duration, 1)},
    )

    return {
        "game_id": game_id,
        "white": agent_white.name,
        "black": agent_black.name,
        "outcome": outcome,
        "result_desc": result_desc,
        "plies": plies_played,
        "duration_s": round(duration, 1),
    }


def run_scheduled_batch(num_matches: int = 2):
    """
    Called by GitHub Actions cron every 15 minutes.
    Picks random pair of agents from roster and executes ladder matches.
    """
    base_dir = Path(os.getenv("GHERKIN_CHESS_DATA_DIR", ".tournament_data"))
    session = SessionManager(base_dir)
    leaderboard = LeaderboardManager(base_dir / "leaderboard.json")

    print(f"=== Starting Scheduled Tournament Batch ({num_matches} matches) ===")
    
    for i in range(num_matches):
        p1, p2 = random.sample(DEFAULT_MODEL_ROSTER, 2)
        print(f"\nMatch {i+1}: {p1['name']} vs {p2['name']}...")
        res = play_tournament_match(p1, p2, session=session, leaderboard=leaderboard, max_plies=20)
        print(f"-> Outcome: {res['result_desc']} ({res['plies']} plies in {res['duration_s']}s)")

    print("\n=== Current OpenSkill Leaderboard Standings ===")
    standings = leaderboard.get_standings()
    for s in standings:
        print(f"Rank {s['rank']}: {s['name']} | Rating: {s['ordinal']} (mu: {s['mu']}, sigma: {s['sigma']}) | Record: {s['wins']}W-{s['draws']}D-{s['losses']}L")