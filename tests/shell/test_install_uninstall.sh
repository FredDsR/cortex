#!/usr/bin/env bash
# Round-trip coverage for install.sh + uninstall.sh.
# Every test runs against a temp HOME, so nothing touches the real install.
set -u
cd "$(dirname "$0")"
. ./lib.sh

INSTALL="$REPO/install.sh"
UNINSTALL="$REPO/uninstall.sh"

# install.sh treats "$HOME/.<harness>/ exists" as "user uses this harness", so
# creating only .claude keeps every assertion to one harness.
setup_claude_only() {
  setup_tmp
  mkdir -p "$TEST_HOME/.claude"
  # Pin the clone path. install.sh now auto-selects package mode when uv or
  # pip is present, and these assertions are about the checkout-and-symlink
  # install, which must keep working offline. Package mode is covered by
  # test_package_mode_delegates_to_the_engine below, with stubbed binaries.
  export CORTEX_INSTALL_MODE=clone
}

skills_dir() { echo "$1/.claude/skills"; }

test_project_install_then_uninstall() {
  setup_claude_only
  proj="$TEST_HOME/proj"; mkdir -p "$proj"

  bash "$INSTALL" --project "$proj" >/dev/null 2>&1
  assert_file_exists "$(skills_dir "$proj")/cortex-tracking"
  assert_file_exists "$(skills_dir "$proj")/cortex-viz"

  out="$(bash "$UNINSTALL" --project "$proj" 2>&1)"
  assert_contains "$out" "removed cortex-tracking"
  assert_file_absent "$(skills_dir "$proj")/cortex-tracking"
  assert_file_absent "$(skills_dir "$proj")/cortex-viz"
  teardown_tmp
}

test_uninstall_is_idempotent() {
  setup_claude_only
  proj="$TEST_HOME/proj"; mkdir -p "$proj"
  bash "$INSTALL" --project "$proj" >/dev/null 2>&1
  bash "$UNINSTALL" --project "$proj" >/dev/null 2>&1
  out="$(bash "$UNINSTALL" --project "$proj" 2>&1)"
  assert_contains "$out" "0 item(s) removed"
  teardown_tmp
}

test_real_directory_is_never_deleted() {
  setup_claude_only
  proj="$TEST_HOME/proj"; mkdir -p "$proj"
  bash "$INSTALL" --project "$proj" >/dev/null 2>&1

  # Someone else's real skill directory sitting where ours was.
  d="$(skills_dir "$proj")/cortex-kb"
  rm -f "$d"; mkdir -p "$d"; echo "mine" > "$d/SKILL.md"

  out="$(bash "$UNINSTALL" --project "$proj" 2>&1)"
  assert_file_exists "$d/SKILL.md"
  assert_contains "$out" "not a symlink"
  teardown_tmp
}

test_foreign_symlink_is_never_deleted() {
  setup_claude_only
  proj="$TEST_HOME/proj"; mkdir -p "$proj"
  bash "$INSTALL" --project "$proj" >/dev/null 2>&1

  # A symlink of the same name pointing at some other checkout.
  other="$TEST_HOME/other-cortex/skills/cortex-sync"
  mkdir -p "$other"
  ln -sfn "$other" "$(skills_dir "$proj")/cortex-sync"

  out="$(bash "$UNINSTALL" --project "$proj" 2>&1)"
  assert_file_exists "$(skills_dir "$proj")/cortex-sync"
  assert_contains "$out" "points outside this repo"
  teardown_tmp
}

test_dry_run_changes_nothing() {
  setup_claude_only
  proj="$TEST_HOME/proj"; mkdir -p "$proj"
  bash "$INSTALL" --project "$proj" >/dev/null 2>&1

  out="$(bash "$UNINSTALL" --project "$proj" --dry-run 2>&1)"
  assert_contains "$out" "would remove cortex-tracking"
  assert_contains "$out" "DRY RUN"
  assert_file_exists "$(skills_dir "$proj")/cortex-tracking"
  teardown_tmp
}

test_global_uninstall_removes_the_slash_command() {
  # The `cortex` bin is no longer installed here: the console script from the
  # installed package provides it. Only the slash command is install.sh's.
  setup_claude_only
  bash "$INSTALL" >/dev/null 2>&1
  assert_file_exists "$TEST_HOME/.claude/commands/close-day.md"

  bash "$UNINSTALL" >/dev/null 2>&1
  assert_file_absent "$TEST_HOME/.claude/commands/close-day.md"
  teardown_tmp
}

test_install_does_not_create_a_bin_symlink() {
  setup_claude_only
  bash "$INSTALL" >/dev/null 2>&1
  assert_file_absent "$TEST_HOME/.cortex/bin/cortex"
  teardown_tmp
}

test_store_data_survives_default_uninstall() {
  setup_claude_only
  bash "$INSTALL" >/dev/null 2>&1
  ws="$TEST_HOME/.cortex/workspaces/demo/sessions/s1"
  mkdir -p "$ws"
  echo "precious" > "$ws/SUMMARY.md"

  out="$(bash "$UNINSTALL" 2>&1)"
  assert_file_exists "$ws/SUMMARY.md"
  assert_contains "$out" "work data is untouched"
  teardown_tmp
}

test_purge_without_sync_refuses_single_yes() {
  setup_claude_only
  bash "$INSTALL" >/dev/null 2>&1
  ws="$TEST_HOME/.cortex/workspaces/demo"
  mkdir -p "$ws"
  echo "precious" > "$ws/note.md"

  out="$(bash "$UNINSTALL" --purge-store --yes 2>&1)"
  rc=$?
  assert_eq "$rc" "1" "should refuse"
  assert_file_exists "$ws/note.md"
  assert_contains "$out" "--yes --yes"
  teardown_tmp
}

test_purge_deletes_store_when_double_confirmed() {
  setup_claude_only
  bash "$INSTALL" >/dev/null 2>&1
  ws="$TEST_HOME/.cortex/workspaces/demo"
  mkdir -p "$ws"
  echo "precious" > "$ws/note.md"

  bash "$UNINSTALL" --purge-store --yes --yes >/dev/null 2>&1
  assert_file_absent "$ws/note.md"
  teardown_tmp
}

test_purge_dry_run_deletes_nothing() {
  setup_claude_only
  bash "$INSTALL" >/dev/null 2>&1
  ws="$TEST_HOME/.cortex/workspaces/demo"
  mkdir -p "$ws"
  echo "precious" > "$ws/note.md"

  out="$(bash "$UNINSTALL" --purge-store --dry-run 2>&1)"
  assert_file_exists "$ws/note.md"
  assert_contains "$out" "would delete"
  teardown_tmp
}

# --- piped install (curl | bash): install.sh clones, then re-runs on disk ----

test_piped_install_clones_and_installs() {
  setup_claude_only
  # Clone source is this repo's committed state; enough to prove the handoff.
  cat "$INSTALL" | CORTEX_DIR="$TEST_HOME/cortex" CORTEX_REPO="file://$REPO" \
    bash >/dev/null 2>&1
  assert_file_exists "$TEST_HOME/cortex/install.sh"
  assert_file_exists "$TEST_HOME/.claude/skills/cortex-tracking"
  teardown_tmp
}

test_piped_install_refuses_foreign_directory() {
  setup_claude_only
  mkdir -p "$TEST_HOME/notcortex"
  echo "important" > "$TEST_HOME/notcortex/thesis.txt"

  out="$(cat "$INSTALL" | CORTEX_DIR="$TEST_HOME/notcortex" \
    CORTEX_REPO="file://$REPO" bash 2>&1)"
  rc=$?
  assert_eq "$rc" "1" "should refuse to clobber"
  assert_contains "$out" "not a cortex checkout"
  assert_file_exists "$TEST_HOME/notcortex/thesis.txt"
  teardown_tmp
}

test_piped_install_updates_existing_checkout() {
  setup_claude_only
  cat "$INSTALL" | CORTEX_DIR="$TEST_HOME/cortex" CORTEX_REPO="file://$REPO" \
    bash >/dev/null 2>&1
  out="$(cat "$INSTALL" | CORTEX_DIR="$TEST_HOME/cortex" \
    CORTEX_REPO="file://$REPO" bash 2>&1)"
  assert_contains "$out" "updating existing checkout"
  teardown_tmp
}

# --- docs -------------------------------------------------------------------

test_package_mode_delegates_to_the_engine() {
  # Package mode's job is delegation: install the engine, then let it link the
  # skills. Stubbing uv and cortex keeps that assertion offline.
  setup_tmp
  mkdir -p "$TEST_HOME/.claude" "$TEST_HOME/stub"
  log="$TEST_HOME/calls.log"

  cat > "$TEST_HOME/stub/uv" <<STUB
#!/bin/sh
echo "uv \$*" >> "$log"
STUB
  cat > "$TEST_HOME/stub/cortex" <<STUB
#!/bin/sh
echo "cortex \$*" >> "$log"
[ "\$1" = "version" ] && echo "0.1.0"
exit 0
STUB
  chmod +x "$TEST_HOME/stub/uv" "$TEST_HOME/stub/cortex"

  PATH="$TEST_HOME/stub:$PATH" CORTEX_INSTALL_MODE=package \
    bash "$INSTALL" >/dev/null 2>&1

  calls="$(cat "$log")"
  # Read the name from the package rather than restating it, so a rename
  # cannot leave this asserting a distribution that no longer exists.
  dist="$(cd "$REPO" && python3 -c 'import sys; sys.path.insert(0,"src"); from cortex.install.cli import DISTRIBUTION_NAME as d; print(d)')"
  assert_contains "$calls" "uv tool install --force $dist"
  assert_contains "$calls" "cortex install-skills"
  teardown_tmp
}

test_package_mode_honours_cortex_spec() {
  setup_tmp
  mkdir -p "$TEST_HOME/.claude" "$TEST_HOME/stub"
  log="$TEST_HOME/calls.log"
  cat > "$TEST_HOME/stub/uv" <<STUB
#!/bin/sh
echo "uv \$*" >> "$log"
STUB
  cat > "$TEST_HOME/stub/cortex" <<STUB
#!/bin/sh
echo "cortex \$*" >> "$log"
exit 0
STUB
  chmod +x "$TEST_HOME/stub/uv" "$TEST_HOME/stub/cortex"

  PATH="$TEST_HOME/stub:$PATH" CORTEX_INSTALL_MODE=package \
    CORTEX_SPEC="/local/checkout" bash "$INSTALL" >/dev/null 2>&1

  assert_contains "$(cat "$log")" "uv tool install --force /local/checkout"
  teardown_tmp
}

test_package_mode_forwards_project_flag() {
  setup_tmp
  mkdir -p "$TEST_HOME/.claude" "$TEST_HOME/stub" "$TEST_HOME/proj"
  log="$TEST_HOME/calls.log"
  cat > "$TEST_HOME/stub/uv" <<STUB
#!/bin/sh
exit 0
STUB
  cat > "$TEST_HOME/stub/cortex" <<STUB
#!/bin/sh
echo "cortex \$*" >> "$log"
exit 0
STUB
  chmod +x "$TEST_HOME/stub/uv" "$TEST_HOME/stub/cortex"

  PATH="$TEST_HOME/stub:$PATH" CORTEX_INSTALL_MODE=package \
    bash "$INSTALL" --project "$TEST_HOME/proj" >/dev/null 2>&1

  assert_contains "$(cat "$log")" "cortex install-skills --project $TEST_HOME/proj"
  teardown_tmp
}

test_readme_documents_antigravity_install() {
  # CI-safe: asserts the command is documented without requiring `agy`.
  readme="$REPO/README.md"
  assert_contains "$(cat "$readme")" "agy plugin install"
  assert_contains "$(cat "$readme")" "### Antigravity"
}

test_readme_one_liner_matches_real_script() {
  # The documented curl URL must name a script that exists in the repo.
  readme="$(cat "$REPO/README.md")"
  assert_contains "$readme" "main/install.sh | bash"
  assert_not_contains "$readme" "bootstrap.sh"
  assert_file_exists "$REPO/install.sh"
}

test_docs_exist_and_are_linked() {
  # The README's docs table must point at files that exist.
  readme="$(cat "$REPO/README.md")"
  for d in README concepts skills cli store hooks-and-plugins; do
    assert_file_exists "$REPO/docs/$d.md"
    assert_contains "$readme" "docs/$d.md"
  done
}

test_docs_cli_verbs_are_real() {
  # Guards against documenting a verb that no longer exists, the way the
  # README once advertised `cortex viz --watch` after it was removed.
  cli="$(cat "$REPO/docs/cli.md")"
  for verb in "cortex kb new" "cortex kb ingest" "cortex viz build" \
              "cortex query neighbors" "cortex inject here" "cortex sync push"; do
    assert_contains "$cli" "$verb"
  done
  assert_not_contains "$cli" "--watch"
  assert_not_contains "$(cat "$REPO/README.md")" "--watch"
}

test_docs_mermaid_blocks_are_closed() {
  # Every ```mermaid fence must have a closing fence, or GitHub renders the
  # rest of the file as one code block.
  for f in "$REPO"/docs/*.md; do
    opens=$(grep -c '^```mermaid$' "$f" || true)
    total=$(grep -c '^```' "$f" || true)
    if [ "$opens" -gt 0 ]; then
      assert_eq "$(( total % 2 ))" "0" "unbalanced fences in $(basename "$f")"
    fi
  done
}

run_test test_project_install_then_uninstall
run_test test_uninstall_is_idempotent
run_test test_real_directory_is_never_deleted
run_test test_foreign_symlink_is_never_deleted
run_test test_dry_run_changes_nothing
run_test test_global_uninstall_removes_the_slash_command
run_test test_install_does_not_create_a_bin_symlink
run_test test_store_data_survives_default_uninstall
run_test test_purge_without_sync_refuses_single_yes
run_test test_purge_deletes_store_when_double_confirmed
run_test test_purge_dry_run_deletes_nothing
run_test test_piped_install_clones_and_installs
run_test test_piped_install_refuses_foreign_directory
run_test test_piped_install_updates_existing_checkout
run_test test_package_mode_delegates_to_the_engine
run_test test_package_mode_honours_cortex_spec
run_test test_package_mode_forwards_project_flag
run_test test_readme_documents_antigravity_install
run_test test_readme_one_liner_matches_real_script
run_test test_docs_exist_and_are_linked
run_test test_docs_cli_verbs_are_real
run_test test_docs_mermaid_blocks_are_closed
report
