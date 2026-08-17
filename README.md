# Prepit XML Builder

Watches a Fiery Prep-it XML export file, extracts job and media details, and writes a simplified `NESTINGDESCRIPTIONFILE` XML for downstream use.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Review `.env` and update the folder paths if needed.

## Run

```powershell
python PrepitXMLBuilder.py
```

## Run from Task Scheduler

1. Create the batch wrapper file in the project root:

```bat
@echo off
cd /d C:\PrepitXMLBuilder
C:\PrepitXMLBuilder\.venv\Scripts\python.exe C:\PrepitXMLBuilder\PrepitXMLBuilder.py
```

2. Open Task Scheduler and create a new task.
3. General:
   - Name: `PrepitXMLBuilder Startup`
   - Select `Run whether user is logged on or not`
   - Check `Run with highest privileges`
4. Trigger:
   - New -> `At startup`
5. Action:
   - Start a program
   - Program/script: `C:\PrepitXMLBuilder\run_prepit.bat`
   - Start in: `C:\PrepitXMLBuilder`
6. Conditions:
   - Uncheck `Start the task only if the computer is on AC power` if needed.
7. Settings:
   - Check `Allow task to be run on demand`
   - Optional: `If the task fails, restart every: 1 minute`, up to 3 times.

Test the task manually first, then reboot to verify it starts automatically.

## Environment Variables

- `FOLDER_TO_MONITOR`: Folder containing the source XML file.
- `CUT_QUEUE_FOLDER`: Folder used to look up matching cut queue XML files.
- `OUT_FOLDER`: Folder containing per-job XML metadata files.
- `SAVE_FOLDER`: Destination folder for generated XML output.
- `SPECIFIC_FILE`: Name of the source file to watch.
- `POLL_INTERVAL_SECONDS`: Sleep interval for the watcher loop.

## GitHub Notes

- `.env` is ignored so local machine paths stay out of source control.
- `.env.example` is included so another machine can be configured quickly.
- `requirements.txt` pins the runtime dependencies needed by the watcher.

Change added  