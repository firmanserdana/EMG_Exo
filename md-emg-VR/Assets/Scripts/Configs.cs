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

[Serializable]
public class BBTConfig
{
    public int sessionDuration;         // Total session time limit [ms]
    public int trialsStartDelay;        // Delay before first trial [ms]
    public int cueGraspStartInterval;   // Delay before registering grasp_start event [ms]
    public int graspCloseDuration;      // Duration of hand-close animation [ms]
    public int graspOpenDuration;       // Duration of hand-open animation [ms]
    public int holdDuration;            // Hold grasped block duration [ms]
    public int moveDuration;            // Duration for moving block across partition [ms]
    public int placePauseDuration;      // Pause after placing block [ms]
    public int interTrialInterval;      // Interval between trials [ms]
    public float blockSize;             // Size of each block cube [m]
    public int numberOfBlocks;          // Total blocks in source zone
    public float boxWidth;              // Box total width [m]
    public float boxDepth;              // Box total depth [m]
    public float boxHeight;             // Box base height [m]
    public float partitionHeight;       // Partition wall height [m]
    public float blockSpawnAreaWidth;   // Spawn area width in source zone [m]
    public float blockSpawnAreaDepth;   // Spawn area depth in source zone [m]
    public float handMoveHeight;        // Hand arc height when moving blocks [m]
    public float handMoveSpeed;         // Hand movement speed
    public string[] graspLabels;        // ["HandClose", "HandOpen"]
    public int[] graspIDs;              // [1, 0] matching open-close IDs
}

[Serializable]
public class DecoderBBTConfig
{
    public int sessionDurationSeconds;   // Nominal benchmark duration [s]
    public int expectedCloseID;          // Decoder class id for hand close
    public int expectedOpenID;           // Decoder class id for hand open
    public int minPredictionsPerPhase;   // Minimum decoder samples to score a phase
    public bool requireBothPhases;       // If true, both pickup and place must pass
    public float phaseTimeoutSeconds;    // Seconds to wait for decoder prediction before timeout
}