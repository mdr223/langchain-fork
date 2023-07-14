import pytest

# Create S3 bucket input(s)
@pytest.fixture
def create_bucket_input_1():
    return "Please create an S3 bucket called mrusso-test-bucket"

@pytest.fixture
def create_bucket_expected_1():
    return {"Bucket": "mrusso-test-bucket"}

@pytest.fixture
def create_bucket_input_2():
    return "Please create an S3 bucket called mrusso-test-bucket in us-east-2"

@pytest.fixture
def create_bucket_expected_2():
    return {
        "Bucket": "mrusso-test-bucket",
        "CreateBucketConfiguration": {
            "LocationConstraint": "us-east-2"
        }
    }
