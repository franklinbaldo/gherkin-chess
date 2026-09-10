from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Annotated, Optional
import cyclopts
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from gherkin_chess.cli_dashboard import build_dashboard_layout, monitor_live_dashboard
from gherkin_chess.leaderboard import LeaderboardManager
from gherkin_chess.mcp_server import mcp, session_manager
from gherkin_chess.session import SessionManager
from gherkin_chess.tournament_runner import (
    DEFAULT_MODEL_ROSTER,
    play_tournament_match,
    run_scheduled_batch,
)

app = cyclopts.App(
    name="gherkin-chess",
    help="Gherkin-Chess: Epistemic Chess Environment with Gherkin-to-Action Gates, OKF Materialization, OpenSkill and Live CLI Dashboard",
)


@app.default
def default_cmd():
    """Default action: launches the interactive live match dashboard."""
    data_dir = Path(os.getenv("GHERKIN_CHESS_DATA_DIR", ".live_tournament_data"))
    console = Console()
    console.print(Panel(
        f"[bold cyan]Iniciando Dashboard CLI do Gherkin-Chess[/bold cyan]\n"
        f"Diretório de dados: [yellow]{data_dir.resolve()}[/yellow]\n"
        f"Para executar uma partida ao vivo com dashboard renderizado:\n"
        f"  [green]uv run gherkin-chess play --live[/green]\n\n"
        f"Pressione Ctrl+C a qualquer momento para sair.",
        title="[bold green]♟ GHERKIN-CHESS CLI[/bold green]",
        border_style="green"
    ))
    monitor_live_dashboard(data_dir=data_dir, refresh_interval=1.0)


@app.command(name="dashboard")
def dashboard(
    data_dir: Annotated[Optional[Path], cyclopts.Parameter(help="Path to tournament data directory")] = None,
    refresh: Annotated[float, cyclopts.Parameter(help="Refresh interval in seconds")] = 1.0,
):
    """Acompanhar partidas em tempo real via dashboard interativo no terminal (CLI)."""
    target_dir = data_dir or Path(os.getenv("GHERKIN_CHESS_DATA_DIR", ".live_tournament_data"))
    monitor_live_dashboard(data_dir=target_dir, refresh_interval=refresh)


@app.command(name="play")
def play(
    matches: Annotated[int, cyclopts.Parameter(help="Number of tournament matches to play")] = 1,
    max_plies: Annotated[int, cyclopts.Parameter(help="Max half-moves per match")] = 20,
    data_dir: Annotated[Optional[Path], cyclopts.Parameter(help="Data directory")] = None,
    live: Annotated[bool, cyclopts.Parameter(help="Render live interactive dashboard while matches play")] = True,
):
    """Executa partidas de torneio entre agentes OpenRouter (MCP vs Raw) com placar OpenSkill."""
    target_dir = data_dir or Path(os.getenv("GHERKIN_CHESS_DATA_DIR", ".live_tournament_data"))
    session = SessionManager(target_dir)
    leaderboard = LeaderboardManager(target_dir / "leaderboard.json")
    console = Console()

    import random

    if live:
        with Live(console=console, screen=True, auto_refresh=False) as live_display:
            def update_ui(current_game_id: str, status: str):
                saved_games = session.list_saved_games()
                active = None
                for g in saved_games:
                    if g.get("game_id") == current_game_id:
                        active = g
                        break
                if not active and saved_games:
                    active = saved_games[0]

                leaderboard._load()
                standings = leaderboard.get_standings()
                metrics = session.corpus.get_application_metrics()

                layout = build_dashboard_layout(
                    game_data=active,
                    leaderboard_data=standings,
                    corpus_metrics=metrics,
                    status_text=status,
                )
                live_display.update(layout, refresh=True)

            for i in range(matches):
                p1, p2 = random.sample(DEFAULT_MODEL_ROSTER, 2)
                game_id = f"match_{int(time.time())}_{random.randint(100, 999)}"
                update_ui(game_id, f"Partida {i+1}/{matches}: {p1['name']} (Brancas) vs {p2['name']} (Pretas)...")

                def on_ply_event(info: dict):
                    update_ui(info["game_id"], f"Partida {i+1}/{matches} | Lance #{info['plies_played']} | Vez de {info['game'].board.turn and 'Brancas' or 'Pretas'}")

                play_tournament_match(
                    p1, p2,
                    session=session,
                    leaderboard=leaderboard,
                    max_plies=max_plies,
                    on_ply=on_ply_event,
                )
                update_ui(game_id, f"Partida {i+1}/{matches} concluída!")
    else:
        for i in range(matches):
            p1, p2 = random.sample(DEFAULT_MODEL_ROSTER, 2)
            console.print(f"[bold cyan]Partida {i+1}/{matches}:[/bold cyan] {p1['name']} vs {p2['name']}...")
            res = play_tournament_match(p1, p2, session=session, leaderboard=leaderboard, max_plies=max_plies)
            console.print(f" -> [green]{res['result_desc']}[/green] ({res['plies']} plies em {res['duration_s']}s)")


@app.command(name="leaderboard")
def show_leaderboard(
    data_dir: Annotated[Optional[Path], cyclopts.Parameter(help="Path to tournament data directory")] = None,
):
    """Exibe o placar Bayesiano oficial OpenSkill dos agentes e modelos."""
    target_dir = data_dir or Path(os.getenv("GHERKIN_CHESS_DATA_DIR", ".live_tournament_data"))
    leaderboard = LeaderboardManager(target_dir / "leaderboard.json")
    standings = leaderboard.get_standings()

    console = Console()
    table = Table(
        title="🏆 Placar Oficial OpenSkill (Plackett-Luce Ladder) 🏆",
        border_style="bright_green",
        header_style="bold green",
    )
    table.add_column("Rank", justify="center", width=6)
    table.add_column("Agente / Modelo", justify="left")
    table.add_column("Rating Ordinal (μ - 3σ)", justify="right")
    table.add_column("μ (Habilidade)", justify="right")
    table.add_column("σ (Incerteza)", justify="right")
    table.add_column("Partidas", justify="center")
    table.add_column("V-E-D", justify="center")
    table.add_column("Aproveitamento", justify="right")

    for s in standings:
        table.add_row(
            str(s["rank"]),
            s["name"],
            f"[bold yellow]{s['ordinal']:.2f}[/bold yellow]",
            f"{s['mu']:.2f}",
            f"{s['sigma']:.2f}",
            str(s["matches"]),
            f"{s['wins']}-{s['draws']}-{s['losses']}",
            f"{s['win_rate']}%",
        )

    console.print(table)


@app.command(name="corpus")
def show_corpus(
    data_dir: Annotated[Optional[Path], cyclopts.Parameter(help="Path to tournament data directory")] = None,
):
    """Lista as Features e Cenários OKF materializados no corpus do torneio."""
    target_dir = data_dir or Path(os.getenv("GHERKIN_CHESS_DATA_DIR", ".live_tournament_data"))
    session = SessionManager(target_dir)
    features = session.corpus.load_all_features()
    metrics = session.corpus.get_application_metrics()

    console = Console()
    console.print(f"[bold cyan]Corpus OKF Knowledge Bundle:[/bold cyan] {len(features)} Features materializadas")
    console.print(
        f"Métricas Epistêmicas: [green]{metrics['reused_count']} Reúsos[/green] | "
        f"[cyan]{metrics['new_knowledge_count']} Novos Cenários[/cyan] | "
        f"[yellow]{metrics['divergence_count']} Divergências[/yellow]\n"
    )

    table = Table(title="Features Materializadas no Corpus", border_style="cyan")
    table.add_column("#", justify="center", width=4)
    table.add_column("Nome da Feature", justify="left")
    table.add_column("Origin FEN", justify="left")
    table.add_column("Cenários", justify="center")

    for i, f in enumerate(features, 1):
        table.add_row(
            str(i),
            f.name,
            f"{f.origin_fen[:35]}..." if f.origin_fen else "N/A",
            str(len(f.scenarios)),
        )
    console.print(table)


@app.command(name="mcp")
def run_mcp():
    """Executa o servidor FastMCP (stdio) para conexão com clientes MCP."""
    mcp.run()


@app.command(name="web")
def run_web_server(port: Annotated[int, cyclopts.Parameter(help="Port for Web UI")] = 8000):
    """Executa a interface Web opcional para observadores."""
    from gherkin_chess.web_server import run_web
    run_web(port=port)


def main():
    import time
    app()


if __name__ == "__main__":
    main()
