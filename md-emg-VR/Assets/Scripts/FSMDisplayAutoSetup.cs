using UnityEngine;
using UnityEngine.UI;
using TMPro;

/// <summary>
/// Auto-generates the FSM Display UI at runtime.
/// Attach this to any GameObject in the scene - it will create all necessary UI elements.
/// </summary>
public class FSMDisplayAutoSetup : MonoBehaviour
{
    [Header("Auto Setup Settings")]
    [SerializeField] private bool autoSetupOnStart = true;
    [SerializeField] private bool createIfMissing = true;

    [Header("Generated References (Auto-filled)")]
    public FSMDisplayManager fsmDisplayManager;
    public Canvas mainCanvas;

    private void Start()
    {
        if (autoSetupOnStart)
        {
            SetupFSMDisplay();
        }
    }

    [ContextMenu("Setup FSM Display UI")]
    public void SetupFSMDisplay()
    {
        // Find or create canvas
        mainCanvas = FindObjectOfType<Canvas>();
        if (mainCanvas == null && createIfMissing)
        {
            GameObject canvasObj = new GameObject("FSMCanvas");
            mainCanvas = canvasObj.AddComponent<Canvas>();
            mainCanvas.renderMode = RenderMode.ScreenSpaceOverlay;
            mainCanvas.sortingOrder = 100; // On top of other UI
            canvasObj.AddComponent<CanvasScaler>().uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            canvasObj.AddComponent<GraphicRaycaster>();
        }

        if (mainCanvas == null)
        {
            Debug.LogError("FSMDisplayAutoSetup: No Canvas found in scene!");
            return;
        }

        // Find or create FSMDisplayManager
        fsmDisplayManager = FindObjectOfType<FSMDisplayManager>();
        if (fsmDisplayManager == null && createIfMissing)
        {
            GameObject managerObj = new GameObject("FSMDisplayManager");
            fsmDisplayManager = managerObj.AddComponent<FSMDisplayManager>();
        }

        if (fsmDisplayManager == null)
        {
            Debug.LogError("FSMDisplayAutoSetup: Could not create FSMDisplayManager!");
            return;
        }

        // Create FSM Display Panel
        GameObject fsmPanel = CreateFSMDisplayPanel();

        // Create BBT Scoring Panel
        GameObject bbtPanel = CreateBBTScoringPanel();

        // Wire up references using reflection (since fields are serialized)
        var fsmType = typeof(FSMDisplayManager);

        SetPrivateField(fsmDisplayManager, "fsmDisplayPanel", fsmPanel);
        SetPrivateField(fsmDisplayManager, "stateText", fsmPanel.transform.Find("StateText")?.GetComponent<TextMeshProUGUI>());
        SetPrivateField(fsmDisplayManager, "stateIndicator", fsmPanel.transform.Find("StateIndicator")?.GetComponent<Image>());
        SetPrivateField(fsmDisplayManager, "lockIndicator", fsmPanel.transform.Find("LockIndicator")?.GetComponent<Image>());
        SetPrivateField(fsmDisplayManager, "lockTimerText", fsmPanel.transform.Find("LockTimerText")?.GetComponent<TextMeshProUGUI>());

        SetPrivateField(fsmDisplayManager, "bbtScoringPanel", bbtPanel);
        SetPrivateField(fsmDisplayManager, "blockCountText", bbtPanel.transform.Find("BlockCountText")?.GetComponent<TextMeshProUGUI>());
        SetPrivateField(fsmDisplayManager, "sessionTimerText", bbtPanel.transform.Find("SessionTimerText")?.GetComponent<TextMeshProUGUI>());
        SetPrivateField(fsmDisplayManager, "graspCountText", bbtPanel.transform.Find("GraspCountText")?.GetComponent<TextMeshProUGUI>());

        Debug.Log("✓ FSM Display UI setup complete!");
    }

    private GameObject CreateFSMDisplayPanel()
    {
        // Main panel
        GameObject panel = CreatePanel("FSMDisplayPanel", mainCanvas.transform);
        RectTransform panelRect = panel.GetComponent<RectTransform>();
        panelRect.anchorMin = new Vector2(0, 1);
        panelRect.anchorMax = new Vector2(0, 1);
        panelRect.pivot = new Vector2(0, 1);
        panelRect.anchoredPosition = new Vector2(20, -20);
        panelRect.sizeDelta = new Vector2(280, 120);

        // Background
        Image panelBg = panel.GetComponent<Image>();
        panelBg.color = new Color(0.1f, 0.1f, 0.1f, 0.85f);

        // State Indicator (colored circle)
        GameObject stateIndicator = CreateImage("StateIndicator", panel.transform);
        RectTransform indicatorRect = stateIndicator.GetComponent<RectTransform>();
        indicatorRect.anchorMin = new Vector2(0, 0.5f);
        indicatorRect.anchorMax = new Vector2(0, 0.5f);
        indicatorRect.pivot = new Vector2(0, 0.5f);
        indicatorRect.anchoredPosition = new Vector2(15, 0);
        indicatorRect.sizeDelta = new Vector2(80, 80);
        Image indicatorImg = stateIndicator.GetComponent<Image>();
        indicatorImg.color = new Color(0.3f, 0.7f, 0.3f); // Green for IDLE

        // State Text
        GameObject stateText = CreateText("StateText", panel.transform, "IDLE", 32);
        RectTransform stateTextRect = stateText.GetComponent<RectTransform>();
        stateTextRect.anchorMin = new Vector2(0, 0.5f);
        stateTextRect.anchorMax = new Vector2(1, 0.5f);
        stateTextRect.pivot = new Vector2(0, 0.5f);
        stateTextRect.anchoredPosition = new Vector2(110, 10);
        stateTextRect.sizeDelta = new Vector2(150, 50);

        // Lock Indicator
        GameObject lockIndicator = CreateImage("LockIndicator", panel.transform);
        RectTransform lockRect = lockIndicator.GetComponent<RectTransform>();
        lockRect.anchorMin = new Vector2(1, 1);
        lockRect.anchorMax = new Vector2(1, 1);
        lockRect.pivot = new Vector2(1, 1);
        lockRect.anchoredPosition = new Vector2(-10, -10);
        lockRect.sizeDelta = new Vector2(40, 40);
        Image lockImg = lockIndicator.GetComponent<Image>();
        lockImg.color = new Color(0.5f, 0.5f, 0.5f, 0.3f); // Inactive

        // Lock Timer Text
        GameObject lockTimerText = CreateText("LockTimerText", panel.transform, "", 16);
        RectTransform lockTimerRect = lockTimerText.GetComponent<RectTransform>();
        lockTimerRect.anchorMin = new Vector2(0, 0);
        lockTimerRect.anchorMax = new Vector2(1, 0);
        lockTimerRect.pivot = new Vector2(0.5f, 0);
        lockTimerRect.anchoredPosition = new Vector2(0, 5);
        lockTimerRect.sizeDelta = new Vector2(280, 25);
        lockTimerText.GetComponent<TextMeshProUGUI>().alignment = TextAlignmentOptions.Center;
        lockTimerText.SetActive(false);

        // Hide by default
        panel.SetActive(false);

        return panel;
    }

    private GameObject CreateBBTScoringPanel()
    {
        // Main panel
        GameObject panel = CreatePanel("BBTScoringPanel", mainCanvas.transform);
        RectTransform panelRect = panel.GetComponent<RectTransform>();
        panelRect.anchorMin = new Vector2(1, 1);
        panelRect.anchorMax = new Vector2(1, 1);
        panelRect.pivot = new Vector2(1, 1);
        panelRect.anchoredPosition = new Vector2(-20, -20);
        panelRect.sizeDelta = new Vector2(200, 140);

        // Background
        Image panelBg = panel.GetComponent<Image>();
        panelBg.color = new Color(0.1f, 0.1f, 0.15f, 0.9f);

        // Title
        GameObject title = CreateText("Title", panel.transform, "BBT SCORE", 18);
        RectTransform titleRect = title.GetComponent<RectTransform>();
        titleRect.anchorMin = new Vector2(0, 1);
        titleRect.anchorMax = new Vector2(1, 1);
        titleRect.pivot = new Vector2(0.5f, 1);
        titleRect.anchoredPosition = new Vector2(0, -5);
        titleRect.sizeDelta = new Vector2(200, 30);
        title.GetComponent<TextMeshProUGUI>().alignment = TextAlignmentOptions.Center;
        title.GetComponent<TextMeshProUGUI>().fontStyle = FontStyles.Bold;

        // Blocks Row
        CreateLabelValueRow(panel.transform, "Blocks:", "BlockCountText", "0", -40);

        // Grasps Row
        CreateLabelValueRow(panel.transform, "Grasps:", "GraspCountText", "0", -70);

        // Session Timer
        GameObject timerLabel = CreateText("TimerLabel", panel.transform, "Time:", 16);
        RectTransform timerLabelRect = timerLabel.GetComponent<RectTransform>();
        timerLabelRect.anchorMin = new Vector2(0, 1);
        timerLabelRect.anchorMax = new Vector2(0, 1);
        timerLabelRect.pivot = new Vector2(0, 1);
        timerLabelRect.anchoredPosition = new Vector2(15, -100);
        timerLabelRect.sizeDelta = new Vector2(80, 30);

        GameObject sessionTimer = CreateText("SessionTimerText", panel.transform, "00:00", 24);
        RectTransform sessionTimerRect = sessionTimer.GetComponent<RectTransform>();
        sessionTimerRect.anchorMin = new Vector2(0, 1);
        sessionTimerRect.anchorMax = new Vector2(1, 1);
        sessionTimerRect.pivot = new Vector2(0, 1);
        sessionTimerRect.anchoredPosition = new Vector2(80, -100);
        sessionTimerRect.sizeDelta = new Vector2(100, 30);
        sessionTimer.GetComponent<TextMeshProUGUI>().color = new Color(0.3f, 0.9f, 0.3f);

        // Hide by default
        panel.SetActive(false);

        return panel;
    }

    private void CreateLabelValueRow(Transform parent, string label, string valueName, string defaultValue, float yOffset)
    {
        GameObject labelObj = CreateText(valueName + "Label", parent, label, 16);
        RectTransform labelRect = labelObj.GetComponent<RectTransform>();
        labelRect.anchorMin = new Vector2(0, 1);
        labelRect.anchorMax = new Vector2(0, 1);
        labelRect.pivot = new Vector2(0, 1);
        labelRect.anchoredPosition = new Vector2(15, yOffset);
        labelRect.sizeDelta = new Vector2(80, 30);

        GameObject valueObj = CreateText(valueName, parent, defaultValue, 28);
        RectTransform valueRect = valueObj.GetComponent<RectTransform>();
        valueRect.anchorMin = new Vector2(0, 1);
        valueRect.anchorMax = new Vector2(1, 1);
        valueRect.pivot = new Vector2(0, 1);
        valueRect.anchoredPosition = new Vector2(100, yOffset);
        valueRect.sizeDelta = new Vector2(80, 30);
        valueObj.GetComponent<TextMeshProUGUI>().fontStyle = FontStyles.Bold;
        valueObj.GetComponent<TextMeshProUGUI>().color = new Color(1f, 0.9f, 0.3f);
    }

    private GameObject CreatePanel(string name, Transform parent)
    {
        GameObject panel = new GameObject(name);
        panel.transform.SetParent(parent, false);
        panel.AddComponent<RectTransform>();
        panel.AddComponent<CanvasRenderer>();
        panel.AddComponent<Image>();
        return panel;
    }

    private GameObject CreateImage(string name, Transform parent)
    {
        GameObject imgObj = new GameObject(name);
        imgObj.transform.SetParent(parent, false);
        imgObj.AddComponent<RectTransform>();
        imgObj.AddComponent<CanvasRenderer>();
        imgObj.AddComponent<Image>();
        return imgObj;
    }

    private GameObject CreateText(string name, Transform parent, string text, int fontSize)
    {
        GameObject textObj = new GameObject(name);
        textObj.transform.SetParent(parent, false);
        textObj.AddComponent<RectTransform>();
        TextMeshProUGUI tmp = textObj.AddComponent<TextMeshProUGUI>();
        tmp.text = text;
        tmp.fontSize = fontSize;
        tmp.color = Color.white;
        tmp.alignment = TextAlignmentOptions.Left;
        return textObj;
    }

    private void SetPrivateField(object obj, string fieldName, object value)
    {
        var field = obj.GetType().GetField(fieldName,
            System.Reflection.BindingFlags.NonPublic |
            System.Reflection.BindingFlags.Instance);
        if (field != null && value != null)
        {
            field.SetValue(obj, value);
        }
    }
}
