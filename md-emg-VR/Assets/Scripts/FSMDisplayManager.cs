using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System;
using System.Collections;

/// <summary>
/// Manages the FSM state display for functional tests (BBT, peg test, etc.)
/// Shows current FSM state, grasp lock indicator, and BBT scoring.
/// </summary>
public class FSMDisplayManager : MonoBehaviour
{
    public static FSMDisplayManager Instance { get; private set; }

    [Header("FSM State Display")]
    [SerializeField] private GameObject fsmDisplayPanel;
    [SerializeField] private TextMeshProUGUI stateText;
    [SerializeField] private Image stateIndicator;
    [SerializeField] private Image lockIndicator;
    [SerializeField] private TextMeshProUGUI lockTimerText;

    [Header("BBT Scoring Display")]
    [SerializeField] private GameObject bbtScoringPanel;
    [SerializeField] private TextMeshProUGUI blockCountText;
    [SerializeField] private TextMeshProUGUI sessionTimerText;
    [SerializeField] private TextMeshProUGUI graspCountText;

    [Header("State Colors")]
    [SerializeField] private Color idleColor = new Color(0.3f, 0.7f, 0.3f);      // Green
    [SerializeField] private Color closingColor = new Color(0.9f, 0.6f, 0.2f);   // Orange
    [SerializeField] private Color lockedColor = new Color(0.2f, 0.5f, 0.9f);    // Blue
    [SerializeField] private Color openingColor = new Color(0.7f, 0.7f, 0.2f);   // Yellow
    [SerializeField] private Color emergencyColor = new Color(0.9f, 0.2f, 0.2f); // Red

    [Header("Lock Indicator Settings")]
    [SerializeField] private Color lockActiveColor = new Color(0.2f, 0.5f, 0.9f, 1f);
    [SerializeField] private Color lockInactiveColor = new Color(0.5f, 0.5f, 0.5f, 0.3f);
    [SerializeField] private float lockPulseSpeed = 2f;

    // Internal state
    private FSMState currentState = FSMState.IDLE;
    private bool isLocked = false;
    private float lockTime = 0f;
    private int blockCount = 0;
    private int graspCount = 0;
    private float sessionStartTime = 0f;
    private bool sessionActive = false;
    private Coroutine lockPulseCoroutine;

    public enum FSMState
    {
        IDLE,
        CLOSING,
        LOCKED_GRASP,
        OPENING,
        EMERGENCY_STOP
    }

    void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }
        Instance = this;
    }

    void Start()
    {
        // Subscribe to TCP events
        if (TcpServerManager.Instance != null)
        {
            TcpServerManager.Instance.OnMessageReceived += HandleTCPMessage;
        }

        // Initialize display
        UpdateStateDisplay();
        UpdateLockIndicator();
        UpdateBBTDisplay();

        // Hide panels by default (show when FSM mode is active)
        if (fsmDisplayPanel != null) fsmDisplayPanel.SetActive(false);
        if (bbtScoringPanel != null) bbtScoringPanel.SetActive(false);
    }

    void Update()
    {
        // Update session timer if active
        if (sessionActive && sessionTimerText != null)
        {
            float elapsed = Time.time - sessionStartTime;
            sessionTimerText.text = FormatTime(elapsed);
        }
    }

    void OnDestroy()
    {
        if (TcpServerManager.Instance != null)
        {
            TcpServerManager.Instance.OnMessageReceived -= HandleTCPMessage;
        }
    }

    /// <summary>
    /// Handle incoming TCP messages for FSM state updates.
    /// </summary>
    private void HandleTCPMessage(TCPEvent eventData)
    {
        if (eventData == null) return;

        switch (eventData.eventName)
        {
            case "fsm_state":
                HandleFSMStateUpdate(eventData);
                break;
            case "fsm_start":
                StartFSMSession();
                break;
            case "fsm_stop":
                StopFSMSession();
                break;
            case "bbt_block_count":
                UpdateBlockCount(eventData.eventID);
                break;
            case "bbt_grasp_complete":
                IncrementGraspCount();
                break;
            case "bbt_reset":
                ResetBBTScore();
                break;
        }
    }

    /// <summary>
    /// Handle FSM state update from Python.
    /// </summary>
    private void HandleFSMStateUpdate(TCPEvent eventData)
    {
        // eventID encodes state: 0=IDLE, 1=CLOSING, 2=LOCKED_GRASP, 3=OPENING, 4=EMERGENCY
        FSMState newState = (FSMState)Mathf.Clamp(eventData.eventID, 0, 4);

        if (newState != currentState)
        {
            currentState = newState;
            UpdateStateDisplay();

            // Handle lock state
            if (currentState == FSMState.LOCKED_GRASP)
            {
                SetLocked(true);
            }
            else if (isLocked)
            {
                SetLocked(false);
            }
        }
    }

    /// <summary>
    /// Update the FSM state visual display.
    /// </summary>
    private void UpdateStateDisplay()
    {
        if (stateText != null)
        {
            stateText.text = GetStateDisplayName(currentState);
        }

        if (stateIndicator != null)
        {
            stateIndicator.color = GetStateColor(currentState);
        }
    }

    /// <summary>
    /// Get display-friendly name for state.
    /// </summary>
    private string GetStateDisplayName(FSMState state)
    {
        return state switch
        {
            FSMState.IDLE => "IDLE",
            FSMState.CLOSING => "CLOSING",
            FSMState.LOCKED_GRASP => "LOCKED",
            FSMState.OPENING => "OPENING",
            FSMState.EMERGENCY_STOP => "STOP!",
            _ => "UNKNOWN"
        };
    }

    /// <summary>
    /// Get color for state indicator.
    /// </summary>
    private Color GetStateColor(FSMState state)
    {
        return state switch
        {
            FSMState.IDLE => idleColor,
            FSMState.CLOSING => closingColor,
            FSMState.LOCKED_GRASP => lockedColor,
            FSMState.OPENING => openingColor,
            FSMState.EMERGENCY_STOP => emergencyColor,
            _ => Color.gray
        };
    }

    /// <summary>
    /// Set the grasp lock state and update indicator.
    /// </summary>
    public void SetLocked(bool locked)
    {
        isLocked = locked;

        if (locked)
        {
            lockTime = Time.time;
            if (lockPulseCoroutine != null)
            {
                StopCoroutine(lockPulseCoroutine);
            }
            lockPulseCoroutine = StartCoroutine(PulseLockIndicator());
        }
        else
        {
            if (lockPulseCoroutine != null)
            {
                StopCoroutine(lockPulseCoroutine);
                lockPulseCoroutine = null;
            }
        }

        UpdateLockIndicator();
    }

    /// <summary>
    /// Update the lock indicator visual.
    /// </summary>
    private void UpdateLockIndicator()
    {
        if (lockIndicator != null)
        {
            lockIndicator.color = isLocked ? lockActiveColor : lockInactiveColor;
            lockIndicator.gameObject.SetActive(true);
        }

        if (lockTimerText != null)
        {
            if (isLocked)
            {
                float elapsed = Time.time - lockTime;
                lockTimerText.text = $"{elapsed:F1}s";
                lockTimerText.gameObject.SetActive(true);
            }
            else
            {
                lockTimerText.gameObject.SetActive(false);
            }
        }
    }

    /// <summary>
    /// Pulse animation for lock indicator when grasp is locked.
    /// </summary>
    private IEnumerator PulseLockIndicator()
    {
        while (isLocked)
        {
            if (lockIndicator != null)
            {
                float pulse = (Mathf.Sin(Time.time * lockPulseSpeed * Mathf.PI) + 1f) * 0.5f;
                Color c = lockActiveColor;
                c.a = 0.6f + pulse * 0.4f;
                lockIndicator.color = c;
            }

            // Update lock timer
            if (lockTimerText != null)
            {
                float elapsed = Time.time - lockTime;
                lockTimerText.text = $"{elapsed:F1}s";
            }

            yield return null;
        }
    }

    /// <summary>
    /// Start FSM/BBT session - show UI panels.
    /// </summary>
    public void StartFSMSession()
    {
        sessionActive = true;
        sessionStartTime = Time.time;

        if (fsmDisplayPanel != null) fsmDisplayPanel.SetActive(true);
        if (bbtScoringPanel != null) bbtScoringPanel.SetActive(true);

        ResetBBTScore();
        Debug.Log("FSM Session Started");
    }

    /// <summary>
    /// Stop FSM/BBT session - hide UI panels.
    /// </summary>
    public void StopFSMSession()
    {
        sessionActive = false;
        SetLocked(false);

        Debug.Log($"FSM Session Ended - Blocks: {blockCount}, Grasps: {graspCount}");
    }

    /// <summary>
    /// Update the block count display.
    /// </summary>
    public void UpdateBlockCount(int count)
    {
        blockCount = count;
        UpdateBBTDisplay();
    }

    /// <summary>
    /// Increment block count by 1.
    /// </summary>
    public void IncrementBlockCount()
    {
        blockCount++;
        UpdateBBTDisplay();
    }

    /// <summary>
    /// Increment grasp count (successful grasp-release cycles).
    /// </summary>
    public void IncrementGraspCount()
    {
        graspCount++;
        UpdateBBTDisplay();
    }

    /// <summary>
    /// Reset BBT scoring.
    /// </summary>
    public void ResetBBTScore()
    {
        blockCount = 0;
        graspCount = 0;
        sessionStartTime = Time.time;
        UpdateBBTDisplay();
    }

    /// <summary>
    /// Update BBT scoring display.
    /// </summary>
    private void UpdateBBTDisplay()
    {
        if (blockCountText != null)
        {
            blockCountText.text = blockCount.ToString();
        }

        if (graspCountText != null)
        {
            graspCountText.text = graspCount.ToString();
        }
    }

    /// <summary>
    /// Format time as MM:SS.
    /// </summary>
    private string FormatTime(float seconds)
    {
        int mins = Mathf.FloorToInt(seconds / 60f);
        int secs = Mathf.FloorToInt(seconds % 60f);
        return $"{mins:D2}:{secs:D2}";
    }

    /// <summary>
    /// Get current FSM state (for external scripts).
    /// </summary>
    public FSMState GetCurrentState()
    {
        return currentState;
    }

    /// <summary>
    /// Check if grasp is currently locked.
    /// </summary>
    public bool IsGraspLocked()
    {
        return isLocked;
    }

    /// <summary>
    /// Get current block count.
    /// </summary>
    public int GetBlockCount()
    {
        return blockCount;
    }

    /// <summary>
    /// Get current grasp count.
    /// </summary>
    public int GetGraspCount()
    {
        return graspCount;
    }
}
