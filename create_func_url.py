"""为 SCF 函数创建函数 URL（替代已下线的 API 网关触发器）"""
import json
import os
from tencentcloud.common import credential
from tencentcloud.scf.v20180416 import scf_client, models as scf_models

# 凭证
SECRET_ID = "${TENCENT_SECRET_ID}"
SECRET_KEY = "${TENCENT_SECRET_KEY}"
REGION = "ap-shanghai"

# 函数信息
FUNCTION_NAME = "yijing-divine"
NAMESPACE = "default"

def main():
    cred = credential.Credential(SECRET_ID, SECRET_KEY)
    client = scf_client.ScfClient(cred, REGION)

    # 列出所有函数
    print("=== 列出所有函数 ===")
    list_req = scf_models.ListFunctionsRequest()
    list_req.Limit = 50
    try:
        list_resp = client.ListFunctions(list_req)
        if list_resp.Functions:
            for f in list_resp.Functions:
                print(f"  函数名: {f.FunctionName}, 命名空间: {f.Namespace}, 状态: {f.Status}, 运行时: {f.Runtime}, 类型: {f.Type}")
        else:
            print("  没有找到任何函数")
    except Exception as e:
        print(f"列出函数失败: {e}")
        return

    # 先查看函数当前状态
    print("\n=== 查询函数信息 ===")
    get_req = scf_models.GetFunctionRequest()
    get_req.FunctionName = FUNCTION_NAME
    get_req.Namespace = NAMESPACE
    get_req.Qualifier = "$LATEST"
    resp = client.GetFunction(get_req)
    print(f"函数状态: {resp.Status}")
    print(f"函数类型: {resp.Type}")
    print(f"运行时: {resp.Runtime}")

    # 创建函数 URL（使用 CreateTrigger，Type="http"）
    print("\n=== 创建函数 URL ===")
    trigger_desc = {
        "AuthType": "NONE",  # 开放访问，无需鉴权
        "NetConfig": {
            "EnableIntranet": False,
            "EnableExtranet": True  # 开启公网访问
        },
        "CorsConfig": {
            "Enable": True,
            "Origins": ["*"],
            "Methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "Headers": ["*"],
            "ExposeHeaders": ["*"],
            "MaxAge": 86400
        }
    }

    create_req = scf_models.CreateTriggerRequest()
    create_req.FunctionName = FUNCTION_NAME
    create_req.Namespace = NAMESPACE
    create_req.TriggerName = "func_url"
    create_req.Type = "http"
    create_req.TriggerDesc = json.dumps(trigger_desc)
    create_req.Enable = "OPEN"
    create_req.Qualifier = "$LATEST"

    try:
        resp = client.CreateTrigger(create_req)
        print(f"创建成功!")
        # 尝试获取 URL 信息
        print(f"返回的 TriggerInfo: {resp.TriggerInfo if hasattr(resp, 'TriggerInfo') else 'N/A'}")

        # 获取完整触发器列表
        list_req = scf_models.GetTriggersRequest()
        list_req.FunctionName = FUNCTION_NAME
        list_req.Namespace = NAMESPACE
        list_req.Qualifier = "$LATEST"
        triggers_resp = client.GetTriggers(list_req)

        print(f"\n=== 当前触发器列表 ===")
        for t in triggers_resp.Triggers:
            print(f"  名称: {t.TriggerName}, 类型: {t.Type}, 状态: {t.Status}")
            print(f"  描述: {t.TriggerDesc}")

    except Exception as e:
        print(f"创建失败: {e}")
        # 如果失败，尝试列出已有触发器看看
        try:
            list_req = scf_models.GetTriggersRequest()
            list_req.FunctionName = FUNCTION_NAME
            list_req.Namespace = NAMESPACE
            triggers_resp = client.GetTriggers(list_req)
            print(f"\n=== 已有触发器 ===")
            for t in triggers_resp.Triggers:
                print(f"  名称: {t.TriggerName}, 类型: {t.Type}")
        except Exception as e2:
            print(f"列出触发器也失败: {e2}")

if __name__ == "__main__":
    main()
