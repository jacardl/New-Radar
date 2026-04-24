# MindSpider stub - MediaCrawler submodule not initialized
# This stub allows the Flask app to start for development purposes
from loguru import logger


class MindSpider:
    """Stub MindSpider class for development."""

    def __init__(self):
        pass

    def initialize_database(self):
        """Initialize the MindSpider database."""
        logger.warning("MindSpider database initialization called (stub)")
        return True
