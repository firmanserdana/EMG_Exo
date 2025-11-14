using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using TMPro;
using UnityEngine;

public class ManagerDecodingFeedback : MonoBehaviour
{
    public static ManagerDecodingFeedback Instance { get; private set; }

    // Other scripts
    private GUIDecodingFeedbackManager guiManager;

    // Hands
    [Header("Hands")]
    public GameObject leftHands;
    public GameObject rightHands;
    public GameObject LeftHandsOpenClose, LeftHandsGraspPatterns, LeftHandsSingleFingers;
    public GameObject RightHandsOpenClose, RightHandsGraspPatterns, RightHandsSingleFingers;

    // Grasping objects 
    [Header("Grasping objects")]
    public GameObject leftHandObjects;
    public GameObject rightHandObjects;
    private Dictionary<string, GameObject> leftGraspObjects;
    private Dictionary<string, GameObject> rightGraspObjects;

    [Header("Materials")]
    [SerializeField] private Material handInactive;
    [SerializeField] private Material handActive;

    // GUI
    [Header("GUI")]
    public UnityEngine.UI.Button btnPlay;
    public UnityEngine.UI.Button btnStop;
    public UnityEngine.UI.Button btnExit;

    // Configs
    private ClosedLoopConfig sessionConfig = new();

    // Task control
    string[] taskGraspLabels;
    int[] taskGraspID;

    void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(this.gameObject);
            return;
        }
        Instance = this;
        DontDestroyOnLoad(this.gameObject);
    }

    // Start is called before the first frame update
    void Start()
    {
        // Initialize the GUI manager
        guiManager = GameObject.Find("Manager").GetComponent<GUIDecodingFeedbackManager>();

        // TCP server connection
        TcpServerManager.Instance.OnMessageReceived += HandleTcpEvents;

        // Initialize the hand controller based on the dominant hand
        if (GameSettings.dominantHand == DominantHand.right)
        {
            leftHands.SetActive(false);
        }
        else
        {
            rightHands.SetActive(false);
        }

        // GUI initializations
        btnPlay.interactable = true;
        btnStop.interactable = false;

        // Load configs
        string configPath = Path.Combine(Application.dataPath, "Config");

        string json = File.ReadAllText(Path.Combine(configPath, "ClosedLoopConfig.json"));
        sessionConfig = JsonUtility.FromJson<ClosedLoopConfig>(json);

        // selecting the grasping labels and IDs based on the grasping type
        if (GameSettings.graspingType == GraspingType.HandOpenClose) // open-close
        {
            taskGraspLabels = sessionConfig.graspLabelsOpenClose;
            taskGraspID = sessionConfig.graspIDOpenClose;

            // hide grasp objects
            rightHandObjects.SetActive(false);
            leftHandObjects.SetActive(false);

            // hide other hands
            LeftHandsGraspPatterns.SetActive(false);
            LeftHandsSingleFingers.SetActive(false);
            RightHandsGraspPatterns.SetActive(false);
            RightHandsSingleFingers.SetActive(false);
        }
        else if (GameSettings.graspingType == GraspingType.GraspPatterns) // grasp patterns
        {
            taskGraspLabels = sessionConfig.graspLabelsGraspPatterns;
            taskGraspID = sessionConfig.graspIDGraspPatterns;

            // Initialize grasp object 
            if (GameSettings.dominantHand == DominantHand.right)
            {
                leftHandObjects.SetActive(false); // Hide the left hand objects
            }
            else
            {
                rightHandObjects.SetActive(false); // Hide the right hand objects
            }

            // hide other hands
            LeftHandsOpenClose.SetActive(false);
            LeftHandsSingleFingers.SetActive(false);
            RightHandsOpenClose.SetActive(false);
            RightHandsSingleFingers.SetActive(false);
        }
        else // single fingers
        {
            taskGraspLabels = sessionConfig.graspLabelsSingleFingers;
            taskGraspID = sessionConfig.graspIDSingleFingers;

            // hide grasp objects
            rightHandObjects.SetActive(false);
            leftHandObjects.SetActive(false);

            // hide other hands
            LeftHandsOpenClose.SetActive(false);
            LeftHandsGraspPatterns.SetActive(false);
            RightHandsOpenClose.SetActive(false);
            RightHandsGraspPatterns.SetActive(false);
        }
    }

    // Update is called once per frame
    void Update()
    {
    }

    public void OnBtnPlayClick()
    {
        // GUI updates
        btnPlay.interactable = false;
        btnStop.interactable = true;

        // Set the session as running
        SessionControl.isRunning = true;

        // Send decoding_start event to Python backend
        TcpServerManager.Instance.SendMessageToClient("decoding_start");

        Debug.Log("Session start");
    }

    public void OnBtnStopClick()
    {
        // Stop the session
        SessionControl.isRunning = false;

        // Send decoding_stop event to Python backend
        TcpServerManager.Instance.SendMessageToClient("decoding_stop");

        // GUI updates
        btnPlay.interactable = true;
        btnStop.interactable = false;

        Debug.Log("Session stop");
    }

    public void OnBtnExitClick()
    {
        // Exit the application
        Application.Quit();

        Debug.Log("Application exit");
    }

    void HandleTcpEvents(TCPEvent eventMsg)
    {
        if (SessionControl.isRunning && eventMsg.eventName == "grasp_decoded")
        {
            Debug.Log($"Grasp decoded event received: {eventMsg.eventID}");

            // Find the index of eventID in the current taskGraspID array
            int classIndex = Array.IndexOf(taskGraspID, eventMsg.eventID);

            if (classIndex >= 0)
            {
                guiManager.SetClassActive(classIndex);

                // Set hand materials for the correct container
                GameObject handsContainer = GetHandsContainer();
                if (handsContainer != null)
                {
                    SetHandMaterials(handsContainer, classIndex);
                }
            }
            else
            {
                Debug.LogWarning($"eventID {eventMsg.eventID} not found in current taskGraspID array.");
            }
        }
    }

    // Helper to get the correct hands container based on task and dominant hand
    private GameObject GetHandsContainer()
    {
        bool isRight = GameSettings.dominantHand == DominantHand.right;
        switch (GameSettings.graspingType)
        {
            case GraspingType.HandOpenClose:
                return isRight ? RightHandsOpenClose : LeftHandsOpenClose;
            case GraspingType.GraspPatterns:
                return isRight ? RightHandsGraspPatterns : LeftHandsGraspPatterns;
            case GraspingType.SingleFingers:
                return isRight ? RightHandsSingleFingers : LeftHandsSingleFingers;
            default:
                return null;
        }
    }

    // Helper to set materials for all children, activating only the classIndex
    private void SetHandMaterials(GameObject handsContainer, int classIndex)
    {
        int i = 0;
        foreach (Transform child in handsContainer.transform)
        {
            // Try to get Renderer from the child or any of its children
            var renderer = child.GetComponent<Renderer>();
            if (renderer == null)
                renderer = child.GetComponentInChildren<Renderer>();

            if (renderer != null)
            {
                renderer.material = (i == classIndex) ? handActive : handInactive;
            }
            i++;
        }
    }

    public void ShowGraspObject(string graspName)
    {
        bool isRightHand = GameSettings.dominantHand == DominantHand.right;

        // Hide all first
        HideGraspObjects();

        // Show the requested one
        if (isRightHand)
        {
            if (rightGraspObjects.TryGetValue($"{graspName}Object", out var obj))
                obj.SetActive(true);
        }
        else
        {
            if (leftGraspObjects.TryGetValue($"{graspName}Object", out var obj))
                obj.SetActive(true);
        }
    }

    public void HideGraspObjects()
    {
        bool isRightHand = GameSettings.dominantHand == DominantHand.right;

        foreach (var obj in (isRightHand ? rightGraspObjects : leftGraspObjects).Values)
            obj.SetActive(false);
    }
}
