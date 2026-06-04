.PHONY: install gates gates-bridge scrub publish smoke ai-gates shell-cron bridge-gates feature-gates

OPENCLAW_DIR ?= $(HOME)/.openclaw

install:
	bash scripts/install-to-openclaw.sh --force

gates: scrub publish
	$(MAKE) ai-gates
	bash scripts/subaru-gates.sh --check

gates-bridge: bridge-gates

scrub:
	bash scripts/scrub-for-publish.sh

publish:
	bash scripts/publish-gates.sh

smoke:
	bash scripts/subaru-smoke.sh

feature-gates:
	bash scripts/subaru-feature-gates.sh

ai-gates:
	bash scripts/openclaw-ai-gates.sh --check

bridge-gates:
	bash scripts/subaru-bridge-gates.sh

shell-cron:
	OPENCLAW_SUBARU_ROOT=$$(pwd) python3 scripts/install-openclaw-shell-cron.sh
