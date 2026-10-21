"""Offline invariants: no login, genuine messages, or secrets required."""
import json
import stat
import sys
import tempfile
import unittest
from contextlib import contextmanager
from email import policy
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'yandex_mail'))
import credentials
import server
import setup_account


def message():
    msg = EmailMessage()
    msg['From'] = 'sender@example.org'
    msg['To'] = 'recipient@example.org'
    msg['Subject'] = 'Проверка'
    msg.set_content('Synthetic test message only.')
    msg.add_attachment(b'test data', maintype='application', subtype='octet-stream',
                       filename='../../пример.bin')
    return msg


class MailTests(unittest.TestCase):
    def test_uidvalidity_change_stops_before_fetch(self):
        client = Mock()
        client.select_folder.return_value = {b'UIDVALIDITY': 8}
        with self.assertRaises(ValueError):
            server.message_bytes(client, 'INBOX', '7:12')
        client.fetch.assert_not_called()
        client.select_folder.assert_called_once_with('INBOX', readonly=True)

    def test_invalid_reference_never_selects_mailbox(self):
        client = Mock()
        for reference in ['1', '1:2,3', '0:1', '1:-1', '1:1\r\nSTORE']:
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                server.select_message(client, 'INBOX', reference)
        client.select_folder.assert_not_called()

    def test_oversized_message_is_not_downloaded(self):
        client = Mock()
        client.select_folder.return_value = {b'UIDVALIDITY': 7}
        client.fetch.return_value = {12: {b'RFC822.SIZE': server.MAX_MESSAGE_BYTES + 1}}
        with self.assertRaises(ValueError):
            server.message_bytes(client, 'INBOX', '7:12')
        client.fetch.assert_called_once_with([12], ['RFC822.SIZE'])

    def test_message_reads_use_peek_and_readonly(self):
        raw = message().as_bytes(policy=policy.SMTP)
        client = Mock()
        client.select_folder.return_value = {b'UIDVALIDITY': 7}
        client.fetch.side_effect = [{12: {b'RFC822.SIZE': len(raw)}},
                                   {12: {b'BODY[]': raw}}]
        parsed = server.message_bytes(client, 'INBOX', '7:12')
        self.assertEqual(str(parsed['Subject']), 'Проверка')
        self.assertEqual(client.fetch.call_args_list[-1].args, ([12], ['BODY.PEEK[]']))
        client.select_folder.assert_called_once_with('INBOX', readonly=True)
        client.add_flags.assert_not_called()

    def test_search_is_paginated_newest_first_without_marking_read(self):
        client = Mock()
        client.select_folder.return_value = {b'UIDVALIDITY': 7}
        client.search.return_value = [1, 2, 3]
        client.fetch.return_value = {2: {b'BODY[HEADER.FIELDS (SUBJECT FROM TO DATE)]':
                                       b'Subject: sample\r\n', b'FLAGS': ()}}
        @contextmanager
        def connection():
            yield client
        with patch.object(server, 'connection', connection):
            result = server.search_emails(subject='a "quoted" value', limit=1, offset=1)
        self.assertEqual(result['messages'][0]['message_id'], '7:2')
        self.assertEqual(result['next_offset'], 2)
        self.assertTrue(result['messages'][0]['unread'])
        client.search.assert_called_once_with(['SUBJECT', 'a "quoted" value'], charset='UTF-8')
        client.select_folder.assert_called_once_with('INBOX', readonly=True)
        client.add_flags.assert_not_called()

    def test_invalid_cli_bounds_fail_before_connection(self):
        with patch.object(server, 'connection') as connect:
            with self.assertRaises(ValueError):
                server.search_emails(limit=0)
            with self.assertRaises(ValueError):
                server.read_email('INBOX', '7:1', max_body_chars=1)
            with self.assertRaises(ValueError):
                server.download_attachment('INBOX', '7:1', -1)
            connect.assert_not_called()

    def test_filename_stays_one_component_and_fits_unicode(self):
        self.assertEqual(server.safe_filename('..\\..\\file.bin'), 'file.bin')
        self.assertEqual(server.safe_filename('../../file.bin'), 'file.bin')
        self.assertLessEqual(len(server.safe_filename('я' * 300).encode()), 160)
        self.assertNotIn('\n', server.safe_filename('a\nb.txt'))
        for filename in ['', '..', '/']:
            with self.assertRaises(ValueError):
                server.safe_filename(filename)

    def test_attachment_never_overwrites_existing_file(self):
        @contextmanager
        def connection():
            yield Mock()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'downloads'
            with patch.object(server, 'DOWNLOADS', target), \
                 patch.object(server, 'connection', connection), \
                 patch.object(server, 'message_bytes', return_value=message()):
                result = server.download_attachment('INBOX', '7:12', 0)
                path = Path(result['path'])
                self.assertEqual(path.parent, target)
                self.assertEqual(path.read_bytes(), b'test data')
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                with self.assertRaises(FileExistsError):
                    server.download_attachment('INBOX', '7:12', 0)
                self.assertEqual(path.read_bytes(), b'test data')

    def test_failed_login_does_not_store_password(self):
        client = Mock()
        client.login.side_effect = RuntimeError('fake failure')
        with patch.object(setup_account, 'create_imap_client', return_value=client), \
             patch.object(setup_account, 'save_account') as save:
            with self.assertRaises(RuntimeError):
                setup_account.configure('user@example.org', 'synthetic-value')
            save.assert_not_called()
        client.logout.assert_called_once()

    def test_account_file_contains_only_address(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / '.local'
            account = state / 'account.json'
            with patch.object(credentials, 'STATE_DIR', state), \
                 patch.object(credentials, 'ACCOUNT_FILE', account), \
                 patch.object(credentials, 'vault', return_value=Mock()):
                credentials.save_account('user@example.org', 'synthetic-value')
            self.assertEqual(json.loads(account.read_text()), {'email': 'user@example.org'})
            self.assertEqual(stat.S_IMODE(account.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o700)


if __name__ == '__main__':
    unittest.main()
