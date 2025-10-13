#!/usr/bin/env bash
# Persist shell history outside the home directory so it survives fixuid remaps.
export PROMPT_COMMAND='history -a'
export HISTFILE=/commandhistory/.bash_history
