.PHONY: install up down migrate qdrant embedding-service api desktop mobile-check index index-json run doctor eval-rag test

install:
	.venv/bin/python -m pip install -e 'backend[dev]'

up:
	./scripts/dev_services.sh up

down:
	./scripts/dev_services.sh down

migrate:
	cd backend && ../.venv/bin/alembic upgrade head

qdrant:
	docker start interview-agent-qdrant || docker run -d --name interview-agent-qdrant -p 6333:6333 -p 6334:6334 -v qdrant_storage:/qdrant/storage qdrant/qdrant

embedding-service:
	./interview embedding-service

api:
	./interview api

desktop:
	npm --prefix apps/desktop run build
	npm --prefix apps/desktop run desktop

mobile-check:
	npm --prefix apps/miniapp run check
	test -f apps/ios/InterviewAgent.xcodeproj/project.pbxproj
	test -f apps/ios/InterviewAgent/Info.plist
	test -f apps/ios/Sources/InterviewAgent/InterviewAgentApp.swift
	test -f apps/android/settings.gradle.kts
	test -f apps/android/app/build.gradle.kts
	test -x apps/android/gradlew
	test -f apps/android/gradle/wrapper/gradle-wrapper.jar
	test -f apps/android/app/src/main/java/com/interviewagent/MainActivity.kt
	test -f apps/harmony/AppScope/app.json5
	test -f apps/harmony/build-profile.json5
	test -f apps/harmony/entry/build-profile.json5
	test -f apps/harmony/entry/src/main/ets/pages/Index.ets

index:
	./interview index --embeddings --embedding-provider service --vector-store qdrant

index-json:
	./interview index --embeddings --embedding-provider local --vector-store json

run:
	./interview

doctor:
	./interview doctor

eval-rag:
	./interview eval-rag

test:
	cd backend && ../.venv/bin/python -m pytest
