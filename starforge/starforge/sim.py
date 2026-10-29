"""
sim.py - the simulation core of STARFORGE.

Everything here is plain NumPy (no pygame), so the physics and the game rules
are completely separate from drawing. main.py draws whatever this module
computes.

Why NumPy?  Each particle is just a row in a few big arrays (x, y, vx, vy).
One line such as  `vx += dx * f * dt`  updates all 26,000 particles at once in
compiled C code instead of looping over them in slow Python.
"""
import math
import numpy as np

# ----------------------------------------------------------------- modes ---
GALAXY, FLOW, FIREWORKS, WELLS, GAME = range(5)
MODE_NAMES = ["GALAXY", "FLOW FIELD", "FIREWORKS", "GRAVITY WELLS", "ORB RUSH"]

# --------------------------------------------------------------- palettes ---
PALETTES = {
    "Aurora":  [(30, 60, 160), (0, 190, 170), (110, 255, 150), (210, 130, 255), (255, 255, 255)],
    "Inferno": [(110, 20, 60), (220, 50, 30), (255, 150, 20), (255, 235, 120), (255, 255, 255)],
    "Ocean":   [(10, 60, 160), (0, 140, 255), (0, 230, 230), (160, 255, 240), (255, 255, 255)],
    "Neon":    [(255, 30, 160), (150, 60, 255), (40, 200, 255), (60, 255, 170), (255, 255, 120)],
    "Sakura":  [(170, 60, 120), (255, 110, 170), (255, 170, 200), (255, 225, 235), (255, 255, 255)],
}


def build_lut(stops):
    """Turn a few colour stops into a smooth 256-entry colour lookup table."""
    stops = np.array(stops, dtype=np.float32)
    xs = np.linspace(0.0, 1.0, len(stops))
    ts = np.linspace(0.0, 1.0, 256)
    return np.stack([np.interp(ts, xs, stops[:, c]) for c in range(3)], axis=1).astype(np.float32)


# ---------------------------------------------------------------- physics ---
SOFT = 400.0   # "softening": stops forces becoming infinite when r -> 0
GM = 4.0e6     # strength of the central star in GALAXY mode
V_MAX = 900.0  # speed limit so slingshots never explode the simulation
SPEED_COLOUR_SCALE = {GALAXY: 0.85, FLOW: 1.5, FIREWORKS: 1.0, WELLS: 0.8, GAME: 1.3}
TRAIL_FADE = {GALAXY: 22, FLOW: 7, FIREWORKS: 9, WELLS: 10, GAME: 26}
GAIN = {GALAXY: 0.32, FLOW: 0.32, FIREWORKS: 1.0, WELLS: 0.4, GAME: 0.45}


class Universe:
    def __init__(self, w, h, n=26000, seed=None):
        self.w, self.h, self.n = w, h, n
        self.cx, self.cy = w / 2, h / 2
        self.rng = np.random.default_rng(seed)

        f32 = np.float32
        self.x = np.zeros(n, f32)
        self.y = np.zeros(n, f32)
        self.vx = np.zeros(n, f32)
        self.vy = np.zeros(n, f32)
        self.life = np.zeros(n, f32)    # fireworks only: 1 -> 0
        self.decay = np.ones(n, f32)    # fireworks only: how fast life drains
        self.hue = np.zeros(n, f32)     # fireworks only: colour of each burst

        self.t = 0.0
        self.mode = GALAXY
        self.user_wells = []            # [x, y, strength]
        self.strength = 1.0             # mouse-wheel controlled
        self.palette_names = list(PALETTES)
        self.palette_i = 0
        self.lut = build_lut(PALETTES[self.palette_names[0]])
        self.firework_timer = 0.0
        self.events = []                # ("collect", combo), ("miss",), ... for sound
        self.rings = []                 # expanding shock-rings (visual effect)

        # game state
        self.state = "idle"             # idle | play | over
        self.score = 0
        self.best = 0
        self.timeleft = 0.0
        self.game_t = 0.0
        self.combo = 0
        self.last_collect = -99.0
        self.orbs = []
        self.voids = []

        self.set_mode(GALAXY)

    # ----------------------------------------------------------- settings ---
    @property
    def palette_name(self):
        return self.palette_names[self.palette_i]

    def next_palette(self):
        self.palette_i = (self.palette_i + 1) % len(self.palette_names)
        self.lut = build_lut(PALETTES[self.palette_name])

    def set_mode(self, mode):
        self.mode = mode
        self.user_wells = []
        self.rings = []
        if mode == WELLS:
            w, h = self.w, self.h
            self.user_wells = [[w * 0.28, h * 0.55, 3.0e6],
                               [w * 0.72, h * 0.55, 3.0e6],
                               [w * 0.50, h * 0.25, 2.2e6]]
        if mode != GAME:
            self.state = "idle"
        self.seed_all()

    def seed_all(self):
        self.life[:] = 0
        if self.mode != FIREWORKS:
            self.respawn(np.arange(self.n), initial=True)

    # ------------------------------------------------------------ respawn ---
    def respawn(self, idx, initial=False):
        """Put the particles in `idx` back into play, the way the mode wants."""
        k = len(idx)
        if k == 0:
            return
        r, m, w, h = self.rng, self.mode, self.w, self.h

        if m == GALAXY:
            rad = 22 + 330 * np.sqrt(r.random(k))
            arm = r.integers(0, 2, k)                      # two spiral arms
            ang = arm * math.pi + rad * 0.017 + r.normal(0, 0.3, k)
            c, s = np.cos(ang), np.sin(ang)
            self.x[idx] = self.cx + rad * c
            self.y[idx] = self.cy + rad * s
            vc = np.sqrt(GM / np.maximum(rad, 1.0)) * (0.9 + 0.2 * r.random(k))
            self.vx[idx] = -s * vc                          # tangent = circular orbit
            self.vy[idx] = c * vc

        elif m == WELLS:
            if initial:
                self.x[idx] = r.random(k) * w
                self.y[idx] = r.random(k) * h
                a = r.random(k) * 2 * math.pi
                sp = 40 + 120 * r.random(k)
            else:                                           # fly in from an edge
                side = r.integers(0, 4, k)
                t = r.random(k)
                px = np.where(side == 0, -10.0, np.where(side == 1, w + 10.0, t * w))
                py = np.where(side == 2, -10.0, np.where(side == 3, h + 10.0, t * h))
                self.x[idx], self.y[idx] = px, py
                a = np.arctan2(self.cy - py, self.cx - px) + r.normal(0, 0.6, k)
                sp = 90 + 150 * r.random(k)
            self.vx[idx] = np.cos(a) * sp
            self.vy[idx] = np.sin(a) * sp

        else:                                               # FLOW and GAME
            self.x[idx] = r.random(k) * w
            self.y[idx] = r.random(k) * h
            self.vx[idx] = 0
            self.vy[idx] = 0

    # ---------------------------------------------------------- integrator ---
    def flow_angle(self, x, y):
        t = self.t
        return (np.sin(x * 0.0055 + t * 0.23)
                + np.sin(y * 0.0068 - t * 0.19)
                + np.sin((x + y) * 0.0041 + t * 0.11)
                + np.cos(np.hypot(x - self.cx, y - self.cy) * 0.009 - t * 0.35)) * 1.57

    def integrate(self, dt, wells, drag=0.0, flow_k=0.0, gy=0.0, wrap=False):
        """
        Move every particle one frame.
        wells = list of (x, y, strength, kill_radius).
        Force from a well:  a = strength * d / (|d|^2 + SOFT)^1.5   (gravity-like)
        A negative strength pushes particles away instead of pulling.
        Returns a boolean array: which particles fell into a well.
        """
        f32 = np.float32
        kill = np.zeros(self.n, bool)
        sub = 2                                   # two sub-steps = more stable orbits
        h = dt / sub
        for _ in range(sub):
            for (wx, wy, s, kr) in wells:
                dx = f32(wx) - self.x
                dy = f32(wy) - self.y
                r2 = dx * dx + dy * dy + f32(SOFT)
                f = f32(s) / (r2 * np.sqrt(r2))
                self.vx += dx * f * f32(h)
                self.vy += dy * f * f32(h)
                if kr > 0:
                    kill |= r2 < f32(kr * kr + SOFT)
            if flow_k:
                a = self.flow_angle(self.x, self.y)
                self.vx += np.cos(a) * f32(flow_k * h)
                self.vy += np.sin(a) * f32(flow_k * h)
            if gy:
                self.vy += f32(gy * h)
            if drag:
                k = f32(math.exp(-drag * h))
                self.vx *= k
                self.vy *= k
            np.clip(self.vx, -V_MAX, V_MAX, out=self.vx)
            np.clip(self.vy, -V_MAX, V_MAX, out=self.vy)
            self.x += self.vx * f32(h)
            self.y += self.vy * f32(h)
        if wrap:
            np.mod(self.x, self.w, out=self.x)
            np.mod(self.y, self.h, out=self.y)
        return kill

    def out_of_bounds(self, margin):
        return ((self.x < -margin) | (self.x > self.w + margin) |
                (self.y < -margin) | (self.y > self.h + margin))

    # --------------------------------------------------------------- update ---
    def update(self, dt, mx, my, lmb=False, rmb=False):
        dt = min(dt, 1 / 30)
        self.t += dt
        self._update_rings(dt)
        m = self.mode
        if m == GAME:
            return self._update_game(dt, mx, my, lmb, rmb)

        s = 2.2e6 * self.strength
        wells = []
        if m == GALAXY:
            wells.append((self.cx, self.cy, GM, 16))
        for wl in self.user_wells:
            wells.append((wl[0], wl[1], wl[2], 12))

        if m == FIREWORKS:
            self._update_fireworks(dt, mx, my, lmb)
            return

        if lmb:
            wells.append((mx, my, s, 0))
        if rmb:
            wells.append((mx, my, -1.2 * s, 0))

        if m == GALAXY:
            kill = self.integrate(dt, wells, drag=0.03)
            self.respawn(np.flatnonzero(kill | self.out_of_bounds(320)))
        elif m == WELLS:
            kill = self.integrate(dt, wells, drag=0.0)
            self.respawn(np.flatnonzero(kill | self.out_of_bounds(120)))
        elif m == FLOW:
            for rg in self.rings:                      # SPACE shockwave pushes the flow outward
                dx = self.x - rg[0]
                dy = self.y - rg[1]
                d = np.hypot(dx, dy) + 1e-3
                push = np.exp(-((d - rg[2]) / 35.0) ** 2) * (rg[3] * 900 * dt)
                self.vx += dx / d * push
                self.vy += dy / d * push
            self.integrate(dt, wells, drag=1.6, flow_k=260, wrap=True)
            # recycle a few particles every frame so the field never clumps into empty space
            self.respawn(self.rng.integers(0, self.n, self.n // 90))

    # ---------------------------------------------------------- fireworks ---
    def burst(self, x, y, count=700, hue=None, power=260.0, ring=False):
        dead = np.flatnonzero(self.life <= 0)
        if len(dead) == 0:
            return
        idx = dead[:min(count, len(dead))]
        k = len(idx)
        r = self.rng
        if hue is None:
            hue = r.random()
        a = r.random(k) * 2 * math.pi
        sp = power * (0.88 + 0.12 * r.random(k)) if ring else power * np.sqrt(r.random(k))
        self.x[idx], self.y[idx] = x, y
        self.vx[idx] = np.cos(a) * sp
        self.vy[idx] = np.sin(a) * sp
        self.life[idx] = 1.0
        self.decay[idx] = 1.0 / (1.1 + 1.3 * r.random(k))
        self.hue[idx] = hue + r.normal(0, 0.035, k)

    def _update_fireworks(self, dt, mx, my, lmb):
        self.firework_timer -= dt
        if self.firework_timer <= 0:
            r = self.rng
            self.firework_timer = 0.55 + 0.7 * r.random()
            self.burst(self.w * (0.15 + 0.7 * r.random()), self.h * (0.15 + 0.4 * r.random()),
                       count=int(600 + 500 * r.random()), power=230 + 90 * r.random(),
                       ring=bool(r.random() < 0.35))
        if lmb:                                              # paint with sparks
            self.burst(mx, my, count=70, hue=(self.t * 0.25) % 1.0, power=120)
        self.integrate(dt, [], drag=0.9, gy=170)
        self.life -= self.decay * np.float32(dt)
        np.maximum(self.life, 0, out=self.life)

    # --------------------------------------------------------------- actions ---
    def action(self, mx, my):
        """SPACE key: does something different in every mode."""
        if self.mode in (GALAXY, WELLS):
            if len(self.user_wells) >= 8:
                self.user_wells.pop(0)
            self.user_wells.append([mx, my, 2.4e6])
        elif self.mode == FIREWORKS:
            self.burst(mx, my, count=1400, power=330, ring=True)
        elif self.mode == FLOW:
            self.rings.append([mx, my, 0.0, 1.0, 0.5])

    def clear_wells(self):
        if self.mode == WELLS:
            self.user_wells = []
        elif self.mode == GALAXY:
            self.user_wells = []

    # ---------------------------------------------------------------- rings ---
    def _update_rings(self, dt):
        for rg in self.rings:
            rg[2] += 420 * dt        # radius grows
            rg[3] -= dt * 1.4        # life drains
        self.rings = [rg for rg in self.rings if rg[3] > 0]

    # ------------------------------------------------------------------ game ---
    def start_game(self):
        self.mode = GAME
        self.user_wells = []
        self.rings = []
        self.state = "play"
        self.score = 0
        self.combo = 0
        self.timeleft = 45.0
        self.game_t = 0.0
        self.last_collect = -99.0
        self.orbs = []
        self.voids = []
        self.seed_all()
        r = self.rng
        for i in range(2):
            self._spawn_void()
        for i in range(2):
            self._spawn_orb()

    def _spawn_void(self):
        r = self.rng
        a = r.random() * 2 * math.pi
        sp = 55 + 55 * r.random()
        self.voids.append({"x": r.uniform(150, self.w - 150), "y": r.uniform(150, self.h - 150),
                           "vx": math.cos(a) * sp, "vy": math.sin(a) * sp, "r": 46.0})

    def _spawn_orb(self):
        r = self.rng
        x = y = 0
        for _ in range(40):
            x, y = r.uniform(110, self.w - 110), r.uniform(110, self.h - 110)
            ok = all(math.hypot(x - v["x"], y - v["y"]) > v["r"] + 110 for v in self.voids)
            ok = ok and all(math.hypot(x - o["x"], y - o["y"]) > 220 for o in self.orbs)
            if ok:
                break
        self.orbs.append({"x": x, "y": y, "r": 40.0, "charge": 0.0, "age": 0.0})

    def _update_game(self, dt, mx, my, lmb, rmb):
        playing = self.state == "play"
        if playing:
            self.game_t += dt
            self.timeleft -= dt
            want_voids = 2 + min(2, int(self.game_t // 18))
            while len(self.voids) < want_voids:
                self._spawn_void()
            if self.timeleft <= 0:
                self.timeleft = 0.0
                self.state = "over"
                self.best = max(self.best, self.score)
                self.events.append(("over",))

        # voids drift around and bounce off the walls
        for v in self.voids:
            v["x"] += v["vx"] * dt
            v["y"] += v["vy"] * dt
            if v["x"] < v["r"] or v["x"] > self.w - v["r"]:
                v["vx"] *= -1
                v["x"] = min(max(v["x"], v["r"]), self.w - v["r"])
            if v["y"] < v["r"] or v["y"] > self.h - v["r"]:
                v["vy"] *= -1
                v["y"] = min(max(v["y"], v["r"]), self.h - v["r"])

        # forces: cursor magnet (gentle by default, strong while LMB, repel on RMB)
        wells = []
        if rmb:
            wells.append((mx, my, -3.0e6, 0))
        else:
            wells.append((mx, my, 2.6e6 if lmb else 1.0e6, 0))
        for v in self.voids:
            wells.append((v["x"], v["y"], -2.4e6, v["r"] * 0.55))
        kill = self.integrate(dt, wells, drag=1.1, flow_k=90, wrap=True)
        self.respawn(np.flatnonzero(kill))     # swarm members lost to a void come back at random

        if not playing:
            return

        # charge the orbs with however many particles are inside them
        ref = 0.02 * self.n
        for o in list(self.orbs):
            o["age"] += dt
            d2 = (self.x - o["x"]) ** 2 + (self.y - o["y"]) ** 2
            inside = int(np.count_nonzero(d2 < o["r"] ** 2))
            o["charge"] = max(0.0, o["charge"] + (inside / ref) * dt * 0.9 - 0.12 * dt)
            if o["charge"] >= 1.0:
                self.orbs.remove(o)
                if self.game_t - self.last_collect < 5.0:
                    self.combo += 1
                else:
                    self.combo = 1
                self.last_collect = self.game_t
                self.score += 100 * self.combo
                self.timeleft += 3.0
                self.rings.append([o["x"], o["y"], 0.0, 1.0, 1.0])
                self.events.append(("collect", self.combo))
                self._spawn_orb()
            elif o["age"] > 15.0:             # too slow: the orb fizzles out
                self.orbs.remove(o)
                self.combo = 0
                self.events.append(("miss",))
                self._spawn_orb()

    # ------------------------------------------------------------- drawing ---
    def particle_pixels(self):
        """Return (ix, iy, rgb) for every visible particle - used by main.py."""
        gain = GAIN[self.mode]
        if self.mode == FIREWORKS:
            alive = self.life > 0
            x, y = self.x[alive], self.y[alive]
            idx = ((0.18 + 0.82 * (self.hue[alive] % 1.0)) * 255).astype(np.int32)
            bright = self.life[alive] ** 0.6
            col = self.lut[idx] * (bright[:, None] * gain * 1.5)
        else:
            x, y = self.x, self.y
            sp = np.hypot(self.vx, self.vy)
            idx = np.clip(sp * SPEED_COLOUR_SCALE[self.mode], 0, 255).astype(np.int32)
            col = self.lut[idx] * gain
        ix = x.astype(np.int32)
        iy = y.astype(np.int32)
        ok = (ix >= 0) & (ix < self.w) & (iy >= 0) & (iy < self.h)
        return ix[ok], iy[ok], col[ok].astype(np.int16)
