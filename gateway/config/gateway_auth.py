import secrets
from base64 import b64decode

import jwt
from config.gateway_settings import settings
from litestar import Request
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.handlers.base import BaseRouteHandler


def basic_auth(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """
    Validates HTTP basic credentials by comparing them to a predefined username and password.
    """
    # encode the credentials to compare
    try:
        usr_name, password = (
            b64decode(connection.headers.get("Authorization").split("Basic ")[1]).decode("utf-8").split(":")
        )

        is_username = secrets.compare_digest(usr_name, settings.NAR_USERNAME)
        is_password = secrets.compare_digest(password, settings.NAR_PASSWORD)

        if not is_username or not is_password:
            raise NotAuthorizedException(headers={"WWW-Authenticate": "Basic"})
    except Exception as _:
        raise NotAuthorizedException(headers={"WWW-Authenticate": "Basic"})


def check_bearer_token(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """
    Validate if the header contains the corrrect bearer token.
    """
    token_type = connection.headers.get("nart")
    bearer_token = f"Bearer {settings.BEARER_ALT_KEY}" if token_type == "alt" else f"Bearer {settings.DPP_KEY}"
    if _ := connection.headers.get("Authorization") != bearer_token:
        connection.logger.error("Bearer token authorization failure!")
        raise NotAuthorizedException()


def check_webhook_token(request: Request) -> dict:
    if not (token := request.headers.get("x-auth-token")):
        request.logger.error("Webhook authorization failure!")
        raise NotAuthorizedException()
    try:
        return jwt.decode(token, settings.DPP_KEY, algorithms=[settings.ALGORITHM])
    except jwt.exceptions.PyJWTError:
        request.logger.error("Webhook authorization failure! JWTError")
        raise NotAuthorizedException()
    except Exception as e:
        request.logger.error(f"Webhook authorization failure! {e}")
        raise NotAuthorizedException()
