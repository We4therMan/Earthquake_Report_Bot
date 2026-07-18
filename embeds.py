import discord
from discord.ext import commands
from datetime import datetime
from USGSreportmaker import format_usgs_time

class EventListView(discord.ui.View):
    def __init__(self, events, per_page=20):
        super().__init__(timeout=300)
        self.events = events
        self.per_page = per_page
        self.page = 0

    def make_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page

        lines = [
            f"{idx}: {title}"
            for idx, title in self.events[start:end]
        ]

        embed = discord.Embed(
            title="Saved Events",
            description="```" + "\n".join(lines) + "```"
        )

        total_pages = (len(self.events) - 1) // self.per_page + 1
        embed.set_footer(text=f"Page {self.page + 1}/{total_pages}")

        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(
                embed=self.make_embed(),
                view=self
            )
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if (self.page + 1) * self.per_page < len(self.events):
            self.page += 1
            await interaction.response.edit_message(
                embed=self.make_embed(),
                view=self
            )
        else:
            await interaction.response.defer()

def make_eew_embed(mag,area_list):
    embed = discord.Embed(
        title="Earthquake Early Warning",
        description="A new ShakeAlert product has been published by the USGS",
        color=discord.Colour.red(),
    )
    
    embed.add_field(name="Estimated magnitude", value=mag)

    formatted_list = f"- {'\n- '.join(area_list)}"
    embed.add_field(name="Counties/Regions",value=formatted_list, inline=True)

    fname = "latest_eew.png"
    embed.set_image(url=f'attachment://{fname}')

    return embed

def make_mmi_embed(mmi_caption,url,ev_time,mag,max_mmi,mmi_desc,cities_max_mmi,update=False,update_time=None):
    embed = discord.Embed(
        title="USGS Earthquake Report (Updated)" if update else "USGS Earthquake Report",
        description=mmi_caption,
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

def make_nomap_embed(ev_time,mag,url):
    embed = discord.Embed(
        title="USGS Earthquake Report",
        description=f"On {ev_time}, an earthquake occurred in the region.\nNo intensity-by-city data is available for this earthquake",
    )

    embed.add_field(name="Magnitude",value=mag, inline=True)
    embed.add_field(name="Additional info",value=url)

    return embed