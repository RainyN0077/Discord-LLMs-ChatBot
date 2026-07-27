"""平台特定的公会/服务器成员解析接口.

用于解耦 context_builder.py 和 persona_manager.py 中的 discord.Member 依赖。
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional


class GuildMemberResolver(ABC):
    """平台特定的公会/服务器成员解析接口.

    用于解耦 context_builder.py 和 persona_manager.py 中的 discord.Member 依赖。
    """

    @abstractmethod
    async def get_member(self, guild_id: str, user_id: str) -> Optional[Any]:
        """获取服务器成员信息.

        Args:
            guild_id: 服务器 ID
            user_id: 用户 ID

        Returns:
            成员信息对象，未找到时返回 None
        """
        ...

    @abstractmethod
    def get_member_roles(self, guild_id: str, user_id: str) -> List[str]:
        """获取成员角色列表.

        Args:
            guild_id: 服务器 ID
            user_id: 用户 ID

        Returns:
            角色 ID 列表
        """
        ...
