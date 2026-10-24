#!/usr/bin/env bash
# Re-encrypt the app page with the same look and salt as the published one.
set -euo pipefail
src="$1"; outdir="$2"
npx -y staticrypt@3.5.4 "$src" -p "$APP_PASSWORD" --short -d "$outdir" --salt 396281142d1ad3157494c4075d3f2196 \
  --template-title "MOC สายงาน 660 · 705" --template-instructions "ใส่รหัสผ่านเพื่อดูผลงานทีม" --template-placeholder "รหัสผ่าน" \
  --template-button "เข้าดู" --template-remember "จำรหัสไว้ในเครื่องนี้" --template-error "รหัสไม่ถูกต้อง ลองใหม่อีกครั้ง" \
  --template-color-primary "#0d5c63" --template-color-secondary "#f3f5f7" --remember 30
