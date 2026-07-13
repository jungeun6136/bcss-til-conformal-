#!/usr/bin/env python3
"""
BCSS 유방암 조직영상 세그멘테이션 전처리 파이프라인
원본 22개 클래스를 5개 대분류로 통합하고, 슬라이드 단위로 train/val/test 분할한다.

사전 준비: CancerDataScience/CrowdsourcingDataset-Amgadetal2019 로 다운로드한
           images/, masks/ 폴더를 data_raw/bcss/ 아래 배치해둘 것.
"""

import os
import re
import json
from pathlib import Path

import numpy as np
from PIL import Image

from stain_normalization import macenko_normalize, normalize_pixels

# ============================================================================
# 클래스 매핑 (meta/gtruth_codes.tsv 원본 확인 결과 그대로 반영)
# ============================================================================

# 원본 GT_code -> 원본 label
RAW_LABELS = {
    0: "outside_roi", 1: "tumor", 2: "stroma", 3: "lymphocytic_infiltrate",
    4: "necrosis_or_debris", 5: "glandular_secretions", 6: "blood", 7: "exclude",
    8: "metaplasia_NOS", 9: "fat", 10: "plasma_cells", 11: "other_immune_infiltrate",
    12: "mucoid_material", 13: "normal_acinus_or_duct", 14: "lymphatics",
    15: "undetermined", 16: "nerve", 17: "skin_adnexa", 18: "blood_vessel",
    19: "angioinvasion", 20: "dcis", 21: "other",
}

# 통합 대분류: 0=배경/제외(학습 시 ignore), 1=Tumor, 2=Stroma, 3=Immune, 4=Necrosis, 5=Other
CONSOLIDATED_CLASSES = {0: "ignore", 1: "tumor", 2: "stroma", 3: "immune", 4: "necrosis", 5: "other"}

RAW_TO_CONSOLIDATED = {
    0: 0,   # outside_roi -> ignore
    7: 0,   # exclude -> ignore
    15: 0,  # undetermined -> ignore
    1: 1,   # tumor
    19: 1,  # angioinvasion -> tumor
    20: 1,  # dcis -> tumor
    2: 2,   # stroma
    13: 2,  # normal_acinus_or_duct -> stroma
    3: 3,   # lymphocytic_infiltrate -> immune
    10: 3,  # plasma_cells -> immune
    11: 3,  # other_immune_infiltrate -> immune
    14: 3,  # lymphatics -> immune
    4: 4,   # necrosis_or_debris
    5: 5, 6: 5, 8: 5, 9: 5, 12: 5, 16: 5, 17: 5, 18: 5, 21: 5,  # other
}

# 룩업 테이블화 (빠른 벡터 연산용, 0~21 인덱스)
_LUT = np.zeros(max(RAW_TO_CONSOLIDATED.keys()) + 1, dtype=np.uint8)
for raw_code, consolidated_code in RAW_TO_CONSOLIDATED.items():
    _LUT[raw_code] = consolidated_code


def consolidate_mask(mask_array: np.ndarray) -> np.ndarray:
    """22개 원본 클래스 마스크를 5개 대분류(+ignore) 마스크로 변환"""
    clipped = np.clip(mask_array, 0, len(_LUT) - 1)
    return _LUT[clipped]


# ============================================================================
# 슬라이드/환자 ID 추출
# ============================================================================

# TCGA 슬라이드 바코드 패턴: TCGA-XX-XXXX (예: TCGA-A2-A0YF)
TCGA_CASE_PATTERN = re.compile(r"TCGA-[0-9A-Za-z]{2}-[0-9A-Za-z]{4}")


def extract_case_id(filename: str) -> str:
    """파일명에서 TCGA 환자(case) ID 추출. 환자 단위 분할에 사용.

    주의: 실제 다운로드한 파일명 형식을 아직 확인하지 못했음.
    다운로드 후 실제 파일명 샘플을 보고 이 함수가 제대로 매칭되는지 검증 필요.
    """
    match = TCGA_CASE_PATTERN.search(filename)
    if match is None:
        raise ValueError(f"파일명에서 TCGA case ID를 찾지 못함: {filename}")
    return match.group(0)


# ============================================================================
# Step 1: 이미지-마스크 페어 수집
# ============================================================================

def collect_pairs(images_dir: Path, masks_dir: Path):
    image_files = {f.stem: f for f in images_dir.glob("*.png")}
    mask_files = {f.stem: f for f in masks_dir.glob("*.png")}

    common_stems = sorted(set(image_files) & set(mask_files))
    missing_masks = sorted(set(image_files) - set(mask_files))
    missing_images = sorted(set(mask_files) - set(image_files))

    print(f"이미지-마스크 매칭: {len(common_stems)}쌍")
    if missing_masks:
        print(f"  ⚠ 마스크 없는 이미지: {len(missing_masks)}개 (제외)")
    if missing_images:
        print(f"  ⚠ 이미지 없는 마스크: {len(missing_images)}개 (제외)")

    return [(image_files[s], mask_files[s]) for s in common_stems]


# ============================================================================
# Step 2: 클래스 분포 확인 (필터링 기준 마련용)
# ============================================================================

def analyze_mask(mask_path: Path) -> dict:
    mask = np.array(Image.open(mask_path))
    consolidated = consolidate_mask(mask)
    total_px = consolidated.size
    ignore_ratio = (consolidated == 0).sum() / total_px
    class_ratios = {
        CONSOLIDATED_CLASSES[c]: (consolidated == c).sum() / total_px
        for c in range(1, 6)
    }
    return {"ignore_ratio": ignore_ratio, **class_ratios}


# ============================================================================
# Step 3: 환자 단위 train/val/test 분할
# ============================================================================

def split_by_case(pairs, train_ratio=0.7, val_ratio=0.15, seed=42):
    rng = np.random.RandomState(seed)

    case_to_pairs = {}
    for img_path, mask_path in pairs:
        case_id = extract_case_id(img_path.name)
        case_to_pairs.setdefault(case_id, []).append((img_path, mask_path))

    case_ids = sorted(case_to_pairs.keys())
    rng.shuffle(case_ids)

    n_cases = len(case_ids)
    n_train = int(n_cases * train_ratio)
    n_val = int(n_cases * val_ratio)

    train_cases = case_ids[:n_train]
    val_cases = case_ids[n_train:n_train + n_val]
    test_cases = case_ids[n_train + n_val:]

    def flatten(cases):
        result = []
        for c in cases:
            result.extend(case_to_pairs[c])
        return result

    print(f"환자 수: {n_cases}명 -> train {len(train_cases)} / val {len(val_cases)} / test {len(test_cases)}")

    return {
        "train": flatten(train_cases),
        "val": flatten(val_cases),
        "test": flatten(test_cases),
        "case_split": {"train": train_cases, "val": val_cases, "test": test_cases},
    }


# ============================================================================
# Step 4: 패치 분할
# ============================================================================
# 실제 데이터 확인 결과 이미지 크기가 슬라이드마다 제각각임
# (예: 3394x2467, 4838x3426, 3794x2919) -> 고정 크기 패치로 잘라야 배치 학습 가능

DEFAULT_PATCH_SIZE = 512
MIN_TISSUE_RATIO = 0.1  # 패치 내 배경(ignore=0)이 아닌 픽셀 비율이 이 이하면 제외


def extract_patches(image: np.ndarray, mask: np.ndarray, patch_size: int = DEFAULT_PATCH_SIZE,
                     stride: int = None, min_tissue_ratio: float = MIN_TISSUE_RATIO):
    """큰 이미지/마스크를 겹치지 않는 고정 크기 패치로 분할.
    조직 비율이 너무 낮은(배경 위주) 패치는 제외.

    Returns: [(image_patch, mask_patch), ...]
    """
    if stride is None:
        stride = patch_size  # 기본은 겹치지 않게

    h, w = mask.shape[:2]
    if h < patch_size or w < patch_size:
        print(f"  ⚠ 이미지가 패치 크기({patch_size})보다 작음 (h={h}, w={w}) -> 건너뜀")
        return []

    patches = []
    for y in range(0, h - patch_size + 1, stride):
        for x in range(0, w - patch_size + 1, stride):
            mask_patch = mask[y:y + patch_size, x:x + patch_size]
            tissue_ratio = (mask_patch != 0).mean()
            if tissue_ratio < min_tissue_ratio:
                continue
            image_patch = image[y:y + patch_size, x:x + patch_size]
            patches.append((image_patch, mask_patch))
    return patches


# ============================================================================
# Step 5: 정규화 (염색 정규화 + 픽셀 정규화)
# ============================================================================

def preprocess_image(image_path: Path, pixel_norm_method: str = "imagenet") -> np.ndarray:
    """이미지 1장을 읽어서 염색 정규화 -> 픽셀 정규화까지 적용한 배열 반환"""
    image = np.array(Image.open(image_path).convert("RGB"))
    try:
        stain_normalized = macenko_normalize(image)
    except ValueError as e:
        # 배경만 있거나 조직 픽셀이 너무 적은 이미지는 염색 정규화 건너뜀
        print(f"  ⚠ {image_path.name}: 염색 정규화 실패({e}), 원본 유지")
        stain_normalized = image
    return normalize_pixels(stain_normalized, method=pixel_norm_method)


def preprocess_split(pairs, output_dir: Path, split_name: str,
                      patch_size: int = DEFAULT_PATCH_SIZE, pixel_norm_method: str = "imagenet"):
    """분할 하나(train/val/test)에 대해 정규화 + 패치 분할 적용 후 저장"""
    split_dir = output_dir / split_name
    split_dir.mkdir(parents=True, exist_ok=True)

    n_slides_ok, n_slides_failed, n_patches = 0, 0, 0
    for img_path, mask_path in pairs:
        try:
            normalized = preprocess_image(img_path, pixel_norm_method)
            mask = np.array(Image.open(mask_path))
        except Exception as e:
            print(f"  ✗ {img_path.name}: 파일 로드/처리 실패 ({e})")
            n_slides_failed += 1
            continue

        # 이미지-마스크 해상도 불일치 방어 (파일 손상 시 조용히 잘못된 패치가 만들어지는 것 방지)
        if normalized.shape[:2] != mask.shape[:2]:
            print(f"  ✗ {img_path.name}: 이미지 {normalized.shape[:2]} vs 마스크 {mask.shape[:2]} 크기 불일치, 건너뜀")
            n_slides_failed += 1
            continue

        consolidated_mask = consolidate_mask(mask)

        if consolidated_mask.max() == 0:
            print(f"  ⚠ {img_path.name}: 마스크가 전부 배경/제외 클래스임, 건너뜀")
            n_slides_failed += 1
            continue

        patches = extract_patches(normalized, consolidated_mask, patch_size=patch_size)

        stem = img_path.stem
        for i, (img_patch, mask_patch) in enumerate(patches):
            np.save(split_dir / f"{stem}_p{i:04d}_image.npy", img_patch.astype(np.float32))
            np.save(split_dir / f"{stem}_p{i:04d}_mask.npy", mask_patch.astype(np.uint8))

        n_patches += len(patches)
        n_slides_ok += 1

    print(f"  [{split_name}] 완료: 슬라이드 {n_slides_ok}개 성공 / {n_slides_failed}개 실패, 패치 {n_patches}개 생성")
    return n_slides_ok, n_slides_failed, n_patches


# ============================================================================
# 메인
# ============================================================================

def main():
    data_dir = Path("data_raw/bcss")
    images_dir = data_dir / "images"
    masks_dir = data_dir / "masks"
    output_dir = Path("preprocessed")
    output_dir.mkdir(exist_ok=True)

    if not images_dir.exists() or not any(images_dir.iterdir()):
        print("=" * 70)
        print("⚠ data_raw/bcss/images, masks 에 데이터가 없습니다.")
        print("먼저 BCSS 데이터셋을 다운로드해서 배치해주세요:")
        print("  git clone https://github.com/CancerDataScience/CrowdsourcingDataset-Amgadetal2019")
        print("  cd CrowdsourcingDataset-Amgadetal2019 && python download_crowdsource_dataset.py")
        print("=" * 70)
        return

    print("[Step 1] 이미지-마스크 페어 수집")
    pairs = collect_pairs(images_dir, masks_dir)

    print("\n[Step 2] 클래스 분포 샘플 확인 (처음 5개)")
    for img_path, mask_path in pairs[:5]:
        stats = analyze_mask(mask_path)
        print(f"  {mask_path.name}: {stats}")

    print("\n[Step 3] 환자 단위 데이터 분할")
    split = split_by_case(pairs)

    with open(output_dir / "split_info.json", "w") as f:
        json.dump(
            {k: v for k, v in split["case_split"].items()},
            f, indent=2
        )
    print(f"\n✓ 분할 정보 저장: {output_dir / 'split_info.json'}")

    print(f"\n[Step 4-5] 패치 분할({DEFAULT_PATCH_SIZE}x{DEFAULT_PATCH_SIZE}) + 염색/픽셀 정규화 적용 및 저장")
    for split_name in ["train", "val", "test"]:
        preprocess_split(split[split_name], output_dir, split_name)

    print("\n전처리 파이프라인 완료")


if __name__ == "__main__":
    main()
