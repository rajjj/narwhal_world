"""
This module supplies wrappers for boto3/s3fs to make working with AWS S3 easier

Usage exmples:
    - library/nartools/tests/test_aws_s3_wrapper.py
"""

from pathlib import Path
from typing import List, Tuple, Union

import boto3
from s3fs import S3FileSystem  # for typing


class S3Wrapper:
    """
    Defines methods which wrap around boto3 and s3fs utilities

    In this version, only directory listing is implemented
    """

    def __init__(
        self,
        fs: Union[S3FileSystem, None] = None,
        aws_access_key_id: Union[str, None] = None,
        aws_secret_access_key: Union[str, None] = None,
    ) -> None:
        """
        Constructor to initialise object based on dev preferences

        Args:
            fs (Union[S3FileSystem, None]): An S3FileSystem object (e.g. narcon.fs)
                to use for S3 operations. If None, s3fs-related methods will be
                disabled.
            aws_access_key_id (Union[str, None]): The AWS access key ID to use for
                the internal boto3 client. If None, the default credentials active
                in the system environment will be used.
            aws_secret_access_key (Union[str, None]): The AWS secret access key to
                use for the internal boto3 client. If None, the default credentials
                active in the system environment will be used. Must be provided
                if and only if aws_access_key_id is provided.
        """

        assert (aws_access_key_id is None and aws_secret_access_key is None) or (
            aws_access_key_id is not None and aws_secret_access_key is not None
        ), "Either both or neither of aws_access_key_id and aws_secret_access_key must be provided"

        self.fs = fs

        if aws_access_key_id is None:
            self.s3_client = boto3.client("s3")
        else:
            self.s3_client = boto3.client(
                "s3", aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key
            )

    def get_bucket_and_key_from_path(path: Union[Path, str]) -> Tuple[str, str]:
        """
        Splits an S3 path into a bucket and a key within the bucket

        Args:
            path (Path): The path in S3 to split
        """

        # Input sanitisation
        path = str(path)
        path = path.replace("s3://", "")

        components = path.split("/", 1)
        bucket = components[0]
        key = components[1] if len(components) > 1 else ""

        return bucket, key

    def s3fs_list_dir(self, dirpath: Union[Path, str]) -> List[str]:
        """
        Given a path to a 'directory' in S3, lists the
        contents of the directory. Files and folders are listed
        using their names only, not their full paths, as is
        standard for the *nix `ls` command.
        This method uses s3fs.

        Args:
            dirpath (Path): The path to the directory to list, starting with the bucket name

        Notes:
            - This function is not recursive, and will only list the
            immediate contents of the directory pointed to.
            - This function takes care of any possible self-listing
            of the given folder, which is possible when the S3 folder
            was created as an empty folder first and then had files/
            folders placed in it. In this sense, this function
            provides a 'true' directory listing.
            - This function does not explicitly handle pagination, and instead
            assumes that s3fs is doing so by default.
        """

        assert self.fs is not None, "S3FileSystem object not provided; s3fs listing method cannot be used"

        # Input sanitisation
        dirpath = str(dirpath)
        dirpath = dirpath.replace("s3://", "")  # Just in case an S3 URI is provided in place of a path
        if not dirpath.endswith("/"):
            dirpath += "/"

        return [
            Path(item).name
            for item in self.fs.ls(dirpath)
            if item != dirpath  # i.e., ignore the self-listing of the dir that s3fs does
        ]

    def __boto3_list_dir_files(self, bucket_name: str, dirpath: str) -> List[str]:
        """
        Lists out all files (leaf nodes) in a given S3 dir

        Args:
            bucket_name (str): The name of the S3 bucket of interest
            dirpath (str): The key or path to the directory within the bucket
        """

        if not dirpath.endswith("/"):
            dirpath += "/"
        skip_len = len(dirpath)

        dir_list = []

        # Boto3 paginates the listing for directories with many contents, so we
        # must in general loop through the pages to get all the contents
        cont_token = None
        output_truncated = True

        while output_truncated:
            if cont_token == None:
                output = self.s3_client.list_objects_v2(Bucket=bucket_name, Prefix=dirpath, Delimiter="/")
            else:
                output = self.s3_client.list_objects_v2(
                    Bucket=bucket_name, Prefix=dirpath, Delimiter="/", ContinuationToken=cont_token
                )
            if "Contents" in output.keys():
                dir_list += [item["Key"][skip_len:] for item in output["Contents"]]

            output_truncated = output["IsTruncated"]
            if output_truncated:
                cont_token = output["NextContinuationToken"]
            else:
                cont_token = None

        if "" in dir_list:
            # Related to the 'self-listing' issue
            dir_list.remove("")

        return dir_list

    def __boto3_list_dir_subdirs(self, bucket_name: str, dirpath: str) -> List[str]:
        """
        Lists out all (immediate) subdirectories in a given dir

        Args:
            bucket_name (str): The name of the S3 bucket of interest
            dirpath (str): The key or path to the directory within the bucket
        """

        if not dirpath.endswith("/"):
            dirpath += "/"
        skip_len = len(dirpath)

        dir_list = []

        # Taking care of pagination as before
        cont_token = None
        output_truncated = True

        while output_truncated:
            if cont_token == None:
                output = self.s3_client.list_objects_v2(Bucket=bucket_name, Prefix=dirpath, Delimiter="/")
            else:
                output = self.s3_client.list_objects_v2(
                    Bucket=bucket_name, Prefix=dirpath, Delimiter="/", ContinuationToken=cont_token
                )
            if "CommonPrefixes" in output.keys():
                dir_list += [item["Prefix"][skip_len:] for item in output["CommonPrefixes"]]

            output_truncated = output["IsTruncated"]
            if output_truncated:
                cont_token = output["NextContinuationToken"]
            else:
                cont_token = None

        if "" in dir_list:
            # Related to the 'self-listing' issue
            dir_list.remove("")

        return dir_list

    def boto3_list_dir(self, dirpath: Union[Path, str]) -> List[str]:
        """
        Given a path to a 'directory' in S3, lists the
        contents of the directory. Files and folders are listed
        using their names only, not their full paths, as is
        standard for the *nix `ls` command.
        This method uses boto3.

        Args:
            dirpath (Path): The path to the directory to list, starting with the bucket name

        Notes:
            - This function is not recursive, and will only list the
            immediate contents of the directory pointed to.
            - The S3 self-listing problem is handled in the callee methods that
            use boto3 directly.
            - The advantage of this method over the s3fs method is that in its
            output, subdirs appear with a trailing '/' for easy identification.
        """

        bucket, key = S3Wrapper.get_bucket_and_key_from_path(dirpath)

        dir_list = self.__boto3_list_dir_subdirs(bucket, key) + self.__boto3_list_dir_files(bucket, key)

        return dir_list
