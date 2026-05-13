import json
import logging
import re
from typing import Any, Dict, List, Optional

from ..models import PlatformMessage, PlatformUser, PlatformChannel, PlatformGuild

logger = logging.getLogger(__name__)

CQ_IMAGE_PATTERN = re.compile(r'\[CQ:image,([^\]]+)\]')
CQ_AT_PATTERN = re.compile(r'\[CQ:at,qq=(\d+)(?:[^\]]*)?\]')
CQ_FACE_PATTERN = re.compile(r'\[CQ:face,[^\]]+\]')
CQ_RECORD_PATTERN = re.compile(r'\[CQ:record,[^\]]+\]')
CQ_VIDEO_PATTERN = re.compile(r'\[CQ:video,[^\]]+\]')
CQ_FILE_PATTERN = re.compile(r'\[CQ:file,[^\]]+\]')
CQ_REPLY_PATTERN = re.compile(r'\[CQ:reply,[^\]]*id=(-?\d+)[^\]]*\]')

CQ_GENERIC_PATTERN = re.compile(r'\[CQ:\w+,[^\]]*\]')

QQ_ROLE_MAP = {
    "owner": "qq_group_owner",
    "admin": "qq_group_admin",
    "member": "qq_group_member",
}


def _parse_cq_params(params_str: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for match in re.finditer(r'(\w+)=((?:[^,\[\]]|\[CQ:[^\]]*\])*)', params_str):
        key = match.group(1)
        value = match.group(2)
        result[key] = value
    return result


def extract_cq_images(raw_message: str) -> List[Dict[str, str]]:
    images: List[Dict[str, str]] = []
    for match in CQ_IMAGE_PATTERN.finditer(raw_message):
        params = _parse_cq_params(match.group(1))
        url = params.get("url", "")
        file_name = params.get("file", "")
        images.append({"url": url, "file": file_name, "kind": "cq_image"})
    return images


def extract_reply_info(raw_message: str) -> Optional[Dict[str, Any]]:
    match = CQ_REPLY_PATTERN.search(raw_message)
    if match:
        return {"message_id": match.group(1)}
    return None


def strip_cq_codes(text: str) -> str:
    text = CQ_REPLY_PATTERN.sub('', text)
    text = CQ_AT_PATTERN.sub('', text)
    text = CQ_FACE_PATTERN.sub('', text)
    text = CQ_RECORD_PATTERN.sub('[语音]', text)
    text = CQ_VIDEO_PATTERN.sub('[视频]', text)
    text = CQ_IMAGE_PATTERN.sub('[图片]', text)
    text = CQ_FILE_PATTERN.sub('[文件]', text)
    text = CQ_GENERIC_PATTERN.sub('', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def convert_to_platform_message(event: Dict[str, Any]) -> Optional[PlatformMessage]:
    post_type = event.get("post_type", "")
    if post_type != "message":
        return None

    message_type = event.get("message_type", "")
    time_val = event.get("time", 0)
    message_id = str(event.get("message_id", ""))
    sender = event.get("sender", {})
    raw_message = event.get("raw_message", "")

    user_id = str(sender.get("user_id", ""))
    nickname = sender.get("nickname", "")
    card = sender.get("card", "")

    author = PlatformUser(
        id=user_id,
        name=nickname,
        display_name=card or nickname,
        platform="qq",
        is_bot=(str(event.get("self_id", "")) == user_id),
    )

    if message_type == "group":
        group_id = str(event.get("group_id", ""))
        channel = PlatformChannel(id=group_id, platform="qq")
        guild = PlatformGuild(id=group_id, platform="qq")
    elif message_type == "private":
        channel_id = user_id
        channel = PlatformChannel(id=channel_id, platform="qq")
        guild = None
    else:
        logger.debug("Unsupported QQ message_type: %s", message_type)
        return None

    clean_content = strip_cq_codes(raw_message)

    images = extract_cq_images(raw_message)
    attachments: List[Dict[str, Any]] = []
    for img in images:
        attachments.append({
            "url": img["url"],
            "kind": img["kind"],
            "file": img["file"],
        })

    reply_info = extract_reply_info(raw_message)

    mentions: List[PlatformUser] = []
    for match in CQ_AT_PATTERN.finditer(raw_message):
        at_qq = match.group(1)
        if at_qq == "all":
            mentions.append(PlatformUser(id="all", name="@全体成员", platform="qq"))
        else:
            mentions.append(PlatformUser(id=at_qq, name=at_qq, platform="qq"))

    return PlatformMessage(
        id=message_id,
        content=raw_message,
        clean_content=clean_content,
        author=author,
        channel=channel,
        guild=guild,
        mentions=mentions,
        attachments=attachments,
        reference=reply_info,
        platform="qq",
        raw_data=event,
    )
