#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出当前账号下所有 VPC 和 TDSQL-C (CynosDB) 实例"""

import json
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.vpc.v20170312 import vpc_client, models as vpc_models
from tencentcloud.cynosdb.v20190107 import cynosdb_client, models as cynosdb_models

SECRET_ID  = "${TENCENT_SECRET_ID}"
SECRET_KEY = "${TENCENT_SECRET_KEY}"
REGION     = "ap-shanghai"

def main():
    cred = credential.Credential(SECRET_ID, SECRET_KEY)

    # 1. 列出所有 VPC
    print("=" * 60)
    print("VPC 列表 (ap-shanghai)")
    print("=" * 60)
    try:
        client = vpc_client.VpcClient(cred, REGION)
        req = vpc_models.DescribeVpcsRequest()
        req.Limit = "50"
        resp = client.DescribeVpcs(req)
        if resp.VpcSet:
            for vpc in resp.VpcSet:
                print(f"  VPC: {vpc.VpcName} ({vpc.VpcId})")
                print(f"    CIDR: {vpc.CidrBlock}")
                print(f"    是否默认: {vpc.IsDefault}")
                print()
        else:
            print("  ❌ 没有找到任何 VPC\n")
    except TencentCloudSDKException as e:
        print(f"  ❌ 查询 VPC 失败: {e}\n")

    # 2. 列出所有子网
    print("=" * 60)
    print("子网列表 (ap-shanghai)")
    print("=" * 60)
    try:
        client = vpc_client.VpcClient(cred, REGION)
        req = vpc_models.DescribeSubnetsRequest()
        req.Limit = "50"
        resp = client.DescribeSubnets(req)
        if resp.SubnetSet:
            for sub in resp.SubnetSet:
                print(f"  子网: {sub.SubnetName} ({sub.SubnetId})")
                print(f"    VPC: {sub.VpcId}, CIDR: {sub.CidrBlock}")
                print()
        else:
            print("  ❌ 没有找到任何子网\n")
    except TencentCloudSDKException as e:
        print(f"  ❌ 查询子网失败: {e}\n")

    # 3. 列出 TDSQL-C (CynosDB) 实例
    print("=" * 60)
    print("TDSQL-C (CynosDB) 实例列表 (ap-shanghai)")
    print("=" * 60)
    try:
        client = cynosdb_client.CynosdbClient(cred, REGION)
        req = cynosdb_models.DescribeClustersRequest()
        resp = client.DescribeClusters(req)
        if resp.TotalCount and int(resp.TotalCount) > 0:
            for cluster in resp.Clusters:
                print(f"  集群: {cluster.ClusterName} ({cluster.ClusterId})")
                print(f"    状态: {cluster.Status}")
                print(f"    VPC: {cluster.VpcId}, 子网: {cluster.SubnetId}")
                print(f"    内网地址: {cluster.Vip}:{cluster.Vport}")
                print(f"    DB 类型: {cluster.DbType}")
                print()
        else:
            print("  ❌ 没有找到任何 TDSQL-C 集群\n")
    except TencentCloudSDKException as e:
        print(f"  ❌ 查询 TDSQL-C 失败: {e}\n")

    # 4. 检查其他常见区域
    print("=" * 60)
    print("检查其他区域是否有 TDSQL-C 实例...")
    print("=" * 60)
    for region in ["ap-beijing", "ap-guangzhou", "ap-chengdu", "ap-hongkong"]:
        try:
            client = cynosdb_client.CynosdbClient(cred, region)
            req = cynosdb_models.DescribeClustersRequest()
            resp = client.DescribeClusters(req)
            if resp.TotalCount and int(resp.TotalCount) > 0:
                print(f"\n  ✅ 在 {region} 找到 {resp.TotalCount} 个集群:")
                for cluster in resp.Clusters:
                    print(f"    {cluster.ClusterName} ({cluster.ClusterId}) - {cluster.Vip}:{cluster.Vport}")
            else:
                print(f"  {region}: 无")
        except TencentCloudSDKException as e:
            print(f"  {region}: 查询失败 ({e})")

if __name__ == "__main__":
    main()
