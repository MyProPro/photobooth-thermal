import sys
sys.path.insert(0, '.')
import json
import urllib.request
import licensing

dev_id = licensing.device_id()
print("Device ID:", dev_id)

# Test 1: Reset PIN via /api/studio/reset-pin-license using device ID (or license key)
url = "http://127.0.0.1:5000/api/studio/reset-pin-license"
data = json.dumps({"licenseKey": dev_id}).encode()
req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
res = urllib.request.urlopen(req)
body = json.loads(res.read().decode())
print("Reset PIN response:", body)
assert body.get("ok") is True
assert body.get("pin") == "1234"

# Test 2: Login via /api/studio/login with the new PIN "1234"
login_url = "http://127.0.0.1:5000/api/studio/login"
req2 = urllib.request.Request(login_url, data=json.dumps({"pin": "1234"}).encode(), headers={"Content-Type": "application/json"})
res2 = urllib.request.urlopen(req2)
body2 = json.loads(res2.read().decode())
print("Login with new PIN response:", body2)
assert body2.get("ok") is True

# Test 3: Login directly with device ID / license key in the PIN field!
req3 = urllib.request.Request(login_url, data=json.dumps({"pin": dev_id}).encode(), headers={"Content-Type": "application/json"})
res3 = urllib.request.urlopen(req3)
body3 = json.loads(res3.read().decode())
print("Direct login with license key / device ID response:", body3)
assert body3.get("ok") is True

print("All tests passed successfully!")
