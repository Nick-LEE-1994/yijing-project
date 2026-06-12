# -*- coding: utf-8 -*-
"""更新 SCF 函数的 VPC 配置并获取函数 URL"""
import json
import time
from tencentcloud.common import credential
from tencentcloud.scf.v20180416 import scf_client, models as scf_models

SECRET_ID = "${TENCENT_SECRET_ID}"
SECRET_KEY = "${TENCENT_SECRET_KEY}"
REGION = "ap-chengdu"
FUNCTION_NAME = "yijing-divine"
NAMESPACE = "default"

VPC_ID = "vpc-gunz4h4k"
SUBNET_ID = "subnet-nrlw5qgd"

cred = credential.Credential(SECRET_ID, SECRET_KEY)
client = scf_client.ScfClient(cred, REGION)

# 1. 等待函数 Active
print("等待函数 Active...")
for i in range(12):
    time.sleep(5)
    req = scf_models.GetFunctionRequest()
    req.FunctionName = FUNCTION_NAME
    req.Namespace = NAMESPACE
    resp = client.GetFunction(req)
    print(f"  状态: {resp.Status}, VPC: {getattr(resp, 'VpcConfig', None)}")
    if resp.Status == "Active":
        break

# 2. 更新 VPC 配置
print("\n更新 VPC 配置...")
req = scf_models.UpdateFunctionConfigurationRequest()
req.FunctionName = FUNCTION_NAME
req.Namespace = NAMESPACE
req.VpcConfig = scf_models.VpcConfig()
req.VpcConfig.VpcId = VPC_ID
req.VpcConfig.SubnetId = SUBNET_ID

# 同时更新环境变量（避免被覆盖）
req.Environment = scf_models.Environment()
req.Environment.Variables = [scf_models.Variable()]
req.Environment.Variables[0].Key = "DEEPSEEK_API_KEY"
req.Environment.Variables[0].Value = "${DEEPSEEK_API_KEY}"

try:
    resp = client.UpdateFunctionConfiguration(req)
    print("VPC 配置更新成功!")
    print(f"  响应: {resp}")
except Exception as e:
    print(f"VPC 配置更新失败: {e}")

# 3. 等待更新完成
print("\n等待配置生效...")
for i in range(12):
    time.sleep(5)
    req = scf_models.GetFunctionRequest()
    req.FunctionName = FUNCTION_NAME
    req.Namespace = NAMESPACE
    resp = client.GetFunction(req)
    vpc_config = getattr(resp, 'VpcConfig', None)
    print(f"  状态: {resp.Status}, VpcId: {vpc_config.VpcId if vpc_config else 'None'}")
    if resp.Status == "Active":
        break

# 4. 获取函数 URL
print("\n获取函数 URL...")
req = scf_models.ListTriggersRequest()
req.FunctionName = FUNCTION_NAME
req.Namespace = NAMESPACE
try:
    resp = client.ListTriggers(req)
    print(f"触发器数量: {len(resp.Triggers)}")
    for t in resp.Triggers:
        print(f"  {t.TriggerName} ({t.Type})")
        desc = t.TriggerDesc
        if isinstance(desc, str):
            try:
                desc = json.loads(desc)
            except:
                pass
        if isinstance(desc, dict):
            for key in ["CustomDomain", "url", "CustomDomainConfig"]:
                if key in desc:
                    print(f"  URL: {desc[key] if isinstance(desc[key], str) else json.dumps(desc[key])}")
except Exception as e:
    print(f"获取触发器失败: {e}")

# 也打印函数详情中的所有属性
print("\n函数详情:")
req = scf_models.GetFunctionRequest()
req.FunctionName = FUNCTION_NAME
req.Namespace = NAMESPACE
resp = client.GetFunction(req)
for attr in ["Status", "ModId", "Namespace", "FunctionName", "Runtime", "Type"]:
    print(f"  {attr}: {getattr(resp, attr, 'N/A')}")
vpc = getattr(resp, 'VpcConfig', None)
if vpc:
    print(f"  VpcId: {vpc.VpcId}")
    print(f"  SubnetId: {vpc.SubnetId}")
