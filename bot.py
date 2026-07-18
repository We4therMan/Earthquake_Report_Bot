import discord
from discord.ext import tasks
from discord import app_commands
from discord.ext import commands
from io import StringIO
from pathlib import Path
from config import TOKEN
from USGSreportmaker import ReportMaker, format_usgs_time
from manage_guilds import init_guild_table, set_channel, get_channel
from manage_reports import init_reports_table, store_report_msg, select_report_msgs
from embeds import EventListView, make_eew_embed, make_mmi_embed, make_nomap_embed
from datetime import datetime, UTC
from zoneinfo import ZoneInfo

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

# @bot.tree.command(name="query",description="Request a new USGS query ")

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
    SAlaunch = "Oct 1, 2019 12:00 AM"
    before_SA = datetime.strptime(rm_temp.ev_timestamp,tformat) < datetime.strptime(SAlaunch,tformat)

    rm_temp.make_eew_map(is_temp=True)
    if rm_temp.has_eew:
        await status.edit(content="Loading ShakeAlert data.")
        
        msg1 = (
            f"This earthquake triggered ShakeAlert.\n"
            f"{rm_temp.eew_caption}\n"
            f"Estimated magnitude: {rm_temp.eew_mag}\n"
            f"An alert was sent to the following regions/counties:\n"
            f"- {'\n- '.join(rm_temp.formatted_warned_areas)}\n"
        )
        await interaction.followup.send(msg1,file=discord.File("data/eew_temp.png"))
    elif before_SA:
        await interaction.followup.send("This earthquake occurred before the launch of ShakeAlert.")
    else:
        await interaction.followup.send("This earthquake did not trigger ShakeAlert.")

    await status.edit(content="Loading intensity data.")
    rm_temp.make_mmi_map(is_temp=True)

    if rm_temp.mmi_plottable:
        msg2 = (
            f"On {rm_temp.ev_timestamp}\n"
            f"{rm_temp.mmi_report_caption}\n"
            f"Magnitude: {rm_temp.ev_mag}\n"
            f"Maximum intensity: {rm_temp.ev_maxnumeral} ({rm_temp.ev_maxdesc})\n"
            f"Maximum intensity felt in the following cities:\n"
            f"- {'\n- '.join(rm_temp.cities_max_mmi)}\n\n"
            f"For more details visit {rm_temp.ev_url}"
        )
        await interaction.followup.send(msg2,file=discord.File("data/mmi_temp.png"))
    else:
        msg2_alt = (
            f"On {rm_temp.ev_timestamp}\n"
            f"A magnitude {rm_temp.ev_mag} earthquake occurred in the region.\n"
            f"No intensity-by-city information is available to plot for this earthquake.\n"
            f"For more details visit {rm_temp.ev_url}"
        )
        await interaction.followup.send(msg2_alt)
    await status.edit(content=f"Finished loading event {':\n'.join(rm.evlist[index])}!")


@bot.command()
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
    synced = await bot.tree.sync()
    await ctx.send(f"Synced {len(synced)} commands globally.")

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

    ev_updated = False
    # if last bot event is same as API last event
    if curr_ev_id == rm.ev_id:
        print("No new event.")
        # if no new event, check for update on same event
        if int(curr_ev_lastupdate) == rm.ev_lastupdate:
            # do nothing if no updates
            print("No updates on latest event.")
            return
        else:
            # if updated, write update message, remake mmi map
            # no need for new eew map
            print("Latest event updated.")
            ev_updated = True
            rm.make_mmi_map()
            msg_update = rm.format_report_msg("update",index)

            # edit all existing reports
            for sent_report in select_report_msgs(rm.ev_id):
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
                try:
                    update_embed = make_mmi_embed(
                        rm.mmi_report_caption,
                        rm.ev_url,
                        rm.ev_timestamp,
                        rm.ev_mag,
                        rm.ev_maxnumeral,
                        rm.ev_maxdesc,
                        rm.cities_max_mmi,
                        update=True,
                        update_time=rm.ev_lastupdate
                    )
                    img = discord.File("data/latest_mmis.png",filename="latest_mmis.png")
                    await msg_to_edit.edit(embed=update_embed,attachments=[img])
                    # await msg_to_edit.edit(content=msg_update,attachments=[discord.File("data/latest_mmis.png")])
                    print(f'msg sent')
                except discord.Forbidden:
                    print(f"No permissions to send message in {channel_id}")
                    continue
            # exit function after loop is done
            return
    else:
        # it's a new event 
        # (note: can also be the previous event if the latest event has a magnitude downgrade)
        # make both maps and messages
        print("New event posted.")
        rm.make_eew_map()
        rm.make_mmi_map()
        msg_eew = rm.format_report_msg("eew",index)
        msg_mmi = rm.format_report_msg("mmi",index)

    print("Broadcasting messages")
    for guild in bot.guilds:
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

        # in each report channel
        # if event has shakealert product, send alert and map
        if rm.has_eew:
            eew_embed = make_eew_embed(rm.eew_caption,rm.eew_mag,rm.formatted_warned_areas)
            await channel.send(file=discord.File("data/latest_eew.png",filename="latest_eew.png"),embed=eew_embed)
            # await channel.send(msg_eew,file=discord.File("data/latest_eew.png"))
        
        if rm.mmi_plottable:
            #if new event, send full new report
            mmi_map = discord.File("data/latest_mmis.png")
            # mmi_msg = await channel.send(msg_mmi,file=mmi_map)
            mmi_embed = make_mmi_embed(
                rm.mmi_report_caption,
                rm.ev_url,
                rm.ev_timestamp,
                rm.ev_mag,
                rm.ev_maxnumeral,
                rm.ev_maxdesc,
                rm.cities_max_mmi
                )
            mmi_msg = await channel.send(file=mmi_map, embed=mmi_embed)
            store_report_msg(rm.ev_id, mmi_msg.guild.id, mmi_msg.channel.id, mmi_msg.id)

        # if event not mappable
        else:
            # msg_nomap = rm.format_report_msg("nomap",index)
            # nomap_msg = await channel.send(msg_nomap)
            nomap_msg = await channel.send(embed=make_nomap_embed(rm.ev_timestamp,rm.ev_mag,rm.ev_url))
            store_report_msg(rm.ev_id, nomap_msg.guild.id, nomap_msg.channel.id, nomap_msg.id)

def read_latest():
    try:
        with open("data/latest_report.txt") as f:
            lines = f.readlines()
            curr_ev_id = lines[0].strip()
            curr_ev_lastupdate = lines[1].strip()
            return curr_ev_id, curr_ev_lastupdate
    except FileNotFoundError:
        return None
    
# on file run, create data files if they don't exist (others are safe)
if not Path("data/guild_settings.db").is_file():
    print("guild_settings.db not found. Creating file. Report channels need to be reset.")
    init_guild_table()

if not Path("data/reports.db").is_file():
    print("reports.db not found. Creating file. Updates will not work on previous events.")
    init_reports_table()

if not Path("data/latest_report.txt").is_file():
    with open("data/latest_report.txt",'w') as f:
        f.write("[id]\n10000000")

# run bot
bot.run(TOKEN)