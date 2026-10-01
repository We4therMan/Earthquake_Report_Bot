from USGSreportmaker import ReportMaker
from datetime import datetime, timedelta
from pathlib import Path

def manage_significant_quakes(rm: ReportMaker):
    """ If significant event, check if event ID has already been placed in .txt file
    and adds it if not. 
    """
    ev_id = rm.ev_id
    id_in_file = False
    with open("data/significant_quakes.txt",'r') as f:
        for line in f:
            id = (line.split(" ")[0])
            if ev_id == id:
                id_in_file = True
                print("This ID found in file.")
                break
    if not id_in_file:
        with open("data/significant_quakes.txt",'a') as f_a:
            print("Appending this event to significant quake list.")
            f_a.write(f"{rm.ev_id} {rm.ev_epoch} {rm.ev_lastupdate}\n")

def get_quakes_to_update():
    """ Updates list of significant quake reports to update.

    Assumes that data/significant_quakes.txt is written during check_quakes.

    - Fetches ID and earthquake timestamp
    - Checks time since earthquake
    - If less than 5 days since, query earthquake and update message
    - If more than 5 days since, remove from list and stop updating
    (Generally, most USGS DYFI responses are in by about 5 days for M>5.0 quakes)
    
    Returns:
    - valid_quakes: list of quake IDs to update [list: [str,...]]
    - quake_last_updates: list of USGS update times for the earthquakes [list: [int,...]]
    """
    valid_quakes = []
    quake_last_updates = []
    # current time
    timestamp_now = int(datetime.now().timestamp() * 1000)
    deadline = timedelta(days=5)

    # read in lines
    with open("data/significant_quakes.txt","r") as f:
        lines = f.readlines()

    # only write lines that are not to be deleted
    with open("data/significant_quakes.txt","w") as f:
        for line in lines:
            try:
                quake_id, quake_timestamp, update_timestamp = line.split()
            except ValueError:
                print("No quakes in file.")
                return [], []
            time_since_quake = timedelta(milliseconds=(timestamp_now-int(quake_timestamp)))

            time_until_deadline = deadline - time_since_quake
            tud_days, tud_hours = time_until_deadline.days, (time_until_deadline.seconds // 3600)
            # print(f"{timestamp_now = }, {time_since_quake = }, {deadline = } {time_until_deadline = }")

            if time_since_quake < deadline:
                # if timestamp is less than 5 days ago, write. Otherwise ignore and stop updating
                print(f"Event {quake_id} will stop being updated in {tud_days} days, {tud_hours} hours.")
                valid_quakes.append(quake_id)
                quake_last_updates.append(int(update_timestamp))
                f.write(line)
            else:
                print(f"Event {quake_id} has passed the deadline and will no longer be updated.")
    return valid_quakes, quake_last_updates