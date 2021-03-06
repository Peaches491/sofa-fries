#! /usr/bin/env bash

set -euo pipefail

function errecho() {
  (>&2 echo "$@")
}

(
  script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
  venv_dir="$script_dir/venv"

  if [ ! -a "$script_dir" ]; then
    errecho "Virtualenv directory \"$venv_dir\" not found"
  fi
  PS1="" source "$script_dir/venv/bin/activate"

  echo "Updating requirements..."
  requirements_file="$script_dir/requirements.txt"
  pip freeze -r "$requirements_file" > "$requirements_file"
  echo "Done."
)
