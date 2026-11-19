"""Exercise the Gmail tunnel against a local TLS server with a launcher's PATH."""

from configparser import ConfigParser
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile
import unittest


CONFIG = Path(__file__).resolve().parents[1] / "files" / "offlineimaprc.ini"
GREETING = b"* OK test server\r\n"


class OfflineimapConfigTests(unittest.TestCase):
    def setUp(self):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        cert, key = directory / "cert.pem", directory / "key.pem"
        request = directory / "request.cnf"
        request.write_text(
            "[req]\ndistinguished_name=dn\nx509_extensions=ext\nprompt=no\n"
            "[dn]\nCN=localhost\n[ext]\nsubjectAltName=DNS:localhost\n"
        )
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-days", "1", "-config", str(request), "-keyout", str(key), "-out", str(cert)],
            check=True, capture_output=True, timeout=15,
        )
        self.server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.server.load_cert_chain(cert, key)
        self.listener = self.enterContext(socket.create_server(("127.0.0.1", 0)))
        self.listener.settimeout(5)
        config = ConfigParser()
        config.read(CONFIG)
        self.repo = config["Repository gmail-remote"]
        self.repo["sslcacertfile"] = str(cert)
        self.repo["remoteport"] = str(self.listener.getsockname()[1])

    def connect(self, host):
        self.repo["remotehost"] = host
        client = self.enterContext(subprocess.Popen(
            ["/bin/sh", "-c", self.repo["transporttunnel"]], env={"PATH": "/usr/bin:/bin"},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ))
        self.addCleanup(client.kill)
        conn, _ = self.listener.accept()
        self.enterContext(conn)
        conn.settimeout(5)
        return client, conn

    def test_accepts_matching_hostname(self):
        client, conn = self.connect("localhost")
        with self.server.wrap_socket(conn, server_side=True) as tls:
            tls.sendall(GREETING)
            tls.unwrap().close()
        output, error = client.communicate(timeout=5)
        self.assertEqual(client.returncode, 0, error)
        self.assertEqual(output, GREETING)

    def test_rejects_mismatched_hostname(self):
        client, conn = self.connect("127.0.0.1")
        with self.assertRaises(ssl.SSLError):
            self.server.wrap_socket(conn, server_side=True)
        output, error = client.communicate(timeout=5)
        self.assertNotEqual(client.returncode, 0)
        self.assertIn(b"hostname mismatch", error)
        self.assertEqual(output, b"")


if __name__ == "__main__":
    unittest.main()
