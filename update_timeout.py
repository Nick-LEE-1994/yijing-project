# -*- coding: utf-8 -*-
"""将 SCF 函数超时从 60s 调到 120s"""
from tencentcloud.common import credential
from tencentcloud.scf.v20180416 import scf_client, models as scf_models

SECRET_ID = "${TENCENT_SECRET_ID}"
SECRET_KEY = "${TENCENT_SECRET_KEY}"
REGION = "ap-chengdu"
FUNCTION_NAME = "yijing-divine"
NAMESPACE = "default"

cred = credential.Credential(SECRET_ID, SECRET_KEY)
client = scf_client.ScfClient(cred, REGION)

req = scf_models.UpdateFunctionConfigurationRequest()
req.FunctionName = FUNCTION_NAME
req.Namespace = NAMESPACE
req.Timeout = 120        # 执行超时 120s
req.InitTimeout = 30     # 初始化超时保持 30s
req.MemorySize = 256     # 内存保持 256MB

# VPC 配置不能丢
from tencentcloud.scf.v20180416.models import VpcConfig, Environment, Variable
req.VpcConfig = VpcConfig()
req.VpcConfig.VpcId = "vpc-gunz4h4k"
req.VpcConfig.SubnetId = "subnet-nrlw5qgd"

req.Environment = Environment()
req.Environment.Variables = [Variable()]
req.Environment.Variables[0].Key = "DEEPSEEK_API_KEY"
req.Environment.Variables[0].Value = "${DEEPSEEK_API_KEY}"

try:
    resp = client.UpdateFunctionConfiguration(req)
    print(f"配置更新成功! Timeout: {req.Timeout}s")
except Exception as e:
    print(f"更新失败: {e}")

# 等待并确认
import time
for i in range(12):
    time.sleep(5)
    g = scf_models.GetFunctionRequest()
    g.FunctionName = FUNCTION_NAME
    g.Namespace = NAMESPACE
    r = client.GetFunction(g)
    print(f"  状态: {r.Status}, Timeout: {getattr(r, 'Timeout', '?')}s")
    if r.Status == "Active":
        break
