using System.Xml;
using System;
using UnityEngine;
using System.Globalization;
using System.Collections.Generic;
using System.IO;

public static class HandAngles
{
    // TODO: move this to a config file
    public static string[] fingerNames = new string[] {
        "Thumb", "Index", "Middle", "Ring", "Pinky"
    };

    static int numJoints = 3; // Number of joints per finger

    // NEW: Returns an array of Quaternions for the given grasp.
    public static List<Quaternion[]> GetGraspRotations(string graspName)
    {
        List<Quaternion[]> rotationsList = new List<Quaternion[]>();

        // For each finger name, assume joint 0 (adjust if needed)
        for (int i = 0; i < fingerNames.Length; i++)
        {
            Quaternion[] rotations = new Quaternion[numJoints];

            for (int j = 0; j < numJoints; j++)
            {
                // Use the existing function to get the Euler angles from XML
                Vector3 angles = getGraspAngles(graspName, fingerNames[i], joint: j);
                rotations[j] = Quaternion.Euler(angles);
            }

            // Add the rotations for this finger to the list
            rotationsList.Add(rotations);
        }

        return rotationsList;
    }

    // This function is used internally to get the angles for the grasp rotations from XML file
    public static Vector3 getGraspAngles(string graspName, string fingerName, int joint)
    {
        XmlDocument doc = new XmlDocument();

        string streamingAssetsPath = Path.Combine(Application.streamingAssetsPath ?? string.Empty, "Parameters", "hands_grasp_angles.xml");
        string fallbackAssetsPath = Path.Combine(Application.dataPath, "Parameters", "hands_grasp_angles.xml");
        string xmlPath = File.Exists(streamingAssetsPath) ? streamingAssetsPath : fallbackAssetsPath;

        if (!File.Exists(xmlPath))
        {
            throw new FileNotFoundException($"Grasp angles XML not found at '{streamingAssetsPath}' or '{fallbackAssetsPath}'.");
        }

        doc.Load(xmlPath);

        XmlNode grasps = doc.DocumentElement; ;

        XmlNode graspType = grasps != null ? grasps.SelectSingleNode(graspName) : null;

        // Check if the finger exists in this grasp definition.

        if (graspType != null && graspType.SelectSingleNode(fingerName) != null)
        {
            XmlNode fingerNode = graspType.SelectSingleNode(fingerName);

            // Ensure the requested joint index exists.
            if (fingerNode.ChildNodes.Count > joint)
            {
                XmlNode fingerJoint = fingerNode.ChildNodes[joint];

                // Retrieve angles if defined.
                if (fingerJoint.ChildNodes.Count >= 3 &&
                    fingerJoint.ChildNodes[0].InnerText != "")
                {
                    float x = float.Parse(fingerJoint.ChildNodes[0].InnerText, CultureInfo.InvariantCulture);
                    float y = float.Parse(fingerJoint.ChildNodes[1].InnerText, CultureInfo.InvariantCulture);
                    float z = float.Parse(fingerJoint.ChildNodes[2].InnerText, CultureInfo.InvariantCulture);

                    return new Vector3(x, y, z);
                }
                else
                {
                    return Vector3.zero;
                }
            }
            else
            {
                throw new Exception("Joint index " + joint + " for " + fingerName + " of " + graspName + " is missing");
            }
        }
        else
        {
            throw new Exception("Definition of " + fingerName + " angles for " + graspName + " is missing");
        }
    }
}