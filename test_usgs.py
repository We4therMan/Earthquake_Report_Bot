import requests

URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"


def latest_earthquake():
    data = requests.get(URL).json()

    quake = data["features"][0]

    props = quake["properties"]

    geom = quake["geometry"]["coordinates"]

    return {
        "id": quake["id"],
        "mag": props["mag"],
        "place": props["place"],
        "url": props["url"],
        "time": props["time"],
        "lon": geom[0],
        "lat": geom[1],
        "depth": geom[2],
    }