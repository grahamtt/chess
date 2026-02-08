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
from puzzles import (
    PUZZLE_DATABASE,
    PUZZLE_BY_ID,
    Puzzle,
    PuzzleCategory,
    PuzzleObjective,
)
from puzzle_progress import (
    PuzzleProgress,
    load_puzzle_progress,
    save_puzzle_progress,
)
from bots import (
    BotBot,
    ChessBot,
    DIFFICULTY_PRESETS,
    MinimaxBot,
    SimpleBot,
    StockfishBot,
    is_stockfish_available,
)
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
LAST_MOVE = "#a9d18e"  # Green for last-move highlighting (from & to squares)
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

    # Refs for side-panel sections (toggled visible/hidden during puzzles)
    elo_section_ref = ft.Ref[ft.Column]()
    eval_section_ref = ft.Ref[ft.Column]()
    opening_section_ref = ft.Ref[ft.Column]()

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

    # Register Stockfish bots (only if the binary is found on this system)
    _stockfish_available = is_stockfish_available()
    if _stockfish_available:
        for _sf_key, (_sf_skill, _sf_time, _sf_elo) in DIFFICULTY_PRESETS.items():
            player_bots[_sf_key] = StockfishBot(
                skill_level=_sf_skill,
                think_time=_sf_time,
            )

    # ELO rating system
    elo_profile: EloProfile = load_elo_profile()
    elo_rating_text = ft.Ref[ft.Text]()
    elo_label_text = ft.Ref[ft.Text]()
    elo_form_text = ft.Ref[ft.Text]()
    elo_record_text = ft.Ref[ft.Text]()
    elo_peak_text = ft.Ref[ft.Text]()
    elo_recommendation_text = ft.Ref[ft.Text]()
    elo_updated_this_game = False  # Guard: only update ELO once per game

    # --- Puzzle solving state ---
    active_puzzle: Puzzle | None = None  # Currently active puzzle (None = normal game)
    puzzle_move_index = 0  # Which player move we're on in the solution
    puzzle_start_time = 0.0  # When the puzzle was loaded
    puzzle_moves_made = 0  # Total moves made by the player in this attempt
    puzzle_progress: PuzzleProgress = load_puzzle_progress()

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

        Puzzles never affect the player's ELO rating.

        Args:
            result_for_white: 1.0 if white won, 0.0 if black won, 0.5 if draw,
                            None if not applicable (bot vs bot or human vs human).
        """
        nonlocal elo_updated_this_game
        if elo_updated_this_game or result_for_white is None:
            return
        # Puzzles never affect ELO
        if active_puzzle is not None:
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

    def get_board_flipped() -> bool:
        """Determine if the board should be shown from black's perspective.

        - Human vs Computer: permanently orient for the human player.
        - Human vs Human: orient for the player whose turn it is.
        - Bot vs Bot: always show from white's perspective.
        """
        white_is_human = white_player == "human"
        black_is_human = black_player == "human"

        if white_is_human and not black_is_human:
            # Human plays white vs computer: never flip
            return False
        elif black_is_human and not white_is_human:
            # Human plays black vs computer: always flip
            return True
        elif white_is_human and black_is_human:
            # Human vs Human: flip when it's black's turn
            return game.turn == "black"
        else:
            # Bot vs Bot: never flip
            return False

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

        # Check if this square is part of the most recent move
        last_move = game.get_last_move()
        is_last_move_square = last_move is not None and (
            (row, col) == last_move[0] or (row, col) == last_move[1]
        )

        if selected == (row, col):
            bg = SELECTED
        elif is_hint_from:
            bg = HINT_FROM
        elif is_hint_to:
            bg = HINT_TO
        elif (row, col) in valid_moves:
            bg = HIGHLIGHT_CAPTURE if cell is not None else HIGHLIGHT
        elif is_last_move_square:
            bg = LAST_MOVE

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
            nonlocal active_puzzle, puzzle_move_index, puzzle_moves_made
            if game_over:
                return
            if not is_human_turn():
                refresh_board()
                return
            if selected is not None and (row, col) in valid_moves:
                # Determine the UCI move the player is making
                import chess as _chess

                from_sq = _chess.square(selected[1], 7 - selected[0])
                to_sq = _chess.square(col, 7 - row)
                # Check for promotion
                board = game.get_board()
                piece = board.piece_at(from_sq)
                is_promo = (
                    piece is not None
                    and piece.piece_type == _chess.PAWN
                    and (
                        _chess.square_rank(to_sq) == 7 or _chess.square_rank(to_sq) == 0
                    )
                )
                uci_move = f"{_chess.square_name(from_sq)}{_chess.square_name(to_sq)}"
                if is_promo:
                    uci_move += "q"  # Default queen promotion for puzzle checks

                # --- Puzzle validation ---
                if (
                    active_puzzle
                    and active_puzzle.objective != PuzzleObjective.FREE_PLAY
                ):
                    puzzle_moves_made += 1
                    if not active_puzzle.is_player_move_correct(
                        puzzle_move_index, uci_move
                    ):
                        # Wrong move — puzzle failed
                        handle_puzzle_failure()
                        selected = None
                        valid_moves = []
                        hint_moves = []
                        refresh_board()
                        page.update()
                        return

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

                # --- Puzzle completion check ---
                if (
                    active_puzzle
                    and active_puzzle.objective != PuzzleObjective.FREE_PLAY
                ):
                    if active_puzzle.is_complete_after_player_move(puzzle_move_index):
                        handle_puzzle_completion()
                        page.update()
                        return
                    # Play opponent's automatic response
                    opponent_uci = active_puzzle.get_opponent_response(
                        puzzle_move_index
                    )
                    puzzle_move_index += 1
                    if opponent_uci:
                        page.run_task(play_puzzle_opponent_move, opponent_uci)
                        return

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
        flipped = get_board_flipped()
        grid.controls.clear()
        for visual_r in range(8):
            row_controls = []
            for visual_c in range(8):
                # Map visual position to logical position
                logical_r = 7 - visual_r if flipped else visual_r
                logical_c = 7 - visual_c if flipped else visual_c
                row_controls.append(build_square(logical_r, logical_c))
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
            # For CHECKMATE_IN_N puzzles, checkmate means puzzle completion
            if (
                active_puzzle
                and active_puzzle.objective == PuzzleObjective.CHECKMATE_IN_N
                and not game_over
            ):
                handle_puzzle_completion()
                return
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
            # If we're in a puzzle and stalemate occurs, that's a failure
            if active_puzzle and active_puzzle.objective != PuzzleObjective.FREE_PLAY:
                handle_puzzle_failure()
                return
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

    # --- Puzzle solving helpers ---
    def handle_puzzle_completion():
        """Called when the player completes a puzzle successfully."""
        nonlocal game_over, active_puzzle, puzzle_progress
        game_over = True
        if active_puzzle:
            elapsed = time.monotonic() - puzzle_start_time
            puzzle_progress.record_attempt(
                puzzle_id=active_puzzle.id,
                puzzle_rating=active_puzzle.difficulty_rating,
                solved=True,
                time_secs=elapsed,
                moves_made=puzzle_moves_made,
            )
            save_puzzle_progress(puzzle_progress)
            rating_change = puzzle_progress.get_rating_change_display()
            rating_str = f" (Rating: {puzzle_progress.player_rating} {rating_change})"
            msg = active_puzzle.completion_message or "Puzzle solved!"
            if puzzle_progress.current_streak > 1:
                msg += f" Streak: {puzzle_progress.current_streak}!"
            message.current.value = f"✓ {msg}{rating_str}"
            message.current.color = ft.Colors.GREEN
        else:
            message.current.value = "Puzzle solved!"
            message.current.color = ft.Colors.GREEN

    def handle_puzzle_failure():
        """Called when the player makes a wrong move in a puzzle."""
        nonlocal game_over, active_puzzle, puzzle_progress
        game_over = True
        if active_puzzle:
            elapsed = time.monotonic() - puzzle_start_time
            puzzle_progress.record_attempt(
                puzzle_id=active_puzzle.id,
                puzzle_rating=active_puzzle.difficulty_rating,
                solved=False,
                time_secs=elapsed,
                moves_made=puzzle_moves_made,
            )
            save_puzzle_progress(puzzle_progress)
            rating_change = puzzle_progress.get_rating_change_display()
            rating_str = f" (Rating: {puzzle_progress.player_rating} {rating_change})"
            msg = active_puzzle.failure_message or "Not the best move."
            # Show the expected move as a hint
            expected_moves = active_puzzle.player_moves
            if puzzle_move_index < len(expected_moves):
                msg += f" Expected: {expected_moves[puzzle_move_index]}"
            message.current.value = f"✗ {msg}{rating_str}"
            message.current.color = ft.Colors.RED
        else:
            message.current.value = "Wrong move! Puzzle failed."
            message.current.color = ft.Colors.RED

    async def play_puzzle_opponent_move(opponent_uci: str):
        """Play the opponent's automatic response in a puzzle after a short delay."""
        nonlocal selected, valid_moves, hint_moves
        import chess as _chess

        await asyncio.sleep(0.4)  # Brief pause so player sees their move
        try:
            move = _chess.Move.from_uci(opponent_uci)
            if game.apply_move(move):
                selected = None
                valid_moves = []
                hint_moves = []
                update_status()
                update_undo_button()
                update_history()
                update_evaluation_bar()
                update_opening_explorer()
                refresh_board()
                page.update()
        except (ValueError, TypeError):
            pass  # Invalid move string, skip

    grid = ft.Column(spacing=0)
    _init_flipped = get_board_flipped()
    for _init_r in range(8):
        _init_row = []
        for _init_c in range(8):
            _lr = 7 - _init_r if _init_flipped else _init_r
            _lc = 7 - _init_c if _init_flipped else _init_c
            _init_row.append(build_square(_lr, _lc))
        grid.controls.append(ft.Row(controls=_init_row, spacing=0))

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
        """Reset the game (called after confirmation).

        When a puzzle is active the current puzzle is restarted instead of
        returning to a blank game.
        """
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
            elo_updated_this_game, \
            active_puzzle, \
            puzzle_move_index, \
            puzzle_start_time, \
            puzzle_moves_made
        page.pop_dialog()

        # If a puzzle is active, restart it instead of resetting to a new game
        current_puzzle = active_puzzle
        if current_puzzle is not None:
            if not game.set_fen(current_puzzle.fen):
                # Fallback: if the FEN is invalid somehow, do a normal reset
                current_puzzle = None

        if current_puzzle is not None:
            # Restart the active puzzle
            selected = None
            valid_moves = []
            hint_moves = []
            elo_updated_this_game = False
            active_puzzle = current_puzzle
            puzzle_move_index = 0
            puzzle_start_time = time.monotonic()
            puzzle_moves_made = 0
            clock_enabled = current_puzzle.clock_enabled
            clock_started = current_puzzle.clock_enabled and game.can_undo()
            game_over = (
                game.is_checkmate() or game.is_stalemate() or game.is_only_kings_left()
            )
            # Show puzzle info in status
            if current_puzzle.objective != PuzzleObjective.FREE_PLAY:
                diff_label = current_puzzle.difficulty_label.value
                msg = f"Puzzle: {current_puzzle.name} ({diff_label} — {current_puzzle.difficulty_rating})"
                if current_puzzle.num_player_moves > 1:
                    msg += f" — Find {current_puzzle.num_player_moves} moves"
                message.current.value = msg
                message.current.color = ft.Colors.PURPLE
            else:
                update_status()
            update_clock_display()
            save_current_state()
            refresh_board()
            update_undo_button()
            update_history()
            update_evaluation_bar()
            update_opening_explorer()
            update_side_panel_visibility()
            page.update()
            return

        # Normal new game reset (no puzzle active)
        game.reset()
        selected = None
        valid_moves = []
        hint_moves = []
        game_over = False
        elo_updated_this_game = False
        active_puzzle = None
        puzzle_move_index = 0
        puzzle_start_time = time.monotonic()
        puzzle_moves_made = 0
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
        update_side_panel_visibility()
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
            clock_started, \
            active_puzzle, \
            puzzle_move_index, \
            puzzle_moves_made
        if not game.undo():
            return
        selected = None
        valid_moves = []
        hint_moves = []  # Clear hints when undoing
        game_over = False
        # Clear puzzle state on undo (puzzle becomes invalid after undo)
        if active_puzzle and active_puzzle.objective != PuzzleObjective.FREE_PLAY:
            active_puzzle = None
            puzzle_move_index = 0
            puzzle_moves_made = 0
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
        update_side_panel_visibility()
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

    def update_side_panel_visibility():
        """Show or hide side-panel sections based on whether a puzzle is active.

        During puzzles, ELO rating, evaluation bar, and opening explorer are
        hidden because they are irrelevant to the puzzle-solving experience.
        """
        in_puzzle = active_puzzle is not None
        for ref in (elo_section_ref, eval_section_ref, opening_section_ref):
            if ref.current is not None:
                ref.current.visible = not in_puzzle
                try:
                    ref.current.update()
                except RuntimeError:
                    pass

    player_options = [
        ft.DropdownOption(key="human", text="Human"),
        ft.DropdownOption(key="random", text="Random"),
        ft.DropdownOption(key="botbot", text="BotBot"),
        ft.DropdownOption(key="minimax_1", text="Minimax 1"),
        ft.DropdownOption(key="minimax_2", text="Minimax 2"),
        ft.DropdownOption(key="minimax_3", text="Minimax 3"),
        ft.DropdownOption(key="minimax_4", text="Minimax 4"),
    ]
    if _stockfish_available:
        player_options.extend(
            [
                ft.DropdownOption(key="stockfish_1", text="Stockfish 1 (~1200)"),
                ft.DropdownOption(key="stockfish_2", text="Stockfish 2 (~1400)"),
                ft.DropdownOption(key="stockfish_3", text="Stockfish 3 (~1600)"),
                ft.DropdownOption(key="stockfish_4", text="Stockfish 4 (~1800)"),
                ft.DropdownOption(key="stockfish_5", text="Stockfish 5 (~2000)"),
                ft.DropdownOption(key="stockfish_6", text="Stockfish 6 (~2200)"),
                ft.DropdownOption(key="stockfish_7", text="Stockfish 7 (~2500)"),
                ft.DropdownOption(key="stockfish_8", text="Stockfish 8 (Max)"),
            ]
        )
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
        refresh_board()
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

    def show_new_game_dialog(_):
        if active_puzzle is not None:
            title = "Restart puzzle"
            content = (
                f'Restart "{active_puzzle.name}"? Your current progress will be lost.'
            )
            confirm_label = "Restart"
        else:
            title = "New game"
            content = "Start a new game? The current game will be lost."
            confirm_label = "New game"
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(content),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=lambda e: page.pop_dialog(),
                ),
                ft.TextButton(confirm_label, on_click=do_new_game),
            ],
            open=False,
        )
        page.show_dialog(dialog)

    def load_puzzle_by_id(puzzle_id: str):
        """Load a puzzle by its unique ID."""
        page.pop_dialog()
        puzzle = PUZZLE_BY_ID.get(puzzle_id)
        if puzzle is None:
            return
        if not game.set_fen(puzzle.fen):
            return
        nonlocal \
            selected, \
            valid_moves, \
            hint_moves, \
            game_over, \
            clock_enabled, \
            clock_started, \
            elo_updated_this_game, \
            active_puzzle, \
            puzzle_move_index, \
            puzzle_start_time, \
            puzzle_moves_made
        selected = None
        valid_moves = []
        hint_moves = []
        elo_updated_this_game = False
        active_puzzle = puzzle
        puzzle_move_index = 0
        puzzle_start_time = time.monotonic()
        puzzle_moves_made = 0
        clock_enabled = puzzle.clock_enabled
        clock_started = puzzle.clock_enabled and game.can_undo()
        game_over = (
            game.is_checkmate() or game.is_stalemate() or game.is_only_kings_left()
        )
        # Show puzzle info in status
        if puzzle.objective != PuzzleObjective.FREE_PLAY:
            diff_label = puzzle.difficulty_label.value
            msg = f"Puzzle: {puzzle.name} ({diff_label} — {puzzle.difficulty_rating})"
            if puzzle.num_player_moves > 1:
                msg += f" — Find {puzzle.num_player_moves} moves"
            message.current.value = msg
            message.current.color = ft.Colors.PURPLE
        else:
            update_status()
        update_clock_display()
        save_current_state()
        refresh_board()
        update_undo_button()
        update_history()
        update_evaluation_bar()
        update_opening_explorer()
        update_side_panel_visibility()
        page.update()

    def _difficulty_color(rating: int) -> str:
        """Return a color string for puzzle difficulty."""
        if rating == 0:
            return ft.Colors.ON_SURFACE_VARIANT
        if rating < 1000:
            return ft.Colors.GREEN
        if rating < 1400:
            return ft.Colors.BLUE
        if rating < 1800:
            return ft.Colors.ORANGE
        return ft.Colors.RED

    def _category_icon(cat: PuzzleCategory) -> str:
        """Return an icon name for a category."""
        icons = {
            PuzzleCategory.CHECKMATE: ft.Icons.FLAG,
            PuzzleCategory.TACTICS: ft.Icons.FLASH_ON,
            PuzzleCategory.ENDGAME: ft.Icons.HOURGLASS_BOTTOM,
            PuzzleCategory.OPENING: ft.Icons.MENU_BOOK,
            PuzzleCategory.DEFENSE: ft.Icons.SHIELD,
            PuzzleCategory.FREE_PLAY: ft.Icons.SPORTS_ESPORTS,
        }
        return icons.get(cat, ft.Icons.EXTENSION)

    def make_puzzle_tile(puzzle: Puzzle):
        """Build a list tile for a puzzle in the dialog."""
        unlocked = puzzle_progress.is_puzzle_unlocked(puzzle.difficulty_rating)
        stats = puzzle_progress.get_stats_for_puzzle(puzzle.id)

        # Difficulty badge
        if puzzle.difficulty_rating > 0:
            diff_label = puzzle.difficulty_label.value
            rating_text = f"{diff_label} ({puzzle.difficulty_rating})"
        else:
            rating_text = "Free Play"

        # Solve indicator
        if stats.solved:
            solve_text = " ✓ Solved"
            if stats.best_time_secs is not None:
                solve_text += f" ({stats.best_time_secs:.1f}s)"
        elif stats.attempts > 0:
            solve_text = f" ✗ Unsolved ({stats.attempts} attempt{'s' if stats.attempts != 1 else ''})"
        else:
            solve_text = ""

        subtitle = f"{rating_text}{solve_text}"
        if not unlocked:
            subtitle = (
                f"🔒 Locked — need rating {puzzle.difficulty_rating - UNLOCK_MARGIN}+"
            )

        return ft.ListTile(
            leading=ft.Icon(
                _category_icon(puzzle.category),
                color=_difficulty_color(puzzle.difficulty_rating)
                if unlocked
                else ft.Colors.ON_SURFACE_VARIANT,
                size=20,
            ),
            title=ft.Text(
                puzzle.name,
                size=14,
                weight=ft.FontWeight.W_500,
                color=ft.Colors.ON_SURFACE
                if unlocked
                else ft.Colors.ON_SURFACE_VARIANT,
            ),
            subtitle=ft.Text(
                subtitle,
                size=11,
                color=_difficulty_color(puzzle.difficulty_rating)
                if unlocked
                else ft.Colors.ON_SURFACE_VARIANT,
            ),
            on_click=(lambda e, pid=puzzle.id: load_puzzle_by_id(pid))
            if unlocked
            else None,
            disabled=not unlocked,
        )

    # Import UNLOCK_MARGIN for display
    from puzzle_progress import UNLOCK_MARGIN

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
            elo_updated_this_game, \
            active_puzzle, \
            puzzle_move_index, \
            puzzle_start_time, \
            puzzle_moves_made
        selected = None
        valid_moves = []
        hint_moves = []
        elo_updated_this_game = False
        active_puzzle = None  # Lichess puzzles use their own flow
        puzzle_move_index = 0
        puzzle_start_time = 0.0
        puzzle_moves_made = 0
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
        update_side_panel_visibility()
        page.update()

    def _show_daily_puzzle_dialog(puzzle: LichessDailyPuzzle):
        """Show a dialog with daily puzzle details and a Play button."""
        # Format metadata
        themes_str = format_themes(puzzle.themes) if puzzle.themes else "—"
        try:
            solution_san = get_solution_san(puzzle)
        except Exception:
            # Fallback: show raw UCI moves if SAN conversion fails
            solution_san = list(puzzle.solution_uci)
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
            page.pop_dialog()  # Close the Lichess puzzle detail dialog
            page.pop_dialog()  # Close the main Puzzles & Scenarios dialog
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

        try:
            puzzle = fetch_daily_puzzle()
        except Exception:
            puzzle = None

        if puzzle is None:
            if message.current is not None:
                message.current.value = (
                    "Could not fetch the daily puzzle. Check your internet connection."
                )
                message.current.color = ft.Colors.RED
                page.update()
            return

        daily_puzzle_cache["latest"] = puzzle
        try:
            _show_daily_puzzle_dialog(puzzle)
        except Exception:
            # Fallback: skip the dialog and load the puzzle directly
            _load_daily_puzzle_fen(puzzle)

    # ------------------------------------------------------------------
    # Puzzles dialog (local + daily puzzle)
    # ------------------------------------------------------------------

    def _get_puzzles_for_category(category_key: str) -> list[Puzzle]:
        """Return puzzles for a category key, sorted by difficulty."""
        if category_key == "all":
            puzzles = list(PUZZLE_DATABASE)
        else:
            cat = PuzzleCategory(category_key)
            puzzles = [p for p in PUZZLE_DATABASE if p.category == cat]
        return sorted(
            puzzles, key=lambda p: (p.difficulty_rating == 0, p.difficulty_rating)
        )

    def build_puzzle_dialog_content():
        """Build the puzzle dialog content with category filter, progress, and daily puzzle."""
        # Player stats header
        rating = puzzle_progress.player_rating
        streak = puzzle_progress.current_streak
        best = puzzle_progress.best_streak
        solved = puzzle_progress.total_solved
        attempted = puzzle_progress.total_attempted
        rate = f"{puzzle_progress.solve_rate:.0%}" if attempted > 0 else "—"

        stats_row = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                "Your Rating: ", size=14, weight=ft.FontWeight.W_500
                            ),
                            ft.Text(
                                str(rating),
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=_difficulty_color(rating),
                            ),
                        ],
                        spacing=4,
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                f"Solved: {solved}/{attempted} ({rate})",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Text(
                                f"  Streak: {streak} (Best: {best})",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=4,
                    ),
                ],
                spacing=2,
                tight=True,
            ),
            padding=ft.padding.only(bottom=8),
        )

        # Lichess Daily Puzzle button at the top
        daily_puzzle_tile = ft.Container(
            content=ft.ListTile(
                leading=ft.Icon(ft.Icons.PUBLIC, color=ft.Colors.DEEP_PURPLE),
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
        )

        # Puzzle list (refreshed when category changes)
        puzzle_list_column = ft.Column(scroll=ft.ScrollMode.AUTO, tight=True, spacing=0)

        def refresh_puzzle_list(category_key: str):
            puzzles = _get_puzzles_for_category(category_key)
            puzzle_list_column.controls.clear()
            for p in puzzles:
                puzzle_list_column.controls.append(make_puzzle_tile(p))
            try:
                puzzle_list_column.update()
            except RuntimeError:
                pass

        # Start with "All"
        refresh_puzzle_list("all")

        # Category dropdown
        category_options = [
            ft.DropdownOption(key="all", text="All"),
            ft.DropdownOption(key=PuzzleCategory.CHECKMATE.value, text="Checkmate"),
            ft.DropdownOption(key=PuzzleCategory.TACTICS.value, text="Tactics"),
            ft.DropdownOption(key=PuzzleCategory.ENDGAME.value, text="Endgame"),
            ft.DropdownOption(key=PuzzleCategory.DEFENSE.value, text="Defense"),
            ft.DropdownOption(key=PuzzleCategory.OPENING.value, text="Opening"),
            ft.DropdownOption(key=PuzzleCategory.FREE_PLAY.value, text="Free Play"),
        ]

        def on_category_change(e):
            refresh_puzzle_list(e.control.value or "all")

        category_dropdown = ft.Dropdown(
            value="all",
            options=category_options,
            width=200,
            on_select=on_category_change,
            dense=True,
        )

        filter_row = ft.Row(
            [ft.Text("Category:", size=13), category_dropdown],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.Column(
            [
                stats_row,
                daily_puzzle_tile,
                ft.Divider(height=1),
                filter_row,
                ft.Container(content=puzzle_list_column, height=300, expand=True),
            ],
            width=480,
            height=480,
            tight=True,
        )

    def show_puzzles_dialog(_):
        """Show the puzzle selection dialog with categories and progress."""
        # Rebuild content each time to reflect latest progress
        dialog = ft.AlertDialog(
            title=ft.Text("Puzzles & Scenarios"),
            content=build_puzzle_dialog_content(),
            actions=[
                ft.TextButton("Close", on_click=lambda e: page.pop_dialog()),
            ],
            open=False,
        )
        page.show_dialog(dialog)

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
                # --- ELO Rating section (hidden during puzzles) ---
                ft.Column(
                    ref=elo_section_ref,
                    controls=[
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
                                            "Form:",
                                            size=11,
                                            color=ft.Colors.ON_SURFACE_VARIANT,
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
                                            "Try:",
                                            size=11,
                                            color=ft.Colors.ON_SURFACE_VARIANT,
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
                    ],
                    spacing=8,
                    tight=True,
                ),
                # --- Evaluation section (hidden during puzzles) ---
                ft.Column(
                    ref=eval_section_ref,
                    controls=[
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
                    ],
                    spacing=8,
                    tight=True,
                ),
                # --- Opening section (hidden during puzzles) ---
                ft.Column(
                    ref=opening_section_ref,
                    controls=[
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
                    ],
                    spacing=8,
                    tight=True,
                ),
                # --- Moves section (always visible) ---
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
