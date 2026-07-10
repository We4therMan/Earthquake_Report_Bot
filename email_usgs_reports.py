"""Yair Franco, 2026"""

import geopandas as gpd
import requests
from datetime import datetime, UTC
from zoneinfo import ZoneInfo
from shapely.geometry import Polygon, Point, shape
from collections import Counter
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import textwrap
import numpy as np
import time

"""
Algorithm condenses long lists of counties if they exceed a 
certain amount of characters to make space for the box (NHK style).

These regions are chosen arbitrarily by me but I'm going 
by what's generally used by locals/on the internet,
basing mainly off definitions in Wikipedia... and
some personal bias because I'm also from California.

Regions defined for Nevada would probably rarely be used, 
except for Western Nevada because most NV earthquakes occur there.
The rest of NV regions have large counties, and don't usually
have very large earthquakes that would require condensing the list.
Therefore, they are not defined.

There is a Humboldt County in both states. Due to distance
these would most likely never get an EEW at the same time. 
The NV one is not defined in a region for the reasons above.

Some blank strings are added so the threshold for condensing
a region doesn't get triggered at 1 or 2 counties in regions with few 
(e.g North Coast).
Threshold is (n of counties) - 3
"""

regions = {
    # ---- Northern California ----
    # Del Norte, Humboldt, Lake, Mendocino
    # "North Coast": ['015', '023', '033', '045'],
    "North Coast": ['Del Norte', 'Humboldt', 'Lake', 'Mendocino','',''],

    # Butte, Lassen, Modoc, Plumas, Shasta, Siskiyou, Tehama, Trinity
    # "The Cascades": ['007','035','049','063','089','103','105'],
    "The Cascades": ['Butte', 'Lassen', 'Modoc', 'Plumas', 'Shasta', 'Siskiyou', 'Tehama', 'Trinity'],

    # Plumas, Sierra, Nevada, Placer, Yuba, El Dorado, Amador, Alpine, Calaveras, Tuolumne, Mariposa, Mono, Madera, Tulare, Inyo
    # "Sierra Nevada": ['063', '091','057','061','115','017','005','003','009','109','043','051','039','107','027'],
    "Sierra Nevada": [
        'Plumas', 'Sierra', 'Nevada', 'Placer', 'Yuba', 'El Dorado', 'Amador', 
        'Alpine', 'Calaveras', 'Tuolumne', 'Mariposa', 'Mono', 'Madera', 'Tulare', 'Inyo'
        ],

    # Butte, Colusa, Glenn, Placer, Sacramento, Shasta, Sutter, Tehama, Yolo, Yuba
    # "Sacramento Valley": ['007','011','021','061','067','089','101','103','113','115'],
    "Sacramento Valley": [
        'Butte', 'Colusa', 'Glenn', 'Placer', 'Sacramento', 
        'Shasta', 'Sutter', 'Tehama', 'Yolo', 'Yuba'
        ],

    # San Joaquin, Kings, Stanislaus, Merced, Fresno, Madera, Tulare, Kern
    # "San Joaquin Valley": ['077','031','099','047','019','039','107','029'],
    "San Joaquin Valley": ['San Joaquin', 'Kings', 'Stanislaus', 'Merced', 'Fresno', 'Madera', 'Tulare', 'Kern'],

    # Alameda, Contra Costa, Marin, Napa, San Mateo, Santa Clara, Solano, Sonoma, San Francisco, Santa Cruz
    # "Bay Area": ['001','013','041','055','081','085','095','097','075','087'],
    "Bay Area": [
        'Alameda', 'Contra Costa', 'Marin', 'Napa', 'San Mateo', 
        'Santa Clara', 'Solano', 'Sonoma', 'San Francisco', 'Santa Cruz'
        ],

    # ---- Southern California ----
    # Santa Barbara, San Luis Obispo, Monterey, San Benito, Santa Cruz
    # "Central Coast": ['083','079','053','069','087'],
    "Central Coast": ['Santa Barbara', 'San Luis Obispo', 'Monterey', 'San Benito', 'Santa Cruz'],

    # Ventura, Los Angeles, Orange, Riverside, San Bernardino
    # "Greater LA Metro": ['111','037','059','065','071'],
    "Greater LA Metro": ['Ventura', 'Los Angeles', 'Orange', 'Riverside', 'San Bernardino', '', ''],

    #Inyo, San Bernardino, Riverside, Imperial
    # "Southeastern CA": ['027','071','065','025'],
    "Southeastern CA": ['Inyo', 'San Bernardino','Riverside', 'Imperial', '', ''],


    # ---- Nevada ----
    # Washoe, Carson City, Douglas, Storey, Lyon
    # "Western NV": ['031','510','005','029','019'],
    "Western NV": ['Washoe', 'Carson City', 'Douglas', 'Storey', 'Lyon'],
}

def mmi_style(mmi,to_shindo=False):
    """Manages shaking-related language depending on the measured intensity of the earthquake."""
    if mmi == 0: mmi = 1
    if mmi > 10: mmi = 10
    
    box_colors = ['white','lightblue','cyan','blue','green','yellow','orange','darkorange','red','darkred']
    txt_colors = ['k',    'k',    'k',       'w',   'w',    'k',      'k',     'k',        'w',  'y']
    weights =    [400,     400,    400,       400,   400,    400,      400,     600,       700,   800]
    MMI_ticks =  ['I',    'II',   'III',     'IV',  'V',    'VI',     'VII',   'VIII',     'IX',  'X']
    shindo =     ['0',     '1',    '2',       '3',   '4',   '5-',     '5+',    '6-',       '6+',  '7']
    descriptions = [
        'Not felt',
        'Weak',
        'Very light',
        'Light',
        'Moderate',
        'Strong',
        'Very strong',
        'Severe',
        'Violent',
        'Extreme'
    ]

    box_color = box_colors[mmi-1]
    txt_color = txt_colors[mmi-1]
    fnt_weight = weights[mmi-1]
    numeral = MMI_ticks[mmi-1]
    if to_shindo: numeral = shindo[mmi-1]
    description = descriptions[mmi-1]    

    return box_color, txt_color, fnt_weight, numeral, description

def mag_style(mag):
    """Manages strength-related language depending on the magnitude of the earthquake."""
    if mag <= 4.0:
        desc = "A minor earthquake"
    if 4.0 <= mag < 5.2:
        desc = "A moderate earthquake"
    if 5.3 <= mag < 5.9:
        desc = "A moderately strong earthquake"
    if 6.0 <= mag < 6.6:
        desc = "A very strong earthquake"
    if mag >= 6.7:
        desc = "A major earthquake"

    return desc

def read_counties():
    """Returns only California and Nevada counties from shapefile"""
    gdf = gpd.read_file('./cb_2018_us_county_20m/cb_2018_us_county_20m.shp')
    gdf["STATEFP"] = gdf["STATEFP"].astype(str).str.zfill(2)
    calnev_counties = gdf[(gdf["STATEFP"] == "06") | (gdf["STATEFP"] == "32")]
    return calnev_counties

# map lims covering the California-Nevada area
lims = [-127.376, -112.412, 31.166, 42.656]

def fetch_usgs_api(starttime='2020-01-01',minmag=5.5, lims=lims):
    """Setup for USGS API request.

    By default only does starttime till present, and no upper limit on magnitude.
    
    Args:
    - starttime: (str) format 'year-month-day'
    - minmag: (float)
    - lims: (list) best not to touch this unless you know what you're doing
    """
    url = 'https://earthquake.usgs.gov/fdsnws/event/1/query'
    query = {
        "format": "geojson",
        "starttime": '2020-01-01',
        "minmagnitude": str(minmag),
        "minlongitude": lims[0],
        "maxlongitude": lims[1],
        "minlatitude": lims[2],
        "maxlatitude": lims[3],
        
    }
    r = requests.get(url, params=query)

    if r.status_code == 200:
        data = r.json()
        return data
    else:
        data = None
        print("Error fetching USGS API")
        return

def get_eew_data(data):
    """Returns alert polygon and epicenter coords from features."""
    event = data['features'][0]
    ev_name = event['properties']['title']
    ev_time = event['properties']['time']
    ev_utc = datetime.fromtimestamp(ev_time / 1000, UTC)
    ev_local = ev_utc.astimezone(ZoneInfo("America/Los_Angeles"))
    time_str = ev_local.strftime("%b %d, %Y %H:%M")
    print(ev_name)
    print(time_str)
    event_detail_url = event['properties']['detail']
    r2 = requests.get(event_detail_url)
    ss_detail = r2.json()

    try:
        eew_url = ss_detail['properties']['products']['shake-alert'][-1]['contents']['summary.json']['url']
        r3 = requests.get(eew_url)
        eew_data = r3.json()
        print('EEW report loaded')
    except:
        print("Event has no ShakeAlert product.")
        return
    
    # get epi and poly from eew report
    try:
        alert = eew_data['alerts'][-1]['features']
    except:
        alert = eew_data['final_alert']['features']

    for feature in alert:
        if feature.get('id') == 'Epicenter' or feature.get('id') == 'finalEpicenter':
            epi_feat = feature
            continue
        
        featMMI = feature['properties'].get('name')
        if featMMI == 'MMI 4' or featMMI == "MMI 3.5":
            MMI = feature['properties']['name']
            # print(MMI)
            polygon_feat = feature

    alert_poly = shape(polygon_feat)
    epix, epiy = epi_feat['geometry']['coordinates']

    return event, ss_detail, alert_poly, epix, epiy

def format_warned_area(calnev_counties,alert_poly):
    calnev_counties['warned'] = calnev_counties.intersects(alert_poly)
    colors = calnev_counties['warned'].map({True: 'yellow', False: 'white'})

    warned_names = calnev_counties[calnev_counties['warned']==True]['NAME'].tolist()
    # warned_fips = calnev_counties[calnev_counties['warned']==True]['COUNTYFP'].tolist()

    regions_used = False

    # about 400 characters should be able to fit in the text box
    if len("".join(warned_names)) >= 50:
        warned_areas = list(warned_names)  # Use list, not numpy array
        condensed_counties = set()

        # Tally which regions are warned
        regions_tally = []
        for county in warned_names:
            for r in regions:
                if county in regions[r]:
                    regions_tally.append(r)

        warns_per_region = Counter(regions_tally)

        # First pass: identify and add condensed regions
        for r in reversed(regions):
            if warns_per_region[r] >= len(regions[r]) - 3 or warns_per_region[r] > 7:
                print(f"Region {r} had {warns_per_region[r]} (max {len(regions[r])}) warnings and will be condensed")
                warned_areas.insert(0, r)  # Add region to front
                regions_used = True
                # Mark all warned counties in this region as condensed
                for county in regions[r]:
                    if county in warned_names:
                        condensed_counties.add(county)

        # Second pass: remove condensed counties, add "Co." to remaining
        final_warned_areas = []
        for area in warned_areas:
            if area in regions.keys():  # It's a region name
                final_warned_areas.append(area)
            elif area not in condensed_counties:  # It's a county not in any condensed region
                final_warned_areas.append(f"{area} Co.")

        print(f'final list {final_warned_areas}')
    else: 
        final_warned_areas = warned_names

    return final_warned_areas, colors, regions_used
    
"""Plot and save img file for EEW"""

def render_eew(calnev_counties,final_warned_areas,colors,regions_used,event,epix,epiy):
    fig, axi = plt.subplots(1,1,figsize=(15,15), subplot_kw={'projection': ccrs.PlateCarree()})

    calnev_counties.plot(ax=axi,color=colors,edgecolor='black',linewidth=0.5)

    pad = 1.5
    x1, y1, x2, y2 = calnev_counties[calnev_counties['warned']==True].total_bounds
    map_lims = (x1 - pad, x2 + pad, y1 - pad/1.5, y2 + pad/1.5)

    axi.set_extent(map_lims)

    # axi.add_feature(cfeature.COASTLINE)
    # axi.add_feature(cfeature.BORDERS, linestyle=':')
    axi.add_feature(cfeature.LAND, edgecolor='black')
    axi.add_feature(cfeature.LAKES, edgecolor='black')
    axi.add_feature(cfeature.RIVERS)
    # axi.add_feature(cfeature.STATES)
    axi.add_feature(cfeature.OCEAN)


    ew_style = dict(boxstyle='square', facecolor='red', edgecolor='black')
    axi.text(0.5,0.98,'EARTHQUAKE WARNING',transform=axi.transAxes,fontsize=36,color='w',fontweight='bold',bbox=ew_style,va='top',ha='center')

    psa_text = "Drop, cover, hold on.\nShaking expected in the following counties:"
    if regions_used: psa_text = "Drop, cover, hold on.\nShaking expected in the following regions/counties:"
    psa_style = dict(boxstyle='square', facecolor='blue', edgecolor='black')
    axi.text(0.5,0.91,psa_text,transform=axi.transAxes,fontsize=16,color='yellow',bbox=psa_style,va='top',ha='center')

    # warned_areas_list = ["12345678943546758697123456789123456789012345678901234567890987654321234567890-"]
    warn_text = "\n".join(textwrap.wrap("        ".join(final_warned_areas), width=60))
    clist_style = dict(boxstyle='square', facecolor='blue', edgecolor='k', pad=0.6)
    axi.text(0.5,0.05,warn_text,transform=axi.transAxes,fontsize=18,color='w',fontweight='bold',bbox=clist_style,va='bottom',ha='center')

    axi.scatter(epix,epiy,marker='X',c='r',ec='white',linewidths=2,s=750)
    # plot_polygon(alert_poly)
    plt.savefig("latest_eew.png",bbox_inches="tight")


def render_mmi(event, ss_detail, calnev_counties):
    city_mmi_url = ss_detail['properties']['products']['losspager'][0]['contents']['json/cities.json']['url']
    r4 = requests.get(city_mmi_url)
    city_mmis = r4.json()
    city_mmis

    global source_data 
    source_data = ss_detail['properties']['products']['losspager'][0]['properties']
    epix, epiy = float(source_data['longitude']), float(source_data['latitude'])
    global mag
    mag = float(source_data['magnitude'])
    box_hl = mag/1.5 #degrees
    x1, x2, y1, y2 = (epix - box_hl, epix + box_hl, epiy - box_hl/1.5, epiy + box_hl/1.5)

    names = []
    coord_pairs = []
    mmis = []

    for city in city_mmis['all_cities']:
        # if city['on_map']:
        names.append(city['name'])
        coord_pairs.append((city['lon'], city['lat']))
        mmis.append(city['mmi'])

    mmis = np.round(np.array(mmis)).astype(int)
    max_mmi = np.max(mmis)
    global maxnumeral
    global maxdesc
    _, _, _, maxnumeral, maxdesc = mmi_style(max_mmi)

    max_ind = np.where(mmis == max_mmi)

    # list of cities where max. intensity was seen
    global cities_max_mmi
    cities_max_mmi = np.array(names)[max_ind]

    map_lims = (x1, x2, y1, y2)

    fig, axi = plt.subplots(1,1,figsize=(15,15), subplot_kw={'projection': ccrs.PlateCarree()})

    axi.add_feature(cfeature.LAND, edgecolor='black')
    axi.add_feature(cfeature.LAKES, edgecolor='black')
    axi.add_feature(cfeature.RIVERS)
    axi.add_feature(cfeature.STATES)
    axi.add_feature(cfeature.OCEAN)

    report_style = dict(boxstyle='square', facecolor='blue', edgecolor='black')
    n='\n' # newline variable

    # caption = f"An earthquake occurred {event['properties']['place']}"
    ev_time = event['properties']['time']
    ev_utc = datetime.fromtimestamp(ev_time / 1000, UTC)
    ev_local = ev_utc.astimezone(ZoneInfo("America/Los_Angeles"))
    time_str = ev_local.strftime("%b %d, %Y %H:%M")
    desc = mag_style(mag)
    epi_mask = calnev_counties.contains(Point(epix,epiy))
    epi_county = calnev_counties[epi_mask]['NAME'].to_list()[0] + " County"
    global caption
    caption = f'{desc} occurred in {epi_county}'
    report_txt = f'{time_str} PT\n{n.join(textwrap.wrap(caption,width=50))}'
    psa_style = dict(boxstyle='square', facecolor='blue', edgecolor='black')
    axi.text(0.5,0.98,report_txt,transform=axi.transAxes,fontsize=20,color='yellow',bbox=psa_style,va='top',ha='center',zorder=15)

    city_wrap = textwrap.wrap(", ".join(cities_max_mmi[:10]), width=70)
    maxmmi_txt = f"Maximum observed intensity {maxnumeral} ({maxdesc}) in\n{n.join(city_wrap)}"
    axi.text(0.5,0.13,f"Magnitude {mag}",transform=axi.transAxes,fontsize=24,color='yellow',fontweight='bold',bbox=report_style,va='bottom',ha='center',zorder=15)
    axi.text(0.5,0.11,maxmmi_txt,transform=axi.transAxes,fontsize=20,color='yellow',bbox=report_style,va='top',ha='center',zorder=15)

    calnev_counties.plot(ax=axi,color='lightgray',edgecolor='black',linewidth=0.5)

    for i, name in enumerate(names):
        x,y = coord_pairs[i][0],coord_pairs[i][1]
        # don't plot points out of bounds
        if (x < x1 or x > x2) or (y < y1 or y > y2):
            continue
        mmi = mmis[i]
        box_color, txt_color, fnt_weight, numeral, _ = mmi_style(mmi)
        mmi_bbox = dict(boxstyle='circle', facecolor=box_color, edgecolor='black')
        axi.text(
            x,y,numeral,
            bbox=mmi_bbox,
            c=txt_color,
            zorder=mmi+1,
            fontweight=fnt_weight,
            )

    axi.set_extent(map_lims)

    axi.scatter(epix,epiy,marker='X',c='r',ec='white',linewidths=2,s=750)

    # axi.set_title(f"Example: {event['properties']['title']}")
    plt.savefig("latest_mmis.png",bbox_inches='tight')

def send_mmi_email(event,maxnumeral,maxdesc,cities_max_mmi):
    import smtplib
    from email.message import EmailMessage

    ev_time = event['properties']['time']
    ev_utc = datetime.fromtimestamp(ev_time / 1000, UTC)
    ev_local = ev_utc.astimezone(ZoneInfo("America/Los_Angeles"))
    time_str = ev_local.strftime("%b %d, %Y %H:%M")


    sender = "fran.yair.co@gmail.com"
    recip = "fran.yair.co@gmail.com"
    app_pass = "elculxcuzmougral"

    msg = EmailMessage()
    msg["Subject"] = "[AUTOMATED] Earthquake Intensity Report (USGS)"
    msg["From"] = sender
    msg["To"] = recip
    image_cid = "mmi_plot"
    msg.add_alternative(f"""\
    <!DOCTYPE html>
    <html>
        <body>
            <p>A new USGS earthquake report has been issued.</p>
            <h2>{time_str}</h2>
            <h2>{caption}</h2>
            <p>Magnitude: {mag}</p>
            <p>Maximum intensity: {maxnumeral} ({maxdesc}) <br> observed in {", ".join(cities_max_mmi)}</p>
            <img src="cid:{image_cid}" alt="MMI map" style="width:750px;"/>
        </body>
    </html>
    """, subtype="html")

    image_path = 'latest_mmis.png'
    with open(image_path, "rb") as f:
        msg.get_payload()[0].add_related(
            f.read(), 
            maintype="image", 
            subtype="png", 
            cid=image_cid
        )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, app_pass)
            server.send_message(msg)
        print("Email with PNG attachment sent successfully!")
    except Exception as e:
        print(f"An error occurred: {e}")

def main(curr_event):
    calnev_counties = read_counties()

    data = fetch_usgs_api()
    event, ss_detail, alert_poly, epix, epiy = get_eew_data(data)

    if event == curr_event:
        print("\n\n\nNo new event. Not rendering or sending emails")
        return event
    else: 
        print("\n\n\nNew event. Rendering and sending emails.")
    final_warned_areas, colors, regions_used = format_warned_area(calnev_counties,alert_poly)

    render_eew(calnev_counties,final_warned_areas,colors,regions_used,event,epix,epiy)
    render_mmi(event,ss_detail,calnev_counties)
    send_mmi_email(event,maxnumeral,maxdesc,cities_max_mmi)
    
    return event

curr_event = None
while True:    
    print("Executing main")
    curr_event = main(curr_event)

    print("Sleeping")
    time.sleep(5)
