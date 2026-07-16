"""Yair Franco, 2026"""

import geopandas as gpd
import io
import requests
from datetime import datetime, UTC
from zoneinfo import ZoneInfo
from shapely.geometry import Polygon, Point, shape, box
from collections import Counter
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import textwrap
import numpy as np
import pandas as pd
import time
import smtplib
from email.message import EmailMessage

import warnings
# stops some geopandas warnings that don't affect maps
# maybe a bad idea to block all warnings though
warnings.filterwarnings('ignore')

class ReportMaker:
    """Class holding methods for creating earthquake report maps and captions for EarthquakeBot."""

    default_county_file = './cb_2018_us_county_20m/cb_2018_us_county_20m.shp'
    # defines lims of a CA-NV with some space offshore for MTJ earthquakes
    lims = [-127.376, -112.412, 31.166, 42.656]
    default_query = {
        "format": "geojson",
        "starttime": '2015-01-01',
        "minmagnitude": '3.0',
        "minlongitude": lims[0],
        "maxlongitude": lims[1],
        "minlatitude": lims[2],
        "maxlatitude": lims[3],
    }

    def __init__(self,county_file=default_county_file,query=default_query):
        """
        Loads in county map data and fetches USGS info.

        county_file: path to shapefile with county data (provided in GitHub) [str]
        query: dict containing USGS earthquakes API query attributes [dict]

        County data can possibly be something other than .shp if geopandas
        can parse it, but I would not experiment with it.

        Query request "format" must be geojson.
        """
        # parse CA-NV counties
        try:
            gdf = gpd.read_file(county_file)
            gdf["STATEFP"] = gdf["STATEFP"].astype(str).str.zfill(2)
            self.ca_nv = gdf[(gdf["STATEFP"] == "06") | (gdf["STATEFP"] == "32")]
            self.ca_nv = self.ca_nv.to_crs(epsg=4326)
        except:
            self.ca_nv = None
            print("Could not read county data. Please check your path or file format (recommend .shp)")
            return
        
        # initialize all attributes (avoid errors for not existing)
        self.evlist = None
        self.ev_id = None
        self.ev_lastupdate = None
        self.ev_url = None
        self.ev_timestamp = None
        self.ev_detail = None
        self.has_eew = False
        self.alert_poly = None
        self.eew_epix = None
        self.eew_epiy = None
        self.alert_colors = None
        self.regions_used = None
        self.formatted_warned_areas = []
        self.mmi_report_caption = ""
        self.city_names = []
        self.mmi_coord_pairs = []
        self.mmis = []
        self.mmi_plottable = False
        self.cities_max_mmi = []
        self.dyfi_used = False
        self.ev_mag = None
        self.ev_epix = None
        self.ev_epiy = None
        self.ev_maxnumeral = None
        self.ev_maxdesc = None

        # fetch USGS data
        url = 'https://earthquake.usgs.gov/fdsnws/event/1/query'
        r = requests.get(url,params=query,timeout=15)

        if r.status_code == 200:
            self.data = r.json()
        else:
            self.data = None
            print("Error fetching USGS API. Please try again.")
            return
        print('Fetched USGS data for query.')

        self.evlist = [(str(i),feat['properties']['title']) for i, feat in enumerate(self.data['features'])]

    def load_ev_detail(self,index=0,is_temp=False):
        """Parses USGS API response and writes txt file with event id

        index: select different item from list (attr evlist). Default 0 (latest event) [int]

        """
        event = self.data['features'][index]
        ev_name = event['properties']['title']
        #save id and update timestamp to detect updates or new events
        self.ev_id = event['id']
        self.ev_lastupdate = event['properties']['updated']
        self.ev_url = event['properties']['url']

        # write txt
        fname = "data/temp_report.txt" if is_temp else "data/latest_report.txt"
        with open(fname,"w") as f:
            f.write(f"{self.ev_id}\n{self.ev_lastupdate}")

        ev_time = event['properties']['time']
        # ev_utc = datetime.fromtimestamp(ev_time / 1000, UTC)
        # ev_local = ev_utc.astimezone(ZoneInfo("America/Los_Angeles"))
        # time_str = ev_local.strftime("%b %d, %Y %I:%M %p")
        time_str = format_usgs_time(ev_time)
        self.ev_timestamp = time_str
        print("Loading report:")
        print(ev_name)
        print(time_str)
        event_detail_url = event['properties']['detail']
        r2 = requests.get(event_detail_url)
        self.ev_detail = r2.json()

        
    """
    format_warned_area() condenses long lists of counties if they exceed a 
    certain amount of characters to make space for the box (NHK style).

    The regions in self.regions are chosen arbitrarily by me but I'm going 
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
    a region doesn't get triggered at 1 or 2 counties in 
    regions with few (e.g North Coast).
    Threshold is (n of counties) - 3 or if (n of warned counties) >= 7
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

    def mmi_style(self,mmi,to_shindo=False):
        """Manages shaking-related language depending on the measured intensity of the earthquake.
        mmi: [int]
        to_shindo: Change style to JMA shindo intensity style [bool]
        """
        if mmi == 0: mmi = 1
        if mmi > 10: mmi = 10
                                                                        #orange and darkorange look too similar
        box_colors = ['white','lightblue','cyan','blue','green','yellow','orange','brown','red','darkred']
        txt_colors = ['k',    'k',    'k',       'w',   'w',    'k',      'k',     'w',        'w',  'y']
        weights =    [400,     400,    400,       400,   400,    400,      400,     600,       700,   800]
        fontsizes =  [10,       10,     10,        10,    10,     10,       10,       8,        12,    12]
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
        fnt_size = fontsizes[mmi-1]
        numeral = MMI_ticks[mmi-1]
        if to_shindo: numeral = shindo[mmi-1]
        description = descriptions[mmi-1]    

        return box_color, txt_color, fnt_weight, fnt_size, numeral, description

    def mag_style(self,mag):
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

    def get_eew_data(self):
        """Defines alert polygon and epicenter coords from features.
        """
        try:
            eew_url = self.ev_detail['properties']['products']['shake-alert'][-1]['contents']['summary.json']['url']
            r3 = requests.get(eew_url)
            eew_data = r3.json()
            self.has_eew = True
            print('EEW report loaded')
        except:
            self.has_eew = False
            print("Event has no ShakeAlert product.")
            return
        
        # get epi and poly from eew report
        try:
            alert = eew_data['alerts'][-1]['features']
        except:
            try:
                # old (before around 2022) format. Get final update for simplicity
                alert = eew_data['final_alert']['features']
            except:
                print("Error parsing alert data. Check alert json format.")
                return

        for feature in alert:
            if feature.get('id') == 'Epicenter' or feature.get('id') == 'finalEpicenter':
                epi_feat = feature
                continue
            
            featMMI = feature['properties'].get('name')
            # as per ShakeAlert WEA threshold (treat MMI 3.5 as 4)
            if featMMI == 'MMI 4' or featMMI == "MMI 3.5":
                # MMI = feature['properties']['name']
                # print(MMI)
                polygon_feat = feature

        self.alert_poly = shape(polygon_feat)
        self.eew_epix, self.eew_epiy = epi_feat['geometry']['coordinates']

    def format_warned_area(self):
        if self.has_eew:
            ca_nv = self.ca_nv
            ca_nv["intersect_area"] = ca_nv.geometry.intersection(self.alert_poly).area
            ca_nv["cover_ratio"] = ca_nv["intersect_area"] / ca_nv.geometry.area
            # county counted if poly covers at least 5% of the area
            # prevents whole counties being alerted by a mere graze of the poly
            # TODO: find a better method. This is problematic for small events in large counties
            # (lots of examples in San Bernardino County)
            ca_nv["warned"] = ca_nv["cover_ratio"] > 0.05
            self.alert_colors = ca_nv['warned'].map({True: 'yellow', False: 'white'})

            warned_names = ca_nv[ca_nv['warned']==True]['NAME'].tolist()
            # warned_fips = ca_nv[ca_nv['warned']==True]['COUNTYFP'].tolist()

            self.regions_used = False

            if len("".join(warned_names)) >= 75:
                warned_areas = list(warned_names)
                condensed_counties = set()

                # Tally which regions are warned
                regions_tally = []
                for county in warned_names:
                    for r in self.regions:
                        if county in self.regions[r]:
                            regions_tally.append(r)

                warns_per_region = Counter(regions_tally)

                # First pass: identify and add condensed self.regions
                for r in reversed(self.regions):
                    if warns_per_region[r] >= len(self.regions[r]) - 3 or warns_per_region[r] > 7:
                        print(f"Region {r} had {warns_per_region[r]} (max {len(self.regions[r])}) warnings and will be condensed")
                        warned_areas.insert(0, r)  # Add region to front
                        self.regions_used = True
                        # Mark all warned counties in this region as condensed
                        for county in self.regions[r]:
                            if county in warned_names:
                                condensed_counties.add(county)

                # Second pass: remove condensed counties, add "Co." to remaining
                final_warned_areas = []
                for area in warned_areas:
                    if area in self.regions.keys():  # It's a region name
                        final_warned_areas.append(area)
                    elif area not in condensed_counties:  # It's a county not in any condensed region
                        final_warned_areas.append(f"{area} Co.")
                        self.formatted_warned_areas = final_warned_areas
                print(f'final list {final_warned_areas}')
            else: 
                self.formatted_warned_areas = warned_names

    def make_eew_map(self,show=False,is_temp=False):
        """
        show: show plot in matplotlib (for testing) [bool, default: False]
        is_temp: adds "temp" to filename for maps called by command and not by API watcher [bool, default: False]
        """
        self.get_eew_data()
        self.format_warned_area()          
        if self.has_eew:
            fig, axi = plt.subplots(1,1,figsize=(15,15), subplot_kw={'projection': ccrs.PlateCarree()})

            self.ca_nv.plot(ax=axi,color=self.alert_colors,edgecolor='black',linewidth=0.5)

            # poly_diameter = minimum_bounding_radius(alert_poly) * 2
            # print(poly_diameter)
            # poly_diameter = max(poly_diameter,1)
            # map_lims = [epix - poly_diameter, epix + poly_diameter, epiy - poly_diameter/1.5, epiy + poly_diameter/1.5]
            pad = 1.5
            x1, y1, x2, y2 = self.ca_nv[self.ca_nv['warned']==True].total_bounds
            map_lims = (x1 - pad, x2 + pad, y1 - pad/1.5, y2 + pad/1.5)
            try:
                axi.set_extent(map_lims)
            except:
                axi.set_extent(self.lims)

            # axi.add_feature(cfeature.COASTLINE)
            # axi.add_feature(cfeature.BORDERS, linestyle=':')
            axi.add_feature(cfeature.LAND, edgecolor='black')
            axi.add_feature(cfeature.LAKES, edgecolor='black')
            axi.add_feature(cfeature.RIVERS)
            axi.add_feature(cfeature.STATES)
            axi.add_feature(cfeature.OCEAN)


            ew_style = dict(boxstyle='square', facecolor='red', edgecolor='black')
            axi.text(0.5,0.98,'EARTHQUAKE WARNING',transform=axi.transAxes,fontsize=36,color='w',fontweight='bold',bbox=ew_style,va='top',ha='center')

            psa_text = "Drop, cover, hold on.\nShaking expected in the following counties:"
            if self.regions_used: psa_text = "Drop, cover, hold on.\nShaking expected in the following regions/counties:"
            psa_style = dict(boxstyle='square', facecolor='blue', edgecolor='black')
            axi.text(0.5,0.91,psa_text,transform=axi.transAxes,fontsize=16,color='yellow',bbox=psa_style,va='top',ha='center')

            warn_text = "\n".join(textwrap.wrap("        ".join(self.formatted_warned_areas), width=60))
            clist_style = dict(boxstyle='square', facecolor='blue', edgecolor='k', pad=0.6)
            axi.text(0.5,0.05,warn_text,transform=axi.transAxes,fontsize=18,color='w',fontweight='bold',bbox=clist_style,va='bottom',ha='center')

            axi.scatter(self.eew_epix,self.eew_epiy,marker='X',c='r',ec='white',linewidths=2,s=750)
            # plot_polygon(alert_poly)

            # axi.set_title(f"Example: {event['properties']['title']}, threshold {MMI}")
            fname = "data/eew_temp.png" if is_temp else "data/latest_eew.png"
            plt.savefig(fname,bbox_inches='tight')
            if show: plt.show()
            else: plt.close()
        else:
            print("No EEW was issued for this event.")

    def get_mmi_data(self):
        try:
            # fetch intensity info from losspager. Usually only available for significant earthquakes
            city_mmi_url = self.ev_detail['properties']['products']['losspager'][0]['contents']['json/cities.json']['url']
            r4 = requests.get(city_mmi_url)
            city_mmis = r4.json()

            source_data = self.ev_detail['properties']['products']['losspager'][0]['properties']
            self.ev_epix, self.ev_epiy = float(source_data['longitude']), float(source_data['latitude'])
            self.ev_mag = float(source_data['magnitude'])
            # alternative map centering on epicenter, bad for offshore earthquakes
            # x1, x2, y1, y2 = (epix - box_hl, epix + box_hl, epiy - box_hl/1.5, epiy + box_hl/1.5)

            names = []
            coord_pairs = []
            mmis = []

            for city in city_mmis['all_cities']:
                names.append(city['name'])
                coord_pairs.append((city['lon'], city['lat']))
                mmis.append(city['mmi'])
            self.city_names = names
            self.mmi_coord_pairs = coord_pairs
            self.mmis = mmis

            self.dyfi_used = False

            if names: self.mmi_plottable = True
            # end of losspager data. Below here use dyfi if not available.
            # needed vars: names, coord pairs, mmis, mag, (epix, epiy)

        except KeyError:
            print("No losspager. Using dyfi txt")
            try:
                dyfi_data = self.ev_detail['properties']['products']['dyfi'][0]

                source_data = dyfi_data['properties']
                self.ev_mag = float(source_data['magnitude'])
                self.ev_epix, self.ev_epiy = float(source_data['longitude']), float(source_data['latitude'])

                r4 = requests.get(dyfi_data['contents']['cdi_zip.txt']['url'])
                txt_zip_mmis = r4.text
                zip_mmis = pd.read_csv(io.StringIO(txt_zip_mmis))

                names = []
                coord_pairs = []
                mmis = []

                names = zip_mmis['City'].tolist()
                mmis = zip_mmis['CDI'].tolist()
                mmis = [int(round(x)) for x in mmis]
                for i, row in zip_mmis.iterrows():
                    coord_pairs.append((row['Longitude'], row['Latitude']))

                self.city_names = names
                self.mmi_coord_pairs = coord_pairs
                self.mmis = mmis

                self.dyfi_used = True

                if names: self.mmi_plottable = True
            except:
                self.ev_mag = self.ev_detail['properties']['mag']
                print("losspager and dyfi not available. Plot cannot be be made")
                self.mmi_plottable = False

    def make_mmi_map(self,show=False,is_temp=False):
        """
        show: show plot in matplotlib (for testing) [bool, default: False]
        is_temp: adds "temp" to filename for maps called by command and not by API watcher [bool, default: False]
        """
        self.get_mmi_data()
        if self.mmi_plottable:
            box_hl = self.ev_mag/2 #box length depends on magnitude, unit: degrees
            epix, epiy = self.ev_epix, self.ev_epiy

            if not self.dyfi_used:
            # map center defined by centroid of MMI dots, to avoid map being way off the coast
            # this method is better for losspager as that list is curated and keeps the closest important locations
                g_all = [Point(p) for p in self.mmi_coord_pairs]+[Point(epix,epiy)]
                mmi_pts = gpd.GeoDataFrame(geometry=g_all)
                centroid = box(*mmi_pts.total_bounds).centroid
                x1, x2, y1, y2 = (centroid.x - box_hl, centroid.x + box_hl, centroid.y - box_hl/1.5, centroid.y + box_hl/1.5)
            else:
            # for dyfi, this method is better because dyfi reports can be scattered really far from the source in large earthquakes
            # still bad for offshore earthquakes. need a better method
                x1, x2, y1, y2 = epix - box_hl, epix + box_hl, epiy - box_hl/1.5, epiy + box_hl/1.5

            map_lims = (x1, x2, y1, y2)


            mmis = np.round(np.array(self.mmis)).astype(int)
            max_mmi = np.max(mmis)
            _, _, _, _, maxnumeral, maxdesc = self.mmi_style(max_mmi)
            self.ev_maxnumeral = maxnumeral
            self.ev_maxdesc = maxdesc

            max_ind = np.where(mmis == max_mmi)

            # list of cities where max. intensity was seen
            self.cities_max_mmi = np.unique(np.array(self.city_names)[max_ind])

            fig, axi = plt.subplots(1,1,figsize=(15,15), subplot_kw={'projection': ccrs.PlateCarree()})

            axi.add_feature(cfeature.LAND, edgecolor='black')
            axi.add_feature(cfeature.LAKES, edgecolor='black')
            axi.add_feature(cfeature.RIVERS)
            axi.add_feature(cfeature.STATES)
            axi.add_feature(cfeature.OCEAN)

            report_style = dict(boxstyle='square', facecolor='blue', edgecolor='black')
            n='\n' # newline variable

            # caption = f"An earthquake occurred {event['properties']['place']}"
            desc = self.mag_style(self.ev_mag)
            epi_mask = self.ca_nv.contains(Point(epix,epiy))
            if epi_mask.any():
                # if epicenter is within a polygon
                epi_county = self.ca_nv[epi_mask]['NAME'].to_list()[0]
                caption = f'{desc} occurred in {epi_county} County'
            else:
                #if epicenter is off all polygons (assumes offshore)
                # better method needed for events onshore off region (e.g. in Oregon, Utah, Mexico, etc.)
                county_closest = self.ca_nv.distance(Point(epix,epiy)).sort_values().index[0]
                epi_county = self.ca_nv.loc[county_closest]["NAME"]
                caption = f'{desc} occurred off {epi_county} County'
            self.mmi_report_caption = caption
            report_txt = f'{self.ev_timestamp} PT\n{n.join(textwrap.wrap(caption,width=50))}'
            psa_style = dict(boxstyle='square', facecolor='blue', edgecolor='black')
            axi.text(0.5,0.98,report_txt,transform=axi.transAxes,fontsize=20,color='yellow',bbox=psa_style,va='top',ha='center',zorder=15)

            city_wrap = textwrap.wrap(", ".join(self.cities_max_mmi[:10]), width=70)
            
            #change language depending on mmi data used
            if self.dyfi_used:
                maxmmi_txt = f"Maximum reported intensity {maxnumeral} ({maxdesc}) in\n{n.join(city_wrap)}"
            else:
                maxmmi_txt = f"Maximum observed intensity {maxnumeral} ({maxdesc}) in\n{n.join(city_wrap)}"

            axi.text(0.5,0.13,f"Magnitude {self.ev_mag}",transform=axi.transAxes,fontsize=24,color='yellow',fontweight='bold',bbox=report_style,va='bottom',ha='center',zorder=15)
            axi.text(0.5,0.11,maxmmi_txt,transform=axi.transAxes,fontsize=20,color='yellow',bbox=report_style,va='top',ha='center',zorder=15)

            self.ca_nv.plot(ax=axi,color='lightgray',edgecolor='black',linewidth=0.5)

            for i, name in enumerate(self.city_names):
                x,y = self.mmi_coord_pairs[i][0],self.mmi_coord_pairs[i][1]
                # don't plot points out of bounds
                if (x < x1 or x > x2) or (y < y1 or y > y2):
                    continue
                mmi = mmis[i]
                box_color, txt_color, fnt_weight, fnt_size, numeral, _ = self.mmi_style(mmi)
                mmi_bbox = dict(boxstyle='circle', facecolor=box_color, edgecolor='black')
                axi.text(
                    x,y,numeral,
                    bbox=mmi_bbox,
                    c=txt_color,
                    zorder=mmi+1,
                    fontsize=fnt_size,
                    fontweight=fnt_weight,
                    clip_on=True
                    )
                
            # in_map_counties = gpd.clip(self.ca_nv,(x1,y1,x2,y2))
            # for j, county in in_map_counties.iterrows():
            #     centroid = county.geometry.representative_point()
            #     axi.annotate(
            #         text=county.NAME,
            #         xy=(centroid.x,centroid.y),
            #         c='gray',
            #         fontsize=6
            #     )

            axi.set_extent(map_lims)

            axi.scatter(epix,epiy,marker='X',c='r',ec='white',linewidths=2,s=750)

            # axi.set_title(f"Example: {event['properties']['title']}")
            fname = "data/mmi_temp.png" if is_temp else "data/latest_mmis.png"
            plt.savefig(fname,bbox_inches='tight')
            if show: plt.show()
            else: plt.close()

    def format_report_msg(self,report_type,test=False):
        """Generates the report message for the bot to send.

        report_type: the type of report to output. Options:
        "eew", "mmi", "update". [str]
        test: should be True during testing (i.e. index of report is not 0) [bool, default: False]

        returns 'msg' [str]

        In bot.py 'check_quakes()', 'test' can take 'index' [int] as argument since 
        by design it is falsy when the bot is not being tested.
        """

        if report_type == "eew":
            msg = (
                f"_A new ShakeAlert product has been published by the USGS._\n\n"
                f"A recent earthquake has triggered the ShakeAlert system.\n"
                f"An alert was sent to the following regions/counties:\n"
                f"- {"\n- ".join(self.formatted_warned_areas)}\n"
                f"If you receive an earthquake alert\n"
                f"**drop, cover, and hold on.**"
            )
        
        elif report_type == "mmi":
            msg = (f"_A new earthquake report has been published by the USGS._\n\n"
                f"**{self.ev_timestamp}**\n"
                f"**{self.mmi_report_caption}**\n"
                f"Magnitude: {self.ev_mag}\n"
                f"Maximum intensity: {self.ev_maxnumeral} ({self.ev_maxdesc})\n"
                f"Maximum intensity felt in the following cities:\n"
                f"- {"\n- ".join(self.cities_max_mmi)}\n\n"
                f"If you felt this earthquake, visit {self.ev_url+"/tellus"}"
                f" to fill out a Did You Feel It report."
            )

        elif report_type == "update":
            msg = (f"_This earthquake report has been updated._\n\n"
                f"**{self.ev_timestamp}**\n"
                f"**{self.mmi_report_caption}**\n"
                f"Magnitude: {self.ev_mag}\n"
                f"Maximum intensity: {self.ev_maxnumeral} ({self.ev_maxdesc})\n"
                f"Maximum intensity felt in the following cities:\n"
                f"- {"\n- ".join(self.cities_max_mmi)}\n"
                f"If you felt this earthquake, visit {self.ev_url+"/tellus"}"
                f" to fill out a Did You Feel It report.\n\n"
                f"Last updated {format_usgs_time(self.ev_lastupdate)}"
            )
        
        elif report_type == "nomap":
            msg = (f"_A new earthquake report has been published by the USGS._\n\n"
                f"On {self.ev_timestamp}\n"
                f"A magnitude {self.ev_mag} earthquake occurred in the region.\n"
                f"No intensity-per-city information is available to plot for this earthquake.\n"
                f"For more details visit {self.ev_url}"
            )

        if test:
            return "**THIS IS A TEST**\n" + msg
        else:
            return msg


  
    def email_mmi_report(self):
        # approve = input("This will send an email. Type 'y' to approve:")
        approve = 'y'
        if approve == 'y':
            # TODO: make a new email account to send these
            sender = "fran.yair.co@gmail.com"
            recip = ["fran.yair.co@gmail.com"]
            app_pass = "elculxcuzmougral"

            msg = EmailMessage()
            msg["Subject"] = f"[AUTOMATED] {self.mmi_report_caption} - Intensity Report (USGS)"
            msg["From"] = sender
            msg["To"] = recip
            image_cid = "mmi_plot"
            msg.add_alternative(f"""\
            <!DOCTYPE html>
            <html>
                <body>
                    <p>A new USGS earthquake report has been issued.</p>
                    <h2>{self.ev_timestamp}</h2>
                    <h2>{self.mmi_report_caption}</h2>
                    <p>Magnitude: {self.ev_mag}</p>
                    <p>Maximum intensity: {self.ev_maxnumeral} ({self.ev_maxdesc}) 
                    observed in <br>{"<br>".join(self.cities_max_mmi)}</p>
                    <img src="cid:{image_cid}" alt="MMI map" style="width:100%;"/>
                </body>
            </html>
            """, subtype="html")

            image_path = 'data/latest_mmis.png'
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

        else: print("Not sending email")

def format_usgs_time(t):
    dt = datetime.fromtimestamp(t/1000, UTC)
    pt = dt.astimezone(ZoneInfo("America/Los_Angeles"))
    timestr = pt.strftime("%b %d, %Y %I:%M %p")
    return timestr