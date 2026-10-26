import os
import tempfile
from pathlib import Path

# Defensive fallback for environments where TEMP/TMP points to an invalid or unmounted drive
try:
    current_temp = Path(tempfile.gettempdir())
    if not current_temp.exists():
        fallback_temp = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "Temp"
        fallback_temp.mkdir(parents=True, exist_ok=True)
        os.environ["TEMP"] = str(fallback_temp)
        os.environ["TMP"] = str(fallback_temp)
        tempfile.tempdir = str(fallback_temp)
except Exception:
    pass
