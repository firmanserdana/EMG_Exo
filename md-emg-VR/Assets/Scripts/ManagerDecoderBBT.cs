using System;
using System.Collections.Generic;
using System.IO;
using TMPro;
using UnityEngine;

/// <summary>
/// Decoder benchmark monitor for BBT sessions.
///
/// Intended usage:
/// - Attach this component in the decoder-BBT scene alongside ManagerBBT.
/// - It tracks local BBT phase events and decoder predictions received via TCP.
/// - Final score reports moved/dropped blocks and phase-level decoder correctness in 60s.
/// </summary>
public class ManagerDecoderBBT : MonoBehaviour
{
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void EnsureDecoderManagerExists()
    {
        if (GameSettings.acquisitionType != AcquisitionType.DecoderBBT)
        {
            return;
        }

        ManagerDecoderBBT existing = FindObjectOfType<ManagerDecoderBBT>();
        if (existing == null)
        {
            GameObject go = new GameObject("ManagerDecoderBBT_Auto");
            go.AddComponent<ManagerDecoderBBT>();
        }
    }

    [Header("Optional HUD")]
    public TMP_Text lblBlocksMoved;
    public TMP_Text lblBlocksDropped;
    public TMP_Text lblPhaseAccuracy;
    public TMP_Text lblTimer;

    private DecoderBBTConfig cfg;

    private bool sessionRunning;
    private float sessionStartTime;

    private int blocksMoved;
    private int blocksDropped;

    private bool currentPickupPassed;
    private bool currentPlacePassed;

    private int pickupPredictions;
    private int pickupCorrect;
    private int placePredictions;
    private int placeCorrect;
    private int movePredictions;
    private int moveCorrect;

    private enum DecoderPhase
    {
        Idle,
        Pickup,
        Move,
        Place,
    }

    private DecoderPhase currentPhase = DecoderPhase.Idle;

    void Start()
    {
        LoadConfig();
        ResetState();

        ManagerBBT.OnLocalEventRegistered += HandleBbtEvent;

        if (TcpServerManager.Instance != null)
        {
            TcpServerManager.Instance.OnMessageReceived += HandleTcpEvent;
        }
    }

    void OnDestroy()
    {
        ManagerBBT.OnLocalEventRegistered -= HandleBbtEvent;

        if (TcpServerManager.Instance != null)
        {
            TcpServerManager.Instance.OnMessageReceived -= HandleTcpEvent;
        }
    }

    void Update()
    {
        if (!sessionRunning)
        {
            return;
        }

        float elapsed = Time.time - sessionStartTime;
        float remaining = Mathf.Max(0f, cfg.sessionDurationSeconds - elapsed);

        if (lblTimer != null)
        {
            int mins = Mathf.FloorToInt(remaining / 60f);
            int secs = Mathf.FloorToInt(remaining % 60f);
            lblTimer.text = $"Decoder-BBT: {mins:D2}:{secs:D2}";
        }

        if (elapsed >= cfg.sessionDurationSeconds)
        {
            CompleteSession("time_limit");
        }

        UpdateHud();
    }

    private void LoadConfig()
    {
        string path = Path.Combine(Application.dataPath, "Config", "DecoderBBTConfig.json");
        if (File.Exists(path))
        {
            cfg = JsonUtility.FromJson<DecoderBBTConfig>(File.ReadAllText(path));
        }
        else
        {
            cfg = new DecoderBBTConfig
            {
                sessionDurationSeconds = 60,
                expectedCloseID = 1,
                expectedOpenID = 0,
                minPredictionsPerPhase = 1,
                requireBothPhases = true
            };

            Debug.LogWarning("DecoderBBTConfig.json not found. Using defaults.");
        }
    }

    private void ResetState()
    {
        sessionRunning = false;
        sessionStartTime = 0f;
        blocksMoved = 0;
        blocksDropped = 0;

        currentPickupPassed = false;
        currentPlacePassed = false;

        pickupPredictions = 0;
        pickupCorrect = 0;
        placePredictions = 0;
        placeCorrect = 0;
        movePredictions = 0;
        moveCorrect = 0;

        currentPhase = DecoderPhase.Idle;
    }

    private void HandleBbtEvent(string eventName, int? eventID)
    {
        if (eventName == "session_start")
        {
            ResetState();
            sessionRunning = true;
            sessionStartTime = Time.time;
            return;
        }

        if (!sessionRunning)
        {
            return;
        }

        switch (eventName)
        {
            case "session_end":
            case "session_stop":
                CompleteSession(eventName);
                break;

            case "grasp_start":
                if (eventID.HasValue && eventID.Value == cfg.expectedCloseID)
                {
                    currentPhase = DecoderPhase.Pickup;
                }
                else if (eventID.HasValue && eventID.Value == cfg.expectedOpenID)
                {
                    currentPhase = DecoderPhase.Place;
                }
                break;

            case "grasp_hold_start":
                if (currentPhase == DecoderPhase.Pickup)
                {
                    currentPhase = DecoderPhase.Move;
                }
                break;

            case "grasp_released":
                RegisterBlockResult();
                currentPhase = DecoderPhase.Idle;
                currentPickupPassed = false;
                currentPlacePassed = false;
                break;
        }
    }

    private void HandleTcpEvent(TCPEvent eventData)
    {
        if (!sessionRunning || eventData == null)
        {
            return;
        }

        if (eventData.eventName != "grasp_decoded")
        {
            return;
        }

        int predicted = eventData.eventID;

        if (currentPhase == DecoderPhase.Pickup)
        {
            pickupPredictions++;
            if (predicted == cfg.expectedCloseID)
            {
                pickupCorrect++;
                currentPickupPassed = true;
            }
        }
        else if (currentPhase == DecoderPhase.Move)
        {
            movePredictions++;
            if (predicted == cfg.expectedCloseID)
            {
                moveCorrect++;
            }
        }
        else if (currentPhase == DecoderPhase.Place)
        {
            placePredictions++;
            if (predicted == cfg.expectedOpenID)
            {
                placeCorrect++;
                currentPlacePassed = true;
            }
        }
    }

    private void RegisterBlockResult()
    {
        bool pickupValid = currentPickupPassed || pickupPredictions < cfg.minPredictionsPerPhase;
        bool placeValid = currentPlacePassed || placePredictions < cfg.minPredictionsPerPhase;

        bool moved = cfg.requireBothPhases ? (pickupValid && placeValid) : (pickupValid || placeValid);

        if (moved)
        {
            blocksMoved++;
        }
        else
        {
            blocksDropped++;
        }
    }

    private void CompleteSession(string reason)
    {
        if (!sessionRunning)
        {
            return;
        }

        sessionRunning = false;

        float pickupAcc = pickupPredictions > 0 ? (float)pickupCorrect / pickupPredictions : 0f;
        float moveAcc = movePredictions > 0 ? (float)moveCorrect / movePredictions : 0f;
        float placeAcc = placePredictions > 0 ? (float)placeCorrect / placePredictions : 0f;

        Debug.Log($"[DecoderBBT] Session complete ({reason}) | moved={blocksMoved}, dropped={blocksDropped}, pickup_acc={pickupAcc:F3}, move_acc={moveAcc:F3}, place_acc={placeAcc:F3}");

        PersistResult(reason, pickupAcc, moveAcc, placeAcc);
        UpdateHud();
    }

    private void PersistResult(string reason, float pickupAcc, float moveAcc, float placeAcc)
    {
        var payload = new DecoderBBTResult
        {
            reason = reason,
            timestamp = DateTime.UtcNow.ToString("o"),
            blocksMoved = blocksMoved,
            blocksDropped = blocksDropped,
            pickupPredictions = pickupPredictions,
            pickupCorrect = pickupCorrect,
            movePredictions = movePredictions,
            moveCorrect = moveCorrect,
            placePredictions = placePredictions,
            placeCorrect = placeCorrect,
            pickupAccuracy = pickupAcc,
            moveAccuracy = moveAcc,
            placeAccuracy = placeAcc
        };

        string folder = Path.Combine(Application.persistentDataPath, "decoder_bbt");
        Directory.CreateDirectory(folder);
        string path = Path.Combine(folder, $"decoder_bbt_{DateTime.UtcNow:yyyyMMdd_HHmmss}.json");
        File.WriteAllText(path, JsonUtility.ToJson(payload, true));
    }

    private void UpdateHud()
    {
        if (lblBlocksMoved != null)
        {
            lblBlocksMoved.text = $"Moved: {blocksMoved}";
        }

        if (lblBlocksDropped != null)
        {
            lblBlocksDropped.text = $"Dropped: {blocksDropped}";
        }

        if (lblPhaseAccuracy != null)
        {
            float pickupAcc = pickupPredictions > 0 ? (float)pickupCorrect / pickupPredictions : 0f;
            float placeAcc = placePredictions > 0 ? (float)placeCorrect / placePredictions : 0f;
            lblPhaseAccuracy.text = $"Pickup: {pickupAcc:P0} | Place: {placeAcc:P0}";
        }
    }

    [Serializable]
    private class DecoderBBTResult
    {
        public string reason;
        public string timestamp;
        public int blocksMoved;
        public int blocksDropped;
        public int pickupPredictions;
        public int pickupCorrect;
        public int movePredictions;
        public int moveCorrect;
        public int placePredictions;
        public int placeCorrect;
        public float pickupAccuracy;
        public float moveAccuracy;
        public float placeAccuracy;
    }
}
