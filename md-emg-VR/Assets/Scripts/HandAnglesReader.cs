using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class HandAnglesReader : MonoBehaviour
{
    public GameObject Hand; // Reference to the Hand object
    private string[] fingerNames = { "Thumb", "Index", "Middle", "Ring", "Pinky" };

    void Start()
    {
        // If Hand reference isn't set in the inspector, try to find it
        if (Hand == null)
        {
            Debug.LogError("Hand object not found. Please assign it in the inspector.");
            return;
        }

        // Loop through each finger
        foreach (string fingerName in fingerNames)
        {
            Transform finger = Hand.transform.Find(fingerName);
            if (finger != null)
            {
                Debug.Log($"===== {fingerName} Finger =====");

                // Log the finger root transform itself
                Vector3 fingerRootAngles = finger.localRotation.eulerAngles;
                Debug.Log($"{fingerName} Root: {fingerRootAngles}");

                // Get all child joints of the finger
                for (int i = 0; i < finger.childCount; i++)
                {
                    Transform joint = finger.GetChild(i);
                    Vector3 eulerAngles = joint.localRotation.eulerAngles;
                    Debug.Log($"{fingerName} Joint {i}: {eulerAngles}");

                    // If the joint has children (sub-joints), log them too
                    LogChildJoints(joint, fingerName, 1);
                }
            }
            else
            {
                Debug.LogWarning($"Finger {fingerName} not found under Hand object");
            }
        }
    }

    // Recursive function to log child joints
    private void LogChildJoints(Transform parent, string fingerName, int depth)
    {
        for (int i = 0; i < parent.childCount; i++)
        {
            Transform child = parent.GetChild(i);
            Vector3 eulerAngles = child.localRotation.eulerAngles;
            Debug.Log($"{fingerName} Sub-Joint {depth}-{i}: {eulerAngles}");

            // Continue recursively if there are more children
            if (child.childCount > 0)
            {
                LogChildJoints(child, fingerName, depth + 1);
            }
        }
    }
}