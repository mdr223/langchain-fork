"""Tools for calling various AWS CLI commands."""
from pydantic.fields import Field
from typing import Optional

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain.tools.base import BaseTool

import boto3

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


class AWSTool(BaseTool):
    """Tool that has capability to query the Serper.dev Google Search API
    and get back json."""

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


class CreateRedshiftServerlessNamespace(AWSTool):
    """Create a namespace for Redshift Serverless in the user's AWS account."""

    name = "Create a namespace for Redshift Serverless"
    description = (
        "This tool creates a Redshift Serverless namespace using the given `namespace_name` in the user's AWS account."
        "The input to this tool should be the name of the namespace the user wishes to create."
        "For example, `SomeNamespace` would be the input if you wanted to create the namespace `SomeNamespace`."
        "The tool outputs a message indicating the success or failure of the create namespace operation."
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
            _ = rs_client.create_namespace(namespaceName=namespace_name)
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
            raise Exception("Failed to parse LLM input to AttachIAMPolicy tool")

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
