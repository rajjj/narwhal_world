import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):

    load_dotenv()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    START_NGROK: bool = os.getenv("USE_NGROK", False)
    NGROK_PORT: int = os.getenv("NGROK_PORT", 8000)

    # default sleep time
    SLEEP_TIME: int = os.getenv("SLEEP_TIME", 60)

    NAR_USERNAME: str = os.getenv("DEF_USERNAME").encode("UTF-8")
    NAR_PASSWORD: str = os.getenv("DEF_PASSWORD").encode("UTF-8")

    # jwt data
    ALGORITHM: str = "HS256"
    BEARER_ALT_KEY: str = os.getenv("BEARER_ALT_KEY")

    # prefect default values
    DEPLOYMENT_KEYWORD: str = os.getenv("DEPLOY_KEYWORD", "deploy")

    # default cloud vendor
    VENDOR: str = os.getenv("VENDOR", "aws")

    # flow cloud storage path
    FLOW_PATH: str = os.getenv("FLOW_PATH")

    # codefresh token
    CF_TOKEN: str = os.getenv("CF_TOKEN")
    # Pipeline id
    CF_FLOW_ID: str = os.getenv("CF_FLOW_ID")
    CF_CI_ID: str = os.getenv("CF_CI_ID")

    # TODO uncomment only if you have a second test workspace
    # Prefect test url/key
    # PREFECT_TEST_URL: str = os.getenv("PREFECT_TEST_URL", "")
    # PREFECT_TEST_KEY: str = os.getenv("PREFECT_TEST_KEY", "")
    # USE_TEST_WORKSPACE: bool = False

    # Prefect prod url/key
    PREFECT_API_URL: str = os.getenv("PREFECT_API_URL")
    PREFECT_API_KEY: str = os.getenv("PREFECT_API_KEY")

    # Data path variables
    DATA_STORE: str = os.getenv("DATA_STORE", "sama-narwhal-data-store")
    DELMITER: str = os.getenv("DELMITER", "--")

    # Hub specific variables
    DPP_KEY: str = os.getenv("DPP_KEY")
    KIKI_BASE_URL: str = os.getenv("KIKI_BASE_URL_PROD")


settings = GatewaySettings()
