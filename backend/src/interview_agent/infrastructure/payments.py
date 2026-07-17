from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from interview_agent.infrastructure.settings import AppSettings


class PaymentProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class PaymentInitiation:
    provider: str
    external_order_id: str
    status: str
    pay_url: str | None = None
    code_url: str | None = None
    raw: dict[str, Any] | None = None


def create_alipay_page_pay(
    settings: AppSettings,
    *,
    external_order_id: str,
    amount_credits: Decimal,
    subject: str,
) -> PaymentInitiation:
    _require(settings.alipay_app_id, "ALIPAY_APP_ID 未配置。")
    _require(settings.alipay_private_key, "ALIPAY_PRIVATE_KEY 未配置。")
    notify_url = settings.alipay_notify_url or f"{settings.public_api_base_url.rstrip('/')}/payments/alipay/notify"
    return_url = settings.alipay_return_url or f"{settings.public_web_base_url.rstrip('/')}/"
    biz_content = {
        "out_trade_no": external_order_id,
        "total_amount": _money_amount(amount_credits),
        "subject": subject,
        "product_code": "FAST_INSTANT_TRADE_PAY",
    }
    params = {
        "app_id": settings.alipay_app_id,
        "method": "alipay.trade.page.pay",
        "format": "JSON",
        "charset": "utf-8",
        "sign_type": "RSA2",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "version": "1.0",
        "notify_url": notify_url,
        "return_url": return_url,
        "biz_content": json.dumps(biz_content, ensure_ascii=False, separators=(",", ":")),
    }
    sign = _rsa2_sign(_canonical_query(params), settings.alipay_private_key)
    pay_url = f"{settings.alipay_gateway}?{urlencode({**params, 'sign': sign})}"
    return PaymentInitiation(
        provider="alipay",
        external_order_id=external_order_id,
        status="pending",
        pay_url=pay_url,
        raw={"notify_url": notify_url, "return_url": return_url},
    )


def verify_alipay_notify(params: dict[str, str], alipay_public_key: str) -> bool:
    sign = params.get("sign", "")
    sign_type = params.get("sign_type", "RSA2")
    if sign_type != "RSA2" or not sign:
        return False
    payload = _canonical_query({key: value for key, value in params.items() if key not in {"sign", "sign_type"}})
    return _rsa2_verify(payload, sign, alipay_public_key)


def create_wechat_native_pay(
    settings: AppSettings,
    *,
    external_order_id: str,
    amount_credits: Decimal,
    description: str,
) -> PaymentInitiation:
    _require(settings.wechat_pay_app_id, "WECHAT_PAY_APP_ID 未配置。")
    _require(settings.wechat_pay_mch_id, "WECHAT_PAY_MCH_ID 未配置。")
    _require(settings.wechat_pay_private_key, "WECHAT_PAY_PRIVATE_KEY 未配置。")
    _require(settings.wechat_pay_cert_serial_no, "WECHAT_PAY_CERT_SERIAL_NO 未配置。")
    notify_url = settings.wechat_pay_notify_url or f"{settings.public_api_base_url.rstrip('/')}/payments/wechat/notify"
    path = "/v3/pay/transactions/native"
    url = f"https://api.mch.weixin.qq.com{path}"
    body = {
        "appid": settings.wechat_pay_app_id,
        "mchid": settings.wechat_pay_mch_id,
        "description": description[:127],
        "out_trade_no": external_order_id,
        "notify_url": notify_url,
        "amount": {"total": _fen_amount(amount_credits), "currency": "CNY"},
    }
    body_text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    timestamp = str(int(time.time()))
    nonce = _nonce(timestamp, external_order_id)
    signature = _rsa2_sign(f"POST\n{path}\n{timestamp}\n{nonce}\n{body_text}\n", settings.wechat_pay_private_key)
    auth = (
        'WECHATPAY2-SHA256-RSA2048 '
        f'mchid="{settings.wechat_pay_mch_id}",'
        f'nonce_str="{nonce}",'
        f'signature="{signature}",'
        f'timestamp="{timestamp}",'
        f'serial_no="{settings.wechat_pay_cert_serial_no}"'
    )
    response = requests.post(
        url,
        data=body_text.encode("utf-8"),
        headers={
            "Authorization": auth,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=15,
    )
    if response.status_code >= 400:
        raise PaymentProviderError(f"微信支付下单失败：{response.status_code} {response.text[:300]}")
    payload = response.json()
    code_url = payload.get("code_url")
    if not code_url:
        raise PaymentProviderError("微信支付未返回 code_url。")
    return PaymentInitiation(
        provider="wechat",
        external_order_id=external_order_id,
        status="pending",
        code_url=code_url,
        raw={"notify_url": notify_url},
    )


def decrypt_wechat_resource(resource: dict[str, Any], api_v3_key: str) -> dict[str, Any]:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        aesgcm = AESGCM(api_v3_key.encode("utf-8"))
        plaintext = aesgcm.decrypt(
            resource["nonce"].encode("utf-8"),
            base64.b64decode(resource["ciphertext"]),
            resource.get("associated_data", "").encode("utf-8"),
        )
        return json.loads(plaintext.decode("utf-8"))
    except Exception as exc:
        raise PaymentProviderError("微信支付回调资源解密失败。") from exc


def verify_wechat_notify(headers, body: bytes, platform_cert_pem: str) -> bool:
    timestamp = headers.get("Wechatpay-Timestamp", "")
    nonce = headers.get("Wechatpay-Nonce", "")
    signature = headers.get("Wechatpay-Signature", "")
    if not timestamp or not nonce or not signature or not platform_cert_pem:
        return False
    message = f"{timestamp}\n{nonce}\n{body.decode('utf-8')}\n"
    try:
        certificate = x509.load_pem_x509_certificate(_pem_bytes(platform_cert_pem, "CERTIFICATE"))
        certificate.public_key().verify(
            base64.b64decode(signature),
            message.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def _money_amount(amount_credits: Decimal) -> str:
    return f"{Decimal(amount_credits):.2f}"


def _fen_amount(amount_credits: Decimal) -> int:
    return int((Decimal(amount_credits) * Decimal("100")).quantize(Decimal("1")))


def _canonical_query(params: dict[str, Any]) -> str:
    return "&".join(f"{key}={params[key]}" for key in sorted(params) if params[key] not in {None, ""})


def _rsa2_sign(payload: str, private_key_text: str) -> str:
    private_key = serialization.load_pem_private_key(_pem_bytes(private_key_text, "PRIVATE KEY"), password=None)
    signature = private_key.sign(payload.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("ascii")


def _rsa2_verify(payload: str, signature: str, public_key_text: str) -> bool:
    try:
        public_key = serialization.load_pem_public_key(_pem_bytes(public_key_text, "PUBLIC KEY"))
        public_key.verify(base64.b64decode(signature), payload.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def _pem_bytes(value: str, label: str) -> bytes:
    cleaned = value.strip().replace("\\n", "\n")
    if "-----BEGIN" in cleaned:
        return cleaned.encode("utf-8")
    wrapped = "\n".join(cleaned[i : i + 64] for i in range(0, len(cleaned), 64))
    return f"-----BEGIN {label}-----\n{wrapped}\n-----END {label}-----\n".encode("utf-8")


def _nonce(*parts: str) -> str:
    raw = "".join(parts).replace("-", "")
    return (raw[:32] or str(int(time.time() * 1000))).ljust(16, "0")[:32]


def _require(value: str, message: str) -> None:
    if not value:
        raise PaymentProviderError(message)
