import os
import random

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

LABEL_MAP = {
    0: 0,
    1: 1, 19: 1, 20: 1,      # tumor
    2: 2,                     # stroma
    3: 3, 10: 3, 11: 3,       # inflammatory
    4: 4,                     # necrosis
    5: 5, 6: 5, 7: 5, 8: 5, 9: 5, 12: 5, 13: 5,
    14: 5, 15: 5, 16: 5, 17: 5, 18: 5, 21: 5,  # other
}

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def remap_mask(mask, label_map=LABEL_MAP):
    remapped = np.zeros_like(mask)
    for orig_val, new_val in label_map.items():
        remapped[mask == orig_val] = new_val
    return remapped


class BCSSDataset(Dataset):
    def __init__(self, img_dir, mask_dir, file_list, patch_size=512, train=True):
        self.img_dir = img_dir
        self.mask_dir = mask_dir
        self.file_list = file_list
        self.patch_size = patch_size
        self.train = train

    def __len__(self):
        return len(self.file_list)

    def __getitem__(self, idx):
        fname = self.file_list[idx]
        image = np.array(Image.open(os.path.join(self.img_dir, fname)).convert("RGB"))
        mask = np.array(Image.open(os.path.join(self.mask_dir, fname)))
        mask = remap_mask(mask)

        h, w = mask.shape
        ps = self.patch_size

        # 이미지가 patch_size보다 작은 경우 방지 (BCSS는 보통 훨씬 크니 잘 안 걸리지만 방어적으로)
        if h < ps or w < ps:
            raise ValueError(f"{fname}: 이미지가 patch_size({ps})보다 작다. shape={mask.shape}")

        # *** 핵심: 같은 좌표로 이미지와 마스크를 동시에 자른다 ***
        top = random.randint(0, h - ps)
        left = random.randint(0, w - ps)
        image = image[top:top + ps, left:left + ps]
        mask = mask[top:top + ps, left:left + ps]

        # 이미지 정규화 (사전학습 인코더 기준에 맞춤)
        image = image.astype(np.float32) / 255.0
        image = (image - IMAGENET_MEAN) / IMAGENET_STD
        image = torch.from_numpy(image).permute(2, 0, 1).float()  # (H,W,C) -> (C,H,W)

        mask = torch.from_numpy(mask).long()  # CrossEntropyLoss는 long 타입 요구

        return image, mask


def make_train_val_split(img_dir, val_ratio=0.2, seed=42):
    files = sorted(os.listdir(img_dir))
    rng = random.Random(seed)
    rng.shuffle(files)
    n_val = int(len(files) * val_ratio)
    val_files = files[:n_val]
    train_files = files[n_val:]
    return train_files, val_files


if __name__ == "__main__":
    DATA_DIR = r"C:\Users\deeplearning\bcss_data"
    IMG_DIR = os.path.join(DATA_DIR, "images")
    MASK_DIR = os.path.join(DATA_DIR, "masks")

    train_files, val_files = make_train_val_split(IMG_DIR)
    print(f"train: {len(train_files)}개, val: {len(val_files)}개")

    train_ds = BCSSDataset(IMG_DIR, MASK_DIR, train_files, patch_size=512, train=True)

    image, mask = train_ds[0]
    print("image tensor shape:", image.shape, image.dtype)
    print("mask tensor shape:", mask.shape, mask.dtype)
    print("mask unique values in this patch:", torch.unique(mask))

    from torch.utils.data import DataLoader
    loader = DataLoader(train_ds, batch_size=4, shuffle=True, num_workers=0)
    batch_img, batch_mask = next(iter(loader))
    print("배치 이미지 shape:", batch_img.shape)
    print("배치 마스크 shape:", batch_mask.shape)