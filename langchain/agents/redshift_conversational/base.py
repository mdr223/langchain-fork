"""An agent designed to hold a conversation in addition to using tools."""
from __future__ import annotations

from typing import Any, List, Optional, Sequence

from pydantic import Field

from langchain.agents.agent import Agent, AgentOutputParser, ToolSearchThenActionAgent
from langchain.agents.agent_types import AgentType
from langchain.agents.redshift_conversational.output_parser import RedshiftConvoOutputParser
from langchain.agents.redshift_conversational.prompt import FORMAT_INSTRUCTIONS, PREFIX, SUFFIX
from langchain.agents.utils import validate_tools_single_input
from langchain.base_language import BaseLanguageModel
from langchain.callbacks.base import BaseCallbackManager
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.tools.base import BaseTool


class RedshiftConversationalAgent(ToolSearchThenActionAgent):
    """An agent designed to hold a conversation in addition to using tools."""

    # aws_account_id = None
    ai_prefix: str = "AI"
    output_parser: AgentOutputParser = Field(default_factory=RedshiftConvoOutputParser)

    @classmethod
    def _get_default_output_parser(
        cls, ai_prefix: str = "AI", **kwargs: Any
    ) -> AgentOutputParser:
        return RedshiftConvoOutputParser(ai_prefix=ai_prefix)

    @property
    def _agent_type(self) -> str:
        """Return Identifier of agent type."""
        return AgentType.REDSHIFT_CONVERSATIONAL_REACT_DESCRIPTION

    @property
    def tools_prefix(self) -> str:
        """Prefix to prepend the tool descriptions with."""
        return "Tool Descriptions: "

    @property
    def observation_prefix(self) -> str:
        """Prefix to prepend the observation with."""
        return "Observation: "

    @property
    def llm_prefix(self) -> str:
        """Prefix to prepend the llm call with."""
        return "Thought:"

    @classmethod
    def create_prompt(
        cls,
        tools: Sequence[BaseTool],
        prefix: str = PREFIX,
        suffix: str = SUFFIX,
        format_instructions: str = FORMAT_INSTRUCTIONS,
        ai_prefix: str = "AI",
        human_prefix: str = "Human",
        # max_iterations: int = 15,
        input_variables: Optional[List[str]] = None,
    ) -> PromptTemplate:
        """Create prompt in the style of the zero shot agent.

        Args:
            tools: List of tools the agent will have access to, used to format the
                prompt.
            prefix: String to put before the list of tools.
            suffix: String to put after the list of tools.
            ai_prefix: String to use before AI output.
            human_prefix: String to use before human output.
            max_iterations: Instruction to LLM for maximum number of times to retry tool search.
            input_variables: List of input variables the final prompt will expect.

        Returns:
            A PromptTemplate with the template assembled from the pieces here.
        """
        tool_strings = "\n".join(
            [f"> {tool.name}: {tool.short_description}" for tool in tools]
        )
        tool_names = ", ".join([tool.name for tool in tools])
        format_instructions = format_instructions.format(
            tool_names=tool_names,
            ai_prefix=ai_prefix,
            human_prefix=human_prefix,
            # max_iterations=max_iterations,
        )
        # template = "\n\n".join([prefix, tool_strings, format_instructions, suffix])
        template = "\n\n".join([prefix, format_instructions, suffix])
        if input_variables is None:
            input_variables = ["input", "chat_history", "agent_scratchpad"]
        return PromptTemplate(template=template, input_variables=input_variables)

    @classmethod
    def _validate_tools(cls, tools: Sequence[BaseTool]) -> None:
        super()._validate_tools(tools)
        validate_tools_single_input(cls.__name__, tools)

    @classmethod
    def from_llm_and_tools(
        cls,
        llm: BaseLanguageModel,
        tools: Sequence[BaseTool],
        callback_manager: Optional[BaseCallbackManager] = None,
        output_parser: Optional[AgentOutputParser] = None,
        prefix: str = PREFIX,
        suffix: str = SUFFIX,
        format_instructions: str = FORMAT_INSTRUCTIONS,
        ai_prefix: str = "AI",
        human_prefix: str = "Human",
        # max_iterations: int = 15,
        input_variables: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Agent:
        """Construct an agent from an LLM and tools."""
        cls._validate_tools(tools)
        prompt = cls.create_prompt(
            tools,
            ai_prefix=ai_prefix,
            human_prefix=human_prefix,
            prefix=prefix,
            suffix=suffix,
            format_instructions=format_instructions,
            # max_iterations=max_iterations,
            input_variables=input_variables,
        )
        llm_chain = LLMChain(
            llm=llm,
            prompt=prompt,
            callback_manager=callback_manager,
        )
        tool_names = [tool.name for tool in tools]
        _output_parser = output_parser or cls._get_default_output_parser(
            ai_prefix=ai_prefix
        )
        return cls(
            llm_chain=llm_chain,
            allowed_tools=tool_names,
            ai_prefix=ai_prefix,
            output_parser=_output_parser,
            **kwargs,
        )
