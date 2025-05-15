using UnityEngine;
using System.Collections.Generic;

public class EMGHandController : MonoBehaviour
{
    [Header("Communication")]
    [SerializeField] private EMGCommunicationHandler communicationHandler;

    [Header("Finger Settings")]
    [SerializeField] private Transform thumbRoot;
    [SerializeField] private Transform indexRoot;
    [SerializeField] private Transform middleRoot;
    [SerializeField] private Transform ringRoot;
    [SerializeField] private Transform littleRoot;

    [Header("Finger Bones")]
    [SerializeField] private Transform[] thumbBones;
    [SerializeField] private Transform[] indexBones;
    [SerializeField] private Transform[] middleBones;
    [SerializeField] private Transform[] ringBones;
    [SerializeField] private Transform[] littleBones;

    [Header("Rotation Limits")]
    [SerializeField] private Vector2 thumbFlexionLimits = new Vector2(0, 60);
    [SerializeField] private Vector2 thumbAbductionLimits = new Vector2(-30, 30);
    [SerializeField] private Vector2 fingerFlexionLimits = new Vector2(0, 90);
    [SerializeField] private Vector2 pinchLimits = new Vector2(0, 25);

    [Header("Animation Settings")]
    [SerializeField] private float smoothing = 5f;
    [SerializeField] private bool smoothMovement = true;

    // Target rotations
    private Dictionary<string, Quaternion> targetRotations = new Dictionary<string, Quaternion>();

    // Previous state for interpolation
    private Dictionary<string, float> prevState = new Dictionary<string, float>();

    void Start()
    {
        if (communicationHandler == null)
        {
            communicationHandler = FindObjectOfType<EMGCommunicationHandler>();

            if (communicationHandler == null)
            {
                Debug.LogError("EMGCommunicationHandler not found! Please assign it in the inspector.");
                enabled = false;
                return;
            }
        }

        // Initialize finger bones if not assigned
        AutoAssignFingerBones();

        // Register for hand state updates
        communicationHandler.OnHandStateUpdated += OnHandStateUpdated;

        // Initialize rotations and states
        InitializeHand();
    }

    void OnDestroy()
    {
        if (communicationHandler != null)
        {
            communicationHandler.OnHandStateUpdated -= OnHandStateUpdated;
        }
    }

    private void AutoAssignFingerBones()
    {
        // Auto-assign finger bones if they're null but the roots are set
        if (thumbBones == null || thumbBones.Length == 0 && thumbRoot != null)
        {
            thumbBones = GetFingerBones(thumbRoot);
        }

        if (indexBones == null || indexBones.Length == 0 && indexRoot != null)
        {
            indexBones = GetFingerBones(indexRoot);
        }

        if (middleBones == null || middleBones.Length == 0 && middleRoot != null)
        {
            middleBones = GetFingerBones(middleRoot);
        }

        if (ringBones == null || ringBones.Length == 0 && ringRoot != null)
        {
            ringBones = GetFingerBones(ringRoot);
        }

        if (littleBones == null || littleBones.Length == 0 && littleRoot != null)
        {
            littleBones = GetFingerBones(littleRoot);
        }
    }

    private Transform[] GetFingerBones(Transform root)
    {
        // Get all child bones in the hierarchy
        List<Transform> bones = new List<Transform>();
        Transform current = root;

        while (current != null)
        {
            bones.Add(current);

            // Try to find child with bone in name
            Transform next = null;
            foreach (Transform child in current)
            {
                if (child.name.ToLower().Contains("bone") ||
                    child.name.ToLower().Contains("joint") ||
                    child.name.ToLower().Contains("phalange"))
                {
                    next = child;
                    break;
                }
            }

            // If no bone-named child found, just take the first child
            if (next == null && current.childCount > 0)
            {
                next = current.GetChild(0);
            }

            current = next;
        }

        return bones.ToArray();
    }

    private void InitializeHand()
    {
        // Store initial rotations
        StoreInitialRotations(thumbBones);
        StoreInitialRotations(indexBones);
        StoreInitialRotations(middleBones);
        StoreInitialRotations(ringBones);
        StoreInitialRotations(littleBones);

        // Initialize previous state
        prevState["thumb_flexion"] = 0f;
        prevState["thumb_extension"] = 0f;
        prevState["thumb_pinching"] = 0f;
        prevState["index_flexion"] = 0f;
        prevState["index_extension"] = 0f;
        prevState["index_pinching"] = 0f;
        prevState["middle_flexion"] = 0f;
        prevState["middle_extension"] = 0f;
        prevState["middle_pinching"] = 0f;
        prevState["ring_little_flexion"] = 0f;
        prevState["ring_little_extension"] = 0f;
        prevState["thumb_abduction"] = 0f;
    }

    private void StoreInitialRotations(Transform[] bones)
    {
        if (bones == null) return;

        foreach (Transform bone in bones)
        {
            if (bone != null)
            {
                targetRotations[bone.name] = bone.localRotation;
            }
        }
    }

    private void OnHandStateUpdated(Dictionary<string, float> state)
    {
        // Calculate joint rotations based on the updated hand state
        UpdateHandAnimations(state);
    }

    void Update()
    {
        if (communicationHandler == null) return;

        // Apply current rotations to the hand
        ApplyRotationsToHand();
    }

    private void UpdateHandAnimations(Dictionary<string, float> state)
    {
        // Handle thumb animations
        float thumbFlex = 0;
        if (state.ContainsKey("thumb_flexion"))
        {
            thumbFlex = state["thumb_flexion"];

            // Cancel out extension if both are present
            if (state.ContainsKey("thumb_extension") && state["thumb_extension"] > 0)
            {
                thumbFlex = Mathf.Max(0, thumbFlex - state["thumb_extension"]);
            }
        }

        // Thumb abduction
        float thumbAbduction = 0;
        if (state.ContainsKey("thumb_abduction"))
        {
            thumbAbduction = state["thumb_abduction"];
        }

        // Finger flexions
        float indexFlex = GetFingerFlexion(state, "index");
        float middleFlex = GetFingerFlexion(state, "middle");
        float ringLittleFlex = GetFingerFlexion(state, "ring_little");

        // Apply animation to thumb
        if (thumbBones != null && thumbBones.Length > 0)
        {
            // Base/CMC joint rotation (abduction)
            if (thumbBones.Length > 0 && thumbBones[0] != null)
            {
                Quaternion baseRot = targetRotations[thumbBones[0].name];
                Quaternion abduction = Quaternion.Euler(
                    Mathf.Lerp(thumbAbductionLimits.x, thumbAbductionLimits.y, thumbAbduction),
                    0, 0);
                thumbBones[0].localRotation = baseRot * abduction;
            }

            // Apply flexion to other joints
            for (int i = 1; i < thumbBones.Length; i++)
            {
                if (thumbBones[i] != null)
                {
                    Quaternion baseRot = targetRotations[thumbBones[i].name];
                    float thumbJointFlex = thumbFlex;

                    // Apply pinching to the last joint (distal) if applicable
                    if (i == thumbBones.Length - 1 && state.ContainsKey("thumb_pinching"))
                    {
                        thumbJointFlex += state["thumb_pinching"] * pinchLimits.y / thumbFlexionLimits.y;
                    }

                    Quaternion flexion = Quaternion.Euler(
                        0,
                        0,
                        Mathf.Lerp(thumbFlexionLimits.x, thumbFlexionLimits.y, thumbJointFlex));

                    targetRotations[thumbBones[i].name] = baseRot * flexion;
                }
            }
        }

        // Apply animation to other fingers
        ApplyFingerAnimation(indexBones, indexFlex, state.ContainsKey("index_pinching") ? state["index_pinching"] : 0);
        ApplyFingerAnimation(middleBones, middleFlex, state.ContainsKey("middle_pinching") ? state["middle_pinching"] : 0);
        ApplyFingerAnimation(ringBones, ringLittleFlex, 0);
        ApplyFingerAnimation(littleBones, ringLittleFlex, 0);

        // Update previous state for interpolation
        foreach (var key in state.Keys)
        {
            prevState[key] = state[key];
        }
    }

    private float GetFingerFlexion(Dictionary<string, float> state, string fingerName)
    {
        float flex = 0;
        string flexKey = fingerName + "_flexion";
        string extKey = fingerName + "_extension";

        if (state.ContainsKey(flexKey))
        {
            flex = state[flexKey];

            // Cancel out extension if both are present
            if (state.ContainsKey(extKey) && state[extKey] > 0)
            {
                flex = Mathf.Max(0, flex - state[extKey]);
            }
        }

        return flex;
    }

    private void ApplyFingerAnimation(Transform[] bones, float flexion, float pinching)
    {
        if (bones == null || bones.Length == 0) return;

        for (int i = 0; i < bones.Length; i++)
        {
            if (bones[i] != null)
            {
                Quaternion baseRot = targetRotations[bones[i].name];

                // Skip the base/metacarpal joint for regular fingers
                if (i == 0) continue;

                // Progressively increase flexion for more distal joints
                float jointFlexion = flexion * (1.0f + 0.2f * i);  // More bend at fingertips

                // Apply pinching to the last joint (distal) if applicable
                if (i == bones.Length - 1 && pinching > 0)
                {
                    jointFlexion += pinching * pinchLimits.y / fingerFlexionLimits.y;
                }

                Quaternion flexion_rot = Quaternion.Euler(
                    0,
                    0,
                    Mathf.Lerp(fingerFlexionLimits.x, fingerFlexionLimits.y, jointFlexion));

                targetRotations[bones[i].name] = baseRot * flexion_rot;
            }
        }
    }

    private void ApplyRotationsToHand()
    {
        // Apply all rotations with smoothing
        ApplyBoneRotations(thumbBones);
        ApplyBoneRotations(indexBones);
        ApplyBoneRotations(middleBones);
        ApplyBoneRotations(ringBones);
        ApplyBoneRotations(littleBones);
    }

    private void ApplyBoneRotations(Transform[] bones)
    {
        if (bones == null) return;

        foreach (Transform bone in bones)
        {
            if (bone != null && targetRotations.ContainsKey(bone.name))
            {
                if (smoothMovement)
                {
                    bone.localRotation = Quaternion.Slerp(
                        bone.localRotation,
                        targetRotations[bone.name],
                        Time.deltaTime * smoothing);
                }
                else
                {
                    bone.localRotation = targetRotations[bone.name];
                }
            }
        }
    }
}