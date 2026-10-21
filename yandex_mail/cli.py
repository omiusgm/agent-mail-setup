"""Read-only CLI for the same functions exposed by MCP."""
import argparse
import json
import sys

import server
from network import create_imap_client


def probe():
    client = create_imap_client()
    try:
        return {'tls_verified': True, 'authenticated': False}
    finally:
        client.logout()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['probe', 'connection_status', 'list_folders',
                        'search_emails', 'read_email', 'download_attachment'])
    parser.add_argument('--args', default='{}', help='JSON parameters; never credentials')
    args = parser.parse_args()
    if args.action == 'probe':
        result = probe()
    else:
        result = getattr(server, args.action)(**json.loads(args.args))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'ok': False, 'error_type': type(exc).__name__,
                          'next_step': 'See docs/troubleshooting.md'}))
        sys.exit(1)
