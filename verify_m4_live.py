import urllib.request
import json
import time

url_dash = "https://grand-horizon-pms.vercel.app/api/housekeeping/dashboard"
url_tasks = "https://grand-horizon-pms.vercel.app/api/housekeeping/tasks"

print("Checking live endpoints...", flush=True)
for attempt in range(1, 10):
    try:
        req = urllib.request.Request(url_dash, headers={"User-Agent": "Antigravity/1.0"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            print(f"Attempt {attempt} SUCCESS! Dashboard data:", flush=True)
            print(json.dumps(data, indent=2), flush=True)
            
        req2 = urllib.request.Request(url_tasks, headers={"User-Agent": "Antigravity/1.0"})
        with urllib.request.urlopen(req2) as resp2:
            tasks = json.loads(resp2.read().decode())
            print(f"Tasks count: {len(tasks)}", flush=True)
            if tasks:
                print(f"Sample task: {tasks[0]}", flush=True)
        break
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Attempt {attempt} HTTP {e.code}: {body}", flush=True)
    except Exception as e:
        print(f"Attempt {attempt} Error: {e}", flush=True)
    time.sleep(3)
