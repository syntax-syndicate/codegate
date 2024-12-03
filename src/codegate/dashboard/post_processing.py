import asyncio
import json
from typing import List, Optional, Tuple

import structlog

from codegate.dashboard.request_models import (
    ChatMessage,
    Conversation,
    PartialConversation,
    QuestionAnswer,
)
from codegate.db.queries import GetPromptWithOutputsRow

logger = structlog.get_logger("codegate")


SYSTEM_PROMPTS = [
    "Given the following... please reply with a short summary that is 4-12 words in length, "
    "you should summarize what the user is asking for OR what the user is trying to accomplish. "
    "You should only respond with the summary, no additional text or explanation, "
    "you don't need ending punctuation.",
]


async def _is_system_prompt(message: str) -> bool:
    """
    Check if the message is a system prompt.
    """
    for prompt in SYSTEM_PROMPTS:
        if prompt in message or message in prompt:
            return True
    return False


async def parse_request(request_str: str) -> Optional[str]:
    """
    Parse the request string from the pipeline and return the message.
    """
    try:
        request = json.loads(request_str)
    except Exception as e:
        logger.exception(f"Error parsing request: {e}")
        return None

    messages = []
    for message in request.get("messages", []):
        role = message.get("role")
        if not role == "user":
            continue
        content = message.get("content")

        message_str = ""
        if isinstance(content, str):
            message_str = content
        elif isinstance(content, list):
            for content_part in content:
                if isinstance(content_part, dict) and content_part.get("type") == "text":
                    message_str = content_part.get("text")

        if message_str and not await _is_system_prompt(message_str):
            messages.append(message_str)

    # We couldn't get anything from the messages, try the prompt
    if not messages:
        message_prompt = request.get("prompt", "")
        if message_prompt and not await _is_system_prompt(message_prompt):
            messages.append(message_prompt)

    # If still we don't have anything, return empty string
    if not messages:
        return None

    # Only respond with the latest message
    return messages[-1]


async def parse_output(output_str: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse the output string from the pipeline and return the message and chat_id.
    """
    try:
        output = json.loads(output_str)
    except Exception as e:
        logger.exception(f"Error parsing request: {e}")
        return None, None

    output_message = ""
    chat_id = None
    if isinstance(output, list):
        for output_chunk in output:
            if not isinstance(output_chunk, dict):
                continue
            chat_id = chat_id or output_chunk.get("id")
            for choice in output_chunk.get("choices", []):
                if not isinstance(choice, dict):
                    continue
                delta_dict = choice.get("delta", {})
                output_message += delta_dict.get("content", "")
    elif isinstance(output, dict):
        chat_id = chat_id or output.get("id")
        for choice in output.get("choices", []):
            if not isinstance(choice, dict):
                continue
            output_message += choice.get("message", {}).get("content", "")

    return output_message, chat_id


async def parse_get_prompt_with_output(
    row: GetPromptWithOutputsRow,
) -> Optional[PartialConversation]:
    """
    Parse a row from the get_prompt_with_outputs query and return a PartialConversation

    The row contains the raw request and output strings from the pipeline.
    """
    async with asyncio.TaskGroup() as tg:
        request_task = tg.create_task(parse_request(row.request))
        output_task = tg.create_task(parse_output(row.output))

    request_msg_str = request_task.result()
    output_msg_str, chat_id = output_task.result()

    # If we couldn't parse the request or output, return None
    if not request_msg_str or not output_msg_str or not chat_id:
        return None

    request_message = ChatMessage(
        message=request_msg_str,
        timestamp=row.timestamp,
        message_id=row.id,
    )
    output_message = ChatMessage(
        message=output_msg_str,
        timestamp=row.output_timestamp,
        message_id=row.output_id,
    )
    question_answer = QuestionAnswer(
        question=request_message,
        answer=output_message,
    )
    return PartialConversation(
        question_answer=question_answer,
        provider=row.provider,
        type=row.type,
        chat_id=chat_id,
        request_timestamp=row.timestamp,
    )


async def match_conversations(
    partial_conversations: List[Optional[PartialConversation]],
) -> List[Conversation]:
    """
    Match partial conversations to form a complete conversation.
    """
    convers = {}
    for partial_conversation in partial_conversations:
        if not partial_conversation:
            continue

        # Group by chat_id
        if partial_conversation.chat_id not in convers:
            convers[partial_conversation.chat_id] = []
        convers[partial_conversation.chat_id].append(partial_conversation)

    # Sort by timestamp
    sorted_convers = {
        chat_id: sorted(conversations, key=lambda x: x.request_timestamp)
        for chat_id, conversations in convers.items()
    }
    # Create the conversation objects
    conversations = []
    for chat_id, sorted_convers in sorted_convers.items():
        questions_answers = []
        for partial_conversation in sorted_convers:
            questions_answers.append(partial_conversation.question_answer)
        conversations.append(
            Conversation(
                question_answers=questions_answers,
                provider=partial_conversation.provider,
                type=partial_conversation.type,
                chat_id=chat_id,
                conversation_timestamp=sorted_convers[0].request_timestamp,
            )
        )

    return conversations
