#!/usr/bin/env bash
# Shared test helpers. Source from each test_*.sh.

set -u

_pass=0
_fail=0
_current_test=""

assert_eq() {
  local actual="$1" expected="$2" msg="${3:-}"
  if [ "$actual" = "$expected" ]; then
    _pass=$((_pass + 1))
  else
    _fail=$((_fail + 1))
    echo "  FAIL: ${_current_test} ${msg}"
    echo "    expected: '${expected}'"
    echo "    actual:   '${actual}'"
  fi
}

assert_contains() {
  local haystack="$1" needle="$2" msg="${3:-}"
  if [[ "$haystack" == *"$needle"* ]]; then
    _pass=$((_pass + 1))
  else
    _fail=$((_fail + 1))
    echo "  FAIL: ${_current_test} ${msg}"
    echo "    expected substring: '${needle}'"
    echo "    in:                 '${haystack}'"
  fi
}

assert_not_contains() {
  local haystack="$1" needle="$2" msg="${3:-}"
  if [[ "$haystack" != *"$needle"* ]]; then
    _pass=$((_pass + 1))
  else
    _fail=$((_fail + 1))
    echo "  FAIL: ${_current_test} ${msg}"
    echo "    unexpected substring: '${needle}'"
    echo "    in:                   '${haystack}'"
  fi
}

assert_file_exists() {
  local path="$1" msg="${2:-}"
  if [ -e "$path" ]; then
    _pass=$((_pass + 1))
  else
    _fail=$((_fail + 1))
    echo "  FAIL: ${_current_test} file missing: $path ${msg}"
  fi
}

assert_file_absent() {
  local path="$1" msg="${2:-}"
  if [ ! -e "$path" ]; then
    _pass=$((_pass + 1))
  else
    _fail=$((_fail + 1))
    echo "  FAIL: ${_current_test} file should not exist: $path ${msg}"
  fi
}

run_test() {
  _current_test="$1"
  echo "  - $_current_test"
  "$_current_test"
}

report() {
  echo "Passed: $_pass"
  echo "Failed: $_fail"
  if [ "$_fail" -gt 0 ]; then return 1; fi
  return 0
}

setup_tmp() {
  TEST_HOME="$(mktemp -d)"
  TEST_CWD="$TEST_HOME/cwd"
  mkdir -p "$TEST_CWD"
  export HOME="$TEST_HOME"
  export XDG_RUNTIME_DIR="$TEST_HOME/run"
  mkdir -p "$XDG_RUNTIME_DIR"
}

teardown_tmp() {
  [ -n "${TEST_HOME:-}" ] && rm -rf "$TEST_HOME"
  unset TEST_HOME TEST_CWD
}
