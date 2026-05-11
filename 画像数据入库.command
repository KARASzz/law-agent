#!/bin/bash

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORK_DIR="$ROOT_DIR/law_agent/profile_ingestion"
INPUT_DIR="$WORK_DIR/input"
OUTPUT_DIR="$WORK_DIR/output"
CONFIG_FILE="$WORK_DIR/config.json"
CLIENT_PROFILE_DB="$ROOT_DIR/data/client_profiles.db"
CANDIDATE_DB="$ROOT_DIR/data/profile_candidates.db"
USE_MODEL="false"
LAST_ERROR=0
INPUT_FILE=""

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_CMD="$ROOT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="$(command -v python3)"
else
  PYTHON_CMD="$(command -v python)"
fi

mkdir -p "$INPUT_DIR" "$OUTPUT_DIR" "$ROOT_DIR/data"

run_py() {
  PYTHONPATH="$ROOT_DIR" "$PYTHON_CMD" -m law_agent.profile_pipeline "$@"
}

pause_screen() {
  echo
  read -r -p "Press Enter to continue..." _
}

find_by_keyword() {
  local keyword="$1"
  local file base
  INPUT_FILE=""
  for file in "$INPUT_DIR"/*.xlsx; do
    [[ -e "$file" ]] || continue
    base="$(basename "$file")"
    [[ "$base" == "~$"* ]] && continue
    if [[ "$base" == *"$keyword"* ]]; then
      INPUT_FILE="$file"
      return 0
    fi
  done
  return 1
}

choose_excel() {
  local files=()
  local file base idx choice
  INPUT_FILE=""

  while IFS= read -r -d '' file; do
    files+=("$file")
  done < <(find "$INPUT_DIR" -maxdepth 1 -type f -name "*.xlsx" ! -name "~$*" -print0 | sort -z)

  if [[ "${#files[@]}" -eq 0 ]]; then
    echo
    echo "[WARN] No usable .xlsx files found in input folder."
    sleep 2
    return 1
  fi

  idx=1
  for file in "${files[@]}"; do
    echo "  [$idx] $(basename "$file")"
    idx=$((idx + 1))
  done

  echo
  read -r -p "Input file number, or press Enter to return: " choice
  [[ -z "$choice" ]] && return 1
  if ! [[ "$choice" =~ ^[0-9]+$ ]] || [[ "$choice" -lt 1 ]] || [[ "$choice" -gt "${#files[@]}" ]]; then
    echo
    echo "[WARN] Invalid file number."
    sleep 2
    return 1
  fi

  INPUT_FILE="${files[$((choice - 1))]}"
  return 0
}

run_clean_profile() {
  local import_after_clean="$1"
  echo
  echo "[INPUT ] $INPUT_FILE"
  echo "[OUTPUT] $OUTPUT_DIR"
  if [[ "$import_after_clean" == "true" ]]; then
    echo "[DB    ] $CLIENT_PROFILE_DB"
  fi
  echo
  echo "[RUN] Cleaning official profile workbook..."

  if [[ "$import_after_clean" == "true" ]]; then
    run_py clean-profile \
      --input "$INPUT_FILE" \
      --output-dir "$OUTPUT_DIR" \
      --config "$CONFIG_FILE" \
      --use-model "$USE_MODEL" \
      --import-db "$CLIENT_PROFILE_DB"
  else
    run_py clean-profile \
      --input "$INPUT_FILE" \
      --output-dir "$OUTPUT_DIR" \
      --config "$CONFIG_FILE" \
      --use-model "$USE_MODEL"
  fi
  LAST_ERROR=$?
}

run_assistant() {
  if ! find_by_keyword "助理"; then
    echo
    echo "[WARN] Assistant table not found by keyword. Choose manually."
    echo
    choose_excel || return
  fi

  echo
  echo "[INPUT ] $INPUT_FILE"
  echo "[OUTPUT] $OUTPUT_DIR"
  echo "[DB    ] $CANDIDATE_DB"
  echo
  echo "[RUN] Cleaning assistant workbook to candidate pool..."
  run_py clean-assistant \
    --input "$INPUT_FILE" \
    --output-dir "$OUTPUT_DIR" \
    --config "$CONFIG_FILE" \
    --candidate-db "$CANDIDATE_DB"
  LAST_ERROR=$?
}

promote_candidates() {
  clear
  echo "+---------------- Promote Candidates ----------------+"
  echo "Candidate DB: $CANDIDATE_DB"
  echo "Profile DB:   $CLIENT_PROFILE_DB"
  echo "+----------------------------------------------------+"
  echo
  run_py list-candidates \
    --config "$CONFIG_FILE" \
    --candidate-db "$CANDIDATE_DB" \
    --promotion-status "not_promoted" \
    --limit 20
  echo
  echo "Type candidate ids separated by comma, type ALL for all pass candidates,"
  echo "or press Enter to return."
  echo
  read -r -p "Candidates: " candidate_ids
  [[ -z "$candidate_ids" ]] && return

  upper_candidate_ids="$(printf "%s" "$candidate_ids" | tr "[:lower:]" "[:upper:]")"
  if [[ "$upper_candidate_ids" == "ALL" ]]; then
    run_py promote-candidates \
      --config "$CONFIG_FILE" \
      --candidate-db "$CANDIDATE_DB" \
      --client-profile-db "$CLIENT_PROFILE_DB" \
      --output-dir "$OUTPUT_DIR" \
      --all-pass
  else
    run_py promote-candidates \
      --config "$CONFIG_FILE" \
      --candidate-db "$CANDIDATE_DB" \
      --client-profile-db "$CLIENT_PROFILE_DB" \
      --output-dir "$OUTPUT_DIR" \
      --candidate-ids "$candidate_ids"
  fi
  LAST_ERROR=$?
}

candidate_stats() {
  echo
  run_py candidate-stats --config "$CONFIG_FILE" --candidate-db "$CANDIDATE_DB"
  LAST_ERROR=$?
}

show_latest() {
  echo
  echo "Latest output file:"
  echo
  latest=""
  for file in "$OUTPUT_DIR"/*.json; do
    [[ -e "$file" ]] || continue
    if [[ -z "$latest" || "$file" -nt "$latest" ]]; then
      latest="$file"
    fi
  done
  if [[ -n "$latest" ]]; then
    echo "  $latest"
    LAST_ERROR=0
  else
    echo "[WARN] No JSON output file found."
    LAST_ERROR=1
  fi
}

diagnostics() {
  while true; do
    clear
    echo "+---------------- Diagnostics ----------------------+"
    echo "|  [1] Python and dependency check                 |"
    echo "|  [2] List input files                            |"
    echo "|  [3] Python module syntax check                  |"
    echo "|  [0] Return                                      |"
    echo "+---------------------------------------------------+"
    echo
    read -r -p "Input number and press Enter: " diag_opt
    case "$diag_opt" in
      1)
        echo
        "$PYTHON_CMD" --version
        "$PYTHON_CMD" -m pip --version
        PYTHONPATH="$ROOT_DIR" "$PYTHON_CMD" -c "import openpyxl; import law_agent.profile_pipeline; print('openpyxl', openpyxl.__version__); print('profile_pipeline ok')"
        LAST_ERROR=$?
        return
        ;;
      2)
        echo
        echo "input folder:"
        echo
        find "$INPUT_DIR" -maxdepth 1 -type f -name "*.xlsx" ! -name "~$*" -print
        LAST_ERROR=$?
        return
        ;;
      3)
        echo
        "$PYTHON_CMD" -m py_compile "$ROOT_DIR/law_agent/profile_pipeline.py" && \
          "$PYTHON_CMD" -m py_compile "$WORK_DIR/clean_to_json.py"
        LAST_ERROR=$?
        return
        ;;
      0)
        return
        ;;
      *)
        echo
        echo "[WARN] Invalid input. Please choose 0-3."
        sleep 2
        ;;
    esac
  done
}

finish_action() {
  echo
  echo "---------------------------------------"
  if [[ "$LAST_ERROR" -eq 0 ]]; then
    echo "[DONE] Task completed."
  else
    echo "[ERROR] Task failed. Exit code: $LAST_ERROR"
  fi
  LAST_ERROR=0
  pause_screen
}

while true; do
  clear
  echo "============================================================"
  echo "                 Law Agent Profile Pipeline"
  echo "============================================================"
  echo
  echo "Project root: $ROOT_DIR"
  echo "Work dir:     $WORK_DIR"
  echo "Python:       $PYTHON_CMD"
  echo
  echo "+---------------- Official Profile ----------------+"
  echo "|  [1] Clean user template                         |"
  echo "|  [2] Clean developer template                    |"
  echo "|  [3] Choose Excel file manually                  |"
  echo "|  [4] Clean chosen file and import to DB          |"
  echo "+---------------- Assistant Candidates ------------+"
  echo "|  [5] Clean assistant table to candidate pool     |"
  echo "|  [6] Promote candidates to official profile DB   |"
  echo "|  [7] Candidate pool stats                        |"
  echo "+---------------- Helper Tools --------------------+"
  echo "|  [8] Show latest output file                     |"
  echo "|  [9] Diagnostics                                 |"
  echo "|  [0] Exit                                        |"
  echo "+--------------------------------------------------+"
  echo
  read -r -p "Input number and press Enter: " opt

  case "$opt" in
    1)
      find_by_keyword "用户填写版" || { echo; echo "[WARN] User template not found in input folder."; sleep 2; continue; }
      run_clean_profile false
      finish_action
      ;;
    2)
      find_by_keyword "开发版" || { echo; echo "[WARN] Developer template not found in input folder."; sleep 2; continue; }
      run_clean_profile false
      finish_action
      ;;
    3)
      clear
      echo "+---------------- Choose Profile Excel File ----------------+"
      echo "  Excel lock files starting with ~$ are hidden."
      echo "+-----------------------------------------------------------+"
      echo
      choose_excel && run_clean_profile false && finish_action
      ;;
    4)
      clear
      echo "+---------------- Choose Profile Excel File ----------------+"
      echo "  Excel lock files starting with ~$ are hidden."
      echo "+-----------------------------------------------------------+"
      echo
      choose_excel && run_clean_profile true && finish_action
      ;;
    5)
      run_assistant
      finish_action
      ;;
    6)
      promote_candidates
      finish_action
      ;;
    7)
      candidate_stats
      finish_action
      ;;
    8)
      show_latest
      finish_action
      ;;
    9)
      diagnostics
      finish_action
      ;;
    0)
      exit 0
      ;;
    *)
      echo
      echo "[WARN] Invalid input. Please choose 0-9."
      sleep 2
      ;;
  esac
done
