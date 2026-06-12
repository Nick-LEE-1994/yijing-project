# -*- coding: utf-8 -*-
"""Deploy index.html to a Tencent Cloud COS static website bucket.

Required environment variables:
  TENCENT_SECRET_ID, TENCENT_SECRET_KEY, TENCENT_APP_ID

Optional environment variables:
  TENCENT_REGION=ap-chengdu
  COS_BUCKET=yijing-static
  COS_INDEX_FILE=index.html
"""

import email.utils
import hashlib
import hmac
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
REGION = os.environ.get("TENCENT_REGION", "ap-chengdu")
BUCKET = os.environ.get("COS_BUCKET", "yijing-static")
APP_ID = os.environ.get("TENCENT_APP_ID", "").strip()
INDEX_FILE = os.environ.get("COS_INDEX_FILE", os.path.join(PROJECT_DIR, "index.html"))


def require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError("Missing required environment variable: %s" % name)
    return value


def bucket_name():
    if not APP_ID:
        raise RuntimeError("Missing required environment variable: TENCENT_APP_ID")
    suffix = "-" + APP_ID
    return BUCKET if BUCKET.endswith(suffix) else BUCKET + suffix


def bucket_host():
    return "%s.cos.%s.myqcloud.com" % (bucket_name(), REGION)


def website_url():
    return "https://%s.cos-website.%s.myqcloud.com" % (bucket_name(), REGION)


def canonical_query(query):
    if not query:
        return ""
    pairs = urllib.parse.parse_qsl(query, keep_blank_values=True)
    return "&".join(
        "%s=%s" % (
            urllib.parse.quote(k.lower(), safe="-_.~"),
            urllib.parse.quote(v, safe="-_.~"),
        )
        for k, v in sorted(pairs)
    )


def cos_authorization(method, path, query, headers, secret_id, secret_key):
    now = int(time.time())
    key_time = "%d;%d" % (now - 60, now + 600)
    sign_time = key_time

    lower_headers = {k.lower(): str(v).strip() for k, v in headers.items()}
    signed_header_names = sorted(lower_headers)
    header_list = ";".join(signed_header_names)
    canonical_headers = "&".join(
        "%s=%s" % (
            urllib.parse.quote(k, safe="-_.~"),
            urllib.parse.quote(lower_headers[k], safe="-_.~"),
        )
        for k in signed_header_names
    )

    http_string = "%s\n%s\n%s\n%s\n" % (
        method.lower(),
        path,
        canonical_query(query),
        canonical_headers,
    )
    string_to_sign = "sha1\n%s\n%s\n" % (
        sign_time,
        hashlib.sha1(http_string.encode("utf-8")).hexdigest(),
    )
    sign_key = hmac.new(secret_key.encode("utf-8"), key_time.encode("utf-8"), hashlib.sha1).hexdigest()
    signature = hmac.new(sign_key.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1).hexdigest()
    return (
        "q-sign-algorithm=sha1&"
        "q-ak=%s&"
        "q-sign-time=%s&"
        "q-key-time=%s&"
        "q-header-list=%s&"
        "q-url-param-list=%s&"
        "q-signature=%s"
    ) % (
        secret_id,
        sign_time,
        key_time,
        header_list,
        ";".join(k for k, _ in sorted(urllib.parse.parse_qsl(query, keep_blank_values=True))),
        signature,
    )


def request_cos(method, path="/", query="", body=b"", extra_headers=None, ok=(200, 204)):
    secret_id = require_env("TENCENT_SECRET_ID")
    secret_key = require_env("TENCENT_SECRET_KEY")
    url = "https://%s%s%s" % (bucket_host(), path, ("?" + query) if query else "")
    headers = {
        "Host": bucket_host(),
        "Date": email.utils.formatdate(usegmt=True),
    }
    if extra_headers:
        headers.update(extra_headers)
    headers["Authorization"] = cos_authorization(method, path, query, headers, secret_id, secret_key)
    req = urllib.request.Request(url, data=body if method != "GET" else None, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            if resp.status not in ok:
                raise RuntimeError("Unexpected COS response %s: %s" % (resp.status, data.decode("utf-8", "ignore")))
            return resp.status, data
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        if exc.code in ok:
            return exc.code, detail.encode("utf-8")
        raise RuntimeError("COS %s %s failed: HTTP %s %s" % (method, path, exc.code, detail))


def create_bucket_if_needed():
    try:
        request_cos("HEAD", ok=(200,))
        print("Bucket exists: %s" % bucket_name())
        return
    except Exception:
        pass
    print("Creating bucket: %s" % bucket_name())
    request_cos("PUT", extra_headers={"x-cos-acl": "public-read"}, ok=(200,))


def configure_website():
    print("Configuring static website...")
    body = (
        "<WebsiteConfiguration>"
        "<IndexDocument><Suffix>index.html</Suffix></IndexDocument>"
        "<ErrorDocument><Key>index.html</Key></ErrorDocument>"
        "</WebsiteConfiguration>"
    ).encode("utf-8")
    request_cos(
        "PUT",
        query="website",
        body=body,
        extra_headers={"Content-Type": "application/xml", "Content-Length": str(len(body))},
        ok=(200,),
    )


def upload_index():
    if not os.path.exists(INDEX_FILE):
        raise RuntimeError("Missing frontend file: %s" % INDEX_FILE)
    with open(INDEX_FILE, "rb") as f:
        body = f.read()
    content_type = mimetypes.guess_type(INDEX_FILE)[0] or "text/html"
    print("Uploading %s (%d bytes)..." % (os.path.basename(INDEX_FILE), len(body)))
    request_cos(
        "PUT",
        path="/index.html",
        body=body,
        extra_headers={
            "Content-Type": content_type + "; charset=utf-8",
            "Content-Disposition": "inline",
            "Content-Length": str(len(body)),
            "Cache-Control": "no-cache",
            "x-cos-acl": "public-read",
        },
        ok=(200,),
    )


def main():
    require_env("TENCENT_SECRET_ID")
    require_env("TENCENT_SECRET_KEY")
    if not APP_ID:
        raise RuntimeError("Missing required environment variable: TENCENT_APP_ID")
    create_bucket_if_needed()
    configure_website()
    upload_index()
    print("\nFrontend deployed:")
    print(website_url())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Frontend deployment failed: %s" % exc, file=sys.stderr)
        sys.exit(1)
