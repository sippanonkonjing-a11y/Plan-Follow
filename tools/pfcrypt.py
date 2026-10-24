"""Small authenticated stream cipher shared with the Google Apps Script uploader.
Keystream block i = HMAC-SHA256(key, nonce || i as 4-byte big-endian); tag = HMAC-SHA256(key, b'tag' || nonce || ciphertext).
File layout: b'PF1' + nonce(16) + ciphertext + tag(32). Key = SHA-256('plan-follow-inbox:' + password)."""
import hmac, hashlib, os, sys

def key_from(password: str) -> bytes:
    return hashlib.sha256(('plan-follow-inbox:' + password).encode('utf-8')).digest()

def _stream(key, nonce, n):
    out = bytearray(); i = 0
    while len(out) < n:
        out += hmac.new(key, nonce + i.to_bytes(4, 'big'), hashlib.sha256).digest(); i += 1
    return bytes(out[:n])

def encrypt(data: bytes, password: str) -> bytes:
    k = key_from(password); nonce = os.urandom(16)
    ct = bytes(a ^ b for a, b in zip(data, _stream(k, nonce, len(data))))
    return b'PF1' + nonce + ct + hmac.new(k, b'tag' + nonce + ct, hashlib.sha256).digest()

def decrypt(blob: bytes, password: str) -> bytes:
    if blob[:3] != b'PF1': raise ValueError('not a PF1 file')
    k = key_from(password); nonce, ct, tag = blob[3:19], blob[19:-32], blob[-32:]
    if not hmac.compare_digest(tag, hmac.new(k, b'tag' + nonce + ct, hashlib.sha256).digest()):
        raise ValueError('wrong password or damaged file')
    return bytes(a ^ b for a, b in zip(ct, _stream(k, nonce, len(ct))))

if __name__ == '__main__':
    mode, src, dst = sys.argv[1:4]; pw = os.environ['APP_PASSWORD']
    data = open(src, 'rb').read()
    open(dst, 'wb').write(encrypt(data, pw) if mode == 'enc' else decrypt(data, pw))
