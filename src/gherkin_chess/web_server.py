from __future__ import annotations

import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .mcp_server import session_manager


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <title>gherkin-chess — Live Observer</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }
        .header { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #334155; padding-bottom: 16px; margin-bottom: 24px; }
        h1 { margin: 0; font-size: 24px; color: #38bdf8; }
        .badge { background: #1e293b; padding: 4px 10px; border-radius: 9999px; font-size: 12px; border: 1px solid #475569; }
        .grid { display: grid; grid-template-columns: 420px 1fr; gap: 24px; }
        .card { background: #1e293b; border-radius: 8px; border: 1px solid #334155; padding: 18px; }
        h2 { font-size: 16px; margin-top: 0; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #334155; padding-bottom: 8px; }
        .board-ascii { font-family: monospace; white-space: pre; background: #090d16; padding: 16px; border-radius: 6px; font-size: 16px; line-height: 1.4; border: 1px solid #334155; }
        .meta-row { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 14px; }
        .meta-label { color: #64748b; }
        .meta-value { font-weight: 600; }
        .history-list { max-height: 250px; overflow-y: auto; font-family: monospace; font-size: 13px; }
        .history-item { padding: 6px 8px; border-bottom: 1px solid #334155; display: flex; justify-content: space-between; }
        .history-item:hover { background: #334155; cursor: pointer; }
        pre.code-block { background: #090d16; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 13px; overflow-x: auto; color: #a5f3fc; border: 1px solid #334155; }
        .tab-btn { background: #334155; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; margin-right: 6px; }
        .tab-btn.active { background: #38bdf8; color: #0f172a; font-weight: bold; }
    </style>
</head>
<body>
    <div class=\"header\">
        <div>
            <h1>♟ gherkin-chess Observer</h1>
            <p style=\"margin:4px 0 0; color:#94a3b8; font-size:14px;\">Decision externalization into Gherkin & materialization via OKF</p>
        </div>
        <div>
            <span class=\"badge\" id=\"gameIdBadge\">Game: default</span>
            <span class=\"badge\" id=\"turnBadge\">Turn: White</span>
        </div>
    </div>

    <div class=\"grid\">
        <div>
            <div class=\"card\" style=\"margin-bottom: 24px;\">
                <h2>Current Board</h2>
                <div class=\"board-ascii\" id=\"boardView\">Loading board...</div>
                <div style=\"margin-top: 16px;\">
                    <div class=\"meta-row\"><span class=\"meta-label\">FEN:</span><span class=\"meta-value\" id=\"fenVal\" style=\"font-size:11px; word-break:break-all;\"></span></div>
                    <div class=\"meta-row\"><span class=\"meta-label\">Legal Moves:</span><span class=\"meta-value\" id=\"legalMovesVal\"></span></div>
                    <div class=\"meta-row\"><span class=\"meta-label\">Status:</span><span class=\"meta-value\" id=\"statusVal\"></span></div>
                </div>
            </div>

            <div class=\"card\">
                <h2>Move History</h2>
                <div class=\"history-list\" id=\"historyList\">No moves yet.</div>
            </div>
        </div>

        <div>
            <div class=\"card\" style=\"margin-bottom: 24px;\">
                <h2>Latest Decision Gherkin & Origin FEN</h2>
                <div class=\"meta-row\"><span class=\"meta-label\">Origin FEN:</span><span class=\"meta-value\" id=\"originFenVal\" style=\"font-size:12px; color:#38bdf8;\">-</span></div>
                <pre class=\"code-block\" id=\"gherkinView\">No Gherkin submitted yet for the current move.</pre>
            </div>

            <div class=\"card\">
                <h2>Operational Memory (Recovered Scenarios)</h2>
                <div id=\"memoryView\">
                    <p style=\"color:#64748b; font-size:14px;\">No memory insights loaded.</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        async function refreshData() {
            try {
                const res = await fetch('/api/state');
                const data = await res.json();
                
                document.getElementById('gameIdBadge').textContent = 'Game: ' + data.game_id;
                document.getElementById('turnBadge').textContent = 'Turn: ' + data.turn;
                document.getElementById('fenVal').textContent = data.fen;
                document.getElementById('legalMovesVal').textContent = data.legal_moves_san.length + ' moves';
                document.getElementById('statusVal').textContent = data.is_game_over ? ('Game Over: ' + data.result) : 'Active';
                document.getElementById('boardView').textContent = data.ascii;

                const hList = document.getElementById('historyList');
                if (data.history && data.history.length > 0) {
                    hList.innerHTML = data.history.map(m => 
                        <div class=\"history-item\">
                            <span># : <b></b> ()</span>
                            <span style=\"color:#94a3b8; font-size:11px;\"></span>
                        </div>
                    ).join('');

                    const lastMove = data.history[data.history.length - 1];
                    document.getElementById('originFenVal').textContent = lastMove.pre_fen;
                    document.getElementById('gherkinView').textContent = lastMove.gherkin;
                } else {
                    hList.innerHTML = 'No moves yet.';
                    document.getElementById('originFenVal').textContent = '-';
                    document.getElementById('gherkinView').textContent = 'Initial position. No moves played.';
                }

                // Memory
                const memRes = await fetch('/api/memory');
                const memData = await memRes.json();
                const memView = document.getElementById('memoryView');
                if (memData && memData.length > 0) {
                    memView.innerHTML = memData.map(item => 
                        <div style=\"border:1px solid #334155; padding:10px; border-radius:6px; margin-bottom:10px;\">
                            <div style=\"display:flex; justify-content:space-between; font-weight:600; color:#38bdf8; font-size:14px;\">
                                <span> (Feature: )</span>
                                <span>Score: </span>
                            </div>
                            <div style=\"font-size:11px; color:#94a3b8; margin:4px 0;\">Origin: </div>
                            <pre class=\"code-block\" style=\"margin:6px 0 0;\"></pre>
                        </div>
                    ).join('');
                } else {
                    memView.innerHTML = '<p style=\"color:#64748b; font-size:14px;\">No past scenarios matched current position.</p>';
                }

            } catch (e) {
                console.error(e);
            }
        }
        refreshData();
        setInterval(refreshData, 3000);
    </script>
</body>
</html>
"""


class ObserverHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
        elif parsed.path == "/api/state":
            game = session_manager.get_game("game_default")
            state = game.get_state()
            state["ascii"] = str(game.board)
            state["history"] = [
                {
                    "move_number": r.move_number,
                    "turn": r.turn,
                    "uci": r.uci,
                    "san": r.san,
                    "pre_fen": r.pre_fen,
                    "post_fen": r.post_fen,
                    "timestamp": r.timestamp,
                    "gherkin": r.gherkin,
                }
                for r in game.history
            ]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(state).encode("utf-8"))
        elif parsed.path == "/api/memory":
            game = session_manager.get_game("game_default")
            insights = game.get_memory_insights()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(insights).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def run_web(port: int = 8000):
    server = HTTPServer(("0.0.0.0", port), ObserverHandler)
    print(f"Starting gherkin-chess Observer Web UI on http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()