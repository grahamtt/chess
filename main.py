"""
Chess game using Flet with python-chess engine and SVG pieces.
"""

import asyncio
import time

import flet as ft
from chess_logic import ChessGame
from pieces_svg import get_svg
from puzzles import PUZZLES
from bots import BotBot, ChessBot, MinimaxBot, SimpleBot

LIGHT_SQUARE = "#f0d9b5"
DARK_SQUARE = "#b58863"
HIGHLIGHT = "#7fc97f"
HIGHLIGHT_CAPTURE = "#f27777"
SELECTED = "#baca44"


def main(page: ft.Page):
    page.title = "Chess"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.window.min_width = 600
    page.window.min_height = 560

    game = ChessGame()
    selected = None  # (row, col) or None
    valid_moves = []  # list of (row, col)
    game_over = False
    message = ft.Ref[ft.Text]()
    history_text = ft.Ref[ft.Text]()
    white_clock_text = ft.Ref[ft.Text]()
    black_clock_text = ft.Ref[ft.Text]()

    # Game clock: each player has fixed time; runs down on their turn
    time_control_secs = 300  # 5 min default; set by dropdown for next game
    white_remaining_secs = float(time_control_secs)
    black_remaining_secs = float(time_control_secs)
    move_start_time = time.monotonic()
    clock_enabled = True  # False when playing puzzles (no time pressure)

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

    def format_clock(seconds: float) -> str:
        """Format remaining time as M:SS or 0:00 when out of time."""
        secs = max(0.0, seconds)
        m = int(secs // 60)
        s = int(secs % 60)
        return f"{m}:{s:02d}"

    def update_clock_display():
        """Refresh both players' clock display (remaining time, active = running). When clock disabled, show 'Clock off'."""
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
        """Call after a move is applied: deduct elapsed time from the player who moved; end game if they ran out. No-op when clock disabled."""
        if not clock_enabled:
            update_clock_display()
            return
        nonlocal move_start_time, white_remaining_secs, black_remaining_secs, game_over
        now = time.monotonic()
        elapsed = now - move_start_time
        move_start_time = now
        # The player who just moved had their clock running (it was their turn before the move)
        if game.turn == "black":
            white_remaining_secs -= elapsed
            if white_remaining_secs <= 0:
                game_over = True
                message.current.value = "White ran out of time. Black wins."
                message.current.color = ft.Colors.BLUE
        else:
            black_remaining_secs -= elapsed
            if black_remaining_secs <= 0:
                game_over = True
                message.current.value = "Black ran out of time. White wins."
                message.current.color = ft.Colors.BLUE
        update_clock_display()

    async def run_clock():
        """Periodically update clock display and end game if current player runs out of time. Does nothing when clock disabled."""
        nonlocal game_over
        while True:
            if game_over or not clock_enabled:
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
                else:
                    message.current.value = "Black ran out of time. White wins."
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
        if selected == (row, col):
            bg = SELECTED
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
            nonlocal selected, valid_moves, game_over
            if game_over:
                return
            if not is_human_turn():
                refresh_board()
                return
            if selected is not None and (row, col) in valid_moves:
                game.make_move(selected[0], selected[1], row, col)
                selected = None
                valid_moves = []
                deduct_move_time_and_check_game_over()
                update_status()
                update_undo_button()
                update_history()
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
        nonlocal selected, valid_moves, game_over
        bot = get_bot_for_turn()
        if not bot or game_over:
            return
        move = bot.choose_move(game.get_board())
        if move is None or not game.apply_move(move):
            return
        selected = None
        valid_moves = []
        deduct_move_time_and_check_game_over()
        update_status()
        update_undo_button()
        update_history()
        refresh_board()
        page.update()

    async def run_bot_vs_bot():
        """Run bot-vs-bot loop in background so UI stays responsive."""
        nonlocal selected, valid_moves, game_over, bot_vs_bot_running
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
                deduct_move_time_and_check_game_over()
                update_status()
                update_undo_button()
                update_history()
                refresh_board()
                page.update()
                if game_over:
                    break
                await asyncio.sleep(0.4)
        finally:
            bot_vs_bot_running = False

    def update_status():
        nonlocal game_over
        if game.is_checkmate():
            winner = "Black" if game.turn == "white" else "White"
            message.current.value = f"Checkmate! {winner} wins."
            message.current.color = ft.Colors.BLUE
            game_over = True
        elif game.is_stalemate():
            message.current.value = "Stalemate. Draw."
            message.current.color = ft.Colors.ORANGE
            game_over = True
        elif game.is_only_kings_left():
            message.current.value = "Draw. Only kings left."
            message.current.color = ft.Colors.ORANGE
            game_over = True
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
            game_over, \
            white_remaining_secs, \
            black_remaining_secs, \
            move_start_time, \
            clock_enabled
        page.pop_dialog()
        game.reset()
        selected = None
        valid_moves = []
        game_over = False
        clock_enabled = True
        white_remaining_secs = float(time_control_secs)
        black_remaining_secs = float(time_control_secs)
        move_start_time = time.monotonic()
        message.current.value = "White to move."
        message.current.color = ft.Colors.BLACK
        update_clock_display()
        refresh_board()
        update_undo_button()
        update_history()
        page.update()
        if is_bot_vs_bot() and get_bot_for_turn() and not game_over:
            page.run_task(run_bot_vs_bot)

    def do_undo(_):
        nonlocal selected, valid_moves, game_over, move_start_time
        if not game.undo():
            return
        selected = None
        valid_moves = []
        game_over = False
        move_start_time = time.monotonic()
        update_status()
        update_clock_display()
        refresh_board()
        update_undo_button()
        update_history()
        page.update()

    def update_history():
        if history_text.current is None:
            return
        history_text.current.value = game.get_move_history() or "No moves yet."
        try:
            history_text.current.update()
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
        nonlocal white_player, black_player, time_control_secs
        page.pop_dialog()
        if config_time_ref.current is not None:
            try:
                time_control_secs = int(config_time_ref.current.value or "300")
            except (ValueError, TypeError):
                time_control_secs = 300
        if config_white_ref.current is not None:
            white_player = config_white_ref.current.value or "human"
        if config_black_ref.current is not None:
            black_player = config_black_ref.current.value or "human"
        update_status()
        update_clock_display()
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
                    value=str(time_control_secs),
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
            config_time_ref.current.value = str(time_control_secs)
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
        nonlocal selected, valid_moves, game_over, clock_enabled
        selected = None
        valid_moves = []
        clock_enabled = puzzle_clock_enabled
        game_over = (
            game.is_checkmate() or game.is_stalemate() or game.is_only_kings_left()
        )
        update_status()
        update_clock_display()
        refresh_board()
        update_undo_button()
        update_history()
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

    puzzles_dialog = ft.AlertDialog(
        title=ft.Text("Puzzles & Scenarios"),
        content=ft.Container(
            content=ft.Column(
                puzzle_list_controls,
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

    history_panel = ft.Container(
        content=ft.Column(
            [
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
    update_clock_display()
    page.run_task(run_clock)


if __name__ == "__main__":
    ft.app(target=main)
