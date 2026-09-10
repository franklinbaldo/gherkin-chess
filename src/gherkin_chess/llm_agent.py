from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional
import litellm

from .game import ChessGame


class LLMChessAgent:
    """
    Autonomous LLM Agent that plays chess using LiteLLM (supporting OpenRouter models).
    Can play either:
    - with_mcp=True: Queries memory insights, deliberates, and MUST pass the Gherkin -> OKF gate.
    - with_mcp=False: Raw LLM move generation without memory or Gherkin gate.
    """

    def __init__(
        self,
        name: str,
        model: str,  # e.g. "openrouter/meta-llama/llama-3.3-70b-instruct" or "openrouter/deepseek/deepseek-chat"
        with_mcp: bool = True,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        self.name = name
        self.model = model
        self.with_mcp = with_mcp
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.api_base = api_base or os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")

    def deliberate_move(self, game: ChessGame) -> Dict[str, Any]:
        """
        Query the LLM to choose a legal move.
        If with_mcp=True, prompt includes retrieved OKF scenarios and demands Gherkin.
        """
        board = game.board
        legal_moves_san = [board.san(m) for m in board.legal_moves]
        legal_moves_uci = [m.uci() for m in board.legal_moves]
        curr_fen = board.fen()
        color = "White" if board.turn else "Black"

        if not self.with_mcp:
            # ── AGENTE VIA MCP SEM GATE GHERKIN (Standard Direct MCP) ──
            # Usa as ferramentas MCP do jogo (estado, engine advice), mas não é obrigado a formular Gherkin
            advice = game.get_engine_advice(time_limit_secs=0.05)
            engine_hint = f"Engine Best Move: {advice.get('best_move')} (Score: {advice.get('evaluation_cp', 0)/100:.2f})" if advice.get("best_move") else ""

            prompt = f"""You are playing chess as {color} connected to the GherkinChess MCP server.
You have called MCP tools:
- get_game_state(): FEN = {curr_fen}
- get_engine_advice(): {engine_hint}
- Legal moves: {', '.join(legal_moves_san)}

You are executing a move via the MCP tool 'play_direct_move' (Gherkin is NOT mandatory for you).
You may follow or diverge from the engine recommendation based on your own chess evaluation.

Choose your move. Respond ONLY in valid JSON with format:
{{"move": "<move_in_san_or_uci>", "thought": "<tactical_reasoning_and_engine_comparison>"}}
"""
            response = self._call_llm(prompt)
            data = self._parse_json(response)
            move_str = data.get("move", legal_moves_san[0])
            return {"move": move_str, "thought": data.get("thought", "")}

        else:
            # ── AGENTE COM MCP (MEMÓRIA OKF + GATE GHERKIN) ──
            insights = game.get_memory_insights(limit=3)
            memory_context = ""
            if insights:
                memory_context = "### RELEVANT OPERATIONAL MEMORY FROM OKF CORPUS:\n"
                for i, item in enumerate(insights, 1):
                    memory_context += f"{i}. Scenario: '{item['scenario_name']}' (Score: {item['score']})\n"
                    memory_context += f"   Gherkin:\n{item['gherkin']}\n\n"

            prompt = f"""You are an intelligent chess agent playing as {color} operating under the strict Gherkin-Chess MCP protocol.
Current FEN: {curr_fen}
Legal moves: {', '.join(legal_moves_san)}

{memory_context}
MANDATORY PROTOCOL RULES:
1. REUSE: If a Scenario from memory matches your plan, set "reuse_scenario_name": "<scenario_name>" and "gherkin": null.
2. DIVERGENCE: If you disagree with a past scenario, set "diverges_from": "<scenario_name>", explain in "divergence_reason", and formulate a new "gherkin".
3. NEW FEATURE: If creating new knowledge, you MUST formulate a complete Gherkin Feature & Scenario.
   NEVER leave "gherkin" null or empty if not reusing! The move MUST be explicitly mentioned in the 'When' step!
   Example of required Gherkin:
   Feature: Tactical Expansion
     Scenario: Advance {legal_moves_san[0]} to contest position
       Given board state at move {game.board.fullmove_number}
       When {color.lower()} plays {legal_moves_san[0]}
       Then control key squares and advance development

Respond ONLY in valid JSON:
{{
  "move": "<chosen_legal_move>",
  "reuse_scenario_name": null,
  "gherkin": "Feature: ...\\n  Scenario: ...\\n    Given ...\\n    When {color.lower()} plays <chosen_legal_move>\\n    Then ...",
  "diverges_from": null,
  "divergence_reason": null
}}
"""
            response = self._call_llm(prompt)
            data = self._parse_json(response)
            return data

    def _call_llm(self, prompt: str) -> str:
        """Call LiteLLM with OpenRouter or fallback."""
        if not self.api_key:
            # If no API key provided in test/mock environment, generate valid fallback
            return '{"move": "e4", "gherkin": "Feature: Open\\n  Scenario: e4\\n    Given start\\n    When white plays e4\\n    Then center\\n"}'

        try:
            res = litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                api_key=self.api_key,
                api_base=self.api_base,
                temperature=0.2,
                max_tokens=500,
            )
            return res.choices[0].message.content or ""
        except Exception as exc:
            # Return safe fallback if network/API limits hit
            return json.dumps({"move": "e4", "thought": f"API fallback due to {exc}"})

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON from markdown code blocks or plain text."""
        try:
            # Try plain json parse
            return json.loads(text.strip())
        except Exception:
            pass

        # Match markdown ```json ... ```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        # Find first { to last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass

        return {}