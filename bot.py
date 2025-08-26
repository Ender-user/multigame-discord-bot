import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import random
import asyncio
import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv  # <-- très important
import os

# Configuration du bot
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Données en mémoire (dans un vrai bot, utilisez une base de données)
user_data = {}
guild_settings = {}
muted_users = {}
banned_users = {}

# Système de sauvegarde
def save_data():
    with open('bot_data.json', 'w') as f:
        json.dump({
            'user_data': user_data, 
            'guild_settings': guild_settings,
            'muted_users': muted_users,
            'banned_users': banned_users
        }, f)

def load_data():
    # Si le fichier n'existe pas, le créer vide
    if not os.path.exists("bot_data.json"):
        with open("bot_data.json", "w") as f:
            json.dump({}, f)

    # Lire le JSON
    with open("bot_data.json", "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {}  # Si le fichier est vide ou mal formé, on retourne un objet vide
    return data

# Initialisation des données utilisateur
def init_user(user_id: str, guild_id: str):
    if user_id not in user_data:
        user_data[user_id] = {}
    if guild_id not in user_data[user_id]:
        user_data[user_id][guild_id] = {
            'xp': 0,
            'level': 1,
            'messages_sent': 0,
            'last_xp_time': None,
            'total_xp_gained': 0,
            'join_date': datetime.datetime.now().isoformat()
        }

# Calcul du niveau basé sur l'XP (comme DraftBot)
def calculate_level(xp):
    # Formule similaire à DraftBot
    level = 0
    xp_needed = 0
    while xp_needed <= xp:
        level += 1
        xp_needed += level * 100
    return max(1, level - 1)

def xp_for_level(level):
    total = 0
    for i in range(1, level + 1):
        total += i * 100
    return total

def xp_for_next_level(current_level):
    return (current_level + 1) * 100

# Événements du bot
@bot.event
async def on_ready():
    print(f'🤖 {bot.user} est connecté et prêt!')
    load_data()
    
    # Synchronisation des commandes slash
    try:
        synced = await bot.tree.sync()
        print(f'✅ {len(synced)} commande(s) slash synchronisée(s)')
    except Exception as e:
        print(f'❌ Erreur lors de la synchronisation: {e}')
    
    # Démarrage des tâches
    save_data_task.start()
    check_temp_punishments.start()
    
    # Statut du bot
    await bot.change_presence(
        activity=discord.Streaming(
            name="Version 0.1.0",
            url="https://www.twitch.tv/flexingseal"
        )
    )


@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    
    user_id = str(message.author.id)
    guild_id = str(message.guild.id)
    init_user(user_id, guild_id)
    
    # Vérifier si l'utilisateur est mute
    mute_key = f"{guild_id}_{user_id}"
    if mute_key in muted_users:
        try:
            await message.delete()
        except:
            pass
        return
    
    # Système d'XP avec cooldown (comme DraftBot)
    now = datetime.datetime.now()
    last_xp_time = user_data[user_id][guild_id].get('last_xp_time')
    
    if last_xp_time:
        last_time = datetime.datetime.fromisoformat(last_xp_time)
        if (now - last_time).total_seconds() < 60:  # Cooldown de 60 secondes
            await bot.process_commands(message)
            return
    
    # Gain d'XP aléatoire
    xp_gain = random.randint(15, 25)
    user_data[user_id][guild_id]['xp'] += xp_gain
    user_data[user_id][guild_id]['total_xp_gained'] += xp_gain
    user_data[user_id][guild_id]['messages_sent'] += 1
    user_data[user_id][guild_id]['last_xp_time'] = now.isoformat()
    
    # Vérification level up
    old_level = user_data[user_id][guild_id]['level']
    new_level = calculate_level(user_data[user_id][guild_id]['xp'])
    user_data[user_id][guild_id]['level'] = new_level
    
    # Notification de level up
    if new_level > old_level:
        embed = discord.Embed(
            title="🎉 Niveau supérieur atteint!",
            description=f"Félicitations {message.author.mention}!",
            color=0x00ff88
        )
        embed.add_field(
            name="📈 Nouveau niveau", 
            value=f"**{new_level}**", 
            inline=True
        )
        embed.add_field(
            name="⭐ XP total", 
            value=f"**{user_data[user_id][guild_id]['xp']}**", 
            inline=True
        )
        embed.add_field(
            name="🎁 Récompense", 
            value=f"+{new_level * 50} coins", 
            inline=True
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text=f"Bravo pour ce niveau {new_level}!")
        
        await message.channel.send(embed=embed)
    
    await bot.process_commands(message)

# Commandes Slash

@bot.tree.command(name="help", description="Affiche toutes les commandes disponibles")
async def help_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📚 Commandes disponibles",
        description="Voici toutes les commandes disponibles du bot:",
        color=0x3498db
    )
    
    commands_info = [
        ("👤 **Profil & XP**", "`/profile` - Voir son profil\n`/rank` - Voir son rang\n`/leaderboard` - Classement du serveur"),
        ("🔨 **Modération**", "`/ban` - Bannir un membre\n`/tempban` - Ban temporaire\n`/mute` - Rendre muet temporairement\n`/unmute` - Démute un membre"),
        ("⚠️ **Avertissements**", "`/warn` - Avertir un membre\n`/warnings` - Voir les avertissements\n`/clearwarns` - Effacer les avertissements"),
        ("ℹ️ **Utilitaires**", "`/help` - Cette aide\n`/serverinfo` - Infos du serveur\n`/userinfo` - Infos d'un utilisateur")
    ]
    
    for category, commands in commands_info:
        embed.add_field(name=category, value=commands, inline=False)
    
    embed.set_footer(text="MultiGame Bot")
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="profile", description="Affiche le profil d'un utilisateur")
@app_commands.describe(user="L'utilisateur dont vous voulez voir le profil")
async def profile_slash(interaction: discord.Interaction, user: discord.Member = None):
    if user is None:
        user = interaction.user
    
    user_id = str(user.id)
    guild_id = str(interaction.guild.id)
    init_user(user_id, guild_id)
    
    data = user_data[user_id][guild_id]
    current_level = data['level']
    current_xp = data['xp']
    xp_for_current = xp_for_level(current_level - 1) if current_level > 1 else 0
    xp_for_next = xp_for_level(current_level)
    xp_progress = current_xp - xp_for_current
    xp_needed = xp_for_next - xp_for_current
    
    # Barre de progression
    progress_percentage = (xp_progress / xp_needed) * 100 if xp_needed > 0 else 100
    progress_bar = "▓" * int(progress_percentage // 10) + "░" * (10 - int(progress_percentage // 10))
    
    embed = discord.Embed(
        title=f"📊 Profil de {user.display_name}",
        color=0x9b59b6
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    
    embed.add_field(name="📈 Niveau", value=f"**{current_level}**", inline=True)
    embed.add_field(name="⭐ XP", value=f"**{current_xp:,}**", inline=True)
    embed.add_field(name="💬 Messages", value=f"**{data['messages_sent']:,}**", inline=True)
    
    embed.add_field(
        name="🎯 Progression vers le niveau suivant",
        value=f"`{progress_bar}` **{progress_percentage:.1f}%**\n{xp_progress:,}/{xp_needed:,} XP",
        inline=False
    )
    
    # Calcul du rang
    all_users = []
    for uid, guilds in user_data.items():
        if guild_id in guilds:
            all_users.append((uid, guilds[guild_id]['xp']))
    
    all_users.sort(key=lambda x: x[1], reverse=True)
    rank = next((i + 1 for i, (uid, _) in enumerate(all_users) if uid == user_id), "N/A")
    
    embed.add_field(name="🏆 Rang sur le serveur", value=f"**#{rank}**", inline=True)
    embed.add_field(name="📅 Membre depuis", value=f"<t:{int(user.joined_at.timestamp())}:D>", inline=True)
    embed.add_field(name="🎲 XP total gagné", value=f"**{data['total_xp_gained']:,}**", inline=True)
    
    embed.set_footer(text=f"ID: {user.id}")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="Affiche le classement XP du serveur")
async def leaderboard_slash(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    
    # Récupérer tous les utilisateurs du serveur
    server_users = []
    for user_id, guilds in user_data.items():
        if guild_id in guilds:
            try:
                member = interaction.guild.get_member(int(user_id))
                if member:
                    server_users.append((user_id, guilds[guild_id], member))
            except:
                continue
    
    # Trier par XP
    server_users.sort(key=lambda x: x[1]['xp'], reverse=True)
    
    embed = discord.Embed(
        title=f"🏆 Classement XP - {interaction.guild.name}",
        description="Top 10 des utilisateurs avec le plus d'XP",
        color=0xf1c40f
    )
    
    for i, (user_id, data, member) in enumerate(server_users[:10]):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"**{i+1}.**"
        embed.add_field(
            name=f"{medal} {member.display_name}",
            value=f"Niveau **{data['level']}** • **{data['xp']:,}** XP\n💬 {data['messages_sent']:,} messages",
            inline=False
        )
    
    embed.set_footer(text=f"Total: {len(server_users)} utilisateurs classés")
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    
    await interaction.response.send_message(embed=embed)

# Commandes de modération

@bot.tree.command(name="ban", description="Bannir un membre du serveur")
@app_commands.describe(
    user="Le membre à bannir",
    reason="Raison du bannissement"
)
async def ban_slash(interaction: discord.Interaction, user: discord.Member, reason: str = "Aucune raison spécifiée"):
    if not interaction.user.guild_permissions.ban_members:
        embed = discord.Embed(
            title="❌ Permission manquante",
            description="Vous n'avez pas la permission de bannir des membres.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        embed = discord.Embed(
            title="❌ Hiérarchie insuffisante",
            description="Vous ne pouvez pas bannir ce membre (rôle supérieur ou égal).",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    try:
        # Essayer d'envoyer un MP à l'utilisateur
        try:
            dm_embed = discord.Embed(
                title="🔨 Vous avez été banni",
                description=f"Vous avez été banni de **{interaction.guild.name}**",
                color=0xff0000
            )
            dm_embed.add_field(name="Raison", value=reason, inline=False)
            dm_embed.add_field(name="Modérateur", value=interaction.user.mention, inline=False)
            await user.send(embed=dm_embed)
        except:
            pass
        
        await user.ban(reason=f"{reason} | Par: {interaction.user}")
        
        embed = discord.Embed(
            title="🔨 Membre banni",
            description=f"**{user}** a été banni du serveur",
            color=0xff0000
        )
        embed.add_field(name="👤 Utilisateur", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="🛡️ Modérateur", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Raison", value=reason, inline=False)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.timestamp = datetime.datetime.now()
        
        await interaction.response.send_message(embed=embed)
        
    except discord.Forbidden:
        embed = discord.Embed(
            title="❌ Erreur",
            description="Je n'ai pas les permissions pour bannir ce membre.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="tempban", description="Bannir temporairement un membre")
@app_commands.describe(
    user="Le membre à bannir temporairement",
    duration="Durée (ex: 1h, 1d, 1w)",
    reason="Raison du bannissement"
)
async def tempban_slash(interaction: discord.Interaction, user: discord.Member, duration: str, reason: str = "Aucune raison spécifiée"):
    if not interaction.user.guild_permissions.ban_members:
        embed = discord.Embed(
            title="❌ Permission manquante",
            description="Vous n'avez pas la permission de bannir des membres.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Parser la durée
    duration_seconds = parse_duration(duration)
    if duration_seconds is None:
        embed = discord.Embed(
            title="❌ Durée invalide",
            description="Format valide: 1h, 1d, 1w (h=heures, d=jours, w=semaines)",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    unban_time = datetime.datetime.now() + datetime.timedelta(seconds=duration_seconds)
    
    try:
        # MP à l'utilisateur
        try:
            dm_embed = discord.Embed(
                title="⏰ Bannissement temporaire",
                description=f"Vous avez été banni temporairement de **{interaction.guild.name}**",
                color=0xff9900
            )
            dm_embed.add_field(name="Durée", value=duration, inline=True)
            dm_embed.add_field(name="Fin du ban", value=f"<t:{int(unban_time.timestamp())}:F>", inline=True)
            dm_embed.add_field(name="Raison", value=reason, inline=False)
            await user.send(embed=dm_embed)
        except:
            pass
        
        await user.ban(reason=f"[TEMP] {reason} | Durée: {duration} | Par: {interaction.user}")
        
        # Enregistrer le ban temporaire
        ban_key = f"{interaction.guild.id}_{user.id}"
        banned_users[ban_key] = {
            'user_id': user.id,
            'guild_id': interaction.guild.id,
            'unban_time': unban_time.isoformat(),
            'reason': reason,
            'moderator': interaction.user.id
        }
        
        embed = discord.Embed(
            title="⏰ Bannissement temporaire",
            description=f"**{user}** a été banni temporairement",
            color=0xff9900
        )
        embed.add_field(name="👤 Utilisateur", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="🛡️ Modérateur", value=interaction.user.mention, inline=True)
        embed.add_field(name="⏱️ Durée", value=duration, inline=True)
        embed.add_field(name="🔚 Fin du ban", value=f"<t:{int(unban_time.timestamp())}:F>", inline=True)
        embed.add_field(name="📝 Raison", value=reason, inline=False)
        embed.set_thumbnail(url=user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)
        
    except discord.Forbidden:
        embed = discord.Embed(
            title="❌ Erreur",
            description="Je n'ai pas les permissions pour bannir ce membre.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="mute", description="Rendre muet un membre temporairement")
@app_commands.describe(
    user="Le membre à rendre muet",
    duration="Durée (ex: 10m, 1h, 1d)",
    reason="Raison du mute"
)
async def mute_slash(interaction: discord.Interaction, user: discord.Member, duration: str, reason: str = "Aucune raison spécifiée"):
    if not interaction.user.guild_permissions.moderate_members:
        embed = discord.Embed(
            title="❌ Permission manquante",
            description="Vous n'avez pas la permission de modérer les membres.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    duration_seconds = parse_duration(duration)
    if duration_seconds is None:
        embed = discord.Embed(
            title="❌ Durée invalide",
            description="Format valide: 10m, 1h, 1d (m=minutes, h=heures, d=jours)",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    unmute_time = datetime.datetime.now() + datetime.timedelta(seconds=duration_seconds)
    
    try:
        await user.timeout(until=unmute_time, reason=f"{reason} | Par: {interaction.user}")
        
        # Enregistrer le mute
        mute_key = f"{interaction.guild.id}_{user.id}"
        muted_users[mute_key] = {
            'user_id': user.id,
            'guild_id': interaction.guild.id,
            'unmute_time': unmute_time.isoformat(),
            'reason': reason,
            'moderator': interaction.user.id
        }
        
        embed = discord.Embed(
            title="🔇 Membre rendu muet",
            description=f"**{user.display_name}** a été rendu muet",
            color=0xff9900
        )
        embed.add_field(name="👤 Utilisateur", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="🛡️ Modérateur", value=interaction.user.mention, inline=True)
        embed.add_field(name="⏱️ Durée", value=duration, inline=True)
        embed.add_field(name="🔚 Fin du mute", value=f"<t:{int(unmute_time.timestamp())}:F>", inline=True)
        embed.add_field(name="📝 Raison", value=reason, inline=False)
        embed.set_thumbnail(url=user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)
        
        # MP à l'utilisateur
        try:
            dm_embed = discord.Embed(
                title="🔇 Vous avez été rendu muet",
                description=f"Vous avez été rendu muet sur **{interaction.guild.name}**",
                color=0xff9900
            )
            dm_embed.add_field(name="Durée", value=duration, inline=True)
            dm_embed.add_field(name="Fin du mute", value=f"<t:{int(unmute_time.timestamp())}:F>", inline=True)
            dm_embed.add_field(name="Raison", value=reason, inline=False)
            await user.send(embed=dm_embed)
        except:
            pass
            
    except discord.Forbidden:
        embed = discord.Embed(
            title="❌ Erreur",
            description="Je n'ai pas les permissions pour mute ce membre.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="unmute", description="Démute un membre")
@app_commands.describe(user="Le membre à démute")
async def unmute_slash(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.moderate_members:
        embed = discord.Embed(
            title="❌ Permission manquante",
            description="Vous n'avez pas la permission de modérer les membres.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    try:
        await user.timeout(until=None, reason=f"Démute par: {interaction.user}")
        
        # Supprimer le mute enregistré
        mute_key = f"{interaction.guild.id}_{user.id}"
        if mute_key in muted_users:
            del muted_users[mute_key]
        
        embed = discord.Embed(
            title="🔊 Membre démuté",
            description=f"**{user.display_name}** peut à nouveau parler",
            color=0x00ff88
        )
        embed.add_field(name="👤 Utilisateur", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="🛡️ Modérateur", value=interaction.user.mention, inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)
        
    except discord.Forbidden:
        embed = discord.Embed(
            title="❌ Erreur",
            description="Je n'ai pas les permissions pour démute ce membre.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="warn", description="Avertir un membre")
@app_commands.describe(
    user="Le membre à avertir",
    reason="Raison de l'avertissement"
)
async def warn_slash(interaction: discord.Interaction, user: discord.Member, reason: str = "Aucune raison spécifiée"):
    if not interaction.user.guild_permissions.manage_messages:
        embed = discord.Embed(
            title="❌ Permission manquante",
            description="Vous n'avez pas la permission de gérer les messages.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    user_id = str(user.id)
    guild_id = str(interaction.guild.id)
    init_user(user_id, guild_id)
    
    # Ajouter l'avertissement
    if 'warnings' not in user_data[user_id][guild_id]:
        user_data[user_id][guild_id]['warnings'] = []
    
    warning = {
        'reason': reason,
        'moderator': interaction.user.id,
        'date': datetime.datetime.now().isoformat(),
        'id': len(user_data[user_id][guild_id]['warnings']) + 1
    }
    
    user_data[user_id][guild_id]['warnings'].append(warning)
    warn_count = len(user_data[user_id][guild_id]['warnings'])
    
    embed = discord.Embed(
        title="⚠️ Avertissement donné",
        description=f"**{user.display_name}** a reçu un avertissement",
        color=0xff9900
    )
    embed.add_field(name="👤 Utilisateur", value=f"{user.mention} (`{user.id}`)", inline=True)
    embed.add_field(name="🛡️ Modérateur", value=interaction.user.mention, inline=True)
    embed.add_field(name="🔢 Total d'avertissements", value=f"**{warn_count}**", inline=True)
    embed.add_field(name="📝 Raison", value=reason, inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.timestamp = datetime.datetime.now()
    
    await interaction.response.send_message(embed=embed)
    
    # MP à l'utilisateur
    try:
        dm_embed = discord.Embed(
            title="⚠️ Avertissement reçu",
            description=f"Vous avez reçu un avertissement sur **{interaction.guild.name}**",
            color=0xff9900
        )
        dm_embed.add_field(name="Raison", value=reason, inline=False)
        dm_embed.add_field(name="Modérateur", value=str(interaction.user), inline=False)
        dm_embed.add_field(name="Total d'avertissements", value=f"{warn_count}", inline=False)
        await user.send(embed=dm_embed)
    except:
        pass

# Fonctions utilitaires
def parse_duration(duration_str):
    """Parse une durée comme '1h', '30m', '7d'"""
    import re
    match = re.match(r'(\d+)([mhdw])', duration_str.lower())
    if not match:
        return None
    
    amount = int(match.group(1))
    unit = match.group(2)
    
    multipliers = {
        'm': 60,           # minutes
        'h': 3600,         # heures
        'd': 86400,        # jours
        'w': 604800        # semaines
    }
    
    return amount * multipliers.get(unit, 0)

# Tâches automatiques
@tasks.loop(minutes=1)
async def check_temp_punishments():
    """Vérifier les bans/mutes temporaires"""
    now = datetime.datetime.now()
    
    # Vérifier les bans temporaires
    to_unban = []
    for ban_key, ban_data in banned_users.items():
        unban_time = datetime.datetime.fromisoformat(ban_data['unban_time'])
        if now >= unban_time:
            to_unban.append(ban_key)
            try:
                guild = bot.get_guild(ban_data['guild_id'])
                if guild:
                    await guild.unban(discord.Object(id=ban_data['user_id']), reason="Fin du bannissement temporaire")
            except:
                pass
    
    for ban_key in to_unban:
        del banned_users[ban_key]
    
    # Vérifier les mutes temporaires
    to_unmute = []
    for mute_key, mute_data in muted_users.items():
        unmute_time = datetime.datetime.fromisoformat(mute_data['unmute_time'])
        if now >= unmute_time:
            to_unmute.append(mute_key)
            try:
                guild = bot.get_guild(mute_data['guild_id'])
                user = guild.get_member(mute_data['user_id'])
                if guild and user:
                    await user.timeout(until=None, reason="Fin du mute temporaire")
            except:
                pass
    
    for mute_key in to_unmute:
        del muted_users[mute_key]

@tasks.loop(minutes=5)
async def save_data_task():
    """Sauvegarde automatique des données"""
    save_data()

# Commandes d'avertissements supplémentaires

@bot.tree.command(name="warnings", description="Voir les avertissements d'un membre")
@app_commands.describe(user="Le membre dont voir les avertissements")
async def warnings_slash(interaction: discord.Interaction, user: discord.Member = None):
    if user is None:
        user = interaction.user
    
    user_id = str(user.id)
    guild_id = str(interaction.guild.id)
    init_user(user_id, guild_id)
    
    warnings = user_data[user_id][guild_id].get('warnings', [])
    
    if not warnings:
        embed = discord.Embed(
            title="✅ Aucun avertissement",
            description=f"**{user.display_name}** n'a aucun avertissement sur ce serveur.",
            color=0x00ff88
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        await interaction.response.send_message(embed=embed)
        return
    
    embed = discord.Embed(
        title=f"⚠️ Avertissements de {user.display_name}",
        description=f"**{len(warnings)}** avertissement(s) au total",
        color=0xff9900
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    
    for i, warning in enumerate(warnings[:10], 1):  # Limiter à 10 pour éviter les embeds trop longs
        try:
            moderator = bot.get_user(warning['moderator'])
            mod_name = moderator.name if moderator else "Modérateur inconnu"
        except:
            mod_name = "Modérateur inconnu"
        
        date = datetime.datetime.fromisoformat(warning['date'])
        embed.add_field(
            name=f"#{warning['id']} • {mod_name}",
            value=f"**Raison:** {warning['reason']}\n**Date:** <t:{int(date.timestamp())}:d>",
            inline=False
        )
    
    if len(warnings) > 10:
        embed.set_footer(text=f"... et {len(warnings) - 10} autre(s) avertissement(s)")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clearwarns", description="Effacer tous les avertissements d'un membre")
@app_commands.describe(user="Le membre dont effacer les avertissements")
async def clearwarns_slash(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.manage_messages:
        embed = discord.Embed(
            title="❌ Permission manquante",
            description="Vous n'avez pas la permission de gérer les messages.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    user_id = str(user.id)
    guild_id = str(interaction.guild.id)
    init_user(user_id, guild_id)
    
    old_warnings = len(user_data[user_id][guild_id].get('warnings', []))
    user_data[user_id][guild_id]['warnings'] = []
    
    embed = discord.Embed(
        title="🗑️ Avertissements effacés",
        description=f"Tous les avertissements de **{user.display_name}** ont été effacés",
        color=0x00ff88
    )
    embed.add_field(name="👤 Utilisateur", value=f"{user.mention} (`{user.id}`)", inline=True)
    embed.add_field(name="🛡️ Modérateur", value=interaction.user.mention, inline=True)
    embed.add_field(name="🔢 Avertissements effacés", value=f"**{old_warnings}**", inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

# Commandes d'informations

@bot.tree.command(name="userinfo", description="Affiche les informations d'un utilisateur")
@app_commands.describe(user="L'utilisateur dont voir les informations")
async def userinfo_slash(interaction: discord.Interaction, user: discord.Member = None):
    if user is None:
        user = interaction.user
    
    embed = discord.Embed(
        title=f"👤 Informations de {user.display_name}",
        color=user.color if user.color != discord.Color.default() else 0x3498db
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    
    # Informations de base
    embed.add_field(name="🆔 ID", value=f"`{user.id}`", inline=True)
    embed.add_field(name="📅 Compte créé", value=f"<t:{int(user.created_at.timestamp())}:D>", inline=True)
    embed.add_field(name="📅 A rejoint", value=f"<t:{int(user.joined_at.timestamp())}:D>", inline=True)
    
    # Statut et activité
    status_emojis = {
        discord.Status.online: "🟢 En ligne",
        discord.Status.idle: "🟡 Absent",
        discord.Status.dnd: "🔴 Ne pas déranger",
        discord.Status.offline: "⚫ Hors ligne"
    }
    embed.add_field(name="📊 Statut", value=status_emojis.get(user.status, "❓ Inconnu"), inline=True)
    
    # Rôles
    if len(user.roles) > 1:  # Exclure @everyone
        roles = [role.mention for role in user.roles[1:]][:10]  # Limiter à 10 rôles
        roles_text = ", ".join(roles)
        if len(user.roles) > 11:
            roles_text += f" et {len(user.roles) - 11} autre(s)..."
        embed.add_field(name=f"🎭 Rôles ({len(user.roles) - 1})", value=roles_text, inline=False)
    
    # Permissions importantes
    perms = user.guild_permissions
    important_perms = []
    if perms.administrator:
        important_perms.append("👑 Administrateur")
    elif perms.manage_guild:
        important_perms.append("🛠️ Gérer le serveur")
    elif perms.manage_channels:
        important_perms.append("📝 Gérer les channels")
    elif perms.manage_messages:
        important_perms.append("💬 Gérer les messages")
    elif perms.ban_members:
        important_perms.append("🔨 Bannir des membres")
    elif perms.kick_members:
        important_perms.append("👢 Expulser des membres")
    
    if important_perms:
        embed.add_field(name="🔑 Permissions importantes", value="\n".join(important_perms), inline=False)
    
    # Informations XP si disponible
    user_id = str(user.id)
    guild_id = str(interaction.guild.id)
    if user_id in user_data and guild_id in user_data[user_id]:
        data = user_data[user_id][guild_id]
        embed.add_field(name="📊 Niveau", value=f"**{data['level']}**", inline=True)
        embed.add_field(name="⭐ XP", value=f"**{data['xp']:,}**", inline=True)
        embed.add_field(name="💬 Messages", value=f"**{data['messages_sent']:,}**", inline=True)
    
    embed.set_footer(text=f"Demandé par {interaction.user.display_name}")
    embed.timestamp = datetime.datetime.now()
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="info", description="Affiche un message embed")
async def info(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Information",
        description="Voici un exemple d'embed envoyé par une commande slash",
        color=discord.Color.blue()
    )
    embed.add_field(name="Auteur", value=interaction.user.mention)
    embed.set_footer(text="Footer de l'embed")
    embed.set_thumbnail(url="https://i.imgur.com/9B6F2GZ.png")  # Exemple d'image

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Affiche les informations du serveur")
async def serverinfo_slash(interaction: discord.Interaction):
    guild = interaction.guild
    
    embed = discord.Embed(
        title=f"🏰 Informations de {guild.name}",
        color=0x3498db
    )
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    # Informations de base
    embed.add_field(name="🆔 ID", value=f"`{guild.id}`", inline=True)
    embed.add_field(name="👑 Propriétaire", value=guild.owner.mention if guild.owner else "Inconnu", inline=True)
    embed.add_field(name="📅 Créé le", value=f"<t:{int(guild.created_at.timestamp())}:D>", inline=True)
    
    # Statistiques des membres
    humans = len([m for m in guild.members if not m.bot])
    bots = len([m for m in guild.members if m.bot])
    
    embed.add_field(name="👥 Membres", value=f"**{guild.member_count}** total", inline=True)
    embed.add_field(name="👤 Humains", value=f"**{humans}**", inline=True)
    embed.add_field(name="🤖 Bots", value=f"**{bots}**", inline=True)
    
    # Channels
    text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
    voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
    categories = len(guild.categories)
    
    embed.add_field(name="💬 Salons texte", value=f"**{text_channels}**", inline=True)
    embed.add_field(name="🔊 Salons vocaux", value=f"**{voice_channels}**", inline=True)
    embed.add_field(name="📁 Catégories", value=f"**{categories}**", inline=True)
    
    # Autres infos
    embed.add_field(name="🎭 Rôles", value=f"**{len(guild.roles)}**", inline=True)
    embed.add_field(name="😀 Émojis", value=f"**{len(guild.emojis)}**", inline=True)
    embed.add_field(name="🔒 Niveau de vérification", value=f"**{str(guild.verification_level).title()}**", inline=True)
    
    # Boosts
    if guild.premium_tier > 0:
        embed.add_field(
            name="💎 Niveau de boost", 
            value=f"**Niveau {guild.premium_tier}** ({guild.premium_subscription_count} boost(s))", 
            inline=False
        )
    
    # Statistiques du bot sur ce serveur
    guild_id = str(guild.id)
    guild_users = sum(1 for user_id, guilds in user_data.items() if guild_id in guilds)
    total_xp = sum(guilds[guild_id]['xp'] for user_id, guilds in user_data.items() if guild_id in guilds)
    
    if guild_users > 0:
        embed.add_field(
            name="📊 Statistiques du bot",
            value=f"**{guild_users}** utilisateur(s) enregistré(s)\n**{total_xp:,}** XP total sur le serveur",
            inline=False
        )
    
    embed.set_footer(text=f"Demandé par {interaction.user.display_name}")
    embed.timestamp = datetime.datetime.now()
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rank", description="Affiche votre rang sur le serveur")
async def rank_slash(interaction: discord.Interaction, user: discord.Member = None):
    if user is None:
        user = interaction.user
    
    user_id = str(user.id)
    guild_id = str(interaction.guild.id)
    init_user(user_id, guild_id)
    
    # Calculer le rang
    all_users = []
    for uid, guilds in user_data.items():
        if guild_id in guilds:
            all_users.append((uid, guilds[guild_id]['xp'], guilds[guild_id]['level']))
    
    all_users.sort(key=lambda x: x[1], reverse=True)  # Trier par XP
    
    user_rank = next((i + 1 for i, (uid, _, _) in enumerate(all_users) if uid == user_id), None)
    
    if user_rank is None:
        embed = discord.Embed(
            title="❌ Aucune données",
            description="Aucune donnée trouvée pour cet utilisateur.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    data = user_data[user_id][guild_id]
    current_level = data['level']
    current_xp = data['xp']
    xp_for_current = xp_for_level(current_level - 1) if current_level > 1 else 0
    xp_for_next = xp_for_level(current_level)
    xp_progress = current_xp - xp_for_current
    xp_needed = xp_for_next - xp_for_current
    
    progress_percentage = (xp_progress / xp_needed) * 100 if xp_needed > 0 else 100
    
    # Émojis de rang
    rank_emoji = "🥇" if user_rank == 1 else "🥈" if user_rank == 2 else "🥉" if user_rank == 3 else "🏅"
    
    embed = discord.Embed(
        title=f"{rank_emoji} Rang de {user.display_name}",
        description=f"Position **#{user_rank}** sur {len(all_users)} utilisateurs",
        color=0xf1c40f if user_rank <= 3 else 0x3498db
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    
    embed.add_field(name="📈 Niveau", value=f"**{current_level}**", inline=True)
    embed.add_field(name="⭐ XP Total", value=f"**{current_xp:,}**", inline=True)
    embed.add_field(name="🏆 Rang", value=f"**#{user_rank}**", inline=True)
    
    # Barre de progression stylée
    filled = int(progress_percentage // 10)
    empty = 10 - filled
    progress_bar = "🟦" * filled + "⬜" * empty
    
    embed.add_field(
        name="📊 Progression vers le niveau suivant",
        value=f"{progress_bar}\n**{progress_percentage:.1f}%** • {xp_progress:,}/{xp_needed:,} XP",
        inline=False
    )
    
    embed.add_field(name="💬 Messages envoyés", value=f"**{data['messages_sent']:,}**", inline=True)
    embed.add_field(name="🎯 XP total gagné", value=f"**{data['total_xp_gained']:,}**", inline=True)
    
    # Différence avec le joueur suivant/précédent
    if user_rank > 1:
        prev_user_xp = all_users[user_rank - 2][1]
        xp_diff = prev_user_xp - current_xp
        embed.add_field(name="⬆️ XP pour le rang supérieur", value=f"**{xp_diff:,}** XP", inline=True)
    
    embed.set_footer(text=f"Continuez à envoyer des messages pour gagner de l'XP!")
    
    await interaction.response.send_message(embed=embed)

# Gestion d'erreurs globale
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        embed = discord.Embed(
            title="❌ Permissions manquantes",
            description="Vous n'avez pas les permissions nécessaires pour utiliser cette commande.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif isinstance(error, app_commands.CommandOnCooldown):
        embed = discord.Embed(
            title="⏰ Cooldown",
            description=f"Cette commande est en cooldown. Réessayez dans {error.retry_after:.1f} secondes.",
            color=0xff9900
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif isinstance(error, app_commands.BotMissingPermissions):
        embed = discord.Embed(
            title="❌ Bot sans permissions",
            description="Je n'ai pas les permissions nécessaires pour exécuter cette commande.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(
            title="❌ Erreur",
            description="Une erreur s'est produite lors de l'exécution de la commande.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        print(f"Erreur de commande slash: {error}")

# Événement pour les nouveaux membres
@bot.event
async def on_member_join(member):
    # Initialiser les données du nouvel utilisateur
    user_id = str(member.id)
    guild_id = str(member.guild.id)
    init_user(user_id, guild_id)
    
    # Message de bienvenue (optionnel)
    if guild_id in guild_settings and 'welcome_channel' in guild_settings[guild_id]:
        channel_id = guild_settings[guild_id]['welcome_channel']
        channel = member.guild.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title="👋 Bienvenue!",
                description=f"Bienvenue sur **{member.guild.name}**, {member.mention}!",
                color=0x00ff88
            )
            embed.add_field(
                name="🎯 Pour commencer",
                value="Envoyez des messages pour gagner de l'XP et monter de niveau!",
                inline=False
            )
            embed.add_field(
                name="ℹ️ Aide",
                value="Tapez `/help` pour voir toutes les commandes disponibles.",
                inline=False
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Vous êtes le {member.guild.member_count}ème membre!")
            
            await channel.send(embed=embed)

# Fonction principale
if __name__ == "__main__":
    print("🚀 Démarrage du bot...")
    print("📝 N'oubliez pas de remplacer 'YOUR_BOT_TOKEN' par votre vrai token!")
    print("🔧 Assurez-vous d'avoir installé discord.py: pip install discord.py")
    
    # Remplacez par votre token de bot Discord

    bot.run(TOKEN)