SHELL := /bin/zsh

.PHONY: supa-env supa-ping supa-reset supa-seed

supa-env:
	cd backend && export $$(cat .env.supabase | xargs)

supa-ping:
	cd backend && export $$(cat .env.supabase | xargs) && poetry run python -m do_not_call.cli ping

supa-reset:
	cd backend && export $$(cat .env.supabase | xargs) && poetry run python -m do_not_call.cli reset

supa-seed:
	cd backend && export $$(cat .env.supabase | xargs) && poetry run python -m do_not_call.cli seed


