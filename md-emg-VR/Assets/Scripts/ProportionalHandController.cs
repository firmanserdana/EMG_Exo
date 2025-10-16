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
    
    // Current finger states (per finger)
    private float[] currentFlexion = new float[5];
    private float[] currentExtension = new float[5];
    private float[] currentForce = new float[5];
    private float[] targetFlexion = new float[5];
    private float[] targetExtension = new float[5];
    private float[] targetForce = new float[5];
    
    // Joint references per finger
    private List<Transform[]> fingerJoints = new List<Transform[]>();
    private List<Quaternion[]> initialRotations = new List<Quaternion[]>();
    private List<Quaternion[]> flexedRotations = new List<Quaternion[]>();
    
    // Finger names for mapping
    private string[] fingerNames = { "Thumb", "Index", "Middle", "Ring", "Pinky" };
    
    void Start()
    {
        InitializeFingerJoints();
        InitializeRotations();
        
        Debug.Log("ProportionalHandController initialized with " + fingers.Length + " fingers");
    }
    
    void InitializeFingerJoints()
    {
        // Store joints for each finger
        foreach (Transform finger in fingers)
        {
            Transform[] joints = finger.GetComponentsInChildren<Transform>();
            fingerJoints.Add(joints);
        }
    }
    
    void InitializeRotations()
    {
        // Store initial (extended) and flexed rotations
        for (int i = 0; i < fingers.Length; i++)
        {
            Transform[] joints = fingerJoints[i];
            
            // Initial rotations (extended state)
            Quaternion[] initRots = new Quaternion[joints.Length];
            for (int j = 0; j < joints.Length; j++)
            {
                initRots[j] = joints[j].localRotation;
            }
            initialRotations.Add(initRots);
            
            // Calculate flexed rotations (simplified - uniform flexion)
            Quaternion[] flexRots = new Quaternion[joints.Length];
            for (int j = 0; j < joints.Length; j++)
            {
                // Apply flexion rotation around local X axis
                float flexAngle = maxFlexionAngle / joints.Length; // Distribute across joints
                flexRots[j] = initRots[j] * Quaternion.Euler(flexAngle, 0, 0);
            }
            flexedRotations.Add(flexRots);
        }
    }
    
    void Update()
    {
        // Smooth interpolation towards target values
        for (int i = 0; i < 5; i++)
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
        int fingerIndex = Array.IndexOf(fingerNames, fingerName);
        if (fingerIndex >= 0 && fingerIndex < 5)
        {
            targetFlexion[fingerIndex] = Mathf.Clamp01(flexion) * speedMultiplier;
            targetExtension[fingerIndex] = Mathf.Clamp01(extension) * speedMultiplier;
            targetForce[fingerIndex] = Mathf.Clamp01(force) * forceMultiplier;
        }
    }
    
    /// <summary>
    /// Set proportional control for all fingers
    /// </summary>
    public void SetAllFingersControl(float flexion, float extension, float force)
    {
        for (int i = 0; i < 5; i++)
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
        for (int fingerIdx = 0; fingerIdx < Mathf.Min(fingers.Length, 5); fingerIdx++)
        {
            // Calculate net flexion (flexion - extension)
            float netFlexion = currentFlexion[fingerIdx] - currentExtension[fingerIdx];
            netFlexion = Mathf.Clamp(netFlexion, -1.0f, 1.0f);
            
            // Convert to 0-1 range where 0=extended, 1=flexed
            float flexionAmount = (netFlexion + 1.0f) / 2.0f;
            
            // Interpolate between extended and flexed rotations
            Transform[] joints = fingerJoints[fingerIdx];
            for (int jointIdx = 0; jointIdx < joints.Length; jointIdx++)
            {
                Quaternion extRot = initialRotations[fingerIdx][jointIdx];
                Quaternion flexRot = flexedRotations[fingerIdx][jointIdx];
                
                joints[jointIdx].localRotation = Quaternion.Slerp(extRot, flexRot, flexionAmount);
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
        
        for (int i = 0; i < Mathf.Min(fingerMaterials.Length, 5); i++)
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
        for (int i = 0; i < 5; i++)
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
        if (fingerIndex >= 0 && fingerIndex < 5)
        {
            flexion = currentFlexion[fingerIndex];
            extension = currentExtension[fingerIndex];
            force = currentForce[fingerIndex];
        }
        else
        {
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
                Dictionary<string, object> fingers = eventData["fingers"] as Dictionary<string, object>;
                
                foreach (var finger in fingers)
                {
                    string fingerName = finger.Key;
                    Dictionary<string, object> control = finger.Value as Dictionary<string, object>;
                    
                    if (control != null)
                    {
                        float flexion = control.ContainsKey("flexion_speed") ? 
                            Convert.ToSingle(control["flexion_speed"]) : 0f;
                        float extension = control.ContainsKey("extension_speed") ? 
                            Convert.ToSingle(control["extension_speed"]) : 0f;
                        float force = control.ContainsKey("force") ? 
                            Convert.ToSingle(control["force"]) : 0f;
                        
                        SetFingerControl(fingerName, flexion, extension, force);
                    }
                }
            }
        }
        catch (Exception e)
        {
            Debug.LogError("Error handling proportional control event: " + e.Message);
        }
    }
}
