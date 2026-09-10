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

## 🧠 Operational Memory: Dual READ/WRITE Loop

The Gherkin corpus is not merely an audit log written after the game; it is an **operational working memory**:

1. **WRITE:** Every move produces knowledge materialized into the OKF bundle:
   $$\text{Pre-Move Position} + \text{Decision} \longrightarrow \text{Gherkin} \longrightarrow \text{okf-parser} \longrightarrow \text{OKF Concept}$$
2. **READ:** Before choosing a move, the MCP inspects the current board and queries the persistent OKF bundle:
   $$\text{Current Board (FEN)} \longrightarrow \text{Contextual Retrieval} \longrightarrow \text{Relevant Scenarios} \longrightarrow \text{Agent Insights}$$

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

The MCP rigorously enforces that the claimed `origin_fen` matches the actual board state.

---

## 🏗 Gherkin & OKF: Structural Fidelity Without Domain Coupling

The OKF metamodel does **not** contain chess concepts (`ChessMove`, `Tactic`, `Piece`). The OKF materializes the **canonical AST primitives of Gherkin**:
- `Feature`
- `Rule`
- `Background`
- `Scenario`
- `Step` (`Given`, `When`, `Then`, `And`, `But`)
- `Examples` / `DataTable` / `DocString`

Domain semantics belong to the text inside the steps and tags, while `okf-parser` handles parsing, identity, and relational storage.

---

## 🚀 Installation & Setup

### Requirements
- Python `>= 3.12`
- `uv` (recommended) or standard `pip`
- (Optional) `stockfish` executable on PATH for deep engine analysis

```bash
git clone https://github.com/franklinbaldo/gherkin-chess.git
cd gherkin-chess

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # Or on Windows: .\.venv\Scripts\activate
uv pip install -e ".[dev]"
```

---

## 🎮 Running the System

### 1. MCP Server (for AI Agents)
Start the FastMCP server over stdio:
```bash
python -m gherkin_chess.cli mcp
```

#### MCP Client Configuration
To connect `gherkin-chess` to Claude Desktop, Gemini CLI, or any MCP client, add to your `mcpServers` config:
```json
{
  "mcpServers": {
    "gherkin-chess": {
      "command": "python",
      "args": ["-m", "gherkin_chess.cli", "mcp"],
      "cwd": "/path/to/gherkin-chess",
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
- `get_relevant_memory(game_id, limit)`: **[READ]** Retrieve top relevant past Scenarios.
- `get_engine_advice(game_id, time_limit_secs)`: Get Stockfish / tactical engine recommendation.
- `play_move(move, gherkin, game_id, explicit_origin_fen)`: **[WRITE]** Execute move through the Gherkin gate.
- `list_corpus_knowledge(limit)`: Inspect stored OKF features.

### 3. Observer Web UI (Human Viewer)
To observe ongoing games, board state, move history, latest Gherkin, and recovered operational memory in real-time:
```bash
python -m gherkin_chess.cli web --port 8000
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## 🧪 Running Tests & Verification

The test suite covers parser roundtripping, real `okf-parser` bundle loading, gate enforcement, and adversarial rejection attacks:

```bash
pytest -v
```

### Adversarial Tests Verified:
- Attempting to move without Gherkin (`MissingGherkinError`).
- Attempting to move with invalid Gherkin syntax (`GherkinParseError`).
- Attempting to move with unrelated Gherkin (`MoveNotRelatedError`).
- Attempting to spoof `origin_fen` (`OriginMismatchError`).
- Attempting to bypass the Gherkin gate using Stockfish recommendations directly.
- Immutability of past origin FENs.

---

## 🎬 End-to-End Demonstration Script

To run the complete demonstration of a two-game sequence showing cross-game operational memory reuse:

```bash
python demo_run.py
```

---

## 📜 License

MIT License. Created by [franklinbaldo](https://github.com/franklinbaldo).