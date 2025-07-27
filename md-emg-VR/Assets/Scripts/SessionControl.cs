public static class SessionControl
{
    // Both open-loop and closed-loop variables
    public static bool isRunning = false;
    public static int trlProgression = 0;
    public static int numTotalTrials = 20;
    public static int[] trialsClass;
    public static string[] trialsLabels;
    public static int[] trialsClassID;

    // Closed-loop variables
    public static int numTrialsCorrect = 0;
    public static bool isDecoding = false;
    public static bool timerActive = false;
    public static float timerElapsedTime = 0f;
}