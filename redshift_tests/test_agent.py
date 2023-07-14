from redshift_tests.fixtures import *
from redshift_tests.inputs import *

from langchain.tools.aws import *

import json


class TestAgent:

    def test_basic(self):
        assert True

    # @mock.patch('langchain.tools.aws.CreateS3Bucket._run')
    @pytest.mark.parametrize(
        "create_bucket_input,create_bucket_expected",
        [
            (create_bucket_input_1, create_bucket_expected_1),
            (create_bucket_input_2, create_bucket_expected_2),
        ]
    )
    def test_create_bucket(self, agent_chain, create_bucket_input, create_bucket_expected, mocker):
        # patch tool
        mocker.patch('langchain.tools.aws.CreateS3Bucket._run')

        # execute agent given input
        _ = agent_chain.run(input=create_bucket_input_1)

        # fetch input string to mocked tool and assert that it is expected
        tool_input_str = CreateS3Bucket._run.call_args.args[0]
        tool_input_str = tool_input_str.strip().strip('`').strip('>')

        assert json.loads(tool_input_str) == create_bucket_expected_1

