"""
Chess game using Flet with python-chess engine and SVG pieces.
"""

import asyncio
import time

import flet as ft
from chess_logic import ChessGame
from opening_book import get_opening_name, get_common_moves
from pieces_svg import get_svg
from lichess import (
    LichessDailyPuzzle,
    fetch_daily_puzzle,
    format_themes,
    get_solution_san,
)
from puzzles import PUZZLES
from bots import BotBot, ChessBot, MinimaxBot, SimpleBot
from game_state import GameState, clear_game_state, load_game_state, save_game_state
from elo import (
    EloProfile,
    get_bot_display_name,
    get_bot_elo,
    get_difficulty_label,
    get_recent_form,
    get_win_rate,
    load_elo_profile,
    recommend_opponent,
    record_game,
    save_elo_profile,
    reset_elo_profile,
)

LIGHT_SQUARE = "#f0d9b5"
DARK_SQUARE = "#b58863"
HIGHLIGHT = "#7fc97f"
HIGHLIGHT_CAPTURE = "#f27777"
SELECTED = "#baca44"
HINT_FROM = "#ffd700"  # Gold for hint source square
HINT_TO = "#ffa500"  # Orange for hint destination square


def main(page: ft.Page):
    page.title = "Chess"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.window.min_width = 600
    page.window.min_height = 560

    game = ChessGame()
    selected = None  # (row, col) or None
    valid_moves = []  # list of (row, col)
    hint_moves = []  # list of ((from_row, from_col), (to_row, to_col), score, san) for hint visualization
    game_over = False
    message = ft.Ref[ft.Text]()
    history_text = ft.Ref[ft.Text]()
    white_clock_text = ft.Ref[ft.Text]()
    black_clock_text = ft.Ref[ft.Text]()
    eval_bar_container = ft.Ref[ft.Container]()
    eval_text = ft.Ref[ft.Text]()
    opening_name_text = ft.Ref[ft.Text]()
    opening_desc_text = ft.Ref[ft.Text]()
    common_moves_column = ft.Ref[ft.Column]()

    # Game clock: each player has fixed time; runs down on their turn
    time_control_secs = 300  # 5 min default; set by dropdown for next game
    white_remaining_secs = float(time_control_secs)
    black_remaining_secs = float(time_control_secs)
    move_start_time = time.monotonic()
    clock_enabled = True  # False when playing puzzles (no time pressure)
    clock_started = (
        False  # True only after white's first move (clock does not run until then)
    )

    # Per-player: "human" | "random" | "botbot" | "minimax_1" | ...
    white_player = "human"
    black_player = "human"
    bot_vs_bot_running = False
    player_bots: dict[str, ChessBot] = {
        "random": SimpleBot(randomness=1.0),  # Fully random
        "botbot": BotBot(randomness=0.5),  # Moderate randomness
        "minimax_1": MinimaxBot(depth=1, randomness=0.3),
        "minimax_2": MinimaxBot(depth=2, randomness=0.3),
        "minimax_3": MinimaxBot(depth=3, randomness=0.3),
        "minimax_4": MinimaxBot(depth=4, randomness=0.3),
    }

    # ELO rating system
    elo_profile: EloProfile = load_elo_profile()
    elo_rating_text = ft.Ref[ft.Text]()
    elo_label_text = ft.Ref[ft.Text]()
    elo_form_text = ft.Ref[ft.Text]()
    elo_record_text = ft.Ref[ft.Text]()
    elo_peak_text = ft.Ref[ft.Text]()
    elo_recommendation_text = ft.Ref[ft.Text]()
    elo_updated_this_game = False  # Guard: only update ELO once per game

    def update_elo_display():
        """Refresh all ELO-related UI elements."""
        if elo_rating_text.current is not None:
            elo_rating_text.current.value = str(elo_profile.rating)
            try:
                elo_rating_text.current.update()
            except RuntimeError:
                pass

        if elo_label_text.current is not None:
            elo_label_text.current.value = get_difficulty_label(elo_profile.rating)
            try:
                elo_label_text.current.update()
            except RuntimeError:
                pass

        if elo_form_text.current is not None:
            elo_form_text.current.value = get_recent_form(elo_profile)
            try:
                elo_form_text.current.update()
            except RuntimeError:
                pass

        if elo_record_text.current is not None:
            elo_record_text.current.value = (
                f"{elo_profile.wins}W / {elo_profile.draws}D / {elo_profile.losses}L"
            )
            try:
                elo_record_text.current.update()
            except RuntimeError:
                pass

        if elo_peak_text.current is not None:
            elo_peak_text.current.value = f"Peak: {elo_profile.peak_rating}"
            try:
                elo_peak_text.current.update()
            except RuntimeError:
                pass

        if elo_recommendation_text.current is not None:
            rec_key = recommend_opponent(elo_profile.rating)
            rec_name = get_bot_display_name(rec_key)
            rec_elo = get_bot_elo(rec_key)
            elo_recommendation_text.current.value = f"{rec_name} (~{rec_elo})"
            try:
                elo_recommendation_text.current.update()
            except RuntimeError:
                pass

    def handle_game_over_elo(result_for_white: float | None):
        """Update ELO after a game ends (human vs bot only).

        Args:
            result_for_white: 1.0 if white won, 0.0 if black won, 0.5 if draw,
                            None if not applicable (bot vs bot or human vs human).
        """
        nonlocal elo_updated_this_game
        if elo_updated_this_game or result_for_white is None:
            return

        # Determine which side the human is playing and which bot they face
        human_color = None
        opponent_key = None
        if white_player == "human" and black_player != "human":
            human_color = "white"
            opponent_key = black_player
        elif black_player == "human" and white_player != "human":
            human_color = "black"
            opponent_key = white_player
        else:
            return  # human vs human or bot vs bot: no ELO update

        # Calculate result from human's perspective
        if human_color == "white":
            human_result = result_for_white
        else:
            human_result = 1.0 - result_for_white

        record_game(elo_profile, opponent_key, human_result)
        save_elo_profile(elo_profile)
        elo_updated_this_game = True
        update_elo_display()

    def get_bot_for_turn() -> ChessBot | None:
        if game.turn == "white":
            return player_bots.get(white_player)
        return player_bots.get(black_player)

    def is_human_turn() -> bool:
        if game.turn == "white":
            return white_player == "human"
        return black_player == "human"

    def is_bot_vs_bot() -> bool:
        return white_player != "human" and black_player != "human"

    def save_current_state():
        """Persist the full game state to disk (called after every move)."""
        state = GameState(
            initial_fen=game.get_initial_fen(),
            moves_uci=game.get_moves_uci(),
            white_player=white_player,
            black_player=black_player,
            time_control_secs=time_control_secs,
            white_remaining_secs=white_remaining_secs,
            black_remaining_secs=black_remaining_secs,
            clock_enabled=clock_enabled,
            clock_started=clock_started,
        )
        save_game_state(state)

    def format_clock(seconds: float) -> str:
        """Format remaining time as M:SS or 0:00 when out of time."""
        secs = max(0.0, seconds)
        m = int(secs // 60)
        s = int(secs % 60)
        return f"{m}:{s:02d}"

    def update_clock_display():
        """Refresh both players' clock display (remaining time, active = running). When clock disabled, show 'Clock off'. Before white's first move, show full time and do not count down."""
        if not clock_enabled:
            if white_clock_text.current is not None:
                white_clock_text.current.value = "—"
                white_clock_text.current.weight = ft.FontWeight.NORMAL
                try:
                    white_clock_text.current.update()
                except RuntimeError:
                    pass
            if black_clock_text.current is not None:
                black_clock_text.current.value = "—"
                black_clock_text.current.weight = ft.FontWeight.NORMAL
                try:
                    black_clock_text.current.update()
                except RuntimeError:
                    pass
            return
        if not clock_started:
            # Before white's first move: show full time for both, no countdown
            if white_clock_text.current is not None:
                white_clock_text.current.value = format_clock(white_remaining_secs)
                white_clock_text.current.weight = (
                    ft.FontWeight.BOLD if game.turn == "white" else ft.FontWeight.NORMAL
                )
                try:
                    white_clock_text.current.update()
                except RuntimeError:
                    pass
            if black_clock_text.current is not None:
                black_clock_text.current.value = format_clock(black_remaining_secs)
                black_clock_text.current.weight = (
                    ft.FontWeight.BOLD if game.turn == "black" else ft.FontWeight.NORMAL
                )
                try:
                    black_clock_text.current.update()
                except RuntimeError:
                    pass
            return
        now = time.monotonic()
        if game.turn == "white":
            white_effective = white_remaining_secs - (now - move_start_time)
            black_effective = black_remaining_secs
        else:
            white_effective = white_remaining_secs
            black_effective = black_remaining_secs - (now - move_start_time)
        if white_clock_text.current is not None:
            white_clock_text.current.value = format_clock(white_effective)
            white_clock_text.current.weight = (
                ft.FontWeight.BOLD if game.turn == "white" else ft.FontWeight.NORMAL
            )
            try:
                white_clock_text.current.update()
            except RuntimeError:
                pass
        if black_clock_text.current is not None:
            black_clock_text.current.value = format_clock(black_effective)
            black_clock_text.current.weight = (
                ft.FontWeight.BOLD if game.turn == "black" else ft.FontWeight.NORMAL
            )
            try:
                black_clock_text.current.update()
            except RuntimeError:
                pass

    def deduct_move_time_and_check_game_over():
        """Call after a move is applied: deduct elapsed time from the player who moved; end game if they ran out. No-op when clock disabled. Clock does not run until after white's first move."""
        if not clock_enabled:
            update_clock_display()
            return
        nonlocal \
            move_start_time, \
            white_remaining_secs, \
            black_remaining_secs, \
            game_over, \
            clock_started
        now = time.monotonic()
        if not clock_started:
            # White just made first move; start the clock now (no deduction for white)
            clock_started = True
            move_start_time = now
            update_clock_display()
            return
        elapsed = now - move_start_time
        move_start_time = now
        # The player who just moved had their clock running (it was their turn before the move)
        if game.turn == "black":
            white_remaining_secs -= elapsed
            if white_remaining_secs <= 0:
                game_over = True
                message.current.value = "White ran out of time. Black wins."
                message.current.color = ft.Colors.BLUE
                handle_game_over_elo(0.0)  # Black wins
        else:
            black_remaining_secs -= elapsed
            if black_remaining_secs <= 0:
                game_over = True
                message.current.value = "Black ran out of time. White wins."
                message.current.color = ft.Colors.BLUE
                handle_game_over_elo(1.0)  # White wins
        update_clock_display()

    async def run_clock():
        """Periodically update clock display and end game if current player runs out of time. Does nothing when clock disabled or before white's first move."""
        nonlocal game_over
        while True:
            if game_over or not clock_enabled or not clock_started:
                if clock_enabled:
                    update_clock_display()
                await asyncio.sleep(0.5)
                continue
            now = time.monotonic()
            if game.turn == "white":
                effective = white_remaining_secs - (now - move_start_time)
            else:
                effective = black_remaining_secs - (now - move_start_time)
            if effective <= 0:
                game_over = True
                if game.turn == "white":
                    message.current.value = "White ran out of time. Black wins."
                    handle_game_over_elo(0.0)  # Black wins
                else:
                    message.current.value = "Black ran out of time. White wins."
                    handle_game_over_elo(1.0)  # White wins
                message.current.color = ft.Colors.BLUE
                update_clock_display()
                page.update()
            else:
                update_clock_display()
                try:
                    if (
                        white_clock_text.current is not None
                        and black_clock_text.current is not None
                    ):
                        page.update(white_clock_text.current, black_clock_text.current)
                except RuntimeError:
                    pass
            await asyncio.sleep(0.2)

    def get_square_size(
        override_width: float | None = None, override_height: float | None = None
    ) -> int:
        w = (
            override_width
            if override_width is not None
            else (getattr(page, "width", None) or 800)
        )
        h = (
            override_height
            if override_height is not None
            else (getattr(page, "height", None) or 600)
        )
        # Reserve space for app bar, status bar, and history panel
        history_width = 220
        side = min(max(200, w - history_width), max(200, h - 120))
        return max(32, int(side) // 8)

    square_size = 64  # updated in refresh_board()

    def square_color(row: int, col: int) -> str:
        is_light = (row + col) % 2 == 0
        return LIGHT_SQUARE if is_light else DARK_SQUARE

    def build_square(row: int, col: int) -> ft.Container:
        cell = game.piece_at(row, col)
        bg = square_color(row, col)

        # Only show hints during human turns
        show_hints = is_human_turn() and hint_moves
        is_hint_from = show_hints and any(
            (row, col) == hint_from for hint_from, _, _, _ in hint_moves
        )
        is_hint_to = show_hints and any(
            (row, col) == hint_to for _, hint_to, _, _ in hint_moves
        )

        if selected == (row, col):
            bg = SELECTED
        elif is_hint_from:
            bg = HINT_FROM
        elif is_hint_to:
            bg = HINT_TO
        elif (row, col) in valid_moves:
            bg = HIGHLIGHT_CAPTURE if cell is not None else HIGHLIGHT

        content_list = []
        if cell is not None:
            color, piece = cell
            svg = get_svg(color, piece)
            pad = max(4, square_size // 8)
            content_list.append(
                ft.Image(
                    src=svg,
                    width=square_size - pad,
                    height=square_size - pad,
                    fit=ft.BoxFit.CONTAIN,
                )
            )

        square_content = ft.Stack(
            controls=content_list,
            width=square_size,
            height=square_size,
            alignment=ft.Alignment(0, 0),
        )

        def on_tap(e):
            nonlocal selected, valid_moves, hint_moves, game_over
            if game_over:
                return
            if not is_human_turn():
                refresh_board()
                return
            if selected is not None and (row, col) in valid_moves:
                game.make_move(selected[0], selected[1], row, col)
                selected = None
                valid_moves = []
                hint_moves = []  # Clear hints after making a move
                deduct_move_time_and_check_game_over()
                update_status()
                update_undo_button()
                update_history()
                update_evaluation_bar()
                update_opening_explorer()
                save_current_state()
                refresh_board()
                page.update()
                if not game_over and not is_human_turn():
                    page.run_task(bot_move_after_human)
                return
            if selected is not None:
                selected = None
                valid_moves = []
            if cell is not None and cell[0] == game.turn:
                selected = (row, col)
                valid_moves = game.legal_moves_from(row, col)
            refresh_board()

        return ft.GestureDetector(
            on_tap=on_tap,
            content=ft.Container(
                content=square_content,
                width=square_size,
                height=square_size,
                bgcolor=bg,
                border=ft.border.all(0, "transparent"),
            ),
        )

    def refresh_board(
        override_width: float | None = None, override_height: float | None = None
    ):
        nonlocal square_size
        square_size = get_square_size(override_width, override_height)
        grid.controls.clear()
        for r in range(8):
            row_controls = [build_square(r, c) for c in range(8)]
            grid.controls.append(ft.Row(controls=row_controls, spacing=0))
        page.update()

    async def bot_move_after_human():
        """Yield to event loop so UI repaints, then run bot move."""
        await asyncio.sleep(0.05)
        play_bot_turn()

    def play_bot_turn():
        """Get one move from bot for current side to move, apply it, and refresh UI."""
        nonlocal selected, valid_moves, hint_moves, game_over
        bot = get_bot_for_turn()
        if not bot or game_over:
            return
        move = bot.choose_move(game.get_board())
        if move is None or not game.apply_move(move):
            return
        selected = None
        valid_moves = []
        hint_moves = []  # Clear hints after bot move
        deduct_move_time_and_check_game_over()
        update_status()
        update_undo_button()
        update_history()
        update_evaluation_bar()
        update_opening_explorer()
        save_current_state()
        refresh_board()
        page.update()

    async def run_bot_vs_bot():
        """Run bot-vs-bot loop in background so UI stays responsive."""
        nonlocal selected, valid_moves, hint_moves, game_over, bot_vs_bot_running
        if bot_vs_bot_running or game_over:
            return
        bot = get_bot_for_turn()
        if not bot:
            return
        bot_vs_bot_running = True
        try:
            while is_bot_vs_bot() and not game_over:
                bot = get_bot_for_turn()
                if not bot:
                    break
                move = bot.choose_move(game.get_board())
                if move is None or not game.apply_move(move):
                    break
                selected = None
                valid_moves = []
                hint_moves = []  # Clear hints after bot move
                deduct_move_time_and_check_game_over()
                update_status()
                update_undo_button()
                update_history()
                update_evaluation_bar()
                update_opening_explorer()
                save_current_state()
                refresh_board()
                page.update()
                if game_over:
                    break
                await asyncio.sleep(0.4)
        finally:
            bot_vs_bot_running = False

    def update_status():
        nonlocal game_over, hint_moves
        # Clear hints when it's not a human's turn
        if not is_human_turn():
            hint_moves = []
        if game.is_checkmate():
            winner = "Black" if game.turn == "white" else "White"
            message.current.value = f"Checkmate! {winner} wins."
            message.current.color = ft.Colors.BLUE
            game_over = True
            # ELO: white wins = 1.0, black wins = 0.0
            result_for_white = 0.0 if game.turn == "white" else 1.0
            handle_game_over_elo(result_for_white)
        elif game.is_stalemate():
            message.current.value = "Stalemate. Draw."
            message.current.color = ft.Colors.ORANGE
            game_over = True
            handle_game_over_elo(0.5)
        elif game.is_only_kings_left():
            message.current.value = "Draw. Only kings left."
            message.current.color = ft.Colors.ORANGE
            game_over = True
            handle_game_over_elo(0.5)
        elif game.is_in_check():
            message.current.value = f"{game.turn.capitalize()} is in check."
            message.current.color = ft.Colors.RED
        else:
            message.current.value = f"{game.turn.capitalize()} to move."
            message.current.color = ft.Colors.BLACK

    grid = ft.Column(spacing=0)
    for r in range(8):
        row_controls = [build_square(r, c) for c in range(8)]
        grid.controls.append(ft.Row(controls=row_controls, spacing=0))

    status_bar = ft.Container(
        content=ft.Row(
            [
                ft.Text(
                    ref=message,
                    value="White to move.",
                    size=16,
                    weight=ft.FontWeight.W_500,
                ),
                ft.Container(expand=True),
                ft.Row(
                    [
                        ft.Text("White ", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(
                            ref=white_clock_text,
                            value=format_clock(time_control_secs),
                            size=14,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            "  Black ", size=14, color=ft.Colors.ON_SURFACE_VARIANT
                        ),
                        ft.Text(
                            ref=black_clock_text,
                            value=format_clock(time_control_secs),
                            size=14,
                        ),
                    ],
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.symmetric(12, 16),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
    )

    def do_new_game(_):
        """Reset the game (called after confirmation)."""
        nonlocal \
            selected, \
            valid_moves, \
            hint_moves, \
            game_over, \
            white_remaining_secs, \
            black_remaining_secs, \
            move_start_time, \
            clock_enabled, \
            clock_started, \
            elo_updated_this_game
        page.pop_dialog()
        game.reset()
        selected = None
        valid_moves = []
        hint_moves = []
        game_over = False
        elo_updated_this_game = False
        clock_started = False
        if time_control_secs is None:
            clock_enabled = False
            white_remaining_secs = 0.0
            black_remaining_secs = 0.0
        else:
            clock_enabled = True
            white_remaining_secs = float(time_control_secs)
            black_remaining_secs = float(time_control_secs)
        move_start_time = time.monotonic()
        message.current.value = "White to move."
        message.current.color = ft.Colors.BLACK
        clear_game_state()
        update_clock_display()
        refresh_board()
        update_undo_button()
        update_history()
        update_evaluation_bar()
        update_opening_explorer()
        update_elo_display()
        page.update()
        if is_bot_vs_bot() and get_bot_for_turn() and not game_over:
            page.run_task(run_bot_vs_bot)

    def do_undo(_):
        nonlocal \
            selected, \
            valid_moves, \
            hint_moves, \
            game_over, \
            move_start_time, \
            clock_started
        if not game.undo():
            return
        selected = None
        valid_moves = []
        hint_moves = []  # Clear hints when undoing
        game_over = False
        move_start_time = time.monotonic()
        # If we undid back to the starting position, clock has not "started" yet
        if clock_enabled:
            clock_started = game.can_undo()
        update_status()
        update_clock_display()
        save_current_state()
        refresh_board()
        update_undo_button()
        update_history()
        update_evaluation_bar()
        update_opening_explorer()
        page.update()

    def update_history():
        if history_text.current is None:
            return
        history_text.current.value = game.get_move_history() or "No moves yet."
        try:
            history_text.current.update()
        except RuntimeError:
            pass  # control not on page yet

    def update_opening_explorer():
        """Update the opening explorer with current position info."""
        opening_name, opening_desc = get_opening_name(game.get_board())

        # Update opening name
        if opening_name_text.current is not None:
            if opening_name:
                opening_name_text.current.value = opening_name
                opening_name_text.current.color = ft.Colors.PURPLE
                opening_name_text.current.weight = ft.FontWeight.W_600
            else:
                opening_name_text.current.value = "No opening identified"
                opening_name_text.current.color = ft.Colors.ON_SURFACE_VARIANT
                opening_name_text.current.weight = ft.FontWeight.NORMAL
            try:
                opening_name_text.current.update()
            except RuntimeError:
                pass

        # Update opening description
        if opening_desc_text.current is not None:
            if opening_desc:
                opening_desc_text.current.value = opening_desc
                opening_desc_text.current.color = ft.Colors.ON_SURFACE_VARIANT
            else:
                opening_desc_text.current.value = ""
            try:
                opening_desc_text.current.update()
            except RuntimeError:
                pass

        # Update common moves
        if common_moves_column.current is not None:
            common_moves = get_common_moves(game.get_board())
            common_moves_column.current.controls.clear()

            if common_moves:
                # Show top 5 moves
                for move, san, score in common_moves[:5]:
                    # Create a visual indicator for move popularity
                    stars = "★" * min(score // 2, 5)
                    move_text = f"{san} {stars}"

                    # Color based on score
                    if score >= 8:
                        color = ft.Colors.GREEN
                    elif score >= 5:
                        color = ft.Colors.BLUE
                    else:
                        color = ft.Colors.ON_SURFACE_VARIANT

                    move_control = ft.Text(
                        move_text,
                        size=12,
                        color=color,
                        weight=ft.FontWeight.W_500
                        if score >= 7
                        else ft.FontWeight.NORMAL,
                    )
                    common_moves_column.current.controls.append(move_control)
            else:
                common_moves_column.current.controls.append(
                    ft.Text(
                        "No moves available",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    )
                )

            try:
                common_moves_column.current.update()
            except RuntimeError:
                pass

    def format_evaluation(centipawns: int) -> str:
        """Format evaluation in a human-readable way."""
        if abs(centipawns) >= 100_000:
            # Checkmate
            if centipawns > 0:
                return "M+"
            else:
                return "M-"
        pawns = centipawns / 100.0
        if pawns >= 0:
            return f"+{pawns:.2f}"
        return f"{pawns:.2f}"

    def update_evaluation_bar():
        """Update the evaluation bar display."""
        if eval_bar_container.current is None or eval_text.current is None:
            return

        try:
            eval_score = game.get_position_evaluation(depth=2)
            pawns = eval_score / 100.0

            # Clamp evaluation for visual display (max ±10 pawns)
            clamped_pawns = max(-10.0, min(10.0, pawns))

            # Calculate bar position: 0.0 = all white, 1.0 = all black, 0.5 = equal
            # Positive eval (white advantage) moves bar left, negative (black advantage) moves right
            bar_position = 0.5 - (clamped_pawns / 20.0)  # Scale to 0-1 range
            bar_position = max(0.0, min(1.0, bar_position))

            # Calculate bar width percentages
            white_width_pct = bar_position * 100

            # Update text
            eval_text.current.value = format_evaluation(eval_score)
            if abs(eval_score) >= 100_000:
                eval_text.current.color = ft.Colors.RED
            elif abs(pawns) > 2.0:
                eval_text.current.color = ft.Colors.ORANGE
            else:
                eval_text.current.color = ft.Colors.BLACK

            # Update bar visual using Stack for proper positioning
            bar_width = 200
            white_width = int(bar_width * white_width_pct / 100)
            black_width = bar_width - white_width

            eval_bar_container.current.content = ft.Stack(
                [
                    # Black background (full width)
                    ft.Container(
                        width=bar_width,
                        height=20,
                        bgcolor=ft.Colors.BLACK,
                    ),
                    # White overlay (from left)
                    ft.Container(
                        width=white_width,
                        height=20,
                        bgcolor=ft.Colors.WHITE,
                        border=ft.border.only(
                            right=ft.BorderSide(1, ft.Colors.OUTLINE)
                            if black_width > 0
                            else None
                        ),
                    ),
                ],
                width=bar_width,
                height=20,
            )

            eval_text.current.update()
            eval_bar_container.current.update()
        except RuntimeError:
            pass  # control not on page yet

    def update_undo_button():
        if undo_btn.current is None:
            return
        undo_btn.current.disabled = not game.can_undo()
        if undo_btn.current.page is not None:
            undo_btn.current.update()
            page.update(undo_btn.current)

    player_options = [
        ft.DropdownOption(key="human", text="Human"),
        ft.DropdownOption(key="random", text="Random"),
        ft.DropdownOption(key="botbot", text="BotBot"),
        ft.DropdownOption(key="minimax_1", text="Minimax 1"),
        ft.DropdownOption(key="minimax_2", text="Minimax 2"),
        ft.DropdownOption(key="minimax_3", text="Minimax 3"),
        ft.DropdownOption(key="minimax_4", text="Minimax 4"),
    ]
    time_options = [
        ft.DropdownOption(key="unlimited", text="Unlimited"),
        ft.DropdownOption(key="60", text="1 min"),
        ft.DropdownOption(key="180", text="3 min"),
        ft.DropdownOption(key="300", text="5 min"),
        ft.DropdownOption(key="600", text="10 min"),
    ]

    config_time_ref = ft.Ref[ft.Dropdown]()
    config_white_ref = ft.Ref[ft.Dropdown]()
    config_black_ref = ft.Ref[ft.Dropdown]()

    def apply_config(_=None):
        """Apply configuration from dialog and close it."""
        nonlocal \
            white_player, \
            black_player, \
            time_control_secs, \
            clock_enabled, \
            clock_started, \
            white_remaining_secs, \
            black_remaining_secs, \
            move_start_time
        page.pop_dialog()
        if config_time_ref.current is not None:
            raw = config_time_ref.current.value or "300"
            if raw == "unlimited":
                time_control_secs = None
                clock_enabled = False  # take effect in current game
            else:
                try:
                    time_control_secs = int(raw)
                except (ValueError, TypeError):
                    time_control_secs = 300
                clock_enabled = True  # take effect in current game
                white_remaining_secs = float(time_control_secs)
                black_remaining_secs = float(time_control_secs)
                move_start_time = time.monotonic()
                # Clock runs only after white's first move
                clock_started = game.can_undo()
        if config_white_ref.current is not None:
            white_player = config_white_ref.current.value or "human"
        if config_black_ref.current is not None:
            black_player = config_black_ref.current.value or "human"
        update_status()
        update_clock_display()
        update_evaluation_bar()
        save_current_state()
        page.update()
        if game_over:
            return
        if is_bot_vs_bot():
            page.run_task(run_bot_vs_bot)
        elif not is_human_turn() and get_bot_for_turn():
            page.run_task(bot_move_after_human)

    config_dialog = ft.AlertDialog(
        title=ft.Text("Configuration"),
        content=ft.Column(
            [
                ft.Text("Time control", size=14, weight=ft.FontWeight.W_500),
                ft.Dropdown(
                    ref=config_time_ref,
                    value="unlimited"
                    if time_control_secs is None
                    else str(time_control_secs),
                    width=200,
                    options=time_options,
                ),
                ft.Text("White", size=14, weight=ft.FontWeight.W_500),
                ft.Dropdown(
                    ref=config_white_ref,
                    value=white_player,
                    width=200,
                    options=player_options,
                ),
                ft.Text("Black", size=14, weight=ft.FontWeight.W_500),
                ft.Dropdown(
                    ref=config_black_ref,
                    value=black_player,
                    width=200,
                    options=player_options,
                ),
            ],
            tight=True,
            spacing=8,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
            ft.TextButton("OK", on_click=apply_config),
        ],
        open=False,
    )

    def show_config_dialog(_):
        page.show_dialog(config_dialog)
        # Sync dialog dropdowns to current config (in case dialog was opened before)
        if config_time_ref.current is not None:
            config_time_ref.current.value = (
                "unlimited" if time_control_secs is None else str(time_control_secs)
            )
            config_time_ref.current.update()
        if config_white_ref.current is not None:
            config_white_ref.current.value = white_player
            config_white_ref.current.update()
        if config_black_ref.current is not None:
            config_black_ref.current.value = black_player
            config_black_ref.current.update()
        page.update()

    undo_btn = ft.Ref[ft.IconButton]()

    new_game_dialog = ft.AlertDialog(
        title=ft.Text("New game"),
        content=ft.Text("Start a new game? The current game will be lost."),
        actions=[
            ft.TextButton(
                "Cancel",
                on_click=lambda e: page.pop_dialog(),
            ),
            ft.TextButton("New game", on_click=do_new_game),
        ],
        open=False,
    )

    def show_new_game_dialog(_):
        page.show_dialog(new_game_dialog)

    def load_puzzle(index: int):
        """Load puzzle by index and close dialog."""
        page.pop_dialog()
        if index < 0 or index >= len(PUZZLES):
            return
        name, fen, _, puzzle_clock_enabled = PUZZLES[index]
        if not game.set_fen(fen):
            return
        nonlocal \
            selected, \
            valid_moves, \
            hint_moves, \
            game_over, \
            clock_enabled, \
            clock_started, \
            elo_updated_this_game
        selected = None
        valid_moves = []
        hint_moves = []  # Clear hints when loading puzzle
        elo_updated_this_game = False
        clock_enabled = puzzle_clock_enabled
        clock_started = puzzle_clock_enabled and game.can_undo()
        game_over = (
            game.is_checkmate() or game.is_stalemate() or game.is_only_kings_left()
        )
        update_status()
        update_clock_display()
        save_current_state()
        refresh_board()
        update_undo_button()
        update_history()
        update_evaluation_bar()
        update_opening_explorer()
        page.update()

    def make_puzzle_tile(index: int, name: str, desc: str):
        return ft.ListTile(
            title=ft.Text(name, size=14, weight=ft.FontWeight.W_500),
            subtitle=ft.Text(desc, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            on_click=lambda e, idx=index: load_puzzle(idx),
        )

    puzzle_list_controls = [
        make_puzzle_tile(i, name, desc)
        for i, (name, _fen, desc, _clock) in enumerate(PUZZLES)
    ]

    # ------------------------------------------------------------------
    # Lichess Daily Puzzle
    # ------------------------------------------------------------------
    daily_puzzle_cache: dict[str, LichessDailyPuzzle | None] = {}

    def _load_daily_puzzle_fen(puzzle: LichessDailyPuzzle):
        """Load a Lichess daily puzzle into the game board."""
        if not game.set_fen(puzzle.fen):
            return
        nonlocal \
            selected, \
            valid_moves, \
            hint_moves, \
            game_over, \
            clock_enabled, \
            clock_started, \
            elo_updated_this_game
        selected = None
        valid_moves = []
        hint_moves = []
        elo_updated_this_game = False
        clock_enabled = False  # Puzzles have no clock
        clock_started = False
        game_over = (
            game.is_checkmate() or game.is_stalemate() or game.is_only_kings_left()
        )
        # Show puzzle info in the status bar
        turn = game.turn.capitalize()
        message.current.value = (
            f"Lichess Daily Puzzle (Rating {puzzle.rating}) — {turn} to move."
        )
        message.current.color = ft.Colors.DEEP_PURPLE
        update_clock_display()
        save_current_state()
        refresh_board()
        update_undo_button()
        update_history()
        update_evaluation_bar()
        update_opening_explorer()
        page.update()

    def _show_daily_puzzle_dialog(puzzle: LichessDailyPuzzle):
        """Show a dialog with daily puzzle details and a Play button."""
        # Format metadata
        themes_str = format_themes(puzzle.themes) if puzzle.themes else "—"
        solution_san = get_solution_san(puzzle)
        solution_str = " → ".join(solution_san) if solution_san else "—"
        turn_color = "Black" if " b " in puzzle.fen else "White"

        # Build the solution reveal as a hidden-by-default element
        solution_text = ft.Text(
            solution_str,
            size=13,
            weight=ft.FontWeight.W_500,
            color=ft.Colors.GREEN,
            visible=False,
        )

        def toggle_solution(_):
            solution_text.visible = not solution_text.visible
            solution_text.update()

        content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Rating:", size=13, weight=ft.FontWeight.W_500),
                        ft.Text(
                            str(puzzle.rating),
                            size=13,
                            color=ft.Colors.DEEP_PURPLE,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Container(width=16),
                        ft.Text("Plays:", size=13, weight=ft.FontWeight.W_500),
                        ft.Text(
                            f"{puzzle.plays:,}",
                            size=13,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    spacing=6,
                ),
                ft.Row(
                    [
                        ft.Text("To move:", size=13, weight=ft.FontWeight.W_500),
                        ft.Text(turn_color, size=13, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=6,
                ),
                ft.Row(
                    [
                        ft.Text("Themes:", size=13, weight=ft.FontWeight.W_500),
                        ft.Text(
                            themes_str,
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            expand=True,
                        ),
                    ],
                    spacing=6,
                ),
                ft.Divider(height=1),
                ft.Row(
                    [
                        ft.Text("Solution:", size=13, weight=ft.FontWeight.W_500),
                        ft.TextButton("Reveal", on_click=toggle_solution),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                solution_text,
                ft.Divider(height=1),
                ft.Text(
                    f"From game: lichess.org/{puzzle.game_id}",
                    size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            tight=True,
            spacing=8,
        )

        def play_puzzle(_):
            page.pop_dialog()
            _load_daily_puzzle_fen(puzzle)

        dp_dialog = ft.AlertDialog(
            title=ft.Text("Lichess Daily Puzzle", weight=ft.FontWeight.W_600),
            content=ft.Container(content=content, width=420),
            actions=[
                ft.TextButton("Close", on_click=lambda e: page.pop_dialog()),
                ft.TextButton("Play", on_click=play_puzzle),
            ],
            open=False,
        )
        page.show_dialog(dp_dialog)

    def do_fetch_daily_puzzle(_):
        """Fetch and display the Lichess daily puzzle."""
        # Show a brief loading indicator in the status bar
        if message.current is not None:
            message.current.value = "Fetching Lichess daily puzzle…"
            message.current.color = ft.Colors.BLUE
            page.update()

        puzzle = fetch_daily_puzzle()

        if puzzle is None:
            if message.current is not None:
                message.current.value = (
                    "Could not fetch the daily puzzle. Check your internet connection."
                )
                message.current.color = ft.Colors.RED
                page.update()
            return

        daily_puzzle_cache["latest"] = puzzle
        _show_daily_puzzle_dialog(puzzle)

    # ------------------------------------------------------------------
    # Puzzles dialog (local + daily puzzle)
    # ------------------------------------------------------------------

    puzzles_dialog = ft.AlertDialog(
        title=ft.Text("Puzzles & Scenarios"),
        content=ft.Container(
            content=ft.Column(
                [
                    # Daily puzzle button at the top
                    ft.Container(
                        content=ft.ListTile(
                            leading=ft.Icon(
                                ft.Icons.PUBLIC, color=ft.Colors.DEEP_PURPLE
                            ),
                            title=ft.Text(
                                "Lichess Daily Puzzle",
                                size=14,
                                weight=ft.FontWeight.W_600,
                                color=ft.Colors.DEEP_PURPLE,
                            ),
                            subtitle=ft.Text(
                                "Fetch today's puzzle from lichess.org",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            on_click=do_fetch_daily_puzzle,
                        ),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                        border_radius=8,
                    ),
                    ft.Divider(height=1),
                    # Existing local puzzles
                    *puzzle_list_controls,
                ],
                scroll=ft.ScrollMode.AUTO,
                tight=True,
                spacing=0,
            ),
            width=400,
            height=400,
        ),
        actions=[
            ft.TextButton("Close", on_click=lambda e: page.pop_dialog()),
        ],
        open=False,
    )

    def show_puzzles_dialog(_):
        page.show_dialog(puzzles_dialog)

    def do_reset_elo(_):
        """Reset the player's ELO rating after confirmation."""
        nonlocal elo_profile
        page.pop_dialog()
        reset_elo_profile()
        elo_profile = EloProfile()
        update_elo_display()
        page.update()

    def _build_elo_history_controls() -> list[ft.Control]:
        """Build the rating history list for the ELO dialog."""
        controls = []
        if not elo_profile.history:
            controls.append(
                ft.Text(
                    "No rated games yet. Play against a bot!",
                    size=13,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                )
            )
            return controls

        win_rate = get_win_rate(elo_profile)
        if win_rate is not None:
            controls.append(
                ft.Text(
                    f"Win rate: {win_rate:.1f}%  |  Peak: {elo_profile.peak_rating}",
                    size=13,
                    weight=ft.FontWeight.W_500,
                )
            )
            controls.append(ft.Divider(height=1))

        # Show last 20 games (most recent first)
        recent = list(reversed(elo_profile.history[-20:]))
        for rec in recent:
            result = rec.get("result", 0.5)
            if result == 1.0:
                result_str = "Win"
                result_color = ft.Colors.GREEN
            elif result == 0.0:
                result_str = "Loss"
                result_color = ft.Colors.RED
            else:
                result_str = "Draw"
                result_color = ft.Colors.ORANGE

            opp = rec.get("opponent", "?")
            opp_name = get_bot_display_name(opp)
            opp_elo = rec.get("opponent_elo", "?")
            before = rec.get("rating_before", "?")
            after = rec.get("rating_after", "?")
            delta = (
                after - before
                if isinstance(after, int) and isinstance(before, int)
                else 0
            )
            delta_str = f"+{delta}" if delta >= 0 else str(delta)
            delta_color = ft.Colors.GREEN if delta >= 0 else ft.Colors.RED

            controls.append(
                ft.Row(
                    [
                        ft.Text(
                            result_str,
                            size=12,
                            color=result_color,
                            width=35,
                            weight=ft.FontWeight.W_500,
                        ),
                        ft.Text(f"vs {opp_name} (~{opp_elo})", size=12, expand=True),
                        ft.Text(
                            f"{before}→{after}",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            delta_str,
                            size=12,
                            color=delta_color,
                            weight=ft.FontWeight.W_500,
                            width=40,
                            text_align=ft.TextAlign.RIGHT,
                        ),
                    ],
                    spacing=6,
                )
            )
        return controls

    def show_elo_dialog(_):
        history_controls = _build_elo_history_controls()
        elo_dialog = ft.AlertDialog(
            title=ft.Row(
                [
                    ft.Text("Rating History", weight=ft.FontWeight.W_600),
                    ft.Container(expand=True),
                    ft.Text(
                        str(elo_profile.rating),
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.DEEP_PURPLE,
                    ),
                ],
            ),
            content=ft.Container(
                content=ft.Column(
                    history_controls,
                    scroll=ft.ScrollMode.AUTO,
                    tight=True,
                    spacing=4,
                ),
                width=420,
                height=360,
            ),
            actions=[
                ft.TextButton("Reset Rating", on_click=do_reset_elo),
                ft.TextButton("Close", on_click=lambda e: page.pop_dialog()),
            ],
            open=False,
        )
        page.show_dialog(elo_dialog)

    def show_hint(_):
        """Show hint moves for the current position."""
        nonlocal hint_moves
        if game_over or not is_human_turn():
            return

        # Get hint moves from the game
        hint_data = game.get_hint_moves(depth=3, top_n=3)
        if not hint_data:
            message.current.value = "No hints available (game over or no moves)."
            message.current.color = ft.Colors.ORANGE
            page.update()
            return

        # Convert hint moves to UI coordinates
        import chess

        hint_moves = []
        for move, score, san in hint_data:
            from_sq = move.from_square
            to_sq = move.to_square
            from_file = chess.square_file(from_sq)
            from_rank = chess.square_rank(from_sq)
            to_file = chess.square_file(to_sq)
            to_rank = chess.square_rank(to_sq)
            from_row, from_col = (7 - from_rank, from_file)
            to_row, to_col = (7 - to_rank, to_file)
            hint_moves.append(((from_row, from_col), (to_row, to_col), score, san))

        # Update message with hint info
        if hint_moves:
            best_move = hint_moves[0]
            best_san = best_move[3]
            if len(hint_moves) > 1:
                message.current.value = f"💡 Hint: Best move is {best_san} (showing top {len(hint_moves)} moves)"
            else:
                message.current.value = f"💡 Hint: Best move is {best_san}"
            message.current.color = ft.Colors.PURPLE
        else:
            message.current.value = "No hints available."
            message.current.color = ft.Colors.ORANGE

        refresh_board()
        page.update()

    # Evaluation bar component
    eval_bar = ft.Container(
        ref=eval_bar_container,
        content=ft.Stack(
            [
                ft.Container(width=200, height=20, bgcolor=ft.Colors.BLACK),
                ft.Container(width=100, height=20, bgcolor=ft.Colors.WHITE),
            ],
            width=200,
            height=20,
        ),
        width=200,
        height=20,
        border=ft.border.all(1, ft.Colors.OUTLINE),
    )

    history_panel = ft.Container(
        content=ft.Column(
            [
                ft.Text("Rating", size=16, weight=ft.FontWeight.W_600),
                ft.Row(
                    [
                        ft.Text(
                            ref=elo_rating_text,
                            value=str(elo_profile.rating),
                            size=22,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.DEEP_PURPLE,
                        ),
                        ft.Text(
                            ref=elo_label_text,
                            value=get_difficulty_label(elo_profile.rating),
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.END,
                ),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    ref=elo_record_text,
                                    value=f"{elo_profile.wins}W / {elo_profile.draws}D / {elo_profile.losses}L",
                                    size=11,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                                ft.Text(
                                    ref=elo_peak_text,
                                    value=f"Peak: {elo_profile.peak_rating}",
                                    size=11,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=8,
                        ),
                        ft.Row(
                            [
                                ft.Text(
                                    "Form:", size=11, color=ft.Colors.ON_SURFACE_VARIANT
                                ),
                                ft.Text(
                                    ref=elo_form_text,
                                    value=get_recent_form(elo_profile),
                                    size=11,
                                    weight=ft.FontWeight.W_500,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=4,
                        ),
                        ft.Row(
                            [
                                ft.Text(
                                    "Try:", size=11, color=ft.Colors.ON_SURFACE_VARIANT
                                ),
                                ft.Text(
                                    ref=elo_recommendation_text,
                                    value="",
                                    size=11,
                                    weight=ft.FontWeight.W_500,
                                    color=ft.Colors.DEEP_PURPLE,
                                ),
                            ],
                            spacing=4,
                        ),
                    ],
                    spacing=2,
                    tight=True,
                ),
                ft.Divider(height=1),
                ft.Text("Evaluation", size=16, weight=ft.FontWeight.W_600),
                ft.Column(
                    [
                        eval_bar,
                        ft.Text(
                            ref=eval_text,
                            value="+0.00",
                            size=14,
                            weight=ft.FontWeight.W_500,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    spacing=4,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(height=1),
                ft.Text("Opening", size=16, weight=ft.FontWeight.W_600),
                ft.Column(
                    [
                        ft.Text(
                            ref=opening_name_text,
                            value="No opening identified",
                            size=14,
                            weight=ft.FontWeight.NORMAL,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            ref=opening_desc_text,
                            value="",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            "Common moves:",
                            size=12,
                            weight=ft.FontWeight.W_500,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Column(
                            ref=common_moves_column,
                            controls=[],
                            spacing=2,
                            tight=True,
                        ),
                    ],
                    spacing=4,
                    tight=True,
                ),
                ft.Divider(height=1),
                ft.Text("Moves", size=16, weight=ft.FontWeight.W_600),
                ft.Column(
                    controls=[
                        ft.Text(
                            ref=history_text,
                            value="No moves yet.",
                            selectable=True,
                            size=14,
                        ),
                    ],
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
            ],
            expand=True,
            spacing=8,
            tight=True,
        ),
        width=220,
        padding=ft.padding.all(12),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border=ft.border.only(left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
    )

    app_bar = ft.AppBar(
        title=ft.Text("Chess", weight=ft.FontWeight.BOLD),
        center_title=True,
        bgcolor=ft.Colors.SURFACE,
        actions=[
            ft.IconButton(
                icon=ft.Icons.MENU_BOOK,
                tooltip="Puzzles & Scenarios",
                on_click=show_puzzles_dialog,
            ),
            ft.IconButton(
                icon=ft.Icons.LIGHTBULB_OUTLINE,
                tooltip="Show hint (best moves)",
                on_click=show_hint,
            ),
            ft.IconButton(
                icon=ft.Icons.LEADERBOARD,
                tooltip="Rating history",
                on_click=show_elo_dialog,
            ),
            ft.IconButton(
                icon=ft.Icons.SETTINGS,
                tooltip="Configuration",
                on_click=show_config_dialog,
            ),
            ft.IconButton(
                ref=undo_btn,
                icon=ft.Icons.UNDO,
                tooltip="Undo move",
                on_click=do_undo,
                disabled=not game.can_undo(),
            ),
            ft.IconButton(
                icon=ft.Icons.REPLAY,
                tooltip="New game",
                on_click=show_new_game_dialog,
            ),
        ],
    )

    # --- Restore saved game state on startup ---
    _saved = load_game_state()
    if _saved is not None:
        if game.load_from_moves(_saved.initial_fen, _saved.moves_uci):
            white_player = _saved.white_player
            black_player = _saved.black_player
            time_control_secs = _saved.time_control_secs
            white_remaining_secs = _saved.white_remaining_secs
            black_remaining_secs = _saved.black_remaining_secs
            clock_enabled = _saved.clock_enabled
            clock_started = _saved.clock_started
            move_start_time = time.monotonic()
            game_over = (
                game.is_checkmate() or game.is_stalemate() or game.is_only_kings_left()
            )

    update_status()
    page.add(
        ft.Column(
            [
                app_bar,
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Row(
                                controls=[grid],
                                alignment=ft.MainAxisAlignment.CENTER,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            expand=True,
                        ),
                        history_panel,
                    ],
                    expand=True,
                    spacing=0,
                ),
                status_bar,
            ],
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )

    def on_page_resize(e: ft.PageResizeEvent):
        refresh_board(e.width, e.height)

    page.on_resize = on_page_resize
    refresh_board()
    update_history()
    update_evaluation_bar()
    update_opening_explorer()
    update_clock_display()
    update_elo_display()
    page.run_task(run_clock)


if __name__ == "__main__":
    ft.app(target=main)
