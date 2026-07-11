import discord
from discord.ext import tasks
from discord import app_commands
from discord.ext import commands
from config import TOKEN
from USGSreportmaker import ReportMaker
from manage_guilds import init_guild_table, set_channel, get_channel
from datetime import datetime, UTC
from zoneinfo import ZoneInfo

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    # await bot.tree.sync()
    init_guild_table()
    print([guild.id for guild in bot.guilds])
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
            await channel.send(f"_Good morning everyone. I have just been activated and the time is {datetime.now()}_")
        except discord.Forbidden:
            print("No permission to write here. Removing to avoid errors.")
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

# @bot.tree.command(name="query",description="Request a new USGS query ")

@bot.tree.command(name="eventlist",description="Show full saved event list.")
async def showevlist(ctx):
    ctx.send(f'`{"\n".join([event for event in rm.evlist])}`')

@bot.tree.command(name="viewevent",description="Show the report for an event in the eventlist.")
@app_commands.describe(index="Index of the eventlist earthquake you want to view (latest is 0, default)")
async def select_list_event(ctx, index: int):
    if not isinstance(index, int):
        ctx.send("Not a valid input. Must be a number.")
        return
    ctx.send(f"Loading event {rm.evlist[index]}")

    rm_temp = ReportMaker() # new insance to avoid editing the auto-reports

    rm_temp.load_ev_detail(index,is_temp=True)
    rm_temp.get_eew_data()

    # check if event happened before launch of ShakeAlert
    tformat = "%b %d, %Y %I:%M %p"
    SAlaunch = "Oct 1, 2019 12:00 AM"
    before_SA = datetime.strptime(rm_temp.ev_timestamp,tformat) < datetime.strptime(SAlaunch,tformat)

    if rm_temp.has_eew:
        rm_temp.make_eew_map(is_temp=True)
        msg1 = (
            f"This earthquake triggered ShakeAlert.\n"
            f"An alert was sent to the following regions/counties:\n"
            f"-{"\n-".join(rm_temp.formatted_warned_areas)}\n"
        )
        ctx.send(msg1,file=discord.File("eew_temp.png"))
    elif before_SA:
        ctx.send("This earthquake occurred before the launch of ShakeAlert.")
    else:
        ctx.send("This earthquake did not trigger ShakeAlert.")

    rm_temp.make_mmi_map(is_temp=True)

    if rm_temp.mmi_plottable:
        msg2 = (
            f"On {rm_temp.ev_timestamp}\n"
            f"{rm_temp.mmi_report_caption}\n"
            f"Magnitude: {rm.ev_mag}\n"
            f"Maximum intensity: {rm_temp.ev_maxnumeral} ({rm_temp.ev_maxdesc})\n"
            f"Maximum intensity felt in the following cities:\n"
            f"-{"\n-".join(rm_temp.cities_max_mmi)}\n\n"
        )
        ctx.send(msg2,file=discord.File("eew_temp.png"))
    else:
        msg2_alt = (
            f"On {rm_temp.ev_timestamp}\n"
            f"A magnitude {rm.ev_mag} earthquake occurred in the region.\n"
            f"No intensity-by-city information is available to plot for this earthquake.\n"
            f"For more details visit {rm_temp.ev_url}"
        )
        ctx.send(msg2_alt)

@bot.command
@commands.is_owner()
async def sync(ctx):
    synced = await bot.tree.sync()
    await ctx.send(f"Synced {len(synced)} commands globally.")

@bot.command()
@commands.is_owner()
async def testsync(ctx):
    # Creates a mock server object using your test server ID
    guild = discord.Object(id=994313879029030953) 
    
    # Copies your global commands over to this specific server scope
    bot.tree.copy_global_to(guild=guild)
    
    # Syncs directly to that server instantly
    synced = await bot.tree.sync(guild=guild)
    await ctx.send(f"Instantly synced {len(synced)} commands to test server.")

@tasks.loop(minutes=1)
async def check_quakes():
    # get bot's current event
    curr_ev_id, curr_ev_lastupdate = read_latest()

    # call API
    global rm
    rm = ReportMaker()
    # load in latest event from API and write txt info (index for test)
    index = 0
    rm.load_ev_detail(index=index)
    # print(rm.evlist)

    ev_updated = False
    # if last bot event is same as API last event
    if curr_ev_id == rm.ev_id:
        print("No new event.")
        # check for update on same event
        if int(curr_ev_lastupdate) == rm.ev_lastupdate:
            # do nothing if no updates
            print("No updates on latest event.")
            return
        else:
            # remake maps for update
            # no need for new EEW map, only MMI
            print("Latest event updated.")
            ev_updated = True
            rm.make_mmi_map()
            mmi_header = "The latest earthquake report by the USGS has been updated."
    else:
        # new event
        # make both maps
        print("New event posted.")
        rm.make_eew_map()
        rm.make_mmi_map()
        eew_header = "A new ShakeAlert product has been published by the USGS."
        mmi_header = "A new earthquake report has been published by the USGS."
    
    if index != 0:
        eew_header = eew_header + "\n\n**THIS IS A TEST**"
        mmi_header = mmi_header + "\n\n**THIS IS A TEST**"

    print("Bot pushing messages")
    for guild in bot.guilds:
        channel_id = get_channel(guild.id)
        if channel_id is None:
            print(f"No channel set for guild {guild.name}")
            continue

        channel = bot.get_channel(channel_id)

        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except discord.NotFound:
                continue

        # do this for each valid channel
        if rm.has_eew:
            alert_message = (f"_{eew_header}_\n\n"
                    f"A recent earthquake has triggered the ShakeAlert system.\n"
                    f"An alert was sent to the following regions/counties:\n"
                    f"- {"\n- ".join(rm.formatted_warned_areas)}\n"
                    f"If you receive an earthquake alert\n"
                    f"**drop, cover, and hold on.**"
                    )
            await channel.send(alert_message,file=discord.File("latest_eew.png"))

        report_message =  (f"_{mmi_header}_\n\n"
                # f"_Message generated {datetime.now()}_"
                f"**{rm.ev_timestamp}**\n"
                f"**{rm.mmi_report_caption}**\n"
                f"Magnitude: {rm.ev_mag}\n"
                f"Maximum intensity: {rm.ev_maxnumeral} ({rm.ev_maxdesc})\n"
                f"Maximum intensity felt in the following cities:\n"
                f"- {"\n- ".join(rm.cities_max_mmi)}\n\n"
                f"If you felt this earthquake, visit {rm.ev_url+"/tellus"}"
                f" to fill out a Did You Feel It report.\n\n\n"
            )
        
        if rm.mmi_plottable:
            mmi_map = discord.File("latest_mmis.png")
            # if event update edit report message
            if ev_updated:
                # update time to datetime
                update_dt = datetime.fromtimestamp(rm.ev_lastupdate/1000, UTC)
                # to pacific time
                update_pt = update_dt.astimezone(ZoneInfo("America/Los_Angeles"))
                #to time string
                update_str = update_pt.strftime("%b %d, %Y %I:%M %p")
                try:
                    latest_mmi_msg.edit(report_message+f"_This event was last updated on {update_str}_", attachments=[mmi_map])
                except:
                    return
            #if new event send full new report
            else:  
                latest_mmi_msg = await channel.send(report_message,file=mmi_map)
        else:
            report_message = (f"_{mmi_header}_\n\n"
                f"On {rm.ev_timestamp}\n"
                f"A magnitude {rm.ev_mag} earthquake occurred in the region.\n"
                f"No intensity-by-city information is available to plot for this earthquake.\n"
                f"For more details visit {rm.ev_url}"
            )
            await channel.send(report_message)

def read_latest():
    try:
        with open("latest_report.txt") as f:
            lines = f.readlines()
            curr_ev_id = lines[0].strip()
            curr_ev_lastupdate = lines[1].strip()
            return curr_ev_id, curr_ev_lastupdate
    except FileNotFoundError:
        return None

bot.run(TOKEN)