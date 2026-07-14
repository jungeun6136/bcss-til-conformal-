import numpy as np
import matplotlib.pyplot as plt
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 깨짐 방지

from conformal_dev import (
    build_real_til_true, make_fake_predictions, conformal_calibrate,
    conformal_predict,
)

CUTOFF = 10.0


def policy_A(til_pred):
    """기권 없음: 전원 자동 판정"""
    pred_label = np.where(til_pred >= CUTOFF, "HIGH", "LOW")
    abstain = np.zeros(len(til_pred), dtype=bool)
    return pred_label, abstain


def policy_B(til_pred, sigma, t):
    """불확실성 임계값: sigma > t 면 기권"""
    abstain = sigma > t
    pred_label = np.where(til_pred >= CUTOFF, "HIGH", "LOW")
    return pred_label, abstain


def policy_C(til_pred, lower, upper):
    """컷오프 교차: 구간이 컷오프를 가로지르면 기권"""
    abstain = (lower <= CUTOFF) & (CUTOFF <= upper)
    pred_label = np.where(til_pred >= CUTOFF, "HIGH", "LOW")
    return pred_label, abstain


def evaluate(pred_label, abstain, til_true):
    """기권율, 자동처리분 정확도 계산"""
    true_label = np.where(til_true >= CUTOFF, "HIGH", "LOW")
    kept = ~abstain
    abstain_rate = abstain.mean()
    if kept.sum() == 0:
        acc = np.nan
    else:
        acc = (pred_label[kept] == true_label[kept]).mean()
    return abstain_rate, acc


if __name__ == "__main__":
    DATA_DIR = r"C:\Users\deeplearning\bcss_data"
    MASK_DIR = DATA_DIR + r"\masks"

    roi_ids, til_true = build_real_til_true(MASK_DIR)
    til_pred, sigma, til_mc = make_fake_predictions(til_true)

    n = len(til_true)
    n_calib = n // 2
    calib_idx = np.arange(n_calib)
    test_idx = np.arange(n_calib, n)

    # ---- 정책 A ----
    pred_A, abst_A = policy_A(til_pred[test_idx])
    rate_A, acc_A = evaluate(pred_A, abst_A, til_true[test_idx])
    print(f"[A] 기권율 {rate_A:.1%}, 정확도 {acc_A:.1%}")

    # ---- 정책 B: t를 훑는다 ----
    t_values = np.linspace(sigma.min(), sigma.max(), 30)
    rates_B, accs_B = [], []
    for t in t_values:
        pred_B, abst_B = policy_B(til_pred[test_idx], sigma[test_idx], t)
        r, a = evaluate(pred_B, abst_B, til_true[test_idx])
        rates_B.append(r)
        accs_B.append(a)

    # ---- 정책 C: alpha를 훑는다 (매번 보정셋으로 q 다시 계산) ----
    alpha_values = np.linspace(0.03, 0.9, 30)
    rates_C, accs_C = [], []
    for alpha in alpha_values:
        q = conformal_calibrate(
            til_pred[calib_idx], til_true[calib_idx], sigma[calib_idx], alpha=alpha)
        lower, upper = conformal_predict(til_pred[test_idx], sigma[test_idx], q)
        pred_C, abst_C = policy_C(til_pred[test_idx], lower, upper)
        r, a = evaluate(pred_C, abst_C, til_true[test_idx])
        rates_C.append(r)
        accs_C.append(a)

    # ---- 그래프 ----
    plt.figure(figsize=(7, 5))
    plt.scatter([rate_A], [acc_A], color="black", label="A (기권 없음)", zorder=5)
    plt.plot(rates_B, accs_B, marker="o", label="B (불확실성 임계값)")
    plt.plot(rates_C, accs_C, marker="s", label="C (컷오프 교차, 우리 방법)")
    plt.xlabel("기권율")
    plt.ylabel("자동처리분 정확도")
    plt.legend()
    plt.title("기권 정책 비교 (가짜 예측 기반, 검증용)")
    plt.savefig("abstain_policy_comparison.png")
    print("결과를 abstain_policy_comparison.png로 저장했다.")