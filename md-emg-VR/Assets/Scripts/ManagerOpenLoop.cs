using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using TMPro;
using Unity.VisualScripting;
using UnityEngine;

public class ManagerOpenLoop : MonoBehaviour
{
    public static ManagerOpenLoop Instance { get; private set; }

    // Other scripts
    private HandController handController;
    private GUIManager guiManager;

    // Hand 
    [Header("Hands")]
    public GameObject leftHand;
    public GameObject rightHand;

    // Grasping objects - used only for grasp patterns
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
    public TMP_Text lblTrialsCount;

    // Configs
    private OpenLoopConfig sessionConfig = new();

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

        // Initialize the hand controller based on the dominant hand
        if (GameSettings.dominantHand == DominantHand.right)
        {
            handController = rightHand.GetComponent<HandController>();
            leftHand.SetActive(false);
        }
        else
        {
            handController = leftHand.GetComponent<HandController>();
            rightHand.SetActive(false);
        }

        // GUI initializations
        btnPlay.interactable = true;
        btnStop.interactable = false;

        UpdateTrialsLabel();

        // Load configs
        string configPath = Path.Combine(Application.dataPath, "Config");

        string json = File.ReadAllText(Path.Combine(configPath, "OpenLoopConfig.json"));
        sessionConfig = JsonUtility.FromJson<OpenLoopConfig>(json);

        SessionControl.trialsClass = new int[SessionControl.numTotalTrials];
        SessionControl.trialsLabels = new string[SessionControl.numTotalTrials];
        SessionControl.trialsClassID = new int[SessionControl.numTotalTrials];

        string[] graspLabels;
        int[] graspID;

        // selecting the grasping labels and IDs based on the grasping type
        if (GameSettings.graspingType == GraspingType.HandOpenClose) // open-close
        {
            graspLabels = sessionConfig.graspLabelsOpenClose;
            graspID = sessionConfig.graspIDOpenClose;

            // hide grasp objects
            rightHandObjects.SetActive(false);
            leftHandObjects.SetActive(false);
        }
        else if (GameSettings.graspingType == GraspingType.GraspPatterns) // grasp patterns
        {
            graspLabels = sessionConfig.graspLabelsGraspPatterns;
            graspID = sessionConfig.graspIDGraspPatterns;

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
            graspLabels = sessionConfig.graspLabelsSingleFingers;
            graspID = sessionConfig.graspIDSingleFingers;

            // hide grasp objects
            rightHandObjects.SetActive(false);
            leftHandObjects.SetActive(false);
        }

        int numGraspClass = graspLabels.Length;

        // temporarly use always interleaved trials class for keep the subject attention on the task

        if (true || GameSettings.graspingType == GraspingType.HandOpenClose)
        {
            // building a [0,..,numGraspClass] sequence for the each class type
            for (int i = 0; i < SessionControl.numTotalTrials; i++)
            {
                SessionControl.trialsClass[i] = i % numGraspClass;
                SessionControl.trialsLabels[i] = graspLabels[SessionControl.trialsClass[i]];
                SessionControl.trialsClassID[i] = graspID[SessionControl.trialsClass[i]];
            }
        }
        //else
        //{
        //    // Populate the trials vectors: repeat each class for repeatPerClass times

        //    int repeatPerClass = SessionControl.numTotalTrials / numGraspClass;
        //    int trialIndex = 0;

        //    for (int classIdx = 0; classIdx < numGraspClass; classIdx++)
        //    {
        //        for (int rep = 0; rep < repeatPerClass; rep++)
        //        {
        //            if (trialIndex >= SessionControl.numTotalTrials)
        //                break;

        //            SessionControl.trialsClass[trialIndex] = classIdx;
        //            SessionControl.trialsLabels[trialIndex] = graspLabels[classIdx];
        //            SessionControl.trialsClassID[trialIndex] = graspID[classIdx];
        //            trialIndex++;
        //        }
        //    }
        //}  
    }

    // Update is called once per frame
    void Update()
    {
    }

    IEnumerator TrialsExecutor()
    {
        float intervalSeconds = sessionConfig.trialIntervalDuration / 1000;

        // Wait before starting the trials
        yield return new WaitForSeconds(sessionConfig.trialsStartDelay / 1000);

        // Loop through the trials
        for (int i = SessionControl.trlProgression; i < SessionControl.numTotalTrials; i++)
        {
            if (SessionControl.isRunning)
            {
                Debug.Log("Trial start");
                RegisterEvent("trial_start");

                yield return StartCoroutine(TrialAnimation());

                RegisterEvent("trial_end");
                Debug.Log("Trial finished");

                if (i == SessionControl.numTotalTrials - 1)
                {
                    yield return new WaitForSeconds(1.5f);

                    RegisterEvent("session_end");
                    Debug.Log("Session finished");

                    // End of session
                    guiManager.SetGUIState(GUIManager.GUIFeedbackState.EndSession);

                    rightHand.SetActive(false);
                    leftHand.SetActive(false);
                }
                else
                {
                    yield return new WaitForSeconds(intervalSeconds);
                }
            }
            else
            {
                RegisterEvent("session_stop");
                break;
            }
        }
    }

    IEnumerator TrialAnimation()
    {
        // Get the current trial informations
        string graspName = SessionControl.trialsLabels[SessionControl.trlProgression];
        int graspID = SessionControl.trialsClassID[SessionControl.trlProgression];

        SessionControl.trlProgression++;

        // Update the trials label
        UpdateTrialsLabel();

        // Show the grasp object in the hand if the grasping type is grasp patterns
        if (GameSettings.graspingType == GraspingType.GraspPatterns)
        {
            ShowGraspObject(graspName);
        }

        // Show the GUI instruction for the grasp
        guiManager.SetGUIInstructions(graspName);

        yield return new WaitForSeconds(sessionConfig.cueGraspStartInterval / 1000f);

        // Show the grasp start cue
        guiManager.SetGUIState(GUIManager.GUIFeedbackState.Start);

        // Start the grasp animation
        Debug.Log($"Grasp start - graspID: {graspID}");
        RegisterEvent("grasp_start", graspID);

        yield return handController.StartGrasp(graspName);

        RegisterEvent("grasp_hold_start");
        Debug.Log("hold start");

        yield return new WaitForSeconds(sessionConfig.holdDuration / 1000f);

        // Hide the grasp start cue
        guiManager.SetGUIState(GUIManager.GUIFeedbackState.Empty);

        Debug.Log("hold end");
        RegisterEvent("grasp_hold_end");

        yield return handController.ReleaseGrasp();

        RegisterEvent("grasp_released");
        Debug.Log("Grasp released");

        // Hide the GUI instruction for the grasp
        guiManager.SetGUIInstructions(GUIManager.GUIFeedbackInstructions.Empty);

        // Hide the grasp object for grasp patterns
        if (GameSettings.graspingType == GraspingType.GraspPatterns)
        {
            HideGraspObjects();
        }
    }

    public void OnBtnPlayClick()
    {
        // GUI updates
        btnPlay.interactable = false;
        btnStop.interactable = true;

        // Set the session as running
        SessionControl.isRunning = true;

        RegisterEvent("session_start");

        // Start the trials executor coroutine
        StartCoroutine(TrialsExecutor());
    }

    public void OnBtnStopClick()
    {
        // Stop the session
        SessionControl.isRunning = false;

        // GUI updates
        btnPlay.interactable = true;
        btnStop.interactable = false;
    }

    public void OnBtnExitClick()
    {
        RegisterEvent("session_exit");

        // Exit the application
        Application.Quit();
        Debug.Log("Exit button clicked");
    }

    private void UpdateTrialsLabel()
    {
        lblTrialsCount.text = $"Trials: {SessionControl.trlProgression}/{SessionControl.numTotalTrials}";
    }

    void RegisterEvent(string eventVal, int? eventID = null)
    {
        TcpServerManager.Instance.SendMessageToClient(eventVal, eventID);
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
