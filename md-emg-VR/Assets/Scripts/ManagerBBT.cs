using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// Manager for the Box and Block Test (BBT) scene.
///
/// Hand movement flow per block:
///   1. Hand hovers over source zone (open)
///   2. "CLOSE HAND"   → hand closes (grasp)          → events: grasp_start(1)
///   3. "MOVING BLOCK"  → hand+block arc to target     → events: grasp_hold_start / grasp_hold_end
///   4. "OPEN HAND"    → hand opens (release block)    → events: grasp_start(0), grasp_released
///   5. Hand returns to source zone (open)
///   6. Repeat
///
/// Hand side logic:
///   - Right hand: picks from RIGHT box, moves to LEFT box
///   - Left hand:  picks from LEFT box, moves to RIGHT box
///
/// Events match the static open-close task exactly so EMG recording works identically:
///   session_start → [trial_start → grasp_start(1) → grasp_hold_start → grasp_hold_end
///                    → grasp_start(0) → grasp_released → trial_end] × N → session_end
/// </summary>
public class ManagerBBT : MonoBehaviour
{
    public static ManagerBBT Instance { get; private set; }

    [Header("Hands (auto-found if empty)")]
    public GameObject leftHand;
    public GameObject rightHand;

    // --- Runtime references ---
    private HandController handController;
    private GameObject activeHand;
    private BBTConfig config;
    private bool isRightHand;

    // --- Hand position tracking ---
    private Vector3 handRestPosition;   // Original hand position (returned to on stop)
    private Quaternion handRestRotation; // Original hand rotation
    private Vector3 sourceHoverPos;     // Position above source zone
    private Vector3 targetHoverPos;     // Position above target zone

    // --- Pronation angles (degrees) ---
    // The hand faces palm-down (pronated) when reaching for and carrying blocks,
    // then returns to neutral (supinated) when opening to release.
    private const float PRONATION_ANGLE = 90f;  // Full pronation: palm faces down

    // --- GUI (all auto-created) ---
    private Button btnPlay;
    private Button btnStop;
    private Button btnExit;
    private Text lblStatus;
    private Text lblInstruction;
    private Text lblBlockCount;
    private Text lblTimer;

    // --- BBT box objects ---
    private Transform sourceZone;
    private Transform targetZone;
    private GameObject boxRoot;
    private List<GameObject> sourceBlocks = new List<GameObject>();
    private List<GameObject> placedBlocks = new List<GameObject>();

    // --- Session state ---
    private int numBlocks;              // From GameSettings.numTrialsPerGrasp
    private int blocksMoved = 0;
    private int currentBlockIndex = 0;
    private float sessionStartTime;
    private bool sessionRunning = false;
    private bool initialized = false;

    // ================================================================
    //  LIFECYCLE
    // ================================================================

    void Awake()
    {
        // Simple singleton — NO DontDestroyOnLoad (lives in this scene only)
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }
        Instance = this;
    }

    void Start()
    {
        Debug.Log("[BBT] ManagerBBT.Start()");

        try
        {
            BuildGUI();
            SetInstruction("Initializing...", Color.white);

            LoadConfig();
            FindHands();

            // Use the trial count from StartUI (e.g. user types 5 → 5 blocks)
            numBlocks = GameSettings.numTrialsPerGrasp;
            if (numBlocks <= 0) numBlocks = config.numberOfBlocks; // fallback
            Debug.Log($"[BBT] Block count from StartUI: {numBlocks}");

            BuildBBTBox();
            SpawnBlocks();

            // Calculate hand hover positions above the two zones
            CalculateHandPositions();

            SetInstruction("Press PLAY to start", Color.white);
            btnPlay.interactable = true;
            btnStop.interactable = false;
            initialized = true;

            Debug.Log($"[BBT] Initialized — hand={handController != null}, " +
                      $"isRight={isRightHand}, blocks={sourceBlocks.Count}");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"[BBT] Start() FAILED: {e.Message}\n{e.StackTrace}");
            if (lblInstruction != null) SetInstruction($"ERROR: {e.Message}", Color.red);
        }
    }

    void Update()
    {
        if (sessionRunning && lblTimer != null)
        {
            float elapsed = Time.time - sessionStartTime;
            int mins = Mathf.FloorToInt(elapsed / 60f);
            int secs = Mathf.FloorToInt(elapsed % 60f);
            lblTimer.text = $"Time: {mins:D2}:{secs:D2}";
        }
    }

    // ================================================================
    //  CONFIG
    // ================================================================

    private void LoadConfig()
    {
        string configPath = Path.Combine(Application.dataPath, "Config", "BBTConfig.json");
        if (File.Exists(configPath))
        {
            config = JsonUtility.FromJson<BBTConfig>(File.ReadAllText(configPath));
            Debug.Log("[BBT] Config loaded");
        }
        else
        {
            Debug.LogWarning("[BBT] BBTConfig.json not found — using defaults");
            config = new BBTConfig
            {
                sessionDuration = 60000,
                trialsStartDelay = 3000,
                graspCloseDuration = 1500,
                graspOpenDuration = 1500,
                holdDuration = 1000,
                moveDuration = 2000,
                placePauseDuration = 500,
                interTrialInterval = 1500,
                blockSize = 0.3f,
                numberOfBlocks = 15,
                boxWidth = 6f,
                boxDepth = 4f,
                boxHeight = 0.4f,
                partitionHeight = 2f,
                blockSpawnAreaWidth = 2.5f,
                blockSpawnAreaDepth = 3f,
                handMoveHeight = 2.5f,
                handMoveSpeed = 0.3f,
                graspLabels = new string[] { "HandClose", "HandOpen" },
                graspIDs = new int[] { 1, 0 }
            };
        }
    }

    // ================================================================
    //  FIND HANDS
    // ================================================================

    private void FindHands()
    {
        if (leftHand == null || rightHand == null)
        {
            HandController[] allHands = FindObjectsOfType<HandController>(true);
            Debug.Log($"[BBT] Found {allHands.Length} HandController(s)");

            foreach (var hc in allHands)
            {
                string n = hc.gameObject.name.ToLower();
                if (n.Contains("right")) rightHand = hc.gameObject;
                else if (n.Contains("left")) leftHand = hc.gameObject;
            }

            if (rightHand == null && leftHand == null && allHands.Length > 0)
            {
                rightHand = allHands[0].gameObject;
                leftHand = allHands[0].gameObject;
            }
        }

        isRightHand = GameSettings.dominantHand == DominantHand.right;

        if (isRightHand && rightHand != null)
        {
            activeHand = rightHand;
            handController = rightHand.GetComponent<HandController>();
            rightHand.SetActive(true);
            if (leftHand != null && leftHand != rightHand) leftHand.SetActive(false);
            Debug.Log($"[BBT] Using right hand: {rightHand.name}");
        }
        else if (leftHand != null)
        {
            activeHand = leftHand;
            handController = leftHand.GetComponent<HandController>();
            leftHand.SetActive(true);
            if (rightHand != null && rightHand != leftHand) rightHand.SetActive(false);
            Debug.Log($"[BBT] Using left hand: {leftHand.name}");
        }
        else
        {
            Debug.LogWarning("[BBT] No hands found — text-only mode");
        }

        // Remember rest position and rotation
        if (activeHand != null)
        {
            handRestPosition = activeHand.transform.position;
            handRestRotation = activeHand.transform.rotation;
        }
    }

    // ================================================================
    //  HAND POSITIONS
    // ================================================================

    /// <summary>
    /// Calculate the hover positions above source and target zones.
    /// Right hand: source = RIGHT side, target = LEFT side
    /// Left hand:  source = LEFT side,  target = RIGHT side
    /// </summary>
    private void CalculateHandPositions()
    {
        if (sourceZone == null || targetZone == null) return;

        float hoverHeight = config.partitionHeight + 1.0f; // above the partition

        // sourceZone is on the LEFT of the box, targetZone on the RIGHT
        // For right hand: pick from right (targetZone position), drop on left (sourceZone position)
        // For left hand:  pick from left (sourceZone position), drop on right (targetZone position)
        if (isRightHand)
        {
            // Right hand picks from right side (targetZone x), drops on left side (sourceZone x)
            sourceHoverPos = new Vector3(
                targetZone.position.x,
                boxRoot.transform.position.y + hoverHeight,
                boxRoot.transform.position.z);
            targetHoverPos = new Vector3(
                sourceZone.position.x,
                boxRoot.transform.position.y + hoverHeight,
                boxRoot.transform.position.z);
        }
        else
        {
            // Left hand picks from left side (sourceZone x), drops on right side (targetZone x)
            sourceHoverPos = new Vector3(
                sourceZone.position.x,
                boxRoot.transform.position.y + hoverHeight,
                boxRoot.transform.position.z);
            targetHoverPos = new Vector3(
                targetZone.position.x,
                boxRoot.transform.position.y + hoverHeight,
                boxRoot.transform.position.z);
        }

        Debug.Log($"[BBT] Hand hover: source={sourceHoverPos}, target={targetHoverPos}");
    }

    // ================================================================
    //  BUILD GUI (pure runtime)
    // ================================================================

    private void BuildGUI()
    {
        GameObject canvasGO = new GameObject("BBT_Canvas");
        Canvas canvas = canvasGO.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 200;
        CanvasScaler scaler = canvasGO.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1280, 720);
        canvasGO.AddComponent<GraphicRaycaster>();

        if (FindObjectOfType<UnityEngine.EventSystems.EventSystem>() == null)
        {
            GameObject es = new GameObject("EventSystem");
            es.AddComponent<UnityEngine.EventSystems.EventSystem>();
            es.AddComponent<UnityEngine.EventSystems.StandaloneInputModule>();
        }

        // ---- TOP BAR ----
        GameObject topBar = MakePanel(canvasGO.transform, "TopBar",
            new Color(0, 0, 0, 0.85f),
            new Vector2(0, 1), new Vector2(1, 1), new Vector2(0.5f, 1),
            Vector2.zero, new Vector2(0, 70));

        btnPlay = MakeButton(topBar.transform, "PLAY", new Color(0.1f, 0.6f, 0.2f),
            new Vector2(15, -8), new Vector2(130, 52));
        btnPlay.onClick.AddListener(OnBtnPlayClick);

        btnStop = MakeButton(topBar.transform, "STOP", new Color(0.7f, 0.1f, 0.1f),
            new Vector2(160, -8), new Vector2(130, 52));
        btnStop.onClick.AddListener(OnBtnStopClick);

        btnExit = MakeButton(topBar.transform, "EXIT", new Color(0.4f, 0.4f, 0.4f),
            new Vector2(305, -8), new Vector2(110, 52));
        btnExit.onClick.AddListener(OnBtnExitClick);

        lblBlockCount = MakeLabel(topBar.transform, "Blocks: 0", 28,
            new Color(1f, 0.9f, 0.2f), new Vector2(440, -8), new Vector2(200, 52));

        lblTimer = MakeLabel(topBar.transform, "Time: 00:00", 28,
            new Color(0.3f, 1f, 0.3f), new Vector2(650, -8), new Vector2(250, 52));

        lblStatus = MakeLabel(topBar.transform, "", 22,
            Color.white, new Vector2(910, -8), new Vector2(350, 52));

        // ---- CENTER INSTRUCTION (big, bold) ----
        GameObject instrPanel = MakePanel(canvasGO.transform, "InstrPanel",
            new Color(0, 0, 0, 0.75f),
            new Vector2(0.5f, 0.08f), new Vector2(0.5f, 0.08f), new Vector2(0.5f, 0.5f),
            Vector2.zero, new Vector2(800, 110));

        GameObject instrTextGO = new GameObject("InstrText");
        instrTextGO.transform.SetParent(instrPanel.transform, false);
        RectTransform instrRect = instrTextGO.AddComponent<RectTransform>();
        instrRect.anchorMin = Vector2.zero;
        instrRect.anchorMax = Vector2.one;
        instrRect.offsetMin = Vector2.zero;
        instrRect.offsetMax = Vector2.zero;
        lblInstruction = instrTextGO.AddComponent<Text>();
        lblInstruction.text = "";
        lblInstruction.fontSize = 52;
        lblInstruction.color = Color.white;
        lblInstruction.alignment = TextAnchor.MiddleCenter;
        lblInstruction.font = GetBuiltinFont();
        lblInstruction.fontStyle = FontStyle.Bold;

        Debug.Log("[BBT] GUI built");
    }

    private Button MakeButton(Transform parent, string label, Color bg, Vector2 pos, Vector2 size)
    {
        GameObject go = new GameObject("Btn_" + label);
        go.transform.SetParent(parent, false);
        RectTransform rt = go.AddComponent<RectTransform>();
        rt.anchorMin = new Vector2(0, 1);
        rt.anchorMax = new Vector2(0, 1);
        rt.pivot = new Vector2(0, 1);
        rt.anchoredPosition = pos;
        rt.sizeDelta = size;
        Image img = go.AddComponent<Image>();
        img.color = bg;
        Button btn = go.AddComponent<Button>();
        btn.targetGraphic = img;

        GameObject textGO = new GameObject("Text");
        textGO.transform.SetParent(go.transform, false);
        RectTransform trt = textGO.AddComponent<RectTransform>();
        trt.anchorMin = Vector2.zero;
        trt.anchorMax = Vector2.one;
        trt.offsetMin = Vector2.zero;
        trt.offsetMax = Vector2.zero;
        Text txt = textGO.AddComponent<Text>();
        txt.text = label;
        txt.fontSize = 24;
        txt.color = Color.white;
        txt.alignment = TextAnchor.MiddleCenter;
        txt.font = GetBuiltinFont();
        txt.fontStyle = FontStyle.Bold;
        return btn;
    }

    private Text MakeLabel(Transform parent, string text, int fontSize, Color color, Vector2 pos, Vector2 size)
    {
        GameObject go = new GameObject("Lbl");
        go.transform.SetParent(parent, false);
        RectTransform rt = go.AddComponent<RectTransform>();
        rt.anchorMin = new Vector2(0, 1);
        rt.anchorMax = new Vector2(0, 1);
        rt.pivot = new Vector2(0, 1);
        rt.anchoredPosition = pos;
        rt.sizeDelta = size;
        Text txt = go.AddComponent<Text>();
        txt.text = text;
        txt.fontSize = fontSize;
        txt.color = color;
        txt.alignment = TextAnchor.MiddleLeft;
        txt.font = GetBuiltinFont();
        txt.fontStyle = FontStyle.Bold;
        txt.horizontalOverflow = HorizontalWrapMode.Overflow;
        return txt;
    }

    private GameObject MakePanel(Transform parent, string name, Color color,
        Vector2 anchorMin, Vector2 anchorMax, Vector2 pivot, Vector2 pos, Vector2 size)
    {
        GameObject go = new GameObject(name);
        go.transform.SetParent(parent, false);
        RectTransform rt = go.AddComponent<RectTransform>();
        rt.anchorMin = anchorMin;
        rt.anchorMax = anchorMax;
        rt.pivot = pivot;
        rt.anchoredPosition = pos;
        rt.sizeDelta = size;
        Image img = go.AddComponent<Image>();
        img.color = color;
        return go;
    }

    private Font GetBuiltinFont()
    {
        // Try multiple built-in font names across Unity versions
        string[] fontNames = { "Arial.ttf", "LegacyRuntime.ttf", "Liberation Sans" };
        foreach (string name in fontNames)
        {
            Font f = Resources.GetBuiltinResource<Font>(name);
            if (f != null) return f;
        }
        // Last resort: find any font loaded in the project
        Font[] allFonts = Resources.FindObjectsOfTypeAll<Font>();
        if (allFonts.Length > 0) return allFonts[0];
        // Absolute fallback: create a blank font (text will render with default)
        Debug.LogWarning("[BBT] No built-in font found — UI text may not render.");
        return Font.CreateDynamicFontFromOSFont("Arial", 14);
    }

    // ================================================================
    //  BUILD BBT BOX & BLOCKS
    // ================================================================

    private void BuildBBTBox()
    {
        Vector3 boxPos;
        if (activeHand != null)
            // Place box well below the hand so it doesn't overlap
            // hand is ~3 units tall, partition is 2 units, so offset -4.5 gives clearance
            boxPos = activeHand.transform.position + new Vector3(0, -4.5f, 1f);
        else if (Camera.main != null)
            boxPos = Camera.main.transform.position + Camera.main.transform.forward * 5f + Vector3.down * 3f;
        else
            boxPos = new Vector3(0, 1f, 3f);

        boxRoot = new GameObject("BBTBox");
        boxRoot.transform.position = boxPos;

        float w = config.boxWidth;
        float d = config.boxDepth;
        float h = config.boxHeight;
        float ph = config.partitionHeight;
        float t = 0.1f;

        MakeCube(boxRoot.transform, "Base", Vector3.zero, new Vector3(w, h, d), new Color(0.55f, 0.4f, 0.25f));
        MakeCube(boxRoot.transform, "Partition", new Vector3(0, h / 2 + ph / 2, 0), new Vector3(t, ph, d), Color.gray);
        MakeCube(boxRoot.transform, "WL", new Vector3(-w / 2, h / 2 + ph / 2, 0), new Vector3(t, ph, d), new Color(0.55f, 0.4f, 0.25f));
        MakeCube(boxRoot.transform, "WR", new Vector3(w / 2, h / 2 + ph / 2, 0), new Vector3(t, ph, d), new Color(0.55f, 0.4f, 0.25f));
        MakeCube(boxRoot.transform, "WF", new Vector3(0, h / 2 + ph / 2, d / 2), new Vector3(w, ph, t), new Color(0.55f, 0.4f, 0.25f));
        MakeCube(boxRoot.transform, "WB", new Vector3(0, h / 2 + ph / 2, -d / 2), new Vector3(w, ph, t), new Color(0.55f, 0.4f, 0.25f));

        // sourceZone = LEFT side, targetZone = RIGHT side (flipped by hand logic later)
        sourceZone = new GameObject("SourceZone").transform;
        sourceZone.SetParent(boxRoot.transform);
        sourceZone.localPosition = new Vector3(-w / 4, h / 2 + 0.05f, 0);

        targetZone = new GameObject("TargetZone").transform;
        targetZone.SetParent(boxRoot.transform);
        targetZone.localPosition = new Vector3(w / 4, h / 2 + 0.05f, 0);

        Debug.Log($"[BBT] Box at {boxPos}");
    }

    private GameObject MakeCube(Transform parent, string name, Vector3 localPos, Vector3 scale, Color color)
    {
        GameObject obj = GameObject.CreatePrimitive(PrimitiveType.Cube);
        obj.name = name;
        obj.transform.SetParent(parent);
        obj.transform.localPosition = localPos;
        obj.transform.localScale = scale;
        obj.GetComponent<Renderer>().material.color = color;
        return obj;
    }

    private void SpawnBlocks()
    {
        foreach (var b in sourceBlocks) if (b != null) Destroy(b);
        sourceBlocks.Clear();
        placedBlocks.Clear();

        float bs = config.blockSize;
        int n = numBlocks;
        int cols = Mathf.CeilToInt(Mathf.Sqrt(n));
        float sp = bs * 1.4f;

        // Spawn blocks on the PICK side (depends on dominant hand)
        // Right hand picks from right → spawn at targetZone
        // Left hand picks from left → spawn at sourceZone
        Transform spawnZone = isRightHand ? targetZone : sourceZone;

        Color[] colors = {
            new Color(0.9f, 0.2f, 0.2f),
            new Color(0.2f, 0.5f, 0.9f),
            new Color(0.2f, 0.8f, 0.3f),
            new Color(0.9f, 0.8f, 0.2f),
            new Color(0.7f, 0.3f, 0.8f)
        };

        for (int i = 0; i < n; i++)
        {
            int r = i / cols;
            int c = i % cols;
            Vector3 pos = spawnZone.position + new Vector3(
                (c - cols / 2f) * sp, bs / 2f, (r - cols / 2f) * sp);

            GameObject block = GameObject.CreatePrimitive(PrimitiveType.Cube);
            block.name = $"Block_{i}";
            block.transform.position = pos;
            block.transform.localScale = Vector3.one * bs;
            block.GetComponent<Renderer>().material.color = colors[i % colors.Length];
            sourceBlocks.Add(block);
        }

        Debug.Log($"[BBT] Spawned {n} blocks on {(isRightHand ? "right" : "left")} side");
    }

    // ================================================================
    //  BUTTON HANDLERS
    // ================================================================

    public void OnBtnPlayClick()
    {
        Debug.Log("[BBT] >>> PLAY <<<");

        if (!initialized)
        {
            SetInstruction("ERROR: Not initialized", Color.red);
            return;
        }
        if (sessionRunning) return;

        btnPlay.interactable = false;
        btnStop.interactable = true;

        sessionRunning = true;
        sessionStartTime = Time.time;
        blocksMoved = 0;
        currentBlockIndex = 0;
        placedBlocks.Clear();
        if (lblBlockCount != null) lblBlockCount.text = $"Blocks: 0 / {numBlocks}";

        // ---- EVENT: session_start (same as ManagerOpenLoop) ----
        RegisterEvent("session_start");

        StartCoroutine(RunSession());
    }

    public void OnBtnStopClick()
    {
        Debug.Log("[BBT] STOP");
        sessionRunning = false;
        StopAllCoroutines();

        // ---- EVENT: session_stop ----
        RegisterEvent("session_stop");

        btnPlay.interactable = true;
        btnStop.interactable = false;
        SetInstruction("Stopped — press PLAY to restart", Color.white);

        // Return hand to rest
        if (activeHand != null)
        {
            activeHand.transform.position = handRestPosition;
            activeHand.transform.rotation = handRestRotation;
        }

        SpawnBlocks();
    }

    public void OnBtnExitClick()
    {
        RegisterEvent("session_exit");
        Application.Quit();
    }

    // ================================================================
    //  MAIN SESSION COROUTINE
    // ================================================================

    IEnumerator RunSession()
    {
        Debug.Log("[BBT] Session started");

        // Move hand to source hover position
        if (activeHand != null)
            yield return StartCoroutine(MoveHandSmooth(activeHand.transform.position, sourceHoverPos));

        SetInstruction("Get ready...", Color.white);
        lblStatus.text = "Starting...";
        yield return new WaitForSeconds(config.trialsStartDelay / 1000f);

        // ---- Main loop: one block per iteration ----
        // Each block produces 2 trials (CLOSE + OPEN), matching OpenLoop exactly:
        //   Trial A: grasp_start(1) → hold_start → hold_end → released  (CLOSE)
        //   [move block]
        //   Trial B: grasp_start(0) → hold_start → hold_end → released  (OPEN)
        while (sessionRunning && currentBlockIndex < sourceBlocks.Count)
        {
            GameObject block = sourceBlocks[currentBlockIndex];
            if (block == null) { currentBlockIndex++; continue; }

            lblStatus.text = $"Block {currentBlockIndex + 1} / {sourceBlocks.Count}";

            // ===== TRIAL A: CLOSE HAND (grasp the block) =====
            RegisterEvent("trial_start");
            Debug.Log($"[BBT] === Block {currentBlockIndex + 1} — Trial CLOSE ===");

            yield return StartCoroutine(TrialClose(block));

            RegisterEvent("trial_end");
            Debug.Log("[BBT] trial_end (close)");

            // ===== MOVE BLOCK (between trials — no events) =====
            yield return StartCoroutine(MoveBlock(block));

            // ===== TRIAL B: OPEN HAND (release the block) =====
            RegisterEvent("trial_start");
            Debug.Log($"[BBT] === Block {currentBlockIndex + 1} — Trial OPEN ===");

            yield return StartCoroutine(TrialOpen(block));

            RegisterEvent("trial_end");
            Debug.Log("[BBT] trial_end (open)");

            // Scoring
            blocksMoved++;
            currentBlockIndex++;
            placedBlocks.Add(block);
            if (lblBlockCount != null) lblBlockCount.text = $"Blocks: {blocksMoved} / {numBlocks}";

            try
            {
                if (FSMDisplayManager.Instance != null)
                {
                    FSMDisplayManager.Instance.IncrementBlockCount();
                    FSMDisplayManager.Instance.IncrementGraspCount();
                }
            }
            catch { }

            Debug.Log($"[BBT] Placed — total: {blocksMoved}");

            // Check if this was the last block
            if (currentBlockIndex >= sourceBlocks.Count)
            {
                yield return new WaitForSeconds(1.5f);
                RegisterEvent("session_end");
                Debug.Log("[BBT] All blocks done → session_end");
                break;
            }

            // ── PAUSE before next block ──
            SetInstruction("Good!", Color.white);
            yield return new WaitForSeconds(config.interTrialInterval / 1000f);

            // Return hand to source for next block
            if (activeHand != null)
            {
                yield return StartCoroutine(MoveHandArc(targetHoverPos, sourceHoverPos));
            }
        }

        // ---- Check if ended early ----
        if (currentBlockIndex < sourceBlocks.Count)
        {
            RegisterEvent("session_end");
        }

        // Return hand to rest (smooth move + smooth rotation)
        if (activeHand != null)
        {
            yield return StartCoroutine(MoveHandSmooth(activeHand.transform.position, handRestPosition));
            // Smoothly rotate back to rest rotation instead of snapping
            yield return StartCoroutine(SmoothRotate(activeHand.transform.rotation, handRestRotation, 0.6f));
        }

        sessionRunning = false;
        btnPlay.interactable = true;
        btnStop.interactable = false;
        SetInstruction($"DONE!  Blocks: {blocksMoved}", new Color(1f, 0.9f, 0.2f));
        lblStatus.text = "Complete";
        Debug.Log($"[BBT] Session complete — blocks: {blocksMoved}");
    }

    // ================================================================
    //  TRIAL ANIMATIONS — each matches OpenLoop TrialAnimation exactly
    //  OpenLoop pattern: grasp_start(ID) → animate → hold_start → hold → hold_end → release → released
    // ================================================================

    /// <summary>
    /// CLOSE trial: pronate hand, show cue, grasp_start(1), close hand, hold, hold_end, released.
    /// Matches OpenLoop event sequence exactly for a HandClose trial.
    /// </summary>
    IEnumerator TrialClose(GameObject block)
    {
        // Pronate hand (palm-down toward block)
        if (activeHand != null)
        {
            yield return StartCoroutine(PronateHand(true));
        }

        // Show instruction cue
        SetInstruction("CLOSE HAND", new Color(1f, 0.35f, 0.3f));
        yield return new WaitForSeconds(0.5f);

        // EVENT: grasp_start(1) — identical to OpenLoop
        RegisterEvent("grasp_start", 1);
        Debug.Log("[BBT] grasp_start(1) — HandClose");

        // Animate hand closing
        if (handController != null)
        {
            Coroutine co = handController.StartGrasp("HandClose");
            if (co != null) yield return co;
            else yield return new WaitForSeconds(1f);
        }
        else
        {
            yield return new WaitForSeconds(1.5f);
        }

        // EVENT: grasp_hold_start — hold the grasp (EMG training window starts here)
        RegisterEvent("grasp_hold_start");
        Debug.Log("[BBT] grasp_hold_start (close)");

        yield return new WaitForSeconds(config.holdDuration / 1000f);

        // EVENT: grasp_hold_end — (EMG training window ends here)
        SetInstruction("", Color.white);
        RegisterEvent("grasp_hold_end");
        Debug.Log("[BBT] grasp_hold_end (close)");

        // Release animation (hand stays closed visually — we just mark event)
        // In OpenLoop, ReleaseGrasp is called here. For BBT we skip the visual
        // release because the hand needs to stay closed to carry the block.
        // But we still fire grasp_released to complete the event cycle.
        RegisterEvent("grasp_released");
        Debug.Log("[BBT] grasp_released (close trial complete)");
    }

    /// <summary>
    /// Move the block from source to target (no EMG events — just animation).
    /// </summary>
    IEnumerator MoveBlock(GameObject block)
    {
        SetInstruction("MOVING BLOCK...", new Color(0.3f, 0.7f, 1f));

        // Attach block to hand
        Transform originalParent = block.transform.parent;
        Vector3 blockOffset = Vector3.zero;
        if (activeHand != null)
        {
            blockOffset = block.transform.position - activeHand.transform.position;
            block.transform.SetParent(activeHand.transform);
            block.transform.localPosition = blockOffset;
        }

        // Arc movement from source to target
        if (activeHand != null)
        {
            yield return StartCoroutine(MoveHandArc(sourceHoverPos, targetHoverPos));
        }
        else
        {
            Vector3 targetPos = GetNextDropPosition();
            yield return StartCoroutine(AnimateBlockArc(block, block.transform.position, targetPos));
        }

        // Detach block at target
        if (activeHand != null)
        {
            block.transform.SetParent(originalParent);
            block.transform.position = GetNextDropPosition();
        }

        SetInstruction("", Color.white);
    }

    /// <summary>
    /// OPEN trial: show cue, grasp_start(0), open hand, hold, hold_end, released.
    /// Matches OpenLoop event sequence exactly for a HandOpen trial.
    /// </summary>
    IEnumerator TrialOpen(GameObject block)
    {
        // Show instruction cue
        SetInstruction("OPEN HAND", new Color(0.3f, 1f, 0.4f));
        yield return new WaitForSeconds(0.5f);

        // EVENT: grasp_start(0) — identical to OpenLoop
        RegisterEvent("grasp_start", 0);
        Debug.Log("[BBT] grasp_start(0) — HandOpen");

        // Animate hand opening (release the block)
        if (handController != null)
        {
            Coroutine co = handController.ReleaseGrasp();
            if (co != null) yield return co;
            else yield return new WaitForSeconds(1f);
        }
        else
        {
            yield return new WaitForSeconds(1.5f);
        }

        // EVENT: grasp_hold_start — hold the open position (EMG training window)
        RegisterEvent("grasp_hold_start");
        Debug.Log("[BBT] grasp_hold_start (open)");

        yield return new WaitForSeconds(config.holdDuration / 1000f);

        // EVENT: grasp_hold_end
        SetInstruction("", Color.white);
        RegisterEvent("grasp_hold_end");
        Debug.Log("[BBT] grasp_hold_end (open)");

        // EVENT: grasp_released — cycle complete
        RegisterEvent("grasp_released");
        Debug.Log("[BBT] grasp_released (open trial complete)");
    }

    // ================================================================
    //  HAND MOVEMENT
    // ================================================================

    /// <summary>
    /// Move the hand in an arc (up and over the partition).
    /// Rotation is NOT changed here — pronation is handled separately.
    /// </summary>
    IEnumerator MoveHandArc(Vector3 from, Vector3 to)
    {
        if (activeHand == null) yield break;

        float duration = config.moveDuration / 1000f;
        float arcHeight = config.handMoveHeight;
        Vector3 mid = (from + to) / 2f + Vector3.up * arcHeight;

        float t = 0f;
        while (t < duration)
        {
            t += Time.deltaTime;
            float p = Mathf.SmoothStep(0, 1, Mathf.Clamp01(t / duration));

            Vector3 a = Vector3.Lerp(from, mid, p);
            Vector3 b = Vector3.Lerp(mid, to, p);
            activeHand.transform.position = Vector3.Lerp(a, b, p);

            yield return null;
        }
        activeHand.transform.position = to;
    }

    /// <summary>
    /// Smoothly pronate (palm faces down) or supinate (return to rest) the hand.
    /// Called before grasping (pronate=true) and before releasing (pronate=false).
    /// </summary>
    IEnumerator PronateHand(bool pronate)
    {
        if (activeHand == null) yield break;

        float duration = 0.4f;
        Quaternion startRot = activeHand.transform.rotation;

        // Pronation axis: rotate around local Z (forearm axis)
        float sign = isRightHand ? -1f : 1f;
        Quaternion targetRot = pronate
            ? handRestRotation * Quaternion.Euler(0, 0, sign * PRONATION_ANGLE)
            : handRestRotation;

        float t = 0f;
        while (t < duration)
        {
            t += Time.deltaTime;
            float p = Mathf.SmoothStep(0, 1, Mathf.Clamp01(t / duration));
            activeHand.transform.rotation = Quaternion.Slerp(startRot, targetRot, p);
            yield return null;
        }
        activeHand.transform.rotation = targetRot;
    }

    /// <summary>
    /// Smoothly move the hand in a straight line.
    /// </summary>
    IEnumerator MoveHandSmooth(Vector3 from, Vector3 to)
    {
        if (activeHand == null) yield break;

        float duration = 0.6f;
        float t = 0f;
        while (t < duration)
        {
            t += Time.deltaTime;
            float p = Mathf.SmoothStep(0, 1, Mathf.Clamp01(t / duration));
            activeHand.transform.position = Vector3.Lerp(from, to, p);
            yield return null;
        }
        activeHand.transform.position = to;
    }

    /// <summary>
    /// Smoothly rotate from one rotation to another over the given duration.
    /// </summary>
    IEnumerator SmoothRotate(Quaternion from, Quaternion to, float duration)
    {
        if (activeHand == null) yield break;
        float t = 0f;
        while (t < duration)
        {
            t += Time.deltaTime;
            float p = Mathf.SmoothStep(0, 1, Mathf.Clamp01(t / duration));
            activeHand.transform.rotation = Quaternion.Slerp(from, to, p);
            yield return null;
        }
        activeHand.transform.rotation = to;
    }

    /// <summary>
    /// Fallback: animate block directly when no hand is present.
    /// </summary>
    IEnumerator AnimateBlockArc(GameObject block, Vector3 from, Vector3 to)
    {
        float duration = config.moveDuration / 1000f;
        float arcHeight = config.handMoveHeight;
        Vector3 mid = (from + to) / 2f + Vector3.up * arcHeight;

        float t = 0f;
        while (t < duration)
        {
            t += Time.deltaTime;
            float p = Mathf.SmoothStep(0, 1, Mathf.Clamp01(t / duration));
            Vector3 a = Vector3.Lerp(from, mid, p);
            Vector3 b = Vector3.Lerp(mid, to, p);
            block.transform.position = Vector3.Lerp(a, b, p);
            yield return null;
        }
        block.transform.position = to;
    }

    /// <summary>
    /// Get the position where the next block should be dropped on the target side.
    /// </summary>
    private Vector3 GetNextDropPosition()
    {
        float bs = config.blockSize;
        int placed = placedBlocks.Count;
        int cols = Mathf.CeilToInt(Mathf.Sqrt(numBlocks));
        float sp = bs * 1.4f;
        int r = placed / cols;
        int c = placed % cols;

        // Drop zone is the opposite side of pick zone
        Transform dropZone = isRightHand ? sourceZone : targetZone;

        return dropZone.position + new Vector3(
            (c - cols / 2f) * sp, bs / 2f, (r - cols / 2f) * sp);
    }

    // ================================================================
    //  TCP EVENTS (matches ManagerOpenLoop.RegisterEvent exactly)
    // ================================================================

    /// <summary>
    /// Send event via TCP to the Python EMG recording script.
    /// Format: {"event":"name","event_id":N} or {"event":"name"}
    /// Null-safe — never throws.
    /// </summary>
    void RegisterEvent(string eventVal, int? eventID = null)
    {
        try
        {
            if (TcpServerManager.Instance != null)
                TcpServerManager.Instance.SendMessageToClient(eventVal, eventID);
            else
                Debug.LogWarning($"[BBT] TcpServerManager not available — event: {eventVal}");
        }
        catch (System.Exception e)
        {
            Debug.LogWarning($"[BBT] Event failed ({eventVal}): {e.Message}");
        }
    }

    // ================================================================
    //  HELPERS
    // ================================================================

    private void SetInstruction(string text, Color color)
    {
        if (lblInstruction != null)
        {
            lblInstruction.text = text;
            lblInstruction.color = color;
        }
    }
}
