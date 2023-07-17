from redshift_tests.shell import run_sh

import pytest

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

CREATE_IAM_ROLE_INPUT_2 = "Please create an IAM role called mrusso-test-role1 with the description 'testing 123'"
CREATE_IAM_ROLE_EXPECTED_2 = "mrusso-test-role2", "testing 123"
