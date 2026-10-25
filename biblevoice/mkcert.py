"""Makes a self-signed HTTPS certificate for the church LAN (phones only allow the microphone over HTTPS). Re-makes it if the PC's IP changes."""
import datetime, ipaddress, os, socket


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try: s.connect(("10.255.255.255", 1)); return s.getsockname()[0]
    except OSError: return "127.0.0.1"
    finally: s.close()


def make(ip):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(65537, 2048); name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "BibleVoice")]); now = datetime.datetime.now(datetime.timezone.utc)
    san = x509.SubjectAlternativeName([x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1")), x509.IPAddress(ipaddress.ip_address(ip))])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=825)).add_extension(san, False).sign(key, hashes.SHA256()))
    open("key.pem", "wb").write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    open("cert.pem", "wb").write(cert.public_bytes(serialization.Encoding.PEM)); open("cert.ip", "w").write(ip)


if __name__ == "__main__":
    ip = lan_ip()
    if not (os.path.exists("cert.pem") and os.path.exists("cert.ip") and open("cert.ip").read() == ip): make(ip)
    print(f"\n  Members open:  https://{ip}:8443\n  Projector:     https://{ip}:8443/screen   (double-click for full screen)\n  (phones show a one-time certificate warning: choose Advanced > Continue)\n")
