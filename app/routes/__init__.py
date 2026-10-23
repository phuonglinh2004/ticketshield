from .auth import auth_bp
from .main import main_bp
from .booking import booking_bp
from .ticket import ticket_bp
from .admin import admin_bp

__all__ = [
    "auth_bp",
    "main_bp",
    "booking_bp",
    "ticket_bp",
    "admin_bp"
]
