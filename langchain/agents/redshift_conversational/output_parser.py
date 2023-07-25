import re
from typing import Union

from langchain.agents.agent import AgentOutputParser
from langchain.agents.redshift_conversational.prompt import FORMAT_INSTRUCTIONS
from langchain.schema import AgentAction, AgentFinish, OutputParserException


class RedshiftConvoOutputParser(AgentOutputParser):
    ai_prefix: str = "AI"

    def get_format_instructions(self) -> str:
        return FORMAT_INSTRUCTIONS

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        # handle finish
        if f"{self.ai_prefix}:" in text:
            return AgentFinish(
                {"output": text.split(f"{self.ai_prefix}:")[-1].strip()}, text
            )

        # handle tool search
        if "Tools:" in text:
            try:
                # regex to match thought and tools
                regex = r"[\n]*Thought: (.*?)[\n]*Tools: (.*?)\n"
                match = re.search(regex, text)
                if not match:
                    raise OutputParserException(f"Could not parse LLM ToolSearch output: `{text}`")
                tools = match.group(2).strip(" ").strip('"')
                text_to_return = f"\nThought: {match.group(1)}\nTools: {tools}"
                return AgentAction("ToolSearch", tools, text_to_return)
            except:
                raise OutputParserException(f"Could not parse LLM output: `{text}`")

        # handle Action
        regex = r"Action: (.*?)[\n]*Action Input:"
        match = re.search(regex, text)
        if not match:
            raise OutputParserException(f"Could not parse LLM output: `{text}`")
        action = match.group(1)
        action_input = text.split("Action Input:")[-1]
        # TODO: possibly replace text --> f"Action: {action.strip()}\nAction Input: {action_input.strip(" ").strip('"')}"
        #       to prevent agent from trying to generate future thoughts / steps
        return AgentAction(action.strip(), action_input.strip(" ").strip('"'), text)

    @property
    def _type(self) -> str:
        return "conversational"
