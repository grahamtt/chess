"""
Chess game using Flet with python-chess engine and SVG pieces.
"""

import flet as ft
from chess_logic import ChessGame
from pieces_svg import get_svg

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

    def get_square_size(override_width: float | None = None, override_height: float | None = None) -> int:
        w = override_width if override_width is not None else (getattr(page, "width", None) or 800)
        h = override_height if override_height is not None else (getattr(page, "height", None) or 600)
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
            if selected is not None and (row, col) in valid_moves:
                game.make_move(selected[0], selected[1], row, col)
                selected = None
                valid_moves = []
                update_status()
                update_undo_button()
                update_history()
                refresh_board()
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

    def refresh_board(override_width: float | None = None, override_height: float | None = None):
        nonlocal square_size
        square_size = get_square_size(override_width, override_height)
        grid.controls.clear()
        for r in range(8):
            row_controls = [build_square(r, c) for c in range(8)]
            grid.controls.append(ft.Row(controls=row_controls, spacing=0))
        page.update()

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
        content=ft.Text(
            ref=message,
            value="White to move.",
            size=16,
            weight=ft.FontWeight.W_500,
        ),
        padding=ft.padding.symmetric(12, 16),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
    )

    def do_new_game(_):
        """Reset the game (called after confirmation)."""
        nonlocal selected, valid_moves, game_over
        page.pop_dialog()
        game.reset()
        selected = None
        valid_moves = []
        game_over = False
        message.current.value = "White to move."
        message.current.color = ft.Colors.BLACK
        refresh_board()
        update_undo_button()
        update_history()
        page.update()

    def do_undo(_):
        nonlocal selected, valid_moves, game_over
        if game_over or not game.undo():
            return
        selected = None
        valid_moves = []
        game_over = False
        update_status()
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
        undo_btn.current.disabled = game_over or not game.can_undo()
        if undo_btn.current.page is not None:
            undo_btn.current.update()
            page.update(undo_btn.current)

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

    history_panel = ft.Container(
        content=ft.Column(
            [
                ft.Text("Moves", size=16, weight=ft.FontWeight.W_600),
                ft.Column(
                    controls=[
                        ft.Text(ref=history_text, value="No moves yet.", selectable=True, size=14),
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
                ref=undo_btn,
                icon=ft.Icons.UNDO,
                tooltip="Undo move",
                on_click=do_undo,
                disabled=game_over or not game.can_undo(),
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


if __name__ == "__main__":
    ft.app(target=main)
