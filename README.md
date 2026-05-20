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
