from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_all_mobile_clients_expose_the_five_product_workspaces() -> None:
    android = (ROOT / "apps/android/app/src/main/java/com/interviewagent/ui/InterviewApp.kt").read_text()
    ios = (ROOT / "apps/ios/Sources/InterviewAgent/RootView.swift").read_text()
    harmony = (ROOT / "apps/harmony/entry/src/main/ets/pages/Index.ets").read_text()
    miniapp = json.loads((ROOT / "apps/miniapp/miniprogram/app.json").read_text())
    for label in ("今日", "面试", "刷题", "复习", "我的"):
        assert label in android
        assert label in ios
        assert label in harmony
    assert [item["text"] for item in miniapp["tabBar"]["list"]] == ["今日", "面试", "刷题", "复习", "我的"]


def test_mobile_entry_points_gate_private_workspaces_behind_authentication() -> None:
    files_and_markers = {
        "apps/android/app/src/main/java/com/interviewagent/ui/InterviewApp.kt": "state.account == null",
        "apps/ios/Sources/InterviewAgent/RootView.swift": "!viewModel.isAuthenticated",
        "apps/harmony/entry/src/main/ets/pages/Index.ets": "!this.store.authenticated",
        "apps/miniapp/miniprogram/pages/today/today.wxml": "!authenticated",
        "apps/miniapp/miniprogram/pages/chat/chat.wxml": "!authenticated",
        "apps/miniapp/miniprogram/pages/practice/practice.wxml": "!authenticated",
        "apps/miniapp/miniprogram/pages/review/review.wxml": "!authenticated",
    }
    for relative_path, marker in files_and_markers.items():
        assert marker in (ROOT / relative_path).read_text(), relative_path


def test_customer_facing_mobile_views_hide_internal_controls() -> None:
    roots_and_patterns = [
        (ROOT / "apps/android/app/src/main/java/com/interviewagent/ui", "*Screen.kt"),
        (ROOT / "apps/android/app/src/main/java/com/interviewagent/ui", "InterviewApp.kt"),
        (ROOT / "apps/ios/Sources/InterviewAgent", "*View.swift"),
        (ROOT / "apps/harmony/entry/src/main/ets/pages", "*.ets"),
        (ROOT / "apps/miniapp/miniprogram/pages", "*.wxml"),
    ]
    sources = "\n".join(
        path.read_text()
        for root, pattern in roots_and_patterns
        for path in root.rglob(pattern)
        if path.is_file()
    )
    for forbidden in ("开发登录", "access_token", "API Key", "租户：", "Embedding：", "对象存储：", "内部提示词"):
        assert forbidden not in sources


def test_harmony_product_is_split_by_responsibility() -> None:
    harmony = ROOT / "apps/harmony/entry/src/main/ets"
    expected = [
        "state/AuthSession.ets", "state/ProductStore.ets", "network/InterviewApiClient.ets", "model/Models.ets",
        "pages/AuthGate.ets", "pages/TodayPage.ets", "pages/InterviewPage.ets", "pages/PracticePage.ets",
        "pages/ReviewPage.ets", "pages/MinePage.ets",
    ]
    assert all((harmony / relative).is_file() for relative in expected)
    assert len((harmony / "pages/Index.ets").read_text().splitlines()) < 100


def test_all_mobile_clients_send_platform_version_and_request_identity() -> None:
    clients = {
        "android": ROOT / "apps/android/app/src/main/java/com/interviewagent/data/InterviewApiClient.kt",
        "ios": ROOT / "apps/ios/Sources/InterviewAgent/InterviewApiClient.swift",
        "harmony": ROOT / "apps/harmony/entry/src/main/ets/network/InterviewApiClient.ets",
        "miniapp": ROOT / "apps/miniapp/miniprogram/utils/api.js",
    }
    for platform, path in clients.items():
        source = path.read_text()
        assert "X-Client-Platform" in source, platform
        assert "X-Client-Version" in source, platform
        assert "X-Client-Request-Id" in source, platform
        assert "X-Request-ID" in source, platform
        assert f'"{platform}"' in source or f"'{platform}'" in source, platform


def test_today_task_cards_open_business_content_on_every_client() -> None:
    contracts = {
        "android": (
            ROOT / "apps/android/app/src/main/java/com/interviewagent/ui/TodayScreen.kt",
            ["onOpenTask", "onClick = { onOpenTask(task) }"],
        ),
        "ios": (
            ROOT / "apps/ios/Sources/InterviewAgent/TodayWorkspaceView.swift",
            ["openTask", "Button { openTask(task) } label:"],
        ),
        "harmony": (
            ROOT / "apps/harmony/entry/src/main/ets/pages/TodayPage.ets",
            ["onOpenTask", ".onClick(() => this.onOpenTask(task))"],
        ),
        "miniapp": (
            ROOT / "apps/miniapp/miniprogram/pages/today/today.wxml",
            ["bindtap=\"openTaskCard\"", "catchtap=\"runTask\""],
        ),
    }
    for platform, (path, markers) in contracts.items():
        source = path.read_text()
        for marker in markers:
            assert marker in source, f"{platform}: {marker}"


def test_native_clients_model_server_task_targets() -> None:
    sources = {
        "android": ROOT / "apps/android/app/src/main/java/com/interviewagent/data/Models.kt",
        "ios": ROOT / "apps/ios/Sources/InterviewAgent/ProductModels.swift",
        "harmony": ROOT / "apps/harmony/entry/src/main/ets/model/Models.ets",
    }
    for platform, path in sources.items():
        source = path.read_text()
        assert "plan" in source.lower(), platform
        assert "day" in source.lower(), platform
        assert "task" in source.lower(), platform
        assert "category" in source, platform


def test_all_mobile_clients_prefetch_long_lists_without_manual_paging() -> None:
    android = "\n".join(
        path.read_text()
        for path in (ROOT / "apps/android/app/src/main/java/com/interviewagent/ui").glob("*.kt")
    )
    ios = "\n".join(
        path.read_text()
        for path in (ROOT / "apps/ios/Sources/InterviewAgent").glob("*.swift")
    )
    harmony = "\n".join(
        path.read_text()
        for path in (ROOT / "apps/harmony/entry/src/main/ets/pages").glob("*.ets")
    )
    miniapp = "\n".join(
        path.read_text()
        for path in (ROOT / "apps/miniapp/miniprogram/pages").rglob("*.js")
    )
    miniapp_configs = "\n".join(
        path.read_text()
        for path in (ROOT / "apps/miniapp/miniprogram/pages").rglob("*.json")
    )

    assert "size - 6" in android
    assert "append = true" in android
    assert "onAppear" in ios and "append: true" in ios
    assert ".onAppear" in harmony and "length - 6" in harmony
    assert "onReachBottom" in miniapp
    assert '"onReachBottomDistance": 800' in miniapp_configs
    for source in (android, ios, harmony, miniapp):
        assert "加载下一页" not in source
        assert "加载更多" not in source
