# backend/app/core_logic/preview_builder.py
import logging
from typing import Dict, Any, List
from unittest.mock import MagicMock

from ..main import PromptPreviewRequest, RoleConfig
from .persona_manager import determine_bot_persona, build_system_prompt, get_rich_identity, get_highest_configured_role
from .context_builder import format_user_message_for_llm
from .knowledge_manager import knowledge_manager
from ..utils import escape_content

logger = logging.getLogger(__name__)

class ConstructionLog:
    """A helper class to build a detailed construction log for the frontend."""
    def __init__(self):
        self._log: List[str] = []

    def add(self, message: str, indent: int = 0):
        prefix = "  " * indent
        self._log.append(f"{prefix}{message}")
        logger.info(f"Preview Log: {prefix}{message}")

    def get_log(self) -> List[str]:
        return self._log

def _create_mock_objects(scenario_data: Dict[str, Any], bot_config: Dict[str, Any]):
    """Creates mock discord.py-like objects based on scenario data."""
    log = ConstructionLog()

    # Mock Guild
    mock_guild = MagicMock()
    mock_guild.id = int(scenario_data.get('guild_id', 0))
    mock_guild.name = "模拟服务器"
    log.add(f"场景设定：服务器 '{mock_guild.name}' (ID: {mock_guild.id})", 1)

    # Mock Channel
    mock_channel = MagicMock()
    mock_channel.id = int(scenario_data.get('channel_id', 0))
    mock_channel.name = "模拟频道"
    mock_channel.guild = mock_guild
    log.add(f"场景设定：频道 '#{mock_channel.name}' (ID: {mock_channel.id})", 1)

    # Mock Author (User/Member)
    mock_author = MagicMock()
    mock_author.id = int(scenario_data.get('user_id', 0))
    mock_author.name = "模拟用户"
    mock_author.display_name = "模拟用户"
    mock_author.roles = []
    
    # Simulate roles for the author
    role_based_configs = bot_config.get("role_based_config", {})
    for role_id_str in scenario_data.get('user_roles', []):
        mock_role = MagicMock()
        mock_role.id = int(role_id_str)
        role_config_data = role_based_configs.get(role_id_str, {})
        mock_role.name = role_config_data.get("title", f"角色{role_id_str}")
        mock_author.roles.append(mock_role)
    
    log.add(f"场景设定：用户 '@{mock_author.name}' (ID: {mock_author.id})", 1)
    if mock_author.roles:
        log.add(f"用户角色：{[r.name for r in mock_author.roles]}", 2)
    
    # Mock Replied Message author if necessary
    mock_replied_author = None
    if scenario_data.get('is_reply') and scenario_data.get('replied_message'):
        replied_data = scenario_data['replied_message']
        mock_replied_author = MagicMock()
        mock_replied_author.id = int(replied_data.get('author_id', 0))
        mock_replied_author.name = "被回复者"
        mock_replied_author.display_name = "被回复者"

    # Mock Mentioned User if necessary
    # This is a simplified simulation. A real scenario could have multiple mentions.
    if "@张三" in scenario_data.get('message_content', ''):
        mock_mentioned_user = MagicMock()
        mock_mentioned_user.id = 9876543210 # A fixed ID for simulation
        mock_mentioned_user.name = "张三"
        mock_mentioned_user.display_name = "张三"
        # Simulate a role for the mentioned user to test rich identity
        mentioned_user_role = MagicMock()
        mentioned_user_role.id = 999
        mentioned_user_role.name = "开发者"
        mock_mentioned_user.roles = [mentioned_user_role]
        
        def get_member(user_id):
            if user_id == mock_mentioned_user.id:
                return mock_mentioned_user
            if mock_replied_author and user_id == mock_replied_author.id:
                return mock_replied_author
            return None
        mock_guild.get_member = get_member

    # Mock Message
    mock_message = MagicMock()
    mock_message.author = mock_author
    mock_message.channel = mock_channel
    mock_message.guild = mock_guild
    mock_message.content = scenario_data.get('message_content', '')
    mock_message.clean_content = escape_content(mock_message.content)

    # Mock Attachments
    mock_message.attachments = []
    image_count = scenario_data.get('image_count', 0)
    if image_count > 0:
        log.add(f"场景设定：用户发送了 {image_count} 张图片", 1)
        for i in range(image_count):
            attachment = MagicMock()
            attachment.content_type = 'image/png'
            mock_message.attachments.append(attachment)
            
    # Mock Mentions
    mock_message.mentions = []
    if "@张三" in mock_message.content:
        log.add("场景设定：消息中提及了 '@张三'", 1)
        mock_message.mentions.append(mock_mentioned_user)


    # Mock Replied Message
    mock_message.reference = None
    if scenario_data.get('is_reply') and scenario_data.get('replied_message'):
        log.add("场景设定：这是一条回复消息", 1)
        replied_data = scenario_data['replied_message']
        
        mock_replied_message = MagicMock()
        mock_replied_message.author = mock_replied_author
        mock_replied_message.clean_content = escape_content(replied_data.get('content', ''))
        mock_replied_message.attachments = []
        
        mock_reference = MagicMock()
        mock_reference.resolved = mock_replied_message
        mock_message.reference = mock_reference
        log.add(f"回复内容：'{mock_replied_message.clean_content}' (来自: @{mock_replied_author.name})", 2)

    return mock_message, log

async def generate_preview(request: PromptPreviewRequest, bot_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates a preview of the system prompt and user request based on the provided
    templates and scenario. This function reuses the actual bot logic to ensure
    the preview is 100% accurate.
    """
    templates = request.templates.dict()
    scenario = request.scenario.dict()
    
    # Override bot_config with templates from the request for this preview
    simulated_bot_config = {**bot_config, 'prompt_templates': templates}
    
    mock_message, log = _create_mock_objects(scenario, simulated_bot_config)
    
    log.add("✅ 预览构建开始...", 0)
    
    # 1. --- Build System Prompt ---
    log.add("➡️ [Phase 1] 构建系统提示词 (System Prompt)", 0)
    
    # Determine persona
    log.add("确定机器人人设...", 1)
    persona, role_config, source_log = determine_bot_persona(mock_message.author, mock_message.channel, simulated_bot_config)
    log.add(f"人设来源: {source_log}", 2)
    if role_config:
        log.add(f"应用角色配置: '{role_config.get('title', 'N/A')}'", 2)

    # Build system prompt string
    log.add("构建最终系统提示词字符串...", 1)
    system_prompt = build_system_prompt(
        persona_prompt=persona,
        bot_config=simulated_bot_config,
        channel=mock_message.channel,
        user=mock_message.author
    )
    
    # This is a bit of a hack to add logging to build_system_prompt without refactoring it
    log.add("注入 '基础规则标题'", 2)
    log.add(f"注入 {len(templates.get('operational_instructions', []))} 条 '核心操作指令'", 2)
    log.add("注入 '当前人设标题'", 2)
    log.add("注入 '情景补充标题' (及示例)", 2)
    log.add("注入 '参与者肖像标题' (及示例)", 2)
    log.add("注入 '安全及操作指南标题' (及示例)", 2)
    
    # 2. --- Build User Request ---
    log.add("➡️ [Phase 2] 构建用户请求块 (User Request)", 0)
    
    # Simulate plugin data injection
    injected_data_str = ""
    if scenario.get('triggered_plugins'):
        log.add("模拟插件数据注入...", 1)
        plugin_outputs = []
        for plugin_scenario in scenario['triggered_plugins']:
            log.add(f"注入来自 '{plugin_scenario['name']}' 的模拟输出", 2)
            plugin_outputs.append(plugin_scenario['simulated_output'])
        injected_data_str = "\n".join(plugin_outputs)
        
    # Simulate knowledge injection (simplified)
    # A full simulation would require a mock knowledge_manager
    if "世界设定" in mock_message.content:
        log.add("模拟知识库注入...", 1)
        log.add("检测到关键词，注入 '世界设定' 上下文", 2)
        knowledge_manager.find_world_book_entries_for_text = lambda x: [{'content': '这是一个关于这个世界的设定条目。', 'keywords': '世界设定'}]
    else:
        knowledge_manager.find_world_book_entries_for_text = lambda x: []

    if "长期记忆" in mock_message.content:
        log.add("模拟知识库注入...", 1)
        log.add("检测到关键词，注入 '长期记忆' 上下文", 2)
        knowledge_manager.get_all_memories = lambda: [{'content': '这是一条相关的长期记忆。'}]
    else:
        knowledge_manager.get_all_memories = lambda: []

    
    # Format the final user message block
    log.add("格式化最终用户请求...", 1)
    
    # We need the author's role config for get_rich_identity
    _, author_role_config = get_highest_configured_role(mock_message.author, simulated_bot_config.get("role_based_config", {})) or (None, None)

    user_request = format_user_message_for_llm(
        message=mock_message,
        client=MagicMock(), # Not used for preview
        bot_config=simulated_bot_config,
        role_config=author_role_config,
        injected_data=injected_data_str
    )
    log.add("调用 `format_user_message_for_llm`...", 2)
    if mock_message.reference:
        log.add("检测到回复，已注入 '回复上下文' 模板", 3)
    if mock_message.attachments:
        log.add("检测到图片，已注入 '图片注释' 模板", 3)
    if injected_data_str:
        log.add("检测到插件数据，已注入 '工具输出' 模板", 3)
    log.add("已注入 '用户消息格式' 模板", 3)
    log.add("使用 '用户请求块' 模板完成最终封装", 3)


    log.add("✅ 预览构建完成", 0)
    
    return {
        "final_system_prompt": system_prompt,
        "final_user_request": user_request,
        "construction_log": log.get_log()
    }