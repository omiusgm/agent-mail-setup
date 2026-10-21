"""Interactive setup: password never belongs in shell arguments or chat."""
import getpass
import sys

from credentials import save_account
from network import create_imap_client


def configure(login, password):
    if '@' not in login or any(c.isspace() for c in login):
        raise ValueError('Enter a full email address.')
    if not password:
        raise ValueError('App password is empty.')
    client = create_imap_client()
    try:
        client.login(login, password)
        count = len(client.list_folders())
    finally:
        try:
            client.logout()
        except Exception:
            pass
    save_account(login, password)
    return count


def main():
    print('Яндекс Почта: IMAP/TLS и Связка ключей macOS')
    print('Включите IMAP и создайте пароль приложения типа «Почта».')
    print('https://id.yandex.ru/security/app-passwords')
    print('Основной пароль аккаунта не нужен. Ввод пароля скрыт.\n')
    login = input('Полный адрес почты: ').strip()
    password = ''.join(getpass.getpass('Пароль приложения «Почта»: ').split())
    count = configure(login, password)
    print(f'Подключено. Доступно папок: {count}. Пароль сохранён в Связке ключей.')


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print('\nНастройка отменена.')
        sys.exit(1)
    except Exception:
        print('\nНе удалось подключиться. Проверьте сеть, IMAP и пароль приложения.')
        print('Секреты и ответы сервера не выводятся. См. docs/troubleshooting.md.')
        sys.exit(1)
