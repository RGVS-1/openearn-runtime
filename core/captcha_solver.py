import re
import asyncio
import logging
from telethon.tl.custom.message import Message

logger = logging.getLogger("openearn.captcha")

async def solve_emoji_captcha_if_present(client, bot_entity, max_retries: int = 3) -> bool:
    """
    Checks recent bot messages for an emoji captcha check.
    If detected, parses the requested emoji and clicks the corresponding inline button.
    Returns True if a captcha was found and solved, False if no captcha was present.
    """
    for attempt in range(max_retries):
        msgs = await client.get_messages(bot_entity, limit=4)
        captcha_msg = None
        target_emoji = None

        for m in msgs:
            if m.text and ("Найдите эмодзи" in m.text or "эмодзи:" in m.text):
                match = re.search(r"эмодзи:\s*(\S+)", m.text)
                if match:
                    target_emoji = match.group(1).strip()
                    captcha_msg = m
                    break

        if not captcha_msg or not target_emoji:
            return False

        logger.info(f"Emoji captcha detected in message {captcha_msg.id}: looking for '{target_emoji}'")

        button_to_click = None
        if captcha_msg.buttons:
            for row in captcha_msg.buttons:
                for b in row:
                    b_text = (b.text or "").strip()
                    if b_text == target_emoji or target_emoji in b_text:
                        button_to_click = b
                        break
                if button_to_click:
                    break

        if button_to_click:
            logger.info(f"Clicking captcha button '{button_to_click.text}' (data={button_to_click.data})...")
            try:
                await button_to_click.click()
                await asyncio.sleep(2.0)
                return True
            except Exception as e:
                logger.error(f"Error clicking captcha button: {e}")
                return False
        else:
            logger.warning(f"Could not find matching button for target emoji '{target_emoji}'")
            return False

    return False
