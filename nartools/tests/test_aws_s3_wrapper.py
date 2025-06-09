from libnar import libnar
from nartools.wrappers.aws_s3 import S3Wrapper

# TODO:
# Look into mocking boto3/s3fs.
# Currently these tests use actual S3 and rely on the test location
# (s3://sama-client-assets/361/testing/Samples/) having a specific
# set of files and subdirectories. This is not ideal.

# Officially, only directory paths starting with the bucket name
# and presented as str or Path objects are supported. However,
# to some extent the code is also able to work with S3 URIs.
TEST_DIR_S3_PATH = "sama-client-assets/361/testing/Samples"
TEST_DIR_S3_PATH_WITH_TRAILING_SLASH = "sama-client-assets/361/testing/Samples/"
TEST_DIR_S3_URI = f"s3://{TEST_DIR_S3_PATH}"
TEST_DIR_S3_URI_WITH_TRAILING_SLASH = f"s3://{TEST_DIR_S3_PATH}/"
TEST_PATHS = [
    TEST_DIR_S3_PATH,
    TEST_DIR_S3_PATH_WITH_TRAILING_SLASH,
    TEST_DIR_S3_URI,
    TEST_DIR_S3_URI_WITH_TRAILING_SLASH,
]

EXPECTED_OUTPUT_BOTO3 = [
    "scene0/",
    "scene1/",
    "scene2/",
    "scene3/",
    "scene4/",
    "scene5/",
    "scene6/",
    "scene7/",
    "scene8/",
    "scene9/",
    "calibrations.json",
]
EXPECTED_OUTPUT_S3FS = [
    "calibrations.json",
    "scene0",
    "scene1",
    "scene2",
    "scene3",
    "scene4",
    "scene5",
    "scene6",
    "scene7",
    "scene8",
    "scene9",
]
# Note that the order of the output is not required to match the expectations,
# so we use set comparison.


def test_s3_listing_via_boto3():
    # Here we try to list the target S3 dir using the method that
    # wraps around boto3.

    s3w = S3Wrapper()

    for path in TEST_PATHS:
        dir_contents = s3w.boto3_list_dir(path)
        assert set(dir_contents) == set(EXPECTED_OUTPUT_BOTO3)


def test_s3_listing_via_s3fs():
    # Here we try to list the target S3 dir using the method that
    # wraps around s3fs.

    narcon = libnar.Narcon()
    narcon.set_aws_cred()
    s3w = S3Wrapper(fs=narcon.fs)

    for path in TEST_PATHS:
        dir_contents = s3w.s3fs_list_dir(path)
        assert set(dir_contents) == set(EXPECTED_OUTPUT_S3FS)
