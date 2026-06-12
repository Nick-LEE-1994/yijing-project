# -*- coding: utf-8 -*-
"""获取函数 URL"""
import json
from tencentcloud.common import credential
from tencentcloud.scf.v20180416 import scf_client, models as scf_models

SECRET_ID = "${TENCENT_SECRET_ID}"
SECRET_KEY = "${TENCENT_SECRET_KEY}"
REGION = "ap-shanghai"

cred = credential.Credential(SECRET_ID, SECRET_KEY)
client = scf_client.ScfClient(cred, REGION)

# 获取函数信息
print("=== 函数信息 ===")
req = scf_models.GetFunctionRequest()
req.FunctionName = "yijing-divine"
req.Namespace = "default"
resp = client.GetFunction(req)
attrs = [a for a in dir(resp) if not a.startswith('_')]
for attr in attrs:
    try:
        val = getattr(resp, attr)
        if val and not callable(val):
            print(f"  {attr}: {val}")
    except:
        pass

# 获取触发器列表
print("\n=== 触发器列表 ===")
treq = scf_models.GetTriggersRequest()
treq.FunctionName = "yijing-divine"
treq.Namespace = "default"
tresp = client.GetTriggers(treq)
print(f"Triggers 类型: {type(tresp.Triggers)}")

for t in tresp.Triggers:
    print(f"\n--- 触发器 ---")
    tattrs = [a for a in dir(t) if not a.startswith('_')]
    for attr in tattrs:
        try:
            val = getattr(t, attr)
            if val is not None and not callable(val):
                print(f"  {attr}: {val}")
        except:
            pass
    # 尝试解析 TriggerDesc
    if hasattr(t, 'TriggerDesc') and t.TriggerDesc:
        try:
            desc = json.loads(t.TriggerDesc)
            print(f"  [解析后 TriggerDesc]:")
            for k, v in desc.items():
                print(f"    {k}: {v}")
        except:
            pass
