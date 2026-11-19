"""Exercise the Gmail tunnel against a local TLS server with a launcher's PATH."""

from configparser import ConfigParser
from pathlib import Path
import shlex
import shutil
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
        self.config = ConfigParser()
        self.config.read(CONFIG)
        self.repo = self.config["Repository gmail-remote"]
        self.directory = directory
        self.client_env = {"PATH": "/usr/bin:/bin", "SSL_CERT_FILE": str(cert)}
        self.repo["remoteport"] = str(self.listener.getsockname()[1])

    def connect(self, host):
        self.repo["remotehost"] = host
        client = self.enterContext(subprocess.Popen(
            ["/bin/sh", "-c", self.repo["transporttunnel"]], env=self.client_env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ))
        self.addCleanup(client.kill)
        conn, _ = self.listener.accept()
        self.enterContext(conn)
        conn.settimeout(5)
        return client, conn

    def test_accepts_matching_hostname(self):
        client, conn = self.connect("localhost")
        command = b"Q001 NOOP\r\n"
        reply = b"Q001 OK complete\r\n"
        with self.server.wrap_socket(conn, server_side=True) as tls:
            tls.sendall(GREETING)
            client.stdin.write(command)
            client.stdin.flush()
            with tls.makefile("rb") as stream:
                self.assertEqual(stream.readline(), command)
            tls.sendall(reply)
            tls.unwrap().close()
        output, error = client.communicate(timeout=5)
        self.assertEqual(client.returncode, 0, error)
        self.assertEqual(output, GREETING + reply)

    def assert_certificate_rejected(self, host, reason):
        client, conn = self.connect(host)
        with self.assertRaises(ssl.SSLError):
            self.server.wrap_socket(conn, server_side=True)
        output, error = client.communicate(timeout=5)
        self.assertNotEqual(client.returncode, 0)
        self.assertIn(reason, error)
        self.assertEqual(output, b"")

    def test_rejects_mismatched_hostname(self):
        self.assert_certificate_rejected("127.0.0.1", b"hostname mismatch")

    def test_rejects_untrusted_certificate(self):
        del self.client_env["SSL_CERT_FILE"]
        self.assert_certificate_rejected("localhost", b"self-signed certificate")

    @unittest.skipUnless(ssl.HAS_TLSv1_1, "the local TLS server cannot negotiate TLS 1.1")
    def test_rejects_tls_1_1_even_when_the_system_allows_it(self):
        # Only this loopback server and its test client allow the obsolete protocol.
        self.server.minimum_version = self.server.maximum_version = ssl.TLSVersion.TLSv1_1
        self.server.set_ciphers("DEFAULT:@SECLEVEL=0")
        policy = self.directory / "client.cnf"
        policy.write_text(
            "openssl_conf=init\n[init]\nssl_conf=ssl\n[ssl]\nsystem_default=legacy\n"
            "[legacy]\nMinProtocol=TLSv1.1\nCipherString=DEFAULT:@SECLEVEL=0\n"
        )
        self.client_env["OPENSSL_CONF"] = str(policy)
        client, conn = self.connect("localhost")
        with self.assertRaises(ssl.SSLError):
            self.server.wrap_socket(conn, server_side=True)
        output, error = client.communicate(timeout=5)
        self.assertNotEqual(client.returncode, 0, error)
        self.assertEqual(output, b"")

        # Prove the fixture works when the client explicitly permits TLS 1.1.
        raw = self.config.get("Repository gmail-remote", "transporttunnel", raw=True)
        self.repo["transporttunnel"] = raw + " -min_protocol TLSv1.1"
        client, conn = self.connect("localhost")
        with self.server.wrap_socket(conn, server_side=True) as tls:
            self.assertEqual(tls.version(), "TLSv1.1")
            tls.sendall(GREETING)
            tls.unwrap().close()
        output, error = client.communicate(timeout=5)
        self.assertEqual(client.returncode, 0, error)
        self.assertEqual(output, GREETING)

    def test_offlineimap_lists_folders_after_login(self):
        executable = shutil.which("offlineimap")
        self.assertIsNotNone(executable, "Install OfflineIMAP to run the Gmail login test")
        self.repo["remotehost"] = "localhost"
        self.repo["remoteuser"] = "fixture"
        self.config["general"]["pythonfile"] = str(CONFIG.with_name("offlineimap.py"))
        (self.directory / "Mail" / "gmail").mkdir(parents=True)
        ini = self.directory / "offlineimaprc"
        with ini.open("w") as stream:
            self.config.write(stream)
        client = self.enterContext(subprocess.Popen(
            [executable, "-c", str(ini), "--info"],
            env=self.client_env | {"HOME": str(self.directory), "GMAIL_APP_SPECIFIC_PASSWORD": "test"},
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ))
        self.addCleanup(client.kill)
        conn, _ = self.listener.accept()
        with conn:
            conn.settimeout(5)
            with self.server.wrap_socket(conn, server_side=True) as tls, tls.makefile("rb") as stream:
                tls.sendall(GREETING)
                logged_in = False
                for line in stream:
                    tag, command, *args = line.split()
                    if command == b"CAPABILITY":
                        tls.sendall(b"* CAPABILITY IMAP4rev1\r\n")
                    elif command == b"LOGIN":
                        self.assertEqual([arg.strip(b'"') for arg in args], [b"fixture", b"test"])
                        logged_in = True
                    elif command == b"LIST":
                        self.assertTrue(logged_in)
                        tls.sendall(b'* LIST () "/" "INBOX"\r\n')
                    elif command == b"LOGOUT":
                        tls.sendall(b"* BYE closing\r\n" + tag + b" OK logout\r\n")
                        break
                    else:
                        self.assertEqual(command, b"NOOP")
                    tls.sendall(tag + b" OK complete\r\n")
        output, error = client.communicate(timeout=10)
        self.assertEqual(client.returncode, 0, error)
        self.assertIn(b"INBOX", output + error)


class OfflineimapTlsPolicyTests(unittest.TestCase):
    def test_requires_at_least_tls_1_2_even_with_older_system_defaults(self):
        config = ConfigParser()
        config.read(CONFIG)
        tunnel = config["Repository gmail-remote"]["transporttunnel"]
        args = shlex.split(tunnel.replace("\\\n", ""))
        self.assertIn("-min_protocol", args)
        self.assertIn(args[args.index("-min_protocol") + 1], ("TLSv1.2", "TLSv1.3"))


if __name__ == "__main__":
    unittest.main()
