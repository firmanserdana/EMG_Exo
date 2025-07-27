using System;

[Serializable]
public class HandConfig
{
    public int numJoints;
}

[Serializable]
public class AnimationConfig
{
    public float speedHz;
}

[Serializable]
public class TCPServerConfig
{
    public int port;
}

[Serializable]
public class OpenLoopConfig
{
    public int trialsStartDelay; // amount of time to wait before starting the first trial [ms]
    public int trialIntervalDuration; // [ms]
    public int cueGraspStartInterval; // [ms] interval between the cue and the start of grasp
    public int holdDuration; // [ms]
    public string[] graspLabelsOpenClose;
    public int[] graspIDOpenClose;
    public string[] graspLabelsGraspPatterns;
    public int[] graspIDGraspPatterns;
    public string[] graspLabelsSingleFingers;
    public int[] graspIDSingleFingers;
}

[Serializable]
public class ClosedLoopConfig
{
    public int trialsStartDelay; // amount of time to wait before starting the first trial [ms]
    public int trialIntervalDuration; // [ms]
    public int cueGraspStartInterval; // [ms] interval between the cue and the start of grasp
    public int holdDuration; // [ms]
    public string[] graspLabelsOpenClose;
    public int[] graspIDOpenClose;
    public string[] graspLabelsGraspPatterns;
    public int[] graspIDGraspPatterns;
    public string[] graspLabelsSingleFingers;
    public int[] graspIDSingleFingers;
}

[Serializable]
public class MVCConfig
{
    public int trialsStartDelay; // amount of time to wait before starting the MVC [ms]
    public int MVCDuration; // [s] duration of the MVC
}