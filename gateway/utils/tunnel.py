from config.gateway_settings import settings
from config.log import logger


# You can use any library you wish for the tunneling, but in this case we will use pyngrok.
def start_ngrok():
    if settings.START_NGROK:
        try:
            from pyngrok import ngrok

            public_url = ngrok.connect(settings.NGROK_PORT).public_url
            # Setup a ngrok tunnel to the dev server.
            logger.info(f"YOUR PUBLIC IP IS: {public_url}")
        except ImportError:
            logger.error("PYNGROK NOT INSTALLED!")
        except:
            logger.error(f"NGROK CONNECTION ERROR!")
