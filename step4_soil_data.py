"""
STEP 4 — SoilGrids Soil Data

Gets SoilGrids 0-5 cm mean values for:
    clay
    sand
    silt
    bdod
    soc
    phh2o

Uses official SoilGrids WCS.
"""

import os
import tempfile
import requests
import pandas as pd
import rasterio

from pyproj import Transformer


# =========================================================
# SETTINGS
# =========================================================

SOIL_PROPERTIES = [
    "clay",
    "sand",
    "silt",
    "bdod",
    "soc",
    "phh2o"
]

# SoilGrids WCS projection
# SoilGrids Homolosine projection
# SoilGrids uses this custom SRS internally.
SOILGRIDS_PROJ = (
    "+proj=igh "
    "+lat_0=0 "
    "+lon_0=0 "
    "+datum=WGS84 "
    "+units=m "
    "+no_defs"
)

SOILGRIDS_CRS_URL = (
    "http://www.opengis.net/def/crs/EPSG/0/152160"
)

transformer = Transformer.from_crs(
    "EPSG:4326",
    SOILGRIDS_PROJ,
    always_xy=True
)



# =========================================================
# VALUE CONVERSION
# =========================================================

def convert_value(property_name, raw_value):

    if raw_value is None:
        return None

    value = float(raw_value)

    # SoilGrids stores these as g/kg
    # Convert to percentage
    if property_name in ["clay", "sand", "silt"]:
        return value / 10.0

    # cg/cm3 -> g/cm3
    elif property_name == "bdod":
        return value / 100.0

    # dg/kg -> g/kg
    elif property_name == "soc":
        return value / 10.0

    # pH x 10 -> pH
    elif property_name == "phh2o":
        return value / 10.0

    return value


# =========================================================
# GET ONE SOIL PROPERTY
# =========================================================

def get_property_wcs(lat, lon, property_name):

    # -----------------------------------------------------
    # Convert lat/lon -> SoilGrids projection
    # -----------------------------------------------------

    x, y = transformer.transform(lon, lat)

    print(f"[soil] SoilGrids coordinates: X={x:.2f}, Y={y:.2f}")

    # -----------------------------------------------------
    # Small 250 m area
    # -----------------------------------------------------

    half_size = 125

    xmin = x - half_size
    xmax = x + half_size

    ymin = y - half_size
    ymax = y + half_size

    # -----------------------------------------------------
    # Coverage
    # -----------------------------------------------------

    coverage_id = (
        f"{property_name}_0-5cm_mean"
    )

    wcs_url = (
        f"https://maps.isric.org/mapserv"
        f"?map=/map/{property_name}.map"
    )

    params = [
        ("SERVICE", "WCS"),
        ("VERSION", "2.0.1"),
        ("REQUEST", "GetCoverage"),
        ("COVERAGEID", coverage_id),
        ("FORMAT", "GEOTIFF_INT16"),

        # IMPORTANT:
        # Two SUBSET parameters
        ("SUBSET", f"X({xmin},{xmax})"),
        ("SUBSET", f"Y({ymin},{ymax})"),

        ("SUBSETTINGCRS", SOILGRIDS_CRS_URL),
        ("OUTPUTCRS", SOILGRIDS_CRS_URL),
    ]

    print(f"[soil] WCS request: {property_name}")

    response = requests.get(
        wcs_url,
        params=params,
        timeout=60
    )

    # -----------------------------------------------------
    # If server returns an error
    # -----------------------------------------------------

    if response.status_code != 200:

        print(
            f"[soil] Server response "
            f"{response.status_code}"
        )

        print(response.text[:1000])

        raise RuntimeError(
            f"WCS request failed for {property_name}"
        )

    # -----------------------------------------------------
    # Check XML error
    # -----------------------------------------------------

    content_type = response.headers.get(
        "Content-Type",
        ""
    )

    if (
        "xml" in content_type.lower()
        or response.content.startswith(b"<?xml")
    ):

        print(response.text[:1000])

        raise RuntimeError(
            f"SoilGrids returned XML error "
            f"for {property_name}"
        )

    # -----------------------------------------------------
    # Save temporary TIFF
    # -----------------------------------------------------

    temp_path = None

    try:

        with tempfile.NamedTemporaryFile(
            suffix=".tif",
            delete=False
        ) as temp_file:

            temp_file.write(response.content)
            temp_path = temp_file.name

        # -------------------------------------------------
        # Read TIFF
        # -------------------------------------------------

        with rasterio.open(temp_path) as src:

            array = src.read(1)

            print(
                f"[soil] Raster size: "
                f"{array.shape}"
            )

            # Find center pixel
            row = array.shape[0] // 2
            col = array.shape[1] // 2

            raw_value = array[row, col]

            # NoData check
            if src.nodata is not None:

                if raw_value == src.nodata:

                    return None

            value = convert_value(
                property_name,
                raw_value
            )

            return value

    finally:

        if temp_path and os.path.exists(temp_path):

            os.remove(temp_path)


# =========================================================
# MAIN SOIL FUNCTION
# =========================================================

def get_soil_data(lat, lon):

    print(
        f"[soil] Using SoilGrids WCS "
        f"for ({lat}, {lon})..."
    )

    result = {
        "lat": lat,
        "lon": lon
    }

    for property_name in SOIL_PROPERTIES:

        try:

            value = get_property_wcs(
                lat,
                lon,
                property_name
            )

            result[property_name] = value

            print(
                f"[soil] {property_name}: "
                f"{value}"
            )

        except Exception as e:

            print(
                f"[soil] WCS failed for "
                f"{property_name}: {e}"
            )

            result[property_name] = None

    return result


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    print("================================")
    print("SOILGRIDS TEST")
    print("================================")

    lat = 27.33
    lon = 88.61

    soil = get_soil_data(
        lat,
        lon
    )

    print("\nFinal Soil Data:")

    for key, value in soil.items():

        print(
            f"{key}: {value}"
        )

    df = pd.DataFrame([soil])

    df.to_csv(
        "soil_properties.csv",
        index=False
    )

    print(
        "\nSaved -> soil_properties.csv"
    )