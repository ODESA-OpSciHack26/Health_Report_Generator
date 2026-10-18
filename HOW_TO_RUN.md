# How to run the report generator (beginner guide)

This guide starts a small web page where you choose **who the report is for**
and **which years**, then press a button to get a report. Everything runs
inside Docker, so you do not install Python, R or Quarto yourself.

## What you need

| Item | Notes |
|---|---|
| Windows 11 with WSL2 | Docker Desktop uses it |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Must be running |
| [VS Code](https://code.visualstudio.com/) | Optional, but this guide uses its terminal |
| Internet | Only for the first build |
| About 10 GB free disk | The image is about 4.3 GB |

## First time only

### 1. Start Docker Desktop
Open **Docker Desktop** from the Start menu. Wait until it says
**"Engine running"** (1-2 minutes).

### 2. Open the project in VS Code
**File -> Open Folder...** and choose the project folder
(`Health_Report_Generator`).

### 3. Open a terminal
Press **Ctrl+`** (the key above Tab). PowerShell is fine.

### 4. Check that Docker works
```
docker info
```
If it prints details (warnings about "blkio" or "cgroup" can be ignored), go on.
If it says `failed to connect to the docker API`, Docker Desktop is not running yet.

### 5. Set two variables
These are needed in every new terminal window.

PowerShell:
```
$env:LOCAL_UID=1000; $env:LOCAL_GID=1000
```
Git Bash:
```
export LOCAL_UID=1000 LOCAL_GID=1000
```

### 6. Build the image
```
docker compose build app
```
This takes a long time the first time (15-30 minutes) because it installs R,
Quarto, TinyTeX and Python packages. Wait until you get the prompt back with
no red error. You only do this once.

## Every time you want to use it

### 1. Start Docker Desktop and wait for "Engine running"

### 2. Start the page
In the VS Code terminal (with the variables from step 5 set):
```
docker compose up app
```
Wait for this line, and leave the terminal open:
```
You can now view your Streamlit app in your browser.
```

### 3. Open the page
Open **http://localhost:8501** in your browser, or inside VS Code:
**Ctrl+Shift+P -> Simple Browser: Show -> http://localhost:8501**.

### 4. Make a report
The page has two tabs.

**Quarto report** (first tab): the full data reports, one HTML file each.
1. **Which report?**
   - *Researcher*: coverage, quality checks, methods and provenance.
   - *Public health officials*: what needs attention now, and where.
2. **Which diseases?** All are picked at first. Remove the ones you do not want
   (click the x), or add them back. The report lists diseases in the order you pick them.
3. Click **Generate report** and wait (about 1-2 minutes; the same choice again is instant).
4. Click **Open report in new tab**, or **Download report** / **Download provenance**.

Reports are saved in `results/app/quarto/`. Each is one self-contained file: it works
offline, and you can email it or put it online.

**Audience report (R)** (second tab):
1. **Who is the report for?**
   - *General public*: plain language, with a "How sure can we be?" section.
   - *Health institution*: monitoring brief with the biggest changes.
   - *Researcher*: technical, with methods and quality checks.
2. **Which years?** `2021 to 2025` or `2022 to 2025`.
3. Click **Generate report** and wait.
   - First time for a choice: about 1-2 minutes.
   - Same choice again: a few seconds (it is reused from the cache).
4. Read the report on the page, or click **Download report** / **Download methods**.

The report is shown inside the page. Click **Open in new tab** to see it full size;
the links inside it (Methods, provenance, data files) work. This uses a second
port, **8502**, which the page opens automatically.

Reports are also saved on your computer in `results/app/<audience>_<years>/`
(`report.html`, `methods.html`, `provenance.json`).

The page builds one report at a time. If you see "Another report is being
created", wait a minute and try again.

### 5. Stop it
Click the terminal and press **Ctrl+C**, then run:
```
docker compose down
```

## Useful commands

| Goal | Command |
|---|---|
| Run in the background | `docker compose up -d app` |
| See the log | `docker compose logs -f app` |
| Stop the background run | `docker compose down` |
| Build the 3 standard reports (no web page) | `docker compose run --rm report snakemake --cores 2` |
| Build the 2 Quarto reports, all diseases (no web page) | `docker compose run --rm report snakemake --cores 2 quarto` (written to `results/site/`) |
| Run the tests | `docker compose run --rm report python -m pytest -q` |
| Rebuild after changing `Dockerfile.report` | `docker compose build app` |

Editing `src/app.py` does not need a rebuild: the project folder is shared
with the container, so just refresh the browser page.

The standard build writes `results/reports/<audience>/report.html`
(see [README.md](README.md)).

## If something goes wrong

| Problem | Fix |
|---|---|
| `failed to connect to the docker API` | Docker Desktop is not running. Start it and wait for "Engine running". |
| Docker Desktop stuck on "Starting" | Run `wsl --update`, then `wsl --shutdown`, then start Docker Desktop again. Make sure virtualization is on in BIOS and "Use the WSL 2 based engine" is ticked in Docker settings. |
| Build fails with `set: pipefail: invalid option name` | A `.sh` file has Windows line endings. This repo's `.gitattributes` prevents it. If it still happens, run `git add --renormalize .` and rebuild. |
| Build fails at the Streamlit step | Copy the red error text and ask for help. The pinned version is in `Dockerfile.report`. |
| Port 8501 or 8502 already in use | In `compose.yaml` change the left number of `"8501:8501"` (page) or `"8502:8502"` (report viewer; also change `VIEWER_PORT` in `src/app.py`). |
| Permission errors writing to `results/` | Run step 5 (the two variables) first. |
| `Invalid request: ...` on the page | The choice was not supported. Pick one of the listed years. |
| "The report could not be built" | Run `docker compose logs app` and read the last lines. |

## Good to know

- The page has **no login**. Run it only on your own computer or a trusted network.
- It uses the data already stored in `data/reference/`. It does not download new data.
- Reports describe officially notified cases only, for Switzerland and
  Liechtenstein as a whole. See [docs/limitations.md](docs/limitations.md).
- Data source: Federal Office of Public Health (FOPH/BAG), Infectious Diseases Dashboard.

## What happens when you press the button (short version)

```
your choice -> web_request.py (checks it) -> custom_report.py
   -> same data + same settings seen before?  yes -> reuse stored report
                                              no  -> build it (Snakemake + Quarto)
   -> report.html shown on the page
```
