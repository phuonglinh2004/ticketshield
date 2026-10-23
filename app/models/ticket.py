from datetime import datetime
from . import db

class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.String(50), primary_key=True)
    order_id = db.Column(db.String(50), db.ForeignKey("orders.order_id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    ticket_type = db.Column(db.String(20), nullable=False)
    seat_id = db.Column(db.String(30), nullable=True)
    price = db.Column(db.Integer, nullable=False)
    ticket_secret = db.Column(db.String(64), nullable=False) # Khóa bí mật sinh TOTP QR riêng cho từng vé
    used = db.Column(db.Integer, default=0, nullable=False) # 0: chưa dùng, 1: đã vào cổng
    used_at = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), default="valid", nullable=False) # 'valid', 'resold', 'gifted', 'revoked'
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    owner = db.relationship("User", backref="tickets", foreign_keys=[user_id])
    event = db.relationship("Event", backref="tickets")

    def to_dict(self):
        return {
            "ticket_id": self.id,
            "order_id": self.order_id,
            "user_id": self.user_id,
            "event_id": self.event_id,
            "event_title": self.event.title if self.event else "Concert Ticketbox",
            "event_date": self.event.date_str if self.event else "",
            "venue": self.event.venue if self.event else "",
            "ticket_type": self.ticket_type,
            "seat_id": self.seat_id,
            "price": self.price,
            "used": self.used,
            "used_at": self.used_at,
            "status": self.status,
            "created_at": self.created_at
        }
