from redshift_tests.fixtures import *
from redshift_tests.inputs import *

from langchain.tools.aws import *

import json
import mock

class TestAgent:

    def test_basic(self):
        assert True

    @mock.patch('langchain.tools.aws.CreateS3Bucket._run')
    def test_create_bucket(self, agent_chain, mock):
        # patch tool
        # mocker.patch('langchain.tools.aws.CreateS3Bucket._run')
        _ = agent_chain.run(input="Please create a bucket called mrusso-test-bucket")
        args, kwargs = mock.call_args
        print(args)
        print(kwargs)
        assert 0
