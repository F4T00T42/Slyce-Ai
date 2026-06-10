"""Orchestration loop: User -> LLM -> tool selection -> tool execution -> reply.

The LLM picks tool(s); we execute them, feed results back, and repeat until it
produces a final answer or hits the iteration cap. Information priority
(DB > KB > web) is enforced via the system prompt and tool descriptions.
"""
import json

from ai.config import settings
from ai.prompts import SYSTEM_PROMPT, TOOL_ROUTING_HINT
from ai.tools import TOOL_SCHEMAS, execute, ToolContext


class Orchestrator:
    # Drives the tool-calling conversation with the LLM.
    def __init__(self, llm, build_context):
        # Inputs: llm (LLMProvider), build_context (callable -> fresh ToolContext;
        # currently unused, context is passed per request to handle()).
        self._llm = llm
        self._build_context = build_context

    def handle(self, message: str, ctx: ToolContext, history: list | None = None) -> dict:
        # Inputs: message (user text), ctx (ToolContext with repos/profile),
        # history (prior [{role, content}] turns for context).
        # Returns {reply, used_tools, citations}.
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + TOOL_ROUTING_HINT}
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        used_tools: list[str] = []

        for _ in range(settings.max_tool_iterations):
            response = self._llm.chat(messages, tools=TOOL_SCHEMAS, tool_choice="auto")
            choice = response.choices[0].message
            tool_calls = getattr(choice, "tool_calls", None)

            # Record the assistant turn (with any tool calls) in the transcript.
            assistant_msg = {"role": "assistant", "content": choice.content or ""}
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ]
            messages.append(assistant_msg)

            # No tool calls -> the model produced a final answer.
            if not tool_calls:
                return {
                    "reply": choice.content or "",
                    "used_tools": used_tools,
                    "citations": ctx.citations,
                }

            # Execute each requested tool and append its result.
            for tc in tool_calls:
                name = tc.function.name
                used_tools.append(name)
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = execute(name, args, ctx)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": name,
                        "content": json.dumps(result, default=str),
                    }
                )

        # Iteration cap hit: force a final textual answer with tools disabled.
        response = self._llm.chat(messages, tools=None)
        return {
            "reply": response.choices[0].message.content or "",
            "used_tools": used_tools,
            "citations": ctx.citations,
        }
