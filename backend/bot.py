import nonebot
from nonebot.adapters.discord import Adapter as DiscordAdapter
from app.discord_patch import apply_component_emoji_fix

apply_component_emoji_fix()

nonebot.init()
driver = nonebot.get_driver()
driver.register_adapter(DiscordAdapter)
nonebot.load_plugins("nb_plugins")
