"""Shared application branding, supplied once when an executable is built."""

try:
    from core._build_identity import APP_NAME, CONTACT_ID
except ModuleNotFoundError as exc:
    if exc.name != "core._build_identity":
        raise
    APP_NAME = "Desktop"
    CONTACT_ID = "41c322a1-b328-495b-a004-5ccd3e45eae8"

APP_INSTANCE_KEY = f"{APP_NAME}.SingleInstance"
APP_ICON_PATH = "assets/app.png"
