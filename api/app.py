from flask import Flask, jsonify
from flask_cors import CORS
import config
import os

from utils.logger import setup_logging, get_logger

setup_logging()
log = get_logger("api.app")

app = Flask(__name__)
CORS(app)

app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH
app.config["UPLOAD_FOLDER"] = str(config.UPLOAD_FOLDER)
app.config["SECRET_KEY"] = config.SECRET_KEY

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)

from api.routes.scanner_routes import scanner_bp
from api.routes.secretary_routes import secretary_bp
from api.routes.management_routes import mgmt_bp
from api.routes.dean_routes import dean_bp
from api.routes.settings_routes import settings_bp, restore_sim_time_from_db
from api.routes.auth_routes import auth_bp
from api.routes.doctor_portal_routes import doctor_bp
from api.routes.audit_routes import audit_bp
from api.routes.role_label_routes import role_labels_bp
from api.routes.qr_attendance_routes import qr_bp
from api.routes.student_profile_routes import profile_bp
from api.audit import log_action

app.register_blueprint(scanner_bp)
app.register_blueprint(secretary_bp)
app.register_blueprint(mgmt_bp)
app.register_blueprint(dean_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(doctor_bp)
app.register_blueprint(audit_bp)
app.register_blueprint(role_labels_bp)
app.register_blueprint(qr_bp)
app.register_blueprint(profile_bp)

restore_sim_time_from_db()


def _auto_close_loop():
    import time
    from api.controllers.attendance_controller import auto_close_sessions
    while True:
        try:
            time.sleep(30)
            closed, msg = auto_close_sessions()
            if closed > 0:
                log.info("[AUTO-CLOSE] %s", msg)
        except Exception as e:
            log.exception("[AUTO-CLOSE] Error")


import threading
_auto_close_thread = threading.Thread(target=_auto_close_loop, daemon=True)
_auto_close_thread.start()


@app.route("/")
def index():
    return jsonify({
        "status": "running",
        "message": "University Attendance System API",
        "version": "1.0.0",
    })


@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "Endpoint not found"}), 404


@app.errorhandler(500)
def server_error(e):
    log.exception("500 Internal Server Error")
    return jsonify({"success": False, "error": "Internal server error"}), 500


@app.errorhandler(Exception)
def unhandled_exception(e):
    log.exception("Unhandled exception: %s", e)
    return jsonify({"success": False, "error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(host=config.SERVER_HOST, port=config.SERVER_PORT, debug=True)
