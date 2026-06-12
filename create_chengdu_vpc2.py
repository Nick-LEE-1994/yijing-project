# -*- coding: utf-8 -*-
"""创建安全组（VPC 和子网已创建：vpc-gunz4h4k, subnet-nrlw5qgd）"""
import hashlib
import hmac
import json
import time
import urllib.request

SECRET_ID = "${TENCENT_SECRET_ID}"
SECRET_KEY = "${TENCENT_SECRET_KEY}"
REGION = "ap-chengdu"

def call_api(service, host, version, action, body_dict):
    payload = json.dumps(body_dict).encode("utf-8")
    timestamp = int(time.time())
    date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))

    content_type = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{content_type}\nhost:{host}\nx-tc-action:{action.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload).hexdigest()
    canonical_request = f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"

    algorithm = "TC3-HMAC-SHA256"
    credential_scope = f"{date}/{service}/tc3_request"
    string_to_sign = f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"

    def _h(key, msg):
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()
    s_date = _h(f"TC3{SECRET_KEY}".encode("utf-8"), date)
    s_svc = _h(s_date, service)
    s_sign = _h(s_svc, "tc3_request")
    signature = hmac.new(s_sign, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = f"{algorithm} Credential={SECRET_ID}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"

    req = urllib.request.Request(
        f"https://{host}", data=payload,
        headers={
            "Authorization": authorization, "Content-Type": content_type,
            "Host": host, "X-TC-Action": action, "X-TC-Version": version,
            "X-TC-Region": REGION, "X-TC-Timestamp": str(timestamp),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

VPC_HOST = "vpc.tencentcloudapi.com"
VPC_VER = "2017-03-12"

# 创建安全组
print("创建安全组...")
resp = call_api("vpc", VPC_HOST, VPC_VER, "CreateSecurityGroup", {
    "GroupName": "yijing-scf-sg",
    "GroupDescription": "SCF access TDSQL-C",
})
if "Error" in resp.get("Response", {}):
    print(f"创建失败: {resp['Response']['Error']}")
else:
    sg_id = resp["Response"]["SecurityGroup"]["SecurityGroupId"]
    print(f"安全组 ID: {sg_id}")

    # 添加规则
    print("添加安全组规则...")
    ingress_rules = [
        {"Protocol": "ALL", "CidrBlock": "10.0.0.0/16", "Port": "ALL", "Action": "ACCEPT", "Description": "Allow VPC internal"},
        {"Protocol": "TCP", "CidrBlock": "0.0.0.0/0", "Port": "3306", "Action": "ACCEPT", "Description": "Allow MySQL 3306"},
    ]
    egress_rules = [
        {"Protocol": "ALL", "CidrBlock": "0.0.0.0/0", "Port": "ALL", "Action": "ACCEPT", "Description": "Allow all outbound"},
    ]

    try:
        resp = call_api("vpc", VPC_HOST, VPC_VER, "CreateSecurityGroupPolicies", {
            "SecurityGroupId": sg_id,
            "SecurityGroupPolicySet": {"Ingress": ingress_rules, "Egress": egress_rules},
        })
        if "Error" in resp.get("Response", {}):
            print(f"添加规则失败: {resp['Response']['Error']}")
        else:
            print("安全组规则添加成功！")
    except Exception as e:
        print(f"添加规则异常: {e}")

    print(f"\n汇总：")
    print(f"  VPC ID:     vpc-gunz4h4k")
    print(f"  子网 ID:    subnet-nrlw5qgd")
    print(f"  安全组 ID:  {sg_id}")
