"""
4 в ряд — умный бот.
Управление: тап по столбцу = ваш ход.
Кнопка «Почему?» показывает оценку каждой колонки — так видно, почему бот выбрал свою.
"""
import pygame
import sys
import time

# ============================================================
#  КОНСТАНТЫ
# ============================================================
ROWS, COLS = 6, 7
EMPTY, PLAYER, BOT = 0, 1, 2
COLUMN_ORDER = (3, 2, 4, 1, 5, 0, 6)   # центр-первыми — сильнее отсечение
INF = 10 ** 9


# ============================================================
#  ЛОГИКА
# ============================================================
def _make_windows():
    ws = []
    for r in range(ROWS):
        for c in range(COLS - 3):
            ws.append(((r, c), (r, c+1), (r, c+2), (r, c+3)))
    for c in range(COLS):
        for r in range(ROWS - 3):
            ws.append(((r, c), (r+1, c), (r+2, c), (r+3, c)))
    for r in range(ROWS - 3):
        for c in range(COLS - 3):
            ws.append(((r, c), (r+1, c+1), (r+2, c+2), (r+3, c+3)))
            ws.append(((r+3, c), (r+2, c+1), (r+1, c+2), (r, c+3)))
    return ws

WINDOWS = _make_windows()
THREAT_W = (0, 1, 12, 70)


class Board:
    __slots__ = ('grid', 'heights', 'count')

    def __init__(self):
        self.grid = [[EMPTY] * COLS for _ in range(ROWS)]
        self.heights = [ROWS - 1] * COLS
        self.count = 0

    def copy(self):
        nb = Board()
        nb.grid = [row[:] for row in self.grid]
        nb.heights = self.heights[:]
        nb.count = self.count
        return nb

    def drop(self, c, piece):
        r = self.heights[c]
        self.grid[r][c] = piece
        self.heights[c] -= 1
        self.count += 1
        return r

    def undo(self, c):
        r = self.heights[c] + 1
        self.grid[r][c] = EMPTY
        self.heights[c] = r
        self.count -= 1

    def is_full(self):
        return self.count >= ROWS * COLS

    def can_drop(self, c):
        return self.heights[c] >= 0


def check_win(grid, r, c, p):
    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
        n = 1
        for s in (1, -1):
            rr, cc = r + dr * s, c + dc * s
            while 0 <= rr < ROWS and 0 <= cc < COLS and grid[rr][cc] == p:
                n += 1
                rr += dr * s
                cc += dc * s
        if n >= 4:
            return True
    return False


def win_cells(grid, r, c, p):
    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
        cells = [(r, c)]
        for s in (1, -1):
            rr, cc = r + dr * s, c + dc * s
            while 0 <= rr < ROWS and 0 <= cc < COLS and grid[rr][cc] == p:
                cells.append((rr, cc))
                rr += dr * s
                cc += dc * s
        if len(cells) >= 4:
            return cells
    return []


def evaluate_for(b, piece):
    g = b.grid
    sc = 0
    for window in WINDOWS:
        mine = theirs = 0
        for (r, c) in window:
            v = g[r][c]
            if v == piece:
                mine += 1
            elif v != EMPTY:
                theirs += 1
        if mine and theirs:
            continue
        if mine:
            sc += THREAT_W[mine]
    for r in range(ROWS):
        v = g[r][3]
        if v == piece:
            sc += 4
        elif v != EMPTY:
            sc -= 4
    return sc


def evaluate(b, p):
    return evaluate_for(b, p) - evaluate_for(b, 3 - p)


class _Timeout(Exception):
    pass


def find_best_move(real_board, piece, time_limit=1.4, max_depth=9):
    # !!! ГЛАВНОЕ ИСПРАВЛЕНИЕ !!!
    # Весь поиск идёт на КОПИИ доски. Реальная доска не меняется ни при каких
    # обстоятельствах — даже при таймауте. Раньше таймаут оставлял «висящие»
    # фишки на игровом поле → игра выглядела как «сама с собой».
    b = real_board.copy()
    start = time.time()

    def search(depth, alpha, beta, p, lr, lc, lp):
        if time.time() - start > time_limit:
            raise _Timeout()
        if lp != 0 and check_win(b.grid, lr, lc, lp):
            return -100000 + (30 - depth) * 50
        if depth == 0 or b.is_full():
            return evaluate(b, p)
        best = -INF
        for c in COLUMN_ORDER:
            if not b.can_drop(c):
                continue
            r = b.drop(c, p)
            try:
                val = -search(depth - 1, -beta, -alpha, 3 - p, r, c, p)
            finally:
                b.undo(c)
            if val > best:
                best = val
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break
        return best

    # 1) Немедленная победа есть?
    for c in COLUMN_ORDER:
        if not b.can_drop(c):
            continue
        r = b.drop(c, piece)
        w = check_win(b.grid, r, c, piece)
        b.undo(c)
        if w:
            return c, {c: 100000}, 1, "win"

    # 2) Итеративное углубление
    best_col, scores, depth_done = None, {}, 0
    try:
        for depth in range(2, max_depth + 1):
            cur = {}
            for c in COLUMN_ORDER:
                if not b.can_drop(c):
                    continue
                r = b.drop(c, piece)
                try:
                    val = -search(depth - 1, -INF, INF, 3 - piece, r, c, piece)
                finally:
                    b.undo(c)
                cur[c] = val
            scores = cur
            depth_done = depth
            best_col = max(cur, key=lambda k: cur[k])
    except _Timeout:
        pass

    if best_col is None:
        for c in COLUMN_ORDER:
            if b.can_drop(c):
                best_col = c
                break
        scores = {c: 0 for c in range(COLS) if b.can_drop(c)}

    return best_col, scores, depth_done, None


# ============================================================
#  ИНТЕРФЕЙС (Pygame)
# ============================================================
pygame.init()
pygame.display.set_caption("4 в ряд — умный бот")
screen = pygame.display.set_mode((480, 820), pygame.RESIZABLE)

BG           = (17, 20, 28)
BG2          = (24, 28, 40)
BOARD_COLOR  = (48, 92, 200)
BOARD_DARK   = (30, 60, 140)
HOLE         = (15, 18, 25)
PLAYER_COLOR = (235, 75, 90)
BOT_COLOR    = (250, 205, 60)
TEXT         = (235, 235, 245)
SUBTEXT      = (150, 155, 170)
ACCENT       = (90, 200, 255)
GOOD         = (100, 220, 130)
BAD          = (240, 100, 110)
WHITE        = (255, 255, 255)

_font_cache = {}
def font(size, bold=False):
    key = (int(size), bold)
    if key not in _font_cache:
        try:
            _font_cache[key] = pygame.font.SysFont("arial", int(size), bold=bold)
        except Exception:
            _font_cache[key] = pygame.font.Font(None, int(size))
    return _font_cache[key]


# ---------- состояние игры ----------
board = Board()
turn = PLAYER
winner = None            # None / PLAYER / BOT / 0 (ничья)
win_cells_list = []
last_move = None
history = []

bot_state = 'idle'       # idle / waiting / thinking
bot_wait_start = 0.0
bot_scores = None
bot_chosen = None
bot_reason = ""
bot_depth = 0
show_scores = True
hover_col = None
message = "Ваш ход"

_last_tap_ts = [0.0]     # дебаунс тапов


def new_game():
    global board, turn, winner, win_cells_list, last_move, history
    global bot_state, bot_scores, bot_chosen, bot_reason, bot_depth
    global message, hover_col
    board = Board()
    turn = PLAYER
    winner = None
    win_cells_list = []
    last_move = None
    history = []
    bot_state = 'idle'
    bot_scores = None
    bot_chosen = None
    bot_reason = ""
    bot_depth = 0
    hover_col = None
    message = "Ваш ход"


# ---------- раскладка ----------
def layout(w, h):
    top_h = max(54, int(h * 0.085))
    bottom_h = max(90, int(h * 0.16))
    area = h - top_h - bottom_h
    cell = min((w * 0.92) / COLS, (area * 0.94) / ROWS)
    bw, bh = cell * COLS, cell * ROWS
    bx = (w - bw) / 2
    by = top_h + (area - bh) / 2
    return top_h, bottom_h, cell, bw, bh, bx, by


def get_buttons(w, h):
    top_h, *_ = layout(w, h)
    bh_btn = max(30, int(top_h * 0.55))
    nw = int(bh_btn * 2.1)
    new_rect = pygame.Rect(w - nw - 12, (top_h - bh_btn) // 2, nw, bh_btn)
    hw = int(bh_btn * 2.9)
    help_rect = pygame.Rect(new_rect.left - hw - 8,
                            (top_h - bh_btn) // 2, hw, bh_btn)
    return new_rect, help_rect


def col_at(pos, L):
    _, _, cell, bw, bh, bx, by = L
    x, y = pos
    if by - cell * 0.7 <= y <= by + bh and bx <= x <= bx + bw:
        c = int((x - bx) / cell)
        if 0 <= c < COLS:
            return c
    return None


# ---------- ходы ----------
def do_player_move(c):
    global turn, winner, win_cells_list, last_move, message
    global bot_state, bot_wait_start, bot_scores, bot_chosen, bot_reason

    if winner is not None or turn != PLAYER:
        return
    if not board.can_drop(c):
        return

    r = board.drop(c, PLAYER)
    history.append(c)
    last_move = (r, c)
    bot_scores = None
    bot_chosen = None
    bot_reason = ""

    if check_win(board.grid, r, c, PLAYER):
        winner = PLAYER
        win_cells_list = win_cells(board.grid, r, c, PLAYER)
        message = "Вы победили!"
        return
    if board.is_full():
        winner = 0
        message = "Ничья"
        return

    turn = BOT
    bot_state = 'waiting'
    bot_wait_start = time.time()
    message = "Бот думает..."


def apply_bot_move():
    global turn, winner, win_cells_list, last_move, message
    global bot_scores, bot_chosen, bot_reason, bot_depth, bot_state, history

    try:
        col, scores, depth, tag = find_best_move(
            board, BOT, time_limit=1.4, max_depth=9)
    except Exception as e:
        print(f"[bot] fallback: {e}")
        col = next((c for c in COLUMN_ORDER if board.can_drop(c)), 0)
        scores, depth, tag = {}, 1, None

    # --- почему сюда? ---
    if tag == "win":
        reason = "Форсирую победу в ближайшем ходе."
    else:
        s = scores.get(col, 0)
        threats = []
        for c in range(COLS):
            if not board.can_drop(c):
                continue
            r = board.drop(c, PLAYER)
            w = check_win(board.grid, r, c, PLAYER)
            board.undo(c)
            if w:
                threats.append(c)

        if len(threats) == 1 and col == threats[0]:
            reason = f"Блокирую немедленную победу соперника в столбце {col+1}."
        elif s > 50000:
            reason = f"Вижу форсированный выигрыш (оценка +{s//1000}k)."
        elif s < -50000:
            reason = "Все варианты проигрышны — выбираю наименьшее зло."
        elif s > 0:
            reason = f"Лучшая оценка позиции +{s} (глубина {depth})."
        elif s == 0:
            reason = f"Позиция равна (глубина {depth})."
        else:
            reason = f"Оценка {s} (глубина {depth})."

    bot_scores = scores
    bot_chosen = col
    bot_reason = reason
    bot_depth = depth
    bot_state = 'idle'

    r = board.drop(col, BOT)
    history.append(col)
    last_move = (r, col)

    if check_win(board.grid, r, col, BOT):
        winner = BOT
        win_cells_list = win_cells(board.grid, r, col, BOT)
        message = "Бот победил"
        return
    if board.is_full():
        winner = 0
        message = "Ничья"
        return

    turn = PLAYER
    message = "Ваш ход"


# ---------- отрисовка ----------
def _draw_top(w, h, top_h):
    pygame.draw.rect(screen, BG2, (0, 0, w, top_h))
    f = font(max(16, int(top_h * 0.34)), bold=True)
    t = f.render("4 в ряд", True, TEXT)
    screen.blit(t, (16, (top_h - t.get_height()) // 2))

    new_rect, help_rect = get_buttons(w, h)
    f2 = font(max(11, int(new_rect.h * 0.32)), bold=True)

    pygame.draw.rect(screen, (60, 120, 220), new_rect,
                     border_radius=int(new_rect.h * 0.3))
    nt = f2.render("Новая", True, WHITE)
    screen.blit(nt, nt.get_rect(center=new_rect.center))

    pygame.draw.rect(screen, (60, 70, 100), help_rect,
                     border_radius=int(help_rect.h * 0.3))
    ht = f2.render("Почему?", True, TEXT)
    screen.blit(ht, ht.get_rect(center=help_rect.center))


def _draw_scores(cell, bw, bx, by):
    f = font(max(10, int(cell * 0.20)), bold=True)
    for c in range(COLS):
        if not bot_scores or c not in bot_scores:
            continue
        v = bot_scores[c]
        cx = bx + c * cell + cell / 2
        cy = by - cell * 0.35
        if v > 50000:
            txt, color = "ПОБЕДА", GOOD
        elif v < -50000:
            txt, color = "ПРОИГР.", BAD
        else:
            txt = f"{v:+d}" if v != 0 else "0"
            color = GOOD if v > 0 else (BAD if v < 0 else SUBTEXT)
        surf = f.render(txt, True, color)
        screen.blit(surf, surf.get_rect(center=(cx, cy)))
        if bot_chosen == c:
            pygame.draw.polygon(screen, ACCENT, [
                (cx - cell * 0.15, cy + cell * 0.18),
                (cx + cell * 0.15, cy + cell * 0.18),
                (cx, cy + cell * 0.30),
            ])


def _draw_bottom(w, h, bottom_h):
    y0 = h - bottom_h
    pygame.draw.rect(screen, BG2, (0, y0, w, bottom_h))
    fmsg = font(max(14, int(bottom_h * 0.24)), bold=True)
    freason = font(max(11, int(bottom_h * 0.17)))

    color = TEXT
    if winner == PLAYER:
        color = PLAYER_COLOR
    elif winner == BOT:
        color = BOT_COLOR
    elif turn == BOT and winner is None:
        color = BOT_COLOR

    msg_surf = fmsg.render(message, True, color)
    screen.blit(msg_surf, (16, y0 + 8))

    if bot_reason and show_scores:
        words = bot_reason.split()
        lines, cur = [], ""
        maxw = w - 32
        for wd in words:
            test = (cur + " " + wd).strip()
            if freason.size(test)[0] <= maxw:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
        yy = y0 + 8 + msg_surf.get_height() + 4
        for line in lines[:3]:
            s = freason.render(line, True, SUBTEXT)
            screen.blit(s, (16, yy))
            yy += s.get_height() + 1
    elif turn == PLAYER and winner is None and not bot_reason:
        tip = freason.render("Тапните по столбцу, чтобы сделать ход",
                             True, SUBTEXT)
        screen.blit(tip, (16, y0 + 8 + msg_surf.get_height() + 6))


def _winner_button(w, h):
    btn = pygame.Rect(0, 0, min(260, int(w * 0.7)), int(h * 0.06))
    btn.center = (w // 2, h // 2 + 30)
    return btn


def _draw_winner_overlay(w, h):
    ov = pygame.Surface((w, h), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 150))
    screen.blit(ov, (0, 0))
    f = font(max(22, int(h * 0.04)), bold=True)
    f2 = font(max(14, int(h * 0.022)), bold=True)

    if winner == PLAYER:
        txt, color = "Вы победили!", PLAYER_COLOR
    elif winner == BOT:
        txt, color = "Бот победил", BOT_COLOR
    else:
        txt, color = "Ничья", TEXT

    surf = f.render(txt, True, color)
    screen.blit(surf, surf.get_rect(center=(w // 2, h // 2 - 30)))

    btn = _winner_button(w, h)
    pygame.draw.rect(screen, (60, 120, 220), btn,
                     border_radius=int(btn.h * 0.4))
    bt = f2.render("Новая игра", True, WHITE)
    screen.blit(bt, bt.get_rect(center=btn.center))


def draw():
    w, h = screen.get_size()
    screen.fill(BG)
    top_h, bottom_h, cell, bw, bh, bx, by = layout(w, h)

    _draw_top(w, h, top_h)

    pad = cell * 0.08
    rect = pygame.Rect(int(bx - pad), int(by - pad),
                       int(bw + 2 * pad), int(bh + 2 * pad))
    pygame.draw.rect(screen, BOARD_DARK, rect.move(0, int(cell * 0.06)),
                     border_radius=int(cell * 0.25))
    pygame.draw.rect(screen, BOARD_COLOR, rect,
                     border_radius=int(cell * 0.25))

    if hover_col is not None and winner is None and turn == PLAYER \
            and board.can_drop(hover_col):
        cx = bx + hover_col * cell + cell / 2
        cy = by - cell * 0.5
        ghost = pygame.Surface((int(cell), int(cell)), pygame.SRCALPHA)
        pygame.draw.circle(ghost, (*PLAYER_COLOR, 110),
                           (int(cell / 2), int(cell / 2)), int(cell * 0.28))
        screen.blit(ghost, (cx - cell / 2, cy - cell / 2))

    for r in range(ROWS):
        for c in range(COLS):
            cx = bx + c * cell + cell / 2
            cy = by + r * cell + cell / 2
            v = board.grid[r][c]
            pygame.draw.circle(screen, HOLE, (int(cx), int(cy)),
                               int(cell * 0.41))
            if v == PLAYER:
                pygame.draw.circle(screen, PLAYER_COLOR,
                                   (int(cx), int(cy)), int(cell * 0.36))
                pygame.draw.circle(screen, (255, 165, 175),
                                   (int(cx - cell * 0.10),
                                    int(cy - cell * 0.10)),
                                   int(cell * 0.09))
            elif v == BOT:
                pygame.draw.circle(screen, BOT_COLOR,
                                   (int(cx), int(cy)), int(cell * 0.36))
                pygame.draw.circle(screen, (255, 240, 170),
                                   (int(cx - cell * 0.10),
                                    int(cy - cell * 0.10)),
                                   int(cell * 0.09))

    for (r, c) in win_cells_list:
        cx = bx + c * cell + cell / 2
        cy = by + r * cell + cell / 2
        pygame.draw.circle(screen, WHITE, (int(cx), int(cy)),
                           int(cell * 0.40), max(2, int(cell * 0.05)))

    if last_move:
        r, c = last_move
        cx = bx + c * cell + cell / 2
        cy = by + r * cell + cell / 2
        pygame.draw.circle(screen, ACCENT, (int(cx), int(cy)),
                           int(cell * 0.44), max(2, int(cell * 0.04)))

    if show_scores and bot_scores:
        _draw_scores(cell, bw, bx, by)

    _draw_bottom(w, h, bottom_h)

    if winner is not None:
        _draw_winner_overlay(w, h)

    pygame.display.flip()


# ---------- обработка тапа ----------
def handle_tap(pos):
    global show_scores, hover_col

    # дебаунс: на телефоне FINGERDOWN и MOUSEBUTTONDOWN могут прийти оба
    now = time.time()
    if now - _last_tap_ts[0] < 0.15:
        return
    _last_tap_ts[0] = now

    w, h = screen.get_size()

    if winner is not None:
        if _winner_button(w, h).collidepoint(pos):
            new_game()
        return

    new_rect, help_rect = get_buttons(w, h)
    if new_rect.collidepoint(pos):
        new_game()
        return
    if help_rect.collidepoint(pos):
        show_scores = not show_scores
        return

    if turn != PLAYER:
        return

    L = layout(w, h)
    c = col_at(pos, L)
    if c is not None and board.can_drop(c):
        do_player_move(c)


# ============================================================
#  ГЛАВНЫЙ ЦИКЛ
# ============================================================
def main():
    global hover_col, screen, bot_state
    clock = pygame.time.Clock()
    fullscreen = False
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(
                    (max(320, event.w), max(480, event.h)), pygame.RESIZABLE)

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode((0, 0),
                                                         pygame.FULLSCREEN)
                    else:
                        screen = pygame.display.set_mode((480, 820),
                                                         pygame.RESIZABLE)
                elif event.key == pygame.K_n:
                    new_game()
                elif event.key == pygame.K_h:
                    # toggle help
                    import builtins
                    pass

            elif event.type == pygame.MOUSEMOTION:
                w, h = screen.get_size()
                L = layout(w, h)
                hover_col = col_at(event.pos, L)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                handle_tap(event.pos)

            elif event.type == pygame.FINGERDOWN:
                w, h = screen.get_size()
                handle_tap((event.x * w, event.y * h))

        # --- ход бота ---
        if bot_state == 'waiting' and time.time() - bot_wait_start > 0.35:
            bot_state = 'thinking'
            draw()  # покажем «думает...»

        if bot_state == 'thinking':
            apply_bot_move()

        draw()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()