import re
from typing import Union

from langchain.agents.agent import AgentOutputParser
from langchain.agents.redshift_conversational.prompt import FORMAT_INSTRUCTIONS
from langchain.schema import AgentAction, AgentFinish, AgentToolSearch, OutputParserException


class RedshiftConvoOutputParser(AgentOutputParser):
    ai_prefix: str = "AI"

    def get_format_instructions(self) -> str:
        return FORMAT_INSTRUCTIONS

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        if f"{self.ai_prefix}:" in text:
            return AgentFinish(
                {"output": text.split(f"{self.ai_prefix}:")[-1].strip()}, text
            )
        regex = r"Action: (.*?)[\n]*Action Input: (.*)"
        match = re.search(regex, text)
        if not match:
            raise OutputParserException(f"Could not parse LLM output: `{text}`")
        action = match.group(1)
        action_input = match.group(2)
        return AgentAction(action.strip(), action_input.strip(" ").strip('"'), text)

    @property
    def _type(self) -> str:
        return "conversational"


# class RedshiftConvoOutputParser(AgentOutputParser):
#     ai_prefix: str = "AI"

#     def get_format_instructions(self) -> str:
#         return FORMAT_INSTRUCTIONS

#     def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
#         # handle finish
#         if f"{self.ai_prefix}:" in text:
#             return AgentFinish(
#                 {"output": text.split(f"{self.ai_prefix}:")[-1].strip()}, text
#             )

#         # handle Potential Actions
#         if "Potential Action:" in text:
#             try:
#                 potential_actions = text.split("Potential Action:")[-1].split(",")
#                 potential_actions = [action.strip() for action in potential_actions]
#                 return AgentToolSearch(potential_actions, text)
#             except:
#                 raise OutputParserException(f"Could not parse LLM output: `{text}`")

#         # handle Action
#         regex = r"Action: (.*?)[\n]*Action Input: (.*)"
#         match = re.search(regex, text)
#         if not match:
#             raise OutputParserException(f"Could not parse LLM output: `{text}`")
#         action = match.group(1)
#         action_input = match.group(2)
#         return AgentAction(action.strip(), action_input.strip(" ").strip('"'), text)

#     @property
#     def _type(self) -> str:
#         return "conversational"