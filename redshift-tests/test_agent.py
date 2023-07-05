import pytest

@pytest.fixture(
    scope="class",
    params=[
        "text-davinci-002",
        "falcon-7b-instruct-bf16-2023-07-03-19-51-07-347",
        "falcon-40b-instruct-bf16-2023-07-04-19-55-13-674",
        "codewhisperer",
    ]
)
def agent_chain(request):
    """Create an AgentExecutor using the given LLM."""
    llm_name = request.param

    # TODO
    agent_chain = None

    return agent_chain


class TestAgent:

    def test_basic(self):
        assert True

    def test_agent_chain(self, agent_chain):
        assert True
