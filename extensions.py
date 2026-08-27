"""
===========================================================
QRESERVE
Flask Extensions
===========================================================
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


# -------------------------------------------------------
# Rate Limiter
#
# Uses the client IP address as the key.
# Default limit applies to every route unless overridden.
# -------------------------------------------------------

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "60 per hour"],
    storage_uri="memory://"
)
