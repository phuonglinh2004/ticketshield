import time
from . import db

class Seat(db.Model):
    __tablename__ = "seats"

    id = db.Column(db.String(30), primary_key=True) # ví dụ: 'SEAT-A01'
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    ticket_type = db.Column(db.String(20), nullable=False)
    row_name = db.Column(db.String(10), nullable=False)
    seat_num = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="available") # 'available', 'held', 'booked'
    held_by = db.Column(db.String(80), nullable=True) # Lưu user/session đang giữ ghế
    held_until = db.Column(db.Float, default=0.0) # Timestamp hết hạn giữ ghế (Hold Lock 5 phút)

    def is_available(self):
        if self.status == "booked":
            return False
        if self.status == "held":
            # Nếu đã quá thời gian giữ ghế thì coi như nhả ghế
            return time.time() > (self.held_until or 0)
        return True

    def to_dict(self):
        # Trả về trạng thái thực tế sau khi tính toán thời hạn giữ ghế
        current_status = self.status
        if self.status == "held" and time.time() > (self.held_until or 0):
            current_status = "available"

        return {
            "id": self.id,
            "event_id": self.event_id,
            "ticket_type": self.ticket_type,
            "row_name": self.row_name,
            "seat_num": self.seat_num,
            "status": current_status
        }
