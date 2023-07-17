from redshift_tests.fixtures import *
from redshift_tests.inputs import *
from redshift_tests.shell import run_sh

from langchain.tools.aws import *

import json


class TestAgent:

    def test_basic(self):
        assert True

    @pytest.mark.parametrize(
        "create_bucket_input,create_bucket_expected",
        [
            (create_bucket_input_1, create_bucket_expected_1),
            (create_bucket_input_2, create_bucket_expected_2),
            (create_bucket_input_3, create_bucket_expected_3),
        ]
    )
    def test_create_bucket(self, agent_chain, create_bucket_input, create_bucket_expected, mocker):
        # # patch tool
        # mocker.patch('langchain.tools.aws.CreateS3Bucket._run')

        # execute agent given input
        _ = agent_chain.run(input=create_bucket_input)

        # run command to see if command created S3 bucket
        bucket_name, region = create_bucket_expected
        _, stdout, _ = run_sh(f"aws s3api list-buckets --region {region}")

        # parse stdout and check for bucket
        buckets = json.loads(stdout)
        matching_buckets = list(filter(lambda bucket: bucket["Name"] == bucket_name, buckets["Buckets"]))
        assert len(matching_buckets) == 1

        # # fetch input string to mocked tool and assert that it is expected
        # tool_input_str = CreateS3Bucket._run.call_args.args[0]
        # tool_input_str = tool_input_str.strip().strip('`').strip('>')

        # assert json.loads(tool_input_str) == create_bucket_expected

    @pytest.mark.parametrize(
        "create_iam_role_input,create_iam_role_expected",
        [
            (create_iam_role_input_1, create_iam_role_expected_1),
            (create_iam_role_input_2, create_iam_role_expected_2),
        ]
    )
    def test_create_iam_role(self, agent_chain, create_iam_role_input, create_iam_role_expected, mocker):
        # # patch tool
        # mocker.patch('langchain.tools.aws.CreateIAMRole._run')

        # execute agent given input
        _ = agent_chain.run(input=create_iam_role_input)

        # run command to see if command created S3 bucket
        role_name, description = create_iam_role_expected
        _, stdout, _ = run_sh(f"aws iam list-roles")

        # parse stdout and check for bucket
        roles = json.loads(stdout)
        matching_roles = list(filter(lambda role: role["RoleName"] == role_name, roles["Roles"]))
        assert len(matching_roles) == 1
        if description is None:
            assert "Description" not in matching_roles[0]
        else:
            assert matching_roles[0]["Description"] == description
