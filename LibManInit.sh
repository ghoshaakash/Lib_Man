#!/usr/bin/env bash

set -e

repo_dir=$(CDPATH= cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
cd -- "$repo_dir"
uv sync --locked

zshrc="${ZDOTDIR:-$HOME}/.zshrc"
# Quote the script path for alias expansion, then quote the alias value itself.
printf -v command '%q' "$repo_dir/LibMan.sh"
alias_line="alias libman='${command//\'/\'\\\'\'}'"

current_alias=
if [[ -f "$zshrc" ]]; then
    current_alias=$(awk '/^[[:blank:]]*alias[[:blank:]]+libman=/ { line = $0 } END { print line }' "$zshrc")
fi
if [[ "$current_alias" != "$alias_line" ]]; then
    printf '\n%s\n' "$alias_line" >> "$zshrc"
fi

printf 'Run source %q to load the libman alias in your current Zsh session.\n' "$zshrc"
