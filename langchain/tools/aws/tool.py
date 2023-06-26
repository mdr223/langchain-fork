"""Tools for calling various AWS CLI commands."""
from pydantic.fields import Field
from typing import Optional

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain.tools.base import BaseTool

import boto3
import json
import redshift_connector
import secrets

import pandas as pd

# DEFINITION
# TODO: have AWS account ID read from env. variable
# TODO: use utility to perform environment + setup check(s)
# TODO: break into sub folders for subcommands (e.g. "iam/", "redshift/", "redshift-serverless/", etc.)
AGENT_IAM_ROLE = "arn:aws:iam::518251513740:role/test-rollm-agent-role"
USER_IAM_ROLE = "arn:aws:iam::518251513740:role/Admin"
ASSUME_ROLE_POLICY_DOC = """{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::518251513740:root"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}"""
DEFAULT_BUCKET_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "DefaultBucketPermList",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::518251513740:root"
            },
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::REPLACE"
        },
        {
            "Sid": "DefaultBucketPermRW",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::518251513740:root"
            },
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::REPLACE/*"
        }
    ]
}

ADMIN_USER_PASSWORD = "Testing123"
ADMIN_USERNAME = "agentadmin"
DB_NAME = "dev"
VPC_ID = "vpc-0a8922b2e49b2c963"
MAX_RESULTS = 10

def get_user_iam_role():
    """TODO replace this with a real function that get's the user's IAM role."""
    return USER_IAM_ROLE

def get_vpc_id():
    """TODO replace this with a real function that get's the VPC ID that the agent's EC2 instance is in."""
    return VPC_ID

def create_redshift_security_group(port=5439):
    """Create a security group that allows Redshift traffic on the specified port."""
    ec2_client = boto3.client('ec2')

    # inner function to generate unique security group name(s)
    def create_sg_name():
        hex_string = secrets.token_hex(4)
        return f"redshift-agent-security-group-{hex_string}"

    # generate unique name and create security group; command returns security group ID
    sg_name = create_sg_name()
    vpc_id = get_vpc_id()
    response = ec2_client.create_security_group(
        Description="Security group allowing redshift connection from LLM agent.",
        GroupName=sg_name,
        VpcId=vpc_id,
    )
    sg_id = response['GroupId']

    # update security group to allow Redshift ingress
    ec2_client.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[
            {
                "FromPort": port,
                "ToPort": port,
                "IpProtocol": "tcp",
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            },
        ]
    )

    # update security group to allow all egress
    ec2_client.authorize_security_group_egress(
        GroupId=sg_id,
        IpPermissions=[
            {
                "FromPort": port,
                "ToPort": port,
                "IpProtocol": "-1",
            },
        ]
    )

    return sg_id


class AWSTool(BaseTool):
    """Base class for a tool that calls some specific functionality of the AWS CLI."""
    name = ""         # override
    description = ""  # override

    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        pass

    async def _arun(
        self,
        query: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("Tool does not support async")


class CreateIAMRole(AWSTool):
    """Create an IAM role in the user's AWS account with the given name."""

    name = "Create AWS IAM role"
    description = (
        "This tool creates an IAM role in the user's account with the name provided to the tool."
        "The input to this tool should be the name of the IAM role you wish to create."
        "For example, `MyRole` would be the input if you wanted to create the IAM role `MyRole`."
        "The tool outputs a message indicating the success or failure of the create role operation."
    )

    def _run(
        self,
        role_name: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        iam_client = boto3.client('iam')

        response = None
        try:
            _ = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=ASSUME_ROLE_POLICY_DOC,
                Description='LLM agent created role',
            )
            response = f"Successfully created role {role_name}."

        except Exception as e:
            response = e

        return response


class AttachIAMPolicy(AWSTool):
    """Attach the given IAM policy to the given IAM role in the user's AWS account."""

    name = "Attach AWS IAM policy to AWS IAM role"
    description = (
        "This tool attaches the given IAM policy to the given IAM role."
        "The input to this tool should be a comma separated list of strings of length two, representing the IAM policy you wish to attach and the IAM role you wish to attach it to."
        "For example, `SomePolicy,SomeRole` would be the input if you wanted to attach the policy `SomePolicy` to the role `SomeRole`."
        "The tool outputs a message indicating the success or failure of the attach policy operation."
    )

    def _run(
        self,
        policy_and_role_name: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse policy_name and role_name
        try:
            policy_name = policy_and_role_name.split(',')[0]
            role_name = policy_and_role_name.split(',')[1]
        except Exception as e:
            raise Exception("Failed to parse LLM input to AttachIAMPolicy tool")

        iam_client = boto3.client('iam')

        response = None
        try:
            _ = iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn=f"arn:aws:iam::aws:policy/{policy_name}",
            )
            response = f"Successfully attached policy {policy_name} to role {role_name}."

        except Exception as e:
            response = e

        return response


class CreateKMSKey(AWSTool):
    """Create key in Key Management Service in the user's AWS account."""

    name = "Create Key Management Service (KMS) key"
    description = (
        "This tool creates a KMS key."
        "The tool takes no input."
        "The tool outputs the `KeyId` of the key that it created."
    )

    def _run(
        self,
        input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        kms_client = boto3.client('kms')

        response = None
        try:
            response = kms_client.create_key()
            response = f"Successfully created KMS key with `KeyId`: {response['KeyId']}."
        except Exception as e:
            response = e

        return response


class CreateS3Bucket(AWSTool):
    """Create S3 Bucket in the user's AWS account."""

    name = "Create S3 Bucket"
    description = (
        "This tool creates an S3 bucket with the given bucket name."
        "The input to this tool should be the name of the S3 bucket you want to create."
        "For example, `MyBucket` would be the input if you wanted to create the S3 bucket `MyBucket`."
        "The tool outputs a message indicating the success or failure of the create S3 bucket operation."
    )

    def _run(
        self,
        bucket_name: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        s3_client = boto3.client('s3')

        response = None
        try:
            # create bucket
            _ = s3_client.create_bucket(Bucket=bucket_name)
            
            # Convert the policy from JSON dict to string
            bucket_policy = json.dumps(DEFAULT_BUCKET_POLICY).replace("REPLACE", bucket_name)

            # Set the new policy
            s3_client.put_bucket_policy(Bucket=bucket_name, Policy=bucket_policy)

            response = f"Successfully created S3 Bucket with name {bucket_name}."
        except Exception as e:
            response = e

        return response


class CreateRedshiftCluster(AWSTool):
    """Create a Redshift Cluster in the user's AWS account."""
    name = "Create a Redshift Cluster"
    description = (
        "This tool creates a Redshift Cluster using the given `cluster_name` in the user's AWS account."
        "The input to this tool should be a comma separated list of strings of length one, two, three, or four."
        "If the input is of length one, the string represents the name of the cluster the user wishes to create."
        #"If the input is of length two, the first string represents the name of the cluster and the second string represents the node type to be used in creating the cluster."
        "If the input is of length two, the second string represents the node type to be used in creating the cluster."
        "If the input is of length three, the third string represents the number of nodes to be used in creating the cluster."
        "If the input is of length four, the fourth string represents the security group ID to be used in creating the cluster."
        "For example, `SomeCluster` would be the input if you wanted to create the cluster `SomeCluster`."
        "As another example, `SomeCluster,ds2.xlarge` would be the input if you wanted to create a single-node cluster `SomeCluster` with the node type `ds2.xlarge`."
        "As another example, `SomeCluster,ds2.xlarge,4` would be the input if you wanted to create a multi-node cluster `SomeCluster` with four nodes of node type `ds2.xlarge`."
        "As another example, `SomeCluster,ds2.xlarge,4,sg-0a1b2c3d4e5f67890` would be the input if you wanted to create a multi-node cluster `SomeCluster` with four nodes of node type `ds2.xlarge` using the security group `sg-0a1b2c3d4e5f67890`."
        "The tool outputs a message indicating the success or failure of the create cluster operation."
    )

    def _run(
        self,
        cluster_name_and_nodes: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse cluster_name and node_type (if provided)
        cluster_name, node_type, num_nodes, security_group = None, None, None, None
        try:
            if ',' in cluster_name_and_nodes:
                args = cluster_name_and_nodes.split(',')
                if len(args) == 2:
                    cluster_name = args[0]
                    node_type = args[1]
                    num_nodes = 1
                    security_group = create_redshift_security_group()
                elif len(args) == 3:
                    cluster_name = args[0]
                    node_type = args[1]
                    num_nodes = int(args[2])
                    security_group = create_redshift_security_group()
                elif len(args) == 4:
                    cluster_name = args[0]
                    node_type = args[1]
                    num_nodes = int(args[2])
                    security_group = args[3]
            else:
                cluster_name = cluster_name_and_nodes
                node_type = "ds2.xlarge"
                num_nodes = 1
                security_group = create_redshift_security_group()

        except Exception as e:
            raise Exception("Failed to parse LLM input to CreateRedshiftCluster tool")

        rs_client = boto3.client('redshift')

        response = None
        try:
            user_iam_role = get_user_iam_role()
            _ = rs_client.create_cluster(
                DBName=DB_NAME,
                ClusterIdentifier=cluster_name,
                ClusterType="multi-node" if num_nodes > 1 else "single-node",
                NodeType=node_type,
                NumberOfNodes=num_nodes,
                MasterUsername=ADMIN_USERNAME,
                MasterUserPassword=ADMIN_USER_PASSWORD,
                DefaultIamRoleArn=AGENT_IAM_ROLE,
                IamRoles=[AGENT_IAM_ROLE, user_iam_role],
                VpcSecurityGroupIds=[security_group],
            )
            response = f"Successfully created Redshift cluster {cluster_name}."
        except Exception as e:
            response = e

        return response


class CreateRedshiftServerlessNamespace(AWSTool):
    """Create a namespace for Redshift Serverless in the user's AWS account."""

    name = "Create a namespace for Redshift Serverless"
    description = (
        "This tool creates a Redshift Serverless namespace using the given `namespace_name` in the user's AWS account."
        "The input to this tool should be a comma separated list of strings of length one or length two."
        "If the input is of length one, the string represents the name of the namespace the user wishes to create."
        "If the input is of length two, the first string represents the name of the namespace and the second string represents the KMS KeyId to be used in creating the namespace."
        "For example, `SomeNamespace` would be the input if you wanted to create the namespace `SomeNamespace`."
        "As another example, `SomeNamespace,SomeKeyId` would be the input if you wanted to create the namespace `SomeNamespace` with the KMS key with KeyId `SomeKeyId`."
        "The tool outputs a message indicating the success or failure of the create namespace operation."
    )

    def _run(
        self,
        namespace_name_and_kms_key_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse namespace_name and kms_key_id (if provided)
        namespace_name, kms_key_id = None, None
        try:
            if ',' in namespace_name_and_kms_key_id:
                namespace_name = namespace_name_and_kms_key_id.split(',')[0]
                kms_key_id = namespace_name_and_kms_key_id.split(',')[1]
            else:
                namespace_name = namespace_name_and_kms_key_id
        except Exception as e:
            raise Exception("Failed to parse LLM input to CreateRedshiftServerlessNamespace tool")

        rs_client = boto3.client('redshift-serverless')

        response = None
        try:
            user_iam_role = get_user_iam_role()
            if kms_key_id is None or kms_key_id == "":
                _ = rs_client.create_namespace(
                    namespaceName=namespace_name,
                    adminUserPassword=ADMIN_USER_PASSWORD,
                    adminUsername=ADMIN_USERNAME,
                    dbName=DB_NAME,
                    defaultIamRoleArn=AGENT_IAM_ROLE,
                    iamRoles=[AGENT_IAM_ROLE, user_iam_role],
                )
            else:
                _ = rs_client.create_namespace(
                    namespaceName=namespace_name,
                    kmsKeyId=kms_key_id,
                    adminUserPassword=ADMIN_USER_PASSWORD,
                    adminUsername=ADMIN_USERNAME,
                    dbName=DB_NAME,
                    defaultIamRoleArn=AGENT_IAM_ROLE,
                    iamRoles=[AGENT_IAM_ROLE, user_iam_role],
                )
            response = f"Successfully created Redshift Serverless namespace {namespace_name}."
        except Exception as e:
            response = e

        return response

class CreateRedshiftServerlessWorkgroup(AWSTool):
    """Create a workgroup for Redshift Serverless in the user's AWS account."""

    name = "Create a workgroup for Redshift Serverless"
    description = (
        "This tool creates a Redshift Serverless workgroup using the given `workgroup_name` in the namespace specified by `namespace_name`."
        "The input to this tool should be a comma separated list of strings of length two or three."
        "If the input is of length two, the first string represents the name of the workgroup you wish to create (i.e. `workgroup_name`) and the second string represents namespace it should be created in (i.e. `namespace_name`)."
        "If the input is of length three, the third string represents the security group ID to be used in creating the workgroup."
        "For example, `SomeWorkgroup,SomeNamespace` would be the input if you wanted to create the workgroup `SomeWorkgroup` in the namespace `SomeNamespace`."
        "As another example, `SomeWorkgroup,SomeNamespace,sg-0a1b2c3d4e5f67890` would be the input if you wanted to create the workgroup `SomeWorkgroup` in the namespace `SomeNamespace` using the security group `sg-0a1b2c3d4e5f67890`."
        "The tool outputs a message indicating the success or failure of the create workgroup operation."
    )

    def _run(
        self,
        workgroup_and_namespace_names: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse workgroup_name and namespace_name
        workgroup_name, namespace_name, security_group = None, None, None
        try:
            args = workgroup_and_namespace_names.split(',')
            if len(args) == 2:
                workgroup_name = args[0]
                namespace_name = args[1]
                security_group = create_redshift_security_group()
            elif len(args) == 3:
                workgroup_name = args[0]
                namespace_name = args[1]
                security_group = args[2]
        except Exception as e:
            raise Exception("Failed to parse LLM input to CreateRedshiftServerlessWorkgroup tool")

        rs_client = boto3.client('redshift-serverless')

        response = None
        try:
            _ = rs_client.create_workgroup(
                workgroupName=workgroup_name,
                namespaceName=namespace_name,
                securityGroupIds=[security_group],
            )
            response = f"Successfully created Redshift Serverless workgroup {workgroup_name} in namespace {namespace_name}."
        except Exception as e:
            response = e

        return response


class DeleteRedshiftCluster(AWSTool):
    """Delete a cluster from Redshift in the user's AWS account."""

    name = "Delete a cluster from Redshift"
    description = (
        "This tool deletes a Redshift cluster using the given `cluster_name`."
        "The input to this tool should be a string representing the name of the cluster you wish to delete (i.e. `cluster_name`)."
        "For example, `SomeCluster` would be the input if you wanted to delete the cluster `SomeCluster`."
        "The tool outputs a message indicating the success or failure of the delete cluster operation."
    )

    def _run(
        self,
        cluster_name: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        rs_client = boto3.client('redshift')

        response = None
        try:
            # delete the cluster
            _ = rs_client.delete_cluster(
                ClusterIdentifier=cluster_name,
                SkipFinalClusterSnapshot=True,
            )
            response = f"Successfully deleted Redshift cluster {cluster_name}."
        except Exception as e:
            response = e

        return response


class DeleteRedshiftServerlessNamespace(AWSTool):
    """Delete a namespace from Redshift Serverless in the user's AWS account."""

    name = "Delete a namespace from Redshift Serverless"
    description = (
        "This tool deletes a Redshift Serverless namespace using the given `namespace_name` in the user's AWS account."
        "The input to this tool should be a string representing the name of the namespace the user wishes to delete."
        "For example, `SomeNamespace` would be the input if you wanted to delete the namespace `SomeNamespace`."
        "The tool outputs a message indicating the success or failure of the delete namespace operation."
    )

    def _run(
        self,
        namespace_name: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        rs_client = boto3.client('redshift-serverless')

        response = None
        try:
            _ = rs_client.delete_namespace(namespaceName=namespace_name)
            response = f"Successfully deleted Redshift Serverless namespace {namespace_name}."
        except Exception as e:
            response = e

        return response


class DeleteRedshiftServerlessWorkgroup(AWSTool):
    """Delete a workgroup from Redshift Serverless in the user's AWS account."""

    name = "Delete a workgroup from Redshift Serverless"
    description = (
        "This tool deletes a Redshift Serverless workgroup using the given `workgroup_name`."
        "The input to this tool should be a string representing the name of the workgroup you wish to delete (i.e. `workgroup_name`)."
        "For example, `SomeWorkgroup` would be the input if you wanted to delete the workgroup `SomeWorkgroup`."
        "The tool outputs a message indicating the success or failure of the delete workgroup operation."
    )

    def _run(
        self,
        workgroup_name: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        rs_client = boto3.client('redshift-serverless')

        response = None
        try:
            # delete the workgroup
            res = rs_client.delete_workgroup(workgroupName=workgroup_name)
            response = f"Successfully deleted Redshift Serverless workgroup {workgroup_name} from namespace {res['workgroup']['namespaceName']}."
        except Exception as e:
            response = e

        return response


class LoadTableFromS3Cluster(AWSTool):
    """Load a table from a parquet file or prefix in S3 into a Redshift Cluster."""

    name = "Load a table from S3 into a provisioned Redshift cluster."
    description = (
        "This tool loads a database table from a (set of) parquet file(s) in S3 into a provisioned Redshift cluster."
        "The input to this tool should be a comma separated list of strings of length two, representing the s3 key or prefix of the dataset you wish to load into redshift and the name of the Redshift cluster you wish to load the data into."
        "For example, `s3://somebucket/someprefix/file.pq,SomeCluster` would be the input if you wanted to load the data from `s3://somebucket/someprefix/file.pq` into a database table in the cluster `SomeCluster`."
        "The tool outputs a message indicating the success or failure of the load table operation."
    )

    def _run(
        self,
        input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse s3_key_or_prefix and cluster_name from input
        try:
            s3_key_or_prefix = input.split(',')[0]
            cluster_name = input.split(',')[1]
        except Exception as e:
            raise Exception("Failed to parse LLM input to LoadTableFromS3Cluster tool")

        # create database connection; TODO: fetch the `some-id` part dynamically
        # - hostname format: cluster-name.some-id.aws-region.redshift.amazonaws.com
        # - mrusso-cluster.chcgpkxl6sbm.us-east-1.redshift.amazonaws.com:5439/dev
        conn = redshift_connector.connect(
            host=f"{cluster_name}.chcgpkxl6sbm.us-east-1.redshift.amazonaws.com",
            database=DB_NAME,
            user=ADMIN_USERNAME,
            password=ADMIN_USER_PASSWORD,
        )
        cursor = conn.cursor()

        # try executing query to load table
        # TODO: remove dummy values
        create_table_cmd = """CREATE TABLE mini_table (
            order_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            amount INTEGER NOT NULL
        );
        """
        copy_table_cmd = f"""COPY mini_table FROM '{s3_key_or_prefix}' IAM_ROLE '{AGENT_IAM_ROLE}' FORMAT AS parquet"""

        response = None
        try:
            cursor.execute(create_table_cmd)
            cursor.execute(copy_table_cmd)
            conn.commit()
            response = f"Successfully created table mini_table in {cluster_name}."
        except Exception as e:
            response = e

        return response


class LoadTableFromS3Serverless(AWSTool):
    """Load a table from a parquet file or prefix in S3 into Redshift Serverless."""

    name = "Load a table from S3 into a workgroup/database in Redshift Serverless."
    description = (
        "This tool loads a database table from a (set of) parquet file(s) in S3 into a workgroup/database in Redshift Serverless."
        "The input to this tool should be a comma separated list of strings of length two, representing the s3 key or prefix of the dataset you wish to load into redshift and the name of the Redshift Serverless workgroup you wish to load the data into."
        "For example, `s3://somebucket/someprefix/file.pq,SomeWorkgroup` would be the input if you wanted to load the data from `s3://somebucket/someprefix/file.pq` into a database table in the workgroup `SomeWorkgroup`."
        "The tool outputs a message indicating the success or failure of the load table operation."
    )

    def _run(
        self,
        input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse s3_key_or_prefix and workgroup_name from input
        try:
            s3_key_or_prefix = input.split(',')[0]
            workgroup_name = input.split(',')[1]
        except Exception as e:
            raise Exception("Failed to parse LLM input to LoadTableFromS3Serverless tool")

        # create database connection
        # - hostname format: workgroup-name.account-number.aws-region.redshift-serverless.amazonaws.com
        conn = redshift_connector.connect(
            host=f"{workgroup_name}.518251513740.us-east-1.redshift-serverless.amazonaws.com",
            database=DB_NAME,
            user=ADMIN_USERNAME,
            password=ADMIN_USER_PASSWORD,
        )
        cursor = conn.cursor()

        # try executing query to load table
        # TODO: remove dummy values
        create_table_cmd = """CREATE TABLE mini_table (
            order_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            amount INTEGER NOT NULL
        );
        """
        copy_table_cmd = f"""COPY mini_table FROM '{s3_key_or_prefix}' IAM_ROLE '{AGENT_IAM_ROLE}' FORMAT AS parquet"""

        response = None
        try:
            cursor.execute(create_table_cmd)
            cursor.execute(copy_table_cmd)
            conn.commit()
            response = f"Successfully created table mini_table in {workgroup_name}."
        except Exception as e:
            response = e

        return response


class SelectQueryDataFromTableServerless(AWSTool):
    """Perform a select query on a specified table in Redshift."""

    name = "Run a select query on a table in Redshift Serverless."
    description = (
        "This tool runs a select query on a given table in Redshift Serverless."
        "The input to this tool should be a comma separated list of strings."
        "The first string represents the name of the workgroup the table lives in."
        "The second string represents the name of the table to query."
        "All subsequent strings represent the names of columns to query from the table."
        "For example, `SomeWorkgroup,SomeTable,ColumnA,ColumnB` would be the input if you wanted to query the columns `ColumnA` and `ColumnB` from the table `SomeTable` in the workgroup `SomeWorkgroup`."
        "The tool outputs a message indicating the success or failure of the query operation."
    )

    def _run(
        self,
        input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse workgroup_name, table_name, and columns from input
        workgroup_name, table_name, columns = None, None, None
        try:
            args = input.split(',')
            workgroup_name = args[0]
            table_name = args[1]
            columns = args[2:]
        except Exception as e:
            raise Exception("Failed to parse LLM input to SelectQueryDataFromTable tool")

        # create database connection
        # - hostname format: workgroup-name.account-number.aws-region.redshift-serverless.amazonaws.com
        conn = redshift_connector.connect(
            host=f"{workgroup_name}.518251513740.us-east-1.redshift-serverless.amazonaws.com",
            database=DB_NAME,
            user=ADMIN_USERNAME,
            password=ADMIN_USER_PASSWORD,
        )
        cursor = conn.cursor()

        # try executing select query on table
        column_str = ",".join(columns)
        select_cmd = f"""SELECT {column_str} FROM {table_name};"""

        response = None
        try:
            cursor.execute(select_cmd)
            result = cursor.fetchall()
            result_df = pd.DataFrame(result, columns=columns)
            response = f"{result_df.head(MAX_RESULTS)}"
        except Exception as e:
            response = e

        return response
