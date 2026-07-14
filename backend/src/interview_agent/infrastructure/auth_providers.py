from __future__ import annotations

from dataclasses import dataclass

import requests

from interview_agent.infrastructure.settings import AppSettings


@dataclass(frozen=True)
class WechatSession:
    openid: str
    unionid: str | None = None
    session_key: str | None = None


class AuthProviderError(Exception):
    pass


def exchange_wechat_code(settings: AppSettings, code: str) -> WechatSession:
    if not settings.wechat_app_id or not settings.wechat_app_secret:
        raise AuthProviderError("微信小程序 AppID/AppSecret 未配置。")
    if not code.strip():
        raise AuthProviderError("微信登录 code 不能为空。")

    response = requests.get(
        settings.wechat_code2session_url,
        params={
            "appid": settings.wechat_app_id,
            "secret": settings.wechat_app_secret,
            "js_code": code,
            "grant_type": "authorization_code",
        },
        timeout=5,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errcode"):
        message = payload.get("errmsg") or "微信 code2session 失败。"
        raise AuthProviderError(message)
    openid = payload.get("openid")
    if not openid:
        raise AuthProviderError("微信 code2session 未返回 openid。")
    return WechatSession(
        openid=openid,
        unionid=payload.get("unionid"),
        session_key=payload.get("session_key"),
    )
