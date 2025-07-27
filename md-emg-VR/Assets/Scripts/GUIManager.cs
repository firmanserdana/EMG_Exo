using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using System;

public class GUIManager : MonoBehaviour
{ 
    [SerializeField] private Image TimeProgressFill;

    // Define Feedback GUI states
    public enum GUIFeedbackInstructions { 
        Empty, HandOpen, HandClose, 
        HookGrasp, LateralGrasp, IndexPointing,
        ThumbFlexion, IndexFlexion, MRPFlexion
    }
    public enum GUIFeedbackState { Empty, Start, Success, Failed, TimeExpired, EndSession }

    private Dictionary<GUIFeedbackInstructions, Sprite> GUIInstructionsSpriteDict;
    private Dictionary<GUIFeedbackState, Sprite> GUIStateSpriteDict;

    // GUI main elements
    [Header("GUI main elements")]
    [SerializeField] private Image GUIInstructionImage;
    [SerializeField] private Image GUIStateImage;

    // Instructions GUI sprites
    [Header("GUI Instructions")]
    [SerializeField] private Sprite UiInstructionEmpty;
    [SerializeField] private Sprite UiInstructionHandOpen;
    [SerializeField] private Sprite UiInstructionHandClose;
    [SerializeField] private Sprite UiInstructionHookGrasp;
    [SerializeField] private Sprite UiInstructionLateralGrasp;
    [SerializeField] private Sprite UiInstructionIndexPointing;
    [SerializeField] private Sprite UiInstructionThumbFlexion;
    [SerializeField] private Sprite UiInstructionIndexFlexion;
    [SerializeField] private Sprite UiInstructionMRPFlexion;

    [Header("GUI State")]
    [SerializeField] private Sprite UiStateEmpty;
    [SerializeField] private Sprite UiStateStart;
    [SerializeField] private Sprite UiStateSuccess;
    [SerializeField] private Sprite UiStateFailed;
    [SerializeField] private Sprite UiStateTimeExpired;
    [SerializeField] private Sprite UiStateEndSession;

    // Timer control variables
    bool timerActive = false;
    float elapsedTime = 0;

    void Awake()
    {
        GUIInstructionsSpriteDict = new Dictionary<GUIFeedbackInstructions, Sprite>
        {
            { GUIFeedbackInstructions.Empty, UiInstructionEmpty },
            { GUIFeedbackInstructions.HandOpen, UiInstructionHandOpen },
            { GUIFeedbackInstructions.HandClose, UiInstructionHandClose },
            { GUIFeedbackInstructions.HookGrasp, UiInstructionHookGrasp },
            { GUIFeedbackInstructions.LateralGrasp, UiInstructionLateralGrasp },
            { GUIFeedbackInstructions.IndexPointing, UiInstructionIndexPointing },
            { GUIFeedbackInstructions.ThumbFlexion, UiInstructionThumbFlexion },
            { GUIFeedbackInstructions.IndexFlexion, UiInstructionIndexFlexion },
            { GUIFeedbackInstructions.MRPFlexion, UiInstructionMRPFlexion }
        };

        GUIStateSpriteDict = new Dictionary<GUIFeedbackState, Sprite>
        {
            { GUIFeedbackState.Empty, UiStateEmpty },
            { GUIFeedbackState.Start, UiStateStart },
            { GUIFeedbackState.Success, UiStateSuccess },
            { GUIFeedbackState.Failed, UiStateFailed },
            { GUIFeedbackState.TimeExpired, UiStateTimeExpired },
            { GUIFeedbackState.EndSession, UiStateEndSession }
        };
    }

    // Start the ticking on the GUI timer feedback
    public void startTimer()
    {
        timerActive = true;
        Invoke("UpdateTimeProgress", GameSettings.timerUpdateDelay);
    }

    // Stop the ticking on the GUI timer feedback
    public void stopTimer()
    {
        timerActive = false;
    }

    // reset the GUI timer
    public void resetTimer()
    {
        elapsedTime = 0;
        TimeProgressFill.fillAmount = 1;
        timerActive = false;
    }

    // Updating the timer bar
    private void UpdateTimeProgress()
    {
        if (timerActive)
        {
            elapsedTime = elapsedTime + GameSettings.timerUpdateDelay;
            TimeProgressFill.fillAmount = 1 - (elapsedTime / GameSettings.trialDuration);
            Invoke("UpdateTimeProgress", GameSettings.timerUpdateDelay);
        }
    }

    public void SetGUIInstructions(GUIFeedbackInstructions instruction)
    {
        if (GUIInstructionsSpriteDict.TryGetValue(instruction, out Sprite sprite))
        {
            GUIInstructionImage.sprite = sprite;
        }
        else
        {
            Debug.LogError("Instruction UI not found: " + instruction);
        }
    }
    public void SetGUIInstructions(string graspName)
    {
        if (Enum.TryParse<GUIFeedbackInstructions>(graspName, out var state))
        {
            SetGUIInstructions(state);
        }
        else
        {
            Debug.LogError($"Invalid GUI Instructions grasp name: {graspName}");
        }
    }

    public void SetGUIState(GUIFeedbackState state)
    {
        if (GUIStateSpriteDict.TryGetValue(state, out Sprite sprite))
        {
            GUIStateImage.sprite = sprite;
        }
        else
        {
            Debug.LogError("State UI not found: " + state);
        }
    }
}
