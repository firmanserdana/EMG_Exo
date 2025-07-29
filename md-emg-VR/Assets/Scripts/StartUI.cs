using System.IO;
using TMPro;
using UnityEngine;
using UnityEngine.SceneManagement;

public enum AcquisitionType
{
    OpenLoop,
    ClosedLoop,
    MVC,
    DecodingFeedback
}

public enum GraspingType
{
    HandOpenClose,
    GraspPatterns,
    SingleFingers
}

public enum DominantHand
{
    right,
    left
}

public static class GameSettings
{
    // Both open-loop and closed-loop variables
    public static AcquisitionType acquisitionType;
    public static GraspingType graspingType;
    public static DominantHand dominantHand;
    public static int numTrialsPerGrasp = 10;

    // Closed-loop variables
    public static int trialDuration = 5; // [s] max duration of the trial
    public static float timerUpdateDelay = 0.05f; // [s] velocity of the timer update
}

public class StartUI : MonoBehaviour
{
    // Scene names
    readonly static string openLoopSceneName = "graspingOpenLoop";
    readonly static string closedLoopSceneName = "graspingClosedLoop";
    readonly static string mvcSceneName = "graspingMVC";
    readonly static string decodingFeedbackSceneName = "graspingFeedback";

    // GUI Elements
    public TMP_Dropdown acquisitionType, graspingType, dominantHand;
    public TMP_InputField numTrials;

    [Header("ClosedLoop parameters")]
    public GameObject ClosedLoopParameters;
    public TMP_InputField trialDurationInputField; // Reference to the TrialDuration input field

    // Configs
    private OpenLoopConfig openLoopSessionConfig = new();
    private ClosedLoopConfig closedLoopSessionConfig = new();
    private MVCConfig MVCSessionConfig = new();

    // Start is called before the first frame update
    void Start()
    {
        // Load configs
        string configPath = Path.Combine(Application.dataPath, "Config");

        string json = File.ReadAllText(Path.Combine(configPath, "OpenLoopConfig.json"));
        openLoopSessionConfig = JsonUtility.FromJson<OpenLoopConfig>(json);

        json = File.ReadAllText(Path.Combine(configPath, "ClosedLoopConfig.json"));
        closedLoopSessionConfig = JsonUtility.FromJson<ClosedLoopConfig>(json);

        json = File.ReadAllText(Path.Combine(configPath, "MVCConfig.json"));
        MVCSessionConfig = JsonUtility.FromJson<MVCConfig>(json);

        // Setup GUI
        ClosedLoopParameters.SetActive(false);
    }

    public void OnStartButtonClick()
    {
        int acquisitionTypeIndex = acquisitionType.value;
        int graspingTypeIndex = graspingType.value;
        int dominantHandIndex = dominantHand.value;

        // Set the game settings based on the dropdown selections
        GameSettings.acquisitionType = (AcquisitionType)acquisitionTypeIndex;
        GameSettings.graspingType = (GraspingType)graspingTypeIndex;
        GameSettings.dominantHand = (DominantHand)dominantHandIndex;
        GameSettings.numTrialsPerGrasp = int.Parse(numTrials.text);

        int numClass = 0;

        if (GameSettings.graspingType == GraspingType.HandOpenClose)
        {
            if (GameSettings.acquisitionType == AcquisitionType.OpenLoop)
            {
                numClass = openLoopSessionConfig.graspIDOpenClose.Length;
            }
            else
            {
                numClass = closedLoopSessionConfig.graspIDOpenClose.Length;
            }

            SessionControl.numTotalTrials = GameSettings.numTrialsPerGrasp * numClass;
        }
        else if (GameSettings.graspingType == GraspingType.SingleFingers)
        {
            if (GameSettings.acquisitionType == AcquisitionType.OpenLoop)
            {
                numClass = openLoopSessionConfig.graspIDSingleFingers.Length;
            }
            else
            {
                numClass = closedLoopSessionConfig.graspIDSingleFingers.Length;
            }

            SessionControl.numTotalTrials = GameSettings.numTrialsPerGrasp * numClass;
        }
        else if (GameSettings.graspingType == GraspingType.GraspPatterns)
        {
            if (GameSettings.acquisitionType == AcquisitionType.OpenLoop)
            {
                numClass = openLoopSessionConfig.graspIDGraspPatterns.Length;
            }
            else
            {
                numClass = closedLoopSessionConfig.graspIDGraspPatterns.Length;
            }

            SessionControl.numTotalTrials = GameSettings.numTrialsPerGrasp * numClass;
        }

        if (GameSettings.acquisitionType == AcquisitionType.OpenLoop)
        {
            SceneManager.LoadScene(openLoopSceneName);
        }
        else if (GameSettings.acquisitionType == AcquisitionType.ClosedLoop)
        {
            // Extract value from the TrialDuration input field
            if (trialDurationInputField != null && int.TryParse(trialDurationInputField.text, out int trialDurationValue))
            {
                GameSettings.trialDuration = trialDurationValue;
            }
            else
            {
                Debug.LogWarning("Invalid or missing TrialDuration input. Using default value.");
            }

            SceneManager.LoadScene(closedLoopSceneName);
        }
        else if (GameSettings.acquisitionType == AcquisitionType.MVC)
        {
            SceneManager.LoadScene(mvcSceneName);
        }
        else if (GameSettings.acquisitionType == AcquisitionType.DecodingFeedback)
        {
            SceneManager.LoadScene(decodingFeedbackSceneName);
        }
    }

    public void OnAcquisitionTypeChange(int index)
    {
        int acquisitionTypeIndex = acquisitionType.value;
        if ((AcquisitionType)acquisitionTypeIndex == AcquisitionType.ClosedLoop)
        {
            ClosedLoopParameters.SetActive(true);
        }
        else
        {
            ClosedLoopParameters.SetActive(false);
        }
    }
}
