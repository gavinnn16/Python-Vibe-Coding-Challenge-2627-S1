"""
STARFORGE - a living particle universe you can play with.

main.py is the "front end": it opens the window, reads the keyboard and mouse,
asks sim.py to move 26,000 particles, and draws the result with a glow effect.

Run it with:   python main.py
"""
import argparse
import json
import math
import os
import time

try:
    import numpy as np
    import pygame
except ImportError:
    print("\nSTARFORGE needs two libraries: pygame-ce and numpy.")
    print("Install them with this command, then run the game again:\n")
    print("    pip install pygame-ce numpy\n")
    input("Press Enter to close...")
    raise SystemExit(1)

import sim
from sim import GALAXY, FLOW, FIREWORKS, WELLS, GAME, MODE_NAMES

W, H = 1280, 720
FPS = 60
N_PARTICLES = 26000
HERE = os.path.dirname(os.path.abspath(__file__))
SAVE_FILE = os.path.join(HERE, "highscore.json")
SHOT_DIR = os.path.join(HERE, "screenshots")

TRAIL_STEPS = [0.4, 0.7, 1.0, 1.6, 2.5]   # multiplier on the fade speed (smaller = longer trails)
BLOOM_NAMES = ["off", "soft", "strong"]

HINTS = {
    GALAXY:    "Hold LEFT mouse to pull the stars, RIGHT to push.  SPACE drops a black hole.  X clears them.",
    FLOW:      "Hold LEFT mouse to pull, RIGHT to push.  SPACE sends a shockwave through the flow.",
    FIREWORKS: "Hold LEFT mouse to paint with sparks.  Click for a big burst.  SPACE = ring burst.",
    WELLS:     "SPACE places a new gravity well (max 8).  X clears them.  Hold LEFT / RIGHT to pull / push.",
    GAME:      "Steer the swarm into the glowing orbs.  LEFT = tighten the swarm, RIGHT = scatter it.  Avoid red voids!",
}
KEYS_LINE = "1-4 modes   G game   C colours   T trails   B bloom   P pause   S screenshot   F11 fullscreen   H hide help   ESC quit"


# ------------------------------------------------------------------ sound ---
def make_sounds():
    """Synthesise every sound effect with NumPy - no audio files needed."""
    init = pygame.mixer.get_init()
    if not init:
        return {}
    sr, _, chans = init

    def tone(freq, dur, vol=0.35, glide=0.0, decay=7.0):
        t = np.arange(int(sr * dur)) / sr
        phase = 2 * math.pi * np.cumsum(freq + glide * t) / sr
        wave = (np.sin(phase) + 0.35 * np.sin(2 * phase)) * np.exp(-decay * t)
        a = (wave * vol * 32767 / 1.35).astype(np.int16)
        if chans >= 2:
            a = np.column_stack([a] * chans)
        return pygame.sndarray.make_sound(np.ascontiguousarray(a))

    try:
        scale = [523.25, 587.33, 659.25, 783.99, 880.0, 1046.5]   # C pentatonic: always sounds nice
        return {
            "ping": [tone(f, 0.45) for f in scale],
            "miss": tone(220, 0.5, glide=-110, decay=5),
            "over": tone(440, 1.1, glide=-300, decay=3),
            "pop": tone(160, 0.25, vol=0.3, glide=-60, decay=14),
        }
    except Exception:
        return {}


# ------------------------------------------------------------- background ---
def make_background(w, h):
    """Deep-space gradient with a vignette and a sprinkle of stars (built once)."""
    xx, yy = np.meshgrid(np.arange(w), np.arange(h), indexing="ij")
    d = np.hypot((xx - w / 2) / w, (yy - h / 2) / h)
    v = np.clip(1.0 - d * 1.5, 0.0, 1.0)
    arr = np.zeros((w, h, 3), np.uint8)
    arr[..., 0] = 6 + 14 * v
    arr[..., 1] = 5 + 8 * v
    arr[..., 2] = 16 + 30 * v
    rng = np.random.default_rng(7)
    sx, sy = rng.integers(0, w, 380), rng.integers(0, h, 380)
    b = rng.integers(60, 230, 380).astype(np.uint8)
    arr[sx, sy] = np.column_stack([b, b, b])
    return pygame.surfarray.make_surface(arr)


# -------------------------------------------------------------------- app ---
class App:
    def __init__(self, args):
        self.args = args
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        try:
            pygame.mixer.init(44100, -16, 2, 512)
        except pygame.error:
            pass
        pygame.display.set_caption("STARFORGE - a living particle universe")
        self.screen = pygame.display.set_mode((W, H), pygame.SCALED | pygame.RESIZABLE)
        self.clock = pygame.time.Clock()

        # off-screen surfaces: the glowing "canvas" and the blur layers for bloom
        self.canvas = pygame.Surface((W, H)).convert()
        self.canvas.fill((0, 0, 0))
        self.s4 = pygame.Surface((W // 4, H // 4)).convert()
        self.s16 = pygame.Surface((W // 16, H // 16)).convert()
        self.b4 = pygame.Surface((W, H)).convert()
        self.b16 = pygame.Surface((W, H)).convert()
        self.bg = make_background(W, H).convert()
        self.dim = pygame.Surface((W, H), pygame.SRCALPHA)
        self.dim.fill((0, 0, 0, 150))

        self.font_s = pygame.font.SysFont("consolas,dejavusansmono,couriernew,monospace", 17)
        self.font_m = pygame.font.SysFont("consolas,dejavusansmono,couriernew,monospace", 26, bold=True)
        self.font_l = pygame.font.SysFont("consolas,dejavusansmono,couriernew,monospace", 78, bold=True)

        self.sounds = make_sounds()
        self.u = sim.Universe(W, H, N_PARTICLES, seed=args.seed)
        self.u.best = self.load_best()

        self.trail_i = 2
        self.bloom = 2
        self.show_hud = True
        self.paused = False
        self.running = True
        self.t_app = 0.0
        self.toast = ("", 0.0)
        self.cursor_hidden = False
        self.fps_text = "--"

        if args.game:
            self.u.start_game()
        else:
            self.u.set_mode({"galaxy": GALAXY, "flow": FLOW, "fireworks": FIREWORKS,
                             "wells": WELLS}[args.mode])

    # ------------------------------------------------------------ helpers ---
    def load_best(self):
        try:
            with open(SAVE_FILE) as f:
                return int(json.load(f).get("best", 0))
        except (OSError, ValueError):
            return 0

    def save_best(self):
        try:
            with open(SAVE_FILE, "w") as f:
                json.dump({"best": int(self.u.best)}, f)
        except OSError:
            pass

    def play(self, name, index=0):
        s = self.sounds.get(name)
        if isinstance(s, list):
            s = s[min(index, len(s) - 1)]
        if s:
            s.play()

    def say(self, text):
        self.toast = (text, 2.2)

    def screenshot(self):
        os.makedirs(SHOT_DIR, exist_ok=True)
        path = os.path.join(SHOT_DIR, time.strftime("starforge_%Y%m%d_%H%M%S.png"))
        pygame.image.save(self.screen, path)
        self.say("Screenshot saved to screenshots/")
        return path

    # ------------------------------------------------------------- events ---
    def handle_events(self):
        u = self.u
        mx, my = pygame.mouse.get_pos()
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
            elif e.type == pygame.MOUSEWHEEL:
                u.strength = min(4.0, max(0.3, u.strength * (1.15 ** e.y)))
                self.say(f"Mouse strength x{u.strength:.2f}")
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and u.mode == FIREWORKS:
                u.burst(mx, my, count=1000, power=300)
                self.play("pop")
            elif e.type == pygame.KEYDOWN:
                k = e.key
                if k == pygame.K_ESCAPE:
                    self.running = False
                elif k in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    u.set_mode(k - pygame.K_1)
                    self.trail_i = 2
                    self.say(MODE_NAMES[u.mode])
                elif k == pygame.K_g:
                    if u.mode == GAME:
                        u.set_mode(GALAXY)
                    else:
                        u.start_game()
                elif k in (pygame.K_r, pygame.K_RETURN) and u.mode == GAME:
                    u.start_game()
                elif k == pygame.K_c:
                    u.next_palette()
                    self.say(f"Palette: {u.palette_name}")
                elif k == pygame.K_t:
                    self.trail_i = (self.trail_i + 1) % len(TRAIL_STEPS)
                    self.say(f"Trail length {5 - self.trail_i}/5")
                elif k == pygame.K_b:
                    self.bloom = (self.bloom + 1) % 3
                    self.say(f"Bloom: {BLOOM_NAMES[self.bloom]}")
                elif k == pygame.K_h:
                    self.show_hud = not self.show_hud
                elif k == pygame.K_p:
                    self.paused = not self.paused
                elif k == pygame.K_s:
                    self.screenshot()
                elif k == pygame.K_x:
                    u.clear_wells()
                elif k == pygame.K_SPACE:
                    u.action(mx, my)
                elif k == pygame.K_F11:
                    pygame.display.toggle_fullscreen()

    def after_update(self):
        u = self.u
        for ev in u.events:
            if ev[0] == "collect":
                self.play("ping", ev[1] - 1)
            elif ev[0] == "miss":
                self.play("miss")
            elif ev[0] == "over":
                self.play("over")
                self.save_best()
        u.events.clear()

    # ------------------------------------------------------------ drawing ---
    def draw_particles(self):
        ix, iy, col = self.u.particle_pixels()
        arr = pygame.surfarray.pixels3d(self.canvas)       # direct (x, y, rgb) view of the pixels
        try:
            cur = arr[ix, iy].astype(np.int16)
            arr[ix, iy] = np.minimum(cur + col, 255).astype(np.uint8)   # additive blending
        finally:
            del arr                                         # must release the surface lock

    def draw_glow_objects(self):
        """Things that should glow: shock-rings, black-hole rims, orb rings, voids."""
        u, c, t = self.u, self.canvas, self.u.t
        lut = u.lut
        rim = tuple(int(v) for v in lut[210])

        for x, y, r, life, power in u.rings:
            if r >= 1:
                col = (int(120 * life * power + 40 * life), int(220 * life * power + 30 * life), int(255 * life))
                pygame.draw.circle(c, col, (int(x), int(y)), int(r), max(1, int(5 * life)))

        if u.mode in (GALAXY, WELLS):
            holes = [(w[0], w[1]) for w in u.user_wells]
            if u.mode == GALAXY:
                holes.append((u.cx, u.cy))
            for (x, y) in holes:
                pygame.draw.circle(c, rim, (int(x), int(y)), 15, 2)

        if u.mode == GAME:
            for v in u.voids:
                pulse = 3 + int(2 * math.sin(t * 6))
                pygame.draw.circle(c, (255, 40, 90), (int(v["x"]), int(v["y"])), int(v["r"]), pulse)
            for o in u.orbs:
                late = o["age"] > 11 and int(t * 6) % 2 == 0
                col = (255, 140, 90) if late else (90, 225, 255)
                pygame.draw.circle(c, col, (int(o["x"]), int(o["y"])), int(o["r"] * (1 + 0.06 * math.sin(t * 5))), 3)

    def draw_bloom(self):
        if not self.bloom:
            return
        pygame.transform.smoothscale(self.canvas, (W // 4, H // 4), self.s4)
        pygame.transform.smoothscale(self.s4, (W // 16, H // 16), self.s16)
        pygame.transform.smoothscale(self.s4, (W, H), self.b4)
        pygame.transform.smoothscale(self.s16, (W, H), self.b16)
        for _ in range(self.bloom):
            self.screen.blit(self.b4, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
            self.screen.blit(self.b16, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def text(self, s, pos, font, color=(235, 240, 255), alpha=255, center=False):
        shadow = font.render(s, True, (0, 0, 0))
        img = font.render(s, True, color)
        if alpha < 255:
            shadow.set_alpha(alpha)
            img.set_alpha(alpha)
        r = img.get_rect()
        if center:
            r.center = pos
        else:
            r.topleft = pos
        self.screen.blit(shadow, r.move(2, 2))
        self.screen.blit(img, r)
        return r

    def draw_world_overlay(self, mx, my):
        """Solid things drawn on top of the glow: black-hole discs, orbs, cursor."""
        u, scr, t = self.u, self.screen, self.u.t
        if u.mode in (GALAXY, WELLS):
            holes = [(w[0], w[1]) for w in u.user_wells]
            if u.mode == GALAXY:
                holes.append((u.cx, u.cy))
            for (x, y) in holes:
                pygame.draw.circle(scr, (0, 0, 0), (int(x), int(y)), 11)

        if u.mode == GAME:
            for v in u.voids:
                pygame.draw.circle(scr, (6, 0, 10), (int(v["x"]), int(v["y"])), int(v["r"] - 3))
            for o in u.orbs:
                R = int(o["r"])
                glow = pygame.Surface((2 * R, 2 * R), pygame.SRCALPHA)
                pygame.draw.circle(glow, (90, 225, 255, int(30 + 90 * o["charge"])), (R, R), R)
                scr.blit(glow, (int(o["x"]) - R, int(o["y"]) - R))
                if o["charge"] > 0.01:
                    rect = pygame.Rect(0, 0, 2 * R + 14, 2 * R + 14)
                    rect.center = (int(o["x"]), int(o["y"]))
                    start = math.pi / 2 - 2 * math.pi * min(o["charge"], 1.0)
                    pygame.draw.arc(scr, (255, 255, 255), rect, start, math.pi / 2, 5)
            # custom cursor: a ring that tightens while you hold the left button
            pygame.draw.circle(scr, (255, 255, 255), (mx, my), 14, 2)
            pygame.draw.circle(scr, (255, 255, 255), (mx, my), 2)

    def draw_hud(self):
        u, scr = self.u, self.screen
        self.text(f"{MODE_NAMES[u.mode]}  |  {u.palette_name}  |  {self.fps_text} FPS  |  {u.n:,} particles",
                  (14, 10), self.font_s, (170, 180, 210))

        if u.mode == GAME:
            self.text(f"SCORE {u.score}", (W // 2, 34), self.font_m, center=True)
            frac = max(0.0, min(1.0, u.timeleft / 45.0))
            bar = pygame.Rect(W // 2 - 210, 62, 420, 10)
            pygame.draw.rect(scr, (40, 45, 70), bar, border_radius=5)
            col = (90, 225, 255) if frac > 0.25 else (255, 110, 90)
            pygame.draw.rect(scr, col, (bar.x, bar.y, int(bar.w * frac), bar.h), border_radius=5)
            self.text(f"{u.timeleft:0.1f}s", (W // 2, 90), self.font_s, (200, 210, 235), center=True)
            self.text(f"BEST {u.best}", (W - 150, 10), self.font_s, (170, 180, 210))
            if u.combo > 1 and u.game_t - u.last_collect < 5.0:
                self.text(f"x{u.combo} COMBO!", (W // 2, 128), self.font_m, (255, 220, 120), center=True)
            if u.game_t < 4.0 and u.state == "play":
                self.text("ORB RUSH", (W // 2, H // 2 - 40), self.font_l, (255, 255, 255),
                          alpha=int(255 * (1 - u.game_t / 4.0)), center=True)
                self.text("Fill the orbs with swarm. Dodge the voids. Beat the clock.", (W // 2, H // 2 + 20),
                          self.font_m, (200, 220, 255), alpha=int(255 * (1 - u.game_t / 4.0)), center=True)

        if self.show_hud:
            self.text(HINTS[u.mode], (14, H - 52), self.font_s, (200, 210, 235))
            self.text(KEYS_LINE, (14, H - 28), self.font_s, (130, 140, 170))

        msg, left = self.toast
        if left > 0:
            self.text(msg, (W // 2, H - 90), self.font_s, (255, 255, 255),
                      alpha=int(255 * min(1.0, left)), center=True)
        if self.paused:
            self.text("PAUSED", (W // 2, H // 2), self.font_l, center=True)

        if u.mode == GAME and u.state == "over":
            self.screen.blit(self.dim, (0, 0))
            self.text("TIME'S UP", (W // 2, H // 2 - 90), self.font_l, center=True)
            self.text(f"Score {u.score}     Best {u.best}", (W // 2, H // 2), self.font_m, (255, 220, 120), center=True)
            if u.score >= u.best and u.score > 0:
                self.text("NEW HIGH SCORE!", (W // 2, H // 2 + 44), self.font_m, (120, 255, 190), center=True)
            self.text("R / ENTER = play again     G = back to the sandbox", (W // 2, H // 2 + 100),
                      self.font_s, (200, 210, 235), center=True)

        # title splash
        if self.t_app < 3.4 and u.mode != GAME:
            a = int(255 * max(0.0, min(1.0, (3.4 - self.t_app) / 1.2)))
            self.text("STARFORGE", (W // 2, H // 2 - 30), self.font_l, center=True, alpha=a)
            self.text("a living particle universe", (W // 2, H // 2 + 28), self.font_m,
                      (180, 200, 255), center=True, alpha=a)

    def draw(self, mx, my):
        u = self.u
        base = sim.TRAIL_FADE[u.mode]
        fade = max(1, int(base * TRAIL_STEPS[self.trail_i]))
        if not self.paused:
            self.canvas.fill((fade, fade, fade), special_flags=pygame.BLEND_RGB_SUB)   # trails fade out
            self.draw_particles()
            self.draw_glow_objects()

        self.screen.blit(self.bg, (0, 0))
        self.screen.blit(self.canvas, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        self.draw_bloom()
        self.draw_world_overlay(mx, my)
        self.draw_hud()

        hide = (u.mode == GAME)
        if hide != self.cursor_hidden:
            pygame.mouse.set_visible(not hide)
            self.cursor_hidden = hide

    # ---------------------------------------------------------------- loop ---
    def run(self):
        frame = 0
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.t_app += dt
            if frame % 20 == 0:
                self.fps_text = f"{self.clock.get_fps():.0f}"
            self.handle_events()
            mx, my = pygame.mouse.get_pos()
            lmb, _, rmb = pygame.mouse.get_pressed()
            if not self.paused:
                self.u.update(dt, mx, my, lmb, rmb)
                self.after_update()
            msg, left = self.toast
            self.toast = (msg, max(0.0, left - dt))
            self.draw(mx, my)
            pygame.display.flip()
            frame += 1
            if self.args.frames and frame >= self.args.frames:
                if self.args.shot:
                    pygame.image.save(self.screen, self.args.shot)
                break
        pygame.quit()


def parse_args():
    p = argparse.ArgumentParser(description="STARFORGE - a living particle universe")
    p.add_argument("--mode", choices=["galaxy", "flow", "fireworks", "wells"], default="galaxy",
                   help="which sandbox mode to start in")
    p.add_argument("--game", action="store_true", help="start directly in ORB RUSH")
    p.add_argument("--seed", type=int, default=None, help="random seed (same seed = same universe)")
    p.add_argument("--frames", type=int, default=0, help=argparse.SUPPRESS)   # for automated tests
    p.add_argument("--shot", type=str, default="", help=argparse.SUPPRESS)    # for automated tests
    return p.parse_args()


if __name__ == "__main__":
    App(parse_args()).run()
