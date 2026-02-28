using UnityEngine;

/// <summary>
/// Script to attach to the BBT box partition and source/target zones.
/// Creates the box environment at runtime with a dividing partition.
/// Attach this to an empty GameObject in the scene — it will generate
/// the box, partition, and zone markers automatically.
/// </summary>
public class BBTBoxSetup : MonoBehaviour
{
    [Header("Box Dimensions")]
    public float boxWidth = 0.5f;
    public float boxDepth = 0.3f;
    public float boxHeight = 0.05f;
    public float wallThickness = 0.01f;
    public float partitionHeight = 0.15f;

    [Header("Materials")]
    public Material boxMaterial;
    public Material partitionMaterial;

    [Header("Generated References (auto-filled at runtime)")]
    public Transform sourceZoneTransform;
    public Transform targetZoneTransform;
    public GameObject partitionWall;

    [Header("Colors (used if no material is assigned)")]
    public Color boxColor = new Color(0.6f, 0.45f, 0.3f);        // Wood-brown
    public Color partitionColor = new Color(0.3f, 0.3f, 0.3f);   // Dark grey

    void Start()
    {
        BuildBox();
    }

    [ContextMenu("Build BBT Box")]
    public void BuildBox()
    {
        // ---- Base / Floor ----
        GameObject baseObj = GameObject.CreatePrimitive(PrimitiveType.Cube);
        baseObj.name = "BBT_Base";
        baseObj.transform.SetParent(transform);
        baseObj.transform.localPosition = Vector3.zero;
        baseObj.transform.localScale = new Vector3(boxWidth, boxHeight, boxDepth);
        SetMaterial(baseObj, boxMaterial, boxColor);

        float halfW = boxWidth / 2f;
        float halfD = boxDepth / 2f;
        float wallH = partitionHeight / 2f;
        float baseTop = boxHeight / 2f;

        // ---- Side walls ----
        // Left wall
        CreateWall("Wall_Left", new Vector3(-halfW, baseTop + wallH, 0f),
            new Vector3(wallThickness, partitionHeight, boxDepth));

        // Right wall
        CreateWall("Wall_Right", new Vector3(halfW, baseTop + wallH, 0f),
            new Vector3(wallThickness, partitionHeight, boxDepth));

        // Front wall
        CreateWall("Wall_Front", new Vector3(0f, baseTop + wallH, halfD),
            new Vector3(boxWidth, partitionHeight, wallThickness));

        // Back wall
        CreateWall("Wall_Back", new Vector3(0f, baseTop + wallH, -halfD),
            new Vector3(boxWidth, partitionHeight, wallThickness));

        // ---- Central partition ----
        partitionWall = GameObject.CreatePrimitive(PrimitiveType.Cube);
        partitionWall.name = "BBT_Partition";
        partitionWall.transform.SetParent(transform);
        partitionWall.transform.localPosition = new Vector3(0f, baseTop + wallH, 0f);
        partitionWall.transform.localScale = new Vector3(wallThickness, partitionHeight, boxDepth);
        SetMaterial(partitionWall, partitionMaterial, partitionColor);

        // ---- Source zone marker (left of partition) ----
        GameObject sourceZone = new GameObject("SourceZone");
        sourceZone.transform.SetParent(transform);
        sourceZone.transform.localPosition = new Vector3(-halfW / 2f, baseTop + 0.001f, 0f);
        sourceZoneTransform = sourceZone.transform;

        // ---- Target zone marker (right of partition) ----
        GameObject targetZone = new GameObject("TargetZone");
        targetZone.transform.SetParent(transform);
        targetZone.transform.localPosition = new Vector3(halfW / 2f, baseTop + 0.001f, 0f);
        targetZoneTransform = targetZone.transform;

        // Note: ManagerBBT builds its own box internally, so no wiring needed.

        Debug.Log("BBT Box built successfully");
    }

    private void CreateWall(string name, Vector3 localPos, Vector3 scale)
    {
        GameObject wall = GameObject.CreatePrimitive(PrimitiveType.Cube);
        wall.name = name;
        wall.transform.SetParent(transform);
        wall.transform.localPosition = localPos;
        wall.transform.localScale = scale;
        SetMaterial(wall, boxMaterial, boxColor);
    }

    private void SetMaterial(GameObject obj, Material mat, Color fallbackColor)
    {
        Renderer renderer = obj.GetComponent<Renderer>();
        if (mat != null)
        {
            renderer.material = mat;
        }
        else
        {
            renderer.material.color = fallbackColor;
        }
    }
}
