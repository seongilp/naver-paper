import requests
import uuid
import re
import rsa
import lzstring
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def naver_style_join(elements):
    """Join elements in Naver's specific format."""
    return "".join([chr(len(s)) + s for s in elements])


def encrypt(key_str, user_id, user_password):
    """Encrypt user credentials using RSA encryption."""
    session_key, key_name, e_str, n_str = key_str.split(",")
    e, n = int(e_str, 16), int(n_str, 16)

    message = naver_style_join([session_key, user_id, user_password]).encode()
    pubkey = rsa.PublicKey(e, n)
    encrypted = rsa.encrypt(message, pubkey)

    return key_name, encrypted.hex()


def get_encryption_key():
    """Retrieve the encryption key from Naver."""
    try:
        response = requests.get("https://nid.naver.com/login/ext/keys.nhn")
        response.raise_for_status()
        return response.content.decode("utf-8")
    except requests.RequestException as e:
        raise ConnectionError("Failed to retrieve encryption key.") from e


def encrypt_account(user_id, user_password):
    """Encrypt user account credentials."""
    key_str = get_encryption_key()
    return encrypt(key_str, user_id, user_password)


def session(user_id, user_password):
    """Create and return a Naver session."""
    try:
        encrypted_name, encrypted_password = encrypt_account(user_id, user_password)
        session = requests.Session()
        retries = Retry(
            total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504]
        )
        session.mount("https://", HTTPAdapter(max_retries=retries))

        request_headers = {"User-agent": "Mozilla/5.0"}
        bvsd_uuid = uuid.uuid4()
        encData = (
            '{"a":"%s-4","b":"1.3.4","d":[{"i":"id","b":{"a":["0,%s"]},"d":"%s","e":false,"f":false},{"i":"%s","e":true,"f":false}],"h":"1f","i":{"a":"Mozilla/5.0"}}'
            % (bvsd_uuid, user_id, user_id, user_password)
        )
        bvsd = '{"uuid":"%s","encData":"%s"}' % (
            bvsd_uuid,
            lzstring.LZString.compressToEncodedURIComponent(encData),
        )

        response = session.post(
            "https://nid.naver.com/nidlogin.login",
            data={
                "svctype": "0",
                "enctp": "1",
                "encnm": encrypted_name,
                "enc_url": "http0X0.0000000000001P-10220.0000000.000000www.naver.com",
                "url": "www.naver.com",
                "smart_level": "1",
                "encpw": encrypted_password,
                "bvsd": bvsd,
            },
            headers=request_headers,
        )

        finalize_url = re.search(
            r'location\.replace\("([^"]+)"\)', response.content.decode("utf-8")
        ).group(1)
        session.get(finalize_url)
        return session

    except Exception as e:
        raise ConnectionError("Failed to create Naver session.") from e

