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
            (CREATE_BUCKET_INPUT_1, CREATE_BUCKET_EXPECTED_1),
            (CREATE_BUCKET_INPUT_2, CREATE_BUCKET_EXPECTED_2),
            (CREATE_BUCKET_INPUT_3, CREATE_BUCKET_EXPECTED_3),
        ],
        ids=[
            'create_bucket_test_1',
            'create_bucket_test_2',
            'create_bucket_test_3',
        ]
    )
    def test_create_bucket(self, agent_chain, create_bucket_input, create_bucket_expected):
        # # patch tool
        # mocker.patch('langchain.tools.aws.CreateS3Bucket._run')

        # execute agent given input
        _ = agent_chain.run(input=create_bucket_input)

        # run command to see if command created S3 bucket
        bucket_name, region = create_bucket_expected
        _, stdout, _ = run_sh(f"aws s3api list-buckets --region {region}", silent=True)

        # parse stdout and check for bucket
        buckets = json.loads(stdout)
        matching_buckets = list(filter(lambda bucket: bucket["Name"] == bucket_name, buckets["Buckets"]))
        assert len(matching_buckets) == 1

        # tear down
        _ = run_sh(f"aws s3api delete-bucket --bucket {bucket_name} --region {region}", silent=True)

        # # fetch input string to mocked tool and assert that it is expected
        # tool_input_str = CreateS3Bucket._run.call_args.args[0]
        # tool_input_str = tool_input_str.strip().strip('`').strip('>')

        # assert json.loads(tool_input_str) == create_bucket_expected


    @pytest.mark.parametrize(
        "create_iam_role_input,create_iam_role_expected",
        [
            (CREATE_IAM_ROLE_INPUT_1, CREATE_IAM_ROLE_EXPECTED_1),
            (CREATE_IAM_ROLE_INPUT_2, CREATE_IAM_ROLE_EXPECTED_2),
        ],
        ids=[
            'create_iam_role_test_1',
            'create_iam_role_test_2',
        ]
    )
    def test_create_iam_role(self, agent_chain, create_iam_role_input, create_iam_role_expected):
        # execute agent given input
        _ = agent_chain.run(input=create_iam_role_input)

        # run command to see if command created IAM role
        role_name, description = create_iam_role_expected
        # _, stdout, _ = run_sh(f"aws iam list-roles", silent=True)
        _, stdout, _ = run_sh(f"aws iam get-role --role-name {role_name}", silent=True)

        # assert that there wasn't an error
        assert stdout != ""

        # assert that the description matches
        role = json.loads(stdout)
        assert role['Role']['Description'] == description

        _ = run_sh(f"aws iam delete-role --role-name {role_name}", silent=True)


    @pytest.mark.parametrize(
        "attach_iam_policy_input,attach_iam_policy_expected",
        [
            (ATTACH_IAM_POLICY_INPUT_1, ATTACH_IAM_POLICY_EXPECTED_1),
            (ATTACH_IAM_POLICY_INPUT_2, ATTACH_IAM_POLICY_EXPECTED_2),
        ],
        ids=[
            'attach_iam_policy_test_1',
            'attach_iam_policy_test_2',
        ]
    )
    def test_attach_iam_policy(self, agent_chain, attach_iam_policy_input, attach_iam_policy_expected, mocker):
        # execute agent given input
        _ = agent_chain.run(input=attach_iam_policy_input)

        # run command to see if it attached iam policy to role
        policy_name, role_name = attach_iam_policy_expected
        _, stdout, _ = run_sh(f"aws iam list-attached-role-policies --role-name {role_name}", silent=True)

        # assert that there wasn't an error
        assert stdout != ""

        # parse stdout and check for bucket
        policies = json.loads(stdout)
        policy_names = list(map(lambda policy: policy["PolicyName"], policies["AttachedPolicies"]))
        assert policy_name in policy_names

        # remove policy from role
        _ = run_sh(f"aws iam delete-role-policy --role-name {role_name} --policy-name {policy_name}")
