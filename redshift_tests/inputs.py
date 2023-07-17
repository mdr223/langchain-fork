from redshift_tests.shell import run_sh

import pytest

#######################################
###### Create S3 bucket input(s) ######
#######################################
@pytest.fixture
def create_bucket_input_1():
    return "Please create an S3 bucket called mrusso-test-bucket1"

@pytest.fixture
def create_bucket_expected_1():
    # default behavior is to create buckets in us-east-2
    # return {
    #     "Bucket": "mrusso-test-bucket1",
    #     "CreateBucketConfiguration": {
    #         "LocationConstraint": "us-east-2"
    #     }
    # }
    yield "mrusso-test-bucket1", "us-east-2"
    _ = run_sh("aws s3 delete-bucket --bucket mrusso-test-bucket1")


@pytest.fixture
def create_bucket_input_2():
    return "Please create an S3 bucket called mrusso-test-bucket2 in us-west-2"

@pytest.fixture
def create_bucket_expected_2():
    # return {
    #     "Bucket": "mrusso-test-bucket2",
    #     "CreateBucketConfiguration": {
    #         "LocationConstraint": "us-west-2"
    #     }
    # }
    yield "mrusso-test-bucket2", "us-west-2"
    _ = run_sh("aws s3 delete-bucket --bucket mrusso-test-bucket2")

@pytest.fixture
def create_bucket_input_3():
    return "Please create an S3 bucket called mrusso-test-bucket3 with the BucketOwnerEnforced"

@pytest.fixture
def create_bucket_expected_3():
    # return {
    #     "Bucket": "mrusso-test-bucket3",
    #     "CreateBucketConfiguration": {
    #         "LocationConstraint": "us-east-2"
    #     },
    #     "ObjectOwnership": "BucketOwnerEnforced"
    # }
    yield "mrusso-test-bucket3", "us-east-2"
    _ = run_sh("aws s3 delete-bucket --bucket mrusso-test-bucket3")

#######################################
###### Create IAM Role input(s) #######
#######################################
@pytest.fixture
def create_iam_role_input_1():
    return "Please create an IAM role called mrusso-test-role1"

@pytest.fixture
def create_iam_role_expected_1():
    yield "mrusso-test-role1", None
    _ = run_sh("aws iam delete-role --role-name mrusso-test-role1")

@pytest.fixture
def create_iam_role_input_2():
    return "Please create an IAM role called mrusso-test-role1 with the description 'testing 123'"

@pytest.fixture
def create_iam_role_expected_2():
    yield "mrusso-test-role2", "testing 123"
    _ = run_sh("aws iam delete-role --role-name mrusso-test-role2")

