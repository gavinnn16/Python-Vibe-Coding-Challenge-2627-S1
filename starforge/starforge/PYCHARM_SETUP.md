# Running STARFORGE in PyCharm (step by step)

Works on Windows, Mac and Linux. Plan for about 5 minutes the first time.

## Before you start
- You need **Python 3.10 to 3.13** (3.12 is the safest). If you only have a very new Python (3.14), the libraries may fail to install; step 3 shows how to switch.
- **Unzip the project first** (right-click the zip, *Extract All*). Never open files from inside the zip preview.

## Step 1: Open the correct folder
1. Start PyCharm.
2. Click **File > Open**.
3. Choose the folder that **directly contains** `main.py`, `sim.py` and `requirements.txt`.
   - If you only see another folder called `starforge` inside, open that inner one instead.
4. Click **OK**, then **Trust Project** if asked.

Check: the file list on the left should show `main.py` and `sim.py` at the top level, not inside a sub-folder.

## Step 2: Create the Python environment
1. Click **File > Settings** (Mac: **PyCharm > Settings**).
2. Go to **Project: starforge > Python Interpreter**.
3. Click **Add Interpreter > Add Local Interpreter**.
4. Choose **Virtualenv Environment**, select **New**, and for *Base interpreter* pick **Python 3.12** (or any 3.10 - 3.13).
5. Click **OK** twice.

Check: the bottom-right corner of PyCharm should show something like `Python 3.12 (starforge)`.

## Step 3: Install the libraries
1. Open the **Terminal** tab at the bottom of PyCharm.
2. Make sure the prompt begins with `(.venv)` and ends in the folder that contains `main.py`.
3. Type this **once** and press Enter **once**:
   ```
   pip install -r requirements.txt
   ```
4. Wait until you see `Successfully installed ...`.

If it says it cannot find `requirements.txt`, you are in the wrong folder. Use `cd` to move into the folder that contains `main.py`, or redo Step 1 with the inner folder.

Alternative that works from any folder:
```
pip install pygame-ce numpy
```

**If the install fails with a long "wheel" or "build" error:** your base Python is too new. Install **Python 3.12** from python.org (tick *Add python.exe to PATH*), then redo Step 2 and choose 3.12 as the base interpreter. Do not install plain `pygame`; use `pygame-ce` (already listed in `requirements.txt`).

## Step 4: Run the project
Right-click **`main.py`** in the file list and choose **Run 'main'**, or open `main.py` and click the green triangle at the top right.

The STARFORGE window opens. Keys: `1-4` modes, `G` game, `C` colours, `B` glow, `T` trails, `H` hide help, `ESC` quit.

## Optional: start in a specific mode
1. Click the run configuration dropdown (top right, says `main`) and choose **Edit Configurations**.
2. In **Parameters**, type one of:
   - `--game` (start in ORB RUSH)
   - `--mode flow` (also `galaxy`, `fireworks`, `wells`)
3. Click **OK**, then run.

## Troubleshooting
| What you see | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'pygame'` | Libraries went into a different interpreter. Check the bottom-right shows the project's `.venv`, then run `pip install -r requirements.txt` in the PyCharm Terminal again. |
| `can't open file '...main.py'` | The Terminal or project is in the wrong folder. Open the folder that contains `main.py` (Step 1). |
| `Could not open requirements file` | Same cause, wrong folder. Or the command was pasted twice; type it once. |
| Build error mentioning `SDL2` or `wheel` | Base Python is too new or you installed `pygame` instead of `pygame-ce`. Use Python 3.12 and `pip install pygame-ce numpy`. |
| Window is slow | Press `B` to reduce the glow and `T` for shorter trails. |
| No sound | Sound is optional. The game still works. |
