using UnityEngine;
using System.Collections.Generic;
using UnityEngine.UI;

public class EMGVisualizer : MonoBehaviour
{
    [Header("References")]
    [SerializeField] private EMGCommunicationHandler communicationHandler;
    [SerializeField] private RectTransform visualizationPanel;

    [Header("Visualization Settings")]
    [SerializeField] private GameObject barPrefab;
    [SerializeField] private Color flexionColor = Color.blue;
    [SerializeField] private Color extensionColor = Color.green;
    [SerializeField] private Color pinchingColor = Color.yellow;
    [SerializeField] private Color abductionColor = Color.red;

    // Bar graph elements
    private Dictionary<string, Image> barGraphs = new Dictionary<string, Image>();
    private Dictionary<string, Text> barLabels = new Dictionary<string, Text>();

    void Start()
    {
        if (communicationHandler == null)
        {
            communicationHandler = FindObjectOfType<EMGCommunicationHandler>();

            if (communicationHandler == null)
            {
                Debug.LogError("EMGCommunicationHandler not found!");
                enabled = false;
                return;
            }
        }

        // Create visualization elements
        CreateVisualizationElements();

        // Register for hand state updates
        communicationHandler.OnHandStateUpdated += OnHandStateUpdated;
    }

    void OnDestroy()
    {
        if (communicationHandler != null)
        {
            communicationHandler.OnHandStateUpdated -= OnHandStateUpdated;
        }
    }

    private void CreateVisualizationElements()
    {
        if (barPrefab == null || visualizationPanel == null)
        {
            Debug.LogError("Bar prefab or visualization panel not assigned!");
            return;
        }

        // Define visualization order and grouping
        List<BarDefinition> barDefinitions = new List<BarDefinition>
        {
            new BarDefinition("thumb_flexion", "Thumb Flex", flexionColor),
            new BarDefinition("thumb_extension", "Thumb Ext", extensionColor),
            new BarDefinition("thumb_pinching", "Thumb Pinch", pinchingColor),
            new BarDefinition("thumb_abduction", "Thumb Abd", abductionColor),

            new BarDefinition("index_flexion", "Index Flex", flexionColor),
            new BarDefinition("index_extension", "Index Ext", extensionColor),
            new BarDefinition("index_pinching", "Index Pinch", pinchingColor),

            new BarDefinition("middle_flexion", "Middle Flex", flexionColor),
            new BarDefinition("middle_extension", "Middle Ext", extensionColor),
            new BarDefinition("middle_pinching", "Middle Pinch", pinchingColor),

            new BarDefinition("ring_little_flexion", "Ring/Little Flex", flexionColor),
            new BarDefinition("ring_little_extension", "Ring/Little Ext", extensionColor)
        };

        // Create bars
        float yPos = 0;
        float barHeight = 20f;
        float spacing = 5f;
        float totalHeight = (barHeight + spacing) * barDefinitions.Count;

        // Adjust panel height
        visualizationPanel.sizeDelta = new Vector2(visualizationPanel.sizeDelta.x, totalHeight);

        // Create bars from bottom to top
        for (int i = 0; i < barDefinitions.Count; i++)
        {
            BarDefinition def = barDefinitions[i];

            // Instantiate bar
            GameObject barObj = Instantiate(barPrefab, visualizationPanel);
            RectTransform barRect = barObj.GetComponent<RectTransform>();
            barRect.anchoredPosition = new Vector2(0, yPos);
            barRect.sizeDelta = new Vector2(0, barHeight);

            // Set up label
            Text label = barObj.GetComponentInChildren<Text>();
            if (label != null)
            {
                label.text = def.displayName;
                barLabels[def.key] = label;
            }

            // Set up bar fill
            Image barFill = barObj.GetComponentInChildren<Image>();
            if (barFill != null)
            {
                barFill.color = def.color;
                barGraphs[def.key] = barFill;
            }

            // Move to next position
            yPos += barHeight + spacing;
        }
    }

    private void OnHandStateUpdated(Dictionary<string, float> state)
    {
        // Update visualization based on the state
        foreach (var entry in state)
        {
            if (barGraphs.ContainsKey(entry.Key))
            {
                // Update bar fill amount (limited to 0-1 range)
                barGraphs[entry.Key].fillAmount = Mathf.Clamp01(entry.Value);

                // Update label with value
                if (barLabels.ContainsKey(entry.Key))
                {
                    barLabels[entry.Key].text = $"{entry.Key.Replace("_", " ")}: {entry.Value:F2}";
                }
            }
        }
    }

    // Helper class for bar definitions
    private class BarDefinition
    {
        public string key;
        public string displayName;
        public Color color;

        public BarDefinition(string key, string displayName, Color color)
        {
            this.key = key;
            this.displayName = displayName;
            this.color = color;
        }
    }
}