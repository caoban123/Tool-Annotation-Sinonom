from typing import List, Dict, Any, Tuple
from .candidate_generation import BaseEmbeddingAdapter

def align_segments_monotonic(
    han_segs: List[Dict[str, Any]],
    viet_segs: List[Dict[str, Any]],
    scorer: BaseEmbeddingAdapter,
    skip_penalty: float = 0.25,
    min_score_threshold: float = 0.35
) -> List[Dict[str, Any]]:
    """
    Finds the optimal monotonic sequence of 1-1, 1-n, n-1, n-m alignments
    using dynamic programming with candidate grouping and skip penalties.
    """
    N = len(han_segs)
    M = len(viet_segs)

    # Allowed transitions: (num_han, num_viet)
    transitions = [
        (1, 1),
        (1, 2),
        (2, 1),
        (2, 2),
        (1, 3),
        (3, 1)
    ]

    # dp[i][j] stores (max_score, parent_state, transition_type)
    dp = [[-1e9] * (M + 1) for _ in range(N + 1)]
    backtrack = [[None] * (M + 1) for _ in range(N + 1)]
    dp[0][0] = 0.0

    for i in range(N + 1):
        for j in range(M + 1):
            if dp[i][j] < -1e8:
                continue

            # Option 1: Skip Han segment
            if i < N:
                score_skip_h = dp[i][j] - skip_penalty
                if score_skip_h > dp[i + 1][j]:
                    dp[i + 1][j] = score_skip_h
                    backtrack[i + 1][j] = (i, j, "skip_han")

            # Option 2: Skip Viet segment
            if j < M:
                score_skip_v = dp[i][j] - skip_penalty
                if score_skip_v > dp[i][j + 1]:
                    dp[i][j + 1] = score_skip_v
                    backtrack[i][j + 1] = (i, j, "skip_viet")

            # Option 3: Valid alignments
            for (dh, dv) in transitions:
                if i + dh <= N and j + dv <= M:
                    h_group = han_segs[i : i + dh]
                    v_group = viet_segs[j : j + dv]

                    h_text = " ".join(s["text"] for s in h_group)
                    v_text = " ".join(s["text"] for s in v_group)

                    sim = scorer.score_pair(h_text, v_text)
                    if sim >= min_score_threshold:
                        new_score = dp[i][j] + sim
                        if new_score > dp[i + dh][j + dv]:
                            dp[i + dh][j + dv] = new_score
                            backtrack[i + dh][j + dv] = (i, j, (dh, dv, sim))

    # Backtrack from (N, M)
    curr_i, curr_j = N, M
    suggestions = []

    while curr_i > 0 or curr_j > 0:
        step = backtrack[curr_i][curr_j]
        if step is None:
            break
        prev_i, prev_j, action = step
        if isinstance(action, tuple):
            dh, dv, score = action
            h_group = han_segs[prev_i : curr_i]
            v_group = viet_segs[prev_j : curr_j]

            if dh == 1 and dv == 1:
                align_type = "1-1"
            elif dh == 1 and dv > 1:
                align_type = "1-n"
            elif dh > 1 and dv == 1:
                align_type = "n-1"
            else:
                align_type = "n-m"

            suggestions.append({
                "han_ids": [s["segment_id"] for s in h_group],
                "viet_ids": [s["segment_id"] for s in v_group],
                "alignment_type": align_type,
                "score": round(score, 3),
                "status": "suggested"
            })

        curr_i, curr_j = prev_i, prev_j

    suggestions.reverse()
    return suggestions
