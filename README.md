# gherkin-chess

> A chess environment for AI agents where every move must be externalized as Gherkin and materialized through OKF before it can be played.

---

## ♟ Research Question & Core Idea

Can an AI agent learn to play chess progressively when its experience is converted into structured declarative knowledge expressed in Gherkin and materialized through OKF?

In `gherkin-chess`, an agent playing chess is **free to reason**, calculate candidate variations, consult accumulated knowledge, and even request tactical evaluations from **Stockfish** (or built-in tactical advisors).

However, a strict gate controls the action boundary:

> **No move can be executed on the board before the agent externalizes its decision in valid Gherkin and materializes it through `okf-parser`.**

```text
Position
   │
   ▼
[READ] Retrieve relevant Gherkin Scenarios from OKF corpus
   │
   ▼
Free reasoning (Agent + optional Stockfish advisor)
   │
   ▼
Intended move + Mandatory Gherkin justification
   │
   ▼
Validation: syntax valid, origin_fen matches pre-move board, move referenced
   │
   ▼
[WRITE] Materialization into OKF via okf-parser
   │
   ▼
Move executed on board
```

---

## 🧠 Operational Memory: Dual READ/WRITE Loop & Historical Consistency

The Gherkin corpus is an **operational working memory** governed by the **Non-Silent Substitution Invariant**:
- Conhecimento anterior relevante **nunca pode ser substituído silenciosamente**.
- Diante de um lance com cenário anterior aplicável, o agente deve escolher formalmente entre:
  1. **Reutilizar (`reuse`):** Confirma a regra existente sem duplicar arquivos no OKF.
  2. **Divergir (`divergence`):** Explica explicitamente por que a regra anterior não se aplica àquele contexto e materializa uma nova regra com tags de linhagem (`@diverges_from`, `@divergence_reason`, `@relation:refines`).
  3. **Criar (`new`):** Quando se trata de um padrão inédito.

---

## 📍 Invariant: Immutable Origin Position (`origin_fen`)

Every piece of Gherkin knowledge is permanently anchored to the exact board state where it was born:

```gherkin
@origin_fen:rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR_w_KQkq_-_0_1
Feature: Opening Principles
  Scenario: Establish Central Control
    Given starting board setup
    When white advances e4
    Then control center squares d5 and f5
```

- **Origin Position ($P_{\text{origin}}$):** The exact FEN right before the move was played. Immutable once created.
- **Application Position ($P_{\text{app}}$):** Any subsequent board in this or future games where the scenario is retrieved as an insight.

---

## 🏗 Gherkin & OKF: Structural Fidelity Without Domain Coupling

The OKF metamodel does **not** contain chess concepts (`ChessMove`, `Tactic`, `Piece`). The OKF materializes the **canonical AST primitives of Gherkin**:
- `Feature`
- `Rule`
- `Background`
- `Scenario`
- `Step` (`Given`, `When`, `Then`, `And`, `But`)
- `Examples` / `DataTable` / `DocString`

---

## 🚀 Setup & Dependency Management with `uv`

The repository is fully configured to use [`uv`](https://docs.astral.sh/uv/) for reproducible dependency resolution, lockfile management, and rapid execution.

### Requirements
- Python `>= 3.12`
- `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh` or `winget install astral-sh.uv`)

### Installation
Clone the repository and sync the locked environment:
```bash
git clone https://github.com/franklinbaldo/gherkin-chess.git
cd gherkin-chess

# Sync environment with dev dependencies using uv
uv sync --extra dev
```

---

## 🎮 Running with `uv run`

### 1. MCP Server (for AI Agents)
Start the FastMCP server over stdio:
```bash
uv run python -m gherkin_chess.cli mcp
```

#### MCP Client Configuration (e.g. Claude Desktop, Gemini CLI)
```json
{
  "mcpServers": {
    "gherkin-chess": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/gherkin-chess", "python", "-m", "gherkin_chess.cli", "mcp"],
      "env": {
        "GHERKIN_CHESS_DATA_DIR": ".gherkin_chess_data"
      }
    }
  }
}
```

### 2. Available MCP Tools
- `start_game(game_id, starting_fen)`: Start or reset a game.
- `get_game_state(game_id)`: Inspect FEN, turn, legal moves (SAN and UCI).
- `get_relevant_memory(game_id, candidate_move, limit)`: **[READ]** Retrieve top relevant past Scenarios.
- `get_engine_advice(game_id, time_limit_secs)`: Get Stockfish / tactical engine recommendation.
- `play_move(move, gherkin, reuse_scenario_name, ...)`: **[WRITE]** Execute move through the Gherkin gate.
- `get_corpus_metrics()`: Inspect epistemic stats (new vs reused vs diverged).
- `list_corpus_knowledge(limit)`: Inspect stored OKF features.

### 3. Observer Web UI (Human Viewer)
```bash
uv run python -m gherkin_chess.cli web --port 8000
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## 🧪 Testing & Verification with `uv`

Run all 18 unit, adversarial, and historical consistency tests:
```bash
uv run pytest -v
```

---

## 🎬 End-to-End Demonstration

Run the demonstration script showcasing knowledge creation, reuse, divergence, and metrics:
```bash
uv run python demo_run.py
```

---

## 📜 License

MIT License. Created by [franklinbaldo](https://github.com/franklinbaldo).