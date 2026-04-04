using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// Decoder-driven BBT benchmark. Runs its own session loop — ManagerBBT's
/// RunSession() is skipped when AcquisitionType == DecoderBBT.
///
/// Rules (matching a real Box-and-Block Test with decoder control):
///   1. Hand stays still at source until decoder predicts CLOSE → hand closes (pickup)
///   2. Hand automatically moves to target. If decoder predicts OPEN during
///      the move → block drops mid-air, counted as a DROP.
///   3. After arriving at target, hand waits for decoder OPEN → hand opens (place).
///      If timeout → block is lost, counted as TIMEOUT.
///   4. Block successfully placed = score +1.
///   5. Session lasts 60 seconds. Score = blocks successfully placed.
///
/// Source blocks are static decoration (never removed).
/// Target side gains a block on each success.
/// </summary>
public class ManagerDecoderBBT : MonoBehaviour
{
    private DecoderBBTConfig cfg;
    private ManagerBBT bbt;

    // Session state
    private bool sessionRunning;
    private float sessionStartTime;
    private Coroutine sessionCoroutine;

    // Scoring
    private int blocksSucceeded;
    private int blocksDroppedDuringMove;
    private int blocksTimedOut;
    private int totalAttempts;

    // Target side placed blocks
    private List<GameObject> placedBlocks = new List<GameObject>();

    // Currently carried block (attached to hand)
    private GameObject carriedBlock;

    // Decoder flags — set by HandleTcpEvent, polled by session loop
    private bool decodingActive;
    private bool closeReceived;
    private bool openReceived;

    private string sessionId;
    private string sessionOutputDirectory;
    private string sessionFileStem;
    private string decoderResultsLogPath;
    private int decoderEventsLogged;

    private enum Phase
    {
        Idle,
        WaitingForClose,
        Closing,
        Moving,
        WaitingForOpen,
        Opening,
        Returning
    }

    private Phase currentPhase = Phase.Idle;

    private static readonly Color[] BlockColors = {
        new Color(0.9f, 0.2f, 0.2f),
        new Color(0.2f, 0.5f, 0.9f),
        new Color(0.2f, 0.8f, 0.3f),
        new Color(0.9f, 0.8f, 0.2f),
        new Color(0.7f, 0.3f, 0.8f)
    };

    // ================================================================
    //  LIFECYCLE
    // ================================================================

    void Start()
    {
        LoadConfig();
        bbt = ManagerBBT.Instance;

        ManagerBBT.OnLocalEventRegistered += HandleBbtEvent;

        if (TcpServerManager.Instance != null)
            TcpServerManager.Instance.OnMessageReceived += HandleTcpEvent;

        Debug.Log($"[DecoderBBT] Initialized — " +
                  $"timeout={cfg.phaseTimeoutSeconds}s, duration={cfg.sessionDurationSeconds}s");
    }

    void OnDestroy()
    {
        ManagerBBT.OnLocalEventRegistered -= HandleBbtEvent;

        if (TcpServerManager.Instance != null)
            TcpServerManager.Instance.OnMessageReceived -= HandleTcpEvent;
    }

    void Update()
    {
        if (!sessionRunning) return;

        float elapsed = Time.time - sessionStartTime;
        float remaining = Mathf.Max(0f, cfg.sessionDurationSeconds - elapsed);

        if (bbt != null && bbt.lblTimer != null)
        {
            int mins = Mathf.FloorToInt(remaining / 60f);
            int secs = Mathf.FloorToInt(remaining % 60f);
            bbt.lblTimer.text = $"Time: {mins:D2}:{secs:D2}";
        }

        UpdateScoreDisplay();
    }

    // ================================================================
    //  CONFIG
    // ================================================================

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
                requireBothPhases = true,
                phaseTimeoutSeconds = 10f
            };
            Debug.LogWarning("[DecoderBBT] Config not found — using defaults");
        }

        if (cfg.phaseTimeoutSeconds <= 0f) cfg.phaseTimeoutSeconds = 10f;
        if (cfg.sessionDurationSeconds <= 0) cfg.sessionDurationSeconds = 60;
    }

    private void ResetState()
    {
        sessionRunning = false;
        sessionStartTime = 0f;
        sessionCoroutine = null;
        blocksSucceeded = 0;
        blocksDroppedDuringMove = 0;
        blocksTimedOut = 0;
        totalAttempts = 0;
        decodingActive = false;
        closeReceived = false;
        openReceived = false;
        currentPhase = Phase.Idle;
        sessionId = null;
        sessionOutputDirectory = null;
        sessionFileStem = null;
        decoderResultsLogPath = null;
        decoderEventsLogged = 0;

        if (carriedBlock != null) { Destroy(carriedBlock); carriedBlock = null; }
        foreach (var b in placedBlocks) { if (b != null) Destroy(b); }
        placedBlocks.Clear();
    }

    private void PrepareSessionPersistence()
    {
        sessionId = $"{DateTime.UtcNow:yyyyMMdd_HHmmss}_{UnityEngine.Random.Range(1000, 9999)}";

        string fileLabel = "decoder_bbt";
        string folder = Path.Combine(Application.persistentDataPath, "decoder_bbt");

        if (TcpServerManager.Instance != null)
        {
            if (!string.IsNullOrWhiteSpace(TcpServerManager.Instance.CurrentSessionLabel))
                fileLabel = TcpServerManager.Instance.CurrentSessionLabel;

            if (!string.IsNullOrWhiteSpace(TcpServerManager.Instance.CurrentOutputDirectory))
                folder = TcpServerManager.Instance.CurrentOutputDirectory;
        }

        Directory.CreateDirectory(folder);

        sessionOutputDirectory = folder;
        sessionFileStem = $"{SanitizeFileStem(fileLabel)}_decoder_bbt_{sessionId}";
        decoderResultsLogPath = Path.Combine(sessionOutputDirectory, $"{sessionFileStem}_decoder_results.jsonl");
        decoderEventsLogged = 0;

        Debug.Log(
            "[DecoderBBT] Session persistence ready: " +
            $"folder={sessionOutputDirectory}, stem={sessionFileStem}"
        );
    }

    private static string SanitizeFileStem(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
            return "decoder_bbt";

        foreach (char invalidChar in Path.GetInvalidFileNameChars())
            value = value.Replace(invalidChar, '_');

        return value.Replace(' ', '_');
    }

    private void AppendDecoderLog(
        string entryType,
        string detail,
        int predictedUnityEventId = -1,
        int predictedRawId = -1,
        float predictionProb = -1f,
        float predictionTimestamp = -1f)
    {
        if (string.IsNullOrWhiteSpace(decoderResultsLogPath))
            PrepareSessionPersistence();

        var entry = new DecoderBBTLogEntry
        {
            sessionId = sessionId,
            sessionLabel = TcpServerManager.Instance != null ? TcpServerManager.Instance.CurrentSessionLabel : string.Empty,
            timestamp = DateTime.UtcNow.ToString("o"),
            elapsedSeconds = Mathf.Max(0f, Time.time - sessionStartTime),
            entryType = entryType,
            detail = detail,
            phase = currentPhase.ToString(),
            predictedUnityEventId = predictedUnityEventId,
            predictedRawId = predictedRawId,
            predictionProb = predictionProb,
            predictionTimestamp = predictionTimestamp,
            blocksMovedSuccessfully = blocksSucceeded,
            blocksSucceeded = blocksSucceeded,
            blocksDropped = blocksDroppedDuringMove,
            blocksDroppedDuringMove = blocksDroppedDuringMove,
            blocksTimedOut = blocksTimedOut,
            totalAttempts = totalAttempts
        };

        try
        {
            File.AppendAllText(decoderResultsLogPath, JsonUtility.ToJson(entry) + Environment.NewLine);
            decoderEventsLogged++;
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[DecoderBBT] Failed to append decoder log: {e.Message}");
        }
    }

    // ================================================================
    //  BBT EVENT HANDLER (from ManagerBBT button clicks)
    // ================================================================

    private void HandleBbtEvent(string eventName, int? eventID)
    {
        if (eventName == "session_start")
        {
            ResetState();
            PrepareSessionPersistence();
            sessionRunning = true;
            sessionStartTime = Time.time;
            AppendDecoderLog("session_start", "decoder_bbt_started");
            sessionCoroutine = StartCoroutine(DecoderSessionLoop());
        }
        else if (eventName == "session_stop" || eventName == "session_end")
        {
            if (sessionRunning) CompleteSession(eventName);
        }
    }

    // ================================================================
    //  TCP EVENT HANDLER (decoder predictions from Python)
    // ================================================================

    /// <summary>
    /// Sets flags that the session loop polls each frame. The hand animation
    /// is triggered by the session loop — this keeps the flow deterministic.
    /// </summary>
    private void HandleTcpEvent(TCPEvent eventData)
    {
        if (!sessionRunning || !decodingActive || eventData == null) return;
        if (eventData.eventName != "grasp_decoded") return;

        int predicted = eventData.eventID;
        string decision = "ignored";

        switch (currentPhase)
        {
            case Phase.WaitingForClose:
                if (predicted == cfg.expectedCloseID)
                {
                    closeReceived = true;
                    decision = "pickup_close_detected";
                    Debug.Log("[DecoderBBT] CLOSE prediction received → pickup");
                }
                break;

            case Phase.Moving:
                if (predicted == cfg.expectedOpenID)
                {
                    openReceived = true;
                    decision = "drop_open_detected";
                    Debug.Log("[DecoderBBT] OPEN prediction during move → DROP!");
                }
                break;

            case Phase.WaitingForOpen:
                if (predicted == cfg.expectedOpenID)
                {
                    openReceived = true;
                    decision = "place_open_detected";
                    Debug.Log("[DecoderBBT] OPEN prediction received → place");
                }
                break;
        }

        AppendDecoderLog(
            "decoder_result",
            decision,
            predictedUnityEventId: predicted,
            predictedRawId: eventData.predictionRawID,
            predictionProb: eventData.predictionProb,
            predictionTimestamp: eventData.predictionTimestamp
        );
    }

    // ================================================================
    //  DECODER SESSION LOOP
    // ================================================================

    private IEnumerator DecoderSessionLoop()
    {
        HandController hc = bbt != null ? bbt.handController : null;
        GameObject hand = bbt != null ? bbt.activeHand : null;

        // Move hand to source hover position and pronate
        if (hand != null)
        {
            yield return StartCoroutine(MoveHandSmooth(hand.transform.position, bbt.sourceHoverPos));
            yield return StartCoroutine(PronateHand(true));
        }

        bbt.SetInstruction("Get ready...", Color.white);
        yield return new WaitForSeconds(1f);

        while (sessionRunning)
        {
            // ---- Check session time ----
            if (SessionTimeUp())
            {
                CompleteSession("time_limit");
                yield break;
            }

            // ============================================================
            //  PHASE 1: Wait for CLOSE prediction at source (no timeout)
            // ============================================================
            currentPhase = Phase.WaitingForClose;
            closeReceived = false;
            decodingActive = true;
            bbt.SetInstruction("CHIUDERE LA MANO", new Color(1f, 0.35f, 0.3f));
            SendToServer("decoding_start");
            RegisterEvent("trial_start");
            RegisterEvent("grasp_start", cfg.expectedCloseID);

            while (!closeReceived && sessionRunning)
            {
                if (SessionTimeUp())
                {
                    decodingActive = false;
                    SendToServer("decoding_stop");
                    RegisterEvent("trial_end");
                    CompleteSession("time_limit");
                    yield break;
                }
                yield return null;
            }

            if (!sessionRunning) yield break;

            decodingActive = false;
            SendToServer("decoding_stop");

            // ============================================================
            //  PHASE 2: Animate hand close + attach block
            // ============================================================
            currentPhase = Phase.Closing;
            totalAttempts++;

            if (hc != null)
            {
                Coroutine co = hc.StartGrasp("HandClose");
                if (co != null) yield return co;
                else yield return new WaitForSeconds(0.5f);
            }

            RegisterEvent("grasp_hold_start");
            yield return new WaitForSeconds(0.3f);
            RegisterEvent("grasp_hold_end");
            RegisterEvent("grasp_released");

            carriedBlock = CreateCarriedBlock();

            // ============================================================
            //  PHASE 3: Move to target — watch for OPEN = DROP
            // ============================================================
            currentPhase = Phase.Moving;
            openReceived = false;
            decodingActive = true;
            bbt.SetInstruction("BLOCCO MOBILE...", new Color(0.3f, 0.7f, 1f));
            SendToServer("decoding_start");

            yield return StartCoroutine(MoveHandArcWithDropCheck(bbt.sourceHoverPos, bbt.targetHoverPos));

            decodingActive = false;
            SendToServer("decoding_stop");

            if (openReceived)
            {
                // ---- BLOCK DROPPED DURING MOVE ----
                blocksDroppedDuringMove++;
                AppendDecoderLog("attempt_outcome", "block_dropped_during_move");
                Debug.Log($"[DecoderBBT] Block DROPPED during move (total drops: {blocksDroppedDuringMove})");

                // Animate hand open
                if (hc != null)
                {
                    Coroutine co = hc.ReleaseGrasp();
                    if (co != null) yield return co;
                    else yield return new WaitForSeconds(0.5f);
                }

                DropBlock();
                bbt.SetInstruction("BLOCCO CADUTO!", Color.red);
                RegisterEvent("trial_end");
                yield return new WaitForSeconds(1f);

                // Return to source
                currentPhase = Phase.Returning;
                if (hand != null)
                    yield return StartCoroutine(MoveHandSmooth(hand.transform.position, bbt.sourceHoverPos));

                UpdateScoreDisplay();
                continue;
            }

            // ============================================================
            //  PHASE 4: At target — wait for OPEN prediction
            // ============================================================
            currentPhase = Phase.WaitingForOpen;
            openReceived = false;
            decodingActive = true;
            bbt.SetInstruction("APRIRE LA MANO", new Color(0.3f, 1f, 0.4f));
            SendToServer("decoding_start");
            RegisterEvent("grasp_start", cfg.expectedOpenID);

            float openWait = 0f;
            while (!openReceived && openWait < cfg.phaseTimeoutSeconds && sessionRunning)
            {
                if (SessionTimeUp())
                {
                    decodingActive = false;
                    SendToServer("decoding_stop");
                    DestroyCarriedBlock();
                    RegisterEvent("trial_end");
                    CompleteSession("time_limit");
                    yield break;
                }
                openWait += Time.deltaTime;
                yield return null;
            }

            decodingActive = false;
            SendToServer("decoding_stop");

            if (openReceived)
            {
                // ---- SUCCESS: place block ----
                currentPhase = Phase.Opening;

                if (hc != null)
                {
                    Coroutine co = hc.StartGrasp("HandOpen");
                    if (co != null) yield return co;
                    else yield return new WaitForSeconds(0.5f);
                }

                RegisterEvent("grasp_released");
                PlaceBlockAtTarget();
                blocksSucceeded++;
                AppendDecoderLog("attempt_outcome", "block_moved_successfully");
                Debug.Log($"[DecoderBBT] Block PLACED (total: {blocksSucceeded})");
                bbt.SetInstruction("SUCCESS!", new Color(0.3f, 1f, 0.4f));
            }
            else
            {
                // ---- TIMEOUT at target ----
                blocksTimedOut++;
                AppendDecoderLog("attempt_outcome", "block_timeout_at_target");
                Debug.Log($"[DecoderBBT] Block TIMEOUT at target (total timeouts: {blocksTimedOut})");

                // Force hand open for next attempt
                if (hc != null)
                {
                    Coroutine co = hc.ReleaseGrasp();
                    if (co != null) yield return co;
                    else yield return new WaitForSeconds(0.5f);
                }

                DestroyCarriedBlock();
                bbt.SetInstruction("TIMEOUT!", Color.yellow);
            }

            RegisterEvent("trial_end");
            UpdateScoreDisplay();
            yield return new WaitForSeconds(0.5f);

            // Return to source
            currentPhase = Phase.Returning;
            if (hand != null)
                yield return StartCoroutine(MoveHandSmooth(hand.transform.position, bbt.sourceHoverPos));
        }
    }

    private bool SessionTimeUp()
    {
        return Time.time - sessionStartTime >= cfg.sessionDurationSeconds;
    }

    // ================================================================
    //  HAND MOVEMENT (with drop detection during arc)
    // ================================================================

    /// <summary>
    /// Arc movement from source to target. Checks openReceived every frame —
    /// if the decoder sends OPEN during the move, the arc stops immediately.
    /// </summary>
    private IEnumerator MoveHandArcWithDropCheck(Vector3 from, Vector3 to)
    {
        if (bbt.activeHand == null) yield break;

        float duration = bbt.config.moveDuration / 1000f;
        float arcHeight = bbt.config.handMoveHeight;
        Vector3 mid = (from + to) / 2f + Vector3.up * arcHeight;

        float t = 0f;
        while (t < duration && !openReceived)
        {
            t += Time.deltaTime;
            float p = Mathf.SmoothStep(0, 1, Mathf.Clamp01(t / duration));
            Vector3 a = Vector3.Lerp(from, mid, p);
            Vector3 b = Vector3.Lerp(mid, to, p);
            bbt.activeHand.transform.position = Vector3.Lerp(a, b, p);
            yield return null;
        }

        // Only snap to final position if we completed the full arc
        if (!openReceived)
            bbt.activeHand.transform.position = to;
    }

    private IEnumerator MoveHandSmooth(Vector3 from, Vector3 to)
    {
        if (bbt.activeHand == null) yield break;

        float duration = 0.6f;
        float t = 0f;
        while (t < duration)
        {
            t += Time.deltaTime;
            float p = Mathf.SmoothStep(0, 1, Mathf.Clamp01(t / duration));
            bbt.activeHand.transform.position = Vector3.Lerp(from, to, p);
            yield return null;
        }
        bbt.activeHand.transform.position = to;
    }

    private IEnumerator PronateHand(bool pronate)
    {
        if (bbt.activeHand == null) yield break;

        float duration = 0.4f;
        Quaternion startRot = bbt.activeHand.transform.rotation;
        float sign = bbt.isRightHand ? -1f : 1f;
        Quaternion targetRot = pronate
            ? bbt.handRestRotation * Quaternion.Euler(0, 0, sign * ManagerBBT.PRONATION_ANGLE)
            : bbt.handRestRotation;

        float t = 0f;
        while (t < duration)
        {
            t += Time.deltaTime;
            float p = Mathf.SmoothStep(0, 1, Mathf.Clamp01(t / duration));
            bbt.activeHand.transform.rotation = Quaternion.Slerp(startRot, targetRot, p);
            yield return null;
        }
        bbt.activeHand.transform.rotation = targetRot;
    }

    // ================================================================
    //  BLOCK MANAGEMENT
    // ================================================================

    private GameObject CreateCarriedBlock()
    {
        if (bbt.activeHand == null) return null;

        float bs = bbt.config.blockSize;
        GameObject block = GameObject.CreatePrimitive(PrimitiveType.Cube);
        block.name = "CarriedBlock";
        block.transform.localScale = Vector3.one * bs;
        block.GetComponent<Renderer>().material.color = BlockColors[totalAttempts % BlockColors.Length];

        block.transform.SetParent(bbt.activeHand.transform);
        block.transform.localPosition = new Vector3(0, -bs * 0.6f, 0);

        return block;
    }

    private void PlaceBlockAtTarget()
    {
        if (carriedBlock == null) return;

        carriedBlock.transform.SetParent(null);

        float bs = bbt.config.blockSize;
        int placed = placedBlocks.Count;
        int cols = Mathf.CeilToInt(Mathf.Sqrt(50));
        float sp = bs * 1.4f;
        int r = placed / cols;
        int c = placed % cols;

        // Drop side is opposite to pick side
        Transform dropZone = bbt.isRightHand ? bbt.sourceZone : bbt.targetZone;

        carriedBlock.transform.position = dropZone.position + new Vector3(
            (c - cols / 2f) * sp, bs / 2f, (r - cols / 2f) * sp);

        placedBlocks.Add(carriedBlock);
        carriedBlock = null;
    }

    private void DropBlock()
    {
        if (carriedBlock == null) return;

        carriedBlock.transform.SetParent(null);
        // Tint gray to indicate failure
        var renderer = carriedBlock.GetComponent<Renderer>();
        if (renderer != null) renderer.material.color = Color.gray;
        Destroy(carriedBlock, 3f);
        carriedBlock = null;
    }

    private void DestroyCarriedBlock()
    {
        if (carriedBlock != null)
        {
            Destroy(carriedBlock);
            carriedBlock = null;
        }
    }

    // ================================================================
    //  EVENTS & COMMS
    // ================================================================

    private void RegisterEvent(string eventVal, int? eventID = null)
    {
        try
        {
            if (TcpServerManager.Instance != null)
                TcpServerManager.Instance.SendMessageToClient(eventVal, eventID);
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[DecoderBBT] Event send failed ({eventVal}): {e.Message}");
        }
    }

    private void SendToServer(string message)
    {
        try
        {
            if (TcpServerManager.Instance != null)
                TcpServerManager.Instance.SendMessageToClient(message);
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[DecoderBBT] Send failed ({message}): {e.Message}");
        }
    }

    // ================================================================
    //  SCORING & DISPLAY
    // ================================================================

    private void UpdateScoreDisplay()
    {
        if (bbt == null) return;

        if (bbt.lblBlockCount != null)
            bbt.lblBlockCount.text = $"Moved: {blocksSucceeded}  Dropped: {blocksDroppedDuringMove}";
    }

    private void CompleteSession(string reason)
    {
        if (!sessionRunning) return;

        sessionRunning = false;
        decodingActive = false;
        currentPhase = Phase.Idle;

        if (sessionCoroutine != null)
        {
            StopCoroutine(sessionCoroutine);
            sessionCoroutine = null;
        }

        DestroyCarriedBlock();

        float elapsed = Time.time - sessionStartTime;

        Debug.Log($"[DecoderBBT] Session complete ({reason}) | " +
                  $"succeeded={blocksSucceeded}, dropped={blocksDroppedDuringMove}, " +
                  $"timeout={blocksTimedOut}, attempts={totalAttempts}, elapsed={elapsed:F1}s");

        bbt.SetInstruction(
            $"DONE! OK:{blocksSucceeded} Drop:{blocksDroppedDuringMove} Timeout:{blocksTimedOut}",
            new Color(1f, 0.9f, 0.2f));

        UpdateScoreDisplay();
        AppendDecoderLog("session_end", reason);
        PersistResult(reason, elapsed);

        RegisterEvent("session_end");
    }

    // ================================================================
    //  PERSISTENCE
    // ================================================================

    private void PersistResult(string reason, float elapsedSeconds)
    {
        if (string.IsNullOrWhiteSpace(sessionOutputDirectory))
            PrepareSessionPersistence();

        var payload = new DecoderBBTResult
        {
            sessionId = sessionId,
            sessionLabel = TcpServerManager.Instance != null ? TcpServerManager.Instance.CurrentSessionLabel : string.Empty,
            reason = reason,
            timestamp = DateTime.UtcNow.ToString("o"),
            outputDirectory = sessionOutputDirectory,
            sessionDurationSeconds = cfg.sessionDurationSeconds,
            elapsedSeconds = elapsedSeconds,
            blocksMovedSuccessfully = blocksSucceeded,
            blocksSucceeded = blocksSucceeded,
            blocksDropped = blocksDroppedDuringMove,
            blocksDroppedDuringMove = blocksDroppedDuringMove,
            blocksTimedOut = blocksTimedOut,
            totalAttempts = totalAttempts,
            decoderEventsLogged = decoderEventsLogged,
            decoderResultsLogFile = string.IsNullOrWhiteSpace(decoderResultsLogPath)
                ? string.Empty
                : Path.GetFileName(decoderResultsLogPath)
        };

        Directory.CreateDirectory(sessionOutputDirectory);
        string path = Path.Combine(sessionOutputDirectory, $"{sessionFileStem}_summary.json");
        File.WriteAllText(path, JsonUtility.ToJson(payload, true));
        Debug.Log($"[DecoderBBT] Results saved to {path}");
    }

    // ================================================================
    //  DATA MODEL
    // ================================================================

    [Serializable]
    private class DecoderBBTResult
    {
        public string sessionId;
        public string sessionLabel;
        public string reason;
        public string timestamp;
        public string outputDirectory;
        public int sessionDurationSeconds;
        public float elapsedSeconds;
        public int blocksMovedSuccessfully;
        public int blocksSucceeded;
        public int blocksDropped;
        public int blocksDroppedDuringMove;
        public int blocksTimedOut;
        public int totalAttempts;
        public int decoderEventsLogged;
        public string decoderResultsLogFile;
    }

    [Serializable]
    private class DecoderBBTLogEntry
    {
        public string sessionId;
        public string sessionLabel;
        public string timestamp;
        public float elapsedSeconds;
        public string entryType;
        public string detail;
        public string phase;
        public int predictedUnityEventId;
        public int predictedRawId;
        public float predictionProb;
        public float predictionTimestamp;
        public int blocksMovedSuccessfully;
        public int blocksSucceeded;
        public int blocksDropped;
        public int blocksDroppedDuringMove;
        public int blocksTimedOut;
        public int totalAttempts;
    }
}
