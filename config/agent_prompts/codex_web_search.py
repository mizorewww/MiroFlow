# SPDX-FileCopyrightText: 2025 MiromindAI
#
# SPDX-License-Identifier: Apache-2.0

import datetime
from typing import Any

from config.agent_prompts.sub_worker import SubAgentWorkerPrompt


class SubAgentCodexWebSearchPrompt(SubAgentWorkerPrompt):
    def generate_system_prompt_with_mcp_tools(
        self, mcp_servers: list[Any], chinese_context: bool = False
    ) -> str:
        formatted_date = datetime.datetime.today().strftime("%Y-%m-%d")
        prompt = f"""You are a Codex web research sub-agent. Today is: {formatted_date}.

Use Codex native web_search for current or source-sensitive facts. Return a concise structured report for the assigned subtask.

Research rules:
- Prefer primary or high-reputation sources.
- Cross-check important facts when possible.
- Include source URLs and timestamps or publication dates when available.
- Clearly flag conflicts, stale data, weak sources, or anything you could not verify.
- Do not expose hidden chain-of-thought. Briefly summarize your method and findings instead.
- Unless otherwise requested, respond in the same language as the assigned subtask.
"""

        if mcp_servers:
            prompt += """
You may also use the MiroFlow MCP tools listed below. Use exactly one MiroFlow tool call per message if you choose a MiroFlow tool. Do not use XML for Codex native web_search.

"""
            for server in mcp_servers:
                prompt += f"## Server name: {server['name']}\n"
                for tool in server.get("tools", []):
                    if "error" in tool and "name" not in tool:
                        continue
                    prompt += f"### Tool name: {tool['name']}\n"
                    prompt += f"Description: {tool['description']}\n"
                    prompt += f"Input JSON schema: {tool['schema']}\n"

        if chinese_context:
            prompt += """
中文语境处理：
- 使用中文关键词和中文资料源优先检索。
- 保留中文资料的原文表达，避免不必要的翻译。
- 输出使用中文，清楚标注来源和不确定性。
"""

        prompt += """
Output format:
1. Best supported answer or findings.
2. Supporting evidence with source URLs.
3. Conflicts or uncertainty.
4. Short recommendation about which evidence should be trusted most.
"""
        return prompt

    def expose_agent_as_tool(self, subagent_name: str) -> dict:
        tool_definition = super().expose_agent_as_tool(subagent_name)
        tool_definition["tools"][0][
            "description"
        ] = "This tool runs a Codex/GPT web-search research agent using Codex native web_search. Use it for source-sensitive or current web evidence, especially when you want an independent search path from Serper/Jina. It returns a concise structured report with URLs, conflicts, and uncertainty."
        return tool_definition
