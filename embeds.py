import discord
from USGSreportmaker import ReportMaker, format_usgs_time

def make_eew_embed(eew_caption,mag,area_list):
    embed = discord.Embed(
        title="Earthquake Early Warning",
        description=f'ShakeAlert has been triggered.\n{eew_caption}',
        color=discord.Colour.red(),
    )
    
    embed.add_field(name="Estimated magnitude", value=mag)

    formatted_list = f"- {'\n- '.join(area_list)}"
    embed.add_field(name="Warned counties/regions",value=formatted_list, inline=True)

    fname = "latest_eew.png"
    embed.set_image(url=f'attachment://{fname}')

    return embed

def make_mmi_embed(
        mmi_caption,
        url,
        ev_time,
        mag,
        max_mmi,
        mmi_desc,
        cities_max_mmi,
        update=False,
        update_time=None
    ):
    embed = discord.Embed(
        title="USGS Earthquake Report (Updated)" if update else "USGS Earthquake Report",
        description=f"{mmi_caption}.\n\nIf you felt this earthquake, fill out a [felt report]({url+"/tellus"}).",
        url = url,
        color=discord.Colour.green(),
    )

    embed.add_field(name="Time",value=ev_time,inline=True)
    embed.add_field(name="Magnitude",value=mag, inline=True)
    embed.add_field(name="Max. intensity",value=f"{max_mmi} ({mmi_desc})",inline=True)

    formatted_list = f"- {'\n- '.join(cities_max_mmi)}"
    embed.add_field(name="Maximum intensity in:",value=formatted_list,inline=False)


    fname = "latest_mmis.png"
    embed.set_image(url=f'attachment://{fname}')

    if update:
        t = format_usgs_time(update_time)
        embed.set_footer(text=f"Last updated {t}")

    return embed

def make_nomap_embed(ev_time,desc,mag,url):
    embed = discord.Embed(
        title="USGS Earthquake Report",
        description=f"On {ev_time},\n{desc}.\nThis message will be updated if intensity information becomes available.",
    )

    embed.add_field(name="Magnitude",value=mag, inline=True)
    embed.add_field(name="Additional info",value=url)

    return embed

def make_viewevent_eew_embed(event_title,has_eew=False,viewev_eew_caption=None,mag=None,area_list=None):
    embed = discord.Embed(
        title=f"Earthquake alert archive: {event_title[1]}",
        description=viewev_eew_caption,
    )

    if has_eew:
        embed.add_field(name="Final alert magnitude:", value=mag)

        formatted_list = f"- {'\n- '.join(area_list)}"
        embed.add_field(name="Counties/regions alerted:",value=formatted_list, inline=False)

        fname = "eew_temp.png"
        embed.set_image(url=f'attachment://{fname}')

    return embed

def make_viewevent_mmi_embed(
        event_title,
        viewevent_mmi_caption,
        ev_time,
        url,
        mag,
        plottable=False,
        max_mmi=None,
        mmi_desc=None,
        cities_max_mmi=None
    ):

    embed = discord.Embed(
        title=f"Earthquake report archive: {event_title[1]}",
        description=f"On {ev_time},\n{viewevent_mmi_caption}",
        url = url,
        color=discord.Colour.green(),
    )

    embed.add_field(name="Magnitude",value=mag, inline=True)

    if plottable:
        embed.add_field(name="Max. intensity",value=f"{max_mmi} ({mmi_desc})",inline=True)

        formatted_list = f"- {'\n- '.join(cities_max_mmi)}"
        embed.add_field(name="Maximum intensity in:",value=formatted_list,inline=False)

        fname = "mmi_temp.png"
        embed.set_image(url=f'attachment://{fname}')

    return embed