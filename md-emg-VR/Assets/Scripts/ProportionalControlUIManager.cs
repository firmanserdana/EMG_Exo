using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

/// <summary>
/// UI Manager for Proportional Control System
/// Provides real-time visual feedback for finger control values
/// </summary>
public class ProportionalControlUIManager : MonoBehaviour
{
    [Header("UI Panels")]
    public GameObject fingerControlPanel;
    public GameObject systemStatusPanel;
    public GameObject performancePanel;
    public GameObject controlModePanel;
    
    [Header("Finger Control UI Elements")]
    public Transform fingerUIContainer;
    public GameObject fingerUIPrefab;
    
    [Header("System Status Elements")]
    public TextMeshProUGUI connectionStatusText;
    public TextMeshProUGUI decoderTypeText;
    public TextMeshProUGUI controlModeText;
    public TextMeshProUGUI mudStatusText;
    public Image connectionStatusIndicator;
    
    [Header("Performance Metrics")]
    public TextMeshProUGUI updateRateText;
    public TextMeshProUGUI latencyText;
    public TextMeshProUGUI activeChannelsText;
    public Slider performanceSlider;
    
    [Header("Control Mode UI")]
    public Button individualModeButton;
    public Button wholeModeButton;
    public Toggle mudToggle;
    
    [Header("Color Themes")]
    public Color connectedColor = Color.green;
    public Color disconnectedColor = Color.red;
    public Color lowForceColor = Color.white;
    public Color highForceColor = Color.red;
    public Color speedColor = Color.cyan;
    
    // Finger UI instances
    private Dictionary<string, FingerUIController> fingerUIControllers = new Dictionary<string, FingerUIController>();
    
    // System state
    private bool isConnected = false;
    private string currentDecoderType = "MLP";
    private string currentControlMode = "Individual Fingers";
    private bool isMudEnabled = false;
    
    // Performance tracking
    private Queue<float> updateTimes = new Queue<float>();
    private float lastUpdateTime = 0f;
    private int maxUpdateSamples = 50;
    
    // Finger names
    private string[] fingerNames = { "Thumb", "Index", "Middle", "Ring", "Pinky" };
    
    void Start()
    {
        InitializeUI();
        SetupEventHandlers();
        
        // Subscribe to proportional control events
        var tcpManager = FindObjectOfType<TcpServerManager>();
        if (tcpManager != null)
        {
            // Register for proportional control events
            tcpManager.OnMessageReceived += HandleProportionalControlMessage;
        }
        
        Debug.Log("ProportionalControlUIManager initialized");
    }
    
    void InitializeUI()
    {
        // Create finger UI elements
        CreateFingerUIElements();
        
        // Initialize system status
        UpdateConnectionStatus(false);
        UpdateSystemInfo("MLP", "Individual Fingers", false);
        
        // Initialize performance display
        if (updateRateText) updateRateText.text = "0.0 Hz";
        if (latencyText) latencyText.text = "0 ms";
        if (activeChannelsText) activeChannelsText.text = "0/64";
        
        Debug.Log("UI initialized with finger panels");
    }
    
    void CreateFingerUIElements()
    {
        if (fingerUIContainer == null || fingerUIPrefab == null)
        {
            Debug.LogError("ProportionalControlUIManager: Missing UI references");
            return;
        }
        
        // Create UI for each finger
        foreach (string fingerName in fingerNames)
        {
            GameObject fingerUI = Instantiate(fingerUIPrefab, fingerUIContainer);
            fingerUI.name = $"Finger_{fingerName}_UI";
            
            FingerUIController controller = fingerUI.GetComponent<FingerUIController>();
            if (controller == null)
            {
                controller = fingerUI.AddComponent<FingerUIController>();
            }
            
            controller.Initialize(fingerName);
            fingerUIControllers[fingerName.ToLower()] = controller;
        }
    }
    
    void SetupEventHandlers()
    {
        // Setup button handlers
        if (individualModeButton)
        {
            individualModeButton.onClick.AddListener(() => {
                SetControlMode("individual_fingers");
            });
        }
        
        if (wholeModeButton)
        {
            wholeModeButton.onClick.AddListener(() => {
                SetControlMode("whole_hand");
            });
        }
        
        if (mudToggle)
        {
            mudToggle.onValueChanged.AddListener((value) => {
                ToggleMUD(value);
            });
        }
    }
    
    /// <summary>
    /// Handle proportional control messages from Python backend
    /// </summary>
    public void HandleProportionalControlMessage(string message)
    {
        try
        {
            var data = JsonUtility.FromJson<ProportionalControlData>(message);
            
            if (data.event_type == "proportional_control")
            {
                UpdateFingerUI(data);
                UpdatePerformanceMetrics();
                
                if (!isConnected)
                {
                    UpdateConnectionStatus(true);
                }
            }
            else if (data.event_type == "system_status")
            {
                UpdateSystemStatus(data);
            }
        }
        catch (System.Exception e)
        {
            Debug.LogWarning($"Error parsing proportional control message: {e.Message}");
        }
    }
    
    void UpdateFingerUI(ProportionalControlData data)
    {
        if (data.fingers == null) return;
        
        foreach (var fingerEntry in data.fingers)
        {
            string fingerName = fingerEntry.Key.ToLower();
            
            if (fingerUIControllers.ContainsKey(fingerName))
            {
                var controller = fingerUIControllers[fingerName];
                var fingerData = fingerEntry.Value;
                
                controller.UpdateValues(
                    fingerData.flexion_speed,
                    fingerData.extension_speed,
                    fingerData.force
                );
            }
        }
    }
    
    void UpdateSystemStatus(ProportionalControlData data)
    {
        // Update system information if provided
        if (!string.IsNullOrEmpty(data.decoder_type))
        {
            currentDecoderType = data.decoder_type.ToUpper();
        }
        
        if (!string.IsNullOrEmpty(data.control_mode))
        {
            currentControlMode = data.control_mode == "individual_fingers" ? 
                "Individual Fingers" : "Whole Hand";
        }
        
        UpdateSystemInfo(currentDecoderType, currentControlMode, data.mud_enabled);
    }
    
    void UpdateConnectionStatus(bool connected)
    {
        isConnected = connected;
        
        if (connectionStatusText)
        {
            connectionStatusText.text = connected ? "CONNECTED" : "DISCONNECTED";
            connectionStatusText.color = connected ? connectedColor : disconnectedColor;
        }
        
        if (connectionStatusIndicator)
        {
            connectionStatusIndicator.color = connected ? connectedColor : disconnectedColor;
        }
    }
    
    void UpdateSystemInfo(string decoderType, string controlMode, bool mudEnabled)
    {
        if (decoderTypeText) decoderTypeText.text = $"Decoder: {decoderType}";
        if (controlModeText) controlModeText.text = $"Mode: {controlMode}";
        if (mudStatusText) 
        {
            mudStatusText.text = $"MUD: {(mudEnabled ? "ON" : "OFF")}";
            mudStatusText.color = mudEnabled ? connectedColor : Color.gray;
        }
    }
    
    void UpdatePerformanceMetrics()
    {
        float currentTime = Time.time;
        
        // Track update rate
        if (lastUpdateTime > 0)
        {
            float deltaTime = currentTime - lastUpdateTime;
            updateTimes.Enqueue(1f / deltaTime);
            
            if (updateTimes.Count > maxUpdateSamples)
            {
                updateTimes.Dequeue();
            }
            
            // Calculate average update rate
            float totalRate = 0f;
            foreach (float rate in updateTimes)
            {
                totalRate += rate;
            }
            float avgRate = totalRate / updateTimes.Count;
            
            if (updateRateText) updateRateText.text = $"{avgRate:F1} Hz";
            
            // Update performance slider (target 20-50 Hz)
            if (performanceSlider)
            {
                float normalizedPerf = Mathf.Clamp01((avgRate - 10f) / 40f); // 10-50 Hz range
                performanceSlider.value = normalizedPerf;
            }
        }
        
        lastUpdateTime = currentTime;
    }
    
    /// <summary>
    /// Set control mode (called from UI buttons)
    /// </summary>
    public void SetControlMode(string mode)
    {
        // Send mode change event to Python backend
        var tcpManager = FindObjectOfType<TcpServerManager>();
        if (tcpManager != null)
        {
            var modeChangeEvent = new Dictionary<string, object>
            {
                ["event_type"] = "control_mode_change",
                ["control_mode"] = mode,
                ["timestamp"] = System.DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()
            };
            
            string jsonMessage = JsonUtility.ToJson(modeChangeEvent);
            tcpManager.SendMessage(jsonMessage);
            
            Debug.Log($"Sent control mode change: {mode}");
        }
        
        // Update UI
        currentControlMode = mode == "individual_fingers" ? "Individual Fingers" : "Whole Hand";
        UpdateSystemInfo(currentDecoderType, currentControlMode, isMudEnabled);
    }
    
    /// <summary>
    /// Toggle Motor Unit Decomposition
    /// </summary>
    public void ToggleMUD(bool enabled)
    {
        isMudEnabled = enabled;
        
        // Send MUD toggle event to Python backend
        var tcpManager = FindObjectOfType<TcpServerManager>();
        if (tcpManager != null)
        {
            var mudToggleEvent = new Dictionary<string, object>
            {
                ["event_type"] = "mud_toggle",
                ["mud_enabled"] = enabled,
                ["timestamp"] = System.DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()
            };
            
            string jsonMessage = JsonUtility.ToJson(mudToggleEvent);
            tcpManager.SendMessage(jsonMessage);
            
            Debug.Log($"Toggled MUD: {enabled}");
        }
        
        // Update UI
        UpdateSystemInfo(currentDecoderType, currentControlMode, enabled);
    }
    
    /// <summary>
    /// Reset all finger displays to neutral
    /// </summary>
    public void ResetFingerDisplays()
    {
        foreach (var controller in fingerUIControllers.Values)
        {
            controller.ResetValues();
        }
    }
    
    /// <summary>
    /// Toggle UI panel visibility
    /// </summary>
    public void TogglePanel(GameObject panel)
    {
        if (panel != null)
        {
            panel.SetActive(!panel.activeInHierarchy);
        }
    }
    
    void OnDestroy()
    {
        // Cleanup event handlers
        var tcpManager = FindObjectOfType<TcpServerManager>();
        if (tcpManager != null)
        {
            tcpManager.OnMessageReceived -= HandleProportionalControlMessage;
        }
    }
}

/// <summary>
/// Individual Finger UI Controller
/// Manages display for a single finger's control values
/// </summary>
public class FingerUIController : MonoBehaviour
{
    [Header("UI Elements")]
    public TextMeshProUGUI fingerNameText;
    public Slider flexionSlider;
    public Slider extensionSlider;
    public Slider forceSlider;
    public Image fingerIcon;
    public Image forceColorIndicator;
    
    [Header("Value Text Displays")]
    public TextMeshProUGUI flexionValueText;
    public TextMeshProUGUI extensionValueText;
    public TextMeshProUGUI forceValueText;
    public TextMeshProUGUI speedValueText;
    
    [Header("Color Settings")]
    public Color inactiveColor = Color.gray;
    public Color activeFlexColor = Color.green;
    public Color activeExtColor = Color.blue;
    public Color forceGradientStart = Color.white;
    public Color forceGradientEnd = Color.red;
    
    private string fingerName;
    private float currentFlexion = 0f;
    private float currentExtension = 0f;
    private float currentForce = 0f;
    
    /// <summary>
    /// Initialize the finger UI with the given finger name
    /// </summary>
    public void Initialize(string name)
    {
        fingerName = name;
        
        if (fingerNameText)
            fingerNameText.text = name;
        
        // Setup sliders
        if (flexionSlider) 
        {
            flexionSlider.minValue = 0f;
            flexionSlider.maxValue = 1f;
            flexionSlider.value = 0f;
        }
        
        if (extensionSlider) 
        {
            extensionSlider.minValue = 0f;
            extensionSlider.maxValue = 1f;
            extensionSlider.value = 0f;
        }
        
        if (forceSlider) 
        {
            forceSlider.minValue = 0f;
            forceSlider.maxValue = 1f;
            forceSlider.value = 0f;
        }
        
        ResetValues();
        
        Debug.Log($"FingerUIController initialized for {name}");
    }
    
    /// <summary>
    /// Update finger control values and UI
    /// </summary>
    public void UpdateValues(float flexion, float extension, float force)
    {
        currentFlexion = Mathf.Clamp01(flexion);
        currentExtension = Mathf.Clamp01(extension);
        currentForce = Mathf.Clamp01(force);
        
        // Update sliders
        if (flexionSlider) flexionSlider.value = currentFlexion;
        if (extensionSlider) extensionSlider.value = currentExtension;
        if (forceSlider) forceSlider.value = currentForce;
        
        // Update value text displays
        if (flexionValueText) flexionValueText.text = $"{currentFlexion:F2}";
        if (extensionValueText) extensionValueText.text = $"{currentExtension:F2}";
        if (forceValueText) forceValueText.text = $"{currentForce:F2}";
        
        // Calculate and display speed
        float speed = (currentFlexion + currentExtension) / 2f;
        if (speedValueText) speedValueText.text = $"{speed:F2}";
        
        // Update visual feedback
        UpdateVisualFeedback();
    }
    
    void UpdateVisualFeedback()
    {
        // Color finger icon based on activity
        if (fingerIcon)
        {
            Color iconColor = inactiveColor;
            
            if (currentFlexion > 0.1f)
                iconColor = Color.Lerp(iconColor, activeFlexColor, currentFlexion);
            
            if (currentExtension > 0.1f)
                iconColor = Color.Lerp(iconColor, activeExtColor, currentExtension);
            
            fingerIcon.color = iconColor;
        }
        
        // Update force color indicator
        if (forceColorIndicator)
        {
            Color forceColor = Color.Lerp(forceGradientStart, forceGradientEnd, currentForce);
            forceColorIndicator.color = forceColor;
        }
        
        // Update slider colors
        UpdateSliderColors();
    }
    
    void UpdateSliderColors()
    {
        // Update flexion slider color
        if (flexionSlider && flexionSlider.fillRect)
        {
            Image fillImage = flexionSlider.fillRect.GetComponent<Image>();
            if (fillImage)
            {
                fillImage.color = Color.Lerp(Color.white, activeFlexColor, currentFlexion);
            }
        }
        
        // Update extension slider color
        if (extensionSlider && extensionSlider.fillRect)
        {
            Image fillImage = extensionSlider.fillRect.GetComponent<Image>();
            if (fillImage)
            {
                fillImage.color = Color.Lerp(Color.white, activeExtColor, currentExtension);
            }
        }
        
        // Update force slider color
        if (forceSlider && forceSlider.fillRect)
        {
            Image fillImage = forceSlider.fillRect.GetComponent<Image>();
            if (fillImage)
            {
                fillImage.color = Color.Lerp(forceGradientStart, forceGradientEnd, currentForce);
            }
        }
    }
    
    /// <summary>
    /// Reset finger values to neutral
    /// </summary>
    public void ResetValues()
    {
        UpdateValues(0f, 0f, 0f);
    }
    
    /// <summary>
    /// Get current finger state
    /// </summary>
    public (float flexion, float extension, float force) GetCurrentValues()
    {
        return (currentFlexion, currentExtension, currentForce);
    }
}

/// <summary>
/// Data structures for JSON parsing
/// </summary>
[System.Serializable]
public class ProportionalControlData
{
    public string event_type;
    public long timestamp;
    public Dictionary<string, FingerControlData> fingers;
    public string decoder_type;
    public string control_mode;
    public bool mud_enabled;
    public float update_rate;
    public float latency;
    public int active_channels;
}

[System.Serializable]
public class FingerControlData
{
    public float flexion_speed;
    public float extension_speed;
    public float force;
    public float net_activation;
    public bool is_active;
}