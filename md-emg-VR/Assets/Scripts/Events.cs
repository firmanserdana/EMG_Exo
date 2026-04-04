using System;

[Serializable]
public class TCPEvent
{
    public string eventName;
    public int eventID;

    // Extended fields for FSM state updates
    public string fsmState;       // IDLE, CLOSING, LOCKED_GRASP, OPENING, EMERGENCY_STOP
    public bool isLocked;         // Grasp lock indicator
    public float lockTime;        // Time in locked state
    public float handPosition;    // 0.0 (open) to 1.0 (closed)
    public float force;           // Grasp force level

    // BBT scoring fields
    public int blockCount;        // Number of blocks transferred
    public int graspCount;        // Number of grasp-release cycles
    public float sessionTime;     // Time since session start

    // Session persistence context
    public string outputDirectory;
    public string sessionLabel;
    public int sessionIndex;

    // Decoder metadata for session-side logging
    public int predictionRawID = -1;
    public float predictionProb = -1f;
    public float predictionTimestamp = -1f;
}

[Serializable]
public class FSMStateEvent
{
    public string state;          // FSM state name
    public int stateCode;         // 0=IDLE, 1=CLOSING, 2=LOCKED, 3=OPENING, 4=EMERGENCY
    public bool locked;           // Is grasp locked
    public float position;        // Hand position 0-1
    public float force;           // Grasp force 0-1
    public bool stateChanged;     // Did state just change
}

[Serializable]
public class BBTScoreEvent
{
    public int blocks;            // Block count
    public int grasps;            // Grasp count  
    public float time;            // Session time
}