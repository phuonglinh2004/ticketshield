from . import db

class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(200), nullable=False)
    artist = db.Column(db.String(100), nullable=False)
    venue = db.Column(db.String(200), nullable=False)
    date_str = db.Column(db.String(100), nullable=False)
    banner_url = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="selling", nullable=False)

    ticket_types = db.relationship("TicketType", backref="event", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "venue": self.venue,
            "date_str": self.date_str,
            "banner_url": self.banner_url,
            "description": self.description,
            "status": self.status
        }

class TicketType(db.Model):
    __tablename__ = "ticket_types"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    total_stock = db.Column(db.Integer, nullable=False)
    remaining_stock = db.Column(db.Integer, nullable=False)
    color = db.Column(db.String(20), default="#2dc275")

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "code": self.code,
            "name": self.name,
            "price": self.price,
            "total_stock": self.total_stock,
            "remaining_stock": self.remaining_stock,
            "color": self.color
        }
