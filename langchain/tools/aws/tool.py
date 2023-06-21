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

import pandas as pd

# DEFINITION
# TODO: have AWS account ID read from env. variable
# TODO: use utility to perform environment + setup check(s)
# TODO: break into sub folders for subcommands (e.g. "iam/", "redshift/", "redshift-serverless/", etc.)
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
    'Version': '2012-10-17',
    'Statement': [{
        'Sid': 'DefaultBucketPerm',
        'Effect': 'Allow',
        'Principal': 'arn:aws:iam::518251513740:*',
        'Action': [
            's3:ListBucket',
            's3:GetObject',
            's3:PutObject',
            's3:DeleteObject'
        ],
        'Resource': f'arn:aws:s3:::REPLACE/*'
    }]
}
ADMIN_USER_PASSWORD = "testing123"
ADMIN_USERNAME = "agentadmin"
DB_NAME = "dev"


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
            bucket_policy = json.dumps(bucket_policy).replace("REPLACE", bucket_name)

            # Set the new policy
            s3_client.put_bucket_policy(Bucket=bucket_name, Policy=bucket_policy)

            response = f"Successfully created S3 Bucket with name {bucket_name}."
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
            if kms_key_id is None or kms_key_id == "":
                _ = rs_client.create_namespace(
                    namespaceName=namespace_name,
                    adminUserPassword=ADMIN_USER_PASSWORD,
                    adminUsername=ADMIN_USERNAME,
                    dbName=DB_NAME,
                )
            else:
                _ = rs_client.create_namespace(
                    namespaceName=namespace_name,
                    kmsKeyId=kms_key_id,
                    adminUserPassword=ADMIN_USER_PASSWORD,
                    adminUsername=ADMIN_USERNAME,
                    dbName=DB_NAME,
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
        "The input to this tool should be a comma separated list of strings of length two, representing the name of the workgroup you wish to create (i.e. `workgroup_name`) and the namespace it should be created in (i.e. `namespace_name`)."
        "For example, `SomeWorkgroup,SomeNamespace` would be the input if you wanted to create the workgroup `SomeWorkgroup` in the namespace `SomeNamespace`."
        "The tool outputs a message indicating the success or failure of the create workgroup operation."
    )

    def _run(
        self,
        workgroup_and_namespace_names: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        # parse policy_name and role_name
        try:
            workgroup_name = workgroup_and_namespace_names.split(',')[0]
            namespace_name = workgroup_and_namespace_names.split(',')[1]
        except Exception as e:
            raise Exception("Failed to parse LLM input to CreateRedshiftServerlessWorkgroup tool")

        rs_client = boto3.client('redshift-serverless')

        response = None
        try:
            _ = rs_client.create_workgroup(
                workgroupName=workgroup_name,
                namespaceName=namespace_name,
            )
            response = f"Successfully created Redshift Serverless workgroup {workgroup_name} in namespace {namespace_name}."
        except Exception as e:
            response = e

        return response


class LoadTableFromS3(AWSTool):
    """Load a table from a parquet file or prefix in S3 into Redshift."""

    name = "Load a table from S3 into Redshift."
    description = (
        "This tool loads a database table from a (set of) parquet file(s) in S3 into Redshift."
        "The input to this tool should be a comma separated list of strings of length two, representing the s3 key or prefix of the dataset you wish to load into redshift and the name of the Redshift Serverless workgroup you with to load the data into."
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
            raise Exception("Failed to parse LLM input to LoadTableFromS3 tool")

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
        create_table_cmd = """CREATE TABLE mini_table
        (
            order_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            amount INTEGER NOT NULL
        );
        """
        copy_table_cmd = f"""COPY mini_table FROM '{s3_key_or_prefix}' IAM_ROLE 'arn:aws:iam::518251513740:instance-profile/test-rollm-agent-role' FORMAT AS parquet"""

        response = None
        try:
            cursor.execute(create_table_cmd)
            cursor.execute(copy_table_cmd)
            conn.commit()
            response = f"Successfully created table mini_table in {workgroup_name}."
        except Exception as e:
            response = e

        return response
        