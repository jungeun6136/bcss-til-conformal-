# 전처리 체크리스트: 유방암 조직영상 세그멘테이션 + 유전체·치료반응 연관 분석

담당: 검모
상태: 계획 수립 단계

---

## 프로젝트 구조

```
pathomics_project/
├── data_raw/
│   └── bcss/
│       ├── images/          ← BCSS 원본 이미지 (직접 다운로드 필요)
│       └── masks/           ← BCSS 세그멘테이션 마스크 (직접 다운로드 필요)
├── preprocessed/             ← 전처리 완료된 데이터 저장 위치
├── PREPROCESSING_CHECKLIST.md (이 파일)
└── preprocess_bcss.py        ← 전처리 스크립트 (다음에 작성)
```

---

## 1단계: BCSS 이미지 데이터 전처리

### 1-1. 원본 데이터 다운로드

**다운로드 방법** (실제 README 확인 완료):
```bash
git clone https://github.com/CancerDataScience/CrowdsourcingDataset-Amgadetal2019
cd CrowdsourcingDataset-Amgadetal2019
pip install girder_client pillow numpy scikit-image imageio
python download_crowdsource_dataset.py
```
(또는 README에 안내된 Google Drive 단일 링크로 일괄 다운로드 가능)

**다운로드 후 생성되는 구조**:
```
annotations/   ← WSI 해상도 JSON 주석
masks/         ← 학습용 정답 마스크 (PNG)
images/        ← 마스크와 짝을 이루는 RGB 이미지 (PNG)
```

- [ ] 위 스크립트 실행하여 다운로드
- [ ] `pathomics_project/data_raw/bcss/`로 이동 배치
- [ ] 이미지-마스크 파일명 매칭 확인 (짝이 안 맞는 파일 있는지 체크)

### 1-2. 클래스 통합 (22개 원본 코드 → 5개 대분류 + 배경)

원본 클래스 정의는 `meta/gtruth_codes.tsv`에서 직접 확인함 (아래는 실제 파일 내용, 추측 아님):

| GT_code | label (원본) | 통합 대분류 |
|:---:|---|---|
| 0 | outside_roi | **배경/제외** (학습 시 weight=0) |
| 1 | tumor | **Tumor** |
| 2 | stroma | **Stroma** |
| 3 | lymphocytic_infiltrate | **Immune** |
| 4 | necrosis_or_debris | **Necrosis** |
| 5 | glandular_secretions | Other |
| 6 | blood | Other |
| 7 | exclude | **배경/제외** |
| 8 | metaplasia_NOS | Other |
| 9 | fat | Other |
| 10 | plasma_cells | **Immune** |
| 11 | other_immune_infiltrate | **Immune** |
| 12 | mucoid_material | Other |
| 13 | normal_acinus_or_duct | **Stroma** |
| 14 | lymphatics | **Immune** |
| 15 | undetermined | **배경/제외** |
| 16 | nerve | Other |
| 17 | skin_adnexa | Other |
| 18 | blood_vessel | Other |
| 19 | angioinvasion | **Tumor** |
| 20 | dcis | **Tumor** |
| 21 | other | Other |

→ 최종 5개 클래스: **Tumor / Stroma / Immune / Necrosis / Other** (+ 배경은 학습 시 loss에서 제외)

- [x] 매핑 테이블 확정 (원본 소스 확인 완료)
- [ ] 매핑 함수 구현 (마스크 픽셀값 재라벨링) — `preprocess_bcss.py`에 작성함

### 1-3. 이미지 규격 통일
- [ ] 이미지 크기 확인 (원본이 제각각인지, 이미 1024×1024인지)
- [ ] 패치 크기 결정 (예: 512×512로 통일)
- [ ] 필요시 패치 분할 (큰 이미지를 여러 패치로 자르기)

### 1-4. 염색 정규화 (Stain Normalization)
⚠️ 병리 이미지 특유의 전처리 — 일반 이미지 전처리와 다른 부분
- [ ] H&E 염색 편차 확인 (여러 기관/스캐너에서 온 이미지라 색감 차이 클 수 있음)
- [ ] Macenko 또는 Reinhard 정규화 기법 적용 검토
- [ ] 정규화 전후 시각적 비교

### 1-5. 결측/이상치 처리
- [ ] 마스크가 비어있거나(전부 배경) 손상된 이미지 제거
- [ ] 클래스가 하나도 없는 패치 필터링 여부 결정

### 1-6. 데이터 분할
⚠️ 중요: 패치 단위가 아니라 **원본 슬라이드(환자) 단위로 분할** 필수
(같은 환자의 패치가 train과 test에 동시에 들어가면 데이터 누수 발생)
- [ ] 슬라이드/환자 ID 기준으로 train/val/test 분할
- [ ] 분할 비율 결정 (예: 70/15/15)
- [ ] 클래스 분포가 분할 간 너무 불균형하지 않은지 확인

### 1-7. 정규화 및 저장
- [ ] 픽셀값 정규화 (0~1 스케일링 또는 ImageNet 평균/표준편차 기준)
- [ ] 전처리 완료 데이터 저장 형식 결정 (개별 파일 vs 압축 배열)

---

## 2단계 (확장): TCGA-BRCA 오믹스·임상 데이터 연결

### 2-1. 환자 ID 매칭
- [ ] BCSS 이미지 출처 슬라이드 → TCGA-BRCA 케이스 ID로 역추적
- [ ] 매칭되는 환자 수 확인 (전체 대비 몇 명이나 되는지가 확장 파트 실현 가능성을 결정)

### 2-2. 오믹스 데이터 전처리
- [ ] 기존 HYDRA-Onco 파이프라인(`preprocess_hydra_triplet.py`) 로직 재사용
- [ ] 발현/돌연변이/카피넘버/메틸화 결측치 처리 (기존 경험 그대로 적용)

### 2-3. 임상 약물치료 라벨 정제
- [ ] TCGA 임상 기록에서 약물명 표준화 (상품명/성분명 혼용 정리)
- [ ] 치료반응 라벨 정의 (예: 반응군 vs 비반응군 이진분류로 단순화)
- [ ] 선행 연구(medRxiv, 2021 TCGA treatment curation)의 정제 기준 참고

---

## 우선순위 정리

| 우선순위 | 작업 | 비고 |
|---------|------|------|
| 🔴 최우선 | BCSS 데이터 다운로드 및 클래스 매핑 확정 | 이게 안 되면 전체가 멈춤 |
| 🔴 최우선 | 환자 단위 train/val/test 분할 | 데이터 누수 방지 필수 |
| 🟡 중요 | 염색 정규화 | 모델 성능에 큰 영향 |
| 🟡 중요 | 환자 ID 매칭 (2단계) | 확장 파트 실현 가능성 결정 |
| 🟢 나중 | 임상 라벨 정제 | 2단계 진행 여부 확정 후 |
