import discord
from discord.ext import tasks
from discord import app_commands
from discord.ext import commands
from io import StringIO
from pathlib import Path
from config import TOKEN
from datetime import datetime, timedelta, UTC
from zoneinfo import ZoneInfo

from USGSreportmaker import ReportMaker, format_usgs_time
from manage_guilds import init_guild_table, set_channel, get_channel
from manage_reports import (make_table, 
                            store_msg, 
                            select_msgs)
from embeds import (make_eew_embed, 
                    make_mmi_embed, 
                    make_nomap_embed, 
                    make_viewevent_eew_embed, 
                    make_viewevent_mmi_embed)


intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    # await bot.tree.sync()
    print([guild.name for guild in bot.guilds])
    print([get_channel(guild.id) for guild in bot.guilds])
    print(f"Bot connected. Logged in as {bot.user}")
    for guild in bot.guilds:
        channel_id = get_channel(guild.id)
        if channel_id is None:
            continue

        channel = bot.get_channel(channel_id)

        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except discord.NotFound:
                continue
        try:
            print(f"Logged into {guild.name}")
            # await channel.send(f"_Good morning everyone. I have just been activated and the time is {datetime.now().strftime("%b %d, %Y %I:%M %p")}_")
            # await channel.send("minasan, konbanwa ^w^")
        except discord.Forbidden:
            print(f"No permission to write in {guild.name}. Removing to avoid errors. Use /setchannel to reset.")
            set_channel(guild.id, 0)
    check_quakes.start()

@bot.event
async def on_guild_join(guild):
    print(f"Joined server: {guild.name}")
    if guild.system_channel:
        set_channel(guild.id, guild.system_channel.id)

@bot.tree.command(name="setchannel", description="Set the channel to send reports in.")
@app_commands.checks.has_permissions(manage_guild=True)
async def setchannel(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):
    set_channel(interaction.guild.id, channel.id)

    await interaction.response.send_message(
        f"Reports will now be sent in {channel.mention}",
        ephemeral=True
    )

@bot.tree.command(name="eventlist",description="Show full saved event list.")
async def eventlist(interaction: discord.Interaction):
    text = "\n".join(f"{i}: {ev}" for i, ev in rm.evlist)
    file = discord.File(
        StringIO(text),
        filename="data/eventlist.txt"
    )
    await interaction.response.send_message(
        f"Latest 100 visible. Download file to see all {len(rm.evlist)} events.",
        file=file,
        ephemeral=True
        )

@bot.tree.command(name="viewevent",description="Show the report for an event in the eventlist.")
@app_commands.describe(index="Index of the eventlist earthquake you want to view (latest is 0, default)")
async def viewevent(interaction: discord.Interaction, index: int):
    try:
        await interaction.response.defer()
        status = await interaction.followup.send(f"Loading event {':\n'.join(rm.evlist[index])}...")
    except IndexError:
        await interaction.followup.send(f"Index out of bounds. Must be 0 to {len(rm.evlist)-1}")

    rm_temp = ReportMaker() # new insance to avoid editing the auto-reports

    rm_temp.load_ev_detail(index,is_temp=True)
    # rm_temp.get_eew_data()

    # check if event happened before launch of ShakeAlert
    tformat = "%b %d, %Y %I:%M %p"
    SAlaunch = "Oct 17, 2019 12:00 AM"
    before_SA = datetime.strptime(rm_temp.ev_timestamp,tformat) < datetime.strptime(SAlaunch,tformat)

    embeds = []
    imgs = []

    await status.edit(content="Loading ShakeAlert data...")

    rm_temp.make_eew_map(is_temp=True)
    if rm_temp.has_eew:
        eew_msg = (
            f"This earthquake triggered ShakeAlert.\n"
            f"{rm_temp.eew_caption}\n"
        )
        temp_eew_embed = make_viewevent_eew_embed(
            event_title=rm_temp.evlist[index],
            has_eew=rm_temp.has_eew,
            viewev_eew_caption=eew_msg,
            mag=rm_temp.eew_mag,
            area_list=rm_temp.formatted_warned_areas
        )
        eew_temp_img = discord.File("data/eew_temp.png",filename="eew_temp.png")
        imgs.append(eew_temp_img)
        # await interaction.followup.send(embed=temp_eew_embed,file=eew_temp_img)
    elif before_SA:
        eew_msg = "This earthquake occurred before the launch of ShakeAlert."
        temp_eew_embed = make_viewevent_eew_embed(
                event_title=rm_temp.evlist[index],
                has_eew=False,
                viewev_eew_caption=eew_msg
            )
        # await interaction.followup.send(embed=temp_eew_embed)
    else:
        eew_msg = "This earthquake did not trigger ShakeAlert."
        temp_eew_embed = make_viewevent_eew_embed(
                event_title=rm_temp.evlist[index],
                has_eew=False,
                viewev_eew_caption=eew_msg
            )
        # await interaction.followup.send(embed=temp_eew_embed)
    embeds.append(temp_eew_embed)

    await status.edit(content="Loading intensity data...")
    rm_temp.make_mmi_map(is_temp=True)

    if rm_temp.mmi_plottable:
        temp_mmi_embed = make_viewevent_mmi_embed(
            event_title=rm_temp.evlist[index],
            viewevent_mmi_caption=rm_temp.mmi_report_caption,
            ev_time=rm_temp.ev_timestamp,
            url=rm_temp.ev_url,
            plottable=rm_temp.mmi_plottable,
            mag=rm_temp.ev_mag,
            max_mmi=rm_temp.ev_maxnumeral,
            mmi_desc=rm_temp.ev_maxdesc,
            cities_max_mmi=rm_temp.cities_max_mmi
        )
        mmi_temp_img = discord.File("data/mmi_temp.png",filename="mmi_temp.png")
        embeds.append(temp_mmi_embed)
        imgs.append(mmi_temp_img)
        # await interaction.followup.send(embed=temp_mmi_embed,file=mmi_temp_img)
        # await interaction.followup.send(msg2,file=discord.File("data/mmi_temp.png"))
    else:
        desc = (rm_temp.mmi_report_caption 
        + "\n\nNo intensity-by-city data is available for this event."
        + "\nFor more information, click the link to go to the USGS page for this earthquake.")

        temp_nomap = make_viewevent_mmi_embed(
            event_title=rm_temp.evlist[index],
            viewevent_mmi_caption=desc,
            ev_time=rm_temp.ev_timestamp,
            url=rm_temp.ev_url,
            plottable=False)
        embeds.append(temp_nomap)
        # await interaction.followup.send(embed=temp_nomap)

    await interaction.followup.send(embeds=embeds,files=imgs)

    await status.edit(content=f"Finished loading event {':\n'.join(rm_temp.evlist[index])}")


@bot.tree.command(name="vieweventbyid",description="Show the report for an event from its USGS 'eventid'.")
@app_commands.describe(id="USGS event ID of the event you want to see")
async def viewevent(interaction: discord.Interaction, id: str):
    # try:
    #     await interaction.response.defer()
    #     status = await interaction.followup.send(f"Loading event {':\n'.join(rm.evlist[index])}...")
    # except IndexError:
    #     await interaction.followup.send(f"Index out of bounds. Must be 0 to {len(rm.evlist)-1}")

    query = {
        "eventid": id,
        "format": "geojson"
    }

    try:
        rm_temp = ReportMaker(query=query) # new insance to avoid editing the auto-reports
        await interaction.response.defer()
        status = await interaction.followup.send(f"Loading event {id}...")
    except:
        await interaction.followup.send(f"Could not load event {id}. Please double check the ID.")

    rm_temp.load_ev_detail(is_temp=True)
    # rm_temp.get_eew_data()

    # check if event happened before launch of ShakeAlert
    tformat = "%b %d, %Y %I:%M %p"
    SAlaunch = "Oct 17, 2019 12:00 AM"
    before_SA = datetime.strptime(rm_temp.ev_timestamp,tformat) < datetime.strptime(SAlaunch,tformat)

    embeds = []
    imgs = []

    await status.edit(content="Loading ShakeAlert data...")

    rm_temp.make_eew_map(is_temp=True)
    if rm_temp.has_eew:
        eew_msg = (
            f"This earthquake triggered ShakeAlert.\n"
            f"{rm_temp.eew_caption}\n"
        )
        temp_eew_embed = make_viewevent_eew_embed(
            event_title=rm_temp.data['properties']['title'],
            has_eew=rm_temp.has_eew,
            viewev_eew_caption=eew_msg,
            mag=rm_temp.eew_mag,
            area_list=rm_temp.formatted_warned_areas
        )
        eew_temp_img = discord.File("data/eew_temp.png",filename="eew_temp.png")
        imgs.append(eew_temp_img)
        # await interaction.followup.send(embed=temp_eew_embed,file=eew_temp_img)
    elif before_SA:
        eew_msg = "This earthquake occurred before the launch of ShakeAlert."
        temp_eew_embed = make_viewevent_eew_embed(
                event_title=rm_temp.data['properties']['title'],
                has_eew=False,
                viewev_eew_caption=eew_msg
            )
        # await interaction.followup.send(embed=temp_eew_embed)
    else:
        eew_msg = "This earthquake did not trigger ShakeAlert."
        temp_eew_embed = make_viewevent_eew_embed(
                event_title=rm_temp.data['properties']['title'],
                has_eew=False,
                viewev_eew_caption=eew_msg
            )
        # await interaction.followup.send(embed=temp_eew_embed)
    embeds.append(temp_eew_embed)

    await status.edit(content="Loading intensity data...")

    rm_temp.make_mmi_map(is_temp=True)
    if rm_temp.mmi_plottable:
        temp_mmi_embed = make_viewevent_mmi_embed(
            event_title=rm_temp.data['properties']['title'],
            viewevent_mmi_caption=rm_temp.mmi_report_caption,
            ev_time=rm_temp.ev_timestamp,
            url=rm_temp.ev_url,
            plottable=rm_temp.mmi_plottable,
            mag=rm_temp.ev_mag,
            max_mmi=rm_temp.ev_maxnumeral,
            mmi_desc=rm_temp.ev_maxdesc,
            cities_max_mmi=rm_temp.cities_max_mmi
        )
        mmi_temp_img = discord.File("data/mmi_temp.png",filename="mmi_temp.png")
        embeds.append(temp_mmi_embed)
        imgs.append(mmi_temp_img)
        # await interaction.followup.send(embed=temp_mmi_embed,file=mmi_temp_img)
        # await interaction.followup.send(msg2,file=discord.File("data/mmi_temp.png"))
    else:
        desc = (rm_temp.mmi_report_caption 
        + "\n\nNo intensity-by-city data is available for this event."
        + "\nFor more information, click the link to go to the USGS page for this earthquake.")

        temp_nomap = make_viewevent_mmi_embed(
            event_title=rm_temp.data['properties']['title'],
            viewevent_mmi_caption=desc,
            ev_time=rm_temp.ev_timestamp,
            url=rm_temp.ev_url,
            mag=rm_temp.ev_mag,
            plottable=False)
        embeds.append(temp_nomap)
        # await interaction.followup.send(embed=temp_nomap)

    await interaction.followup.send(embeds=embeds,files=imgs)

    await status.edit(content=f"Finished loading event {rm_temp.ev_detail['properties']['title']}!")

@bot.command()
@commands.is_owner()
async def sync(ctx):
    synced = await bot.tree.sync()
    await ctx.send(f"Synced {len(synced)} commands globally.")

@bot.command()
@commands.is_owner()
async def testmsg(ctx):
    test_nomap_embed = make_nomap_embed(
        "THIS IS A SAMPLE REPORT.\n"+rm.ev_timestamp,
        rm.mmi_report_caption,
        rm.ev_mag,
        rm.ev_url
    )
    test_mmi_embed = make_mmi_embed(
        "THIS IS A SAMPLE REPORT.\n"+rm.mmi_report_caption,
        rm.ev_url,
        rm.ev_timestamp,
        rm.ev_mag,
        rm.ev_maxnumeral,
        rm.ev_maxdesc,
        rm.cities_max_mmi,
    )
    test_eew_embed = make_eew_embed(
        "THIS IS A SAMPLE REPORT.\n"+"A major earthquake was detected off San Francisco County",
        7.5,
        ["Bay Area", "North Coast", "Sacramento Valley"]
    )
    embeds = [test_nomap_embed,test_eew_embed,test_mmi_embed]
    imgs = [
        discord.File("data/latest_mmis.png",filename="latest_mmis.png"),
        discord.File("data/latest_eew.png",filename="latest_eew.png")
             ]
    testmsg = await ctx.send(embeds=embeds,files=imgs)
    print(testmsg)

@tasks.loop(minutes=1)
async def check_quakes():
    # get bot's current event
    curr_ev_id, curr_ev_lastupdate = read_latest()

    # call API
    global rm
    rm = ReportMaker()

    # load in latest event from API and write txt info (index for test)
    index = 0 # falsy if 0, used in format_report_msg
    rm.load_ev_detail(index=index)

    # if last bot event is same as API last event
    if curr_ev_id == rm.ev_id:
        print("No new event.")
        # if no new event, check for update on same event
        if int(curr_ev_lastupdate) == rm.ev_lastupdate:
            # do nothing if no updates
            print("No updates on latest event.")
            return
        # ----------------- IF EVENT IS UPDATED -------------------------
        else:
            # if updated, write update message, remake mmi map
            # no need for new eew map
            print("Latest event updated.")
            rm.make_eew_map()
            rm.make_mmi_map()

            # edit all existing reports
            for sent_report in select_msgs(rm.ev_id):
                update_embeds, update_imgs = make_embeds_from_reportmaker(
                    rm,
                    is_update=True,
                    update_timestamp=rm.ev_lastupdate
                )

                guild_id, channel_id, msg_id = sent_report
                print(f"Fetching msg {msg_id}")
                # get channel id from bot chache
                channel = bot.get_channel(channel_id)
                # find through api if not available
                if not channel:
                    try:
                        channel = await bot.fetch_channel(channel_id)
                    except discord.NotFound:
                        print(f"Channel {channel} in guild {guild_id} not found.")
                        continue
                    except discord.Forbidden:
                        print(f"Bot does not have permission to access {channel} in guild {guild_id}.")
                        continue

                # fetch original report msg
                if channel:
                    try:
                        msg_to_edit = await channel.fetch_message(msg_id)
                    except:
                        print(f"Original report message in {channel_id} not found. It may have been deleted.")
                        continue
                # edit message
                try:
                    await msg_to_edit.edit(embeds=update_embeds,attachments=update_imgs)
                    print(f'msg sent')
                except discord.Forbidden:
                    print(f"No permissions to edit message in {channel_id}")
                    continue
            # finish function after loop is done
            return
    else:
        # it's a new event 
        # (note: can also be the previous event if the latest event has a magnitude downgrade)
        # make both maps and messages
        print("New event posted.")
        if rm.ev_mag >= 5.0:
            with open("data/notable_quakes.txt",'a') as f:
                f.write(f"{rm.ev_id} {rm.ev_timestamp} {rm.ev_lastupdate}\n")
        rm.make_eew_map()
        rm.make_mmi_map()
        msg_eew = rm.format_report_msg("eew",index)
        msg_mmi = rm.format_report_msg("mmi",index)

    # ---------------------------- FOR NEW EVENTS -----------------------------
    print("Broadcasting messages")
    for guild in bot.guilds:
        embeds, imgs = make_embeds_from_reportmaker(rm)

        channel_id = get_channel(guild.id)
        if not channel_id:
            print(f"No channel set for guild {guild.name}. Use /setchannel (channel name) to set a channel.")
            continue

        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except discord.NotFound:
                continue
            except discord.Forbidden:
                continue
        sent_msg = await channel.send(embeds=embeds,files=imgs)
        store_msg(rm.ev_id, sent_msg.guild.id, sent_msg.channel.id, sent_msg.id)

def read_latest():
    try:
        with open("data/latest_report.txt") as f:
            lines = f.readlines()
            curr_ev_id = lines[0].strip()
            curr_ev_lastupdate = lines[1].strip()
            return curr_ev_id, curr_ev_lastupdate
    except FileNotFoundError:
        return None

# TODO: fix logic so that it only tries to update message if there is a new ev update
# otherwise it'll do it every time (this may not be necessarily bad but save resources)

@tasks.loop(minutes=10)
async def update_significant_quakes():
    print("Checking for notable quakes to update.")
    quakes_to_check, last_update_times = get_quakes_to_update()

    for quake_id, lastup_time in zip(quakes_to_check, last_update_times):
        query = {
            "format": "geojson",
            "eventid": quake_id
        }
        rm_notable = ReportMaker(query=query)
        rm_notable.load_ev_detail()
        if lastup_time == rm_notable.ev_lastupdate:
            # if no update, do nothing
            continue
        rm_notable.make_eew_map()
        rm_notable.make_mmi_map()

        for sent_report in select_msgs(rm_notable.ev_id):
            update_embeds, update_imgs = make_embeds_from_reportmaker(
                rm_notable,
                is_update=True,
                update_timestamp=rm_notable.ev_lastupdate
            )

            guild_id, channel_id, msg_id = sent_report
            print(f"Fetching msg {msg_id}")
            # get channel id from bot chache
            channel = bot.get_channel(channel_id)
            # find through api if not available
            if not channel:
                try:
                    channel = await bot.fetch_channel(channel_id)
                except discord.NotFound:
                    print(f"Channel {channel} in guild {guild_id} not found.")
                    continue
                except discord.Forbidden:
                    print(f"Bot does not have permission to access {channel} in guild {guild_id}.")
                    continue

            # fetch original report msg
            if channel:
                try:
                    msg_to_edit = await channel.fetch_message(msg_id)
                except:
                    print(f"Original report message in {channel_id} not found. It may have been deleted.")
                    continue
            # edit message
            try:
                await msg_to_edit.edit(embeds=update_embeds,attachments=update_imgs)
                print(f'msg sent')
            except discord.Forbidden:
                print(f"No permissions to edit message in {channel_id}")
                continue

def get_quakes_to_update():
    """ Updates list of notable quake reports to update.

    Assumes that data/notable_quakes.txt is written during check_quakes.

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
    with open("data/notable_quakes.txt","r") as f:
        lines = f.readlines()

    # only write lines that are not to be deleted
    with open("data/notable_quakes.txt","w") as f:
        for line in lines:
            quake_id, quake_timestamp, update_timestamp = line.split()
            time_since_quake = timedelta(milliseconds=(timestamp_now-int(quake_timestamp)))
            if time_since_quake < deadline:
                # if timestamp is less than 5 days ago, write. Otherwise ignore and stop updating
                valid_quakes.append(quake_id)
                quake_last_updates.append(int(update_timestamp))
                f.write(line)
        
    return valid_quakes, quake_last_updates

def make_embeds_from_reportmaker(
        rm: ReportMaker, 
        is_update = False, 
        update_timestamp: int = None,
        ):
    """ Creates Discord embeds from the available info in the given ReportMaker object.

    Input:
    - rm: ReportMaker object **with eew and mmi data loaded**
    - is_update: whether these embeds are for a message update [bool; default: False]
    - update_timestamp: USGS event update timestamp for updated reports [int; default: None]

    Returns: 
    - embeds: list of embeds to send in message [list of discord.Embed objects]
    - imgs: list of files made for the embeds [list of discord.File objects]
    """

    if (rm.ev_id == None) or (rm.has_eew == None) or (rm.mmi_plottable == None):
        raise RuntimeError("Object 'rm' must have data loaded in.\
                            Please run rm.load_ev_detail(), \
                           rm.make_mmi_map(), and rm.make_eew_map()\
                           before inputting into make_embeds_from_reportmaker()")
    
    embeds = []
    imgs = []
    if rm.has_eew:
        eew_embed = make_eew_embed(
            rm.eew_caption,
            rm.eew_mag,
            rm.formatted_warned_areas
        )
        eew_map = discord.File("data/latest_eew.png",filename="latest_eew.png")
        embeds.append(eew_embed)
        imgs.append(eew_map)

    if rm.mmi_plottable:
        mmi_embed = make_mmi_embed(
            rm.mmi_report_caption,
            rm.ev_url,
            rm.ev_timestamp,
            rm.ev_mag,
            rm.ev_maxnumeral,
            rm.ev_maxdesc,
            rm.cities_max_mmi,
            update=is_update,
            update_time=update_timestamp
        )
        mmi_map = discord.File("data/latest_mmis.png",filename="latest_mmis.png")
        embeds.append(mmi_embed)
        imgs.append(mmi_map)

    # if no mmi data yet
    else:
        nomap_embed = make_nomap_embed(
            rm.ev_timestamp,
            rm.mmi_report_caption,
            rm.ev_mag,
            rm.ev_url
        )
        embeds.append(nomap_embed)

    return embeds, imgs

# on file run, create data files if they don't exist (others are safe)
if not Path("data/guild_settings.db").is_file():
    print("guild_settings.db not found. Creating file. Report channels need to be reset.")
    init_guild_table()

if not Path("data/messages.db").is_file():
    print("messages.db not found. Creating file. Updates will not work on previous events.")
    make_table()

if not Path("data/latest_report.txt").is_file():
    with open("data/latest_report.txt",'w') as f:
        f.write("[id]\n10000000")

# run bot
bot.run(TOKEN)