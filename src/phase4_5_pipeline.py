import ast
import numpy as np
import pandas as pd
import os

CUTOFF = 10.0


def load_til_results(csv_path):
    """til_results_{model}.csv 로드. til_mc 컬럼은 문자열로 저장된 리스트일 수 있어 파싱한다."""
    df = pd.read_csv(csv_path)
    if df['til_mc'].dtype == object:
        df['til_mc'] = df['til_mc'].apply(ast.literal_eval)
    return df


def conformal_calibrate(til_pred, til_true, sigma, alpha=0.10, eps=1e-6):
    scores = np.abs(til_pred - til_true) / (sigma + eps)
    n = len(scores)
    k = int(np.ceil((n + 1) * (1 - alpha)))
    if k > n:
        return np.inf
    return np.sort(scores)[k - 1]


def run_phase4(df, calib_roi_ids, test_roi_ids, alpha=0.10, out_csv=None):
    """보정셋으로 q 산출 -> 테스트셋에 구간 적용 -> covered 계산 -> CSV 저장"""
    calib = df[df['roi_id'].isin(calib_roi_ids)]
    test = df[df['roi_id'].isin(test_roi_ids)].copy()

    q = conformal_calibrate(
        calib['til_pred'].values, calib['til_true'].values, calib['sigma'].values, alpha=alpha)

    test['lower'] = test['til_pred'] - q * test['sigma']
    test['upper'] = test['til_pred'] + q * test['sigma']
    test['covered'] = (test['til_true'] >= test['lower']) & (test['til_true'] <= test['upper'])

    coverage = test['covered'].mean()
    print(f"q = {q:.3f}, 커버리지 = {coverage:.1%}")

    if out_csv:
        test.to_csv(out_csv, index=False)
        print(f"저장: {out_csv}")

    return test, q


def policy_A(til_pred):
    abstain = np.zeros(len(til_pred), dtype=bool)
    pred_label = np.where(til_pred >= CUTOFF, "HIGH", "LOW")
    return pred_label, abstain


def policy_B(til_pred, sigma, t):
    abstain = sigma > t
    pred_label = np.where(til_pred >= CUTOFF, "HIGH", "LOW")
    return pred_label, abstain


def policy_C(til_pred, lower, upper):
    abstain = (lower <= CUTOFF) & (CUTOFF <= upper)
    pred_label = np.where(til_pred >= CUTOFF, "HIGH", "LOW")
    return pred_label, abstain


def evaluate_policy(pred_label, abstain, til_true):
    true_label = np.where(til_true >= CUTOFF, "HIGH", "LOW")
    kept = ~abstain
    abstain_rate = abstain.mean()
    acc = np.nan if kept.sum() == 0 else (pred_label[kept] == true_label[kept]).mean()
    return abstain_rate, acc


def run_phase5(test_df, sigma_threshold=None, out_csv=None):
    """정책 A/B/C 평가 -> abstention_{model}.csv 저장"""
    til_pred = test_df['til_pred'].values
    til_true = test_df['til_true'].values
    sigma = test_df['sigma'].values
    lower = test_df['lower'].values
    upper = test_df['upper'].values

    if sigma_threshold is None:
        sigma_threshold = np.median(sigma)  # 기본값: 중앙값 기준

    results = []

    pred, abst = policy_A(til_pred)
    rate, acc = evaluate_policy(pred, abst, til_true)
    results.append({"정책": "A (기권 없음)", "기권율": rate, "자동처리 정확도": acc})

    pred, abst = policy_B(til_pred, sigma, sigma_threshold)
    rate, acc = evaluate_policy(pred, abst, til_true)
    results.append({"정책": f"B (t={sigma_threshold:.2f})", "기권율": rate, "자동처리 정확도": acc})

    pred, abst = policy_C(til_pred, lower, upper)
    rate, acc = evaluate_policy(pred, abst, til_true)
    results.append({"정책": "C (컷오프 교차)", "기권율": rate, "자동처리 정확도": acc})

    result_df = pd.DataFrame(results)
    print(result_df)

    if out_csv:
        result_df.to_csv(out_csv, index=False)
        print(f"저장: {out_csv}")

    return result_df


if __name__ == "__main__":
    # ---- 아직 진짜 CSV가 없으니, 가짜 til_results_unet.csv를 만들어서 파이프라인 전체를 테스트한다 ----
    from conformal_dev import build_real_til_true, make_fake_predictions

    DATA_DIR = r"C:\Users\deeplearning\bcss_data"
    MASK_DIR = DATA_DIR + r"\masks"

    roi_ids, til_true = build_real_til_true(MASK_DIR)
    til_pred, sigma, til_mc = make_fake_predictions(til_true)

    fake_df = pd.DataFrame({
        "roi_id": roi_ids,
        "til_true": til_true,
        "til_pred": til_pred,
        "sigma": sigma,
        "til_mc": [list(row) for row in til_mc],
    })
    os.makedirs("outputs", exist_ok=True)
    
    fake_df.to_csv("outputs/til_results_unet_FAKE.csv", index=False)
    print("가짜 til_results_unet_FAKE.csv 생성 완료. 이제부터 이 파일을 '실제 파일'인 것처럼 읽는다.")

    # ---- 여기서부터는 진짜 파일이 왔을 때와 똑같은 흐름 ----
    df = load_til_results("til_results_unet_FAKE.csv")

    n = len(df)
    n_calib = n // 2
    calib_ids = df['roi_id'].values[:n_calib]
    test_ids = df['roi_id'].values[n_calib:]

    test_df, q = run_phase4(df, calib_ids, test_ids, alpha=0.10, out_csv="outputs/conformal_unet_FAKE.csv")
    run_phase5(test_df, out_csv="outputs/abstention_unet_FAKE.csv")