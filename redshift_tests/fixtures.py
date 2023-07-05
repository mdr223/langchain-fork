from langchain import OpenAI

from langchain.agents import initialize_agent, Tool
from langchain.agents import AgentType
from langchain.llms import Bedrock, CodeWhisperer, Falcon
from langchain.memory import ConversationBufferMemory
from langchain.tools.aws import (
    CreateIAMRole,
    AttachIAMPolicy,
    CreateRedshiftCluster,
    CreateRedshiftServerlessNamespace,
    CreateRedshiftServerlessWorkgroup,
    DeleteRedshiftCluster,
    DeleteRedshiftServerlessNamespace,
    DeleteRedshiftServerlessWorkgroup,
    LoadTableFromS3Serverless,
    LoadTableFromS3Cluster,
    SelectQueryDataFromTableServerless,
    CreateS3Bucket,
    CreateKMSKey,
    ToolSearch,
)

import boto3
import pytest


@pytest.fixture(scope="class")
def tools_with_toolsearch():
    """Construct tools available to AI agent and include ToolSearch functionality."""
    tools = [
        CreateIAMRole(),
        AttachIAMPolicy(),
        CreateRedshiftCluster(),
        CreateRedshiftServerlessNamespace(),
        CreateRedshiftServerlessWorkgroup(),
        DeleteRedshiftCluster(),
        DeleteRedshiftServerlessNamespace(),
        DeleteRedshiftServerlessWorkgroup(),
        LoadTableFromS3Serverless(),
        LoadTableFromS3Cluster(),
        SelectQueryDataFromTableServerless(),
        CreateS3Bucket(),
        CreateKMSKey(),
    ]

    # create ToolSearch
    tool_descriptions = {tool.name: tool.description for tool in tools}
    tool_search = ToolSearch(tool_descriptions=tool_descriptions)

    # add ToolSearch to list of tools
    tools.append(tool_search)

    return tools


@pytest.fixture(scope="class")
def memory():
    return ConversationBufferMemory(memory_key="chat_history")


@pytest.fixture(
    scope="class",
    params=[
        "text-davinci-002",
        "falcon-7b-instruct-bf16-2023-07-03-19-51-07-347",
        "falcon-40b-instruct-bf16-2023-07-04-19-55-13-674",
        "codewhisperer",
        "amazon.titan-tg1-large",
    ]
)
def agent_chain(tools_with_toolsearch, memory, request):
    """Create an AgentExecutor using the given LLM."""
    llm_name = request.param

    # construct LLM from llm_name
    ### Falcon
    llm = None
    if "falcon" in llm_name:
        llm = Falcon(model=llm_name)

    ### Bedrock
    elif "titan" in llm_name:
        bedrock_client = boto3.client(
            service_name='bedrock',
            region_name='us-east-1',
            endpoint_url='https://bedrock.us-east-1.amazonaws.com',
        )
        llm = Bedrock(model_id=llm_name, client=bedrock_client)

    ### CodeWhisperer
    elif "codewhisperer" in llm_name:
        session = boto3.Session()
        cw_client = session.client(
            "codewhisperer",
            endpoint_url="https://codewhisperer.us-east-1.amazonaws.com",
            region_name="us-east-1",
        )
        llm = CodeWhisperer(client=cw_client)

    ### OpenAI
    else:
        llm = OpenAI(temperature=0, model_name=llm_name)

    # construct agent chain given tools, LLM, and memory
    agent_chain = initialize_agent(
        tools_with_toolsearch,
        llm,
        agent=AgentType.REDSHIFT_CONVERSATIONAL_REACT_DESCRIPTION,
        verbose=True,
        memory=memory,
    )

    return agent_chain
