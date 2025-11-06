using System.Collections;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 3D Hand Model Controller for Proportional Control
/// Provides realistic hand animation and visual feedback
/// </summary>
public class ProportionalHandModel : MonoBehaviour
{
    [Header("Hand Configuration")]
    public HandType handType = HandType.Right;
    public bool enablePhysics = false;
    public float animationSpeed = 5f;
    
    [Header("Finger Joint References")]
    public FingerJoints thumbJoints;
    public FingerJoints indexJoints;
    public FingerJoints middleJoints;
    public FingerJoints ringJoints;
    public FingerJoints pinkyJoints;
    
    [Header("Visual Feedback")]
    public Material[] fingerMaterials = new Material[5];
    public Color normalColor = Color.white;
    public Color forceColor = Color.red;
    public Color speedColor = Color.cyan;
    public bool enableGlow = true;
    public float glowIntensity = 2f;
    
    [Header("Animation Settings")]
    public AnimationCurve flexionCurve = AnimationCurve.EaseInOut(0, 0, 1, 1);
    public AnimationCurve forceCurve = AnimationCurve.Linear(0, 0, 1, 1);
    public float smoothingTime = 0.1f;
    
    // Finger data storage
    private Dictionary<string, FingerJoints> fingerJointsMap;
    private Dictionary<string, FingerState> fingerStates;
    private Dictionary<string, FingerState> targetStates;
    
    // Animation coroutines
    private Dictionary<string, Coroutine> animationCoroutines;
    
    // Performance optimization
    private float lastUpdateTime = 0f;
    private float updateThreshold = 0.02f; // 50 Hz max
    
    void Start()
    {
        InitializeFingerMaps();
        InitializeFingerStates();
        
        // Subscribe to proportional control events
        var handController = GetComponent<ProportionalHandController>();
        if (handController != null)
        {
            Debug.Log("ProportionalHandModel integrated with ProportionalHandController");
        }
        else
        {
            Debug.LogWarning("ProportionalHandModel: No ProportionalHandController found on this GameObject");
        }
        
        // Initialize materials
        InitializeMaterials();
        
        Debug.Log($"ProportionalHandModel initialized: {handType} hand with {fingerJointsMap.Count} fingers");
    }
    
    void InitializeFingerMaps()
    {
        fingerJointsMap = new Dictionary<string, FingerJoints>()
        {
            ["thumb"] = thumbJoints,
            ["index"] = indexJoints,
            ["middle"] = middleJoints,
            ["ring"] = ringJoints,
            ["pinky"] = pinkyJoints
        };
        
        animationCoroutines = new Dictionary<string, Coroutine>();
    }
    
    void InitializeFingerStates()
    {
        fingerStates = new Dictionary<string, FingerState>();
        targetStates = new Dictionary<string, FingerState>();
        
        foreach (var finger in fingerJointsMap.Keys)
        {
            fingerStates[finger] = new FingerState();
            targetStates[finger] = new FingerState();
        }
    }
    
    void InitializeMaterials()
    {
        // Create material instances to avoid modifying shared materials
        for (int i = 0; i < fingerMaterials.Length; i++)
        {
            if (fingerMaterials[i] != null)
            {
                fingerMaterials[i] = Instantiate(fingerMaterials[i]);
            }
        }
    }
    
    void Update()
    {
        // Performance throttling
        if (Time.time - lastUpdateTime < updateThreshold)
            return;
        
        // Update finger animations
        UpdateFingerAnimations();
        
        // Update visual feedback
        UpdateVisualFeedback();
        
        lastUpdateTime = Time.time;
    }
    
    /// <summary>
    /// Set target control values for a specific finger
    /// </summary>
    public void SetFingerTarget(string fingerName, float flexion, float extension, float force)
    {
        string finger = fingerName.ToLower();
        
        if (targetStates.ContainsKey(finger))
        {
            var state = targetStates[finger];
            state.flexion = Mathf.Clamp01(flexion);
            state.extension = Mathf.Clamp01(extension);
            state.force = Mathf.Clamp01(force);
            state.speed = (flexion + extension) / 2f;
            state.isActive = (flexion + extension) > 0.05f;
            
            // Start smooth animation to target
            StartFingerAnimation(finger);
        }
    }
    
    /// <summary>
    /// Set target values for all fingers (whole-hand mode)
    /// </summary>
    public void SetAllFingersTarget(float flexion, float extension, float force)
    {
        foreach (var finger in fingerJointsMap.Keys)
        {
            SetFingerTarget(finger, flexion, extension, force);
        }
    }
    
    void StartFingerAnimation(string fingerName)
    {
        // Stop existing animation for this finger
        if (animationCoroutines.ContainsKey(fingerName) && animationCoroutines[fingerName] != null)
        {
            StopCoroutine(animationCoroutines[fingerName]);
        }
        
        // Start new animation
        animationCoroutines[fingerName] = StartCoroutine(AnimateFinger(fingerName));
    }
    
    IEnumerator AnimateFinger(string fingerName)
    {
        if (!fingerStates.ContainsKey(fingerName) || !targetStates.ContainsKey(fingerName))
            yield break;
        
        var currentState = fingerStates[fingerName];
        var targetState = targetStates[fingerName];
        
        float elapsedTime = 0f;
        var startState = new FingerState(currentState);
        
        while (elapsedTime < smoothingTime)
        {
            elapsedTime += Time.deltaTime;
            float t = elapsedTime / smoothingTime;
            
            // Apply animation curve
            float curvedT = flexionCurve.Evaluate(t);
            
            // Interpolate values
            currentState.flexion = Mathf.Lerp(startState.flexion, targetState.flexion, curvedT);
            currentState.extension = Mathf.Lerp(startState.extension, targetState.extension, curvedT);
            currentState.force = Mathf.Lerp(startState.force, targetState.force, forceCurve.Evaluate(t));
            currentState.speed = Mathf.Lerp(startState.speed, targetState.speed, curvedT);
            currentState.isActive = targetState.isActive;
            
            yield return null;
        }
        
        // Ensure final values are exactly the target
        currentState.CopyFrom(targetState);
    }
    
    void UpdateFingerAnimations()
    {
        foreach (var fingerEntry in fingerJointsMap)
        {
            string fingerName = fingerEntry.Key;
            FingerJoints joints = fingerEntry.Value;
            
            if (joints == null || !fingerStates.ContainsKey(fingerName))
                continue;
            
            var state = fingerStates[fingerName];
            
            // Calculate net flexion (-1 = full extension, 1 = full flexion)
            float netFlexion = state.flexion - state.extension;
            netFlexion = Mathf.Clamp(netFlexion, -1f, 1f);
            
            // Apply to joint rotations
            ApplyFingerRotation(joints, netFlexion, state.force);
        }
    }
    
    void ApplyFingerRotation(FingerJoints joints, float flexionAmount, float force)
    {
        if (joints.proximal != null)
        {
            float proximalAngle = flexionAmount * joints.proximalFlexionRange;
            joints.proximal.localRotation = Quaternion.Euler(proximalAngle, 0, 0);
        }
        
        if (joints.intermediate != null)
        {
            float intermediateAngle = flexionAmount * joints.intermediateFlexionRange * 0.8f;
            joints.intermediate.localRotation = Quaternion.Euler(intermediateAngle, 0, 0);
        }
        
        if (joints.distal != null)
        {
            float distalAngle = flexionAmount * joints.distalFlexionRange * 0.6f;
            joints.distal.localRotation = Quaternion.Euler(distalAngle, 0, 0);
        }
        
        // Apply force-based scaling (subtle effect)
        if (force > 0.5f)
        {
            float forceScale = 1f + (force - 0.5f) * 0.1f; // Max 5% scaling
            
            if (joints.proximal != null)
                joints.proximal.localScale = Vector3.one * forceScale;
            if (joints.intermediate != null)
                joints.intermediate.localScale = Vector3.one * forceScale;
            if (joints.distal != null)
                joints.distal.localScale = Vector3.one * forceScale;
        }
        else
        {
            // Reset scaling
            if (joints.proximal != null)
                joints.proximal.localScale = Vector3.one;
            if (joints.intermediate != null)
                joints.intermediate.localScale = Vector3.one;
            if (joints.distal != null)
                joints.distal.localScale = Vector3.one;
        }
    }
    
    void UpdateVisualFeedback()
    {
        int fingerIndex = 0;
        
        foreach (var fingerEntry in fingerStates)
        {
            string fingerName = fingerEntry.Key;
            var state = fingerEntry.Value;
            
            if (fingerIndex < fingerMaterials.Length && fingerMaterials[fingerIndex] != null)
            {
                Material mat = fingerMaterials[fingerIndex];
                
                // Calculate target color based on force and speed
                Color targetColor = normalColor;
                
                if (state.isActive)
                {
                    // Blend between normal and force color based on force level
                    targetColor = Color.Lerp(normalColor, forceColor, state.force);
                    
                    // Add speed tint
                    if (state.speed > 0.3f)
                    {
                        targetColor = Color.Lerp(targetColor, speedColor, state.speed * 0.3f);
                    }
                }
                
                // Apply color
                mat.color = targetColor;
                
                // Apply glow effect if enabled
                if (enableGlow && mat.HasProperty("_EmissionColor"))
                {
                    Color emissionColor = targetColor * (state.force * glowIntensity);
                    mat.SetColor("_EmissionColor", emissionColor);
                    
                    if (state.force > 0.1f)
                    {
                        mat.EnableKeyword("_EMISSION");
                    }
                    else
                    {
                        mat.DisableKeyword("_EMISSION");
                    }
                }
            }
            
            fingerIndex++;
        }
    }
    
    /// <summary>
    /// Reset all fingers to neutral position
    /// </summary>
    public void ResetHand()
    {
        foreach (var finger in fingerJointsMap.Keys)
        {
            SetFingerTarget(finger, 0f, 0f, 0f);
        }
    }
    
    /// <summary>
    /// Get current finger state
    /// </summary>
    public FingerState GetFingerState(string fingerName)
    {
        string finger = fingerName.ToLower();
        return fingerStates.ContainsKey(finger) ? fingerStates[finger] : new FingerState();
    }
    
    /// <summary>
    /// Set hand pose from predefined poses
    /// </summary>
    public void SetHandPose(HandPose pose)
    {
        switch (pose)
        {
            case HandPose.Open:
                SetAllFingersTarget(0f, 1f, 0f);
                break;
            case HandPose.Closed:
                SetAllFingersTarget(1f, 0f, 0.8f);
                break;
            case HandPose.Point:
                ResetHand();
                SetFingerTarget("index", 0f, 1f, 0.3f);
                break;
            case HandPose.Peace:
                ResetHand();
                SetFingerTarget("index", 0f, 1f, 0.3f);
                SetFingerTarget("middle", 0f, 1f, 0.3f);
                break;
            case HandPose.Thumbs_Up:
                ResetHand();
                SetFingerTarget("thumb", 0f, 1f, 0.5f);
                break;
        }
    }
    
    /// <summary>
    /// Enable/disable physics for the hand model
    /// </summary>
    public void SetPhysicsEnabled(bool enabled)
    {
        enablePhysics = enabled;
        
        // Toggle rigidbodies and colliders
        Rigidbody[] rigidbodies = GetComponentsInChildren<Rigidbody>();
        Collider[] colliders = GetComponentsInChildren<Collider>();
        
        foreach (var rb in rigidbodies)
        {
            rb.isKinematic = !enabled;
        }
        
        foreach (var col in colliders)
        {
            col.enabled = enabled;
        }
    }
    
    /// <summary>
    /// Validate joint references and log any issues
    /// </summary>
    [ContextMenu("Validate Joint References")]
    public void ValidateJointReferences()
    {
        Debug.Log("Validating finger joint references...");
        
        foreach (var fingerEntry in fingerJointsMap)
        {
            string fingerName = fingerEntry.Key;
            FingerJoints joints = fingerEntry.Value;
            
            if (joints == null)
            {
                Debug.LogError($"Missing joints reference for {fingerName}");
                continue;
            }
            
            int validJoints = 0;
            if (joints.proximal != null) validJoints++;
            if (joints.intermediate != null) validJoints++;
            if (joints.distal != null) validJoints++;
            
            Debug.Log($"{fingerName}: {validJoints}/3 joints assigned");
            
            if (validJoints == 0)
            {
                Debug.LogWarning($"No joints assigned for {fingerName} finger");
            }
        }
    }
    
    void OnDestroy()
    {
        // Stop all animations
        foreach (var coroutine in animationCoroutines.Values)
        {
            if (coroutine != null)
            {
                StopCoroutine(coroutine);
            }
        }
    }
}

/// <summary>
/// Finger joint references for a single finger
/// </summary>
[System.Serializable]
public class FingerJoints
{
    [Header("Joint References")]
    public Transform proximal;    // Base joint (knuckle)
    public Transform intermediate; // Middle joint
    public Transform distal;      // End joint (fingertip)
    
    [Header("Flexion Ranges (degrees)")]
    public float proximalFlexionRange = 90f;
    public float intermediateFlexionRange = 90f;
    public float distalFlexionRange = 45f;
    
    [Header("Extension Ranges (degrees)")]
    public float proximalExtensionRange = 30f;
    public float intermediateExtensionRange = 0f;
    public float distalExtensionRange = 15f;
    
    /// <summary>
    /// Check if all joints are assigned
    /// </summary>
    public bool IsComplete()
    {
        return proximal != null && intermediate != null && distal != null;
    }
    
    /// <summary>
    /// Get number of assigned joints
    /// </summary>
    public int GetJointCount()
    {
        int count = 0;
        if (proximal != null) count++;
        if (intermediate != null) count++;
        if (distal != null) count++;
        return count;
    }
}

/// <summary>
/// Current state of a finger
/// </summary>
[System.Serializable]
public class FingerState
{
    public float flexion = 0f;
    public float extension = 0f;
    public float force = 0f;
    public float speed = 0f;
    public bool isActive = false;
    
    public FingerState() { }
    
    public FingerState(FingerState other)
    {
        CopyFrom(other);
    }
    
    public void CopyFrom(FingerState other)
    {
        flexion = other.flexion;
        extension = other.extension;
        force = other.force;
        speed = other.speed;
        isActive = other.isActive;
    }
}

/// <summary>
/// Hand type enumeration
/// </summary>
public enum HandType
{
    Left,
    Right
}

/// <summary>
/// Predefined hand poses
/// </summary>
public enum HandPose
{
    Neutral,
    Open,
    Closed,
    Point,
    Peace,
    Thumbs_Up,
    Hook,
    Lateral_Grasp
}