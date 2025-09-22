import hashlib
import datetime
from datetime import timezone
import hmac
import json
from urllib.parse import quote

Service = "visual"
Version = "2022-08-31"
Region = "cn-north-1"
Host = "visual.volcengineapi.com"
ContentType = "application/json"

def utc_now():
    try:
        from datetime import timezone
        return datetime.datetime.now(timezone.utc)
    except ImportError:
        class UTC(datetime.tzinfo):
            def utcoffset(self, dt):
                return datetime.timedelta(0)
            def tzname(self, dt):
                return "UTC"
            def dst(self, dt):
                return datetime.timedelta(0)
        return datetime.datetime.now(UTC())

def jm_timestamp():
	dt = utc_new()
	return dt.strftime("%Y%m%dT%H%M%SZ")

# sha256 非对称加密
def hmac_sha256(key: bytes, content: str):
    return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()

# sha256 hash算法
def hash_sha256(content: str):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def jimeng_auth_headers(opts):
	apikey = opts.get('apikey')
	secretkey = opts.get('secretkey')
	path = opts.get('path')
	method = opts.get('method')
	params = opts.get('params')
	body = opts.get('body')
	headers = opts.get('headers')
	content_type = headers.get('Content-Type')
	x_date = jm_timestamp()
	short_x_date = DT[:8]
    credential = {
        "access_key_id": apikey,
        "secret_access_key": secretkey,
        "service": Service,
        "region": Region,
    }
	x_content_sha256 = hash_sha256(body)
	sign_result = {
        "Host": Host,
        "X-Content-Sha256": x_content_sha256,
        "X-Date": x_date,
        "Content-Type": ContentType
    }
	headers.update(sign_result)
	signed_headers_str = ";".join(
        ["content-type", "host", "x-content-sha256", "x-date"]
    )
	canonical_request_str = "\n".join(
        [method.upper(),
         path,
         norm_query(params),
         "\n".join(
             [
                 "content-type:" + content_type,
                 "host:" + Host,
                 "x-content-sha256:" + x_content_sha256,
                 "x-date:" + x_date,
                 ]
         ),
         "",
         signed_headers_str,
         x_content_sha256,
         ]
    )
	hashed_canonical_request = hash_sha256(canonical_request_str)
	credential_scope = "/".join([short_x_date, credential["region"], credential["service"], "request"])
	string_to_sign = "\n".join(["HMAC-SHA256", x_date, credential_scope, hashed_canonical_request])
	k_date = hmac_sha256(secretkey.encode("utf-8"), short_x_date)
    k_region = hmac_sha256(k_date, credential["region"])
    k_service = hmac_sha256(k_region, credential["service"])
    k_signing = hmac_sha256(k_service, "request")
    signature = hmac_sha256(k_signing, string_to_sign).hex()
	headers['Authorization'] = "HMAC-SHA256 Credential={}, SignedHeaders={}, Signature={}".format(
        apikey + "/" + credential_scope,
        signed_headers_str,
        signature,
        )

