# -*- coding: utf-8 -*-
r"""
sw_reply.py  —  재사용 1:1 리드 회신 발송기 (SpotWarp / GPU-Action).

tp_reply.py(TenderPartner)와 동일한 구조. 개별(1:1) 회신을 보낼 때 항상 이 함수를 쓴다.
세 가지를 자동 보장한다:
  1) 발신/회신 주소를 info@gpu-action.com 으로 통일 (1:1 회신 도메인 — 콜드 발송용
     info@gpu-action-app.com 과 절대 혼용 금지, 2026-08-10 혼용 사고 재발 방지).
  2) **회장님 Gmail(leochen.rfp@gmail.com)로 BCC 사본** — 발송분이 Gmail 에 기록되게.
  3) log_data 를 넘기면 발송 즉시 대시보드 [3응대기록]에 자동 증분 기록 (AGENTS.md
     제4 절대 헌법 4단계 — 이걸 빠뜨려서 2026-09-08 AyyazTech 건을 수동으로 나중에
     채워넣은 적 있음, 재발 방지용으로 이 모듈을 만듦).

⚠️ 대량 콜드/후속 발송 봇은 이 모듈을 쓰면 안 된다 (수백 통 BCC 로 받은편지함이 뒤덮인다).
   오직 사람이 개별 응대하는 1:1 회신에만 쓴다. 대량 발송은 spotwarp_youtube_sender.py 등
   기존 콜드 발송기(from info@gpu-action-app.com)를 그대로 쓴다.

사용:
    from sw_reply import send_reply
    send_reply(
        to="creator@example.com",
        subject="Re: ...",
        html="<p>Hi,</p>...",
        headers={"In-Reply-To": msg_id, "References": msg_id},   # 선택, 스레드 연결용
        log_data={  # 선택 — 넘기면 대시보드 자동 기록
            "company": "...", "contact": "...", "ref": "...",
            "ask": "...", "reply": "...", "status": "...",
        },
    )
"""
import os
import sys
import resend

FROM_DEFAULT = "Leo Chen | SpotWarp <info@gpu-action.com>"
REPLY_TO_DEFAULT = "info@gpu-action.com"
HQ_BCC = "leochen.rfp@gmail.com"          # 본부 기록용 숨은참조 — 개별 발송분이 여기 남는다
HERE = os.path.dirname(os.path.abspath(__file__))


def _load_env(path):
    env = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env


def _api_key():
    key = os.getenv("RESEND_API_KEY") or _load_env(os.path.join(HERE, ".env")).get("RESEND_API_KEY")
    if not key:
        raise SystemExit("RESEND_API_KEY not found (env 또는 gpu-action/.env)")
    return key


def _wrap(html):
    """표준 프리미엄 이메일 래퍼 (기존 1:1 회신과 동일 스타일)."""
    if '<div' in html[:40]:
        return html
    return (
        '<div style="font-family: sans-serif; font-size: 14px; color: #1e293b; '
        'line-height: 1.6; max-width: 640px; margin: 0 auto;">' + html + '</div>'
    )


def _attach(paths):
    out = []
    for p in paths or []:
        ap = p if os.path.isabs(p) else os.path.join(HERE, p)
        with open(ap, "rb") as f:
            out.append({"filename": os.path.basename(ap), "content": list(f.read())})
    return out


def send_reply(to, subject, html, attachments=None,
               sender=FROM_DEFAULT, reply_to=REPLY_TO_DEFAULT, bcc=HQ_BCC,
               scheduled_at=None, headers=None, log_data=None):
    """1:1 리드 회신 발송. 항상 HQ Gmail 로 BCC 사본을 남긴다. Resend id 반환."""
    resend.api_key = _api_key()
    payload = {
        "from": sender,
        "to": to,
        "reply_to": reply_to,
        "bcc": bcc,                       # ← 본부 기록용 사본 (개별 발송분이 Gmail 에 남음)
        "subject": subject,
        "html": _wrap(html),
    }
    if headers:
        payload["headers"] = headers
    att = _attach(attachments)
    if att:
        payload["attachments"] = att
    if scheduled_at:
        payload["scheduled_at"] = scheduled_at
    r = resend.Emails.send(payload)
    when = f" (scheduled {scheduled_at})" if scheduled_at else ""
    resend_id = r.get('id', 'N/A')
    print(f"Queued to {to} (bcc {bcc}){when}. Resend ID: {resend_id}")

    # [Atomic Send & Log] 발송 즉시 대시보드 3응대기록 자동 증분 기록
    if log_data and isinstance(log_data, dict):
        try:
            sys.path.insert(0, r"C:\Users\choi5\연구자동화 에이전트들")
            from append_engagement import log_engagement
            from datetime import datetime
            today_str = datetime.now().strftime("%Y-%m-%d")
            log_engagement(
                division=3,
                date_str=log_data.get("date", today_str),
                company=log_data.get("company", to),
                contact=log_data.get("contact", "-"),
                email=to,
                ref=log_data.get("ref", subject),
                ask=log_data.get("ask", "-"),
                reply=log_data.get("reply", f"공식 1:1 회신 완료 (Resend {resend_id[:8]}, info@gpu-action.com)"),
                status=log_data.get("status", "회신 완료 — 고객 회신 대기")
            )
            print("  ✓ 대시보드 [3응대기록] 자동 등재 완료.")
        except Exception as e:
            print(f"  ! 대시보드 자동 등재 경고: {e}")

    return r
