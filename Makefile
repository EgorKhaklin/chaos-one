# Root-level Makefile — convenience wrappers around the backend and Unity
# pipelines. Use `make` inside `backend/` for backend-specific targets.

.PHONY: help backend-package unity-app full-launcher clean-builds

help:
	@echo "Chaos One — root convenience targets"
	@echo ""
	@echo "  make backend-package   Build the chaos-one launcher binary (delegates to backend/)"
	@echo "  make unity-app         Build the Unity .app via unity/build.sh (needs Unity Hub)"
	@echo "  make full-launcher     Backend binary + Unity .app, packaged together under dist/"
	@echo "  make clean-builds      Remove backend/dist, unity/dist, and root dist/"
	@echo ""
	@echo "For development, use targets under backend/ — see backend/Makefile."

backend-package:
	$(MAKE) -C backend package

unity-app:
	bash unity/build.sh --output unity/dist/ChaosOne.app

full-launcher: backend-package unity-app
	mkdir -p dist/unity-build
	cp -R backend/dist/chaos-one dist/chaos-one
	cp -R "unity/dist/ChaosOne.app" dist/unity-build/
	@echo ""
	@echo "[full-launcher] dist/chaos-one will discover dist/unity-build/ChaosOne.app on launch."
	@ls -lh dist/

clean-builds:
	rm -rf backend/dist backend/build unity/dist dist
