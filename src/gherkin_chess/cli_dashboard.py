from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import chess
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from gherkin_chess.corpus import CorpusManager
from gherkin_chess.leaderboard import LeaderboardManager
from gherkin_chess.session import SessionManager


def build_board_text(board: chess.Board, last_move: Optional[chess.Move] = None) -> Text:
    piece_symbols = {
        "P": "♙", "N": "♘", "B": "♗", "R": "♖", "Q": "♕", "K": "♔",
        "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚",
    }
    t = Text()
    t.append("    a   b   c   d   e   f   g   h  \n", style="bold cyan")
    t.append("  ┌───┬───┬───┬───┬───┬───┬───┬───┐\n", style="bright_black")

    for rank in range(7, -1, -1):
        t.append(f"{rank + 1} │", style="bold cyan")
        for file in range(8):
            sq = chess.square(file, rank)
            piece = board.piece_at(sq)
            sym = piece_symbols.get(piece.symbol(), "·") if piece else "·"

            is_last_from = last_move and last_move.from_square == sq
            is_last_to = last_move and last_move.to_square == sq

            if is_last_to:
                cell_style = "bold white on green"
            elif is_last_from:
                cell_style = "bold black on dark_green"
            elif piece and piece.color == chess.WHITE:
                cell_style = "bold bright_white"
            elif piece and piece.color == chess.BLACK:
                cell_style = "bold bright_yellow"
            else:
                cell_style = "bright_black"

            t.append(f" {sym} ", style=cell_style)
            t.append("│", style="bright_black")

        t.append(f" {rank + 1}\n", style="bold cyan")
        if rank > 0:
            t.append("  ├───┼───┼───┼───┼───┼───┼───┼───┤\n", style="bright_black")
        else:
            t.append("  └───┴───┴───┴───┴───┴───┴───┴───┘\n", style="bright_black")

    t.append("    a   b   c   d   e   f   g   h  ", style="bold cyan")
    return t


def build_dashboard_layout(
    game_data: Optional[Dict[str, Any]],
    leaderboard_data: Optional[List[Dict[str, Any]]],
    corpus_metrics: Optional[Dict[str, Any]],
    status_text: str = "Aguardando próxima partida...",
) -> Layout:
    """Compose the multi-panel Rich dashboard layout."""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=3),
    )

    layout["main"].split_row(
        Layout(name="left", ratio=3),
        Layout(name="right", ratio=4),
    )

    layout["right"].split_column(
        Layout(name="telemetry", size=13),
        Layout(name="leaderboard", ratio=1),
    )

    # 1. Header
    header_text = Text()
    header_text.append("♟ GHERKIN-CHESS LIVE TOURNAMENT DASHBOARD ♟", style="bold bright_white on blue")
    header_text.append("  |  Gate Gherkin-to-Action & OpenSkill Ladder", style="italic white on blue")
    layout["header"].update(Panel(header_text, style="blue"))

    # 2. Chess Board (Left)
    if game_data:
        fen = game_data.get("fen", chess.STARTING_FEN)
        board = chess.Board(fen)
        history = game_data.get("history", [])
        last_move_obj = None
        if history:
            last_m = history[-1]
            try:
                last_move_obj = chess.Move.from_uci(last_m.get("uci", ""))
            except Exception:
                pass

        board_text = build_board_text(board, last_move=last_move_obj)
        turn_str = "Brancas (White)" if board.turn == chess.WHITE else "Pretas (Black)"
        move_num = board.fullmove_number

        board_panel = Panel(
            board_text,
            title=f"[bold cyan]Tabuleiro Oficial[/bold cyan] (Lance #{move_num} • Vez: {turn_str})",
            subtitle=f"[dim]FEN: {fen[:38]}...[/dim]",
            border_style="cyan",
        )
    else:
        empty_board = build_board_text(chess.Board())
        board_panel = Panel(
            empty_board,
            title="[bold cyan]Tabuleiro Oficial[/bold cyan] (Inativo)",
            subtitle="[dim]Nenhuma partida em andamento no momento[/dim]",
            border_style="cyan",
        )
    layout["left"].update(board_panel)

    # 3. Telemetry & Epistemic Trace (Top Right)
    telemetry_table = Table(box=None, expand=True, show_header=False)
    telemetry_table.add_column("Key", style="bold bright_magenta", width=18)
    telemetry_table.add_column("Val", style="bright_white")

    if game_data and game_data.get("history"):
        latest = game_data["history"][-1]
        mode = latest.get("epistemic_mode", "unknown")
        mode_style = "green" if mode == "reuse" else ("yellow" if mode == "divergence" else "cyan")
        
        telemetry_table.add_row("Último Lance:", f"[bold green]{latest.get('san')} ({latest.get('uci')})[/bold green] por {latest.get('turn')}")
        telemetry_table.add_row("Modo Epistêmico:", f"[{mode_style} bold]{mode.upper()}[/{mode_style} bold]")
        telemetry_table.add_row("Cenário OKF:", f"{latest.get('applied_scenario') or 'None'}")
        if latest.get("diverged_from"):
            telemetry_table.add_row("Divergiu de:", f"[yellow]{latest.get('diverged_from')}[/yellow]")
            telemetry_table.add_row("Justificativa:", f"[italic]{latest.get('divergence_reason')}[/italic]")
        telemetry_table.add_row("Origin FEN:", f"[dim]{str(latest.get('origin_fen', ''))[:35]}...[/dim]")
        
        gh_lines = [l.strip() for l in latest.get("gherkin", "").splitlines() if l.strip()][:3]
        telemetry_table.add_row("Gherkin Gate:", f"[italic bright_cyan]{' -> '.join(gh_lines)}[/italic bright_cyan]")
    else:
        telemetry_table.add_row("Status:", "[yellow]Aguardando execução do primeiro lance...[/yellow]")
        telemetry_table.add_row("Agente Brancas:", "DeepSeek-V3 / Gemma-4 (MCP)")
        telemetry_table.add_row("Agente Pretas:", "Nemotron / LFM (Raw)")

    if corpus_metrics:
        telemetry_table.add_row("Corpus OKF:", f"Tot: {corpus_metrics.get('total_applications', 0)} | Reúso: {corpus_metrics.get('reused_count', 0)} | Novos: {corpus_metrics.get('new_knowledge_count', 0)} | Divergências: {corpus_metrics.get('divergence_count', 0)}")

    layout["telemetry"].update(
        Panel(telemetry_table, title="[bold magenta]Telemetria & Epistemologia OKF[/bold magenta]", border_style="magenta")
    )

    # 4. OpenSkill Leaderboard (Bottom Right)
    leaderboard_table = Table(expand=True, border_style="green", header_style="bold bright_green")
    leaderboard_table.add_column("Rank", justify="center", width=4)
    leaderboard_table.add_column("Agente / Modelo", justify="left")
    leaderboard_table.add_column("Ordinal", justify="right")
    leaderboard_table.add_column("μ (Mu)", justify="right")
    leaderboard_table.add_column("σ (Sigma)", justify="right")
    leaderboard_table.add_column("V-E-D", justify="center")

    if leaderboard_data:
        for p in leaderboard_data[:6]:
            leaderboard_table.add_row(
                str(p.get("rank")),
                p.get("name", ""),
                f"[bold yellow]{p.get('ordinal', 0.0):.2f}[/bold yellow]",
                f"{p.get('mu', 25.0):.2f}",
                f"{p.get('sigma', 8.33):.2f}",
                f"{p.get('wins', 0)}-{p.get('draws', 0)}-{p.get('losses', 0)}",
            )
    else:
        leaderboard_table.add_row("-", "Nenhum participante pontuado ainda", "-", "-", "-", "-")

    layout["leaderboard"].update(
        Panel(leaderboard_table, title="[bold green]Placar Bayesiano OpenSkill (Plackett-Luce)[/bold green]", border_style="green")
    )

    # 5. Footer
    footer_text = Text(f" {status_text} • Pressione Ctrl+C para sair", style="bright_yellow")
    layout["footer"].update(Panel(footer_text, style="bright_black"))

    return layout


def monitor_live_dashboard(data_dir: Path, refresh_interval: float = 1.0):
    """Loop to display real-time dashboard from data directory."""
    console = Console()
    session = SessionManager(data_dir)
    leaderboard = LeaderboardManager(data_dir / "leaderboard.json")

    with Live(console=console, screen=True, auto_refresh=False) as live:
        try:
            while True:
                saved_games = session.list_saved_games()
                current_game = saved_games[0] if saved_games else None

                leaderboard._load()
                standings = leaderboard.get_standings()
                metrics = session.corpus.get_application_metrics()

                status = f"Diretório: [{data_dir}] | Partidas arquivadas: {len(saved_games)}"
                if current_game:
                    status += f" | Jogo: {current_game.get('game_id')}"

                layout = build_dashboard_layout(
                    game_data=current_game,
                    leaderboard_data=standings,
                    corpus_metrics=metrics,
                    status_text=status,
                )
                live.update(layout, refresh=True)
                time.sleep(refresh_interval)
        except KeyboardInterrupt:
            pass
