using UnityEngine;
using UnityEditor;

/// <summary>
/// Editor menu to quickly add FSM Display to any scene.
/// </summary>
public class FSMDisplaySetupMenu : MonoBehaviour
{
    [MenuItem("EMG-Exo/Setup FSM Display UI")]
    public static void SetupFSMDisplayUI()
    {
        // Check if already exists
        FSMDisplayAutoSetup existing = FindObjectOfType<FSMDisplayAutoSetup>();
        if (existing != null)
        {
            Debug.Log("FSMDisplayAutoSetup already exists in scene. Running setup...");
            existing.SetupFSMDisplay();
            return;
        }

        // Create new setup object
        GameObject setupObj = new GameObject("FSMDisplayAutoSetup");
        FSMDisplayAutoSetup setup = setupObj.AddComponent<FSMDisplayAutoSetup>();

        // Run setup immediately in editor
        setup.SetupFSMDisplay();

        Debug.Log("✓ FSM Display UI added to scene!");
        Debug.Log("  The UI will auto-show when FSM mode is activated from Python.");

        // Select the created object
        Selection.activeGameObject = setupObj;
    }

    [MenuItem("EMG-Exo/Remove FSM Display UI")]
    public static void RemoveFSMDisplayUI()
    {
        // Find and destroy FSM display objects
        FSMDisplayAutoSetup setup = FindObjectOfType<FSMDisplayAutoSetup>();
        if (setup != null)
        {
            DestroyImmediate(setup.gameObject);
        }

        FSMDisplayManager manager = FindObjectOfType<FSMDisplayManager>();
        if (manager != null)
        {
            DestroyImmediate(manager.gameObject);
        }

        // Find and destroy panels
        GameObject fsmPanel = GameObject.Find("FSMDisplayPanel");
        if (fsmPanel != null) DestroyImmediate(fsmPanel);

        GameObject bbtPanel = GameObject.Find("BBTScoringPanel");
        if (bbtPanel != null) DestroyImmediate(bbtPanel);

        GameObject fsmCanvas = GameObject.Find("FSMCanvas");
        if (fsmCanvas != null) DestroyImmediate(fsmCanvas);

        Debug.Log("✓ FSM Display UI removed from scene.");
    }
}
