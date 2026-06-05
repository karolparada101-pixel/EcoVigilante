# @ Con fines académicos
# por KarolyMaira

import hashlib
import base64
import json
import os
import re
import secrets
import smtplib
import subprocess
import threading
import time
import unicodedata
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle, Paragraph

from flask import Flask, Response, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

try:
    import mysql.connector
    from mysql.connector import Error
    from mysql.connector import errorcode
except ImportError:  # pragma: no cover
    mysql = None
    Error = Exception
    errorcode = None


app = Flask(__name__)
app.secret_key = "ecovigilante-homepage"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
BASE_DIR = Path(__file__).resolve().parent
IA_PYTHON = Path(r"D:\IA\venv\Scripts\python.exe")
IA_SERVER = BASE_DIR / "ia_server.py"
PROFILE_UPLOAD_DIR = BASE_DIR / "static" / "profile_photos"
FACE_DATASET_DIR = BASE_DIR / "static" / "face_dataset"
ALLOWED_PROFILE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_FACE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

RECOVERY_FILE_PREFIX = "ECOVIGILANTE-RECOVERY"
USER_SAFE_ERROR = "No pudimos completar la accion. Revisa los datos ingresados e intenta nuevamente."

COLOR_PALETTE = [
    {"name": "Verde Base", "hex": "#2F7D4B"},
    {"name": "Verde Profundo", "hex": "#1D5A35"},
    {"name": "Fondo Natural", "hex": "#EEF6EA"},
    {"name": "Texto Principal", "hex": "#163126"},
    {"name": "Texto Secundario", "hex": "#4B6B5A"},
    {"name": "Lima Suave", "hex": "#6AB36D"},
]

FONT_SHOWCASE = [
    {
        "label": "Titulares",
        "name": "Sora",
        "sample": "Ecovigilante impulsa una cultura ambiental inteligente.",
        "usage": "Titulos, metricas destacadas y llamadas a la accion.",
        "class_name": "font-sora",
    },
    {
        "label": "Texto base",
        "name": "Outfit",
        "sample": "Lectura clara, moderna y organizada para toda la experiencia visual.",
        "usage": "Parrafos, tarjetas, navegacion y listados del sistema.",
        "class_name": "font-outfit",
    },
]

CAMERA_MODEL_PATH = BASE_DIR / "yolov8m.pt"
CAMERA_CONFIG_DIR = BASE_DIR / ".ultralytics"
CAMERA_MPL_DIR = BASE_DIR / ".matplotlib"
CAMERA_MAX_CONTENT_LENGTH = 16 * 1024 * 1024
CAMERA_CATEGORY_FALLBACK = {
    "aprovechable": {"label": "Aprovechable", "desc": "Papel, plastico, vidrio, metal"},
    "no_aprovechable": {"label": "No aprovechable", "desc": "Residuos contaminados o no reciclables"},
    "organico": {"label": "Organico", "desc": "Residuos de comida y vegetales"},
}

_ai_process = None
_ai_lock = threading.Lock()
_camera_classifier = None
_camera_classifier_error = None
_camera_lock = threading.Lock()


def get_camera_category_info():
    try:
        from model.waste_classifier import CATEGORY_INFO

        return CATEGORY_INFO
    except Exception:
        return CAMERA_CATEGORY_FALLBACK


def get_camera_classifier():
    global _camera_classifier, _camera_classifier_error

    if _camera_classifier is not None:
        return _camera_classifier, None
    if _camera_classifier_error is not None:
        return None, _camera_classifier_error

    with _camera_lock:
        if _camera_classifier is not None:
            return _camera_classifier, None
        try:
            CAMERA_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CAMERA_MPL_DIR.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("YOLO_CONFIG_DIR", str(CAMERA_CONFIG_DIR))
            os.environ.setdefault("MPLCONFIGDIR", str(CAMERA_MPL_DIR))
            from model.waste_classifier import WasteClassifier

            _camera_classifier = WasteClassifier(str(CAMERA_MODEL_PATH))
            return _camera_classifier, None
        except Exception as exc:
            _camera_classifier_error = (
                "No fue posible cargar el clasificador de camara. "
                "Revisa que las dependencias de IA esten instaladas."
            )
            print(f"[Ecovigilante] Error cargando clasificador de camara: {exc}")
            return None, _camera_classifier_error


def decode_camera_image_payload(payload):
    if not payload or "image" not in payload:
        return None, "No se encontro la imagen"

    raw_image = payload["image"]
    try:
        encoded = raw_image.split(",", 1)[1] if "," in raw_image else raw_image
        return base64.b64decode(encoded), None
    except Exception:
        return None, "La imagen recibida no es valida"


def load_dotenv_file(path):
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_dotenv_file(BASE_DIR / ".env")


def get_env_value(*names, default=""):
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    return default


def get_env_int(*names, default=0):
    raw_value = get_env_value(*names, default=str(default))
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default


def get_env_bool(*names, default=True):
    raw_value = str(get_env_value(*names, default="1" if default else "0")).strip().lower()
    return raw_value in {"1", "true", "yes", "on"}


DB_CONFIG = {
    "host": get_env_value("MYSQL_HOST", default="localhost"),
    "port": get_env_int("MYSQL_PORT", default=3306),
    "user": get_env_value("MYSQL_USER", default="root"),
    "password": get_env_value("MYSQL_PASSWORD", default=""),
    "database": get_env_value("MYSQL_DB", default="flask_db"),
}
MAIL_CONFIG = {
    "host": get_env_value("MAIL_SERVER", "ECOVIGILANTE_MAIL_HOST"),
    "port": get_env_int("MAIL_PORT", "ECOVIGILANTE_MAIL_PORT", default=587),
    "username": get_env_value("MAIL_USERNAME", "ECOVIGILANTE_MAIL_USER"),
    "password": get_env_value("MAIL_PASSWORD", "ECOVIGILANTE_MAIL_PASSWORD").replace(" ", ""),
    "sender": get_env_value(
        "MAIL_DEFAULT_SENDER",
        "ECOVIGILANTE_MAIL_SENDER",
        "MAIL_USERNAME",
        "ECOVIGILANTE_MAIL_USER",
    ),
    "use_tls": get_env_bool("MAIL_USE_TLS", "ECOVIGILANTE_MAIL_TLS", default=True),
}
SECURITY_CODE_TTL = get_env_int("EMAIL_OTP_GRACE_SECONDS", default=300)
app.secret_key = get_env_value("FLASK_SECRET_KEY", default=app.secret_key)


def get_db_connection():
    if mysql is None:
        return None, "El servicio no esta disponible en este momento."

    try:
        return mysql.connector.connect(**DB_CONFIG), None
    except Error as err:
        if errorcode and getattr(err, "errno", None) == errorcode.ER_BAD_DB_ERROR:
            try:
                bootstrap_config = {key: value for key, value in DB_CONFIG.items() if key != "database"}
                connection = mysql.connector.connect(**bootstrap_config)
                cursor = connection.cursor()
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
                connection.commit()
                cursor.close()
                connection.close()
                return mysql.connector.connect(**DB_CONFIG), None
            except Error:
                return None, "El servicio no esta disponible en este momento."
        return None, "El servicio no esta disponible en este momento."


def ensure_core_schema():
    connection, error = get_db_connection()
    if error:
        return error

    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tipo_documento (
                id_tipo_documento INT AUTO_INCREMENT PRIMARY KEY,
                descripcion VARCHAR(80) NOT NULL UNIQUE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tipo_genero (
                id_tipo_genero INT AUTO_INCREMENT PRIMARY KEY,
                descripcion VARCHAR(80) NOT NULL UNIQUE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tipo_usuario (
                id_tipo_usuario INT AUTO_INCREMENT PRIMARY KEY,
                descripcion VARCHAR(80) NOT NULL UNIQUE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nombres VARCHAR(120) NOT NULL,
                apellidos VARCHAR(120) NOT NULL,
                id_tipo_documento INT NOT NULL,
                numero_documento VARCHAR(40) NOT NULL UNIQUE,
                id_tipo_genero INT NOT NULL,
                correo VARCHAR(160) NOT NULL UNIQUE,
                telefono VARCHAR(40) NOT NULL,
                id_tipo_usuario INT NOT NULL,
                usuario VARCHAR(120) NOT NULL UNIQUE,
                contrasena VARCHAR(255) NOT NULL,
                foto_perfil VARCHAR(255) NULL,
                rostro_facial VARCHAR(255) NULL,
                ecopuntos INT NOT NULL DEFAULT 0,
                ecomultas INT NOT NULL DEFAULT 0,
                activo TINYINT(1) NOT NULL DEFAULT 1,
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_usuarios_tipo_usuario (id_tipo_usuario)
            )
            """
        )
        ensure_catalog_items(
            cursor,
            "tipo_documento",
            "id_tipo_documento",
            {
                "cedula_ciudadania": "Cedula de ciudadania",
                "tarjeta_identidad": "Tarjeta de identidad",
                "cedula_extranjeria": "Cedula de extranjeria",
                "pasaporte": "Pasaporte",
            },
            "id_tipo_documento",
        )
        ensure_catalog_items(
            cursor,
            "tipo_genero",
            "id_tipo_genero",
            {
                "femenino": "Femenino",
                "masculino": "Masculino",
                "otro": "Otro",
                "prefiero_no_decirlo": "Prefiero no decirlo",
            },
            "id_tipo_genero",
        )
        ensure_catalog_items(
            cursor,
            "tipo_usuario",
            "id_tipo_usuario",
            {
                "estudiante": "Estudiante",
                "docente": "Docente",
                "admin": "Admin",
            },
            "id_tipo_usuario",
        )
        ensure_unique_description_index(cursor, "tipo_documento")
        ensure_unique_description_index(cursor, "tipo_genero")
        ensure_unique_description_index(cursor, "tipo_usuario")
        connection.commit()
        return None
    except Error as err:
        print(f"[Ecovigilante] Error preparando esquema base: {err}")
        return "No fue posible preparar la base de datos."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def column_exists(cursor, table_name, column_name):
    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    row = cursor.fetchone()
    if isinstance(row, dict):
        return row["total"] > 0
    return row[0] > 0


def index_exists(cursor, table_name, index_name):
    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND index_name = %s
        """,
        (table_name, index_name),
    )
    row = cursor.fetchone()
    if isinstance(row, dict):
        return row["total"] > 0
    return row[0] > 0


def ensure_unique_description_index(cursor, table_name):
    index_name = f"uq_{table_name}_descripcion"
    if not index_exists(cursor, table_name, index_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD UNIQUE KEY {index_name} (descripcion)")


def normalize_catalog_key(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", ascii_value).strip()


def canonical_catalog_key(table_name, description):
    key = normalize_catalog_key(description)
    if table_name == "tipo_documento":
        if "cedula" in key and "extranjer" in key:
            return "cedula_extranjeria"
        if "cedula" in key:
            return "cedula_ciudadania"
        if "tarjeta" in key:
            return "tarjeta_identidad"
        if "pasaporte" in key:
            return "pasaporte"
    if table_name == "tipo_genero":
        if "femenino" in key:
            return "femenino"
        if "masculino" in key:
            return "masculino"
        if "prefiero" in key:
            return "prefiero_no_decirlo"
        if "otro" in key:
            return "otro"
    if table_name == "tipo_usuario":
        if "admin" in key:
            return "admin"
        if "docente" in key:
            return "docente"
        if "estudiante" in key:
            return "estudiante"
    return key


def ensure_catalog_items(cursor, table_name, id_field, canonical_items, user_field=None):
    cursor.execute(f"SELECT {id_field} AS id, descripcion FROM {table_name} ORDER BY {id_field}")
    rows = cursor.fetchall()
    canonical_ids = {}

    for row in rows:
        row_id = row["id"] if isinstance(row, dict) else row[0]
        description = row["descripcion"] if isinstance(row, dict) else row[1]
        key = canonical_catalog_key(table_name, description)
        if key in canonical_items:
            canonical_ids[key] = min(canonical_ids.get(key, row_id), row_id)

    for key, description in canonical_items.items():
        if key not in canonical_ids:
            cursor.execute(f"INSERT INTO {table_name} (descripcion) VALUES (%s)", (description,))
            canonical_ids[key] = cursor.lastrowid

    cursor.execute(f"SELECT {id_field} AS id, descripcion FROM {table_name} ORDER BY {id_field}")
    rows = cursor.fetchall()
    delete_ids = []
    for row in rows:
        row_id = row["id"] if isinstance(row, dict) else row[0]
        description = row["descripcion"] if isinstance(row, dict) else row[1]
        key = canonical_catalog_key(table_name, description)
        canonical_id = canonical_ids.get(key)
        if not canonical_id:
            delete_ids.append(row_id)
            continue
        if row_id != canonical_id:
            if user_field:
                cursor.execute(f"UPDATE usuarios SET {user_field} = %s WHERE {user_field} = %s", (canonical_id, row_id))
            delete_ids.append(row_id)

    for row_id in delete_ids:
        cursor.execute(f"DELETE FROM {table_name} WHERE {id_field} = %s", (row_id,))

    for key, description in canonical_items.items():
        cursor.execute(
            f"UPDATE {table_name} SET descripcion = %s WHERE {id_field} = %s",
            (description, canonical_ids[key]),
        )


def ensure_user_profile_columns():
    core_error = ensure_core_schema()
    if core_error:
        return core_error

    connection, error = get_db_connection()
    if error:
        return error

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        if not column_exists(cursor, "usuarios", "activo"):
            cursor.execute("ALTER TABLE usuarios ADD COLUMN activo TINYINT(1) NOT NULL DEFAULT 1")
        if not column_exists(cursor, "usuarios", "foto_perfil"):
            cursor.execute("ALTER TABLE usuarios ADD COLUMN foto_perfil VARCHAR(255) NULL")
        if not column_exists(cursor, "usuarios", "rostro_facial"):
            cursor.execute("ALTER TABLE usuarios ADD COLUMN rostro_facial VARCHAR(255) NULL")
        if not column_exists(cursor, "usuarios", "ecopuntos"):
            cursor.execute("ALTER TABLE usuarios ADD COLUMN ecopuntos INT NOT NULL DEFAULT 0")
        if not column_exists(cursor, "usuarios", "ecomultas"):
            cursor.execute("ALTER TABLE usuarios ADD COLUMN ecomultas INT NOT NULL DEFAULT 0")
        connection.commit()
        return None
    except Error:
        return "No fue posible preparar la informacion de perfiles."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def allowed_profile_file(filename):
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return extension in ALLOWED_PROFILE_EXTENSIONS


def allowed_face_file(filename):
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return extension in ALLOWED_FACE_EXTENSIONS


def save_profile_photo(file_storage, user_id):
    if not file_storage or not file_storage.filename:
        return None, None
    if not allowed_profile_file(file_storage.filename):
        return None, "La foto debe ser JPG, PNG o WEBP."

    PROFILE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    extension = secure_filename(file_storage.filename).rsplit(".", 1)[-1].lower()
    filename = f"user-{user_id}-{int(time.time())}.{extension}"
    file_storage.save(PROFILE_UPLOAD_DIR / filename)
    return f"profile_photos/{filename}", None


def safe_document_folder(numero_documento):
    clean_value = re.sub(r"[^A-Za-z0-9_-]", "", numero_documento or "")
    return clean_value or "sin-documento"


def save_registration_face(numero_documento, image_data_json=""):
    document_folder = safe_document_folder(numero_documento)
    target_dir = FACE_DATASET_DIR / document_folder
    target_dir.mkdir(parents=True, exist_ok=True)

    # Clean previous photos for this user
    for existing in target_dir.glob("rostro_*.jpg"):
        existing.unlink()

    if not image_data_json:
        return [], "Toma al menos una foto de rostro para completar el registro."

    try:
        images = json.loads(image_data_json) if image_data_json.startswith("[") else [image_data_json]
    except (json.JSONDecodeError, TypeError):
        images = [image_data_json]

    saved_paths = []
    for idx, image_data in enumerate(images, 1):
        try:
            encoded = image_data.split(",", 1)[1] if "," in image_data else image_data
            image_bytes = base64.b64decode(encoded)
            if not image_bytes:
                continue
            filename = f"rostro_{idx}.jpg"
            target_path = target_dir / filename
            target_path.write_bytes(image_bytes)
            saved_paths.append(f"face_dataset/{document_folder}/{filename}")
        except Exception:
            continue

    if not saved_paths:
        return [], "La foto de rostro no es valida."

    return saved_paths, None


def get_default_student_type_id():
    user_types, error = fetch_catalog("tipo_usuario", "id_tipo_usuario")
    if error:
        return None, error

    for item in user_types:
        if normalize_role_name(item["descripcion"]) == "estudiante":
            return item["id"], None

    if user_types:
        return user_types[0]["id"], None
    return None, "No hay tipos de usuario disponibles."


def get_public_user_type_id(raw_type_id):
    user_types, error = fetch_catalog("tipo_usuario", "id_tipo_usuario")
    if error:
        return None, error

    requested = str(raw_type_id or "").strip()
    for item in user_types:
        role = normalize_role_name(item["descripcion"])
        if str(item["id"]) == requested and role in {"estudiante", "docente"}:
            return item["id"], None

    return get_default_student_type_id()


def is_duplicate_error(err):
    return bool(
        errorcode
        and getattr(err, "errno", None) == errorcode.ER_DUP_ENTRY
    )


def duplicate_user_message(err):
    detail = str(err).lower()
    if "numero_documento" in detail:
        return "Ya existe un usuario registrado con ese numero de documento."
    if "correo" in detail or "email" in detail:
        return "Ya existe un usuario registrado con ese correo."
    if "usuario" in detail:
        return "Ya existe un usuario con esos datos de acceso. Intenta nuevamente."
    return "Ya existe un registro con esos datos."


def make_security_code(length=6):
    return "".join(secrets.choice("0123456789") for _ in range(length))


def hash_security_code(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def verify_security_code(stored_hash, submitted_code):
    return secrets.compare_digest(stored_hash or "", hash_security_code(submitted_code or ""))


def code_is_expired(expires_at):
    return time.time() > float(expires_at or 0)


def send_email_message(to_email, subject, body):
    if not all([MAIL_CONFIG["host"], MAIL_CONFIG["sender"], MAIL_CONFIG["username"], MAIL_CONFIG["password"]]):
        print(f"[Ecovigilante] {subject} para {to_email}: {body}")
        return True, "Correo simulado en consola local."

    message = EmailMessage()
    message["From"] = f"Ecovigilante <{MAIL_CONFIG['sender']}>"
    message["To"] = to_email
    message["Subject"] = subject
    message["Reply-To"] = MAIL_CONFIG["sender"]
    message["X-Ecovigilante-Notice"] = "security-code"
    message.set_content(body)
    message.add_alternative(
        f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #163126;">
            <div style="max-width: 520px; padding: 24px; border: 1px solid #d8ead2; border-radius: 16px;">
              <h2 style="margin-top: 0; color: #1d5a35;">Ecovigilante</h2>
              <p>{body.replace(chr(10), '<br>')}</p>
            </div>
          </body>
        </html>
        """,
        subtype="html",
    )

    try:
        with smtplib.SMTP(MAIL_CONFIG["host"], MAIL_CONFIG["port"], timeout=15) as smtp:
            smtp.ehlo()
            if MAIL_CONFIG["use_tls"]:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(MAIL_CONFIG["username"], MAIL_CONFIG["password"])
            refused = smtp.send_message(message)
            if refused:
                print(f"[Ecovigilante] Destinatarios rechazados: {refused}")
                return False, "El correo no pudo ser entregado al destinatario."
        return True, None
    except Exception as err:
        print(f"[Ecovigilante] Error enviando correo: {err}")
        return False, "No fue posible enviar el correo de verificacion. Intenta nuevamente."


def normalize_username_piece(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    clean_value = re.sub(r"[^a-z0-9]+", ".", ascii_value).strip(".")
    return clean_value or "usuario"


def generate_unique_username(nombres, apellidos, numero_documento):
    schema_error = ensure_user_profile_columns()
    if schema_error:
        return None, schema_error

    first_name = nombres.split()[0] if nombres else "usuario"
    first_lastname = apellidos.split()[0] if apellidos else "general"
    document_digits = re.sub(r"\D", "", numero_documento or "")
    suffix = document_digits[-4:] if document_digits else "0000"
    base_username = ".".join(
        [
            normalize_username_piece(first_name),
            normalize_username_piece(first_lastname),
            suffix,
        ]
    )

    connection, error = get_db_connection()
    if error:
        return None, error

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        candidate = base_username
        sequence = 1

        while True:
            cursor.execute(
                """
                SELECT id
                FROM usuarios
                WHERE usuario = %s
                LIMIT 1
                """,
                (candidate,),
            )
            if not cursor.fetchone():
                return candidate, None

            sequence += 1
            candidate = f"{base_username}.{sequence}"
    except Error as err:
        return None, USER_SAFE_ERROR
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def fetch_users():
    ensure_user_profile_columns()
    connection, error = get_db_connection()
    if error:
        return [], error

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                u.id,
                u.usuario,
                u.nombres,
                u.apellidos,
                td.descripcion AS tipo_documento,
                u.numero_documento,
                tg.descripcion AS tipo_genero,
                tu.descripcion AS tipo_usuario,
                u.correo,
                u.telefono,
                u.activo,
                u.foto_perfil,
                u.rostro_facial,
                u.ecopuntos,
                u.ecomultas,
                u.fecha_registro
            FROM usuarios u
            LEFT JOIN tipo_documento td ON td.id_tipo_documento = u.id_tipo_documento
            LEFT JOIN tipo_genero tg ON tg.id_tipo_genero = u.id_tipo_genero
            LEFT JOIN tipo_usuario tu ON tu.id_tipo_usuario = u.id_tipo_usuario
            ORDER BY u.id DESC
            """
        )
        return cursor.fetchall(), None
    except Error:
        return [], "No fue posible consultar la informacion solicitada."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def fetch_catalog(table_name, id_field):
    schema_error = ensure_user_profile_columns()
    if schema_error:
        return [], schema_error

    connection, error = get_db_connection()
    if error:
        return [], error

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            f"""
            SELECT {id_field} AS id, descripcion
            FROM {table_name}
            ORDER BY descripcion ASC
            """
        )
        return cursor.fetchall(), None
    except Error:
        return [], "No fue posible cargar las opciones del formulario."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def get_form_options():
    document_types, doc_error = fetch_catalog("tipo_documento", "id_tipo_documento")
    gender_types, gen_error = fetch_catalog("tipo_genero", "id_tipo_genero")
    return {
        "document_types": document_types,
        "gender_types": gender_types,
        "options_error": doc_error or gen_error,
    }


def create_user(form_data):
    schema_error = ensure_user_profile_columns()
    if schema_error:
        return None, schema_error

    default_type_id, type_error = get_default_student_type_id()
    if type_error:
        return None, type_error

    generated_username, error = generate_unique_username(
        form_data["nombres"],
        form_data["apellidos"],
        form_data["numero_documento"],
    )
    if error:
        return None, error

    connection, error = get_db_connection()
    if error:
        return None, error

    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO usuarios (
                nombres,
                apellidos,
                id_tipo_documento,
                numero_documento,
                id_tipo_genero,
                correo,
                telefono,
                id_tipo_usuario,
                usuario,
                contrasena
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                form_data["nombres"],
                form_data["apellidos"],
                form_data["id_tipo_documento"],
                form_data["numero_documento"],
                form_data["id_tipo_genero"],
                form_data["correo"],
                form_data["telefono"],
                default_type_id,
                generated_username,
                generate_password_hash(form_data["contrasena"]),
            ),
        )
        new_user_id = cursor.lastrowid
        face_paths, face_error = save_registration_face(
            form_data["numero_documento"],
            form_data.get("foto_rostro_data", ""),
        )
        if face_error:
            connection.rollback()
            return None, face_error
        if face_paths:
            cursor.execute(
                """
                UPDATE usuarios
                SET rostro_facial = %s
                WHERE id = %s
                """,
                (face_paths[0], new_user_id),
            )
        connection.commit()
        return generated_username, None
    except Error as err:
        if is_duplicate_error(err):
            return None, duplicate_user_message(err)
        return None, USER_SAFE_ERROR
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def validate_login(correo, contrasena):
    ensure_user_profile_columns()
    connection, error = get_db_connection()
    if error:
        return None, error

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                u.id,
                u.usuario,
                u.nombres,
                u.apellidos,
                u.correo,
                u.contrasena,
                u.id_tipo_usuario,
                u.activo,
                tu.descripcion AS tipo_usuario
            FROM usuarios u
            LEFT JOIN tipo_usuario tu ON tu.id_tipo_usuario = u.id_tipo_usuario
            WHERE u.correo = %s
            LIMIT 1
            """,
            (correo,),
        )
        user = cursor.fetchone()
        if not user:
            return None, "No encontramos un usuario con ese correo."

        if "activo" in user and not user["activo"]:
            return None, "Tu usuario esta inhabilitado. Contacta al administrador."

        stored_password = user["contrasena"] or ""
        is_valid = (
            check_password_hash(stored_password, contrasena)
            if stored_password.startswith(("pbkdf2:", "scrypt:"))
            else stored_password == contrasena
        )

        if not is_valid:
            return None, "La contrasena ingresada no es valida."

        return user, f"Bienvenido, {user['nombres']} {user['apellidos']}."
    except Error:
        return None, "No fue posible validar el inicio de sesion. Intenta nuevamente."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def fetch_user_profile(user_id):
    ensure_user_profile_columns()
    connection, error = get_db_connection()
    if error:
        return None, error

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                u.id,
                u.usuario,
                u.nombres,
                u.apellidos,
                td.descripcion AS tipo_documento,
                u.numero_documento,
                tg.descripcion AS tipo_genero,
                u.id_tipo_usuario,
                tu.descripcion AS tipo_usuario,
                u.correo,
                u.telefono,
                u.activo,
                u.foto_perfil,
                u.rostro_facial,
                u.ecopuntos,
                u.ecomultas,
                u.fecha_registro
            FROM usuarios u
            LEFT JOIN tipo_documento td ON td.id_tipo_documento = u.id_tipo_documento
            LEFT JOIN tipo_genero tg ON tg.id_tipo_genero = u.id_tipo_genero
            LEFT JOIN tipo_usuario tu ON tu.id_tipo_usuario = u.id_tipo_usuario
            WHERE u.id = %s
            LIMIT 1
            """,
            (user_id,),
        )
        user = cursor.fetchone()
        if not user:
            return None, "No fue posible encontrar el usuario solicitado."

        user["ecopuntos"] = int(user.get("ecopuntos") or 0)
        user["ecomultas"] = int(user.get("ecomultas") or 0)
        user["saldo_ambiental"] = user["ecopuntos"] - user["ecomultas"]
        return user, None
    except Error:
        return None, "No fue posible consultar tu perfil. Intenta nuevamente."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def fetch_user_by_email(correo):
    connection, error = get_db_connection()
    if error:
        return None, error

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, usuario, nombres, apellidos, correo, contrasena
            FROM usuarios
            WHERE correo = %s
            LIMIT 1
            """,
            (correo,),
        )
        user = cursor.fetchone()
        if not user:
            return None, "No encontramos un usuario con ese correo."
        return user, None
    except Error:
        return None, "No fue posible consultar el usuario. Intenta nuevamente."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def update_user_password(user_id, new_password):
    connection, error = get_db_connection()
    if error:
        return error

    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE usuarios
            SET contrasena = %s
            WHERE id = %s
            """,
            (generate_password_hash(new_password), user_id),
        )
        connection.commit()
        return None
    except Error:
        return "No fue posible actualizar la contrasena. Intenta nuevamente."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def update_user_profile(user_id, form_data, photo_path=None):
    ensure_user_profile_columns()
    connection, error = get_db_connection()
    if error:
        return error

    cursor = None
    try:
        cursor = connection.cursor()
        values = [
            form_data["nombres"],
            form_data["apellidos"],
            form_data["id_tipo_documento"],
            form_data["numero_documento"],
            form_data["id_tipo_genero"],
            form_data["correo"],
            form_data["telefono"],
        ]
        photo_sql = ""
        if photo_path:
            photo_sql = ", foto_perfil = %s"
            values.append(photo_path)
        values.append(user_id)
        cursor.execute(
            f"""
            UPDATE usuarios
            SET nombres = %s,
                apellidos = %s,
                id_tipo_documento = %s,
                numero_documento = %s,
                id_tipo_genero = %s,
                correo = %s,
                telefono = %s
                {photo_sql}
            WHERE id = %s
            """,
            tuple(values),
        )
        connection.commit()
        return None
    except Error as err:
        if is_duplicate_error(err):
            return duplicate_user_message(err)
        return "No fue posible actualizar el perfil."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def admin_update_user(user_id, form_data):
    ensure_user_profile_columns()
    connection, error = get_db_connection()
    if error:
        return error

    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE usuarios
            SET nombres = %s,
                apellidos = %s,
                id_tipo_documento = %s,
                numero_documento = %s,
                id_tipo_genero = %s,
                id_tipo_usuario = %s,
                correo = %s,
                telefono = %s
            WHERE id = %s
            """,
            (
                form_data["nombres"],
                form_data["apellidos"],
                form_data["id_tipo_documento"],
                form_data["numero_documento"],
                form_data["id_tipo_genero"],
                form_data["id_tipo_usuario"],
                form_data["correo"],
                form_data["telefono"],
                user_id,
            ),
        )
        connection.commit()
        return None
    except Error as err:
        if is_duplicate_error(err):
            return duplicate_user_message(err)
        return "No fue posible actualizar el usuario."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def set_user_active_status(user_id, active):
    ensure_user_profile_columns()
    connection, error = get_db_connection()
    if error:
        return error

    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE usuarios
            SET activo = %s
            WHERE id = %s
            """,
            (1 if active else 0, user_id),
        )
        connection.commit()
        return None
    except Error:
        return "No fue posible cambiar el estado del usuario."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def build_recovery_file_key(user):
    raw_value = "|".join(
        [
            app.secret_key,
            str(user.get("id", "")),
            user.get("correo", ""),
            user.get("usuario", ""),
            user.get("contrasena", ""),
        ]
    )
    digest = hashlib.sha256(raw_value.encode("utf-8")).hexdigest()
    return f"{RECOVERY_FILE_PREFIX}-{digest}"


def build_recovery_file_content(user):
    return "\n".join(
        [
            "Archivo de recuperacion de Ecovigilante",
            f"correo={user['correo']}",
            f"usuario={user['usuario']}",
            f"clave={build_recovery_file_key(user)}",
            "",
        ]
    )


def parse_recovery_file(content):
    data = {}
    for line in (content or "").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip().lower()] = value.strip()
    return data


def normalize_role_name(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    clean_value = re.sub(r"[^a-z0-9]+", " ", ascii_value).strip()
    if "admin" in clean_value:
        return "admin"
    if "docente" in clean_value or "profesor" in clean_value:
        return "docente"
    return "estudiante"


def dashboard_endpoint_for_role(role_name):
    role = normalize_role_name(role_name)
    if role == "admin":
        return "admin_dashboard"
    if role == "docente":
        return "teacher_dashboard"
    return "student_dashboard"


def fetch_user_type_counts():
    connection, error = get_db_connection()
    if error:
        return [], error

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                COALESCE(tu.descripcion, 'Sin tipo') AS tipo_usuario,
                COUNT(u.id) AS total
            FROM usuarios u
            LEFT JOIN tipo_usuario tu ON tu.id_tipo_usuario = u.id_tipo_usuario
            GROUP BY tu.descripcion
            ORDER BY total DESC, tipo_usuario ASC
            """
        )
        return cursor.fetchall(), None
    except Error as err:
        return [], f"No fue posible consultar usuarios por tipo: {err}"
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def require_current_user():
    user_id = session.get("user_id")
    if not user_id:
        flash("Inicia sesion para ver tu pagina personal.", "error")
        return None, redirect(url_for("login"))

    user, error = fetch_user_profile(user_id)
    if error:
        flash(error, "error")
        return None, redirect(url_for("login"))

    return user, None


def ensure_role(user, allowed_roles):
    current_role = normalize_role_name(user.get("tipo_usuario"))
    if current_role in allowed_roles:
        return None

    flash("Tu usuario no tiene permiso para entrar a esa pantalla.", "error")
    return redirect(url_for(dashboard_endpoint_for_role(user.get("tipo_usuario"))))


def ensure_class_tables():
    core_error = ensure_user_profile_columns()
    if core_error:
        return core_error

    connection, error = get_db_connection()
    if error:
        return error

    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS clases_docente (
                id_clase INT AUTO_INCREMENT PRIMARY KEY,
                id_docente INT NOT NULL,
                nombre VARCHAR(120) NOT NULL,
                codigo VARCHAR(16) NOT NULL UNIQUE,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_clases_docente_id_docente (id_docente)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS inscripciones_clase (
                id_inscripcion INT AUTO_INCREMENT PRIMARY KEY,
                id_clase INT NOT NULL,
                id_estudiante INT NOT NULL,
                fecha_inscripcion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_clase_estudiante (id_clase, id_estudiante),
                INDEX idx_inscripciones_clase (id_clase),
                INDEX idx_inscripciones_estudiante (id_estudiante)
            )
            """
        )
        connection.commit()
        return None
    except Error:
        return "No fue posible preparar las clases. Intenta nuevamente."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def ensure_classification_tables():
    core_error = ensure_user_profile_columns()
    if core_error:
        return core_error
    connection, error = get_db_connection()
    if error:
        return error
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS registros_clasificacion (
                id INT AUTO_INCREMENT PRIMARY KEY,
                id_usuario INT NOT NULL,
                fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
                residuo_detectado VARCHAR(100),
                categoria_asignada VARCHAR(50),
                categoria_correcta VARCHAR(50),
                es_correcto TINYINT(1) NOT NULL DEFAULT 0,
                confianza_modelo FLOAT,
                container_color VARCHAR(20),
                es_auto_capture TINYINT(1) NOT NULL DEFAULT 1,
                INDEX idx_reg_clasif_usuario (id_usuario),
                INDEX idx_reg_clasif_fecha (fecha_hora)
            )
            """
        )
        connection.commit()
        return None
    except Error:
        return "No fue posible preparar la tabla de clasificaciones."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def make_class_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(6))


def create_teacher_class(teacher_id, class_name):
    error = ensure_class_tables()
    if error:
        return None, error

    clean_name = (class_name or "").strip()
    if not clean_name:
        return None, "Escribe el nombre de la materia o clase."

    connection, error = get_db_connection()
    if error:
        return None, error

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        for _ in range(12):
            code = make_class_code()
            try:
                cursor.execute(
                    """
                    INSERT INTO clases_docente (id_docente, nombre, codigo)
                    VALUES (%s, %s, %s)
                    """,
                    (teacher_id, clean_name, code),
                )
                connection.commit()
                cursor.execute(
                    """
                    SELECT id_clase, id_docente, nombre, codigo, fecha_creacion
                    FROM clases_docente
                    WHERE id_clase = %s
                    LIMIT 1
                    """,
                    (cursor.lastrowid,),
                )
                return cursor.fetchone(), None
            except Error as err:
                if is_duplicate_error(err):
                    continue
                raise

        return None, "No fue posible generar el codigo de la clase."
    except Error:
        return None, "No fue posible crear la clase."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def fetch_teacher_classes(teacher_id):
    error = ensure_class_tables()
    if error:
        return [], error

    connection, error = get_db_connection()
    if error:
        return [], error

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                c.id_clase,
                c.id_docente,
                c.nombre,
                c.codigo,
                c.fecha_creacion,
                COUNT(i.id_inscripcion) AS total_estudiantes
            FROM clases_docente c
            LEFT JOIN inscripciones_clase i ON i.id_clase = c.id_clase
            WHERE c.id_docente = %s
            GROUP BY c.id_clase, c.id_docente, c.nombre, c.codigo, c.fecha_creacion
            ORDER BY c.fecha_creacion DESC, c.id_clase DESC
            """,
            (teacher_id,),
        )
        return cursor.fetchall(), None
    except Error:
        return [], "No fue posible cargar tus clases."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def fetch_teacher_class_students(class_id):
    error = ensure_class_tables()
    if error:
        return [], error

    connection, error = get_db_connection()
    if error:
        return [], error

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                u.id,
                u.nombres,
                u.apellidos,
                u.correo,
                u.usuario,
                u.ecopuntos,
                u.ecomultas,
                i.fecha_inscripcion
            FROM inscripciones_clase i
            INNER JOIN usuarios u ON u.id = i.id_estudiante
            WHERE i.id_clase = %s
            ORDER BY i.fecha_inscripcion DESC
            """,
            (class_id,),
        )
        students = cursor.fetchall()
        for student in students:
            student["ecopuntos"] = int(student.get("ecopuntos") or 0)
            student["ecomultas"] = int(student.get("ecomultas") or 0)
            student["saldo_ambiental"] = student["ecopuntos"] - student["ecomultas"]
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(es_correcto = 1) AS correctas,
                    SUM(es_correcto = 0) AS incorrectas
                FROM registros_clasificacion
                WHERE id_usuario = %s
                """,
                (student["id"],),
            )
            stats = cursor.fetchone()
            student["clasificaciones_total"] = stats["total"] or 0
            student["clasificaciones_correctas"] = stats["correctas"] or 0
            student["clasificaciones_incorrectas"] = stats["incorrectas"] or 0
            total = student["clasificaciones_total"]
            student["porcentaje_aciertos"] = round(stats["correctas"] / total * 100, 1) if total > 0 else 0.0
        return students, None
    except Error:
        return [], "No fue posible cargar los estudiantes inscritos."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def fetch_class_by_code(class_code):
    error = ensure_class_tables()
    if error:
        return None, error

    connection, error = get_db_connection()
    if error:
        return None, error

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                c.id_clase,
                c.id_docente,
                c.nombre,
                c.codigo,
                c.fecha_creacion,
                d.nombres AS docente_nombres,
                d.apellidos AS docente_apellidos,
                d.correo AS docente_correo
            FROM clases_docente c
            INNER JOIN usuarios d ON d.id = c.id_docente
            WHERE c.codigo = %s
            LIMIT 1
            """,
            (class_code,),
        )
        teacher_class = cursor.fetchone()
        if not teacher_class:
            return None, "No encontramos una clase con ese codigo."
        return teacher_class, None
    except Error:
        return None, "No fue posible buscar la clase."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def enroll_student_in_class(student_id, class_code):
    clean_code = re.sub(r"[^A-Za-z0-9]", "", class_code or "").upper()
    if not clean_code:
        return None, "Ingresa el codigo de la clase."

    teacher_class, error = fetch_class_by_code(clean_code)
    if error:
        return None, error

    connection, error = get_db_connection()
    if error:
        return None, error

    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO inscripciones_clase (id_clase, id_estudiante)
            VALUES (%s, %s)
            """,
            (teacher_class["id_clase"], student_id),
        )
        connection.commit()
        return teacher_class, "Inscripcion realizada correctamente."
    except Error as err:
        if is_duplicate_error(err):
            return teacher_class, "Ya estas inscrito en esta clase."
        return None, "No fue posible completar la inscripcion."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def fetch_student_enrollments(student_id):
    error = ensure_class_tables()
    if error:
        return [], error

    connection, error = get_db_connection()
    if error:
        return [], error

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                c.id_clase,
                c.nombre,
                c.codigo,
                i.fecha_inscripcion,
                d.nombres AS docente_nombres,
                d.apellidos AS docente_apellidos,
                d.correo AS docente_correo
            FROM inscripciones_clase i
            INNER JOIN clases_docente c ON c.id_clase = i.id_clase
            INNER JOIN usuarios d ON d.id = c.id_docente
            WHERE i.id_estudiante = %s
            ORDER BY i.fecha_inscripcion DESC
            """,
            (student_id,),
        )
        return cursor.fetchall(), None
    except Error:
        return [], "No fue posible cargar tus clases inscritas."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def face_model_available():
    try:
        from face_recognizer import is_available
        return is_available()
    except ImportError:
        return False


def fetch_user_by_document(numero_documento):
    schema_error = ensure_user_profile_columns()
    if schema_error:
        return None, schema_error

    clean_document = (numero_documento or "").strip()
    if not clean_document:
        return None, "No se recibio el documento reconocido."

    connection, error = get_db_connection()
    if error:
        return None, error

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                id,
                nombres,
                apellidos,
                numero_documento,
                ecopuntos,
                ecomultas
            FROM usuarios
            WHERE numero_documento = %s
            LIMIT 1
            """,
            (clean_document,),
        )
        user = cursor.fetchone()
        if not user:
            return None, "No encontramos un usuario con ese documento."
        user["ecopuntos"] = int(user.get("ecopuntos") or 0)
        user["ecomultas"] = int(user.get("ecomultas") or 0)
        user["saldo_ambiental"] = user["ecopuntos"] - user["ecomultas"]
        return user, None
    except Error:
        return None, "No fue posible buscar el usuario reconocido."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def apply_eco_action(numero_documento, action, amount=1):
    user, error = fetch_user_by_document(numero_documento)
    if error:
        return None, error

    try:
        amount = max(1, int(amount or 1))
    except (TypeError, ValueError):
        amount = 1

    clean_action = (action or "").strip().lower()
    if clean_action not in {"sumar", "restar"}:
        return None, "Selecciona si deseas sumar ecopuntos o registrar ecomulta."

    field = "ecopuntos" if clean_action == "sumar" else "ecomultas"
    connection, error = get_db_connection()
    if error:
        return None, error

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            f"""
            UPDATE usuarios
            SET {field} = {field} + %s
            WHERE id = %s
            """,
            (amount, user["id"]),
        )
        connection.commit()
        return fetch_user_by_document(user["numero_documento"])
    except Error:
        return None, "No fue posible actualizar el saldo ambiental."
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def ensure_ai_process():
    global _ai_process

    if not IA_PYTHON.exists():
        return None, "No se encontro el entorno de Python de la carpeta IA."

    if not IA_SERVER.exists():
        return None, "No se encontro el archivo servidor para consultar la IA."

    if _ai_process and _ai_process.poll() is None:
        return _ai_process, None

    try:
        _ai_process = subprocess.Popen(
            [str(IA_PYTHON), str(IA_SERVER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except Exception as err:  # pragma: no cover
        return None, f"No fue posible iniciar la IA local: {err}"

    return _ai_process, None


def ask_local_ai(prompt):
    with _ai_lock:
        process, error = ensure_ai_process()
        if error:
            return None, error

        try:
            payload = json.dumps({"prompt": prompt}, ensure_ascii=False)
            process.stdin.write(payload + "\n")
            process.stdin.flush()

            raw_line = process.stdout.readline()
            if not raw_line:
                detail = process.stderr.read().strip()
                return None, detail or "La IA local dejo de responder."

            message = json.loads(raw_line)
        except json.JSONDecodeError:
            return None, "La respuesta de la IA local no tuvo un formato valido."
        except Exception as err:  # pragma: no cover
            return None, f"No fue posible comunicarse con la IA local: {err}"

    if not message.get("ok"):
        return None, message.get("error") or "La IA local devolvio un error."

    answer = (message.get("answer") or "").strip()
    if not answer:
        return None, "La IA no devolvio respuesta."
    return answer, None


@app.context_processor
def inject_session_user():
    return {
        "session_username": session.get("username"),
        "session_display_name": session.get("display_name"),
        "session_user_id": session.get("user_id"),
        "session_user_type": session.get("user_type"),
        "session_dashboard_endpoint": dashboard_endpoint_for_role(session.get("user_type")),
    }


@app.route("/")
def home():
    return render_template(
        "index.html",
        color_palette=COLOR_PALETTE,
        font_showcase=FONT_SHOWCASE,
        open_ai_panel=False,
    )


@app.route("/camara")
def camera_page():
    return render_template(
        "camera.html",
        categories=get_camera_category_info(),
        session_user_id=session.get("user_id"),
        session_dashboard_endpoint=dashboard_endpoint_for_role(session.get("user_type")),
    )


@app.route("/camara/classify", methods=["POST"])
def camera_classify():
    classifier, error = get_camera_classifier()
    if error:
        return jsonify({"error": error}), 503
    if "image" not in request.files:
        return jsonify({"error": "No se encontro la imagen"}), 400

    image_bytes = request.files["image"].read()
    return jsonify(classifier.classify(image_bytes))


@app.route("/camara/classify_base64", methods=["POST"])
def camera_classify_base64():
    classifier, error = get_camera_classifier()
    if error:
        return jsonify({"error": error}), 503

    image_bytes, payload_error = decode_camera_image_payload(request.get_json(silent=True))
    if payload_error:
        return jsonify({"error": payload_error}), 400

    return jsonify(classifier.classify(image_bytes))


@app.route("/camara/detect", methods=["POST"])
def camera_detect():
    classifier, error = get_camera_classifier()
    if error:
        return jsonify({"error": error}), 503

    image_bytes, payload_error = decode_camera_image_payload(request.get_json(silent=True))
    if payload_error:
        return jsonify({"error": payload_error}), 400

    return jsonify(classifier.detect(image_bytes))


@app.route("/camara/detect_with_container", methods=["POST"])
def camera_detect_with_container():
    classifier, error = get_camera_classifier()
    if error:
        return jsonify({"error": error}), 503

    image_bytes, payload_error = decode_camera_image_payload(request.get_json(silent=True))
    if payload_error:
        return jsonify({"error": payload_error}), 400

    return jsonify(classifier.detect_with_container(image_bytes))


@app.route("/camara/modelo-facial")
def camera_face_model_status():
    available = face_model_available()
    return jsonify({"available": available})


@app.route("/camara/usuario-por-documento")
def camera_user_by_document():
    user, error = fetch_user_by_document(request.args.get("documento", ""))
    if error:
        return jsonify({"ok": False, "error": error}), 404
    return jsonify({"ok": True, "user": user})


@app.route("/camara/ecoaccion", methods=["POST"])
def camera_eco_action():
    payload = request.get_json(silent=True) or {}
    user, error = apply_eco_action(
        payload.get("documento", ""),
        payload.get("accion", ""),
        payload.get("cantidad", 1),
    )
    if error:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, "user": user})


@app.route("/camara/registrar-clasificacion", methods=["POST"])
def camera_register_classification():
    payload = request.get_json(silent=True) or {}
    user, error = fetch_user_by_document(payload.get("documento", ""))
    if error:
        return jsonify({"ok": False, "error": error}), 404

    error = ensure_classification_tables()
    if error:
        return jsonify({"ok": False, "error": error}), 500

    action = payload.get("action", "")
    waste_items = payload.get("waste_items", [])
    container_color = payload.get("container_color", "")
    validation = payload.get("validation", {})
    es_correcto = 1 if validation.get("valid") else 0
    es_auto = 1 if payload.get("auto_capture", False) else 0

    connection, db_error = get_db_connection()
    if db_error:
        return jsonify({"ok": False, "error": db_error}), 500
    cursor = None
    try:
        cursor = connection.cursor()
        for item in waste_items:
            cursor.execute(
                """
                INSERT INTO registros_clasificacion
                    (id_usuario, residuo_detectado, categoria_asignada, categoria_correcta,
                     es_correcto, confianza_modelo, container_color, es_auto_capture)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user["id"],
                    item.get("class", ""),
                    item.get("category", ""),
                    validation.get("expected_category", ""),
                    es_correcto,
                    item.get("confidence", 0.0),
                    container_color,
                    es_auto,
                ),
            )

        if es_correcto == 1:
            user, eco_error = apply_eco_action(
                payload.get("documento", ""), "sumar", payload.get("cantidad", 1)
            )
        else:
            user, eco_error = apply_eco_action(
                payload.get("documento", ""), "restar", payload.get("cantidad", 1)
            )
        if eco_error:
            connection.rollback()
            return jsonify({"ok": False, "error": eco_error}), 400

        connection.commit()
        return jsonify({"ok": True, "user": user, "registros": len(waste_items)})
    except Error:
        connection.rollback()
        return jsonify({"ok": False, "error": "Error al registrar clasificacion."}), 500
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


@app.route("/api/estadisticas/<int:user_id>")
def api_user_stats(user_id):
    error = ensure_classification_tables()
    if error:
        return jsonify({"ok": False, "error": error}), 500

    connection, db_error = get_db_connection()
    if db_error:
        return jsonify({"ok": False, "error": db_error}), 500
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(es_correcto = 1) AS correctas,
                SUM(es_correcto = 0) AS incorrectas
            FROM registros_clasificacion
            WHERE id_usuario = %s
            """,
            (user_id,),
        )
        stats = cursor.fetchone()
        total = stats["total"] or 0
        correctas = stats["correctas"] or 0
        incorrectas = stats["incorrectas"] or 0
        stats["porcentaje_aciertos"] = round(correctas / total * 100, 1) if total > 0 else 0.0
        stats["ok"] = True

        cursor.execute(
            """
            SELECT residuo_detectado, categoria_asignada, es_correcto, confianza_modelo,
                   fecha_hora, container_color
            FROM registros_clasificacion
            WHERE id_usuario = %s
            ORDER BY fecha_hora DESC
            LIMIT 50
            """,
            (user_id,),
        )
        stats["historial"] = cursor.fetchall()
        return jsonify(stats)
    except Error:
        return jsonify({"ok": False, "error": "Error al consultar estadisticas."}), 500
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


@app.route("/api/estadisticas-clase/<int:class_id>")
def api_class_stats(class_id):
    error = ensure_classification_tables()
    if error:
        return jsonify({"ok": False, "error": error}), 500
    connection, db_error = get_db_connection()
    if db_error:
        return jsonify({"ok": False, "error": db_error}), 500
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                u.id, u.nombres, u.apellidos, u.numero_documento,
                COUNT(r.id) AS total,
                SUM(r.es_correcto = 1) AS correctas,
                SUM(r.es_correcto = 0) AS incorrectas
            FROM registros_clasificacion r
            INNER JOIN inscripciones_clase ic ON ic.id_estudiante = r.id_usuario AND ic.id_clase = %s
            INNER JOIN usuarios u ON u.id = r.id_usuario
            GROUP BY u.id
            ORDER BY correctas DESC
            """,
            (class_id,),
        )
        students = cursor.fetchall()
        for s in students:
            t = s["total"] or 0
            s["porcentaje_aciertos"] = round(s["correctas"] / t * 100, 1) if t > 0 else 0.0

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(es_correcto = 1) AS correctas,
                SUM(es_correcto = 0) AS incorrectas
            FROM registros_clasificacion r
            INNER JOIN inscripciones_clase ic ON ic.id_estudiante = r.id_usuario AND ic.id_clase = %s
            """,
            (class_id,),
        )
        global_stats = cursor.fetchone()
        t = global_stats["total"] or 0
        global_stats["porcentaje_aciertos"] = round(global_stats["correctas"] / t * 100, 1) if t > 0 else 0.0
        return jsonify({"ok": True, "students": students, "global": global_stats})
    except Error:
        return jsonify({"ok": False, "error": "Error al consultar estadisticas de la clase."}), 500
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


@app.route("/camara/reconocer-rostro", methods=["POST"])
def camera_recognize_face():
    import base64
    import io
    from PIL import Image
    from face_recognizer import recognize

    payload = request.get_json(silent=True) or {}
    image_data = payload.get("image", "")
    if not image_data:
        return jsonify({"ok": False, "error": "No se recibió imagen"}), 400

    try:
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]
        image_bytes = base64.b64decode(image_data)
        img = Image.open(io.BytesIO(image_bytes))
        doc, confidence = recognize(img)
        if not doc:
            return jsonify({"ok": False, "error": "Rostro no reconocido"}), 404
        user, error = fetch_user_by_document(doc)
        if error:
            return jsonify({"ok": False, "error": "Usuario no encontrado"}), 404
        return jsonify({"ok": True, "confidence": round(confidence, 3), "user": user})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/camara/retrain-faces", methods=["POST"])
def camera_retrain_faces():
    from face_recognizer import retrain

    try:
        result = retrain()
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/usuarios")
def users():
    users, db_message = fetch_users()
    return render_template("users.html", users=users, db_message=db_message)


@app.route("/mi-usuario")
def user_dashboard():
    if not session.get("user_id"):
        flash("Inicia sesion para ver tu pagina personal.", "error")
        return redirect(url_for("login"))

    return redirect(url_for(dashboard_endpoint_for_role(session.get("user_type"))))


@app.route("/perfil", methods=["GET", "POST"])
def profile():
    user, response = require_current_user()
    if response:
        return response

    options = get_form_options()
    if request.method == "POST":
        form_data = {
            "nombres": request.form.get("nombres", "").strip(),
            "apellidos": request.form.get("apellidos", "").strip(),
            "id_tipo_documento": request.form.get("id_tipo_documento", "").strip(),
            "numero_documento": request.form.get("numero_documento", "").strip(),
            "id_tipo_genero": request.form.get("id_tipo_genero", "").strip(),
            "id_tipo_usuario": request.form.get("id_tipo_usuario", "").strip(),
            "correo": request.form.get("correo", "").strip(),
            "telefono": request.form.get("telefono", "").strip(),
        }
        if not all(form_data.values()):
            flash("Completa todos los campos del perfil.", "error")
        else:
            photo_path, photo_error = save_profile_photo(request.files.get("foto_perfil"), user["id"])
            if photo_error:
                flash(photo_error, "error")
            else:
                error = update_user_profile(user["id"], form_data, photo_path)
                if error:
                    flash(error, "error")
                else:
                    session["display_name"] = f"{form_data['nombres']} {form_data['apellidos']}"
                    session["email"] = form_data["correo"]
                    flash("Perfil actualizado correctamente.", "success")
                    return redirect(url_for("profile"))

    user, _ = fetch_user_profile(user["id"])
    return render_template("profile.html", user=user, **options)


@app.route("/estudiante")
def student_dashboard():
    user, response = require_current_user()
    if response:
        return response

    response = ensure_role(user, {"estudiante"})
    if response:
        return response

    enrollments, enrollment_error = fetch_student_enrollments(user["id"])
    if enrollment_error:
        flash(enrollment_error, "error")

    return render_template("student_dashboard.html", user=user, enrollments=enrollments)


@app.route("/estudiante/inscribirse", methods=["POST"])
def enroll_by_class_code():
    user, response = require_current_user()
    if response:
        return response

    response = ensure_role(user, {"estudiante"})
    if response:
        return response

    class_code = request.form.get("codigo_clase", "")
    teacher_class, message = enroll_student_in_class(user["id"], class_code)
    flash(message, "success" if teacher_class else "error")
    return redirect(url_for("student_dashboard"))


@app.route("/docente")
def teacher_dashboard():
    user, response = require_current_user()
    if response:
        return response

    response = ensure_role(user, {"docente"})
    if response:
        return response

    teacher_classes, class_error = fetch_teacher_classes(user["id"])
    if class_error:
        flash(class_error, "error")

    total_students = 0
    for teacher_class in teacher_classes:
        students, students_error = fetch_teacher_class_students(teacher_class["id_clase"])
        if students_error:
            flash(students_error, "error")
            students = []
        teacher_class["students"] = students
        teacher_class["enrollment_url"] = url_for(
            "join_class_by_code",
            class_code=teacher_class["codigo"],
            _external=True,
        )
        total_students += len(students)

    return render_template(
        "teacher_dashboard.html",
        user=user,
        teacher_classes=teacher_classes,
        total_students=total_students,
    )


@app.route("/docente/descargar-pdf/<int:class_id>")
def teacher_class_pdf(class_id):
    user, response = require_current_user()
    if response:
        return response

    response = ensure_role(user, {"docente"})
    if response:
        return response

    teacher_classes, class_error = fetch_teacher_classes(user["id"])
    if class_error:
        flash(class_error, "error")
        return redirect(url_for("teacher_dashboard"))

    teacher_class = None
    for tc in teacher_classes:
        if tc["id_clase"] == class_id:
            teacher_class = tc
            break

    if not teacher_class:
        flash("Clase no encontrada.", "error")
        return redirect(url_for("teacher_dashboard"))

    students, students_error = fetch_teacher_class_students(class_id)
    if students_error:
        flash(students_error, "error")
        return redirect(url_for("teacher_dashboard"))

    buffer = BytesIO()
    documento = SimpleDocTemplate(buffer, pagesize=letter)
    estilos = getSampleStyleSheet()

    datos = [["Nombres", "Apellidos", "Usuario", "Correo", "Ecopuntos", "Ecomultas", "Saldo", "% Aciertos"]]
    for s in students:
        datos.append([
            s["nombres"],
            s["apellidos"],
            s["usuario"],
            s["correo"],
            str(s["ecopuntos"]),
            str(s["ecomultas"]),
            str(s["saldo_ambiental"]),
            f"{s['porcentaje_aciertos']}%" if s["clasificaciones_total"] > 0 else "--",
        ])

    tabla = Table(datos, colWidths=[90, 90, 70, 120, 50, 50, 45, 55])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))

    contenido = [
        Paragraph(f"Estudiantes - {teacher_class['nombre']}", estilos["Title"]),
        Spacer(1, 8),
        Paragraph(f"Código: {teacher_class['codigo']}", estilos["Normal"]),
        Spacer(1, 16),
        tabla,
    ]
    documento.build(contenido)
    pdf = buffer.getvalue()
    buffer.close()

    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename={teacher_class['codigo']}_estudiantes.pdf"
    return response


@app.route("/docente/clases", methods=["POST"])
def create_teacher_class_route():
    user, response = require_current_user()
    if response:
        return response

    response = ensure_role(user, {"docente"})
    if response:
        return response

    class_name = request.form.get("nombre_clase", "")
    teacher_class, message = create_teacher_class(user["id"], class_name)
    flash(
        f"Clase creada correctamente. Codigo: {teacher_class['codigo']}"
        if teacher_class
        else message,
        "success" if teacher_class else "error",
    )
    return redirect(url_for("teacher_dashboard"))


@app.route("/clase/<class_code>")
def join_class_by_code(class_code):
    clean_code = re.sub(r"[^A-Za-z0-9]", "", class_code or "").upper()
    if not session.get("user_id"):
        session["pending_class_code"] = clean_code
        flash("Inicia sesion como estudiante para inscribirte a la clase.", "success")
        return redirect(url_for("login"))

    user, response = require_current_user()
    if response:
        return response

    response = ensure_role(user, {"estudiante"})
    if response:
        return response

    teacher_class, message = enroll_student_in_class(user["id"], clean_code)
    flash(message, "success" if teacher_class else "error")
    return redirect(url_for("student_dashboard"))


@app.route("/clase/<class_code>/qr")
def class_qr(class_code):
    teacher_class, error = fetch_class_by_code(class_code)
    if error:
        return Response("Clase no encontrada", status=404)

    try:
        import qrcode

        enrollment_url = url_for("join_class_by_code", class_code=teacher_class["codigo"], _external=True)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=3,
        )
        qr.add_data(enrollment_url)
        qr.make(fit=True)
        image = qr.make_image(fill_color="#1d5a35", back_color="white")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return Response(buffer.getvalue(), mimetype="image/png")
    except Exception:
        return Response("No fue posible generar el QR", status=500)


@app.route("/admin")
def admin_dashboard():
    user, response = require_current_user()
    if response:
        return response

    response = ensure_role(user, {"admin"})
    if response:
        return response

    users, users_error = fetch_users()
    type_counts, counts_error = fetch_user_type_counts()
    options = get_form_options()
    return render_template(
        "admin_dashboard.html",
        user=user,
        users=users,
        type_counts=type_counts,
        db_message=users_error or counts_error,
        **options,
    )


@app.route("/admin/usuarios/<int:user_id>/editar", methods=["POST"])
def admin_edit_user(user_id):
    user, response = require_current_user()
    if response:
        return response

    response = ensure_role(user, {"admin"})
    if response:
        return response

    form_data = {
        "nombres": request.form.get("nombres", "").strip(),
        "apellidos": request.form.get("apellidos", "").strip(),
        "id_tipo_documento": request.form.get("id_tipo_documento", "").strip(),
        "numero_documento": request.form.get("numero_documento", "").strip(),
        "id_tipo_genero": request.form.get("id_tipo_genero", "").strip(),
        "id_tipo_usuario": request.form.get("id_tipo_usuario", "").strip(),
        "correo": request.form.get("correo", "").strip(),
        "telefono": request.form.get("telefono", "").strip(),
    }
    if not all(form_data.values()):
        flash("Completa todos los campos para editar el usuario.", "error")
    else:
        error = admin_update_user(user_id, form_data)
        flash(error or "Usuario actualizado correctamente.", "error" if error else "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/usuarios/<int:user_id>/estado", methods=["POST"])
def admin_toggle_user_status(user_id):
    user, response = require_current_user()
    if response:
        return response

    response = ensure_role(user, {"admin"})
    if response:
        return response

    if user_id == user["id"]:
        flash("No puedes inhabilitar tu propio usuario administrador.", "error")
        return redirect(url_for("admin_dashboard"))

    active = request.form.get("activo") == "1"
    error = set_user_active_status(user_id, active)
    flash(error or ("Usuario habilitado." if active else "Usuario inhabilitado."), "error" if error else "success")
    return redirect(url_for("admin_dashboard"))


# Ruta dedicada para acceder a la interfaz de preguntas a la IA.
# Aqui no se muestra una pagina separada: se reutiliza la home
# y se abre el panel lateral de IA en estado desplegado.
@app.route("/ia")
def ia_page():
    return render_template(
        "index.html",
        color_palette=COLOR_PALETTE,
        font_showcase=FONT_SHOWCASE,
        open_ai_panel=True,
    )


# Endpoint que si ejecuta la consulta a la IA local.
# Recibe la pregunta desde la vista /ia en formato JSON y devuelve
# la respuesta tambien en JSON para mostrarla dinamicamente en pantalla.
@app.route("/ia/chat", methods=["POST"])
def ia_chat():
    payload = request.get_json(silent=True) or {}
    prompt = (payload.get("prompt") or "").strip()

    if not prompt:
        return jsonify({"ok": False, "error": "Escribe una pregunta para consultar la IA."}), 400

    answer, error = ask_local_ai(prompt)
    if error:
        return jsonify({"ok": False, "error": error}), 500

    return jsonify({"ok": True, "answer": answer})


@app.route("/registro", methods=["GET", "POST"])
def register():
    options = get_form_options()
    if request.method == "POST":
        form_data = {
            "nombres": request.form.get("nombres", "").strip(),
            "apellidos": request.form.get("apellidos", "").strip(),
            "id_tipo_documento": request.form.get("id_tipo_documento", "").strip(),
            "numero_documento": request.form.get("numero_documento", "").strip(),
            "id_tipo_genero": request.form.get("id_tipo_genero", "").strip(),
            "correo": request.form.get("correo", "").strip(),
            "telefono": request.form.get("telefono", "").strip(),
            "contrasena": request.form.get("contrasena", ""),
            "foto_rostro_data": request.form.get("foto_rostro_data", ""),
            "terminos": request.form.get("terminos", ""),
        }

        required_values = [
            form_data["nombres"],
            form_data["apellidos"],
            form_data["id_tipo_documento"],
            form_data["numero_documento"],
            form_data["id_tipo_genero"],
            form_data["correo"],
            form_data["telefono"],
            form_data["contrasena"],
        ]

        errors = []

        if not all(required_values):
            errors.append("Completa todos los campos para registrarte.")

        if not re.match(r"^[A-Za-záéíóúÁÉÍÓÚñÑ ]+$", form_data["nombres"]):
            errors.append("El campo nombres solo debe contener letras.")
        if not re.match(r"^[A-Za-záéíóúÁÉÍÓÚñÑ ]+$", form_data["apellidos"]):
            errors.append("El campo apellidos solo debe contener letras.")
        if not re.match(r"^[0-9]+$", form_data["numero_documento"]):
            errors.append("El numero de documento solo debe contener numeros.")
        if not re.match(r"^[0-9]+$", form_data["telefono"]):
            errors.append("El telefono solo debe contener numeros.")
        if len(form_data["contrasena"]) < 8 or len(form_data["contrasena"]) > 12:
            errors.append("La contrasena debe tener entre 8 y 12 caracteres.")
        if not form_data["terminos"]:
            errors.append("Debes aceptar los terminos y condiciones.")
        if options["options_error"]:
            errors.append(options["options_error"])

        has_face = bool(form_data["foto_rostro_data"])
        if not has_face:
            errors.append("Toma al menos una foto de rostro para completar el registro.")

        if errors:
            for error in errors:
                flash(error, "error")
        else:
            generated_username, error = create_user(form_data)
            if error:
                flash(error, "error")
            else:
                flash(
                    f"Usuario registrado correctamente. Tu nombre de usuario es {generated_username}. Ahora inicia sesion con tu correo y contrasena.",
                    "success",
                )
                return redirect(url_for("login"))

    return render_template("auth.html", mode="register", **options)


@app.route("/recuperar-contrasena", methods=["GET", "POST"])
def forgot_password():
    options = get_form_options()
    if request.method == "POST":
        correo = request.form.get("correo", "").strip()
        if not correo:
            flash("Ingresa tu correo para recuperar la contrasena.", "error")
        else:
            user, error = fetch_user_by_email(correo)
            if error:
                flash("Si el correo esta registrado, enviaremos un codigo de recuperacion.", "success")
            else:
                code = make_security_code()
                session["password_reset"] = {
                    "user_id": user["id"],
                    "email": user["correo"],
                    "code_hash": hash_security_code(code),
                    "expires_at": time.time() + SECURITY_CODE_TTL,
                }
                ok, mail_error = send_email_message(
                    user["correo"],
                    f"Codigo de recuperacion Ecovigilante: {code}",
                    f"Tu codigo de recuperacion es: {code}\n\nVence en 10 minutos.",
                )
                if ok:
                    flash("Enviamos un codigo de recuperacion a tu correo.", "success")
                    return redirect(url_for("verify_password_reset"))
                flash(mail_error, "error")

    return render_template("auth.html", mode="forgot_password", **options)


@app.route("/verificar-recuperacion", methods=["GET", "POST"])
def verify_password_reset():
    options = get_form_options()
    recovery = session.get("password_reset")
    if not recovery:
        flash("Solicita primero la recuperacion de contrasena.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        code = request.form.get("codigo", "").strip()
        new_password = request.form.get("contrasena", "")
        confirm_password = request.form.get("confirmar_contrasena", "")

        if code_is_expired(recovery.get("expires_at")):
            session.pop("password_reset", None)
            flash("El codigo vencio. Solicita uno nuevo.", "error")
            return redirect(url_for("forgot_password"))
        if not all([code, new_password, confirm_password]):
            flash("Completa el codigo y la nueva contrasena.", "error")
        elif new_password != confirm_password:
            flash("Las contrasenas no coinciden.", "error")
        elif not verify_security_code(recovery.get("code_hash"), code):
            flash("El codigo ingresado no es valido.", "error")
        else:
            error = update_user_password(recovery["user_id"], new_password)
            if error:
                flash(error, "error")
            else:
                session.pop("password_reset", None)
                flash("Contrasena actualizada correctamente. Ya puedes iniciar sesion.", "success")
                return redirect(url_for("login"))

    return render_template("auth.html", mode="verify_password_reset", **options)


@app.route("/recuperar-con-archivo", methods=["GET", "POST"])
def recover_with_file():
    options = get_form_options()
    if request.method == "POST":
        correo = request.form.get("correo", "").strip()
        new_password = request.form.get("contrasena", "")
        confirm_password = request.form.get("confirmar_contrasena", "")
        recovery_file = request.files.get("archivo_recuperacion")

        if not all([correo, new_password, confirm_password]) or not recovery_file:
            flash("Completa el correo, la nueva contrasena y adjunta tu archivo de recuperacion.", "error")
        elif new_password != confirm_password:
            flash("Las contrasenas no coinciden.", "error")
        else:
            user, error = fetch_user_by_email(correo)
            if error:
                flash("No fue posible validar el archivo de recuperacion.", "error")
            else:
                content = recovery_file.read().decode("utf-8", errors="ignore")
                file_data = parse_recovery_file(content)
                expected_key = build_recovery_file_key(user)
                if (
                    file_data.get("correo", "").lower() != user["correo"].lower()
                    or not secrets.compare_digest(file_data.get("clave", ""), expected_key)
                ):
                    flash("El archivo de recuperacion no corresponde a ese usuario.", "error")
                else:
                    error = update_user_password(user["id"], new_password)
                    if error:
                        flash(error, "error")
                    else:
                        flash("Contrasena actualizada correctamente con tu archivo de recuperacion.", "success")
                        return redirect(url_for("login"))

    return render_template("auth.html", mode="recover_with_file", **options)


@app.route("/archivo-recuperacion")
def recovery_file():
    user, response = require_current_user()
    if response:
        return response

    full_user, error = fetch_user_by_email(user["correo"])
    if error:
        flash("No fue posible generar el archivo de recuperacion.", "error")
        return redirect(url_for(dashboard_endpoint_for_role(user.get("tipo_usuario"))))

    content = build_recovery_file_content(full_user)
    filename = f"ecovigilante-recuperacion-{full_user['usuario']}.txt"
    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/verificacion", methods=["GET", "POST"])
def two_factor_verification():
    options = get_form_options()
    pending_user = session.get("pending_2fa_user")
    two_factor = session.get("two_factor")
    if not pending_user or not two_factor:
        flash("Inicia sesion para recibir el codigo de verificacion.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        code = request.form.get("codigo", "").strip()
        if code_is_expired(two_factor.get("expires_at")):
            session.pop("pending_2fa_user", None)
            session.pop("two_factor", None)
            flash("El codigo vencio. Inicia sesion nuevamente.", "error")
            return redirect(url_for("login"))
        if not verify_security_code(two_factor.get("code_hash"), code):
            flash("El codigo ingresado no es valido.", "error")
        else:
            session.pop("two_factor", None)
            user = session.pop("pending_2fa_user")
            session["user_id"] = user["id"]
            session["username"] = user["usuario"]
            session["display_name"] = f"{user['nombres']} {user['apellidos']}"
            session["email"] = user["correo"]
            session["user_type"] = user.get("tipo_usuario")
            session["user_type_id"] = user.get("id_tipo_usuario")
            flash(f"Bienvenido, {user['nombres']} {user['apellidos']}.", "success")
            pending_class_code = session.pop("pending_class_code", None)
            if pending_class_code:
                return redirect(url_for("join_class_by_code", class_code=pending_class_code))
            return redirect(url_for(dashboard_endpoint_for_role(user.get("tipo_usuario"))))

    return render_template("auth.html", mode="two_factor", **options)


@app.route("/login", methods=["GET", "POST"])
def login():
    options = get_form_options()
    if request.method == "POST":
        correo = request.form.get("correo", "").strip()
        contrasena = request.form.get("contrasena", "")

        if not all([correo, contrasena]):
            flash("Ingresa correo y contrasena para iniciar sesion.", "error")
        else:
            user, message = validate_login(correo, contrasena)
            flash(message, "success" if user else "error")
            if user:
                code = make_security_code()
                session["pending_2fa_user"] = {
                    "id": user["id"],
                    "usuario": user["usuario"],
                    "nombres": user["nombres"],
                    "apellidos": user["apellidos"],
                    "correo": user["correo"],
                    "tipo_usuario": user.get("tipo_usuario"),
                    "id_tipo_usuario": user.get("id_tipo_usuario"),
                }
                session["two_factor"] = {
                    "code_hash": hash_security_code(code),
                    "expires_at": time.time() + SECURITY_CODE_TTL,
                }
                ok, mail_error = send_email_message(
                    user["correo"],
                    f"Codigo de verificacion Ecovigilante: {code}",
                    f"Tu codigo de verificacion es: {code}\n\nVence en 10 minutos.",
                )
                if ok:
                    flash("Enviamos un codigo de verificacion a tu correo.", "success")
                    return redirect(url_for("two_factor_verification"))
                session.pop("pending_2fa_user", None)
                session.pop("two_factor", None)
                flash(mail_error, "error")

    return render_template("auth.html", mode="login", **options)


@app.route("/cerrar-sesion")
def logout():
    session.clear()
    flash("La sesion se cerro correctamente.", "success")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
