#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""等待 SCF 函数更新完成，然后测试数据库连接"""

import time
import json
import urllib.request
import urllib.error
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.scf.v20180416 import scf_client, models

SECRET_ID  = "${TENCENT_SECRET_ID}"
SECRET_KEY = "${TENCENT_SECRET_KEY}"
REGION     = "ap-shanghai"
FUNCTION_NAME = "yijing-divine"
BASE_URL   = "https://1304112547-kj7bx6ppcm.ap-shanghai.tencentscf.com"

def wait_for_active(client):
    """等待函数状态变成 Active"""
    print("等待函数更新完成...")
    for i in range(30):  # 最多等 5 分钟
        try:
            req = models.GetFunctionRequest()
            req.FunctionName = FUNCTION_NAME
            req.Namespace    = "default"
            resp = client.GetFunction(req)
            status = resp.Status
            print(f"  [{i+1}] 状态: {status}")
            if status == "Active":
                print("  ✅ 函数已就绪！")
                return True
        except TencentCloudSDKException as e:
            print(f"  [{i+1}] 查询失败: {e}")
        time.sleep(10)
    print("  ⚠️ 超时，函数可能仍在更新")
    return False

def test_register():
    """测试注册接口（需要数据库连接）"""
    print("\n=== 测试 /api/auth/register（需要数据库）===")
    url = BASE_URL + "/api/auth/register"
    payload = json.dumps({
        "username": "test_user_" + str(int(time.time())),
        "password": "Test1234"
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json"
    }, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            print(f"  状态码: {resp.status}")
            print(f"  响应: {body}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"  HTTP 错误 {e.code}: {body}")
        # 500 错误可能是数据库连不上
        if e.code == 500:
            try:
                data = json.loads(body)
                msg = data.get("msg", "")
                print(f"  错误信息: {msg}")
            except:
                pass
        return False
    except Exception as e:
        print(f"  请求失败: {e}")
        return False

def test_health_db():
    """测试健康检查（如果实现了 db 检查）"""
    print("\n=== 测试 /api/health ===")
    url = BASE_URL + "/api/health"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            print(f"  状态码: {resp.status}")
            print(f"  响应: {body}")
            data = json.loads(body)
            if "db" in data:
                print(f"  数据库状态: {data['db']}")
                return data.get("db") == True
            return None  # 健康检查不检查数据库
    except Exception as e:
        print(f"  请求失败: {e}")
        return False

def main():
    cred = credential.Credential(SECRET_ID, SECRET_KEY)
    client = scf_client.ScfClient(cred, REGION)
    
    # 1. 等待函数就绪
    if not wait_for_active(client):
        print("\n⚠️ 函数未就绪，测试结果可能不准确")
    
    # 2. 测试健康检查
    test_health_db()
    
    # 3. 测试注册（需要数据库）
    test_register()
    
    print("\n=== 建议 ===")
    print("如果注册接口返回 500 且提示数据库错误：")
    print("1. 检查 TDSQL-C 实例是否存在（去控制台确认）")
    print("2. 检查 config.py 的数据库配置是否正确")
    print("3. 如果 TDSQL-C 已暂停，首次连接会自动唤醒（约 30 秒）")

if __name__ == "__main__":
    main()
