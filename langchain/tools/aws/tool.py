"""Tools for calling various AWS CLI commands."""
from pydantic.fields import Field
from typing import Dict, Optional

# TODO: move this into langchain
from redshift_tests.shell import run_sh
from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain.tools.base import BaseTool

import boto3
import json
import pyarrow.parquet
import redshift_connector
import secrets

import pandas as pd

# DEFINITION
# TODO: have AWS account ID fed into relevant tools
# TODO: use utility to perform environment + setup check(s)
# TODO: break into sub folders for subcommands (e.g. "iam/", "redshift/", "redshift-serverless/", etc.)
AGENT_IAM_ROLE = "arn:aws:iam::276726865914:role/redshift-llm-agent-role"
USER_IAM_ROLE = "arn:aws:iam::276726865914:role/Admin"
ASSUME_ROLE_POLICY_DOC = """{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::276726865914:root"
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
                "AWS": "arn:aws:iam::276726865914:root"
            },
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::REPLACE"
        },
        {
            "Sid": "DefaultBucketPermRW",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::276726865914:root"
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
VPC_ID = "vpc-3cd2a454"
MAX_RESULTS = 10
PANDAS_TYPE_TO_REDSHIFT_TYPE = {
    "int32": "INTEGER"
}

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


class ToolSearch(BaseTool):
    """Tool that's used to look up the descriptions of other tools."""
    name = "ToolSearch"
    description = (
        "This tool looks up and returns the descriptions of other tools provided to the LLM agent. This can help the agent decide which tool to use to respond to a user's input, as well as how to use that tool."
        " The input to this tool should be a comma separated list of one or more strings."
        " Each string is the name of another tool provided to the LLM agent, which the agent would like to lookup the description for."
        " For example, `SomeToolA,SomeToolB` would be the input if you wanted to look up the descriptions of tools `SomeToolA` and `SomeToolB` and learn how to properly use them."
        " This tool's output contains the descriptions of all the tools that are provided as input."
    )
    tool_descriptions: Dict[str, str] = {}

    @property
    def short_description(self) -> str:
        return self.description

    def _run(
        self,
        tool_names: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        tool_description_str = "\n"
        try:
            tool_name_list = [tool_name.strip().strip(" ").strip('"') for tool_name in tool_names.split(",")]
            for tool_name in tool_name_list:
                if tool_name in self.tool_descriptions:
                    tool_description_str += f"> {tool_name}: {self.tool_descriptions[tool_name]}\n"
                else:
                    tool_description_str += f"> {tool_name}: no tool with this name was provided to ToolSearch, please double-check spelling and capitalization.\n"

        except Exception as e:
            raise Exception("Failed to parse LLM input to ToolSearch tool")

        return tool_description_str

    async def _arun(
        self,
        tools: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("Tool does not support async")


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


# class BashAWSTool(BaseTool):
#     """Base class for a tool that calls some specific functionality of the AWS CLI."""
#     name = "BashAWSTool"
#     description = """This tool executes AWS CLI commands that are passed into it.

#     For example, if this tool is given the input:
#     \"\"\"
#     aws create redshift-cluster --cluster-identifier my-cluster --node-type dc2.large --master-username admin --master-user-password SecurePassword123
#     \"\"\"
#     It will execute this aws command and create the Redshift cluster as specified.

#     The only requirement of this tool is that it is provided a syntactically correct AWS CLI v2 command to execute.
#     """

#     @property
#     def short_description(self) -> str:
#         return self.description.split('.')[0]

#     def _run(
#         self,
#         aws_command: str,
#         run_manager: Optional[CallbackManagerForToolRun] = None,
#     ) -> str:
#         """Use the tool."""
#         # parse input
#         try:
#             aws_command = pass
#         except Exception as e:
#             # TODO: prompt model to try to self-correct up to N times before giving up
#             raise Exception("Failed to parse LLM input to BashAWSTool tool")

#         # execute command
#         # TODO: also try to self-correct command up to N times here
#         _, stdout, stderr = run_sh(aws_command)

#         # prepare and return response
#         response = stdout if stdout != "" else stderr

#         return response


class CreateIAMRole(AWSTool):
    """Create an IAM role in the user's AWS account with the given name."""

    name = "CreateIAMRole"
 
    # NOTE: removed {"AssumeRolePolicyDocument": "string",} from tool input
    description = """This tool creates an IAM role in the user's account with the name provided to the tool.

    The input to this tool should be a JSON dictionary object with the following format:
    ```
    {
        "RoleName": "`role_name`",
        "Path": "string",
        "Description": "string",
        "MaxSessionDuration": 123,
        "PermissionsBoundary": "string",
        "Tags": [
            {
                "Key": "string",
                "Value": "string"
            },
        ]
    }
    ```
    The following dictionary keys are *REQUIRED*: `RoleName`

    All other dictionary keys are optional.
    
    *IMPORTANT*: If a user's request does not explicitly or implicitly instruct you how to set an optional key, then simply omit that key from the JSON you generate.

    JSON values inside of `` are meant to be filled by the agent.
    JSON values separated by | represent the unique set of values that may used.
    Otherwise, the data type of the value is shown.

    For example, if you wanted to create the IAM role `MyRole` you would generate the JSON:
    ```
    {
        "RoleName": "MyRole"
    }
    ```

    The tool outputs a message indicating the success or failure of the create IAM role operation.
    """

    @property
    def short_description(self) -> str:
        return self.description.split('.')[0]

    def _run(
        self,
        create_role_json: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse JSON
        create_role_kwargs = None
        try:
            create_role_kwargs = json.loads(create_role_json.strip().strip('`').strip('>'))
        except Exception as e:
            raise Exception("Failed to parse LLM input to CreateIAMRole tool")

        iam_client = boto3.client('iam')

        response = None
        try:
            create_role_kwargs["AssumeRolePolicyDocument"] = ASSUME_ROLE_POLICY_DOC
            _ = iam_client.create_role(**create_role_kwargs)
            response = f"Successfully created role {create_role_kwargs['RoleName']}."

        except Exception as e:
            response = e

        return response


class AttachIAMPolicy(AWSTool):
    """Attach the given IAM policy to the given IAM role in the user's AWS account."""

    name = "AttachIAMPolicy"
    description = """This tool attaches the given IAM policy to the given IAM role.

    The input to this tool should be a JSON dictionary object with the following format:
    ```
    {
        "RoleName": "`role_name`",
        "PolicyArn": "`policy_arn`"
    }
    ```
    The following dictionary keys are *REQUIRED*: `RoleName`, `PolicyArn`

    All other dictionary keys are optional.

    *IMPORTANT*: If a user's request does not explicitly or implicitly instruct you how to set an optional key, then simply omit that key from the JSON you generate.

    JSON values inside of `` are meant to be filled by the agent.
    JSON values separated by | represent the unique set of values that may used.
    Otherwise, the data type of the value is shown.

    For example, if you wanted to attch the IAM policy `SomePolicy` to the IAM role `MyRole` you would generate the JSON:
    ```
    {
        "RoleName": "MyRole",
        "PolicyArn": "arn:aws:iam::aws:policy/SomePolicy"
    }
    ```

    The tool outputs a message indicating the success or failure of the attach IAM policy operation.
    """

    @property
    def short_description(self) -> str:
        return self.description.split('.')[0]

    def _run(
        self,
        attach_policy_json: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse JSON
        attach_policy_kwargs = None
        try:
            attach_policy_kwargs = json.loads(attach_policy_json.strip().strip('`').strip('>'))
        except Exception as e:
            raise Exception("Failed to parse LLM input to AttachIAMPolicy tool")

        iam_client = boto3.client('iam')

        response = None
        try:
            _ = iam_client.attach_role_policy(**attach_policy_kwargs)
            response = f"Successfully attached policy {attach_policy_kwargs['PolicyArn']} to role {attach_policy_kwargs['RoleName']}."

        except Exception as e:
            response = e

        return response


class CreateKMSKey(AWSTool):
    """Create key in Key Management Service in the user's AWS account."""

    name = "CreateKMSKey"
    description = """This tool creates a KMS key.

    The input to this tool should be a JSON dictionary object with the following format:
    ```
    {
        "Policy": "string",
        "Description": "string",
        "KeyUsage": "SIGN_VERIFY"|"ENCRYPT_DECRYPT"|"GENERATE_VERIFY_MAC",
        "CustomerMasterKeySpec": "RSA_2048"|"RSA_3072"|"RSA_4096"|"ECC_NIST_P256"|"ECC_NIST_P384"|"ECC_NIST_P521"|"ECC_SECG_P256K1"|"SYMMETRIC_DEFAULT"|"HMAC_224"|"HMAC_256"|"HMAC_384"|"HMAC_512"|"SM2",
        "KeySpec": "RSA_2048"|"RSA_3072"|"RSA_4096"|"ECC_NIST_P256"|"ECC_NIST_P384"|"ECC_NIST_P521"|"ECC_SECG_P256K1"|"SYMMETRIC_DEFAULT"|"HMAC_224"|"HMAC_256"|"HMAC_384"|"HMAC_512"|"SM2",
        "Origin": "AWS_KMS"|"EXTERNAL"|"AWS_CLOUDHSM"|"EXTERNAL_KEY_STORE",
        "CustomKeyStoreId": "string",
        "BypassPolicyLockoutSafetyCheck": True|False,
        "Tags": [
            {
                "TagKey": "string",
                "TagValue": "string"
            },
        ],
        "MultiRegion": True|False,
        "XksKeyId": "string"
    }
    ```
    All dictionary keys are optional.

    *IMPORTANT*: If a user's request does not explicitly or implicitly instruct you how to set an optional key, then simply omit that key from the JSON you generate.

    JSON values inside of `` are meant to be filled by the agent.
    JSON values separated by | represent the unique set of values that may used.
    Otherwise, the data type of the value is shown.

    For example, if you wanted to create a KMS key with no custom arguments you generate the JSON:
    ```
    {}
    ```

    As another example, if you wanted to create a KMS key with a key policy called "SomePolicy" and an Asymmetric RSA key pair, then you could generate the JSON:
    ```
    {
        "Policy": "arn:aws:iam::aws:policy/SomePolicy",
        "KeySpec": "RSA_4096"
    }
    ```

    The tool outputs the `KeyId` of the key that it created.
    """

    @property
    def short_description(self) -> str:
        return self.description.split('.')[0]

    def _run(
        self,
        create_kms_key_json: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse JSON
        create_kms_key_kwargs = None
        try:
            create_kms_key_kwargs = json.loads(create_kms_key_json.strip().strip('`').strip('>'))
        except Exception as e:
            raise Exception("Failed to parse LLM input to CreateKMSKey tool")

        kms_client = boto3.client('kms')

        response = None
        try:
            response = kms_client.create_key(**create_kms_key_kwargs)
            response = f"Successfully created KMS key with `KeyId`: {response['KeyId']}."
        except Exception as e:
            response = e

        return response


class CreateS3Bucket(AWSTool):
    """Create S3 Bucket in the user's AWS account."""

    name = "CreateS3Bucket"
    description = """This tool creates an S3 bucket with the given bucket name.

    The input to this tool should be a JSON dictionary object with the following format:
    ```
    {
        "Bucket": "`bucket_name`",
        "ACL": "private"|"public-read"|"public-read-write"|"authenticated-read",
        "CreateBucketConfiguration": {
            "LocationConstraint": "af-south-1"|"ap-east-1"|"ap-northeast-1"|"ap-northeast-2"|"ap-northeast-3"|"ap-south-1"|"ap-southeast-1"|"ap-southeast-2"|"ap-southeast-3"|"ca-central-1"|"cn-north-1"|"cn-northwest-1"|"EU"|"eu-central-1"|"eu-north-1"|"eu-south-1"|"eu-west-1"|"eu-west-2"|"eu-west-3"|"me-south-1"|"sa-east-1"|"us-east-2"|"us-gov-east-1"|"us-gov-west-1"|"us-west-1"|"us-west-2"
        },
        "GrantFullControl": "string",
        "GrantRead": "string",
        "GrantReadACP": "string",
        "GrantWrite": "string",
        "GrantWriteACP": "string",
        "ObjectLockEnabledForBucket": True|False,
        "ObjectOwnership": "BucketOwnerPreferred"|"ObjectWriter"|"BucketOwnerEnforced"
    }
    ```
    The following dictionary keys are *REQUIRED*: `Bucket`, `CreateBucketConfiguration`

    All other dictionary keys are optional.
    
    *IMPORTANT*: If a user's request does not explicitly or implicitly instruct you how to set an optional key, then simply omit that key from the JSON you generate. If a user does not specify which region to create a bucket in, use us-east-2.

    JSON values inside of `` are meant to be filled by the agent.
    JSON values separated by | represent the unique set of values that may used.
    Otherwise, the data type of the value is shown.

    For example, if you wanted to create the S3 bucket `MyBucket` you would generate the JSON:
    ```
    {
        "Bucket": "MyBucket",
        "CreateBucketConfiguration": {
            "LocationConstraint": "us-east-2"
        }
    }
    ```

    As another example, if you wanted to create the S3 Bucket `MyBucket` in us-west-2 you would generate the JSON:
    ```
    {
        "Bucket": "MyBucket",
        "CreateBucketConfiguration": {
            "LocationConstraint": "us-west-2"
        }
    }
    ```

    The tool outputs a message indicating the success or failure of the create S3 bucket operation.
    """

    @property
    def short_description(self) -> str:
        return self.description.split('.')[0]

    def _run(
        self,
        create_bucket_json: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse JSON
        create_bucket_kwargs = None
        try:
            create_bucket_kwargs = json.loads(create_bucket_json.strip().strip('`').strip('>'))
        except Exception as e:
            raise Exception("Failed to parse LLM input to CreateS3Bucket tool")

        # create S3 client
        s3_client = (
            boto3.client('s3')
            if "CreateBucketConfiguration" not in create_bucket_kwargs and "LocationConstraint" not in create_bucket_kwargs["CreateBucketConfiguration"]
            else boto3.client('s3', region_name=create_bucket_kwargs["CreateBucketConfiguration"]["LocationConstraint"])
        )

        response = None
        try:
            # create bucket
            _ = s3_client.create_bucket(**create_bucket_kwargs)
            
            # Convert the policy from JSON dict to string
            bucket_policy = json.dumps(DEFAULT_BUCKET_POLICY).replace("REPLACE", create_bucket_kwargs['Bucket'])

            # Set the new policy
            s3_client.put_bucket_policy(Bucket=create_bucket_kwargs['Bucket'], Policy=bucket_policy)

            response = f"Successfully created S3 Bucket with name {create_bucket_kwargs['Bucket']}."
        except Exception as e:
            response = e

        return response


class CreateRedshiftCluster(AWSTool):
    """Create a Redshift cluster in the user's AWS account."""
    name = "CreateRedshiftCluster"
    description = """This tool creates a Redshift Cluster using the given `cluster_name` in the user's AWS account.

    The input to this tool should be a JSON dictionary object with the following format:
    ```
    {
        "ClusterIdentifier": "`cluster_name`",
        "NodeType": "ds2.xlarge"|"ds2.8xlarge"|"dc1.large"|"dc1.8xlarge"|"dc2.large"|"dc2.8xlarge"|"ra3.xlplus"|"ra3.4xlarge"|"ra3.16xlarge",
        "MasterUsername": "`username`",
        "MasterUserPassword": "`password`",
        "ClusterType": "multi-node"|"single-node",
        "NumberOfNodes": 123,
        "DBName": "string",
        "VpcSecurityGroupIds": [
            "string",
        ],
        "Port": 123,
        "Tags": [
            {
                "Key": "string",
                "Value": "string"
            },
        ],
        "IamRoles": [
            "string",
        ],
        "DefaultIamRoleArn": "string",
    }
    ```
    The following dictionary keys are *REQUIRED*: `ClusterIdentifier`, `NodeType`, `MasterUsername`, `MasterUserPassword`, `ClusterType`, and `NumberOfNodes`.

    *DEFAULTS*:
    If a user does not specify a `NodeType`, then use "dc2.large".
    If a user does not specify a `MasterUsername`, then use "admin".
    If a user does not specify a `MasterUserPassword`, then use "Testing123".
    If a user does not specify a `ClusterType`, then use "multi-node".
    If a user does not specify a `NumberOfNodes`, AND `ClusterType` is "multi-node", then use 2.
    If a user does not specify a `NumberOfNodes`, And `ClusterType` is "single-node", then use 1.

    All other dictionary keys are optional.

    *IMPORTANT*: If a user's request does not explicitly or implicitly instruct you how to set an optional key, then simply omit that key from the JSON you generate.

    JSON values inside of `` are meant to be filled by the agent.
    JSON values separated by | represent the unique set of values that may used.
    Otherwise, the data type of the value is shown.

    For example, if you wanted to create the cluster `MyCluster` you would generate the JSON:
    ```
    {
        "ClusterIdentifier": "MyCluster",
        "NodeType": "dc2.large",
        "MasterUsername": "admin",
        "MasterUserPassword": "Testing123",
        "ClusterType": "multi-node",
        "NumberOfNodes": 2
    }
    ```

    As another example, if you wanted to create a single-node cluster `MyCluster1` with the admin username "hello" and admin password "World" you would generate the JSON:
    ```
    {
        "ClusterIdentifier": "MyCluster1",
        "NodeType": "dc2.large",
        "MasterUsername": "hello",
        "MasterUserPassword": "World",
        "ClusterType": "single-node",
        "NumberOfNodes": 1
    }
    ```

    As another example, if you wanted to create a multi-node cluster `MyCluster2` with four ra3.xlplus nodes you would generate the JSON:
    ```
    {
        "ClusterIdentifier": "MyCluster2",
        "NodeType": "ra3.xlplus",
        "MasterUsername": "admin",
        "MasterUserPassword": "Testing123",
        "ClusterType": "multi-node",
        "NumberOfNodes": 4
    }
    ```

    The tool outputs a message indicating the success or failure of the create Redshift cluster operation.
    """

    @property
    def short_description(self) -> str:
        return self.description.split('.')[0]

    def _run(
        self,
        create_cluster_json: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse JSON
        create_cluster_kwargs = None
        try:
            create_cluster_kwargs = json.loads(create_cluster_json.strip().strip('`').strip('>'))
        except Exception as e:
            raise Exception("Failed to parse LLM input to CreateRedshiftCluster tool")

        rs_client = boto3.client('redshift')
        security_group = create_redshift_security_group()

        # set some kwarg defaults
        if "DBName" not in create_cluster_kwargs:
            create_cluster_kwargs['DBName'] = DB_NAME

        if "DefaultIamRoleArn" not in create_cluster_kwargs:
            create_cluster_kwargs['DefaultIamRoleArn'] = AGENT_IAM_ROLE

        if "IamRoles" not in create_cluster_kwargs:
            user_iam_role = get_user_iam_role()
            create_cluster_kwargs['IamRoles'] = [AGENT_IAM_ROLE, user_iam_role]

        if "VpcSecurityGroupIds" not in create_cluster_kwargs:
            create_cluster_kwargs['VpcSecurityGroupIds'] = [security_group]

        response = None
        try:
            _ = rs_client.create_cluster(**create_cluster_kwargs)
            response = f"Successfully created Redshift cluster {create_cluster_kwargs['ClusterIdentifier']}."
        except Exception as e:
            response = e

        return response


class CreateRedshiftServerlessNamespace(AWSTool):
    """Create a namespace for Redshift Serverless in the user's AWS account."""

    name = "CreateRedshiftServerlessNamespace"
    description = """This tool creates a Redshift Serverless namespace using the given `namespace_name` in the user's AWS account.

    The input to this tool should be a JSON dictionary object with the following format:
    ```
    {
        "namespaceName": "`namespace_name`",
        "adminUserPassword": "string",
        "adminUsername": "string",
        "dbName": "string",
        "defaultIamRoleArn": "string",
        "iamRoles": [
            "string",
        ],
        "kmsKeyId": "string",
        "logExports": [
            "useractivitylog"|"userlog"|"connectionlog",
        ],
        "tags": [
            {
                "key": "string",
                "value": "string"
            },
        ]
    }
    ```
    The following dictionary keys are *REQUIRED*: `namespaceName`

    All other dictionary keys are optional.
    
    *IMPORTANT*: If a user's request does not explicitly or implicitly instruct you how to set an optional key, then simply omit that key from the JSON you generate.

    JSON values inside of `` are meant to be filled by the agent.
    JSON values separated by | represent the unique set of values that may used.
    Otherwise, the data type of the value is shown.

    For example, if you wanted to create the namespace `SomeNamespace` you would generate the JSON:
    ```
    {
        "namespaceName": "SomeNamespace"
    }
    ```

    As another example, if you wanted to create the namespace `SomeNamespace` with the KMS key with KeyId `SomeKeyId` you would generate the JSON:
    ```
    {
        "namespaceName": "SomeNamespace",
        "kmsKeyId": "string"
    }
    ```

    The tool outputs a message indicating the success or failure of the create namespace operation.
    """

    @property
    def short_description(self) -> str:
        return self.description.split('.')[0]

    def _run(
        self,
        create_namespace_json: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse JSON
        create_namespace_kwargs = None
        try:
            create_namespace_kwargs = json.loads(create_namespace_json.strip().strip('`').strip('>'))
        except Exception as e:
            raise Exception("Failed to parse LLM input to CreateRedshiftServerlessNamespace tool")

        rs_client = boto3.client('redshift-serverless')

        response = None
        try:
            # TODO: think through secure way to provide DB credentials
            if 'defaultIamRoleArn' not in create_namespace_kwargs:
                create_namespace_kwargs['defaultIamRoleArn'] = AGENT_IAM_ROLE
            if 'iamRoles' not in create_namespace_kwargs:
                user_iam_role = get_user_iam_role()
                create_namespace_kwargs['iamRoles'] = [AGENT_IAM_ROLE, user_iam_role]

            _ = rs_client.create_namespace(**create_namespace_kwargs)
            response = f"Successfully created Redshift Serverless namespace {create_namespace_kwargs['namespaceName']}."
        except Exception as e:
            response = e

        return response


class CreateRedshiftServerlessWorkgroup(AWSTool):
    """Create a workgroup for Redshift Serverless in the user's AWS account."""

    name = "CreateRedshiftServerlessWorkgroup"
    description = """This tool creates a Redshift Serverless workgroup using the given `workgroup_name` in the namespace specified by `namespace_name`.

    The input to this tool should be a JSON dictionary object with the following format:
    ```
    {
        "workgroupName": "`workgroup_name`",
        "namespaceName": "`namespace_name`",
        "baseCapacity": 123,
        "configParameters": [
            {
                "parameterKey": "string",
                "parameterValue": "string"
            },
        ],
        "enhancedVpcRouting": True|False,
        "port": 123,
        "publiclyAccessible": True|False,
        "securityGroupIds": [
            "string",
        ],
        "subnetIds": [
            "string",
        ],
        "tags": [
            {
                "key": "string",
                "value": "string"
            },
        ]
    }
    ```
    The following dictionary keys are *REQUIRED*: `workgroupName`, `namespaceName`

    All other dictionary keys are optional.
    
    *IMPORTANT*: If a user's request does not explicitly or implicitly instruct you how to set an optional key, then simply omit that key from the JSON you generate.

    JSON values inside of `` are meant to be filled by the agent.
    JSON values separated by | represent the unique set of values that may used.
    Otherwise, the data type of the value is shown.

    For example, if you wanted to create the workgroup `SomeWorkgroup` in the namespace `SomeNamespace` you would generate the JSON:
    ```
    {
        "workgroupName": "SomeWorkgroup",
        "namespaceName": "SomeNamespace"
    }
    ```

    As another example, if you wanted to create the workgroup `SomeWorkgroup` in the namespace `SomeNamespace` using the security group `sg-0a1b2c3d4e5f67890` you would generate the JSON:
    ```
    {
        "workgroupName": "SomeWorkgroup",
        "namespaceName": "SomeNamespace",
        "securityGroupIds": ["sg-0a1b2c3d4e5f67890"]
    }
    ```

    The tool outputs a message indicating the success or failure of the create workgroup operation.
    """

    @property
    def short_description(self) -> str:
        return self.description.split('.')[0]

    def _run(
        self,
        create_workgroup_json: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse JSON
        create_workgroup_kwargs = None
        try:
            create_workgroup_kwargs = json.loads(create_workgroup_json.strip().strip('`').strip('>'))
        except Exception as e:
            raise Exception("Failed to parse LLM input to CreateRedshiftServerlessWorkgroup tool")

        rs_client = boto3.client('redshift-serverless')

        response = None
        try:
            _ = rs_client.create_workgroup(**create_workgroup_kwargs)
            response = f"Successfully created Redshift Serverless workgroup {create_workgroup_kwargs['workgroupName']} in namespace {create_workgroup_kwargs['namespaceName']}."
        except Exception as e:
            response = e

        return response


class DeleteRedshiftCluster(AWSTool):
    """Delete a cluster from Redshift in the user's AWS account."""

    name = "DeleteRedshiftCluster"
    description = """This tool deletes a Redshift cluster using the given cluster identifier.

    The input to this tool should be a JSON dictionary object with the following format:
    ```
    {
        ClusterIdentifier": "`cluster_name`",
        SkipFinalClusterSnapshot": True|False,
        FinalClusterSnapshotIdentifier": "string",
        FinalClusterSnapshotRetentionPeriod": 123
    }
    ```
    The following dictionary keys are *REQUIRED*: `ClusterIdentifier`

    *DEFAULTS*:
    If a user does not specify a `SkipFinalClusterSnapshot`, then use True.

    All other dictionary keys are optional.

    *IMPORTANT*: If a user's request does not explicitly or implicitly instruct you how to set an optional key, then simply omit that key from the JSON you generate.

    JSON values inside of `` are meant to be filled by the agent.
    JSON values separated by | represent the unique set of values that may used.
    Otherwise, the data type of the value is shown.

    For example, if you wanted to delete the cluster `MyCluster` you would generate the JSON:
    ```
    {
        "ClusterIdentifier": "MyCluster",
        "SkipFinalClusterSnapshot": True
    }
    ```

    The tool outputs a message indicating the success or failure of the delete Redshift cluster operation.
    """

    @property
    def short_description(self) -> str:
        return self.description.split('.')[0]

    def _run(
        self,
        delete_cluster_json: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse JSON
        delete_cluster_kwargs = None
        try:
            delete_cluster_kwargs = json.loads(delete_cluster_json.strip().strip('`').strip('>'))
        except Exception as e:
            raise Exception("Failed to parse LLM input to DeleteRedshiftCluster tool")

        rs_client = boto3.client('redshift')

        response = None
        try:
            # delete the cluster
            _ = rs_client.delete_cluster(**delete_cluster_kwargs)
            response = f"Successfully deleted Redshift cluster {delete_cluster_kwargs['ClusterIdentifier']}."
        except Exception as e:
            response = e

        return response


class DeleteRedshiftServerlessNamespace(AWSTool):
    """Delete a namespace from Redshift Serverless in the user's AWS account."""

    name = "DeleteRedshiftServerlessNamespace"
    description = """This tool deletes a Redshift Serverless namespace using the given `namespace_name` in the user's AWS account.

    The input to this tool should be a JSON dictionary object with the following format:
    ```
    {
        "namespaceName": "`namespace_name`",
        "finalSnapshotName": "string",
        "finalSnapshotRetentionPeriod": 123
    }
    ```
    The following dictionary keys are *REQUIRED*: `namespaceName`

    All other dictionary keys are optional.
    
    *IMPORTANT*: If a user's request does not explicitly or implicitly instruct you how to set an optional key, then simply omit that key from the JSON you generate.

    JSON values inside of `` are meant to be filled by the agent.
    JSON values separated by | represent the unique set of values that may used.
    Otherwise, the data type of the value is shown.

    For example, if you wanted to delete the namespace `SomeNamespace` you would generate the JSON:
    ```
    {
        "namespaceName": "SomeNamespace"
    }
    ```

    The tool outputs a message indicating the success or failure of the delete namespace operation.
    """

    @property
    def short_description(self) -> str:
        return self.description.split('.')[0]

    def _run(
        self,
        delete_namespace_json: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse JSON
        delete_namespace_kwargs = None
        try:
            delete_namespace_kwargs = json.loads(delete_namespace_json.strip().strip('`'))
        except Exception as e:
            raise Exception("Failed to parse LLM input to DeleteRedshiftServerlessNamespace tool")

        rs_client = boto3.client('redshift-serverless')

        response = None
        try:
            _ = rs_client.delete_namespace(**delete_namespace_kwargs)
            response = f"Successfully deleted Redshift Serverless namespace {delete_namespace_kwargs['namespaceName']}."
        except Exception as e:
            response = e

        return response


class DeleteRedshiftServerlessWorkgroup(AWSTool):
    """Delete a workgroup from Redshift Serverless in the user's AWS account."""

    name = "DeleteRedshiftServerlessWorkgroup"
    description = """This tool deletes a Redshift Serverless workgroup using the given `workgroup_name`.

    The input to this tool should be a JSON dictionary object with the following format:
    ```
    {
        "workgroupName": "`workgroup_name`"
    }
    ```
    The following dictionary keys are *REQUIRED*: `workgroupName`

    JSON values inside of `` are meant to be filled by the agent.
    JSON values separated by | represent the unique set of values that may used.
    Otherwise, the data type of the value is shown.

    For example, if you wanted to delete the workgroup `SomeWorkgroup` you would generate the JSON:
    ```
    {
        "workgroupName": "SomeWorkgroup"
    }
    ```

    The tool outputs a message indicating the success or failure of the delete workgroup operation.
    """

    @property
    def short_description(self) -> str:
        return self.description.split('.')[0]

    def _run(
        self,
        delete_workgroup_json: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse JSON
        delete_workgroup_kwargs = None
        try:
            delete_workgroup_kwargs = json.loads(delete_workgroup_json.strip().strip('`'))
        except Exception as e:
            raise Exception("Failed to parse LLM input to DeleteRedshiftServerlessWorkgroup tool")

        rs_client = boto3.client('redshift-serverless')

        response = None
        try:
            # delete the workgroup
            res = rs_client.delete_workgroup(**delete_workgroup_kwargs)
            response = f"Successfully deleted Redshift Serverless workgroup {delete_workgroup_kwargs['workgroupName']} from namespace {res['workgroup']['namespaceName']}."
        except Exception as e:
            response = e

        return response


class LoadTableFromS3Cluster(AWSTool):
    """Load a table from a parquet file or prefix in S3 into a Redshift Cluster."""

    name = "LoadTableFromS3Cluster"
    # description = (
    #     "This tool loads a database table from a (set of) parquet file(s) in S3 into a provisioned Redshift cluster."
    #     " The input to this tool should be a comma separated list of strings of length two, representing the s3 key or prefix of the dataset you wish to load into redshift and the name of the Redshift cluster you wish to load the data into."
    #     " For example, `s3://somebucket/someprefix/file.pq,SomeCluster` would be the input if you wanted to load the data from `s3://somebucket/someprefix/file.pq` into a database table in the cluster `SomeCluster`."
    #     " The tool outputs a message indicating the success or failure of the load table operation."
    # )
    description = """This tool loads a database table from a (set of) parquet file(s) in S3 into a provisioned Redshift cluster.

    The input to this tool should be a JSON dictionary object with the following format:
    ```
    {
        "S3Key": "`s3_key_or_prefix`",
        "clusterName": "`cluster_name`",
        "adminUsername": "`username`",
        "adminUserPassword": "`password`",
        "dbName": "`db_name`"
        "tableName": "string"
    }
    ```
    The following dictionary keys are *REQUIRED*: `S3Key`, `clusterName`, `adminUserPassword`, `adminUsername`, `dbName`

    All other dictionary keys are optional.

    *IMPORTANT*: If a user's request does not explicitly or implicitly instruct you how to set an optional key, then simply omit that key from the JSON you generate.

    JSON values inside of `` are meant to be filled by the agent.
    JSON values separated by | represent the unique set of values that may used.
    Otherwise, the data type of the value is shown.

    For example, if you wanted to load the data from `s3://somebucket/someprefix/file.pq` into a database table in the cluster `SomeCluster` using the adminUsername `admin`, adminUserPassword `Testing123`, and database `dev` you would generate the JSON:
    ```
    {
        "S3Key": "s3://somebucket/someprefix/file.pq",
        "clusterName": "SomeCluster",
        "adminUsername": "admin",
        "adminUserPassword": "Testing123",
        "dbName": "dev"
    }
    ```

    The tool outputs a message indicating the success or failure of the load table operation.
    """

    @property
    def short_description(self) -> str:
        return self.description.split('.')[0]

    def _run(
        self,
        input_json: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse JSON
        input_kwargs = None
        try:
            input_kwargs = json.loads(input_json.strip().strip('`'))
        except Exception as e:
            raise Exception("Failed to parse LLM input to LoadTableFromS3Cluster tool")

        # fetch cluster endpoint
        _, stdout, _ = run_sh("aws redshift describe-clusters --no-paginate")
        clusters = json.loads(stdout)
        cluster = list(filter(lambda cluster: cluster['ClusterIdentifier'] == input_kwargs['ClusterIdentifier'], clusters['Clusters']))[0]
        endpoint = cluster['Endpoint']['Address']
        port = int(cluster['Endpoint']['Port'])

        # fill in kwargs
        if "dbName" not in input_kwargs:
            input_kwargs['dbName'] = DB_NAME

        if "adminUsername" not in input_kwargs:
            input_kwargs['adminUsername'] = ADMIN_USERNAME

        if "adminUserPassword" not in input_kwargs:
            input_kwargs['adminUserPassword'] = ADMIN_USER_PASSWORD

        # create database connection
        # - hostname format: cluster-name.some-id.aws-region.redshift.amazonaws.com
        # - mrusso-cluster.chcgpkxl6sbm.us-east-1.redshift.amazonaws.com:5439/dev
        conn = redshift_connector.connect(
            # host=f"{cluster_name}.chcgpkxl6sbm.us-east-1.redshift.amazonaws.com",
            host=endpoint,
            database=input_kwargs['dbName'],
            user=input_kwargs['adminUsername'],
            password=input_kwargs['adminUserPassword'],
        )
        cursor = conn.cursor()

        # construct table name if none was provided
        if 'tableName' not in input_kwargs:
            # query for existing table names
            tablename_query = """SELECT DISTINCT tablename FROM PG_TABLE_DEF WHERE schemaname = 'public';"""
            cursor.execute(tablename_query)
            results = cursor.fetchall()

            # construct new table name
            tablenames = list(map(lambda res: res[0], results))
            table_idx = 0
            while f"table_copied_from_s3_{table_idx}" not in tablenames:
                table_idx += 1

            # set table name
            input_kwargs['tableName'] = f"table_copied_from_s3_{table_idx}"

        # query table's schema
        schema = pyarrow.parquet.read_schema(input_kwargs['S3Key'], memory_map=True)
        schema = {column: PANDAS_TYPE_TO_REDSHIFT_TYPE[str(pa_dtype)] for column, pa_dtype in zip(schema.names, schema.types)}

        # construct command to create table in Redshift
        col_str = ""
        for col, dtype in schema.items():
            col_str += f"{col} {dtype},"

        create_table_cmd = f"""CREATE TABLE {table_name} ({col_str[:-1]});"""

        # command to copy table from S3 to Redshift
        copy_table_cmd = f"""COPY {input_kwargs['tableName']} FROM '{input_kwargs['S3Key']}' IAM_ROLE '{AGENT_IAM_ROLE}' FORMAT AS parquet"""

        response = None
        try:
            cursor.execute(create_table_cmd)
            cursor.execute(copy_table_cmd)
            conn.commit()
            response = f"Successfully created table mini_table in {input_kwargs['ClusterIdentifier']}."
        except Exception as e:
            response = e

        return response


class LoadTableFromS3Serverless(AWSTool):
    """Load a table from a parquet file or prefix in S3 into Redshift Serverless."""

    name = "LoadTableFromS3Serverless"
    description = """This tool loads a database table from a (set of) parquet file(s) in S3 into a workgroup/database in Redshift Serverless.

    The input to this tool should be a JSON dictionary object with the following format:
    ```
    {
        "S3Key": "`s3_key_or_prefix`",
        "workgroupName": "`workgroup_name`",
        "adminUsername": "`username`",
        "adminUserPassword": "`password`",
        "dbName": "`db_name`"
        "tableName": "string"
    }
    ```
    The following dictionary keys are *REQUIRED*: `S3Key`, `workgroupName`, `adminUserPassword`, `adminUsername`, `dbName`

    All other dictionary keys are optional.

    *IMPORTANT*: If a user's request does not explicitly or implicitly instruct you how to set an optional key, then simply omit that key from the JSON you generate.

    JSON values inside of `` are meant to be filled by the agent.
    JSON values separated by | represent the unique set of values that may used.
    Otherwise, the data type of the value is shown.

    For example, if you wanted to load the data from `s3://somebucket/someprefix/file.pq` into a database table in the workgroup `SomeWorkgroup` using the adminUsername `admin`, adminUserPassword `Testing123`, and database `dev` you would generate the JSON:
    ```
    {
        "S3Key": "s3://somebucket/someprefix/file.pq",
        "workgroupName": "SomeWorkgroup",
        "adminUsername": "admin",
        "adminUserPassword": "Testing123",
        "dbName": "dev"
    }
    ```

    The tool outputs a message indicating the success or failure of the load table operation.
    """

    @property
    def short_description(self) -> str:
        return self.description.split('.')[0]

    def _run(
        self,
        input_json: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse JSON
        input_kwargs = None
        try:
            input_kwargs = json.loads(input_json.strip().strip('`'))
        except Exception as e:
            raise Exception("Failed to parse LLM input to LoadTableFromS3Serverless tool")

        # fill in kwargs
        if "dbName" not in input_kwargs:
            input_kwargs['dbName'] = DB_NAME

        if "adminUsername" not in input_kwargs:
            input_kwargs['adminUsername'] = ADMIN_USERNAME

        if "adminUserPassword" not in input_kwargs:
            input_kwargs['adminUserPassword'] = ADMIN_USER_PASSWORD

        # TODO: think through secure way to provide DB credentials
        # create database connection
        # - hostname format: workgroup-name.account-number.aws-region.redshift-serverless.amazonaws.com
        conn = redshift_connector.connect(
            host=f"{input_kwargs['workgroupName']}.276726865914.us-east-2.redshift-serverless.amazonaws.com",
            database=input_kwargs['dbName'],
            user=input_kwargs['adminUsername'],
            password=input_kwargs['adminUserPassword'],
        )
        cursor = conn.cursor()

        # construct table name if none was provided
        if 'tableName' not in input_kwargs:
            # query for existing table names
            tablename_query = """SELECT DISTINCT tablename FROM PG_TABLE_DEF WHERE schemaname = 'public';"""
            cursor.execute(tablename_query)
            results = cursor.fetchall()

            # construct new table name
            tablenames = list(map(lambda res: res[0], results))
            table_idx = 0
            while f"table_copied_from_s3_{table_idx}" not in tablenames:
                table_idx += 1

            # set table name
            input_kwargs['tableName'] = f"table_copied_from_s3_{table_idx}"

        # query table's schema
        schema = pyarrow.parquet.read_schema(input_kwargs['S3Key'], memory_map=True)
        schema = {column: PANDAS_TYPE_TO_REDSHIFT_TYPE[str(pa_dtype)] for column, pa_dtype in zip(schema.names, schema.types)}

        # construct command to create table in Redshift
        col_str = ""
        for col, dtype in schema.items():
            col_str += f"{col} {dtype},"

        create_table_cmd = f"""CREATE TABLE {table_name} ({col_str[:-1]});"""

        # command to copy table from S3 to Redshift
        copy_table_cmd = f"""COPY {input_kwargs['tableName']} FROM '{input_kwargs['S3Key']}' IAM_ROLE '{AGENT_IAM_ROLE}' FORMAT AS parquet"""

        response = None
        try:
            cursor.execute(create_table_cmd)
            cursor.execute(copy_table_cmd)
            conn.commit()
            response = f"Successfully created table {input_kwargs['tableName']} in {input_kwargs['workgroupName']}."
        except Exception as e:
            response = e

        return response


class SelectQueryDataFromTableServerless(AWSTool):
    """Perform a select query on a specified table in Redshift."""

    name = "SelectQueryDataFromTableServerless"
    description = """This tool runs a select query on a given table in Redshift Serverless.

    The input to this tool should be a JSON dictionary object with the following format:
    ```
    {
        "workgroupName": "`workgroup_name`",
        "tableName": "`table_name`",
        "adminUserPassword": "`password`",
        "adminUsername": "`username`",
        "dbName": "`db_name`"
        "columns": [
            "string"
        ]
    }
    ```
    The following dictionary keys are *REQUIRED*: `workgroupName`, `tableName`, `adminUserPassword`, `adminUsername`, `dbName`

    All other dictionary keys are optional.
    
    *IMPORTANT*: If a user's request does not explicitly or implicitly instruct you how to set an optional key, then simply omit that key from the JSON you generate.

    JSON values inside of `` are meant to be filled by the agent.
    JSON values separated by | represent the unique set of values that may used.
    Otherwise, the data type of the value is shown.

    For example, if you wanted to query the columns `ColumnA` and `ColumnB` from the table `SomeTable` in the workgroup `SomeWorkgroup` you would generate the JSON:
    ```
    {
        "workgroupName": "SomeWorkgroup",
        "tableName": "SomeTable",
        "adminUserPassword": "admin",
        "adminUsername": "Testing123",
        "dbName": "dev",
        "columns": ["ColumnA", "ColumnB"]
    }
    ```

    If you want to query all columns in the table, simply omit the "columns" key:
    ```
    {
        "workgroupName": "SomeWorkgroup",
        "tableName": "SomeTable",
        "adminUserPassword": "admin",
        "adminUsername": "Testing123",
        "dbName": "dev"
    }
    ```

    The tool outputs a message indicating the success or failure of the query operation.
    """

    @property
    def short_description(self) -> str:
        return self.description.split('.')[0]

    def _run(
        self,
        input_json: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse JSON
        input_kwargs = None
        try:
            input_kwargs = json.loads(input_json.strip().strip('`'))
        except Exception as e:
            raise Exception("Failed to parse LLM input to SelectQueryDataFromTableServerless tool")

        # create database connection
        # - hostname format: workgroup-name.account-number.aws-region.redshift-serverless.amazonaws.com
        conn = redshift_connector.connect(
            host=f"{workgroup_name}.276726865914.us-east-1.redshift-serverless.amazonaws.com",
            database=input_kwargs['dbName'],
            user=input_kwargs['adminUsername'],
            password=input_kwargs['adminUserPassword'],
        )
        cursor = conn.cursor()

        # try executing select query on table
        column_str = ",".join(input_kwargs['columns']) if "columns" in input_kwargs else "*"
        select_cmd = f"""SELECT {column_str} FROM {input_kwargs['tableName']};"""

        response = None
        try:
            cursor.execute(select_cmd)
            result = cursor.fetchall()
            result_df = pd.DataFrame(result, columns=columns)
            response = f"\n{result_df.head(MAX_RESULTS)}"
        except Exception as e:
            response = e

        return response
