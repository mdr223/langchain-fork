from redshift_tests.fixtures import *
from redshift_tests.inputs import *

from langchain.tools.aws import *

import json

class TestAgent:

    def test_basic(self):
        assert True

    # @mock.patch('langchain.tools.aws.CreateS3Bucket._run')
    def test_create_bucket(self, agent_chain, mocker):
        # patch tool
        mocker.patch('langchain.tools.aws.CreateS3Bucket._run')
        _ = agent_chain.run(input="Please create a bucket called mrusso-test-bucket")
        args, kwargs = CreateS3Bucket._run.call_args
        print(args)
        print(kwargs)
        assert 0
