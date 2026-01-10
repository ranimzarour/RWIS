using UnityEngine;
using TMPro;

public class DanceComparator : MonoBehaviour
{
    [Header("UI")]
    public TextMeshProUGUI scoreText;

    [Header("Avatars")]
    public Animator referenceAnimator; // UnityChan_Pro
    public Animator playerAnimator;    // MocopiAvatar

    [Header("Temporal Settings")]
    [Tooltip("Tolérance temporelle en frames (±X). Induit ~X frames de latence car on score le centre de la fenêtre.")]
    [Min(0)] public int temporalToleranceFrames = 5;

    [Tooltip("Calcule/affiche un score toutes les n frames.")]
    [Min(1)] public int scoreEveryNFrames = 10;

    [Tooltip("Si true, déclenche EndDance() quand l'anim de référence est finie (si non-loop).")]
    public bool autoEndWhenReferenceEnds = true;

    // -----------------------------
    // Pose scoring (rotations)
    // -----------------------------
    [Header("Pose Weights (rotations)")]
    [Tooltip("Poids pour mains + pieds (pose rotation).")]
    public float weightHandsFeet = 70f;

    [Tooltip("Poids pour hanches (pose rotation).")]
    public float weightHips = 50f;

    [Tooltip("Poids pour tête (pose rotation).")]
    public float weightHead = 30f;

    [Tooltip("Poids par défaut pour les autres os (pose rotation).")]
    public float weightDefault = 40f;

    [Header("Pose Tolerance")]
    [Tooltip("Au-delà de cet angle moyen pondéré (degrés), le PoseScore tombe à 0.")]
    [Min(1f)] public float maxWeightedAngleForZeroPoseScore = 45f;

    // -----------------------------
    // End-effector position scoring
    // -----------------------------
    [Header("Position (hands/feet)")]
    [Tooltip("Poids de la composante position dans le score final.")]
    [Range(0f, 1f)] public float positionScoreWeight = 0.25f;

    [Tooltip("Distance moyenne (m) au-delà de laquelle le PositionScore tombe à 0.")]
    [Min(0.001f)] public float maxPositionErrorForZeroPositionScore = 0.25f;

    [Tooltip("Comparer positions relatives aux hanches (recommandé).")]
    public bool useHipsRelativePositions = true;

    // -----------------------------
    // Rhythm / velocity scoring
    // -----------------------------
    [Header("Rhythm (hands/feet velocities)")]
    [Tooltip("Poids de la composante rythme (vitesse) dans le score final.")]
    [Range(0f, 1f)] public float rhythmScoreWeight = 0.25f;

    [Tooltip("Différence moyenne de vitesse (m/s) au-delà de laquelle le RhythmScore tombe à 0.")]
    [Min(0.001f)] public float maxVelocityErrorForZeroRhythmScore = 2.0f;

    [Tooltip("Si true, compare uniquement la magnitude (speed) des vitesses. Plus robuste au bruit.")]
    public bool compareVelocityMagnitudeOnly = true;

    [Tooltip("Comparer vitesses relatives aux hanches (recommandé).")]
    public bool useHipsRelativeVelocities = true;

    // -----------------------------
    // Final mix
    // -----------------------------
    [Header("Final Mix")]
    [Tooltip("Poids de la pose (rotations) dans le score final.")]
    [Range(0f, 1f)] public float poseScoreWeight = 0.50f;

    // -----------------------------
    // Debug / Output
    // -----------------------------
    [Header("Debug / Output")]
    [Range(0, 100)] public float accuracyPercentage;         // score courant (meilleur shift) en %
    [Range(0, 100)] public float finalAccuracyPercentage;    // moyenne des scores échantillonnés

    [Header("Debug - Best match details")]
    public int bestTemporalShift;                 // shift choisi dans [-X..X]
    public float lastPoseScore01;                 // 0..1
    public float lastPositionScore01;             // 0..1 (si utilisé)
    public float lastRhythmScore01;               // 0..1 (si utilisé)
    public float lastWeightedPoseAngleErrorDeg;   // degrés
    public float lastAvgPositionErrorM;           // mètres
    public float lastAvgVelocityError;            // m/s (ou diff speed)

    // -----------------------------
    // Bones
    // -----------------------------
    private HumanBodyBones[] bonesToEvaluate = new HumanBodyBones[]
    {
        HumanBodyBones.Hips,
        HumanBodyBones.Spine,
        HumanBodyBones.Head,

        HumanBodyBones.LeftUpperArm, HumanBodyBones.LeftLowerArm, HumanBodyBones.LeftHand,
        HumanBodyBones.RightUpperArm, HumanBodyBones.RightLowerArm, HumanBodyBones.RightHand,

        HumanBodyBones.LeftUpperLeg, HumanBodyBones.LeftLowerLeg, HumanBodyBones.LeftFoot,
        HumanBodyBones.RightUpperLeg, HumanBodyBones.RightLowerLeg, HumanBodyBones.RightFoot
    };

    private int hipsIndex = -1;

    private int[] endEffectorIndices; // mains + pieds

    // -----------------------------
    // Buffer (allocation-free)
    // -----------------------------
    private class PoseFrame
    {
        public Quaternion[] rot;
        public Vector3[] pos;
        public Vector3[] vel;
        public bool[] valid;
        public bool[] velValid;

        public PoseFrame(int boneCount)
        {
            rot = new Quaternion[boneCount];
            pos = new Vector3[boneCount];
            vel = new Vector3[boneCount];
            valid = new bool[boneCount];
            velValid = new bool[boneCount];
        }
    }

    private PoseFrame[] refRing;
    private PoseFrame[] playerRing;
    private int ringWriteIndex = 0;
    private int ringCount = 0;
    private int lastBufferSize = -1;

    // For velocities (needs previous sample per avatar)
    private Vector3[] prevRefPos;
    private bool[] prevRefValid;
    private bool hasPrevRef = false;

    private Vector3[] prevPlayerPos;
    private bool[] prevPlayerValid;
    private bool hasPrevPlayer = false;

    // Score accumulation
    private int frameCounter = 0;
    private float sumScores = 0f;
    private int scoreCount = 0;
    private bool ended = false;

    private int BufferSize => (temporalToleranceFrames * 2) + 1;

    void OnEnable()
    {
        ResetDance();
    }

    public void ResetDance()
    {
        ended = false;
        frameCounter = 0;
        sumScores = 0f;
        scoreCount = 0;

        accuracyPercentage = 0f;
        finalAccuracyPercentage = 0f;

        bestTemporalShift = 0;
        lastPoseScore01 = 0f;
        lastPositionScore01 = 0f;
        lastRhythmScore01 = 0f;
        lastWeightedPoseAngleErrorDeg = 0f;
        lastAvgPositionErrorM = 0f;
        lastAvgVelocityError = 0f;

        BuildBoneIndices();
        InitOrResizeBuffersIfNeeded(force: true);

        hasPrevRef = false;
        hasPrevPlayer = false;

        if (prevRefValid != null) System.Array.Clear(prevRefValid, 0, prevRefValid.Length);
        if (prevPlayerValid != null) System.Array.Clear(prevPlayerValid, 0, prevPlayerValid.Length);

        UpdateUI(isFinal: false, showWarmup: true);
    }

    void LateUpdate()
    {
        if (ended) return;
        if (referenceAnimator == null || playerAnimator == null) return;

        BuildBoneIndices();
        InitOrResizeBuffersIfNeeded(force: false);

        // 1) Capture poses in ring buffer
        CapturePose(referenceAnimator, refRing[ringWriteIndex], ref prevRefPos, ref prevRefValid, ref hasPrevRef);
        CapturePose(playerAnimator, playerRing[ringWriteIndex], ref prevPlayerPos, ref prevPlayerValid, ref hasPrevPlayer);

        ringWriteIndex = (ringWriteIndex + 1) % BufferSize;
        ringCount = Mathf.Min(ringCount + 1, BufferSize);

        frameCounter++;

        // 2) Score every N frames once buffer is full
        if (ringCount == BufferSize && (frameCounter % scoreEveryNFrames == 0))
        {
            ComputeScoreWithTemporalTolerance();

            sumScores += accuracyPercentage;
            scoreCount++;

            UpdateUI(isFinal: false, showWarmup: false);
        }

        // 3) Auto end
        if (autoEndWhenReferenceEnds && IsReferenceAnimationFinished())
        {
            EndDance();
        }
    }

    public void EndDance()
    {
        if (ended) return;
        ended = true;

        finalAccuracyPercentage = (scoreCount > 0) ? (sumScores / scoreCount) : 0f;
        UpdateUI(isFinal: true, showWarmup: false);

        Debug.Log($"[DanceComparator] Final score: {finalAccuracyPercentage:F1}% (samples: {scoreCount})");
    }

    // -----------------------------
    // Setup helpers
    // -----------------------------
    private void BuildBoneIndices()
    {
        if (hipsIndex < 0)
        {
            for (int i = 0; i < bonesToEvaluate.Length; i++)
            {
                if (bonesToEvaluate[i] == HumanBodyBones.Hips)
                {
                    hipsIndex = i;
                    break;
                }
            }
        }

        if (endEffectorIndices == null || endEffectorIndices.Length == 0)
        {
            System.Collections.Generic.List<int> idx = new System.Collections.Generic.List<int>(4);
            for (int i = 0; i < bonesToEvaluate.Length; i++)
            {
                var b = bonesToEvaluate[i];
                if (b == HumanBodyBones.LeftHand || b == HumanBodyBones.RightHand ||
                    b == HumanBodyBones.LeftFoot || b == HumanBodyBones.RightFoot)
                {
                    idx.Add(i);
                }
            }
            endEffectorIndices = idx.ToArray();
        }
    }

    private void InitOrResizeBuffersIfNeeded(bool force)
    {
        int size = BufferSize;
        if (!force && size == lastBufferSize && refRing != null && playerRing != null) return;

        lastBufferSize = size;

        refRing = new PoseFrame[size];
        playerRing = new PoseFrame[size];
        for (int i = 0; i < size; i++)
        {
            refRing[i] = new PoseFrame(bonesToEvaluate.Length);
            playerRing[i] = new PoseFrame(bonesToEvaluate.Length);
        }

        ringWriteIndex = 0;
        ringCount = 0;

        // prev arrays for velocities
        int n = bonesToEvaluate.Length;
        if (prevRefPos == null || prevRefPos.Length != n)
        {
            prevRefPos = new Vector3[n];
            prevRefValid = new bool[n];
        }
        if (prevPlayerPos == null || prevPlayerPos.Length != n)
        {
            prevPlayerPos = new Vector3[n];
            prevPlayerValid = new bool[n];
        }
    }

    private void CapturePose(
        Animator anim,
        PoseFrame dst,
        ref Vector3[] prevPos,
        ref bool[] prevValid,
        ref bool hasPrev)
    {
        float dt = Time.deltaTime;
        if (dt <= 1e-6f) dt = 1f / 60f;

        for (int i = 0; i < bonesToEvaluate.Length; i++)
        {
            Transform t = anim.GetBoneTransform(bonesToEvaluate[i]);
            if (t != null)
            {
                Vector3 p = t.position;
                Quaternion r = t.rotation;

                dst.pos[i] = p;
                dst.rot[i] = r;
                dst.valid[i] = true;

                if (hasPrev && prevValid[i])
                {
                    dst.vel[i] = (p - prevPos[i]) / dt;
                    dst.velValid[i] = true;
                }
                else
                {
                    dst.vel[i] = Vector3.zero;
                    dst.velValid[i] = false;
                }

                prevPos[i] = p;
                prevValid[i] = true;
            }
            else
            {
                dst.valid[i] = false;
                dst.velValid[i] = false;
                prevValid[i] = false;
            }
        }

        hasPrev = true;
    }

    // -----------------------------
    // Ring indexing
    // -----------------------------
    private int OldestIndex()
    {
        int idx = ringWriteIndex - ringCount;
        if (idx < 0) idx += BufferSize;
        return idx;
    }

    private int RingIndexFromOldest(int offset)
    {
        int idx = OldestIndex() + offset;
        idx %= BufferSize;
        return idx;
    }

    // -----------------------------
    // Scoring (temporal tolerance)
    // -----------------------------
    private void ComputeScoreWithTemporalTolerance()
    {
        int centerOffset = temporalToleranceFrames; // 0..2X
        int refCenterIdx = RingIndexFromOldest(centerOffset);
        PoseFrame refPose = refRing[refCenterIdx];

        float bestScore01 = -1f;

        int bestShift = 0;
        float bestPoseScore = 0f, bestPosScore = 0f, bestRhythmScore = 0f;
        float bestPoseErr = 0f, bestPosErr = 0f, bestVelErr = 0f;

        for (int shift = -temporalToleranceFrames; shift <= temporalToleranceFrames; shift++)
        {
            int playerOffset = centerOffset + shift;
            int playerIdx = RingIndexFromOldest(playerOffset);
            PoseFrame playerPose = playerRing[playerIdx];

            // Compute sub-scores
            float poseScore01, poseErrDeg;
            bool poseOk = ComputePoseScore(refPose, playerPose, out poseScore01, out poseErrDeg);

            float posScore01, posErrM;
            bool posOk = ComputeEndEffectorPositionScore(refPose, playerPose, out posScore01, out posErrM);

            float rhythmScore01, velErr;
            bool rhythmOk = ComputeEndEffectorRhythmScore(refPose, playerPose, out rhythmScore01, out velErr);

            // Dynamic mix: ignore components that are invalid
            float wPose = poseOk ? poseScoreWeight : 0f;
            float wPos = posOk ? positionScoreWeight : 0f;
            float wRhythm = rhythmOk ? rhythmScoreWeight : 0f;

            float wSum = wPose + wPos + wRhythm;
            if (wSum <= 1e-6f) continue;

            float combined01 = (wPose * poseScore01 + wPos * posScore01 + wRhythm * rhythmScore01) / wSum;

            if (combined01 > bestScore01)
            {
                bestScore01 = combined01;

                bestShift = shift;

                bestPoseScore = poseScore01;
                bestPosScore = posScore01;
                bestRhythmScore = rhythmScore01;

                bestPoseErr = poseErrDeg;
                bestPosErr = posErrM;
                bestVelErr = velErr;
            }
        }

        if (bestScore01 < 0f) bestScore01 = 0f;

        // Output
        accuracyPercentage = Mathf.Clamp01(bestScore01) * 100f;

        bestTemporalShift = bestShift;

        lastPoseScore01 = bestPoseScore;
        lastPositionScore01 = bestPosScore;
        lastRhythmScore01 = bestRhythmScore;

        lastWeightedPoseAngleErrorDeg = bestPoseErr;
        lastAvgPositionErrorM = bestPosErr;
        lastAvgVelocityError = bestVelErr;
    }

    private bool ComputePoseScore(PoseFrame a, PoseFrame b, out float score01, out float weightedAvgAngleDeg)
    {
        float total = 0f;
        float wsum = 0f;

        for (int i = 0; i < bonesToEvaluate.Length; i++)
        {
            if (!a.valid[i] || !b.valid[i]) continue;

            float w = GetPoseBoneWeight(bonesToEvaluate[i]);
            if (w <= 0f) continue;

            float angle = Quaternion.Angle(a.rot[i], b.rot[i]);
            total += w * angle;
            wsum += w;
        }

        if (wsum <= 1e-6f)
        {
            score01 = 0f;
            weightedAvgAngleDeg = 0f;
            return false;
        }

        weightedAvgAngleDeg = total / wsum;

        float denom = Mathf.Max(1e-6f, maxWeightedAngleForZeroPoseScore);
        score01 = 1f - (weightedAvgAngleDeg / denom);
        score01 = Mathf.Clamp01(score01);
        return true;
    }

    private bool ComputeEndEffectorPositionScore(PoseFrame a, PoseFrame b, out float score01, out float avgErrorMeters)
    {
        // If user disables it by weight = 0, treat as invalid so it won't be mixed.
        if (positionScoreWeight <= 1e-6f || endEffectorIndices == null || endEffectorIndices.Length == 0)
        {
            score01 = 0f;
            avgErrorMeters = 0f;
            return false;
        }

        float total = 0f;
        float wsum = 0f;

        bool hipsOkA = (hipsIndex >= 0 && a.valid[hipsIndex]);
        bool hipsOkB = (hipsIndex >= 0 && b.valid[hipsIndex]);

        Vector3 hipsPosA = hipsOkA ? a.pos[hipsIndex] : Vector3.zero;
        Vector3 hipsPosB = hipsOkB ? b.pos[hipsIndex] : Vector3.zero;

        for (int k = 0; k < endEffectorIndices.Length; k++)
        {
            int i = endEffectorIndices[k];
            if (!a.valid[i] || !b.valid[i]) continue;

            Vector3 pa = a.pos[i];
            Vector3 pb = b.pos[i];

            if (useHipsRelativePositions && hipsOkA && hipsOkB)
            {
                pa = pa - hipsPosA;
                pb = pb - hipsPosB;
            }

            float d = Vector3.Distance(pa, pb);

            float w = weightHandsFeet; // end effectors only
            total += w * d;
            wsum += w;
        }

        if (wsum <= 1e-6f)
        {
            score01 = 0f;
            avgErrorMeters = 0f;
            return false;
        }

        avgErrorMeters = total / wsum;

        float denom = Mathf.Max(1e-6f, maxPositionErrorForZeroPositionScore);
        score01 = 1f - (avgErrorMeters / denom);
        score01 = Mathf.Clamp01(score01);
        return true;
    }

    private bool ComputeEndEffectorRhythmScore(PoseFrame a, PoseFrame b, out float score01, out float avgVelError)
    {
        if (rhythmScoreWeight <= 1e-6f || endEffectorIndices == null || endEffectorIndices.Length == 0)
        {
            score01 = 0f;
            avgVelError = 0f;
            return false;
        }

        float total = 0f;
        float wsum = 0f;

        bool hipsOkA = (hipsIndex >= 0 && a.valid[hipsIndex] && a.velValid[hipsIndex]);
        bool hipsOkB = (hipsIndex >= 0 && b.valid[hipsIndex] && b.velValid[hipsIndex]);

        Vector3 hipsVelA = hipsOkA ? a.vel[hipsIndex] : Vector3.zero;
        Vector3 hipsVelB = hipsOkB ? b.vel[hipsIndex] : Vector3.zero;

        for (int k = 0; k < endEffectorIndices.Length; k++)
        {
            int i = endEffectorIndices[k];

            if (!a.valid[i] || !b.valid[i]) continue;
            if (!a.velValid[i] || !b.velValid[i]) continue;

            Vector3 va = a.vel[i];
            Vector3 vb = b.vel[i];

            if (useHipsRelativeVelocities && hipsOkA && hipsOkB)
            {
                va = va - hipsVelA;
                vb = vb - hipsVelB;
            }

            float err;
            if (compareVelocityMagnitudeOnly)
            {
                err = Mathf.Abs(va.magnitude - vb.magnitude);
            }
            else
            {
                err = Vector3.Distance(va, vb);
            }

            float w = weightHandsFeet;
            total += w * err;
            wsum += w;
        }

        if (wsum <= 1e-6f)
        {
            score01 = 0f;
            avgVelError = 0f;
            return false;
        }

        avgVelError = total / wsum;

        float denom = Mathf.Max(1e-6f, maxVelocityErrorForZeroRhythmScore);
        score01 = 1f - (avgVelError / denom);
        score01 = Mathf.Clamp01(score01);
        return true;
    }

    private float GetPoseBoneWeight(HumanBodyBones bone)
    {
        if (bone == HumanBodyBones.LeftHand || bone == HumanBodyBones.RightHand ||
            bone == HumanBodyBones.LeftFoot || bone == HumanBodyBones.RightFoot)
            return weightHandsFeet;

        if (bone == HumanBodyBones.Hips) return weightHips;
        if (bone == HumanBodyBones.Head) return weightHead;

        return weightDefault;
    }

    // -----------------------------
    // End condition
    // -----------------------------
    private bool IsReferenceAnimationFinished()
    {
        if (referenceAnimator == null) return false;
        if (referenceAnimator.IsInTransition(0)) return false;

        AnimatorStateInfo st = referenceAnimator.GetCurrentAnimatorStateInfo(0);
        if (st.loop) return false;

        return st.normalizedTime >= 1f;
    }

    // -----------------------------
    // UI
    // -----------------------------
    private void UpdateUI(bool isFinal, bool showWarmup)
    {
        if (scoreText == null) return;

        if (showWarmup)
        {
            scoreText.text = "Score: --%";
            scoreText.color = Color.white;
            return;
        }

        float value = isFinal ? finalAccuracyPercentage : accuracyPercentage;

        scoreText.text = isFinal
            ? $"Final Score: {value:F0}%"
            : $"Score: {value:F0}%";

        if (value > 80f) scoreText.color = Color.green;
        else if (value > 50f) scoreText.color = Color.yellow;
        else scoreText.color = Color.red;
    }
}
