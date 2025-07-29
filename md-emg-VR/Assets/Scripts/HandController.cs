using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;


public class HandController : MonoBehaviour
{
    // Array of fingers; each finger has nested joints.
    public Transform[] fingers;

    private HandConfig handConfig = new();
    private AnimationConfig animationConfig = new();

    // List of rotation arrays, one per finger, containing initial rotations for each joint.
    private List<Quaternion[]> initialRotations;
    private Coroutine animationCoroutine = null;
    private bool isAnimating = false; // Flag to track if the hand is animating
    private bool isGrasping = false; // Flag to track if the hand is grasping

    private void Start()
    {
        // Load configs
        string configPath = Path.Combine(Application.dataPath, "Config");

        string json = File.ReadAllText(Path.Combine(configPath, "HandConfig.json"));
        handConfig = JsonUtility.FromJson<HandConfig>(json);

        json = File.ReadAllText(Path.Combine(configPath, "AnimationConfig.json"));
        animationConfig = JsonUtility.FromJson<AnimationConfig>(json);

        initialRotations = new List<Quaternion[]>();

        // Loop through each finger and record the local rotations of all its joints.
        foreach (Transform finger in fingers)
        {
            // Get all joints (including the finger root) in each finger.
            Transform[] joints = finger.GetComponentsInChildren<Transform>();
            Quaternion[] rotations = new Quaternion[joints.Length];

            for (int i = 0; i < joints.Length; i++)
            {
                rotations[i] = joints[i].localRotation;
            }

            initialRotations.Add(rotations);
        }
    }

    public Coroutine StartGrasp(string graspName)
    {
        if (isAnimating)
        {
            StopCoroutine(animationCoroutine);
        }

        // Get target rotations from the XML file using HandAngles.
        // Convert the returned Quaternion[] to a List<Quaternion[]>.
        List<Quaternion[]> targetRotations = HandAngles.GetGraspRotations(graspName);
        animationCoroutine = StartCoroutine(AnimateFingers(targetRotations, graspAnimation: true));

        return animationCoroutine;
    }

    public void StopAnimation()
    {
        if (isAnimating)
        {
            StopCoroutine(animationCoroutine);
            isAnimating = false; // Reset the animation flag
        }
    }

    public Coroutine ReleaseGrasp()
    {
        if (isAnimating)
        {
            StopCoroutine(animationCoroutine);
        }

        // Return to initial rotations.
        animationCoroutine = StartCoroutine(AnimateFingers(initialRotations, graspAnimation: false));
        isGrasping = false; // Reset the grasping flag

        return animationCoroutine;
    }

    private IEnumerator AnimateFingers(List<Quaternion[]> targetRotations, bool graspAnimation = false)
    {
        isAnimating = true;
        float duration = 1f / animationConfig.speedHz;
        float elapsedTime = 0f;

        // Store current rotations for each joint of each finger.
        List<Quaternion[]> startRotations = new List<Quaternion[]>();
        foreach (Transform finger in fingers)
        {
            Transform[] joints = finger.GetComponentsInChildren<Transform>();
            Quaternion[] rotations = new Quaternion[joints.Length];
            for (int i = 0; i < joints.Length; i++)
            {
                rotations[i] = joints[i].localRotation;
            }
            startRotations.Add(rotations);
        }

        // Animate each joint of each finger.
        while (elapsedTime < duration)
        {
            elapsedTime += Time.deltaTime;
            float t = Mathf.Clamp01(elapsedTime / duration);

            for (int fI = 0; fI < fingers.Length; fI++)
            {
                Transform[] joints = fingers[fI].GetComponentsInChildren<Transform>();
                for (int jI = 0; jI < handConfig.numJoints; jI++)
                {
                    joints[jI].localRotation = Quaternion.Slerp(startRotations[fI][jI], targetRotations[fI][jI], t);
                }
            }

            yield return null;
        }

        // Ensure all joints are set to their target rotations.
        for (int fingerIndex = 0; fingerIndex < fingers.Length; fingerIndex++)
        {
            Transform[] joints = fingers[fingerIndex].GetComponentsInChildren<Transform>();
            for (int jointIndex = 0; jointIndex < handConfig.numJoints; jointIndex++)
            {
                joints[jointIndex].localRotation = targetRotations[fingerIndex][jointIndex];
            }
        }

        isAnimating = false;

        // If grasp animation is true, set the isGrasping flag.
        if (graspAnimation)
        {
            isGrasping = true;
        }
    }

    public bool IsAnimating
    {
        get { return isAnimating; }
    }

    public bool IsGrasping
    {
        get { return isGrasping; }
    }
}