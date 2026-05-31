.PHONY: install gates scrub publish smoke ai-gates shell-cron

OPENCLAW_DIR ?= $(HOME)/.openclaw

install:
	bash scripts/install-to-openclaw.sh --force

gates: scrub publish
	$(MAKE) ai-gates
	bash scripts/subaru-gates.sh --check

scrub:
	bash scripts/scrub-for-publish.sh

publish:
	bash scripts/publish-gates.sh

smoke:
	bash scripts/subaru-smoke.sh

ai-gates:
	bash scripts/openclaw-ai-gates.sh --check

shell-cron:
	OPENCLAW_SUBARU_ROOT=$$(pwd) python3 scripts/install-openclaw-shell-cron.sh
