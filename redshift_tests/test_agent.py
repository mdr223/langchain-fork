from redshift_tests.fixtures import *
from redshift_tests.inputs import *
from redshift_tests.shell import run_sh

from langchain.tools.aws import *

import json
import re
import time


def wait_on_create_namespace(namespace_name):
    creating = True
    while creating:
        _, stdout, _ = run_sh(f"aws redshift-serverless get-namespace --namespace-name {namespace_name}")

        # fail fast if stdout is not produced
        if stdout == "":
            raise Exception("Namespace creation failed")

        # read namespace creation status
        namespace = json.loads(stdout)

        # sleep for 15s if it's still creating
        if namespace["namespace"]["status"] == "CREATING":
            time.sleep(15)

        # return if namespace is created
        elif namespace["namespace"]["status"] == "AVAILABLE":
            return

        # otherwise, set creating to False
        else:
            creating = False

    # if the status is not creating and the namespace is not created, raise an exception
    raise Exception("Namespace creation failed")


def wait_on_create_workgroup(workgroup_name):
    creating = True
    while creating:
        _, stdout, _ = run_sh(f"aws redshift-serverless get-workgroup --workgroup-name {workgroup_name}")

        # fail fast if stdout is not produced
        if stdout == "":
            raise Exception("Workgroup creation failed")

        # read workgroup creation status
        workgroup = json.loads(stdout)

        # sleep for 15s if it's still creating
        if workgroup["workgroup"]["status"] == "CREATING":
            time.sleep(15)

        # return if workgroup is created
        elif workgroup["workgroup"]["status"] == "AVAILABLE":
            return

        # otherwise, set creating to False
        else:
            creating = False

    # if the status is not creating and the workgroup is not created, raise an exception
    raise Exception("Workgroup creation failed")


def wait_on_delete_workgroup(workgroup_name):
    deleting = True
    while deleting:
        _, stdout, stderr = run_sh(f"aws redshift-serverless get-workgroup --workgroup-name {workgroup_name}")

        # check if workgroup is still deleting
        if stdout != "":
            workgroup = json.loads(stdout)
            deleting = workgroup["workgroup"]["status"] == "DELETING"

        # if workgroup is deleted then return
        elif stdout == "" and "ResourceNotFoundException" in stderr:
            return

        # otherwise, set deleting to False
        else:
            deleting = False

        if deleting:
            # sleep for 15s if this fails
            time.sleep(15)

    # if the status is not deleting and the workgroup is not deleted, raise an exception
    raise Exception("Workgroup deletion failed")


def wait_on_delete_namespace(namespace_name):
    deleting = True
    while deleting:
        _, stdout, stderr = run_sh(f"aws redshift-serverless get-namespace --namespace-name {namespace_name}")

        # check if namespace is still deleting
        if stdout != "":
            namespace = json.loads(stdout)
            deleting = namespace["namespace"]["status"] == "DELETING"

        # if namespace is deleted then return
        elif stdout == "" and "ResourceNotFoundException" in stderr:
            return

        # otherwise, set deleting to False
        else:
            deleting = False

        if deleting:
            # sleep for 15s if it's still deleting
            time.sleep(15)

    # if the status is not deleting and the namespace is not deleted, raise an exception
    raise Exception("Namespace deletion failed")


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
        # clear memory
        agent_chain.memory.clear()

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
        # clear memory
        agent_chain.memory.clear()

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
        if description is not None:
            assert role['Role']['Description'] == description
        else:
            assert "Description" not in role['Role'].keys()

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
        # clear memory
        agent_chain.memory.clear()

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
        _ = run_sh(f"aws iam detach-role-policy --role-name {role_name} --policy-arn arn:aws:iam::aws:policy/{policy_name}")

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
        "redshift_cluster_input,redshift_cluster_expected",
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
        # clear memory
        agent_chain.memory.clear()

        # execute agent given input
        create_redshift_cluster_input, delete_redshift_cluster_input = redshift_cluster_input

        # run create cluster command
        _ = agent_chain.run(input=create_redshift_cluster_input)

        # get expected info
        cluster_id, node_type, num_nodes = redshift_cluster_expected

        # sleep for 10s and check if cluster was created
        time.sleep(10)
        _, stdout, _ = run_sh(f"aws redshift describe-clusters", silent=True)
        clusters = json.loads(stdout)
        cluster_ids = list(map(lambda cluster: cluster['ClusterIdentifier'], clusters['Clusters']))
        if cluster_id not in cluster_ids:
            raise Exception(f"Cluster {cluster_id} not created")

        # wait for cluster to finish creating
        _ = run_sh(f"aws redshift wait cluster-available --cluster-identifier {cluster_id}")

        # run command to see if it created cluster
        _, stdout, _ = run_sh(f"aws redshift describe-clusters", silent=True)

        # assert that there wasn't an error
        assert stdout != ""

        # check that cluster is present and has correct configuration
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

        # check that cluster is no longer present
        clusters = json.loads(stdout)
        cluster_ids = list(map(lambda cluster: cluster['ClusterIdentifier'], clusters['Clusters']))
        assert cluster_id not in cluster_ids

    @pytest.mark.parametrize(
        "redshift_serverless_input,redshift_serverless_expected",
        [
            (REDSHIFT_SERVERLESS_INPUT_1, REDSHIFT_SERVERLESS_EXPECTED_1),
            (REDSHIFT_SERVERLESS_INPUT_2, REDSHIFT_SERVERLESS_EXPECTED_2),
            # (REDSHIFT_SERVERLESS_INPUT_3, REDSHIFT_SERVERLESS_EXPECTED_3),
        ],
        ids=[
            'redshift_serverless_1',
            'redshift_serverless_2',
            # 'redshift_serverless_3',
        ]
    )
    def test_redshift_serverless(self, agent_chain, redshift_serverless_input, redshift_serverless_expected):
        # clear memory
        agent_chain.memory.clear()

        # execute agent given input
        create_redshift_namespace_input = redshift_serverless_input[0]
        create_redshift_workgroup_input = redshift_serverless_input[1]
        delete_redshift_workgroup_input = redshift_serverless_input[2]
        delete_redshift_namespace_input = redshift_serverless_input[3]
        namespace_name = redshift_serverless_expected["namespaceName"]
        workgroup_name = redshift_serverless_expected["workgroupName"]

        # run create namespace command
        _ = agent_chain.run(input=create_redshift_namespace_input)

        # wait for namespace to finish creating
        wait_on_create_namespace(namespace_name)

        # run create workgroup command
        _ = agent_chain.run(input=create_redshift_workgroup_input)

        # wait for workgroup to finish creating
        wait_on_create_workgroup(workgroup_name)

        # check that workgroup and namespace are created with correct configuration
        _, ns_stdout, _ = run_sh(f"aws redshift-serverless get-namespace --namespace-name {namespace_name}")
        _, wg_stdout, _ = run_sh(f"aws redshift-serverless get-workgroup --workgroup-name {workgroup_name}")
        namespace = json.loads(ns_stdout)
        workgroup = json.loads(wg_stdout)
        for key, value in redshift_serverless_expected["namespaceKeys"].items():
            assert namespace[key] == value

        for key, value in redshift_serverless_expected["workgroupKeys"].items():
            assert workgroup[key] == value

        # run delete workgroup command
        _ = agent_chain.run(input=delete_redshift_workgroup_input)

        # wait for workgroup to finish deleting
        wait_on_delete_workgroup(workgroup_name)

        # run delete namespace command
        _ = agent_chain.run(input=delete_redshift_namespace_input)

        # wait for namespace to finish deleting
        wait_on_delete_namespace(namespace_name)
