# fsspec

## What is fsspec ##

Filesystem Spec (fsspec) is a project to provide a unified pythonic interface to local, remote and embedded file systems and bytes storage.

[Official Documentation link](<https://filesystem-spec.readthedocs.io/en/latest/>)

Instead of using boto3 libraries to access s3 you will use the cloud agnostic library that is based on fsspec.

| Cloud provider| fsspec compatible library name | documentation link  | Path URL format |
|:-------------:|:------------------------------:|:-------------------:|:------------------------------:|
| GCP           | gcsfs                          | <https://gcsfs.readthedocs.io/en/latest/>  |gs://|
| AWS           | s3fs                           | <https://s3fs.readthedocs.io/en/latest/>   |s3://|
| Azure         | adlfs                          | <https://github.com/fsspec/adlfs>          ||
