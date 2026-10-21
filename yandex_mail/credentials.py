"""One local account; app password stored only in macOS Keychain."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / '.local'
ACCOUNT_FILE = STATE_DIR / 'account.json'
SERVICE = 'agent-mail-setup-yandex'


def vault():
    if sys.platform != 'darwin':
        raise RuntimeError('This sample requires macOS Keychain; no file fallback is enabled.')
    from keyring.backends.macOS import Keyring
    return Keyring()


def save_account(login, password):
    if '@' not in login or any(c.isspace() for c in login):
        raise ValueError('Enter a full email address.')
    if STATE_DIR.is_symlink():
        raise ValueError('The local state directory must not be a symlink.')
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    STATE_DIR.chmod(0o700)
    vault().set_password(SERVICE, login, password)
    fd, name = tempfile.mkstemp(prefix='account-', dir=STATE_DIR)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump({'email': login}, stream)
        os.replace(name, ACCOUNT_FILE)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def account():
    if not ACCOUNT_FILE.is_file():
        raise ValueError('Run setup_account.py to connect your account.')
    login = json.loads(ACCOUNT_FILE.read_text())['email']
    password = vault().get_password(SERVICE, login)
    if not password:
        raise ValueError('App password is missing from macOS Keychain; run setup again.')
    return login, password
