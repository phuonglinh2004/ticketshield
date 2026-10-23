from datetime import datetime
from . import db

class Order(db.Model):
    __tablename__ = "orders"

    order_id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    ticket_type = db.Column(db.String(20), nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    method = db.Column(db.String(50), nullable=False)
    buyer_name = db.Column(db.String(120), nullable=False)
    buyer_phone = db.Column(db.String(20), nullable=False)
    buyer_email = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self):
        return {
            "order_id": self.order_id,
            "user_id": self.user_id,
            "event_id": self.event_id,
            "ticket_type": self.ticket_type,
            "qty": self.qty,
            "total": self.total,
            "method": self.method,
            "buyer_name": self.buyer_name,
            "buyer_phone": self.buyer_phone,
            "buyer_email": self.buyer_email,
            "created_at": self.created_at
        }

class ResellListing(db.Model):
    __tablename__ = "resell_listings"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticket_id = db.Column(db.String(50), db.ForeignKey("tickets.id"), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    original_price = db.Column(db.Integer, nullable=False)
    resell_price = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="active", nullable=False) # 'active', 'sold', 'cancelled'
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    ticket = db.relationship("Ticket", backref="resell_listing", uselist=False)
    seller = db.relationship("User", backref="resell_listings", foreign_keys=[seller_id])

    def to_dict(self):
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "seller_id": self.seller_id,
            "seller_name": self.seller.full_name if self.seller else "Thành viên",
            "original_price": self.original_price,
            "resell_price": self.resell_price,
            "status": self.status,
            "created_at": self.created_at
        }
