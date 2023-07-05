import pytest

# Create S3 bucket input(s)
@pytest.fixture
def create_bucket_input_1():
    return "Please create an S3 bucket called mrusso-test-bucket"

@pytest.fixture
def create_bucket_input_2():
    return "Please create an S3 bucket called mrusso-test-bucket in us-west-2"
