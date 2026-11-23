#!/usr/bin/env bash

# A command on PATH may be a symlink into the checkout.
script_path=${BASH_SOURCE[0]}
while [[ -L "$script_path" ]]; do
    target=$(readlink -- "$script_path") || exit 1
    case "$target" in
        /*) script_path=$target ;;
        *) script_path=$(dirname -- "$script_path")/$target ;;
    esac
done

repo_dir=$(CDPATH= cd -P -- "$(dirname -- "$script_path")" && pwd -P) || exit 1
python="$repo_dir/.venv/bin/python"
if [[ ! -x "$python" ]]; then
    printf 'Run uv sync --locked in %s to set up LibMan.\n' "$repo_dir" >&2
    exit 1
fi

export PYTHONPATH="$repo_dir/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$python" -P -u -m lib_man.launcher "$@"

