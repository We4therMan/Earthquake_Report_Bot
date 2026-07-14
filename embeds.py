import discord
from discord.ext import commands

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

def make_eew_embed(area_list):
    embed = discord.Embed(
        title="Earthquake Early Warning",
        description="A new ShakeAlert product has been published by the USGS",
        color='#eb1e25',
    )

    embed.add_field(name="Counties/Regions",value=area_list, inline=True)

    fname = "latest_eew.png"
    warning_map = discord.File(fname, filename=fname)
    embed.set_image(url=f'attachment://{fname}')

    return embed

def make_mmi_embed(mmi_caption,mag,max_mmi,cities_max_mmi):
    embed = discord.Embed(
        title="USGS Earthquake Report",
        description=mmi_caption,
        color="#16eb21",
    )

    embed.add_field(name="Magnitude",value=mag, inline=True)
    embed.add_field(name="Max. intensity",value=max_mmi,inline=True)

    embed.add_field(name="Max. intensity in:",value=cities_max_mmi)

    fname = "latest_mmi.png"
    warning_map = discord.File(fname, filename=fname)
    embed.set_image(url=f'attachment://{fname}')

    return embed