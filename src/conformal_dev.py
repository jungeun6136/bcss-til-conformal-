import os
import numpy as np
from PIL import Image

LABEL_MAP = {
    0: 0,
    1: 1, 19: 1, 20: 1,      # tumor
    2: 2,                     # stroma
    3: 3, 10: 3, 11: 3,       # inflammatory
    4: 4,                     # necrosis
    5: 5, 6: 5, 7: 5, 8: 5, 9: 5, 12: 5, 13: 5,
    14: 5, 15: 5, 16: 5, 17: 5, 18: 5, 21: 5,
}


def remap_mask(mask, label_map=LABEL_MAP):
    remapped = np.zeros_like(mask)
    for orig_val, new_val in label_map.items():
        remapped[mask == orig_val] = new_val
    return remapped


def compute_til_from_gt(mask):
    """sTIL(%) = inflammatory 픽셀 / (inflammatory + stroma 픽셀) * 100
       0(don't-care)은 분자·분모 모두 제외. tumor는 분모에 안 넣는다."""
    remapped = remap_mask(mask)
    inflammatory = np.sum(remapped == 3)
    stroma = np.sum(remapped == 2)
    denom = inflammatory + stroma
    if denom == 0:
        return None  # 이 ROI는 제외
    return 100.0 * inflammatory / denom


def build_real_til_true(mask_dir):
    """실제 다운받은 151장 GT 마스크로 진짜 til_true 배열 만들기"""
    files = sorted(os.listdir(mask_dir))
    roi_ids, til_true = [], []
    for fname in files:
        mask = np.array(Image.open(os.path.join(mask_dir, fname)))
        til = compute_til_from_gt(mask)
        if til is not None:
            roi_ids.append(fname)
            til_true.append(til)
    return roi_ids, np.array(til_true)


def make_fake_predictions(til_true, seed=42):
    """모델이 아직 없으니, GT에 인위적 노이즈를 넣어 가짜 예측을 만든다."""
    rng = np.random.RandomState(seed)
    n = len(til_true)
    til_pred = til_true + rng.normal(0, 5, n)          # 오차 5%p 주입
    til_mc = til_pred[:, None] + rng.normal(0, 2, (n, 20))  # MC 샘플 20개 흉내
    sigma = til_mc.std(axis=1)
    return til_pred, sigma, til_mc


def conformal_calibrate(til_pred, til_true, sigma, alpha=0.10, eps=1e-6):
    """비적합도 점수 계산 -> 분위수 q 산출 (보정셋에서만 사용할 것!)"""
    scores = np.abs(til_pred - til_true) / (sigma + eps)
    n = len(scores)
    k = int(np.ceil((n + 1) * (1 - alpha)))

    if k > n:
        # 보정셋 크기로는 이 신뢰도(alpha)를 보장할 수 없다.
        # 안전하게 구간을 무한대로 넓혀서 "무조건 포함"으로 처리한다.
        return np.inf

    q = np.sort(scores)[k - 1]
    return q


def conformal_predict(til_pred, sigma, q):
    lower = til_pred - q * sigma
    upper = til_pred + q * sigma
    return lower, upper


if __name__ == "__main__":
    DATA_DIR = r"C:\Users\deeplearning\bcss_data"
    MASK_DIR = os.path.join(DATA_DIR, "masks")

    roi_ids, til_true = build_real_til_true(MASK_DIR)
    print(f"실제 GT로부터 계산된 ROI 개수: {len(roi_ids)}")

    til_pred, sigma, til_mc = make_fake_predictions(til_true)

    # 151개를 보정셋/테스트셋으로 반씩 나눠서 검증 (진짜 상황 흉내)
    n = len(til_true)
    n_calib = n // 2
    calib_idx = np.arange(n_calib)
    test_idx = np.arange(n_calib, n)

    q = conformal_calibrate(
        til_pred[calib_idx], til_true[calib_idx], sigma[calib_idx], alpha=0.10)
    print(f"보정 상수 q: {q:.3f}")

    lower, upper = conformal_predict(til_pred[test_idx], sigma[test_idx], q)
    covered = (til_true[test_idx] >= lower) & (til_true[test_idx] <= upper)
    print(f"테스트셋 실측 커버리지: {covered.mean():.1%}  (90% 근처, 85~95% 사이면 정상)")