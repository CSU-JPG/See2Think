
LOG_DIR="/storage/v-jinpewang/yansiyu_workspace/See2Think/logs"

mkdir -p $LOG_DIR

echo "NAME FROM ENV: $NAME"

echo "AGE FROM ENV: $AGE"

echo "simple test" > "$LOG_DIR/simple.txt"
