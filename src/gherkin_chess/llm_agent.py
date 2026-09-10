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
            # ── AGENTE SEM MCP (APENAS MOVIMENTO) ──
            prompt = f"""You are playing chess as {color}.
Current FEN: {curr_fen}
Legal moves: {', '.join(legal_moves_san)}

Choose your move. Respond ONLY in valid JSON with format:
{{"move": "<move_in_san_or_uci>", "thought": "<short_reasoning>"}}
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

            prompt = f"""You are an intelligent chess agent playing as {color} operating under the Gherkin-Chess MCP protocol.
Current FEN: {curr_fen}
Legal moves: {', '.join(legal_moves_san)}

{memory_context}
RULES:
1. You can choose to REUSE an existing Scenario if it matches your strategy (specify 'reuse_scenario_name').
2. Otherwise, you must formulate a valid Gherkin Feature and Scenario justifying your chosen move (specify 'gherkin').
3. The move MUST be legal and explicitly mentioned in your Gherkin step (e.g. When {color.lower()} plays <move>).

Respond ONLY in valid JSON with format:
{{
  "move": "<chosen_legal_move>",
  "reuse_scenario_name": "<name_or_null>",
  "gherkin": "<valid_gherkin_text_or_null>",
  "diverges_from": "<scenario_name_or_null>",
  "divergence_reason": "<explanation_if_diverging_or_null>"
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