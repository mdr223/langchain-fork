from redshift_tests.fixtures import *
from redshift_tests.inputs import *
from redshift_tests.shell import run_sh

from langchain.tools.aws import *

import json
import re


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
    def test_attach_iam_policy(self, agent_chain, attach_iam_policy_input, attach_iam_policy_expected):
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

    # NOTE: KMS keys cannot be deleted, so let's not do this
    #
    # @pytest.mark.parametrize(
    #     "create_kms_key_input,create_kms_key_expected",
    #     [
    #         (CREATE_KMS_KEY_INPUT_1, CREATE_KMS_KEY_EXPECTED_1),
    #         (CREATE_KMS_KEY_INPUT_2, CREATE_KMS_KEY_EXPECTED_2),
    #     ],
    #     ids=[
    #         'create_kms_key_test_1',
    #         'create_kms_key_test_2',
    #     ]
    # )
    # def test_create_kms_key(self, agent_chain, create_kms_key_input, create_kms_key_expected):
    #     # execute agent given input
    #     output = agent_chain.run(input=create_kms_key_input)
    #     kms_key_id = re.match("*`KeyId`: (.*)", output)
    #     kms_key_id = kms_id.strip()

    #     # run command to see if it created kms key
    #     policy_name, role_name = create_kms_key_expected
    #     _, stdout, _ = run_sh(f"aws kms list-keys", silent=True)

    #     # assert that there wasn't an error
    #     assert stdout != ""

    #     # parse stdout and check for bucket
    #     keys = json.loads(stdout)
    #     key_ids = list(map(lambda key: key["KeyId"], keys["Keys"]))
    #     assert kms_key_id in key_ids

    #     # check KeySpec
    #     _, stdout, _ = run_sh(f"aws kms describe-key --key-id {kms_key_id}")
    #     kms_key_dict = json.loads(stdout)
    #     assert kms_key_dict['KeyMetadata']['KeySpec'] == create_kms_key_expected

    #     # delete key
    #     _ = run_sh(f"aws iam delete-role-policy --role-name {role_name} --policy-name {policy_name}")

    @pytest.mark.parametrize(
        "create_redshift_cluster_input,create_redshift_cluster_expected",
        [
            (REDSHIFT_CLUSTER_INPUT_1, REDSHIFT_CLUSTER_EXPECTED_1),
            (REDSHIFT_CLUSTER_INPUT_2, REDSHIFT_CLUSTER_EXPECTED_2),
            (REDSHIFT_CLUSTER_INPUT_3, REDSHIFT_CLUSTER_EXPECTED_3),
        ],
        ids=[
            'redshift_cluster_1',
            'redshift_cluster_2',
            'redshift_cluster_3',
        ]
    )
    def test_redshift_cluster(self, agent_chain, redshift_cluster_input, redshift_cluster_expected):
        # execute agent given input
        create_redshift_cluster_input, delete_redshift_cluster_input = redshift_cluster_input

        # run create cluster command
        _ = agent_chain.run(input=create_redshift_cluster_input)

        # wait for cluster to finish creating
        _ = run_sh(f"aws redshift wait cluster-available --cluster-identifier {cluster_id}")

        # run command to see if it created cluster
        _, stdout, _ = run_sh(f"aws redshift describe-clusters", silent=True)

        # assert that there wasn't an error
        assert stdout != ""

        # check that cluster is present and has correct configuration
        cluster_id, node_type, num_nodes = redshift_cluster_expected
        clusters = json.loads(stdout)
        cluster = list(filter(lambda cluster: cluster['ClusterIdentifier'] == cluster_id, clusters['Clusters']))[0]
        assert cluster['NodeType'] == node_type
        assert cluster['NumberOfNodes'] == num_nodes

        # run delete cluster command
        _ = agent_chain.run(input=delete_redshift_cluster_input)

        # wait for cluster to finish deleting
        _ = run_sh(f"aws redshift wait cluster-deleted --cluster-identifier {cluster_id}")

        # run command to see if it deleted cluster
        _, stdout, _ = run_sh(f"aws redshift describe-clusters", silent=True)

        # assert that there wasn't an error
        assert stdout != ""

        # check that cluster is present and has correct configuration
        clusters = json.loads(stdout)
        cluster_ids = list(map(lambda cluster: cluster['ClusterIdentifier'], clusters['Clusters']))
        assert cluster_id not in cluster_ids
