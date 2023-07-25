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
                # get text after "Tools:", but before newline
                tools = text.split("Tools:")[-1].split("\n")[0]
                text = tools.strip(" ").strip('"')
                return AgentAction("ToolSearch", text, text)
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
