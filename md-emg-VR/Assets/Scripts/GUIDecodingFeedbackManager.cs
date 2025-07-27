using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using System;

public class GUIDecodingFeedbackManager : MonoBehaviour
{ 
    // Define Feedback GUI states
    public enum GUIFeedbackInstructions { 
        Empty, HandOpen, HandClose, 
        HookGrasp, LateralGrasp, IndexPointing,
        ThumbFlexion, IndexFlexion, MRPFlexion
    }

    private Dictionary<GUIFeedbackInstructions, Sprite> GUIInstructionsSpriteDict;

    // GUI main elements
    [Header("GUI State")]
    [SerializeField] private Sprite UiStateActive;
    [SerializeField] private Sprite UiStateInactive;

    [Header("GUI Class Items")]
    [SerializeField] private List<Image> targets2Images;
    [SerializeField] private List<Image> targets3Images;

    private List<Image> guiClassImages;

    private void Start()
    {
        if (GameSettings.graspingType == GraspingType.HandOpenClose) // open-close has 2 targets
        {
            guiClassImages = targets2Images;
            targets3Images.ForEach(image => image.gameObject.SetActive(false));
        }
        else // other grasping types have 3 targets
        {
            guiClassImages = targets3Images;
            targets2Images.ForEach(image => image.gameObject.SetActive(false));
        }
    }

    public void SetClassActive(int classIndex)
    {
        for (int i = 0; i < guiClassImages.Count; i++)
        {
            if (guiClassImages[i] != null)
            {
                guiClassImages[i].sprite = (i == classIndex) ? UiStateActive : UiStateInactive;
            }
        }
    }
}
