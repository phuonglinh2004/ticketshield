from flask import Blueprint, render_template, jsonify
from app.models import Event, TicketType, Seat

main_bp = Blueprint("main", __name__)

@main_bp.get("/")
def home():
    return render_template("index.html")

@main_bp.get("/gate")
def gate():
    return render_template("gate.html")

@main_bp.get("/api/events")
def api_events():
    """Lấy thông tin sự kiện chính và danh sách hạng vé"""
    ev = Event.query.first()
    if not ev:
        return jsonify(ok=False, msg="Chưa có sự kiện nào trong hệ thống"), 404

    ticket_types = [tt.to_dict() for tt in ev.ticket_types]
    return jsonify(
        ok=True,
        event=ev.to_dict(),
        ticket_types=ticket_types
    )

@main_bp.get("/api/seats")
def api_seats():
    """Lấy danh sách ghế ngồi theo sơ đồ sân vận động / khán đài"""
    seats = Seat.query.all()
    return jsonify(
        ok=True,
        seats=[s.to_dict() for s in seats]
    )
