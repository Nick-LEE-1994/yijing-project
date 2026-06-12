"""Tencent Cloud API deployment helper - using SDK with proper approach"""
import json, os, sys

# Ensure tccli's python SDK can work
from tencentcloud.common.credential import Credential
from tencentcloud.vpc.v20170302.vpc_client import VpcClient as VpcV2
from tencentcloud.vpc.v20170302 import models as vpc_v2_models
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile

SECRET_ID = "${TENCENT_SECRET_ID}"
SECRET_KEY = "${TENCENT_SECRET_KEY}"
REGION = "ap-chengdu"

def call_vpc(action, params):
    """Call VPC API using the CommonClient approach"""
    cred = Credential(SECRET_ID, SECRET_KEY)
    httpProfile = HttpProfile()
    httpProfile.endpoint = "vpc.tencentcloudapi.com"
    clientProfile = ClientProfile()
    clientProfile.httpProfile = httpProfile
    from tencentcloud.common.common_client import CommonClient
    client = CommonClient("vpc", "2017-03-12", cred, REGION, clientProfile)
    return client.call(action, params)

# Try DescribeVpcs with call method
cred = Credential(SECRET_ID, SECRET_KEY)
httpProfile = HttpProfile()
httpProfile.endpoint = "vpc.tencentcloudapi.com"
clientProfile = ClientProfile()
clientProfile.httpProfile = httpProfile
from tencentcloud.vpc.v20170312 import vpc_client as vpc_client_12, models as vpc_models_12

client = vpc_client_12.VpcClient(cred, REGION, clientProfile)

# Check available methods
import inspect
members = [m for m in dir(client) if not m.startswith('_') and 'Describe' in m]
print("Available Describe methods:", members)

# Try with VPC 2020 version
from tencentcloud.vpc.v20200312 import vpc_client as vpc_2020, models as vpc_2020_models
client2 = vpc_2020.VpcClient(cred, REGION, clientProfile)
members2 = [m for m in dir(client2) if not m.startswith('_') and 'Describe' in m]
print("V2020 Describe methods:", members2)
