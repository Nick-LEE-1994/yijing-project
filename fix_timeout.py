#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 SCF 函数配置：增加超时时间，并检查 VPC 设置"""

import time
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.scf.v20180416 import scf_client, models

SECRET_ID   = "${TENCENT_SECRET_ID}"
SECRET_KEY  = "${TENCENT_SECRET_KEY}"
REGION      = "ap-shanghai"
FUNCTION_NAME = "yijing-divine"

def main():
    cred = credential.Credential(SECRET_ID, SECRET_KEY)
    client = scf_client.ScfClient(cred, REGION)

    # 1. 查看当前函数配置
    print("=== 当前函数配置 ===")
    get_req = models.GetFunctionRequest()
    get_req.FunctionName = FUNCTION_NAME
    get_req.Namespace    = "default"
    get_req.Qualifier    = "$LATEST"
    resp = client.GetFunction(get_req)
    print(f"  超时时间: {resp.Timeout} 秒")
    print(f"  内存: {resp.MemorySize} MB")
    print(f"  VPC: {resp.VpcConfig.VpcId if resp.VpcConfig else '未配置'}")
    print(f"  状态: {resp.Status}")

    # 2. 修改超时时间为 30 秒
    print("\n=== 更新函数超时时间 → 30 秒 ===")
    update_req = models.UpdateFunctionConfigurationRequest()
    update_req.FunctionName = FUNCTION_NAME
    update_req.Namespace    = "default"
    update_req.Timeout      = 30  # 增加到 30 秒
    update_req.MemorySize   = 256  # 增加到 256 MB
    try:
        client.UpdateFunctionConfiguration(update_req)
        print("  配置更新成功！")
    except TencentCloudSDKException as e:
        print(f"  更新失败: {e}")

    # 3. 等待函数更新完成
    print("\n=== 等待函数更新完成 ===")
    for i in range(20):
        time.sleep(5)
        try:
            r = client.GetFunction(get_req)
            status = r.Status
            print(f"  [{i+1}] 状态: {status}")
            if status == "Active":
                print("  ✅ 函数已就绪！")
                break
        except:
            pass

    # 4. 测试健康检查
    print("\n=== 测试 /api/health ===")
    import urllib.request
    import urllib.error
    url = "https://1304112547-kj7bx6ppcm.ap-shanghai.tencentscf.com/api/health"
    try:
        with urllib.request.urlopen(url, timeout=35) as r:
            body = r.read().decode("utf-8")
            print(f"  状态码: {r.status}")
            print(f"  响应: {body}")
    except urllib.error.HTTPError as e:
        print(f"  HTTP 错误 {e.code}: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"  请求失败: {e}")

if __name__ == "__main__":
    main()
