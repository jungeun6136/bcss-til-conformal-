# 병리영상 세그멘테이션 전처리 데이터 사용 가이드

## 🚀 빠른 시작

### 0. 원본 데이터 다운로드 (아직 안 했다면)

```bash
git clone https://github.com/CancerDataScience/CrowdsourcingDataset-Amgadetal2019
cd CrowdsourcingDataset-Amgadetal2019
pip install girder_client pillow numpy scikit-image imageio
python download_crowdsource_dataset.py
```

다운로드된 `images/`, `masks/` 폴더를 `pathomics_project/data_raw/bcss/` 아래로 옮깁니다.

### 1. 전처리 실행

```bash
cd pathomics_project
pip install pillow numpy
python preprocess_bcss.py
```

실행하면 `preprocessed/train/`, `preprocessed/val/`, `preprocessed/test/`에 패치 단위 `.npy` 파일이 생성됩니다.

```
preprocessed/
├── split_info.json          ← 환자 단위 분할 정보 (어떤 환자가 train/val/test인지)
├── train/
│   ├── TCGA-A1-A0SK-DX1_..._p0000_image.npy   ← (512, 512, 3) float32
│   ├── TCGA-A1-A0SK-DX1_..._p0000_mask.npy    ← (512, 512) uint8 (0~5)
│   └── ...
├── val/
└── test/
```

---

## 📊 데이터 구조 이해하기

### 이미지 패치 (`*_image.npy`)
```python
import numpy as np

img = np.load("preprocessed/train/TCGA-A1-A0SK-DX1_..._p0000_image.npy")
print(img.shape)   # (512, 512, 3)
print(img.dtype)   # float32
print(img.min(), img.max())  # ImageNet 정규화 기준이라 음수 포함 가능
```

### 마스크 패치 (`*_mask.npy`)
```python
mask = np.load("preprocessed/train/TCGA-A1-A0SK-DX1_..._p0000_mask.npy")
print(mask.shape)   # (512, 512)
print(mask.dtype)   # uint8
print(np.unique(mask))  # [0, 1, 2, 3, 4, 5] 중 일부 (0=배경/제외)
```

**클래스 값 의미**:
| 값 | 클래스 |
|:---:|---|
| 0 | 배경/제외 (loss 계산 시 무시) |
| 1 | Tumor |
| 2 | Stroma |
| 3 | Immune |
| 4 | Necrosis |
| 5 | Other |

---

## ⚙️ 샘플 사용 사례

### 1️⃣ 전처리 결과 빠르게 확인

```python
import numpy as np
from pathlib import Path

split_dir = Path("preprocessed/train")
image_files = sorted(split_dir.glob("*_image.npy"))
print(f"train 패치 수: {len(image_files)}")

img = np.load(image_files[0])
mask = np.load(str(image_files[0]).replace("_image.npy", "_mask.npy"))
print(f"이미지: {img.shape}, 마스크: {mask.shape}")
print(f"마스크 클래스 분포: {np.bincount(mask.flatten(), minlength=6)}")
```

### 2️⃣ PyTorch Dataset으로 로드

```python
import torch
from torch.utils.data import Dataset
from pathlib import Path
import numpy as np

class BCSSPatchDataset(Dataset):
    def __init__(self, split_dir):
        self.image_files = sorted(Path(split_dir).glob("*_image.npy"))

    def __len__(self):
        return len(self.image_files)

    def __getitem__(self, idx):
        img_path = self.image_files[idx]
        mask_path = str(img_path).replace("_image.npy", "_mask.npy")

        image = np.load(img_path)          # (512, 512, 3)
        mask = np.load(mask_path)          # (512, 512)

        # (H, W, C) -> (C, H, W)
        image = torch.from_numpy(image).permute(2, 0, 1).float()
        mask = torch.from_numpy(mask).long()

        return image, mask


train_dataset = BCSSPatchDataset("preprocessed/train")
val_dataset = BCSSPatchDataset("preprocessed/val")

from torch.utils.data import DataLoader
train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True)

print(f"train 패치 수: {len(train_dataset)}")
images, masks = next(iter(train_loader))
print(f"배치 shape: {images.shape}, {masks.shape}")
```

### 3️⃣ 배경 클래스(0)를 무시하는 손실 함수 설정

```python
import torch.nn as nn

# 0번 클래스(배경/제외)는 학습에 기여하지 않도록 ignore_index 지정
criterion = nn.CrossEntropyLoss(ignore_index=0)

# 사용 예
# loss = criterion(model_output, mask)  # model_output: (B, 6, H, W), mask: (B, H, W)
```

### 4️⃣ 클래스 불균형 확인 (Tumor/Stroma가 Necrosis보다 훨씬 많을 가능성)

```python
import numpy as np
from pathlib import Path
from collections import Counter

split_dir = Path("preprocessed/train")
counter = Counter()
for mask_path in split_dir.glob("*_mask.npy"):
    mask = np.load(mask_path)
    values, counts = np.unique(mask, return_counts=True)
    for v, c in zip(values, counts):
        counter[int(v)] += int(c)

class_names = {0: "ignore", 1: "tumor", 2: "stroma", 3: "immune", 4: "necrosis", 5: "other"}
total = sum(v for k, v in counter.items() if k != 0)
for k in sorted(counter):
    ratio = counter[k] / total * 100 if k != 0 else None
    label = class_names.get(k, str(k))
    print(f"{label}: {counter[k]:,} 픽셀" + (f" ({ratio:.1f}%)" if ratio else ""))
```

### 5️⃣ 환자 단위 분할 정보 확인 (데이터 누수 검증용)

```python
import json

with open("preprocessed/split_info.json") as f:
    split_info = json.load(f)

print(f"Train 환자 수: {len(split_info['train'])}")
print(f"Val 환자 수: {len(split_info['val'])}")
print(f"Test 환자 수: {len(split_info['test'])}")

# train과 test에 겹치는 환자가 없는지 확인 (데이터 누수 검증)
overlap = set(split_info['train']) & set(split_info['test'])
print(f"Train-Test 겹치는 환자: {len(overlap)}개 (0이어야 정상)")
assert len(overlap) == 0, "데이터 누수 발생! 같은 환자가 train과 test에 동시에 있음"
```

---

## 🔍 문제 해결

### 문제: 전처리 스크립트가 "데이터가 없습니다" 라고 나옴
`data_raw/bcss/images`, `data_raw/bcss/masks`에 실제 파일이 있는지 확인하세요.

### 문제: 특정 슬라이드가 "처리 실패"로 스킵됨
콘솔에 출력되는 실패 사유(파일 로드 실패 / 크기 불일치 / 전부 배경)를 확인하세요. 이건 파이프라인이 조용히 잘못된 데이터를 만들지 않도록 의도적으로 막는 것입니다.

### 문제: 패치가 하나도 안 만들어진 슬라이드가 있음
해당 슬라이드가 512×512보다 작거나, 조직 비율이 10% 미만인 경우입니다. `extract_patches()`의 `min_tissue_ratio`, `patch_size` 인자로 조정 가능합니다.

---

## ⚠️ 아직 실제 데이터로 검증 안 된 부분

이 가이드의 코드 예제는 파이프라인 설계상 맞게 짜여 있지만, **실제 BCSS 전체 데이터로 처음부터 끝까지 돌려본 적은 아직 없습니다.** 실행 중 예상 못 한 오류가 나올 수 있으니, 처음엔 소량(5~10장)으로 먼저 테스트하는 것을 권장합니다.

---

*작성일: 2026-07-13*
*담당: 검모 (전처리)*
