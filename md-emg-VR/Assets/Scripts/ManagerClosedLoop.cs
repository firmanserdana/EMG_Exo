using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using TMPro;
using UnityEngine;

public class ManagerClosedLoop : MonoBehaviour
{
    public static ManagerClosedLoop Instance { get; private set; }

    // Other scripts
    private HandController handController, handObjectiveController;
    private GUIManager guiManager;

    // Hand 
    [Header("Hands")]
    public GameObject leftHand;
    public GameObject rightHand;
    public GameObject leftHandObjective;
    public GameObject rightHandObjective;

    // Grasping objects 
    [Header("Grasping objects")]
    public GameObject leftHandObjects;
    public GameObject rightHandObjects;
    private Dictionary<string, GameObject> leftGraspObjects;
    private Dictionary<string, GameObject> rightGraspObjects;

    // GUI
    [Header("GUI")]
    public UnityEngine.UI.Button btnPlay;
    public UnityEngine.UI.Button btnStop;
    public UnityEngine.UI.Button btnExit;
    public TMP_Text lblTrialsCount, lblAccuracy;

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
        guiManager = GameObject.Find("Manager").GetComponent<GUIManager>();

        // TCP server connection
        TcpServerManager.Instance.OnMessageReceived += HandleTcpEvents;

        // Initialize the hand controller based on the dominant hand
        if (GameSettings.dominantHand == DominantHand.right)
        {
            handController = rightHand.GetComponent<HandController>();
            handObjectiveController = rightHandObjective.GetComponent<HandController>();
            leftHand.SetActive(false);
            leftHandObjective.SetActive(false);
        }
        else
        {
            handController = leftHand.GetComponent<HandController>();
            handObjectiveController = leftHandObjective.GetComponent<HandController>();
            rightHand.SetActive(false);
            rightHandObjective.SetActive(false);
        }

        // GUI initializations
        btnPlay.interactable = true;
        btnStop.interactable = false;

        UpdateTrialsLabel();

        // Load configs
        string configPath = Path.Combine(Application.dataPath, "Config");

        string json = File.ReadAllText(Path.Combine(configPath, "ClosedLoopConfig.json"));
        sessionConfig = JsonUtility.FromJson<ClosedLoopConfig>(json);

        SessionControl.trialsClass = new int[SessionControl.numTotalTrials];
        SessionControl.trialsLabels = new string[SessionControl.numTotalTrials];
        SessionControl.trialsClassID = new int[SessionControl.numTotalTrials];

        // selecting the grasping labels and IDs based on the grasping type
        if (GameSettings.graspingType == GraspingType.HandOpenClose) // open-close
        {
            taskGraspLabels = sessionConfig.graspLabelsOpenClose;
            taskGraspID = sessionConfig.graspIDOpenClose;

            // hide grasp objects
            rightHandObjects.SetActive(false);
            leftHandObjects.SetActive(false);
        }
        else if (GameSettings.graspingType == GraspingType.GraspPatterns) // grasp patterns
        {
            taskGraspLabels = sessionConfig.graspLabelsGraspPatterns;
            taskGraspID = sessionConfig.graspIDGraspPatterns;

            // Initialize grasp object 
            if (GameSettings.dominantHand == DominantHand.right)
            {
                rightGraspObjects = new Dictionary<string, GameObject>();

                foreach (Transform child in rightHandObjects.transform)
                {
                    rightGraspObjects[child.name] = child.gameObject;
                    child.gameObject.SetActive(false); // Hide the right hand objects initially
                }

                leftHandObjects.SetActive(false); // Hide the left hand objects
            }
            else
            {
                leftGraspObjects = new Dictionary<string, GameObject>();

                foreach (Transform child in leftHandObjects.transform)
                {
                    leftGraspObjects[child.name] = child.gameObject;
                    child.gameObject.SetActive(false); // Hide the left hand objects initially
                }

                rightHandObjects.SetActive(false); // Hide the right hand objects
            }
        }
        else // single fingers
        {
            taskGraspLabels = sessionConfig.graspLabelsSingleFingers;
            taskGraspID = sessionConfig.graspIDSingleFingers;

            // hide grasp objects
            rightHandObjects.SetActive(false);
            leftHandObjects.SetActive(false);
        }

        int numGraspClass = taskGraspLabels.Length;
        int numTrialsPerGrasp = SessionControl.numTotalTrials / numGraspClass;

        // building a [0,..,numGraspClass] sequence for the trials type
        for (int bl = 0; bl < numTrialsPerGrasp; bl++)
        {
            int[] indices = Enumerable.Range(0, numGraspClass).ToArray();
            Shuffle(indices); // shuffling the order of the trials

            for (int i = 0; i < numGraspClass; i++)
            {
                SessionControl.trialsClass[numGraspClass * bl + i] = indices[i];
                SessionControl.trialsLabels[numGraspClass * bl + i] = taskGraspLabels[indices[i]];
                SessionControl.trialsClassID[numGraspClass * bl + i] = taskGraspID[indices[i]];
            }
        }
    }

    // Update is called once per frame
    void Update()
    {
        // check if trial timer has expired
        if (SessionControl.isDecoding && SessionControl.timerElapsedTime <= 0)
        {
            SessionControl.isDecoding = false;

            RegisterEvent("trial_result", 2);
            RegisterEvent("trial_duration_expired");
            RegisterEvent("decoding_stop");

            // Show the grasp failed GUI
            guiManager.SetGUIState(GUIManager.GUIFeedbackState.TimeExpired);

            RegisterEvent("trial_end");
            Debug.Log("Trial finished");

            SessionControl.trlProgression++;

            // Update the trials label
            UpdateTrialsLabel();

            // Hide the grasp objects in the hand if the grasping type is grasp patterns
            if (GameSettings.graspingType == GraspingType.GraspPatterns)
            {
                HideGraspObjects();
            }

            StartCoroutine(WaitAndStartNewTrial());
        }
    }


    IEnumerator WaitAndStartNewTrial()
    {
        yield return new WaitForSeconds(3f);

        // Start the trials start executor coroutine
        StartCoroutine(TrialsStartExecutor());
    }

    IEnumerator TrialsStartExecutor()
    {
        // Reset the GUI instruction for the grasp and reset the GUI state
        guiManager.SetGUIInstructions(GUIManager.GUIFeedbackInstructions.Empty);
        guiManager.SetGUIState(GUIManager.GUIFeedbackState.Empty);

        // release both hand and objective grasp
        handObjectiveController.ReleaseGrasp();
        yield return handController.ReleaseGrasp();

        // Check if the session is finished
        if (SessionControl.trlProgression == SessionControl.numTotalTrials)
        {
            yield return new WaitForSeconds(1.5f);

            RegisterEvent("session_end");
            Debug.Log("Session finished");

            // End of session
            guiManager.SetGUIState(GUIManager.GUIFeedbackState.EndSession);

            // Hide the grasp objects in the hand if the grasping type is grasp patterns
            if (GameSettings.graspingType == GraspingType.GraspPatterns)
            {
                HideGraspObjects();
            }

            // Hide both hands and objective hands
            rightHand.SetActive(false);
            rightHandObjective.SetActive(false);
            leftHand.SetActive(false);
            leftHandObjective.SetActive(false);
        }
        else
        {
            float intervalSeconds = sessionConfig.trialIntervalDuration / 1000;

            // Wait before starting the trials
            yield return new WaitForSeconds(sessionConfig.trialsStartDelay / 1000);

            // Reset the GUI timer
            guiManager.resetTimer();

            // Hide feedack state elements
            guiManager.SetGUIState(GUIManager.GUIFeedbackState.Empty);

            // Hide the grasp objects in the hand if the grasping type is grasp patterns
            if (GameSettings.graspingType == GraspingType.GraspPatterns)
            {
                HideGraspObjects();
            }

            if (SessionControl.isRunning)
            {
                Debug.Log("Trial start");
                RegisterEvent("trial_start");

                yield return StartCoroutine(HandObjectiveAnimation());
            }
            else
            {
                yield return new WaitForSeconds(intervalSeconds);
            }
        }
    }

    IEnumerator HandObjectiveAnimation()
    {
        // Get the current trial informations
        string graspName = SessionControl.trialsLabels[SessionControl.trlProgression];
        int graspID = SessionControl.trialsClassID[SessionControl.trlProgression];

        // Show the GUI instruction for the grasp
        guiManager.SetGUIInstructions(graspName);

        // Show the grasp object in the hand if the grasping type is grasp patterns
        if (GameSettings.graspingType == GraspingType.GraspPatterns)
        {
            ShowGraspObject(graspName);
        }

        yield return new WaitForSeconds(sessionConfig.cueGraspStartInterval / 1000f);

        // Show the grasp start cue
        guiManager.SetGUIState(GUIManager.GUIFeedbackState.Start);

        // Start the grasp animation
        Debug.Log("Grasp objective start");
        RegisterEvent("grasp_objective_start", graspID);

        // start the hand objective grasp animation
        yield return handObjectiveController.StartGrasp(graspName);

        // Start decoding
        SessionControl.isDecoding = true;
        RegisterEvent("decoding_start");

        // Start the trial timer
        SessionControl.timerElapsedTime = GameSettings.trialDuration;
        guiManager.startTimer();
        Invoke("UpdateTimerProgress", GameSettings.timerUpdateDelay); // start the experiment timer
    }

    IEnumerator TrialDecodedExecutor(int graspID)
    {
        RegisterEvent("grasp_decoded", graspID);
        Debug.Log($"Grasp decoded - graspID: {graspID}");

        guiManager.stopTimer(); // stop the timer

        bool graspSuccess = SessionControl.trialsClassID[SessionControl.trlProgression] == graspID;

        if (graspSuccess)
        {
            RegisterEvent("trial_result", 1);
            RegisterEvent("grasp_success");
            SessionControl.numTrialsCorrect++;

            // Show the grasp success GUI
            guiManager.SetGUIState(GUIManager.GUIFeedbackState.Success);
        }
        else
        {
            RegisterEvent("trial_result", 0);
            RegisterEvent("grasp_error");

            // Show the grasp failed GUI
            guiManager.SetGUIState(GUIManager.GUIFeedbackState.Failed);
        }

        yield return StartCoroutine(HandGraspAnimation(graspID));

        RegisterEvent("trial_end");
        Debug.Log("Trial finished");

        SessionControl.trlProgression++;

        // Update the trials label
        UpdateTrialsLabel();

        // Start the trials start executor coroutine
        StartCoroutine(TrialsStartExecutor());
    }

    IEnumerator HandGraspAnimation(int graspID)
    {
        int graspIndex = Array.IndexOf(taskGraspID, graspID);

        // Get the current trial informations
        string graspName = taskGraspLabels[graspIndex];

        // Start the grasp animation
        RegisterEvent("grasp_start", graspID);

        yield return handController.StartGrasp(graspName);

        RegisterEvent("grasp_hold_start");
        Debug.Log("grasp hold start");

        yield return new WaitForSeconds(sessionConfig.holdDuration / 1000f);

        Debug.Log("hold end");
        RegisterEvent("grasp_hold_end");

        // release both hand and objective grasp
        handObjectiveController.ReleaseGrasp();
        yield return handController.ReleaseGrasp();

        RegisterEvent("grasp_released");
        Debug.Log("Grasp released");
    }

    public void OnBtnPlayClick()
    {
        // GUI updates
        btnPlay.interactable = false;
        btnStop.interactable = true;

        // Set the session as running
        SessionControl.isRunning = true;

        RegisterEvent("session_start");

        // Start the trials start executor coroutine
        StartCoroutine(TrialsStartExecutor());

        Debug.Log("Session start");
    }

    public void OnBtnStopClick()
    {
        // Stop the session
        SessionControl.isRunning = false;
        RegisterEvent("session_stop");

        // GUI updates
        btnPlay.interactable = true;
        btnStop.interactable = false;

        Debug.Log("Session stop");
    }

    public void OnBtnExitClick()
    {
        RegisterEvent("session_exit");

        // Exit the application
        Application.Quit();

        Debug.Log("Application exit");
    }

    private void UpdateTrialsLabel()
    {
        lblTrialsCount.text = $"Trials: {SessionControl.trlProgression}/{SessionControl.numTotalTrials}";

        if (SessionControl.trlProgression > 0)
        {
            lblAccuracy.text = $"Accuracy: {SessionControl.numTrialsCorrect}/{SessionControl.trlProgression} " +
                $"({(SessionControl.trlProgression > 0 ? Mathf.Round(SessionControl.numTrialsCorrect / (float)SessionControl.trlProgression * 100) : 0)}%)";
        }
        else
        {
            lblAccuracy.text = "";
        }
    }

    void RegisterEvent(string eventVal, int? eventID = null)
    {
        TcpServerManager.Instance.SendMessageToClient(eventVal, eventID);
    }

    void HandleTcpEvents(TCPEvent eventMsg)
    {
        if (SessionControl.isDecoding)
        {
            if (eventMsg.eventName == "grasp_decoded")
            {
                // Stop decoding
                SessionControl.isDecoding = false;
                RegisterEvent("decoding_stop");

                // Handle trial decoded event
                StartCoroutine(TrialDecodedExecutor(eventMsg.eventID));
            }
        }
    }

    void Shuffle(int[] array)
    {
        System.Random random = new System.Random();
        for (int i = array.Length - 1; i > 0; i--)
        {
            int j = random.Next(0, i + 1);
            int temp = array[i];
            array[i] = array[j];
            array[j] = temp;
        }
    }
    private void UpdateTimerProgress()
    {
        if (SessionControl.isDecoding)
        {
            SessionControl.timerElapsedTime -= GameSettings.timerUpdateDelay;
            Invoke("UpdateTimerProgress", GameSettings.timerUpdateDelay);
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
