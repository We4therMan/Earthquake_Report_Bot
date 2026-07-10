import discord
from discord.ext import tasks
from discord import app_commands
from discord.ext import commands
from config import TOKEN
from USGSreportmaker import ReportMaker
from manage_guilds import init_guild_table, set_channel, get_channel
from datetime import datetime

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

@tasks.loop(minutes=1)
async def check_quakes():
    # get bot's current event
    curr_ev_id, curr_ev_lastupdate = read_latest()

    # call API
    rm = ReportMaker()
    # load in latest event from API and write txt info
    index = 0
    rm.load_ev_detail(index=index)
    # print(rm.evlist)

    # if last bot event is same as API last event
    if curr_ev_id == rm.ev_id:
        print("No new event.")
        # check for update on same event
        if int(curr_ev_lastupdate) == rm.ev_lastupdate:
            print("No updates on latest event.")
            # do nothing if no updates
            return
        else:
            # remake maps for update
            # no need for new EEW map, only MMI
            print("Latest event updated.")
            rm.make_mmi_map()
            mmi_header = "The latest earthquake report by the USGS has been updated."
    else:
        # make both maps for new event
        print("New event posted.")
        rm.make_eew_map()
        rm.make_mmi_map()
        eew_header = "A new ShakeAlert product has been published by the USGS."
        mmi_header = "A new earthquake report has been published by the USGS."
    
    if index != 0:
        eew_header = eew_header + "\n\n**THIS IS A TEST**"
        mmi_header = mmi_header + "\n\n**THIS IS A TEST**"
        
    report_message =  (f"_{mmi_header}_\n\n"
        # f"_Message generated {datetime.now()}_"
        f"**{rm.ev_timestamp}**\n"
        f"**{rm.mmi_report_caption}**\n"
        f"Magnitude: {rm.ev_mag}\n"
        f"Maximum intensity: {rm.ev_maxnumeral} ({rm.ev_maxdesc})\n"
        f"Maximum intensity felt in the following cities:\n"
        f"-{"\n-".join(rm.cities_max_mmi)}\n\n"
        f"If you felt this earthquake, visit {rm.ev_url+"/tellus"}"
        f" to fill out a Did You Feel It report.\n\n\n"
    )
    
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

        if rm.has_eew:
            alert_message = (f"_{eew_header}_\n\n"
                    f"A recent earthquake has triggered the ShakeAlert system.\n"
                    f"An alert was sent to the following regions/counties:\n"
                    f"-{"\n-".join(rm.formatted_warned_areas)}\n"
                    f"If you receive an earthquake alert\n"
                    f"**drop, cover, and hold on.**"
                    )

            await channel.send(alert_message,file=discord.File("latest_eew.png"))

        await channel.send(report_message,file=discord.File("latest_mmis.png"))

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