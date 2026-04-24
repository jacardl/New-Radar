"""
DeepSeek V3.1 tool call parser.

Similar to V3 but with a slightly different format:
    <éæ¸¢oolé»ä¹§allé»ä¹¥eginé?function_name<éæ¸¢oolé»ä¹»epé?arguments<éæ¸¢oolé»ä¹§allé»ä¹ªndé?

Note: V3 has type+name before the separator, V3.1 has name before and args after.

Based on VLLM's DeepSeekV31ToolParser.extract_tool_calls()
"""

import re
import uuid
from typing import List, Optional

from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)

from environments.tool_call_parsers import ParseResult, ToolCallParser, register_parser


@register_parser("deepseek_v3_1")
@register_parser("deepseek_v31")
class DeepSeekV31ToolCallParser(ToolCallParser):
    """
    Parser for DeepSeek V3.1 tool calls.

    Slightly different regex than V3: function_name comes before the separator,
    arguments come after (no type field, no json code block wrapper).
    """

    START_TOKEN = "<éæ¸¢oolé»ä¹§allsé»ä¹¥eginé?"

    # Regex captures: function_name, function_arguments
    PATTERN = re.compile(
        r"<éæ¸¢oolé»ä¹§allé»ä¹¥eginé?(?P<function_name>.*?)<éæ¸¢oolé»ä¹»epé?(?P<function_arguments>.*?)<éæ¸¢oolé»ä¹§allé»ä¹ªndé?",
        re.DOTALL,
    )

    def parse(self, text: str) -> ParseResult:
        if self.START_TOKEN not in text:
            return text, None

        try:
            matches = self.PATTERN.findall(text)
            if not matches:
                return text, None

            tool_calls: List[ChatCompletionMessageToolCall] = []
            for match in matches:
                func_name, func_args = match
                tool_calls.append(
                    ChatCompletionMessageToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        type="function",
                        function=Function(
                            name=func_name.strip(),
                            arguments=func_args.strip(),
                        ),
                    )
                )

            if not tool_calls:
                return text, None

            content = text[: text.find(self.START_TOKEN)].strip()
            return content if content else None, tool_calls

        except Exception:
            return text, None
