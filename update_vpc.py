#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""更新 SCF 函数的 VPC 配置，并测试数据库连接"""

import time
import json
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.scf.v20180416 import scf_client, models

SECRET_ID  = "${TENCENT_SECRET_ID}"
SECRET_KEY = "${TENCENT_SECRET_KEY}"
REGION     = "ap-shanghai"
FUNCTION_NAME = "yijing-divine"
NAMESPACE  = "default"

# 正确的 VPC 信息
VPC_ID    = "vpc-26569si6"
SUBNET_ID = "subnet-cd0vkn5d"

def main():
    cred = credential.Credential(SECRET_ID, SECRET_KEY)
    client = scf_client.ScfClient(cred, REGION)

    # 1. 更新函数 VPC 配置
    print("=== 更新 SCF 函数 VPC 配置 ===")
    req = models.UpdateFunctionConfigurationRequest()
    req.FunctionName = FUNCTION_NAME
    req.Namespace    = NAMESPACE
    req.VpcConfig    = models.VpcConfig()
    req.VpcConfig.VpcId    = VPC_ID
    req.VpcConfig.SubnetId = SUBNET_ID

    try:
        resp = client.UpdateFunctionConfiguration(req)
        print("  VPC 配置更新成功！")
        print(f"  RequestId: {resp.RequestId}")
    except TencentCloudSDKException as e:
        print(f"  ❌ 更新失败: {e}")
        return

    # 2. 等待函数更新完成
    print("\n=== 等待函数更新完成（约 30 秒）===")
    time.sleep(30)

    # 3. 检查函数状态
    print("\n=== 检查函数状态 ===")
    get_req = models.GetFunctionRequest()
    get_req.FunctionName = FUNCTION_NAME
    get_req.Namespace    = NAMESPACE
    try:
        resp = client.GetFunction(get_req)
        print(f"  函数状态: {resp.Status}")
        if hasattr(resp, 'VpcConfig') and resp.VpcConfig:
            print(f"  VPC: {resp.VpcConfig.VpcId}")
            print(f"  子网: {resp.VpcConfig.SubnetId}")
    except TencentCloudSDKException as e:
        print(f"  查询失败: {e}")
        return

    # 4. 测试健康检查（会尝试连接数据库）
    print("\n=== 测试 /api/health ===")
    import urllib.request
    import urllib.error
    url = "https://1304112547-kj7bx6ppcm.ap-shanghai.tencentscf.com/api/health"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            body = r.read().decode("utf-8")
            print(f"  状态码: {r.status}")
            print(f"  响应: {body}")
            data = json.loads(body)
            if data.get("db"):
                print("  ✅ 数据库连接成功！")
            else:
                print("  ⚠️ 数据库连接失败（可能是 TDSQL-C 暂停中，会自动唤醒）")
    except urllib.error.HTTPError as e:
        print(f"  HTTP 错误 {e.code}: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"  测试失败: {e}")

if __name__ == "__main__":
    main()
