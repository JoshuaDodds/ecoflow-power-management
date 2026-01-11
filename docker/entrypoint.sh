case "$SERVICE" in
  soc_bridge) python -u services/soc_bridge.py ;;
  policy_engine) python -u services/policy_engine.py ;;
  *) echo "Unknown SERVICE=$SERVICE"; exit 1 ;;
esac
