#!/bin/sh
# Run the dashboard checks. Usage:  tests/run_checks.sh [math|guard|all|quick]
#   math   every number on every page against an independent model of the rules (scenarios: normal, overtime, under-logging, leave, over capacity, sprint over, not started)
#   guard  layout, alignment of every (i) button, no sideways scroll at phone/tablet/desktop widths, wording, relay and refresh safety
#   all    math + guard + everything else (default)
#   quick  math only, the fastest useful check after a change to numbers
# Needs DASH_PASSWORD (the team password) for the sign-in tests; set DASH_PASSWORD=x to skip those that type the password.
cd "$(dirname "$0")/.." || exit 1
PY="${PYTHON:-python3}"
case "${1:-all}" in
  math|quick) SEL="-m math" ;;
  guard) SEL="-m guard" ;;
  all) SEL="" ;;
  *) echo "usage: $0 [math|guard|all|quick]"; exit 2 ;;
esac
echo "Running: ${1:-all} checks (see tests/CHECKLIST.md for what each protects)"
"$PY" -m pytest tests $SEL -q --tb=short -p no:cacheprovider
status=$?
[ $status -eq 0 ] && echo "ALL CHECKS PASSED" || echo "CHECKS FAILED: do not deploy"
exit $status
