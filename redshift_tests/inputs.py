from redshift_tests.shell import run_sh

import pytest

###################################################################
######################### BASIC TESTS #############################
###################################################################

#######################################
###### Create S3 bucket input(s) ######
#######################################
CREATE_BUCKET_INPUT_1 = "Please create an S3 bucket called mrusso-test-bucket1"
CREATE_BUCKET_EXPECTED_1 = "mrusso-test-bucket1", "us-east-2"

CREATE_BUCKET_INPUT_2 = "Please create an S3 bucket called mrusso-test-bucket2 in us-west-2"
CREATE_BUCKET_EXPECTED_2 = "mrusso-test-bucket2", "us-west-2"

CREATE_BUCKET_INPUT_3 = "Please create an S3 bucket called mrusso-test-bucket3 with the BucketOwnerEnforced"
CREATE_BUCKET_EXPECTED_3 = "mrusso-test-bucket3", "us-east-2"

#######################################
###### Create IAM Role input(s) #######
#######################################
CREATE_IAM_ROLE_INPUT_1 = "Please create an IAM role called mrusso-test-role1"
CREATE_IAM_ROLE_EXPECTED_1 = "mrusso-test-role1", None

CREATE_IAM_ROLE_INPUT_2 = "Please create an IAM role called mrusso-test-role2 with the description 'testing 123'"
CREATE_IAM_ROLE_EXPECTED_2 = "mrusso-test-role2", "testing 123"

#########################################
###### Attach IAM Policy input(s) #######
#########################################
ATTACH_IAM_POLICY_INPUT_1 = "Please attach the IAM policy CloudWatchLogsFullAccess to the IAM role redshift-llm-agent-role"
ATTACH_IAM_POLICY_EXPECTED_1 = "CloudWatchLogsFullAccess", "redshift-llm-agent-role"

ATTACH_IAM_POLICY_INPUT_2 = "Please attach CloudWatchLogsReadOnlyAccess to redshift-llm-agent-role"
ATTACH_IAM_POLICY_EXPECTED_2 = "CloudWatchLogsReadOnlyAccess", "redshift-llm-agent-role"

# NOTE: KMS keys cannot be deleted, so let's not do this
# #########################################
# ######## Create KMS Key input(s) ########
# #########################################
# CREATE_KMS_KEY_INPUT_1 = "Please create a KMS key."
# CREATE_KMS_KEY_EXPECTED_1 = "SYMMETRIC_DEFAULT"

# CREATE_KMS_KEY_INPUT_2 = "Please create a KMS key using RSA 3072."
# CREATE_KMS_KEY_EXPECTED_2 = "RSA_3072"

########################################################
###### Create / Delete Redshift Cluster input(s) #######
########################################################
REDSHIFT_CLUSTER_INPUT_1 = ("Please create a redshift cluster called MRussoTestCluster1", "Please delete MRussoTestCluster1")
REDSHIFT_CLUSTER_EXPECTED_1 = "MRussoTestCluster1", "ds2.xlarge", 2

REDSHIFT_CLUSTER_INPUT_2 = ("Please create a single-node redshift cluster called MRussoSingleNodeTestCluster", "Please delete MRussoSingleNodeTestCluster")
REDSHIFT_CLUSTER_EXPECTED_2 = "MRussoSingleNodeTestCluster", "ds2.xlarge", 1

REDSHIFT_CLUSTER_INPUT_3 = ("Please create a redshift cluster called MRussoTestCluster2 with 3 nodes of type dc2.large.", "Please delete MRussoTestCluster2")
REDSHIFT_CLUSTER_EXPECTED_3 = "MRussoTestCluster2", "dc2.large", 3

###########################################################
###### Create / Delete Redshift Serverless input(s) #######
###########################################################
REDSHIFT_SERVERLESS_INPUT_1 = (
    "Please create a redshift serverless namespace called MRussoTestNamespace1",
    "Please create a redshift serverless workgroup called MRussoTestWorkgroup1",
    "Please delete MRussoTestWorkgroup1",
    "Please delete MRussoTestNamespace1",
)
REDSHIFT_SERVERLESS_EXPECTED_1 = {
    "namespaceName": "MRussoTestNamespace1",
    "workgroupName": "MRussoTestWorkgroup1",
    "namespaceKeys": {},
    "workgroupKeys": {},
}

REDSHIFT_SERVERLESS_INPUT_2 = (
    "Please create a redshift serverless namespace called MRussoTestNamespace2 with admin username 'hello', password 'world', and database 'fugazi'",
    "Please create a redshift serverless workgroup called MRussoTestWorkgroup2 using port 1234 and security group sg-38485253",
    "Please delete MRussoTestWorkgroup2",
    "Please delete MRussoTestNamespace2",
)
REDSHIFT_SERVERLESS_EXPECTED_2 = {
    "namespaceName": "MRussoTestNamespace2",
    "workgroupName": "MRussoTestWorkgroup2",
    "namespaceKeys": {
        "adminUsername": "hello",
        "dbName": "fugazi",
    },
    "workgroupKeys": {
        "port": 1234,
        "securityGroupIds": ["sg-38485253"],
    },
}
