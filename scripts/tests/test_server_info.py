import sys
from pathlib import Path

from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.main import server_info


def make_request(*, host, scheme='http', forwarded_proto=None, forwarded_host=None, server_port=8000):
    headers = [(b'host', host.encode('ascii'))]
    if forwarded_proto:
        headers.append((b'x-forwarded-proto', forwarded_proto.encode('ascii')))
    if forwarded_host:
        headers.append((b'x-forwarded-host', forwarded_host.encode('ascii')))
    return Request({
        'type': 'http',
        'http_version': '1.1',
        'method': 'GET',
        'scheme': scheme,
        'path': '/server-info',
        'raw_path': b'/server-info',
        'query_string': b'',
        'headers': headers,
        'server': ('0.0.0.0', server_port),
        'client': ('127.0.0.1', 50000),
    })


def test_server_info_does_not_append_internal_port_to_domain_host():
    info = server_info(make_request(
        host='redline.example.com',
        forwarded_proto='https',
    ))

    assert info == {
        'base_url': 'https://redline.example.com',
        'lan_ip': 'redline.example.com',
        'port': None,
    }


def test_server_info_keeps_explicit_domain_port():
    info = server_info(make_request(
        host='redline.example:8443',
        forwarded_proto='https',
    ))

    assert info['base_url'] == 'https://redline.example:8443'
    assert info['port'] == 8443


def test_server_info_appends_listener_port_to_ipv4_address():
    info = server_info(make_request(host='192.168.10.192'))

    assert info == {
        'base_url': 'http://192.168.10.192:8000',
        'lan_ip': '192.168.10.192',
        'port': 8000,
    }


def test_server_info_formats_ipv6_address_with_brackets():
    info = server_info(make_request(host='[2001:db8::10]'))

    assert info == {
        'base_url': 'http://[2001:db8::10]:8000',
        'lan_ip': '2001:db8::10',
        'port': 8000,
    }
