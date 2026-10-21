"""Verified IMAP/TLS, optionally bound to a macOS physical interface."""
import os
import socket
import ssl
import sys

from imapclient import IMAPClient, tls

ALLOWED_HOSTS = {'imap.yandex.ru', 'imap.yandex.com', 'imap.ya.ru'}


def direct_socket(host, port, timeout, interface):
    if sys.platform != 'darwin':
        raise RuntimeError('Interface binding in this sample requires macOS.')
    index = socket.if_nametoindex(interface)
    last_error = None
    for family, kind, protocol, _, address in socket.getaddrinfo(
            host, port, socket.AF_INET, socket.SOCK_STREAM):
        sock = socket.socket(family, kind, protocol)
        try:
            sock.settimeout(timeout)
            # IP_BOUND_IF, defined by the macOS SDK in netinet/in.h.
            sock.setsockopt(socket.IPPROTO_IP, 25, index)
            sock.connect(address)
            return sock
        except OSError as exc:
            last_error = exc
            sock.close()
    raise last_error or OSError('No IPv4 endpoint found.')


def create_imap_client():
    host = os.getenv('YANDEX_IMAP_HOST', 'imap.yandex.ru')
    if host not in ALLOWED_HOSTS:
        raise ValueError('Only official Yandex IMAP hostnames are allowed.')
    interface = os.getenv('YANDEX_MAIL_INTERFACE', '').strip()
    context = ssl.create_default_context()
    if not interface:
        return IMAPClient(host, port=993, ssl=True, ssl_context=context, timeout=30)

    class BoundTLS(tls.IMAP4_TLS):
        def _create_socket(self, timeout):
            raw = direct_socket(self.host, self.port,
                                self._timeout if timeout is None else timeout,
                                interface)
            try:
                return self.ssl_context.wrap_socket(raw, server_hostname=self.host)
            except Exception:
                raw.close()
                raise

    class BoundClient(IMAPClient):
        def _create_IMAP4(self):
            if not self.ssl or self.stream:
                raise RuntimeError('Only IMAP/TLS is supported.')
            return BoundTLS(self.host, self.port, self.ssl_context,
                            getattr(self._timeout, 'connect', None))

    return BoundClient(host, port=993, ssl=True, ssl_context=context, timeout=30)
