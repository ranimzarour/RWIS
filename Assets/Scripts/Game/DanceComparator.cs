using UnityEngine;
using TMPro; // Don't forget this namespace for UI

public class DanceComparator : MonoBehaviour
{
    [Header("UI")]
    public TextMeshProUGUI scoreText; // Field to drag your text object into

    [Header("Avatars")]
    public Animator referenceAnimator; // UnityChan_Pro
    public Animator playerAnimator;    // MocopiAvatar

    [Header("Settings")]
    // List of bones to evaluate for the score
    private HumanBodyBones[] bonesToEvaluate = new HumanBodyBones[]
    {
        HumanBodyBones.Hips,
        HumanBodyBones.Spine,
        HumanBodyBones.Head,
        HumanBodyBones.LeftUpperArm, HumanBodyBones.LeftLowerArm,
        HumanBodyBones.RightUpperArm, HumanBodyBones.RightLowerArm,
        HumanBodyBones.LeftUpperLeg, HumanBodyBones.LeftLowerLeg,
        HumanBodyBones.RightUpperLeg, HumanBodyBones.RightLowerLeg
    };

    [Header("Debug / Output")]
    public float currentErrorScore; // 0 = Perfect, > 0 = Error
    public float accuracyPercentage;

    void Update()
    {
        if (referenceAnimator == null || playerAnimator == null) return;

        CalculateDanceScore();
        UpdateUI();
    }

    void CalculateDanceScore()
    {
        float totalAngleDifference = 0f;
        int activeBoneCount = 0;

        foreach (HumanBodyBones boneName in bonesToEvaluate)
        {
            // Retrieve bone Transforms from the Animators
            Transform refBone = referenceAnimator.GetBoneTransform(boneName);
            Transform playerBone = playerAnimator.GetBoneTransform(boneName);

            // Ensure both avatars actually have this bone mapped
            if (refBone != null && playerBone != null)
            {
                // Compare rotation (global rotation is usually safer for world-space comparison)
                // Quaternion.Angle returns the difference in degrees
                float diff = Quaternion.Angle(refBone.rotation, playerBone.rotation);
                
                totalAngleDifference += diff;
                activeBoneCount++;
            }
        }

        if (activeBoneCount > 0)
        {
            // Calculate average error across all evaluated bones
            currentErrorScore = totalAngleDifference / activeBoneCount;

            // Simple percentage conversion (adjust 45.0f based on desired tolerance)
            // If average error is > 45 degrees, the score is 0%
            float score = 1.0f - (currentErrorScore / 45.0f);
            accuracyPercentage = Mathf.Clamp01(score) * 100f;
        }
    }

    void UpdateUI()
    {
        if (scoreText != null)
        {
            // Update the text with the score, formatted to 0 decimal places
            scoreText.text = "Score: " + accuracyPercentage.ToString("F0") + "%";
            
            // Optional: Change color based on performance
            if (accuracyPercentage > 80) scoreText.color = Color.green;
            else if (accuracyPercentage > 50) scoreText.color = Color.yellow;
            else scoreText.color = Color.red;
        }
    }
}