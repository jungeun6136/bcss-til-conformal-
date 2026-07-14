import os
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

# ---------------------------------------------------------------------------
# 경로 설정
# ---------------------------------------------------------------------------
DATA_DIR = r"C:\Users\deeplearning\bcss_data"  # 검증 끝난 데이터 폴더
IMG_DIR = os.path.join(DATA_DIR, "images")
MASK_DIR = os.path.join(DATA_DIR, "masks")

# ---------------------------------------------------------------------------
# BCSS 원본 코드(0~21) -> 프로젝트용 5클래스 매핑
# 0 = don't-care, 1=tumor, 2=stroma, 3=inflammatory, 4=necrosis, 5=other
# ---------------------------------------------------------------------------
LABEL_MAP = {
    0: 0,   # outside_roi -> don't-care (그대로 유지)

    1: 1,   # tumor
    19: 1,  # angioinvasion -> tumor로 병합 (기획서 규약)
    20: 1,  # dcis -> tumor로 병합 (기획서 규약)

    2: 2,   # stroma

    3: 3,   # lymphocytic_infiltrate -> inflammatory
    10: 3,  # plasma_cells -> inflammatory로 병합 (기획서 규약)
    11: 3,  # other_immune_infiltrate -> inflammatory로 병합 (기획서 규약)

    4: 4,   # necrosis_or_debris -> necrosis

    # 나머지는 전부 "other"(5)로 묶는다
    5: 5,   # glandular_secretions
    6: 5,   # blood
    7: 5,   # exclude
    8: 5,   # metaplasia_NOS
    9: 5,   # fat
    12: 5,  # mucoid_material
    13: 5,  # normal_acinus_or_duct
    14: 5,  # lymphatics
    15: 5,  # undetermined
    16: 5,  # nerve
    17: 5,  # skin_adnexa
    18: 5,  # blood_vessel
    21: 5,  # other
}


def remap_mask(mask, label_map=LABEL_MAP):
    """BCSS 원본 21클래스 마스크를 프로젝트용 5클래스(+don't-care)로 재매핑."""
    remapped = np.zeros_like(mask)
    for orig_val, new_val in label_map.items():
        remapped[mask == orig_val] = new_val
    return remapped


def scan_full_dataset(img_dir, mask_dir):
    """전체 데이터셋을 훑어서 클래스 분포와 don't-care 포함 여부를 확인."""
    img_files = sorted(os.listdir(img_dir))
    mask_files = sorted(os.listdir(mask_dir))
    print(f"이미지 {len(img_files)}개, 마스크 {len(mask_files)}개")

    all_values = set()
    files_with_zero = 0

    for fname in mask_files:
        mask = np.array(Image.open(os.path.join(mask_dir, fname)))
        vals = set(np.unique(mask).tolist())
        all_values |= vals
        if 0 in vals:
            files_with_zero += 1

    print("전체 데이터셋에 등장하는 모든 클래스 값:", sorted(all_values))
    print(f"0(don't-care)이 포함된 파일 개수: {files_with_zero} / {len(mask_files)}")

    return img_files, mask_files


def visualize_one_sample(img_dir, mask_dir, sample_name, save_path="remap_check.png"):
    """샘플 하나를 골라 원본 마스크와 재매핑된 마스크를 나란히 시각화."""
    image = np.array(Image.open(os.path.join(img_dir, sample_name)))
    mask = np.array(Image.open(os.path.join(mask_dir, sample_name)))
    remapped = remap_mask(mask)

    print(f"sample: {sample_name}")
    print(f"image shape: {image.shape}, dtype: {image.dtype}")
    print(f"mask shape: {mask.shape}, unique values (raw): {np.unique(mask)}")
    print(f"mask unique values (remapped): {np.unique(remapped)}")

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    axes[0].imshow(image)
    axes[0].set_title("image")
    axes[1].imshow(mask, cmap="tab20", vmin=0, vmax=21)
    axes[1].set_title("mask (raw)")
    axes[2].imshow(remapped, cmap="tab10", vmin=0, vmax=5)
    axes[2].set_title("mask (remapped, 0-5)")
    plt.tight_layout()
    plt.savefig(save_path)
    print(f"결과를 {save_path}로 저장했다.")


if __name__ == "__main__":
    img_files, mask_files = scan_full_dataset(IMG_DIR, MASK_DIR)

    sample_name = img_files[0]
    visualize_one_sample(IMG_DIR, MASK_DIR, sample_name)