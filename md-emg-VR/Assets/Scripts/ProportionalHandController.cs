using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Proportional Hand Controller for continuous EMG control
/// Supports speed and force-based finger control
/// </summary>
public class ProportionalHandController : MonoBehaviour
{
    // Array of fingers (Thumb, Index, Middle, Ring, Pinky)
    public Transform[] fingers;
    
    // Visual feedback for force
    public Material[] fingerMaterials;
    public Color normalColor = Color.white;
    public Color forceColor = Color.red;
    
    // Proportional control parameters
    [Header("Proportional Control Settings")]
    public float speedMultiplier = 1.0f;
    public float forceMultiplier = 1.0f;
    public float smoothingFactor = 0.2f; // Exponential smoothing
    
    // Finger angles configuration
    [Header("Finger Angle Ranges")]
    public float maxFlexionAngle = 90.0f;
    public float maxExtensionAngle = 0.0f;
    
    // Current finger states (per finger) - properly initialized in Start()
    private float[] currentFlexion;
    private float[] currentExtension;
    private float[] currentForce;
    private float[] targetFlexion;
    private float[] targetExtension;
    private float[] targetForce;
    
    // Joint references per finger
    private List<Transform[]> fingerJoints = new List<Transform[]>();
    private List<Quaternion[]> initialRotations = new List<Quaternion[]>();
    private List<Quaternion[]> flexedRotations = new List<Quaternion[]>();
    
    // Finger names for mapping
    private string[] fingerNames = { "thumb", "index", "middle", "ring", "pinky" };
    
    // Number of active fingers (determined at runtime)
    private int numFingers;
    
    void Start()
    {
        // Validate fingers array
        if (fingers == null || fingers.Length == 0)
        {
            Debug.LogError("ProportionalHandController: No fingers assigned! Please assign finger transforms in the inspector.");
            enabled = false;
            return;
        }
        
        numFingers = fingers.Length;
        
        // Initialize arrays with proper size
        currentFlexion = new float[numFingers];
        currentExtension = new float[numFingers];
        currentForce = new float[numFingers];
        targetFlexion = new float[numFingers];
        targetExtension = new float[numFingers];
        targetForce = new float[numFingers];
        
        InitializeFingerJoints();
        InitializeRotations();
        
        Debug.Log($"ProportionalHandController initialized with {numFingers} fingers");
    }
    
    void InitializeFingerJoints()
    {
        // Store joints for each finger
        foreach (Transform finger in fingers)
        {
            if (finger != null)
            {
                Transform[] joints = finger.GetComponentsInChildren<Transform>();
                fingerJoints.Add(joints);
            }
            else
            {
                Debug.LogWarning("ProportionalHandController: Null finger transform found!");
                fingerJoints.Add(new Transform[0]);
            }
        }
    }
    
    void InitializeRotations()
    {
        // Store initial (extended) and flexed rotations
        for (int i = 0; i < numFingers; i++)
        {
            if (i >= fingerJoints.Count || fingerJoints[i] == null)
            {
                initialRotations.Add(new Quaternion[0]);
                flexedRotations.Add(new Quaternion[0]);
                continue;
            }
            
            Transform[] joints = fingerJoints[i];
            
            // Initial rotations (extended state)
            Quaternion[] initRots = new Quaternion[joints.Length];
            for (int j = 0; j < joints.Length; j++)
            {
                if (joints[j] != null)
                {
                    initRots[j] = joints[j].localRotation;
                }
            }
            initialRotations.Add(initRots);
            
            // Calculate flexed rotations (simplified - uniform flexion)
            Quaternion[] flexRots = new Quaternion[joints.Length];
            for (int j = 0; j < joints.Length; j++)
            {
                if (joints[j] != null)
                {
                    // Apply flexion rotation around local X axis
                    float flexAngle = maxFlexionAngle / joints.Length; // Distribute across joints
                    flexRots[j] = initRots[j] * Quaternion.Euler(flexAngle, 0, 0);
                }
                else
                {
                    flexRots[j] = initRots[j];
                }
            }
            flexedRotations.Add(flexRots);
        }
    }
    
    void Update()
    {
        // Smooth interpolation towards target values
        for (int i = 0; i < numFingers; i++)
        {
            currentFlexion[i] = Mathf.Lerp(currentFlexion[i], targetFlexion[i], smoothingFactor);
            currentExtension[i] = Mathf.Lerp(currentExtension[i], targetExtension[i], smoothingFactor);
            currentForce[i] = Mathf.Lerp(currentForce[i], targetForce[i], smoothingFactor);
        }
        
        // Apply finger rotations
        UpdateFingerRotations();
        
        // Update visual feedback
        UpdateVisualFeedback();
    }
    
    /// <summary>
    /// Set proportional control values for a specific finger
    /// </summary>
    public void SetFingerControl(string fingerName, float flexion, float extension, float force)
    {
        int fingerIndex = Array.IndexOf(fingerNames, fingerName.ToLower());
        if (fingerIndex >= 0 && fingerIndex < numFingers)
        {
            targetFlexion[fingerIndex] = Mathf.Clamp01(flexion) * speedMultiplier;
            targetExtension[fingerIndex] = Mathf.Clamp01(extension) * speedMultiplier;
            targetForce[fingerIndex] = Mathf.Clamp01(force) * forceMultiplier;
        }
        else
        {
            Debug.LogWarning($"ProportionalHandController: Unknown or invalid finger '{fingerName}' (index: {fingerIndex})");
        }
    }
    
    /// <summary>
    /// Set proportional control for all fingers
    /// </summary>
    public void SetAllFingersControl(float flexion, float extension, float force)
    {
        for (int i = 0; i < numFingers; i++)
        {
            targetFlexion[i] = Mathf.Clamp01(flexion) * speedMultiplier;
            targetExtension[i] = Mathf.Clamp01(extension) * speedMultiplier;
            targetForce[i] = Mathf.Clamp01(force) * forceMultiplier;
        }
    }
    
    /// <summary>
    /// Update finger rotations based on current control values
    /// </summary>
    private void UpdateFingerRotations()
    {
        for (int fingerIdx = 0; fingerIdx < Mathf.Min(fingers.Length, numFingers); fingerIdx++)
        {
            // Calculate net flexion (flexion - extension)
            float netFlexion = currentFlexion[fingerIdx] - currentExtension[fingerIdx];
            netFlexion = Mathf.Clamp(netFlexion, -1.0f, 1.0f);
            
            // Convert to 0-1 range where 0=extended, 1=flexed
            float flexionAmount = (netFlexion + 1.0f) / 2.0f;
            
            // Interpolate between extended and flexed rotations
            if (fingerIdx < fingerJoints.Count && fingerJoints[fingerIdx] != null)
            {
                Transform[] joints = fingerJoints[fingerIdx];
                for (int jointIdx = 0; jointIdx < joints.Length; jointIdx++)
                {
                    if (joints[jointIdx] != null &&
                        fingerIdx < initialRotations.Count && fingerIdx < flexedRotations.Count &&
                        jointIdx < initialRotations[fingerIdx].Length && jointIdx < flexedRotations[fingerIdx].Length)
                    {
                        Quaternion extRot = initialRotations[fingerIdx][jointIdx];
                        Quaternion flexRot = flexedRotations[fingerIdx][jointIdx];
                        
                        joints[jointIdx].localRotation = Quaternion.Slerp(extRot, flexRot, flexionAmount);
                    }
                }
            }
        }
    }
    
    /// <summary>
    /// Update visual feedback based on force levels
    /// </summary>
    private void UpdateVisualFeedback()
    {
        if (fingerMaterials == null || fingerMaterials.Length == 0)
            return;
        
        for (int i = 0; i < Mathf.Min(fingerMaterials.Length, numFingers); i++)
        {
            if (fingerMaterials[i] != null)
            {
                // Interpolate color based on force
                Color targetColor = Color.Lerp(normalColor, forceColor, currentForce[i]);
                fingerMaterials[i].color = targetColor;
            }
        }
    }
    
    /// <summary>
    /// Reset all fingers to neutral position
    /// </summary>
    public void ResetFingers()
    {
        for (int i = 0; i < numFingers; i++)
        {
            targetFlexion[i] = 0.0f;
            targetExtension[i] = 0.0f;
            targetForce[i] = 0.0f;
            currentFlexion[i] = 0.0f;
            currentExtension[i] = 0.0f;
            currentForce[i] = 0.0f;
        }
    }
    
    /// <summary>
    /// Get current state of a finger
    /// </summary>
    public void GetFingerState(int fingerIndex, out float flexion, out float extension, out float force)
    {
        if (fingerIndex >= 0 && fingerIndex < numFingers)
        {
            flexion = currentFlexion[fingerIndex];
            extension = currentExtension[fingerIndex];
            force = currentForce[fingerIndex];
        }
        else
        {
            Debug.LogWarning($"ProportionalHandController: Invalid finger index {fingerIndex} (valid range: 0-{numFingers-1})");
            flexion = extension = force = 0.0f;
        }
    }
    
    /// <summary>
    /// Handle proportional control event from Python backend
    /// </summary>
    public void HandleProportionalControlEvent(Dictionary<string, object> eventData)
    {
        try
        {
            if (eventData.ContainsKey("fingers"))
            {
                // Avoid shadowing the fingers field by using a different variable name
                var fingersDict = eventData["fingers"] as Dictionary<string, object>;
                
                if (fingersDict == null)
                {
                    Debug.LogWarning("ProportionalHandController: Invalid fingers data format");
                    return;
                }
                
                foreach (var fingerEntry in fingersDict)
                {
                    string fingerName = fingerEntry.Key;
                    var control = fingerEntry.Value as Dictionary<string, object>;
                    
                    if (control != null)
                    {
                        // Safe type conversion with fallback values
                        float flexion = 0f;
                        float extension = 0f;
                        float force = 0f;
                        
                        if (control.ContainsKey("flexion_speed"))
                        {
                            if (float.TryParse(control["flexion_speed"].ToString(), out float f))
                                flexion = f;
                        }
                        
                        if (control.ContainsKey("extension_speed"))
                        {
                            if (float.TryParse(control["extension_speed"].ToString(), out float e))
                                extension = e;
                        }
                        
                        if (control.ContainsKey("force"))
                        {
                            if (float.TryParse(control["force"].ToString(), out float fr))
                                force = fr;
                        }
                        
                        SetFingerControl(fingerName, flexion, extension, force);
                    }
                    else
                    {
                        Debug.LogWarning($"ProportionalHandController: Invalid control data for finger '{fingerName}'");
                    }
                }
            }
            else
            {
                Debug.LogWarning("ProportionalHandController: Event data missing 'fingers' key");
            }
        }
        catch (Exception e)
        {
            Debug.LogError($"ProportionalHandController: Error handling proportional control event: {e.Message}");
        }
    }
}