#Madison Boyd
#CSC 405
#Iteration 3

# controllers/usersettings.py
from backend.services.usersettings import get_settings, update_wishlist
import logging  # added - ava
logger = logging.getLogger(__name__)  # added - ava
def show_settings_view():
    data = get_settings()
    logger.debug(f"Wishlist: {data.wishlist}")

def add_item_to_wishlist(item_name: str):
    success = update_wishlist(item_name)
    if success:
        logger.debug(f"Added '{item_name}' to wishlist.")
    else:
        logger.debug(f"'{item_name}' already exists.")