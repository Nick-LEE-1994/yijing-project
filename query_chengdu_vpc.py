# -*- coding: utf-8 -*-
"""通过 cynosdb API 查询 TDSQL-C 实例网络详情"""
import hashlib
import hmac
import json
import time
import urllib.request

SECRET_ID = "${TENCENT_SECRET_ID}"
SECRET_KEY = "${TENCENT_SECRET_KEY}"

def call_api(service, host, version, action, region, body_dict):
    payload = json.dumps(body_dict).encode("utf-8")
    timestamp = int(time.time())
    date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))

    http_request_method = "POST"
    canonical_uri = "/"
    canonical_querystring = ""
    content_type = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{content_type}\nhost:{host}\nx-tc-action:{action.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload).hexdigest()
    canonical_request = f"{http_request_method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"

    algorithm = "TC3-HMAC-SHA256"
    credential_scope = f"{date}/{service}/tc3_request"
    hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical_request}"

    def _hmac_sha256(key, msg):
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_date = _hmac_sha256(f"TC3{SECRET_KEY}".encode("utf-8"), date)
    secret_service = _hmac_sha256(secret_date, service)
    secret_signing = _hmac_sha256(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = f"{algorithm} Credential={SECRET_ID}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"

    url = f"https://{host}"
    req = urllib.request.Request(
        url, data=payload,
        headers={
            "Authorization": authorization,
            "Content-Type": content_type,
            "Host": host,
            "X-TC-Action": action,
            "X-TC-Version": version,
            "X-TC-Region": region,
            "X-TC-Timestamp": str(timestamp),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


# 1. 查询 TDSQL-C 实例列表
print("=" * 60)
print("查询 TDSQL-C 实例 (cynosdb)")
print("=" * 60)
try:
    resp = call_api("cynosdb", "cynosdb.tencentcloudapi.com", "2019-01-07", "DescribeClusters", "ap-chengdu", {"Limit": "100"})
    print(json.dumps(resp, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")

# 2. 查询实例详情（通过已知实例ID）
print("\n" + "=" * 60)
print("查询实例详情 cynosdbmysql-gu4chj7u")
print("=" * 60)
try:
    resp = call_api("cynosdb", "cynosdb.tencentcloudapi.com", "2019-01-07", "DescribeClusterDetail", "ap-chengdu", {
        "ClusterId": "cynosdbmysql-gu4chj7u"
    })
    print(json.dumps(resp, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")
