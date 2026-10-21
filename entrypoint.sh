#!/bin/bash
set -e

SERVER_URL=${GPU_ACTION_SERVER_URL:-"https://gpu-action.com"}
LICENSE_VAL=${LICENSE_KEY:-"SALAD-TRIAL"}

echo "=========================================================="
echo "   SpotWarp Fault-Tolerance Container v3.5.2 (SaladCloud)"
echo "=========================================================="

mkdir -p /workspace/checkpoints

if [ "$LICENSE_VAL" = "SALAD-TRIAL" ] || [ -z "$LICENSE_KEY" ]; then
    echo "🟢 Zero-Friction Onboarding: 14-Day SaladCloud Evaluation Mode ACTIVE."
    echo "🛡️ Workspace directory ready at: /workspace/checkpoints"
    echo "💡 To enable local delta-backup & Same-Cloud (Salad -> Salad) failover"
    echo "   from your workstation, run:"
    echo "     pip install spotwarp"
    echo "     spotwarp start --org <YOUR_SALAD_ORG> -d"
    echo "🔑 Upgrade to an unlimited license anytime at: https://gpu-action.com"
else
    echo "🔑 Verifying license key (Twelve-Factor Env) with $SERVER_URL..."
    VERIFY_RESPONSE=$(curl -s -L -X POST \
        -H "Content-Type: application/json" \
        -d "{\"license_key\": \"$LICENSE_KEY\"}" \
        "$SERVER_URL/api/v1/verify_license" || echo "{}")

    VALID=$(echo "$VERIFY_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('valid', False))" 2>/dev/null || echo "false")
    MESSAGE=$(echo "$VERIFY_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('message', ''))" 2>/dev/null || echo "")

    if [ "$VALID" = "True" ] || [ "$VALID" = "true" ]; then
        echo "✅ License verified: $MESSAGE"
        echo "🛡️ SpotWarp SaladCloud Protection Ready (/workspace/checkpoints)."
    else
        echo "⚠️ License key not recognized ($MESSAGE) — falling back to 14-Day SaladCloud Evaluation Mode."
    fi
fi
echo "=========================================================="

# Execute main workspace command (Jupyter Notebook on port 8888 or custom training script)
if [ $# -eq 0 ]; then
    echo "🚀 Starting Jupyter Server on port 8888..."
    if command -v jupyter &> /dev/null; then
        if [ -z "$JUPYTER_TOKEN" ]; then
            JUPYTER_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(24))")
            echo "🔐 Generated session JUPYTER_TOKEN: $JUPYTER_TOKEN"
        fi
        exec jupyter notebook --ip=:: --port=8888 --no-browser --allow-root --NotebookApp.token="$JUPYTER_TOKEN"
    else
        exec /bin/bash
    fi
else
    echo "🚀 Executing training workload: $@"
    exec "$@"
fi
