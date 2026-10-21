import os
import socket
import ssl
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'yandex_mail'))
import network


class NetworkTests(unittest.TestCase):
    def test_default_transport_validates_certificate_and_hostname(self):
        with patch.dict(os.environ, {'YANDEX_MAIL_INTERFACE': '',
                                     'YANDEX_IMAP_HOST': 'imap.yandex.ru'}), \
             patch.object(network, 'IMAPClient') as client:
            network.create_imap_client()
        context = client.call_args.kwargs['ssl_context']
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_arbitrary_credential_destination_is_rejected(self):
        with patch.dict(os.environ, {'YANDEX_IMAP_HOST': 'untrusted.example.org'}), \
             patch.object(network, 'IMAPClient') as client:
            with self.assertRaises(ValueError):
                network.create_imap_client()
            client.assert_not_called()

    def test_bound_socket_sets_interface_before_connect(self):
        sock = Mock()
        events = []
        sock.setsockopt.side_effect = lambda *args: events.append('bind')
        sock.connect.side_effect = lambda *args: events.append('connect')
        with patch.object(network.sys, 'platform', 'darwin'), \
             patch.object(socket, 'if_nametoindex', return_value=4), \
             patch.object(socket, 'getaddrinfo', return_value=[
                 (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.0.2.10', 993))]), \
             patch.object(socket, 'socket', return_value=sock):
            result = network.direct_socket('imap.yandex.ru', 993, 5, 'en0')
        self.assertIs(result, sock)
        sock.setsockopt.assert_called_once_with(socket.IPPROTO_IP, 25, 4)
        self.assertEqual(events, ['bind', 'connect'])

    def test_failed_binding_does_not_fall_back_to_vpn(self):
        sock = Mock()
        sock.setsockopt.side_effect = OSError('synthetic failure')
        with patch.object(network.sys, 'platform', 'darwin'), \
             patch.object(socket, 'if_nametoindex', return_value=4), \
             patch.object(socket, 'getaddrinfo', return_value=[
                 (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.0.2.10', 993))]), \
             patch.object(socket, 'socket', return_value=sock), \
             patch.object(socket, 'create_connection') as default_route:
            with self.assertRaises(OSError):
                network.direct_socket('imap.yandex.ru', 993, 5, 'en0')
        sock.connect.assert_not_called()
        sock.close.assert_called_once()
        default_route.assert_not_called()


if __name__ == '__main__':
    unittest.main()
