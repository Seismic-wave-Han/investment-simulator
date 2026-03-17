# 투자 시나리오 연평균 수익률 비교 (간단 버전)

시드(억), 월저축(억/월), 평균 수익률(%), 인플레이션(%)를 입력해 **1~10년 후 총자산**을 계산합니다.

- **명목 총자산**: 수익률만 반영
- **실질 총자산**: 인플레이션을 반영해 현재가치로 환산 (명목 / \((1+\text{infl})^n\))

## 로컬 실행 (가장 간단)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

실행:

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 로 접속합니다.

## 배포 1) Streamlit Community Cloud (추천, 무료/간단)

사람들이 링크로 바로 접속해서 쓰게 하려면 이 방법이 제일 쉽습니다.

- GitHub에 이 폴더를 올립니다.
- Streamlit Community Cloud에서 새 앱을 만들고:
  - **Repository**: 방금 올린 저장소
  - **Main file path**: `app.py`
  - **Python requirements**: `requirements.txt`

배포가 끝나면 공유 가능한 URL이 생성됩니다.

## 배포 2) Docker로 배포 (서버/PC 어디서나 동일 실행)

빌드:

```bash
docker build -t finance-streamlit .
```

실행:

```bash
docker run --rm -p 8501:8501 finance-streamlit
```

브라우저에서 `http://localhost:8501` 로 접속합니다.

## 계산 가정

- 시드와 월저축은 **억 단위**로 입력합니다.
- 월저축은 매달 **1회 납입**된다고 가정합니다.
- 평균 수익률/인플레이션은 **연 단위**이며 매년 동일하다고 가정합니다.

