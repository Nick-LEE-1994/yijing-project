"""获取 SCF 函数 URL - 尝试多种方式"""
import json, hashlib, hmac, time, requests

SECRET_ID = "${TENCENT_SECRET_ID}"
SECRET_KEY = "${TENCENT_SECRET_KEY}"
REGION = "ap-chengdu"
HOST = "scf.tencentcloudapi.com"

def tc3_request(service, host, action, version, payload):
    timestamp = int(time.time())
    date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))
    credential_scope = f"{date}/{service}/tc3_request"
    payload_str = json.dumps(payload, ensure_ascii=False)

    def sha256(s):
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    canonical_headers = f"content-type:application/json\nhost:{host}\nx-tc-action:{action.lower()}"
    signed_headers = "content-type;host;x-tc-action"
    canonical_request = f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{sha256(payload_str)}"
    string_to_sign = f"TC3-HMAC-SHA256\n{timestamp}\n{credential_scope}\n{sha256(canonical_request)}"

    def hmac_sha256(key, msg):
        if isinstance(key, str):
            key = key.encode("utf-8")
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_date = hmac_sha256(SECRET_KEY, date)
    secret_service = hmac_sha256(secret_date, service)
    secret_signing = hmac_sha256(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = f"TC3-HMAC-SHA256 Credential={SECRET_ID}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"

    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json",
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Version": version,
        "X-TC-Region": REGION,
        "X-TC-Timestamp": str(timestamp),
    }

    resp = requests.post(f"https://{host}", data=payload_str.encode("utf-8"), headers=headers, timeout=30)
    return resp.json()

# Try GetFunction with more detail
print("=== GetFunction full response ===")
result = tc3_request("scf", HOST, "GetFunction", "2018-04-16", {"FunctionName": "yijing-divine"})
if "Response" in result:
    print(json.dumps(result["Response"], indent=2, ensure_ascii=False))
