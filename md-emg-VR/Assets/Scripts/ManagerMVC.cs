using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using TMPro;
using UnityEngine;

public class ManagerMVC : MonoBehaviour
{
    public static ManagerMVC Instance { get; private set; }

    // Other scripts
    private HandController handController;
    private GUIManager guiManager;

    // Hand 
    [Header("Hands")]
    public GameObject leftHand;
    public GameObject rightHand;

    // GUI
    [Header("GUI")]
    public UnityEngine.UI.Button btnPlay;
    public UnityEngine.UI.Button btnStop;
    public UnityEngine.UI.Button btnExit;

    // Configs
    private MVCConfig sessionConfig = new();

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

        // Load configs
        string configPath = Path.Combine(Application.dataPath, "config");

        string json = File.ReadAllText(Path.Combine(configPath, "MVCConfig.json"));
        sessionConfig = JsonUtility.FromJson<MVCConfig>(json);

        // Initialize the session control params
        SessionControl.timerElapsedTime = sessionConfig.MVCDuration;
        GameSettings.trialDuration = sessionConfig.MVCDuration; // Convert milliseconds to seconds
    }

    // Update is called once per frame
    void Update()
    {
        // check if trial timer has expired
        if (SessionControl.isRunning && SessionControl.timerElapsedTime <= 0)
        {
            SessionControl.isRunning = false;
            RegisterEvent("mvc_end");

            // Show the grasp failed GUI
            guiManager.SetGUIState(GUIManager.GUIFeedbackState.Empty);

            // Release the grasp
            handController.ReleaseGrasp();

            Debug.Log("Ending MVC grasp");
        }
    }
    
    IEnumerator MVCExecutor()
    {
        // Reset the GUI instruction for the grasp and reset the GUI state
        guiManager.SetGUIInstructions(GUIManager.GUIFeedbackInstructions.Empty);
        guiManager.SetGUIState(GUIManager.GUIFeedbackState.Empty);

        // Wait before starting the MVC session
        yield return new WaitForSeconds(sessionConfig.trialsStartDelay / 1000);

        // Reset the GUI timer
        guiManager.resetTimer();

        // Hide feedack state elements
        guiManager.SetGUIState(GUIManager.GUIFeedbackState.Empty);

        if (SessionControl.isRunning)
        {
            Debug.Log("Starting MVC grasp");
            // Show the start cue
            guiManager.SetGUIState(GUIManager.GUIFeedbackState.Start);

            yield return handController.StartGrasp("HandClose");

            // Start the trial timer
            guiManager.startTimer();
            Invoke("UpdateTimerProgress", GameSettings.timerUpdateDelay); // start the experiment timer

            RegisterEvent("mvc_start");
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

        // Start the trials start executor coroutine
        StartCoroutine(MVCExecutor());

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

    void RegisterEvent(string eventVal, int? eventID=null)
    {
        TcpServerManager.Instance.SendMessageToClient(eventVal, eventID);
    }

    private void UpdateTimerProgress()
    {
        if (SessionControl.isRunning)
        {
            SessionControl.timerElapsedTime -= GameSettings.timerUpdateDelay;
            Invoke("UpdateTimerProgress", GameSettings.timerUpdateDelay);
        }
    }
}
