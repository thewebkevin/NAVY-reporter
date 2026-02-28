import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import sqlite3
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────────────────────────
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DB_FILE  = os.path.join(DATA_DIR, "bot.db")

NEUTRAL_SHIPS = [
    "BMS - Aquatipper",
    "BMS - Ironship",
    "BMS - Longhook",
    "BMS - Bowhead",
    "BMS - Bluefin",
    "Bellweather by VAC",
    "Das Krokodil by VAC",
]

COLONIAL_SHIPS = [
    "Strider",
    "K-81e \"Sombre\"",
    "Type B - \"Lucian\"",
    "Type C - \"Charon\"",
    "Poseidon",
    "Titan",
    "Conqueror",
    "AC-b \"Trident\"",
]

COLONIAL_PLANES = [
    "A51 Venti \"Daedalus\"",
    "Toxot-902 \"Blind Silver\"",
    "Mergo-4 \"Myrmidon\"",
    "V-1 Tzykalia",
    "V-5b Pegasus",
]

WARDEN_SHIPS = [
    "Rinnspeir Ornitier-Class Gunship",
    "68A-4 Ronan Fathomer",
    "81f-f Ronan Blackguard",
    "74b-1 Ronan Gunship",
    "Mercy",
    "Callahan",
    "Blacksteele",
    "Nakki",
]

WARDEN_PLANES = [
    "Luminary Mk. IV Herald",
    "Luminary Mk. II Harbinger",
    "Tulka I1.9 White Raven",
    "M925 Austringer Man-O-War",
    "Tulka P4 Welkinrive",
    "Rinnspeir Mk. I Zealot",
]

ALL_UNITS = sorted(
    set(NEUTRAL_SHIPS + COLONIAL_SHIPS + COLONIAL_PLANES + WARDEN_SHIPS + WARDEN_PLANES)
) + ["Other"]

MAP_HEXES = [
    "Acrithia", "Allod's Bight", "Ash Fields", "Basin Sionnach",
    "Bright's Marsh", "Callahan's Passage", "Callum's Cape",
    "Clahstra", "Clanshead Valley", "Deadlands", "Drowned Vale",
    "Endless Shore", "Farranac Coast", "Fisherman's Row",
    "Godcrofts", "Great March", "Heartlands", "Howl County",
    "Kalokai", "King's Cage", "Loch Mór", "Marban Hollow",
    "Moors", "Morgen's Crossing", "Nevish Line", "Oarbreaker Isles",
    "Origin", "Reaching Trail", "Reaver's Pass", "Reaversgrave",
    "Refuge", "Sanctum", "Shackled Chasm", "Sinking Sands",
    "Snagglemast Ridge", "Speaking Woods", "Stema Landing",
    "Stlican Shelf", "Stone Cradle", "Tempest Island",
    "Terminus", "The Fingers", "Umbral Wildwood", "Viper Pit",
    "Weathered Expanse", "Westgate",
]


# ── Database ──────────────────────────────────────────────────────────────────
def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            INSERT OR IGNORE INTO config VALUES ('war_number',        '1');
            INSERT OR IGNORE INTO config VALUES ('report_channel_id', NULL);
            INSERT OR IGNORE INTO config VALUES ('allowed_role_id',   NULL);
            INSERT OR IGNORE INTO config VALUES ('allowed_role_name', 'officer');

            CREATE TABLE IF NOT EXISTS kills (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id   INTEGER NOT NULL,
                reporter_name TEXT    NOT NULL,
                unit          TEXT    NOT NULL,
                quantity      INTEGER NOT NULL DEFAULT 1,
                location      TEXT    NOT NULL,
                crew          TEXT    NOT NULL DEFAULT '[]',
                notes         TEXT             DEFAULT '',
                war           INTEGER NOT NULL,
                timestamp     TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS losses (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id   INTEGER NOT NULL,
                reporter_name TEXT    NOT NULL,
                unit          TEXT    NOT NULL,
                quantity      INTEGER NOT NULL DEFAULT 1,
                location      TEXT    NOT NULL,
                crew          TEXT    NOT NULL DEFAULT '[]',
                notes         TEXT             DEFAULT '',
                war           INTEGER NOT NULL,
                timestamp     TEXT    NOT NULL
            );
        """)


def get_cfg(key: str, default=None):
    with db() as conn:
        row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    if row and row["value"] is not None:
        return row["value"]
    return default


def set_cfg(key: str, value):
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO config(key, value) VALUES (?, ?)",
            (key, None if value is None else str(value)),
        )


def get_war() -> int:
    return int(get_cfg("war_number", "1"))


def _parse_rows(rows) -> list[dict]:
    result = []
    for row in rows:
        d = dict(row)
        d["crew"] = json.loads(d["crew"])
        result.append(d)
    return result


def get_kills(war: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM kills WHERE war=? ORDER BY id", (war,)).fetchall()
    return _parse_rows(rows)


def get_losses(war: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM losses WHERE war=? ORDER BY id", (war,)).fetchall()
    return _parse_rows(rows)


def add_kill(reporter_id: int, reporter_name: str, unit: str, quantity: int,
             location: str, crew: list, notes: str, war: int, timestamp: str):
    with db() as conn:
        conn.execute(
            "INSERT INTO kills (reporter_id,reporter_name,unit,quantity,location,crew,notes,war,timestamp) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (reporter_id, reporter_name, unit, quantity, location, json.dumps(crew), notes, war, timestamp),
        )


def add_loss(reporter_id: int, reporter_name: str, unit: str, quantity: int,
             location: str, crew: list, notes: str, war: int, timestamp: str):
    with db() as conn:
        conn.execute(
            "INSERT INTO losses (reporter_id,reporter_name,unit,quantity,location,crew,notes,war,timestamp) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (reporter_id, reporter_name, unit, quantity, location, json.dumps(crew), notes, war, timestamp),
        )


def user_in_entry(uid: int, entry: dict) -> bool:
    if entry["reporter_id"] == uid:
        return True
    return any(c["id"] == uid for c in entry.get("crew", []))


# ── Role check ────────────────────────────────────────────────────────────────
def officer_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        role_id   = get_cfg("allowed_role_id")
        role_name = get_cfg("allowed_role_name", "officer")
        member = interaction.user
        if isinstance(member, discord.Member):
            if role_id:
                if any(r.id == int(role_id) for r in member.roles):
                    return True
            else:
                if any(r.name.lower() == role_name.lower() for r in member.roles):
                    return True
        raise app_commands.CheckFailure("missing_role")
    return app_commands.check(predicate)


async def get_report_channel(interaction: discord.Interaction) -> discord.TextChannel:
    channel_id = get_cfg("report_channel_id")
    if channel_id:
        channel = interaction.client.get_channel(int(channel_id))
        if channel:
            return channel
    return interaction.channel


# ── Modals ────────────────────────────────────────────────────────────────────
class KillModal(discord.ui.Modal, title="🎯 Report Kill"):
    quantity = discord.ui.TextInput(label="Quantity", default="1", max_length=3)
    notes    = discord.ui.TextInput(
        label="Notes (optional)", style=discord.TextStyle.paragraph,
        required=False, max_length=300,
    )

    def __init__(self, unit: str, hex: str, crew: list[discord.Member]):
        super().__init__()
        self.unit_value  = unit
        self.hex_value   = hex
        self.crew_members = crew

    async def on_submit(self, interaction: discord.Interaction):
        war = get_war()
        crew_list = [{"id": m.id, "name": str(m), "display_name": m.display_name} for m in self.crew_members]
        add_kill(
            reporter_id=interaction.user.id,
            reporter_name=str(interaction.user),
            unit=self.unit_value,
            quantity=int(self.quantity.value or 1),
            location=self.hex_value,
            crew=crew_list,
            notes=self.notes.value,
            war=war,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        embed = discord.Embed(title="💀 Kill Reported!", color=discord.Color.green())
        embed.add_field(name="Target",   value=f"**{self.quantity.value or 1}x {self.unit_value}**", inline=True)
        embed.add_field(name="Location", value=self.hex_value, inline=True)
        if crew_list:
            embed.add_field(name="Crew", value=" ".join(f"<@{c['id']}>" for c in crew_list), inline=False)
        if self.notes.value:
            embed.add_field(name="Notes", value=self.notes.value, inline=False)
        embed.set_footer(text=f"Reported by {interaction.user.display_name} • War #{war}")
        embed.timestamp = datetime.now(timezone.utc)

        await interaction.response.send_message("✅ Kill logged!", ephemeral=True)
        channel = await get_report_channel(interaction)
        await channel.send(embed=embed)


class LossModal(discord.ui.Modal, title="⚰️ Report Loss"):
    quantity = discord.ui.TextInput(label="Quantity", default="1", max_length=3)
    notes    = discord.ui.TextInput(
        label="Notes (optional)", style=discord.TextStyle.paragraph,
        required=False, max_length=300,
    )

    def __init__(self, unit: str, hex: str, crew: list[discord.Member]):
        super().__init__()
        self.unit_value  = unit
        self.hex_value   = hex
        self.crew_members = crew

    async def on_submit(self, interaction: discord.Interaction):
        war = get_war()
        crew_list = [{"id": m.id, "name": str(m), "display_name": m.display_name} for m in self.crew_members]
        add_loss(
            reporter_id=interaction.user.id,
            reporter_name=str(interaction.user),
            unit=self.unit_value,
            quantity=int(self.quantity.value or 1),
            location=self.hex_value,
            crew=crew_list,
            notes=self.notes.value,
            war=war,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        embed = discord.Embed(title="⚰️ Loss Reported", color=discord.Color.red())
        embed.add_field(name="Unit",     value=f"**{self.quantity.value or 1}x {self.unit_value}**", inline=True)
        embed.add_field(name="Location", value=self.hex_value, inline=True)
        if crew_list:
            embed.add_field(name="Crew", value=" ".join(f"<@{c['id']}>" for c in crew_list), inline=False)
        if self.notes.value:
            embed.add_field(name="Notes", value=self.notes.value, inline=False)
        embed.set_footer(text=f"Reported by {interaction.user.display_name} • War #{war}")
        embed.timestamp = datetime.now(timezone.utc)

        await interaction.response.send_message("✅ Loss logged.", ephemeral=True)
        channel = await get_report_channel(interaction)
        await channel.send(embed=embed)


# ── Bot setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot  = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


@bot.event
async def on_ready():
    init_db()
    await tree.sync()
    print(f"Logged in as {bot.user} — slash commands synced.")


# ── Global error handler ──────────────────────────────────────────────────────
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        role_name = get_cfg("allowed_role_name", "officer")
        await interaction.response.send_message(
            f"❌ You need the **{role_name}** role to use this command.", ephemeral=True,
        )
    elif isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ You need Administrator permission to use this command.", ephemeral=True,
        )
    else:
        raise error


# ── Slash commands ────────────────────────────────────────────────────────────
@tree.command(name="kill", description="Report a kill for your regiment")
@app_commands.describe(
    unit="Vehicle or unit you killed",
    hex="Map hex where the kill occurred",
    crew1="First crew/regiment member",
    crew2="Second crew/regiment member",
    crew3="Third crew/regiment member",
)
@officer_only()
async def kill_cmd(
    interaction: discord.Interaction,
    unit: str, hex: str,
    crew1: discord.Member = None,
    crew2: discord.Member = None,
    crew3: discord.Member = None,
):
    crew = [m for m in [crew1, crew2, crew3] if m is not None]
    await interaction.response.send_modal(KillModal(unit=unit, hex=hex, crew=crew))


@kill_cmd.autocomplete("unit")
async def kill_unit_autocomplete(_i: discord.Interaction, current: str):
    return [app_commands.Choice(name=u, value=u) for u in ALL_UNITS if current.lower() in u.lower()][:25]


@kill_cmd.autocomplete("hex")
async def kill_hex_autocomplete(_i: discord.Interaction, current: str):
    return [app_commands.Choice(name=h, value=h) for h in MAP_HEXES if current.lower() in h.lower()][:25]


@tree.command(name="loss", description="Report a loss for your regiment")
@app_commands.describe(
    unit="Vehicle or unit that was lost",
    hex="Map hex where the loss occurred",
    crew1="First crew/regiment member",
    crew2="Second crew/regiment member",
    crew3="Third crew/regiment member",
)
@officer_only()
async def loss_cmd(
    interaction: discord.Interaction,
    unit: str, hex: str,
    crew1: discord.Member = None,
    crew2: discord.Member = None,
    crew3: discord.Member = None,
):
    crew = [m for m in [crew1, crew2, crew3] if m is not None]
    await interaction.response.send_modal(LossModal(unit=unit, hex=hex, crew=crew))


@loss_cmd.autocomplete("unit")
async def loss_unit_autocomplete(_i: discord.Interaction, current: str):
    return [app_commands.Choice(name=u, value=u) for u in ALL_UNITS if current.lower() in u.lower()][:25]


@loss_cmd.autocomplete("hex")
async def loss_hex_autocomplete(_i: discord.Interaction, current: str):
    return [app_commands.Choice(name=h, value=h) for h in MAP_HEXES if current.lower() in h.lower()][:25]


@tree.command(name="stats", description="Show your personal kill/loss stats this war")
@officer_only()
async def stats_cmd(interaction: discord.Interaction):
    war = get_war()
    uid = interaction.user.id

    kills  = [k for k in get_kills(war)  if user_in_entry(uid, k)]
    losses = [l for l in get_losses(war) if user_in_entry(uid, l)]

    total_kills  = sum(k["quantity"] for k in kills)
    total_losses = sum(l["quantity"] for l in losses)
    kd = f"{total_kills / total_losses:.2f}" if total_losses else "∞"

    embed = discord.Embed(
        title=f"📊 Stats for {interaction.user.display_name}",
        description=f"War #{war}", color=discord.Color.blurple(),
    )
    embed.add_field(name="💀 Kills",   value=str(total_kills),  inline=True)
    embed.add_field(name="⚰️ Losses", value=str(total_losses), inline=True)
    embed.add_field(name="K/D",        value=kd,                inline=True)

    if kills:
        recent = "\n".join(f"`{k['quantity']}x {k['unit']}` @ {k['location']}" for k in kills[-5:])
        embed.add_field(name="Recent Kills", value=recent, inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="leaderboard", description="Show regiment kill leaderboard for current war")
@officer_only()
async def leaderboard_cmd(interaction: discord.Interaction):
    war   = get_war()
    tally: dict[int, dict] = {}

    def ensure(uid: int, name: str):
        if uid not in tally:
            tally[uid] = {"name": name, "kills": 0, "losses": 0}

    for k in get_kills(war):
        ensure(k["reporter_id"], k["reporter_name"])
        tally[k["reporter_id"]]["kills"] += k["quantity"]
        for c in k["crew"]:
            ensure(c["id"], c["name"])
            tally[c["id"]]["kills"] += k["quantity"]

    for l in get_losses(war):
        ensure(l["reporter_id"], l["reporter_name"])
        tally[l["reporter_id"]]["losses"] += l["quantity"]
        for c in l["crew"]:
            ensure(c["id"], c["name"])
            tally[c["id"]]["losses"] += l["quantity"]

    sorted_players = sorted(tally.values(), key=lambda x: x["kills"], reverse=True)
    medals = ["🥇", "🥈", "🥉"]
    lines  = [
        f"{medals[i] if i < 3 else f'`#{i+1}`'} **{p['name']}** — {p['kills']}/{p['losses']} K/L"
        for i, p in enumerate(sorted_players[:10])
    ]

    embed = discord.Embed(title=f"🏆 Kill Leaderboard — War #{war}", color=discord.Color.gold())
    embed.description = "\n".join(lines) if lines else "No kills reported yet this war."
    embed.set_footer(text="Use /kill and /loss to report engagements")
    await interaction.response.send_message(embed=embed)


@tree.command(name="war_summary", description="Full regiment summary for the current war")
@officer_only()
async def war_summary_cmd(interaction: discord.Interaction):
    war    = get_war()
    kills  = get_kills(war)
    losses = get_losses(war)

    total_kills  = sum(k["quantity"] for k in kills)
    total_losses = sum(l["quantity"] for l in losses)

    kill_units: dict[str, int] = {}
    for k in kills:
        kill_units[k["unit"]] = kill_units.get(k["unit"], 0) + k["quantity"]
    top_kill = max(kill_units, key=kill_units.get) if kill_units else "N/A"

    embed = discord.Embed(title=f"⚔️ Regiment War Summary — War #{war}", color=discord.Color.orange())
    embed.add_field(name="Total Kills",      value=str(total_kills),  inline=True)
    embed.add_field(name="Total Losses",     value=str(total_losses), inline=True)
    embed.add_field(name="K/L Ratio",        value=f"{total_kills/total_losses:.2f}" if total_losses else "∞", inline=True)
    embed.add_field(name="Most Hunted Unit", value=top_kill, inline=True)
    embed.add_field(name="Engagements",      value=f"{len(kills)} kills | {len(losses)} losses reported", inline=False)
    await interaction.response.send_message(embed=embed)


@tree.command(name="new_war", description="[Admin] Archive current war and start a new one")
@app_commands.checks.has_permissions(administrator=True)
async def new_war_cmd(interaction: discord.Interaction):
    old_war = get_war()
    set_cfg("war_number", old_war + 1)
    await interaction.response.send_message(
        f"✅ War #{old_war} archived. **War #{old_war + 1}** has begun! Previous stats are preserved.",
    )


@tree.command(name="set_channel", description="[Admin] Set this channel as the kill/loss report channel")
@app_commands.checks.has_permissions(administrator=True)
async def set_channel_cmd(interaction: discord.Interaction):
    set_cfg("report_channel_id", interaction.channel_id)
    await interaction.response.send_message(
        f"✅ Kill/loss reports will now be posted to {interaction.channel.mention}.", ephemeral=True,
    )


@tree.command(name="set_role", description="[Admin] Set the role required to use kill/loss commands")
@app_commands.describe(role="The role to allow (default: officer)")
@app_commands.checks.has_permissions(administrator=True)
async def set_role_cmd(interaction: discord.Interaction, role: discord.Role):
    set_cfg("allowed_role_id",   role.id)
    set_cfg("allowed_role_name", role.name)
    await interaction.response.send_message(
        f"✅ Only members with {role.mention} can now use kill/loss commands.", ephemeral=True,
    )


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        raise ValueError("Set the DISCORD_TOKEN environment variable.")
    bot.run(TOKEN)
