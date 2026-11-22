#!/bin/sh
# One-line install:
#   curl -fsSL https://raw.githubusercontent.com/ShulkwiSEC/ImportFromMyHarness/main/install.sh | sh
# Flags (after `sh -s --`): -y  answer yes to everything   --no-setup  install only
# Env: IFMH_SOURCE=<pip/git/path spec>  override what gets installed
set -eu

SRC="${IFMH_SOURCE:-git+https://github.com/ShulkwiSEC/ImportFromMyHarness}"
YES=0; SETUP=1
for a in "$@"; do
  case "$a" in -y|--yes) YES=1 ;; --no-setup) SETUP=0 ;; *) echo "unknown option: $a" >&2; exit 2 ;; esac
done

if [ -t 2 ] && [ -z "${NO_COLOR:-}" ]; then B='\033[1m'; G='\033[32m'; Y='\033[33m'; D='\033[2m'; N='\033[0m'; else B=; G=; Y=; D=; N=; fi
say()  { printf "${B}==>${N} %s\n" "$*" >&2; }
ok()   { printf "${G}ok${N}  %s\n" "$*" >&2; }
warn() { printf "${Y}!!${N}  %s\n" "$*" >&2; }
die()  { printf "error: %s\n" "$*" >&2; exit 1; }

# yes/no that works under `curl | sh` (stdin is the script, so read the terminal)
confirm() {
  [ "$YES" = 1 ] && return 0
  if [ -r /dev/tty ]; then
    printf "%s [y/N] " "$1" >&2; read -r ans </dev/tty || return 1
    case "$ans" in y|Y|yes) return 0 ;; *) return 1 ;; esac
  fi
  die "no terminal to ask '$1'. Re-run with: ... | sh -s -- -y"
}

printf "\n${B}ImportFromMyHarness${N} ${D}bring your whole harness with you${N}\n\n" >&2
say "This will: (1) make sure uv is installed  (2) install importfrommyharness as a tool  (3) offer a guided first run."
say "Nothing needs sudo. Re-running upgrades in place."

export PATH="$HOME/.local/bin:$PATH"
if command -v uv >/dev/null 2>&1; then
  ok "uv found ($(uv --version))"
else
  confirm "uv (the Python tool runner) is missing. Install it from astral.sh?" || die "uv is required: https://docs.astral.sh/uv/"
  command -v curl >/dev/null 2>&1 || die "curl is needed to install uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh >&2 || die "uv install failed"
  ok "uv installed"
fi

say "Installing importfrommyharness"
uv tool install --force "$SRC" >&2 || die "install failed. Try: uv tool install '$SRC'"
command -v importfrommyharness >/dev/null 2>&1 || die "installed, but not on PATH. Add: export PATH=\"\$HOME/.local/bin:\$PATH\""
ok "$(importfrommyharness --version)"

if [ "$SETUP" = 1 ] && [ -r /dev/tty ] && [ "$YES" = 0 ]; then
  confirm "Run the guided setup now?" && exec importfrommyharness setup </dev/tty
fi
printf "\nNext: ${B}importfrommyharness setup${N}  (guided)   or   ${B}importfrommyharness --help${N}\n" >&2
