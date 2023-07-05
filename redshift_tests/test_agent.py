from redshift_tests.fixtures import *
from redshift_tests.inputs import *


class TestAgent:

    def test_basic(self):
        assert True

    def test_create_bucket(self, tools_with_toolsearch, create_bucket_input_1, mocker):
        mocker.patch('langchain.tools.aws.CreateS3Bucket.short_description')
        _ = tools_with_toolsearch[11].short_description()
        tools_with_toolsearch[11].assert_called_once()
