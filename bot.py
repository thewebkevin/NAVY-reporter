import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncpg
import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta

# ── Config ──────────────────────────────────────────────────────────────────
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DB_FILE  = os.path.join(DATA_DIR, "bot.db")

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

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

# ── Unit Images ────────────────────────────────────────────────────────────────
# Map unit name → direct image URL for embed thumbnails.
# Add image URLs here as you gather them — leave blank to omit the thumbnail.
UNIT_IMAGES: dict[str, str] = {
    # ── Colonial Ships ──
    "Strider":              "https://foxhole.wiki.gg/images/thumb/StriderFront.jpg/1024px-StriderFront.jpg?68a3b1",
    "K-81e \"Sombre\"":    "https://foxhole.wiki.gg/images/K81eSombreFront.jpg",
    "Type B - \"Lucian\"": "https://foxhole.wiki.gg/images/Lucian_Front.jpg",
    "Type C - \"Charon\"": "https://foxhole.wiki.gg/images/thumb/Charon_Front.jpg/1280px-Charon_Front.jpg?4bc662",
    "Poseidon":             "https://foxhole.wiki.gg/images/PoseidonFront.jpg",
    "Titan":                "https://foxhole.wiki.gg/images/Titan.jpg",
    "Conqueror":            "https://foxhole.wiki.gg/images/thumb/ColonialDestroyerRender.png/1920px-ColonialDestroyerRender.png?2088ea",
    "AC-b \"Trident\"":    "https://foxhole.wiki.gg/images/ACbTrident.jpg",
    # ── Colonial Planes ──
    "A51 Venti \"Daedalus\"":      "https://foxhole.wiki.gg/images/A51_Venti_%E2%80%9CDaedalus%E2%80%9D_Render.jpg",
    "Toxot-902 \"Blind Silver\"":  "https://foxhole.wiki.gg/images/ToxotStripped.jpg",
    "Mergo-4 \"Myrmidon\"":        "https://foxhole.wiki.gg/images/Mergo-4_%E2%80%9CMyrmidon%E2%80%9D_Render.jpg",
    "V-1 Tzykalia":                "https://foxhole.wiki.gg/images/V-1_Tzykalia_Render.jpg",
    "V-5b Pegasus":                "https://foxhole.wiki.gg/images/V-5b_Pegasus_Render.jpg",
    # ── Warden Ships ──
    "Rinnspeir Ornitier-Class Gunship": "https://foxhole.wiki.gg/images/Ornitier_front.png",
    "68A-4 Ronan Fathomer":             "https://foxhole.wiki.gg/images/68A-4_Ronan_Fathomer_Render.jpg",
    "81f-f Ronan Blackguard":           "https://foxhole.wiki.gg/images/81f-f_Ronan_Blackguard_Render.jpg",
    "74b-1 Ronan Gunship":              "https://foxhole.wiki.gg/images/RonanFront_NavalUpdate.png",
    "Mercy":                            "https://foxhole.wiki.gg/images/WardenCarrierFront.jpg",
    "Callahan":                         "https://foxhole.wiki.gg/images/CallahanBattleship.jpg",
    "Blacksteele":                      "https://foxhole.wiki.gg/images/BlacksteeleRear.jpg",
    "Nakki":                            "https://foxhole.wiki.gg/images/NakkiScreenshot.jpg",
    # ── Warden Planes ──
    "Luminary Mk. IV Herald":       "https://foxhole.wiki.gg/images/Luminary_Mk._IV_Herald_Render.jpg",
    "Luminary Mk. II Harbinger":    "https://foxhole.wiki.gg/images/Luminary_Mk._II_Harbinger_Render.jpg",
    "Tulka I1.9 White Raven":       "https://foxhole.wiki.gg/images/Tulka_I1.9_White_Raven_Render.jpg",
    "M925 Austringer Man-O-War":    "https://foxhole.wiki.gg/images/M925_Austringer_Man-O-War_Render.jpg",
    "Tulka P4 Welkinrive":          "https://foxhole.wiki.gg/images/Tulka_P4_Welkinrive_Render.jpg",
    "Rinnspeir Mk. I Zealot":       "https://foxhole.wiki.gg/images/Rinnspeir_Mk._I_Zealot_Render.jpg",
    # ── Neutral Ships ──
    "BMS - Aquatipper":      "https://foxhole.wiki.gg/images/thumb/ScreenshotBarge.png/1280px-ScreenshotBarge.png?b5ac91",
    "BMS - Ironship":        "https://foxhole.wiki.gg/images/Freighter_ScreenshotTankLoaded.png",
    "BMS - Longhook":        "https://foxhole.wiki.gg/images/LonghookFront.png",
    "BMS - Bowhead":         "https://foxhole.wiki.gg/images/thumb/ResourceShip.jpg/1280px-ResourceShip.jpg?127e65",
    "BMS - Bluefin":         "https://foxhole.wiki.gg/images/thumb/StorageShip.jpg/1280px-StorageShip.jpg?879557",
    "Bellweather by VAC":    "https://foxhole.wiki.gg/images/BellweatherbyVACFront.jpg",
    "Das Krokodil by VAC":   "https://foxhole.wiki.gg/images/thumb/DasKrokodilbyVACFront.jpg/1024px-DasKrokodilbyVACFront.jpg?6221d3",
}


def get_unit_image(unit: str) -> str | None:
    url = UNIT_IMAGES.get(unit, "")
    return url if url else None

MAP_HEXES = [
    "Acrithia", "Allod's Bight", "Ash Fields", "Basin Sionnach",
    "Callahan's Passage", "Callum's Cape", "Clanshead Valley",
    "Deadlands", "Endless Shore", "Farranac Coast", "Fisherman's Row",
    "Godcrofts", "Great March", "Howl County", "Kalokai", "King's Cage",
    "Kuura Strand", "Loch Mór", "Lykos Isle", "Marban Hallow",
    "Morgen's Crossing", "Nevish Line", "Oarbreaker Isles", "Olavis Wake",
    "Onyx", "Origin", "Palantine Berm", "Pari Peak", "Piper's Enclave",
    "Reaching Trail", "Reaver's Pass", "Red River", "Sableport",
    "Shackled Chasm", "Speaking Woods", "Stema Landing", "Stlican Shelf",
    "Stonecradle", "Tempest Island", "Terminus", "The Clahstra",
    "The Drowned Vale", "The Fingers", "The Gutter", "The Heartlands",
    "The Linn of Mercy", "The Moors", "Tyrant Foothills", "Umbral Wildwood",
    "Viper Pit", "Weathered Expanse", "Westgate", "Wresta",
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


def user_in_crew(uid: int, entry: dict) -> bool:
    """Only counts explicitly tagged crew — reporter does not get automatic credit."""
    return any(c["id"] == uid for c in entry.get("crew", []))


def get_recent_by_reporter(reporter_id: int, limit: int = 5) -> list[dict]:
    results = []
    with db() as conn:
        kills  = conn.execute(
            "SELECT *, 'kill' as type FROM kills  WHERE reporter_id=? ORDER BY id DESC LIMIT ?",
            (reporter_id, limit),
        ).fetchall()
        losses = conn.execute(
            "SELECT *, 'loss' as type FROM losses WHERE reporter_id=? ORDER BY id DESC LIMIT ?",
            (reporter_id, limit),
        ).fetchall()
    for row in list(kills) + list(losses):
        d = dict(row)
        d["crew"] = json.loads(d["crew"])
        results.append(d)
    results.sort(key=lambda x: x["timestamp"], reverse=True)
    return results[:limit]


def delete_entry(entry_id: int, entry_type: str):
    table = "kills" if entry_type == "kill" else "losses"
    with db() as conn:
        conn.execute(f"DELETE FROM {table} WHERE id=?", (entry_id,))


def clear_all_entries():
    with db() as conn:
        conn.execute("DELETE FROM kills")
        conn.execute("DELETE FROM losses")


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


def _build_kill_embed(unit: str, quantity: int, hex: str, war: int,
                      crew_list: list, notes: str, filed_by: str) -> discord.Embed:
    qty_label = f"{quantity}× " if quantity != 1 else ""
    desc = f"Eliminated in **{hex}**"
    if crew_list:
        desc += "\n👥 " + " ".join(f"<@{c['id']}>" for c in crew_list)
    if notes:
        desc += f"\n*{notes}*"
    embed = discord.Embed(
        title=f"☠  {qty_label}{unit} — KILL CONFIRMED",
        description=desc,
        color=0x4b5320,
    )
    img_url = get_unit_image(unit)
    if img_url:
        embed.set_thumbnail(url=img_url)
    embed.set_footer(text=f"Filed by {filed_by}  ·  OFFICE OF NAVAL INTELLIGENCE  ·  War #{war}")
    embed.timestamp = datetime.now(timezone.utc)
    return embed


def _build_loss_embed(unit: str, quantity: int, hex: str, war: int,
                      crew_list: list, notes: str, filed_by: str) -> discord.Embed:
    qty_label = f"{quantity}× " if quantity != 1 else ""
    desc = f"Lost in **{hex}**"
    if crew_list:
        desc += "\n👥 " + " ".join(f"<@{c['id']}>" for c in crew_list)
    if notes:
        desc += f"\n*{notes}*"
    embed = discord.Embed(
        title=f"⚰  {qty_label}{unit} — UNIT LOST",
        description=desc,
        color=0x6b1a1a,
    )
    img_url = get_unit_image(unit)
    if img_url:
        embed.set_thumbnail(url=img_url)
    embed.set_footer(text=f"Filed by {filed_by}  ·  OFFICE OF NAVAL INTELLIGENCE  ·  War #{war}")
    embed.timestamp = datetime.now(timezone.utc)
    return embed


# ── Bot setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot  = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


_stockpile_setup_done = False


@bot.event
async def on_ready():
    init_db()
    global _stockpile_setup_done
    if not _stockpile_setup_done:
        if DATABASE_URL:
            await init_stockpile_db()
            for row in await list_all_active_stockpiles():
                view = StockpileResetView(row["id"])
                if row["message_id"]:
                    bot.add_view(view, message_id=row["message_id"])
                else:
                    bot.add_view(view)
            if not check_stockpiles.is_running():
                check_stockpiles.start()
        else:
            print("[stockpile] DATABASE_URL not set — stockpile timer feature disabled.")
        _stockpile_setup_done = True
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
    unit="Unit you killed",
    hex="Map hex where the kill occurred",
    quantity="Number destroyed (default: 1)",
    notes="Battle notes (optional)",
    crew1="Crew member 1",
    crew2="Crew member 2",
    crew3="Crew member 3",
    crew4="Crew member 4",
    crew5="Crew member 5",
)
@officer_only()
async def kill_cmd(
    interaction: discord.Interaction,
    unit: str, hex: str,
    quantity: int = 1,
    notes: str = None,
    crew1: discord.Member = None,
    crew2: discord.Member = None,
    crew3: discord.Member = None,
    crew4: discord.Member = None,
    crew5: discord.Member = None,
):
    war = get_war()
    crew = [m for m in [crew1, crew2, crew3, crew4, crew5] if m is not None]
    crew_list = [{"id": m.id, "name": str(m), "display_name": m.display_name} for m in crew]
    add_kill(
        reporter_id=interaction.user.id,
        reporter_name=str(interaction.user),
        unit=unit, quantity=quantity, location=hex,
        crew=crew_list, notes=notes or "", war=war,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    embed = _build_kill_embed(unit, quantity, hex, war, crew_list, notes or "", interaction.user.display_name)
    await interaction.response.send_message("✅ Kill logged!", ephemeral=True)
    channel = await get_report_channel(interaction)
    try:
        await channel.send(embed=embed)
    except discord.Forbidden:
        await interaction.followup.send(
            f"⚠️ I don't have permission to post in {channel.mention}. "
            "An admin needs to run `/set_channel` in a channel I can access, "
            "or give me **Send Messages** + **Embed Links** permissions there.",
            ephemeral=True,
        )


@kill_cmd.autocomplete("unit")
async def kill_unit_autocomplete(_i: discord.Interaction, current: str):
    return [app_commands.Choice(name=u, value=u) for u in ALL_UNITS if current.lower() in u.lower()][:25]


@kill_cmd.autocomplete("hex")
async def kill_hex_autocomplete(_i: discord.Interaction, current: str):
    return [app_commands.Choice(name=h, value=h) for h in MAP_HEXES if current.lower() in h.lower()][:25]


@tree.command(name="loss", description="Report a loss for your regiment")
@app_commands.describe(
    unit="Unit that was lost",
    hex="Map hex where the loss occurred",
    quantity="Number lost (default: 1)",
    notes="Battle notes (optional)",
    crew1="Crew member 1",
    crew2="Crew member 2",
    crew3="Crew member 3",
    crew4="Crew member 4",
    crew5="Crew member 5",
)
@officer_only()
async def loss_cmd(
    interaction: discord.Interaction,
    unit: str, hex: str,
    quantity: int = 1,
    notes: str = None,
    crew1: discord.Member = None,
    crew2: discord.Member = None,
    crew3: discord.Member = None,
    crew4: discord.Member = None,
    crew5: discord.Member = None,
):
    war = get_war()
    crew = [m for m in [crew1, crew2, crew3, crew4, crew5] if m is not None]
    crew_list = [{"id": m.id, "name": str(m), "display_name": m.display_name} for m in crew]
    add_loss(
        reporter_id=interaction.user.id,
        reporter_name=str(interaction.user),
        unit=unit, quantity=quantity, location=hex,
        crew=crew_list, notes=notes or "", war=war,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    embed = _build_loss_embed(unit, quantity, hex, war, crew_list, notes or "", interaction.user.display_name)
    await interaction.response.send_message("✅ Loss logged.", ephemeral=True)
    channel = await get_report_channel(interaction)
    try:
        await channel.send(embed=embed)
    except discord.Forbidden:
        await interaction.followup.send(
            f"⚠️ I don't have permission to post in {channel.mention}. "
            "An admin needs to run `/set_channel` in a channel I can access, "
            "or give me **Send Messages** + **Embed Links** permissions there.",
            ephemeral=True,
        )


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

    kills  = [k for k in get_kills(war)  if user_in_crew(uid, k)]
    losses = [l for l in get_losses(war) if user_in_crew(uid, l)]

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

    # Only crew members get credit — reporter is just the person logging the entry
    for k in get_kills(war):
        for c in k["crew"]:
            ensure(c["id"], c["name"])
            tally[c["id"]]["kills"] += k["quantity"]

    for l in get_losses(war):
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
    embed.set_footer(text="Tag crew members in /kill and /loss to earn credit")
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


@tree.command(name="set_war", description="[Admin] Set the war number directly and optionally clear all data")
@app_commands.describe(
    number="The war number to set (e.g. 132)",
    clear="Wipe all existing kill/loss data (default: False)",
)
@app_commands.checks.has_permissions(administrator=True)
async def set_war_cmd(interaction: discord.Interaction, number: int, clear: bool = False):
    old_war = get_war()
    set_cfg("war_number", number)
    if clear:
        clear_all_entries()
        await interaction.response.send_message(
            f"✅ War number set to **#{number}** (was #{old_war}). All kill/loss data has been wiped.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            f"✅ War number set to **#{number}** (was #{old_war}). Existing data preserved.",
            ephemeral=True,
        )


# ── Delete entry UI ───────────────────────────────────────────────────────────
class DeleteSelect(discord.ui.Select):
    def __init__(self, entries: list[dict]):
        options = []
        for e in entries:
            kind  = "💀 Kill" if e["type"] == "kill" else "⚰️ Loss"
            label = f"{kind}: {e['quantity']}x {e['unit']} @ {e['location']}"
            options.append(discord.SelectOption(
                label=label[:100],
                value=f"{e['type']}:{e['id']}",
                description=f"War #{e['war']} • {e['timestamp'][:10]}",
            ))
        super().__init__(placeholder="Select the entry to delete…", options=options)

    async def callback(self, interaction: discord.Interaction):
        entry_type, entry_id = self.values[0].split(":", 1)
        delete_entry(int(entry_id), entry_type)
        kind = "Kill" if entry_type == "kill" else "Loss"
        await interaction.response.edit_message(
            content=f"✅ {kind} entry deleted.", view=None,
        )


class DeleteView(discord.ui.View):
    def __init__(self, entries: list[dict]):
        super().__init__(timeout=60)
        self.add_item(DeleteSelect(entries))


@tree.command(name="delete", description="Delete one of your recent kill/loss entries")
@officer_only()
async def delete_cmd(interaction: discord.Interaction):
    entries = get_recent_by_reporter(interaction.user.id, limit=5)
    if not entries:
        await interaction.response.send_message("You have no recent entries to delete.", ephemeral=True)
        return
    await interaction.response.send_message(
        "Select the entry you want to remove:", view=DeleteView(entries), ephemeral=True,
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


# ── Stockpile timers: Postgres layer ───────────────────────────────────────────
PG_POOL: asyncpg.Pool | None = None

STOCKPILE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS guild_settings (
        guild_id             BIGINT PRIMARY KEY,
        default_warn_role_id BIGINT
    );

    CREATE TABLE IF NOT EXISTS stockpiles (
        id                   SERIAL PRIMARY KEY,
        guild_id             BIGINT NOT NULL,
        channel_id           BIGINT NOT NULL,
        message_id           BIGINT,
        name                 TEXT NOT NULL,
        duration_hours       REAL NOT NULL DEFAULT 48,
        warn_threshold_hours REAL NOT NULL DEFAULT 6,
        warn_repeat_minutes  INT,
        warn_role_id         BIGINT,
        last_reset_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
        reset_by_id          BIGINT,
        reset_by_name        TEXT,
        status               TEXT NOT NULL DEFAULT 'ok',
        last_warned_at       TIMESTAMPTZ,
        active               BOOLEAN NOT NULL DEFAULT TRUE
    );

    CREATE TABLE IF NOT EXISTS stockpile_log (
        id           SERIAL PRIMARY KEY,
        stockpile_id INT NOT NULL REFERENCES stockpiles(id),
        actor_id     BIGINT NOT NULL,
        actor_name   TEXT NOT NULL,
        action       TEXT NOT NULL,
        at           TIMESTAMPTZ NOT NULL DEFAULT now()
    );
"""


async def get_pool() -> asyncpg.Pool:
    global PG_POOL
    if PG_POOL is None:
        PG_POOL = await asyncpg.create_pool(DATABASE_URL)
    return PG_POOL


async def init_stockpile_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(STOCKPILE_SCHEMA)


async def create_stockpile(guild_id: int, channel_id: int, name: str, duration_hours: float,
                            warn_threshold_hours: float, warn_repeat_minutes: int | None,
                            warn_role_id: int | None) -> int:
    pool = await get_pool()
    return await pool.fetchval(
        """INSERT INTO stockpiles
               (guild_id, channel_id, name, duration_hours, warn_threshold_hours, warn_repeat_minutes, warn_role_id)
           VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id""",
        guild_id, channel_id, name, duration_hours, warn_threshold_hours, warn_repeat_minutes, warn_role_id,
    )


async def set_message_id(stockpile_id: int, message_id: int):
    pool = await get_pool()
    await pool.execute("UPDATE stockpiles SET message_id=$1 WHERE id=$2", message_id, stockpile_id)


async def get_stockpile(stockpile_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM stockpiles WHERE id=$1", stockpile_id)
    return dict(row) if row else None


async def list_stockpiles(guild_id: int) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM stockpiles WHERE guild_id=$1 AND active=TRUE ORDER BY name", guild_id,
    )
    return [dict(r) for r in rows]


async def list_all_active_stockpiles() -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch("SELECT * FROM stockpiles WHERE active=TRUE")
    return [dict(r) for r in rows]


async def log_action(stockpile_id: int, actor_id: int, actor_name: str, action: str):
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO stockpile_log (stockpile_id, actor_id, actor_name, action) VALUES ($1,$2,$3,$4)",
        stockpile_id, actor_id, actor_name, action,
    )


async def reset_stockpile(stockpile_id: int, user_id: int, user_name: str):
    pool = await get_pool()
    await pool.execute(
        """UPDATE stockpiles
           SET last_reset_at=now(), reset_by_id=$1, reset_by_name=$2, status='ok', last_warned_at=NULL
           WHERE id=$3""",
        user_id, user_name, stockpile_id,
    )
    await log_action(stockpile_id, user_id, user_name, "reset")


async def remove_stockpile(stockpile_id: int):
    pool = await get_pool()
    await pool.execute("UPDATE stockpiles SET active=FALSE WHERE id=$1", stockpile_id)


async def set_status(stockpile_id: int, status: str):
    pool = await get_pool()
    await pool.execute("UPDATE stockpiles SET status=$1 WHERE id=$2", status, stockpile_id)


async def set_last_warned(stockpile_id: int):
    pool = await get_pool()
    await pool.execute("UPDATE stockpiles SET last_warned_at=now() WHERE id=$1", stockpile_id)


async def get_history(stockpile_id: int, limit: int = 10) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM stockpile_log WHERE stockpile_id=$1 ORDER BY at DESC LIMIT $2",
        stockpile_id, limit,
    )
    return [dict(r) for r in rows]


async def get_default_role(guild_id: int) -> int | None:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT default_warn_role_id FROM guild_settings WHERE guild_id=$1", guild_id)
    return row["default_warn_role_id"] if row else None


async def set_default_role(guild_id: int, role_id: int):
    pool = await get_pool()
    await pool.execute(
        """INSERT INTO guild_settings (guild_id, default_warn_role_id) VALUES ($1,$2)
           ON CONFLICT (guild_id) DO UPDATE SET default_warn_role_id=$2""",
        guild_id, role_id,
    )


async def ensure_db_available(interaction: discord.Interaction) -> bool:
    if not DATABASE_URL:
        await interaction.response.send_message(
            "⚠️ Stockpile tracking isn't configured yet — an admin needs to attach a Postgres "
            "database (`DATABASE_URL`) to this bot on Railway.",
            ephemeral=True,
        )
        return False
    return True


# ── Stockpile timers: embed & button ────────────────────────────────────────────
STOCKPILE_STATUS_EMOJI = {"ok": "🟢", "warning": "🟡", "expired": "🔴"}
STOCKPILE_STATUS_COLOR = {
    "ok":      discord.Color.green(),
    "warning": discord.Color.gold(),
    "expired": discord.Color.red(),
}


def build_stockpile_embed(row: dict) -> discord.Embed:
    expires_at = row["last_reset_at"] + timedelta(hours=row["duration_hours"])
    expires_unix = int(expires_at.timestamp())
    status = row["status"]

    embed = discord.Embed(
        title=f"📦 {row['name']}",
        color=STOCKPILE_STATUS_COLOR.get(status, discord.Color.greyple()),
    )
    embed.add_field(
        name="Status",
        value=f"{STOCKPILE_STATUS_EMOJI.get(status, '⚪')} {status.upper()}",
        inline=True,
    )
    embed.add_field(name="Expires", value=f"<t:{expires_unix}:R>", inline=True)
    if row["reset_by_id"]:
        reset_unix = int(row["last_reset_at"].timestamp())
        embed.add_field(
            name="Last Reset",
            value=f"<@{row['reset_by_id']}> · <t:{reset_unix}:R>",
            inline=False,
        )
    embed.set_footer(text=f"Stockpile #{row['id']} · Press the button below after refreshing it in-game")
    return embed


class StockpileResetView(discord.ui.View):
    def __init__(self, stockpile_id: int):
        super().__init__(timeout=None)
        self.stockpile_id = stockpile_id
        button = discord.ui.Button(
            label="Reset Timer",
            emoji="🔄",
            style=discord.ButtonStyle.success,
            custom_id=f"stockpile_reset:{stockpile_id}",
        )
        button.callback = self.on_reset
        self.add_item(button)

    async def on_reset(self, interaction: discord.Interaction):
        row = await get_stockpile(self.stockpile_id)
        if not row or not row["active"]:
            await interaction.response.send_message("This stockpile is no longer tracked.", ephemeral=True)
            return
        try:
            await reset_stockpile(self.stockpile_id, interaction.user.id, str(interaction.user))
            row = await get_stockpile(self.stockpile_id)
            await interaction.response.edit_message(embed=build_stockpile_embed(row), view=self)
        except Exception as e:
            print(f"[stockpile] reset failed for #{self.stockpile_id}: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("⚠️ Something went wrong resetting this timer.", ephemeral=True)


class StockpileSelect(discord.ui.Select):
    def __init__(self, rows: list[dict], purpose: str):
        options = [
            discord.SelectOption(
                label=r["name"][:100],
                value=str(r["id"]),
                description=f"Stockpile #{r['id']} · {STOCKPILE_STATUS_EMOJI.get(r['status'], '⚪')} {r['status']}",
            )
            for r in rows
        ]
        super().__init__(placeholder="Choose a stockpile…", options=options)
        self.purpose = purpose

    async def callback(self, interaction: discord.Interaction):
        stockpile_id = int(self.values[0])

        if self.purpose == "history":
            logs = await get_history(stockpile_id)
            if not logs:
                await interaction.response.edit_message(content="No history yet for this stockpile.", view=None)
                return
            lines = [
                f"`{log['action']}` — **{log['actor_name']}** · <t:{int(log['at'].timestamp())}:f>"
                for log in logs
            ]
            await interaction.response.edit_message(content="\n".join(lines), view=None)

        elif self.purpose == "remove":
            row = await get_stockpile(stockpile_id)
            await remove_stockpile(stockpile_id)
            await log_action(stockpile_id, interaction.user.id, str(interaction.user), "removed")
            if row and row["message_id"]:
                channel = interaction.client.get_channel(row["channel_id"])
                if channel:
                    try:
                        msg = await channel.fetch_message(row["message_id"])
                        removed_embed = discord.Embed(
                            title=f"📦 {row['name']} — REMOVED",
                            description="No longer being tracked.",
                            color=discord.Color.greyple(),
                        )
                        await msg.edit(embed=removed_embed, view=None)
                    except (discord.NotFound, discord.Forbidden):
                        pass
            name = row["name"] if row else "stockpile"
            await interaction.response.edit_message(content=f"🗑️ Stopped tracking **{name}**.", view=None)


class StockpileSelectView(discord.ui.View):
    def __init__(self, rows: list[dict], purpose: str):
        super().__init__(timeout=60)
        self.add_item(StockpileSelect(rows, purpose))


# ── Stockpile timers: slash commands ────────────────────────────────────────────
stockpile_group = app_commands.Group(name="stockpile", description="Track private stockpile refresh timers")


@stockpile_group.command(name="create", description="Start tracking a new stockpile timer")
@app_commands.describe(
    name="Name/location of the stockpile (e.g. 'Bridgehead A depot')",
    hours="Hours until it expires if not reset (default 48)",
    warn_hours="Hours remaining at which to start warning (default 6)",
    warn_repeat_minutes="Repeat the warning every N minutes while low (optional; default: warn once)",
    role="Role to ping for warnings (optional; falls back to the server default)",
)
@officer_only()
async def stockpile_create_cmd(
    interaction: discord.Interaction,
    name: str,
    hours: float = 48.0,
    warn_hours: float = 6.0,
    warn_repeat_minutes: int = None,
    role: discord.Role = None,
):
    if not await ensure_db_available(interaction):
        return
    if hours <= 0 or warn_hours <= 0:
        await interaction.response.send_message("❌ `hours` and `warn_hours` must be greater than 0.", ephemeral=True)
        return

    await interaction.response.defer()
    stockpile_id = await create_stockpile(
        guild_id=interaction.guild_id,
        channel_id=interaction.channel_id,
        name=name,
        duration_hours=hours,
        warn_threshold_hours=warn_hours,
        warn_repeat_minutes=warn_repeat_minutes,
        warn_role_id=role.id if role else None,
    )
    await log_action(stockpile_id, interaction.user.id, str(interaction.user), "created")
    row = await get_stockpile(stockpile_id)
    view = StockpileResetView(stockpile_id)
    try:
        msg = await interaction.channel.send(embed=build_stockpile_embed(row), view=view)
    except discord.Forbidden:
        await remove_stockpile(stockpile_id)
        await interaction.followup.send(
            f"⚠️ I don't have permission to post in {interaction.channel.mention}. "
            "Give me **View Channel**, **Send Messages**, and **Embed Links** permissions there, "
            "then run `/stockpile create` again.",
            ephemeral=True,
        )
        return
    await set_message_id(stockpile_id, msg.id)
    bot.add_view(view, message_id=msg.id)
    await interaction.followup.send(f"✅ Now tracking **{name}**.", ephemeral=True)


@stockpile_group.command(name="list", description="List tracked stockpiles in this server")
async def stockpile_list_cmd(interaction: discord.Interaction):
    if not await ensure_db_available(interaction):
        return
    rows = await list_stockpiles(interaction.guild_id)
    if not rows:
        await interaction.response.send_message(
            "No stockpiles are being tracked yet. Use `/stockpile create`.", ephemeral=True,
        )
        return
    lines = []
    for r in rows:
        expires_at = r["last_reset_at"] + timedelta(hours=r["duration_hours"])
        unix = int(expires_at.timestamp())
        lines.append(
            f"{STOCKPILE_STATUS_EMOJI.get(r['status'], '⚪')} **{r['name']}** — <t:{unix}:R> · <#{r['channel_id']}>"
        )
    embed = discord.Embed(title="📦 Tracked Stockpiles", description="\n".join(lines), color=discord.Color.blurple())
    await interaction.response.send_message(embed=embed, ephemeral=True)


@stockpile_group.command(name="history", description="View recent reset history for a stockpile")
async def stockpile_history_cmd(interaction: discord.Interaction):
    if not await ensure_db_available(interaction):
        return
    rows = await list_stockpiles(interaction.guild_id)
    if not rows:
        await interaction.response.send_message("No stockpiles tracked yet.", ephemeral=True)
        return
    await interaction.response.send_message(
        "Pick a stockpile:", view=StockpileSelectView(rows, "history"), ephemeral=True,
    )


@stockpile_group.command(name="remove", description="[Admin] Stop tracking a stockpile")
@app_commands.checks.has_permissions(administrator=True)
async def stockpile_remove_cmd(interaction: discord.Interaction):
    if not await ensure_db_available(interaction):
        return
    rows = await list_stockpiles(interaction.guild_id)
    if not rows:
        await interaction.response.send_message("No stockpiles tracked yet.", ephemeral=True)
        return
    await interaction.response.send_message(
        "Pick a stockpile to remove:", view=StockpileSelectView(rows, "remove"), ephemeral=True,
    )


@stockpile_group.command(name="set_default_role", description="[Admin] Set the default role pinged for stockpile warnings")
@app_commands.describe(role="The role to ping when a stockpile needs attention")
@app_commands.checks.has_permissions(administrator=True)
async def stockpile_set_default_role_cmd(interaction: discord.Interaction, role: discord.Role):
    if not await ensure_db_available(interaction):
        return
    await set_default_role(interaction.guild_id, role.id)
    await interaction.response.send_message(
        f"✅ {role.mention} will be pinged for stockpile warnings by default.", ephemeral=True,
    )


tree.add_command(stockpile_group)


# ── Stockpile timers: background watcher ────────────────────────────────────────
@tasks.loop(minutes=3)
async def check_stockpiles():
    try:
        rows = await list_all_active_stockpiles()
    except Exception as e:
        print(f"[stockpile] failed to fetch stockpiles: {e}")
        return

    now = datetime.now(timezone.utc)
    for row in rows:
        expires_at = row["last_reset_at"] + timedelta(hours=row["duration_hours"])
        remaining_seconds = (expires_at - now).total_seconds()

        if remaining_seconds <= 0:
            new_status = "expired"
        elif remaining_seconds <= row["warn_threshold_hours"] * 3600:
            new_status = "warning"
        else:
            new_status = "ok"

        should_warn = False
        if new_status in ("warning", "expired"):
            if row["last_warned_at"] is None:
                should_warn = True
            elif row["warn_repeat_minutes"]:
                elapsed_minutes = (now - row["last_warned_at"]).total_seconds() / 60
                if elapsed_minutes >= row["warn_repeat_minutes"]:
                    should_warn = True

        if new_status != row["status"]:
            await set_status(row["id"], new_status)
            if row["message_id"]:
                channel = bot.get_channel(row["channel_id"])
                if channel:
                    try:
                        msg = await channel.fetch_message(row["message_id"])
                        updated_row = dict(row)
                        updated_row["status"] = new_status
                        await msg.edit(embed=build_stockpile_embed(updated_row))
                    except (discord.NotFound, discord.Forbidden):
                        pass

        if should_warn:
            channel = bot.get_channel(row["channel_id"])
            if channel:
                role_id = row["warn_role_id"] or await get_default_role(row["guild_id"])
                mention = f"<@&{role_id}>" if role_id else ""
                unix = int(expires_at.timestamp())
                if new_status == "expired":
                    body = f"🔴 **{row['name']}** stockpile timer has EXPIRED (was due <t:{unix}:R>) — it may already be gone!"
                else:
                    body = f"🟡 **{row['name']}** stockpile timer expires <t:{unix}:R> — someone needs to refresh it in-game."
                if not role_id:
                    body += "\n*(No warning role configured — an admin can run `/stockpile set_default_role`.)*"
                text = f"{mention} {body}".strip()
                try:
                    await channel.send(text)
                except discord.Forbidden:
                    pass
            await set_last_warned(row["id"])


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        raise ValueError("Set the DISCORD_TOKEN environment variable.")
    bot.run(TOKEN)
