import csv
from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = "dev-secret-key"
ALGORITHM = "HS256"

LDAP_CSV_PATH = r"backend\employees.csv"
AUTHZ_CSV_PATH = r"backend\authorized_users.csv"


def authenticate_user(employee_id: str, password: str) -> bool:
    try:
        with open(LDAP_CSV_PATH, mode="r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                if (
                    str(row.get("employee_id")) == str(employee_id)
                    and row.get("password") == password
                ):
                    return True

        return False

    except FileNotFoundError:
        # Optional: log this properly in real systems
        return False


def is_user_authorized(employee_id: str) -> bool:
    try:
        with open(AUTHZ_CSV_PATH, mode="r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                if str(row.get("employee_id")) == str(employee_id):
                    return str(row.get("isEnabled", "0")).strip() == "1"

        return False

    except FileNotFoundError:
        return False


def authenticate_and_authorize_user(employee_id: str, password: str) -> tuple[bool, bool]:
    authenticated = authenticate_user(employee_id, password)
    if not authenticated:
        return False, False

    authorized = is_user_authorized(employee_id)
    return True, authorized


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=8)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
