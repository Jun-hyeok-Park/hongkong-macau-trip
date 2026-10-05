"""travel/index.html(개인용 원본) → publish/index.html(공개용) 빌드.

사용법 (프로젝트 루트에서):
    python publish/tools/build_publish.py

위치: 공개 저장소(publish/) 안에 두어 마스킹 로직을 Git으로 관리한다.
      원본 travel/index.html 은 저장소 밖(프로젝트 루트)에 있으며 절대 커밋하지 않는다.

원칙
- 원본은 수정하지 않는다. 공개본은 매번 원본에서 새로 만든다 (publish/index.html 을 직접 고치지 말 것).
- 마스킹 대상: 탑승객 이름(meta.travelerNames), PNR(pnr), 예약번호(bookingNo, "예약번호: ..."),
  e-ticket 번호(eTicket/eticket), 그 값들이 다른 곳(체크리스트 ref 등)에 복사된 경우까지.
- 원본에서 비밀값을 직접 추출해 결과물 전체를 다시 검색한다. 하나라도 남으면 파일을 쓰지 않고 실패(exit 1).
"""
import os
import re
import sys

# publish/tools/build_publish.py → 프로젝트 루트(= publish 의 상위 폴더)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "travel", "index.html")
OUT_DIR = os.path.join(ROOT, "publish")
OUT = os.path.join(OUT_DIR, "index.html")
MASK = "비공개"

# key:"value" 또는 key: "value" 형태의 개인정보 필드
SECRET_KEYS = ["travelerNames", "pnr", "bookingNo", "voucherNo", "confirmationNo", "eTicket", "eticket", "ticketNo", "passportNo", "phone", "email"]


def field_values(text, key):
    return re.findall(r'\b%s\s*:\s*"([^"]*)"' % re.escape(key), text)


def collect_secrets(src):
    secrets = set()
    for key in SECRET_KEYS:
        for v in field_values(src, key):
            v = v.strip()
            if v and v != MASK:
                secrets.add(v)
    # 개별 토큰도 검사 대상에 포함 (이름 한 단어, 예약번호 숫자 등)
    tokens = set()
    for v in secrets:
        for t in re.split(r"[\s·,/()]+", v):
            if len(t) >= 5 and not t.lower().startswith("trip"):
                tokens.add(t)
    return secrets, tokens


def sanitize(src, secrets, tokens):
    out = src
    for key in SECRET_KEYS:
        out = re.sub(r'(\b%s\s*:\s*)"[^"]*"' % re.escape(key), r'\1"%s"' % MASK, out)
    # 다른 위치에 복사된 비밀값 (긴 것부터 치환)
    for v in sorted(secrets | tokens, key=len, reverse=True):
        out = out.replace(v, MASK)
    # 체크리스트 등에 직접 적은 "예약번호: XXXX" / "PNR XXXX" 패턴
    out = re.sub(r"(예약번호\s*:?\s*)(?!—|-|\s|비공개)[A-Za-z0-9][A-Za-z0-9\-]{3,}", r"\1" + MASK, out)
    out = re.sub(r"(PNR\s*:?\s*)(?!<|\$|비공개)[A-Z0-9]{5,8}\b", r"\1" + MASK, out)
    # 공개본 표시 + 검색엔진 비노출
    out = out.replace("<head>", '<head>\n<meta name="robots" content="noindex,nofollow">', 1)
    out = re.sub(r"(<footer><div class=\"wrap\">)",
                 r'\1공개용 사본 — 탑승객 이름·PNR·예약번호 등 개인정보는 제거되었습니다 · ', out, count=1)
    return out


def verify(out, secrets, tokens):
    problems = []
    for v in sorted(secrets | tokens):
        if v in out:
            problems.append(f"비밀값 잔존: {v!r}")
    for key in SECRET_KEYS:
        for v in field_values(out, key):
            if v not in (MASK, ""):
                problems.append(f"{key} 필드 미마스킹: {v!r}")
    # 일반 패턴 검사: 13자리 이상 숫자(예약번호·e-ticket), e-ticket(3-10자리), PNR 표기 뒤 코드
    for m in re.finditer(r"\d{13,}", out):
        problems.append(f"긴 숫자열(예약번호/e-ticket 의심): {m.group(0)}")
    for m in re.finditer(r"\b\d{3}-\d{10}\b", out):
        problems.append(f"e-ticket 형식 의심: {m.group(0)}")
    for m in re.finditer(r"PNR\s*:?\s*([A-Z0-9]{5,8})\b", out):
        problems.append(f"PNR 잔존 의심: {m.group(1)}")
    return problems


def main():
    src = open(SRC, encoding="utf-8").read()
    secrets, tokens = collect_secrets(src)
    if not secrets:
        print("경고: 원본에서 개인정보 필드를 찾지 못했습니다 (SECRET_KEYS 확인).")
    out = sanitize(src, secrets, tokens)
    problems = verify(out, secrets, tokens)
    if problems:
        print("❌ 공개본 생성 중단 — 개인정보가 남아 있습니다:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    print(f"✅ publish/index.html 생성 완료 ({len(out):,} bytes)")
    print(f"   마스킹한 값 {len(secrets)}개 · 검사 토큰 {len(tokens)}개 · 잔존 0건")


if __name__ == "__main__":
    main()
