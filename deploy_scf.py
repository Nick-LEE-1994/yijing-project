# -*- coding: utf-8 -*-
"""Deploy or update the Tencent Cloud SCF backend.

Required environment variables:
  TENCENT_SECRET_ID, TENCENT_SECRET_KEY, DEEPSEEK_API_KEY, DB_PASSWORD,
  JWT_SECRET

Recommended environment variables:
  DB_HOST, DB_USER, DB_NAME, CORS_ORIGINS, TENCENT_REGION, SCF_FUNCTION_NAME,
  SCF_VPC_ID, SCF_SUBNET_ID
"""

import base64
import json
import os
import sys
import time

from tencentcloud.common import credential
from tencentcloud.scf.v20180416 import models as scf_models
from tencentcloud.scf.v20180416 import scf_client


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ZIP_PATH = os.path.join(PROJECT_DIR, "scf_deploy.zip")

REGION = os.environ.get("TENCENT_REGION", "ap-chengdu")
FUNCTION_NAME = os.environ.get("SCF_FUNCTION_NAME", "yijing-divine")
NAMESPACE = os.environ.get("SCF_NAMESPACE", "default")
VPC_ID = os.environ.get("SCF_VPC_ID", "vpc-gunz4h4k")
SUBNET_ID = os.environ.get("SCF_SUBNET_ID", "subnet-nrlw5qgd")

REQUIRED_ENV = (
    "TENCENT_SECRET_ID",
    "TENCENT_SECRET_KEY",
    "DEEPSEEK_API_KEY",
    "DB_PASSWORD",
    "JWT_SECRET",
)


def require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError("Missing required environment variable: %s" % name)
    return value


def env_var(key, default=""):
    value = os.environ.get(key, default)
    var = scf_models.Variable()
    var.Key = key
    var.Value = str(value)
    return var


def build_environment():
    for name in REQUIRED_ENV:
        require_env(name)

    keys = [
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "DB_HOST",
        "DB_PORT",
        "DB_USER",
        "DB_PASSWORD",
        "DB_NAME",
        "JWT_SECRET",
        "JWT_EXPIRES_DAYS",
        "DAILY_AI_LIMIT",
        "CORS_ORIGINS",
        "BUILD_VERSION",
    ]
    defaults = {
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "DEEPSEEK_MODEL": "deepseek-v4-flash",
        "DB_PORT": "3306",
        "DB_USER": "root",
        "DB_NAME": "yijing",
        "JWT_EXPIRES_DAYS": "7",
        "DAILY_AI_LIMIT": "10",
        "CORS_ORIGINS": "http://localhost:8081",
        "BUILD_VERSION": "public-deploy-20260609",
    }
    env = scf_models.Environment()
    env.Variables = [env_var(key, defaults.get(key, "")) for key in keys]
    return env


def read_zip_b64():
    if not os.path.exists(ZIP_PATH):
        raise RuntimeError("Missing deployment zip: %s. Run rebuild_v4.py first." % ZIP_PATH)
    with open(ZIP_PATH, "rb") as f:
        zip_bytes = f.read()
    print("Deployment package: %.2f MB" % (len(zip_bytes) / 1024 / 1024))
    return base64.b64encode(zip_bytes).decode("utf-8")


def apply_runtime_config(req, include_create_fields=False):
    if include_create_fields:
        req.Runtime = "Python3.9"
        req.Type = "HTTP"
        req.Handler = "scf_handler.main"
    req.MemorySize = int(os.environ.get("SCF_MEMORY_SIZE", "256"))
    req.Timeout = int(os.environ.get("SCF_TIMEOUT", "120"))
    req.InitTimeout = int(os.environ.get("SCF_INIT_TIMEOUT", "30"))

    req.VpcConfig = scf_models.VpcConfig()
    req.VpcConfig.VpcId = VPC_ID
    req.VpcConfig.SubnetId = SUBNET_ID

    req.PublicNetConfig = scf_models.PublicNetConfigIn()
    req.PublicNetConfig.PublicNetStatus = "ENABLE"
    req.PublicNetConfig.EipConfig = scf_models.EipConfigIn()
    req.PublicNetConfig.EipConfig.EipStatus = os.environ.get("SCF_EIP_STATUS", "DISABLE")

    req.Environment = build_environment()


def create_function(client):
    print("Creating SCF function %s..." % FUNCTION_NAME)
    req = scf_models.CreateFunctionRequest()
    req.FunctionName = FUNCTION_NAME
    req.Namespace = NAMESPACE
    req.Description = "Yijing Meihua divination API"
    req.Code = scf_models.Code()
    req.Code.ZipFile = read_zip_b64()
    apply_runtime_config(req, include_create_fields=True)
    client.CreateFunction(req)


def update_function_code(client):
    print("Updating SCF code...")
    req = scf_models.UpdateFunctionCodeRequest()
    req.FunctionName = FUNCTION_NAME
    req.Namespace = NAMESPACE
    req.Code = scf_models.Code()
    req.Code.ZipFile = read_zip_b64()
    client.UpdateFunctionCode(req)


def update_function_config(client):
    print("Updating SCF configuration...")
    req = scf_models.UpdateFunctionConfigurationRequest()
    req.FunctionName = FUNCTION_NAME
    req.Namespace = NAMESPACE
    apply_runtime_config(req)
    client.UpdateFunctionConfiguration(req)


def wait_for_active(client, timeout=180):
    print("Waiting for function to become Active...")
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(5)
        req = scf_models.GetFunctionRequest()
        req.FunctionName = FUNCTION_NAME
        req.Namespace = NAMESPACE
        resp = client.GetFunction(req)
        print("  status: %s" % resp.Status)
        if resp.Status == "Active":
            return
        if resp.Status in ("CreateFailed", "UpdateFailed"):
            raise RuntimeError("SCF function is in failed state: %s" % resp.Status)
    raise RuntimeError("Timed out waiting for SCF function to become Active")


def get_function_url(client):
    req = scf_models.ListTriggersRequest()
    req.FunctionName = FUNCTION_NAME
    req.Namespace = NAMESPACE
    resp = client.ListTriggers(req)
    for trigger in resp.Triggers:
        if trigger.Type != "http":
            continue
        desc = json.loads(trigger.TriggerDesc)
        if desc.get("CustomDomain"):
            return desc["CustomDomain"]
        if desc.get("url"):
            return desc["url"]
        net_config = desc.get("NetConfig")
        if isinstance(net_config, dict) and net_config.get("ExtranetUrl"):
            return net_config["ExtranetUrl"]
    return None


def create_function_url(client):
    origins = [
        origin.strip()
        for origin in os.environ.get("CORS_ORIGINS", "http://localhost:8081").split(",")
        if origin.strip()
    ]
    trigger_desc = {
        "AuthType": "NONE",
        "NetConfig": {"EnableIntranet": False, "EnableExtranet": True},
        "CorsConfig": {
            "Enable": True,
            "Origins": origins,
            "Methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
            "Headers": ["*"],
            "ExposeHeaders": ["*"],
            "MaxAge": 86400,
        },
    }

    req = scf_models.CreateTriggerRequest()
    req.FunctionName = FUNCTION_NAME
    req.Namespace = NAMESPACE
    req.TriggerName = "func_url"
    req.Type = "http"
    req.TriggerDesc = json.dumps(trigger_desc)
    req.Enable = "OPEN"
    req.Qualifier = "$LATEST"

    try:
        client.CreateTrigger(req)
    except Exception as exc:
        if "ResourceInUse" not in str(exc):
            raise
    return get_function_url(client)


def main():
    secret_id = require_env("TENCENT_SECRET_ID")
    secret_key = require_env("TENCENT_SECRET_KEY")
    client = scf_client.ScfClient(credential.Credential(secret_id, secret_key), REGION)

    exists = True
    try:
        req = scf_models.GetFunctionRequest()
        req.FunctionName = FUNCTION_NAME
        req.Namespace = NAMESPACE
        resp = client.GetFunction(req)
        print("Function exists: %s, status=%s" % (FUNCTION_NAME, resp.Status))
    except Exception:
        exists = False

    if exists:
        update_function_code(client)
        wait_for_active(client)
        update_function_config(client)
    else:
        create_function(client)

    wait_for_active(client)
    url = create_function_url(client)
    if not url:
        raise RuntimeError("Could not resolve SCF function URL from trigger response")

    print("\nSCF backend deployed:")
    print(url)
    print("\nSet index.html BACKEND_URL to this value if it changed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Deployment failed: %s" % exc, file=sys.stderr)
        sys.exit(1)
