from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Optional, Union

from fsspec import AbstractFileSystem

# Current valid cloud vendors
VALID_CLOUD_VENDORS = ["aws", "gcp", "azure"]


@dataclass
class CredInfo(ABC):
    pass


@dataclass
class GCPCredInfo(CredInfo):
    sa_email: Optional[str] = None
    audience: Optional[str] = None
    token_expiry: Optional[str] = None
    token: Optional[Union[str, dict]] = field(default=None, repr=False)
    project: Optional[str] = field(default=None, repr=False)
    refresh_mode: Optional[str] = None


@dataclass
class AWSCredInfo(CredInfo):
    id: Optional[str] = None
    secret: Optional[str] = field(default=None, repr=False)
    profile: Optional[str] = None


@dataclass
class AZCredInfo(CredInfo):
    account_name: Optional[str] = None
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = field(default=None, repr=False)
    credential: Optional[Any] = field(default=None, repr=False)


class CloudStorageFactory:
    @staticmethod
    def create(cloud_vendor: str, **kwargs) -> "CloudStorage":
        if cloud_vendor not in VALID_CLOUD_VENDORS:
            raise ValueError(f"Invalid cloud vendor: {cloud_vendor}!")
        return CloudStorage(cloud_vendor, **kwargs)


@dataclass
class CloudStorage:
    cloud_vendor: str
    fs_use_async: bool = False
    fs_anon: bool = False
    fs: Optional[AbstractFileSystem] = None
    fs_session: Optional[Any] = None
    cred_info: Optional[CredInfo] = None

    def get_fs(self) -> AbstractFileSystem:
        if not self.fs:
            self.set_fs()
        return self.fs

    def set_fs(self):
        fs_setter = getattr(self, f"_set_{self.cloud_vendor}_fs", None)
        if fs_setter:
            fs_setter()
        else:
            raise NotImplementedError(f"Unsupported cloud vendor: {self.cloud_vendor}")

    def _set_aws_fs(self):
        try:
            import s3fs

            params = {"asynchronous": self.fs_use_async, "anon": self.fs_anon}
            if isinstance(self.cred_info, AWSCredInfo):
                if self.cred_info.id and self.cred_info.secret:
                    params["key"] = self.cred_info.id
                    params["secret"] = self.cred_info.secret
                elif self.cred_info.profile:
                    params["profile"] = self.cred_info.profile
            self.fs = s3fs.S3FileSystem(**params)
        except ModuleNotFoundError:
            raise ModuleNotFoundError("Missing the s3fs package!")

    def _set_gcp_fs(self):
        try:
            import gcsfs

            params = {"asynchronous": self.fs_use_async}
            if isinstance(self.cred_info, GCPCredInfo):
                if self.cred_info.project:
                    params["project"] = self.cred_info.project
                if self.cred_info.token:
                    params["token"] = self.cred_info.token
            self.fs = gcsfs.GCSFileSystem(**params)
        except ModuleNotFoundError:
            raise ModuleNotFoundError("Missing the gcsfs package!")

    def _set_azure_fs(self):
        try:
            import adlfs

            params = {"asynchronous": self.fs_use_async, "anon": self.fs_anon}
            if isinstance(self.cred_info, AZCredInfo):
                if self.cred_info.account_name and self.cred_info.credential:
                    params["account_name"] = self.cred_info.account_name
                    params["credential"] = self.cred_info.credential
                if self.cred_info.tenant_id and self.cred_info.client_id and self.cred_info.client_secret:
                    params["tenant_id"] = self.cred_info.tenant_id
                    params["client_id"] = self.cred_info.client_id
                    params["client_secret"] = self.cred_info.client_secret
            self.fs = adlfs.AzureBlobFileSystem(**params)
        except ModuleNotFoundError:
            raise ModuleNotFoundError("Missing the adlfs package!")
