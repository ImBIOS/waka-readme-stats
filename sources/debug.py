"""
Debug utilities for better error handling and logging in waka-readme-stats.
"""


class DebugManager:
    """
    Static class for managing debug output.
    Provides utilities for info, warning, error, and success logging.
    """

    @staticmethod
    def i(message: str):
        """Log an information message."""
        print(f"INFO: {message}")

    @staticmethod
    def w(message: str):
        """Log a warning message."""
        print(f"WARNING: {message}")

    @staticmethod
    def g(message: str):
        """Log a success (good) message."""
        print(f"SUCCESS: {message}")

    @staticmethod
    def p(message: str):
        """Log a problem message."""
        print(f"PROBLEM: {message}")

    @staticmethod
    def e(message: str):
        """Log an error message."""
        print(f"ERROR: {message}")


# Add this to be imported in other modules
DBM = DebugManager
