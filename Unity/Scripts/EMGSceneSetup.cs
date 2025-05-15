using UnityEngine;
using UnityEngine.UI;
using System.Collections;

public class EMGSceneSetup : MonoBehaviour
{
    [Header("Hand Model")]
    [SerializeField] private GameObject handModelPrefab;
    [SerializeField] private Vector3 handPosition = new Vector3(0, 0, 0);
    [SerializeField] private Vector3 handRotation = new Vector3(0, 180, 0);
    [SerializeField] private Vector3 handScale = new Vector3(1, 1, 1);

    [Header("UI Elements")]
    [SerializeField] private bool createUI = true;
    [SerializeField] private Canvas uiCanvas;
    [SerializeField] private GameObject visualizerPanelPrefab;

    [Header("Components")]
    [SerializeField] private bool autoAssignComponents = true;
    [SerializeField] private string communicationHandlerName = "EMGCommunicationHandler";
    [SerializeField] private string handControllerName = "EMGHandController";
    [SerializeField] private string visualizerName = "EMGVisualizer";

    [Header("Setup Options")]
    [SerializeField] private bool setupOnStart = true;
    [SerializeField] private bool createLights = true;
    [SerializeField] private bool createCamera = true;

    private GameObject handModel;
    private EMGCommunicationHandler communicationHandler;
    private EMGHandController handController;
    private EMGVisualizer visualizer;

    void Start()
    {
        if (setupOnStart)
        {
            SetupScene();
        }
    }

    [ContextMenu("Setup EMG Scene")]
    public void SetupScene()
    {
        // Create basic scene elements
        if (createCamera && Camera.main == null)
        {
            CreateCamera();
        }

        if (createLights && FindObjectsOfType<Light>().Length == 0)
        {
            CreateLights();
        }

        // Create communication handler if needed
        if (communicationHandler == null)
        {
            communicationHandler = FindObjectOfType<EMGCommunicationHandler>();

            if (communicationHandler == null)
            {
                GameObject commObject = new GameObject(communicationHandlerName);
                communicationHandler = commObject.AddComponent<EMGCommunicationHandler>();
                Debug.Log("Created EMGCommunicationHandler");
            }
        }

        // Create or find hand model
        if (handModel == null)
        {
            // Try to find existing hand model in scene
            handController = FindObjectOfType<EMGHandController>();
            if (handController != null)
            {
                handModel = handController.gameObject;
            }
            else if (handModelPrefab != null)
            {
                // Instantiate hand model from prefab
                handModel = Instantiate(handModelPrefab, handPosition, Quaternion.Euler(handRotation));
                handModel.transform.localScale = handScale;
                Debug.Log("Created hand model from prefab");

                // Add EMGHandController if needed
                handController = handModel.GetComponent<EMGHandController>();
                if (handController == null)
                {
                    handController = handModel.AddComponent<EMGHandController>();
                    Debug.Log("Added EMGHandController to hand model");
                }

                // Setup references
                if (autoAssignComponents && handController != null)
                {
                    handController.name = handControllerName;

                    // Assign communication handler to hand controller
                    var serializedObject = new UnityEditor.SerializedObject(handController);
                    var commHandlerProperty = serializedObject.FindProperty("communicationHandler");
                    if (commHandlerProperty != null)
                    {
                        commHandlerProperty.objectReferenceValue = communicationHandler;
                        serializedObject.ApplyModifiedProperties();
                        Debug.Log("Assigned communication handler to hand controller");
                    }
                }
            }
            else
            {
                Debug.LogWarning("No hand model prefab assigned and no hand model found in scene!");
            }
        }

        // Create UI elements
        if (createUI)
        {
            CreateUIElements();
        }
    }

    private void CreateCamera()
    {
        GameObject cameraObj = new GameObject("Main Camera");
        Camera camera = cameraObj.AddComponent<Camera>();
        cameraObj.tag = "MainCamera";

        // Position camera to view the hand
        cameraObj.transform.position = new Vector3(0, 1.6f, -0.5f);
        cameraObj.transform.rotation = Quaternion.Euler(0, 180, 0);

        // Add audio listener
        cameraObj.AddComponent<AudioListener>();

        Debug.Log("Created main camera");
    }

    private void CreateLights()
    {
        // Create a directional light for main illumination
        GameObject directionalLight = new GameObject("Directional Light");
        Light dirLight = directionalLight.AddComponent<Light>();
        dirLight.type = LightType.Directional;
        dirLight.intensity = 1.0f;
        dirLight.color = Color.white;
        directionalLight.transform.rotation = Quaternion.Euler(50, -30, 0);

        // Add ambient light
        RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Skybox;
        RenderSettings.ambientIntensity = 1.0f;

        Debug.Log("Created lighting");
    }

    private void CreateUIElements()
    {
        // Create canvas if needed
        if (uiCanvas == null)
        {
            GameObject canvasObj = new GameObject("Canvas");
            uiCanvas = canvasObj.AddComponent<Canvas>();
            uiCanvas.renderMode = RenderMode.ScreenSpaceOverlay;

            // Add required components
            canvasObj.AddComponent<UnityEngine.UI.CanvasScaler>();
            canvasObj.AddComponent<UnityEngine.UI.GraphicRaycaster>();

            Debug.Log("Created UI canvas");
        }

        // Create visualizer panel
        GameObject visualizerObj;
        if (visualizerPanelPrefab != null)
        {
            visualizerObj = Instantiate(visualizerPanelPrefab, uiCanvas.transform);
        }
        else
        {
            visualizerObj = new GameObject("EMG Visualizer Panel");
            visualizerObj.transform.SetParent(uiCanvas.transform, false);

            // Add panel components
            RectTransform rect = visualizerObj.AddComponent<RectTransform>();
            rect.anchorMin = new Vector2(0, 0);
            rect.anchorMax = new Vector2(0.3f, 1);
            rect.pivot = new Vector2(0, 0);
            rect.offsetMin = new Vector2(10, 10);
            rect.offsetMax = new Vector2(-10, -10);

            Image bg = visualizerObj.AddComponent<Image>();
            bg.color = new Color(0, 0, 0, 0.5f);

            // Add scrollview for bars
            GameObject scrollObj = new GameObject("ScrollView");
            scrollObj.transform.SetParent(visualizerObj.transform, false);
            ScrollRect scrollRect = scrollObj.AddComponent<ScrollRect>();

            RectTransform scrollRectTransform = scrollObj.GetComponent<RectTransform>();
            scrollRectTransform.anchorMin = Vector2.zero;
            scrollRectTransform.anchorMax = Vector2.one;
            scrollRectTransform.offsetMin = new Vector2(5, 5);
            scrollRectTransform.offsetMax = new Vector2(-5, -5);

            // Add viewport and content
            GameObject viewportObj = new GameObject("Viewport");
            viewportObj.transform.SetParent(scrollObj.transform, false);
            RectTransform viewportRect = viewportObj.AddComponent<RectTransform>();
            viewportRect.anchorMin = Vector2.zero;
            viewportRect.anchorMax = Vector2.one;
            viewportRect.offsetMin = Vector2.zero;
            viewportRect.offsetMax = Vector2.zero;

            GameObject contentObj = new GameObject("Content");
            contentObj.transform.SetParent(viewportObj.transform, false);
            RectTransform contentRect = contentObj.AddComponent<RectTransform>();
            contentRect.anchorMin = new Vector2(0, 1);
            contentRect.anchorMax = new Vector2(1, 1);
            contentRect.pivot = new Vector2(0.5f, 1);
            contentRect.sizeDelta = new Vector2(0, 500);

            // Setup scrollview references
            scrollRect.viewport = viewportRect;
            scrollRect.content = contentRect;
            scrollRect.horizontal = false;
            scrollRect.vertical = true;

            // Add visualizer component
            visualizer = visualizerObj.AddComponent<EMGVisualizer>();
            visualizer.name = visualizerName;

            Debug.Log("Created EMG Visualizer panel");
        }

        // Setup visualizer if needed
        if (visualizer == null)
        {
            visualizer = FindObjectOfType<EMGVisualizer>();
        }

        // Assign references
        if (autoAssignComponents && visualizer != null)
        {
            // Assign communication handler to visualizer
            var serializedObject = new UnityEditor.SerializedObject(visualizer);
            var commHandlerProperty = serializedObject.FindProperty("communicationHandler");
            if (commHandlerProperty != null)
            {
                commHandlerProperty.objectReferenceValue = communicationHandler;
                serializedObject.ApplyModifiedProperties();
                Debug.Log("Assigned communication handler to visualizer");
            }
        }
    }

#if UNITY_EDITOR
    [UnityEditor.MenuItem("EMG Tools/Setup EMG Scene")]
    public static void SetupEMGScene()
    {
        // Find existing setup component or create new one
        EMGSceneSetup setup = FindObjectOfType<EMGSceneSetup>();
        if (setup == null)
        {
            GameObject setupObj = new GameObject("EMG Scene Setup");
            setup = setupObj.AddComponent<EMGSceneSetup>();
        }
        
        setup.SetupScene();
    }
#endif
}