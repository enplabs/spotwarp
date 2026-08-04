#!/bin/bash
set -e

# Default backend verification server URL
SERVER_URL=${GPU_ACTION_SERVER_URL:-"https://gpu-action.com"}

echo "============================================="
echo "   GPU-Action Spot-Guard Bootstrapper v2.0"
echo "============================================="

if [ -z "$LICENSE_KEY" ]; then
    echo "⚠️ WARNING: LICENSE_KEY environment variable is not set."
    echo "⚠️ Spot-Instance Failover Guard is DISABLED."
    echo "⚠️ To enable protection, sign up at https://gpu-action.com"
    echo "============================================="
else
    echo "🔑 Verifying license key with $SERVER_URL..."
    # Simple curl check (follow redirects, silent, output to stdout)
    VERIFY_RESPONSE=$(curl -s -L -X POST \
        -H "Content-Type: application/json" \
        -d "{\"license_key\": \"$LICENSE_KEY\"}" \
        "$SERVER_URL/api/v1/verify_license")
    
    # Parse json for valid status using simple grep/python
    VALID=$(echo "$VERIFY_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('valid', False))" 2>/dev/null || echo "false")
    MESSAGE=$(echo "$VERIFY_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('message', ''))" 2>/dev/null || echo "")

    if [ "$VALID" = "True" ] || [ "$VALID" = "true" ]; then
        echo "✅ License verified successfully: $MESSAGE"
        echo "⚡ Starting GPU-Action Spot-Guard Daemon..."
        
        # Start daemon in background (assumes vast/runpod api keys are set in environment)
        gpu-action start --license-key "$LICENSE_KEY" > /var/log/gpu-action-guard.log 2>&1 &
        echo "🛡️ Spot-Instance Failover Guard is now running in the background."
        echo "🛡️ Log file: /var/log/gpu-action-guard.log"
    else
        echo "❌ License verification failed: $MESSAGE"
        echo "⚠️ Spot-Instance Failover Guard is DISABLED."
    fi
    echo "============================================="
fi

# Execute main workspace command (e.g. Jupyter or custom CMD)
if [ $# -eq 0 ]; then
    echo "🚀 Starting Jupyter Notebook..."
    # Check if jupyter is installed, fallback to bash if not
    if command -v jupyter &> /dev/null; then
        exec jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root --NotebookApp.token='' --NotebookApp.password=''
    else
        echo "Jupyter not found. Dropping to bash..."
        exec /bin/bash
    fi
else
    echo "🚀 Executing custom command: $@"
    exec "$@"
fi
