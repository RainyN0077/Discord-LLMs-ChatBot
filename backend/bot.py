import nonebot
from nonebot.adapters.discord import Adapter as DiscordAdapter

nonebot.init()
driver = nonebot.get_driver()
driver.register_adapter(DiscordAdapter)
nonebot.load_plugins("nb_plugins")
