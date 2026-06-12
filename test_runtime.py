# -*- coding: utf-8 -*-
"""快速测试：更新函数运行时为 Python 3.12"""
import json
from tencentcloud.common import credential
from tencentcloud.scf.v20180416 import scf_client, models as scf_models

SECRET_ID = "${TENCENT_SECRET_ID}"
SECRET_KEY = "${TENCENT_SECRET_KEY}"
REGION = "ap-shanghai"

cred = credential.Credential(SECRET_ID, SECRET_KEY)
client = scf_client.ScfClient(cred, REGION)

# 尝试更新运行时为 Python 3.12
for runtime in ["Python3.12", "Python3.11", "Python3.10"]:
    print(f"\n尝试 Runtime={runtime}...")
    try:
        req = scf_models.UpdateFunctionConfigurationRequest()
        req.FunctionName = "yijing-divine"
        req.Namespace = "default"
        req.Runtime = runtime
        resp = client.UpdateFunctionConfiguration(req)
        print(f"  成功! Runtime={runtime}")
        break
    except Exception as e:
        print(f"  失败: {e}")
        print(f"  尝试下一个版本...")
