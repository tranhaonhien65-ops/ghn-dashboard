#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "========================================================="
echo "   🚀 Đang khởi chạy GHN Operations Analytics Dashboard..."
echo "========================================================="

# Start backend server in background
python3 server.py 8080 &
SERVER_PID=$!

sleep 1

# Open browser automatically on Mac
if which open > /dev/null; then
    open "http://localhost:8080"
fi

echo "✅ Dashboard đang hoạt động tại: http://localhost:8080"
echo "👉 Hoặc mở trực tiếp tệp: $DIR/index.html"
echo "Bấm Ctrl + C để dừng máy chủ."

wait $SERVER_PID
