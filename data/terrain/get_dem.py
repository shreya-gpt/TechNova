#"If you ever need to re-run get_dem.py for a different area, you'll need your own OpenTopography API key in a .env file — see the script for the variable name."
from dotenv import load_dotenv
load_dotenv()

import requests
import os

south, north = 27.20, 27.45
west, east = 92.30, 92.55

url = "https://portal.opentopography.org/API/globaldem"
params = {
    "demtype": "SRTMGL1",
    "south": south,
    "north": north,
    "west": west,
    "east": east,
    "outputFormat": "GTiff",
    "API_Key": os.environ.get("OPENTOPO_API_KEY")  # Use the API key from environment variables
}

script_dir = os.path.dirname(os.path.abspath(__file__))
output_path = os.path.join(script_dir, "dem.tif")

resp = requests.get(url, params=params)

if resp.status_code == 200 and resp.content[:2] in (b"II", b"MM"):
    # II or MM at the start = valid TIFF file signature
    with open(output_path, "wb") as f:
        f.write(resp.content)
    print("Saved DEM:", output_path, "-", os.path.getsize(output_path), "bytes")
else:
    print("Request failed:", resp.status_code, resp.text[:300])