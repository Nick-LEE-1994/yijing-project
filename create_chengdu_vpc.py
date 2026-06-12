# -*- coding: utf-8 -*-
"""在成都创建 VPC + 子网 + 安全组（SCF 访问 TDSQL-C 用）"""
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

# 1. 创建 VPC
print("=" * 60)
print("第1步：创建 VPC")
print("=" * 60)
vpc_cidr = "10.0.0.0/16"
resp = call_api("vpc", VPC_HOST, VPC_VER, "CreateVpc", {
    "VpcName": "yijing-scf-vpc",
    "CidrBlock": vpc_cidr,
})
print(json.dumps(resp, indent=2, ensure_ascii=False))
vpc_id = resp["Response"]["Vpc"]["VpcId"]
print(f"\n✓ VPC 创建成功: {vpc_id}")

# 2. 创建子网（成都一区，与 TDSQL-C 同可用区）
print("\n" + "=" * 60)
print("第2步：创建子网")
print("=" * 60)
subnet_cidr = "10.0.1.0/24"
zone = "ap-chengdu-1"
resp = call_api("vpc", VPC_HOST, VPC_VER, "CreateSubnet", {
    "VpcId": vpc_id,
    "SubnetName": "yijing-scf-subnet",
    "CidrBlock": subnet_cidr,
    "Zone": zone,
})
print(json.dumps(resp, indent=2, ensure_ascii=False))
subnet_id = resp["Response"]["Subnet"]["SubnetId"]
print(f"\n✓ 子网创建成功: {subnet_id}")

# 3. 创建安全组（放通 VPC 内网 + 3306 端口）
print("\n" + "=" * 60)
print("第3步：创建安全组")
print("=" * 60)
resp = call_api("vpc", VPC_HOST, VPC_VER, "CreateSecurityGroup", {
    "GroupName": "yijing-scf-sg",
    "GroupDescription": "SCF access TDSQL-C",
})
print(json.dumps(resp, indent=2, ensure_ascii=False))
sg_id = resp["Response"]["SecurityGroup"]["SecurityGroupId"]
print(f"\n✓ 安全组创建成功: {sg_id}")

# 4. 添加安全组规则：允许 VPC 内网全部流量 + 允许所有 IP 访问 3306
print("\n" + "=" * 60)
print("第4步：添加安全组入站规则")
print("=" * 60)

rules = [
    # 允许 VPC 内网 (10.0.0.0/16) 所有端口
    {
        "SecurityGroupId": sg_id,
        "Direction": "ingress",
        "Protocol": "ALL",
        "CidrBlock": "10.0.0.0/16",
        "Port": "ALL",
        "Action": "ACCEPT",
        "Description": "Allow VPC internal",
    },
    # 允许所有 IP 访问 3306（MySQL）
    {
        "SecurityGroupId": sg_id,
        "Direction": "ingress",
        "Protocol": "TCP",
        "CidrBlock": "0.0.0.0/0",
        "Port": "3306",
        "Action": "ACCEPT",
        "Description": "Allow MySQL 3306",
    },
    # 允许所有出站
    {
        "SecurityGroupId": sg_id,
        "Direction": "egress",
        "Protocol": "ALL",
        "CidrBlock": "0.0.0.0/0",
        "Port": "ALL",
        "Action": "ACCEPT",
        "Description": "Allow all outbound",
    },
]

for i, rule in enumerate(rules):
    try:
        resp = call_api("vpc", VPC_HOST, VPC_VER, "CreateSecurityGroupPoliciesWithPreset", {
            "SecurityGroupId": sg_id,
            "SecurityGroupPolicySet": {"Ingress": [rule]} if rule["Direction"] == "ingress" else {},
        })
        print(f"  规则 {i+1}: {rule['Description']} - ✓")
    except Exception as e:
        # 试用另一种方式
        try:
            resp = call_api("vpc", VPC_HOST, VPC_VER, "CreateSecurityGroupPolicies", {
                "SecurityGroupId": sg_id,
                "SecurityGroupPolicySet": {
                    "Ingress": [rule] if rule["Direction"] == "ingress" else [],
                    "Egress": [rule] if rule["Direction"] == "egress" else [],
                },
            })
            print(f"  规则 {i+1}: {rule['Description']} - ✓ (v2)")
        except Exception as e2:
            print(f"  规则 {i+1}: {rule['Description']} - ✗ {e2}")

# 输出汇总
print("\n" + "=" * 60)
print("创建完成！汇总信息：")
print("=" * 60)
print(f"  VPC ID:    {vpc_id}")
print(f"  子网 ID:   {subnet_id}")
print(f"  安全组 ID: {sg_id}")
print(f"  可用区:    {zone}")
print(f"\n请在 deploy_scf.py 中使用这些 ID：")
print(f'  VPC_ID = "{vpc_id}"')
print(f'  SUBNET_ID = "{subnet_id}"')
print(f"\n下一步：在 TDSQL-C 控制台 → 网络管理 → 将实例切换到此 VPC")
print(f"  VPC: {vpc_id}")
print(f"  子网: {subnet_id}")
