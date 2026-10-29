# STARFORGE

**Project Name:** STARFORGE: a living particle universe

**Project Description:**
STARFORGE is an interactive simulation where 26,000 glowing particles obey real
(simplified) physics and you control them with your mouse. It has four sandbox
art modes plus a complete arcade game:

| Key | Mode | What it is |
|-----|------|------------|
| `1` | **Galaxy** | A spiral galaxy orbiting a central black hole. Drop extra black holes with `SPACE`. |
| `2` | **Flow Field** | Particles ride an animated vector field and paint silk-like ribbons. `SPACE` sends a shockwave. |
| `3` | **Fireworks** | Click for bursts, hold to paint with sparks, `SPACE` for ring bursts. |
| `4` | **Gravity Wells** | Particles slingshot between gravity wells, creating chaotic orbit art. |
| `G` | **ORB RUSH (game)** | Steer the swarm into glowing orbs to charge them, dodge the red voids, chain combos, and beat the 45-second clock (time is added for every orb). High score is saved. |

Other keys: `C` colour palettes, `T` trail length, `B` bloom (glow), `P` pause,
`S` screenshot, `F11` fullscreen, `H` hide help, mouse wheel = mouse strength, `ESC` quit.

**Python Libraries Used:**
- `pygame-ce` (the community edition of pygame, same `import pygame`): window, input, drawing, and the glow/bloom compositing
- `numpy`: the whole physics engine is vectorised (all 26,000 particles update in one operation), plus procedurally generated sound effects (no audio files)
- Standard library: `math`, `json`, `argparse`, `os`, `time`

**GitHub Repository / Project Link:** (add your link here)

**Instructions for Running the Project:**

*Requirements:* Windows, Mac or Linux with **Python 3.10 - 3.13** (3.12 recommended), a keyboard and a mouse. No webcam, GPU or internet connection is needed after setup.

**Easiest way (Windows):**
1. **Unzip the whole folder first.** Right-click the zip, choose *Extract All*. Do not run files from inside the zip preview.
2. Open the extracted folder. You should see `main.py`, `sim.py` and `run.bat` side by side.
3. Double-click **`run.bat`**. The first run installs everything automatically (about a minute); later runs start instantly.

**Mac / Linux:** open a terminal in the folder and run `bash run.sh`.

**Manual way (any system):** open a terminal *in the folder that contains `main.py`* and run:
```
python -m venv .venv
.venv\Scripts\activate          (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python main.py
```

**PyCharm:** see the step-by-step guide in `PYCHARM_SETUP.md`.

**Troubleshooting**
| Problem | Fix |
|---|---|
| `Python was not found` | Install Python 3.12 from python.org and tick **Add python.exe to PATH**. |
| pygame fails to build / "wheel" error | You are probably on a very new Python (3.14). Install Python 3.12 and try again. |
| `can't open file main.py` | The terminal is in the wrong folder. Use `cd` into the folder that contains `main.py`. |
| Runs slowly | Press `B` to lower the glow, and `T` for shorter trails. |
| No sound | Sound is optional; the game still works. |

Optional start-up options: `python main.py --mode flow`, `python main.py --game`, `python main.py --seed 42`

## How it works (for your explanation)
- **Structure-of-arrays + NumPy:** each particle is one index in arrays `x, y, vx, vy`.
  `vx += dx * f * dt` updates all of them at once in C, which is why Python can handle 26k particles at 60 FPS.
- **Gravity model:** acceleration `a = s * d / (|d|^2 + soft)^1.5` (inverse-square with softening so it never divides by zero).
  A negative strength becomes repulsion. Orbits use `v = sqrt(GM / r)` for the circular-orbit speed.
- **Numerical stability:** two physics sub-steps per frame and a speed limit.
- **Flow field:** an animated sum of sine waves gives an angle at every point; particles steer along it.
- **Rendering:** particles are written straight into the pixel array with additive blending; the screen fades slightly each frame to make trails; a blurred, down-scaled copy is added back on top to create bloom (glow).
- **Colour:** each particle's speed is mapped through a 256-colour lookup table built by interpolating palette stops.
- **Game rules:** orbs charge based on how many particles are inside them (`np.count_nonzero`), voids repel and destroy particles, combos reward quick chains, and orbs expire if you take too long.
- **Architecture:** `sim.py` (physics + game rules, no graphics) and `main.py` (drawing + input + sound). This separation made the simulation testable on its own.

## Suggested 60-second demo
1. Start in Galaxy: hold the mouse to pull the spiral apart, press `SPACE` to add black holes.
2. Press `2` and `3` to show Flow Field and Fireworks, cycling `C` for palettes.
3. Press `G` to play ORB RUSH and let a classmate try to beat your score.
