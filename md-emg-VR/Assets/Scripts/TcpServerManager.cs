using PimDeWitte.UnityMainThreadDispatcher;
using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;

public class TcpServerManager : MonoBehaviour
{
    [Serializable]
    private class RawTcpEvent
    {
        public string @event;
        public int event_id;
        public string eventName;
        public int eventID;
        public string fsmState;
        public bool isLocked;
        public float lockTime;
        public float handPosition;
        public float force;
        public int blockCount;
        public int graspCount;
        public float sessionTime;
        public string outputDirectory;
        public string sessionLabel;
        public int sessionIndex = -1;
        public int predictionRawID = -1;
        public float predictionProb = -1f;
        public float predictionTimestamp = -1f;
    }

    public static TcpServerManager Instance { get; private set; }

    public string CurrentOutputDirectory { get; private set; }
    public string CurrentSessionLabel { get; private set; }
    public int? CurrentSessionIndex { get; private set; }

    private TcpListener server;
    private TcpClient client;
    private NetworkStream stream;
    private Thread listenerThread;
    private bool running = false;

    // Event for received messages
    public event Action<TCPEvent> OnMessageReceived;

    void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(this.gameObject);
            return;
        }

        Instance = this;
        DontDestroyOnLoad(this.gameObject);
    }

    void Start()
    {
        // Guard: if this instance was marked for destruction by Awake(), skip
        if (Instance != this) return;

        // Load configs
        string configPath = Path.Combine(Application.dataPath, "Config");

        string json = File.ReadAllText(Path.Combine(configPath, "TCPServerConfig.json"));
        TCPServerConfig serverConfig = JsonUtility.FromJson<TCPServerConfig>(json);

        StartServer(serverConfig.port);
    }

    public void StartServer(int port)
    {
        if (!running)
        {
            server = new TcpListener(IPAddress.Any, port);
            server.Start();
            running = true;
            listenerThread = new Thread(ListenForClient);
            listenerThread.IsBackground = true;
            listenerThread.Start();
        }
    }

    private void ListenForClient()
    {
        try
        {
            client = server.AcceptTcpClient();
            stream = client.GetStream();
            Debug.Log("Client connected!");

            byte[] buffer = new byte[1024];

            while (running)
            {
                int bytesRead = 0;
                try
                {
                    bytesRead = stream.Read(buffer, 0, buffer.Length);
                }
                catch (Exception ex)
                {
                    Debug.LogWarning("Client disconnected or error: " + ex.Message);
                    break; // Exit the loop on error/disconnect
                }

                if (bytesRead == 0)
                {
                    Debug.Log("Client closed connection.");
                    break; // Client closed connection
                }

                string msg_received = Encoding.UTF8.GetString(buffer, 0, bytesRead);

                // Parse both JSON schemas: {"event","event_id"} and {"eventName","eventID"}
                TCPEvent eventData = ParseTcpEvent(msg_received.TrimEnd('\n'));

                // Notify listeners on the main thread
                UnityMainThreadDispatcher.Instance().Enqueue(() =>
                {
                    OnMessageReceived?.Invoke(eventData);
                });
            }

            Debug.Log("Client disconnected, stopping listener.");
        }
        finally
        {
            stream?.Close();
            client?.Close();

            // restart listening for new clients
            if (running && server != null)
            {
                ListenForClient(); // Recursively wait for the next client
            }
        }
    }

    private TCPEvent ParseTcpEvent(string payload)
    {
        try
        {
            RawTcpEvent raw = JsonUtility.FromJson<RawTcpEvent>(payload);
            if (raw == null)
            {
                return new TCPEvent();
            }

            string resolvedName = !string.IsNullOrEmpty(raw.eventName) ? raw.eventName : raw.@event;
            int resolvedId = raw.eventID != 0 ? raw.eventID : raw.event_id;

            if (resolvedName == "session_context")
            {
                CurrentOutputDirectory = raw.outputDirectory;
                CurrentSessionLabel = raw.sessionLabel;
                CurrentSessionIndex = raw.sessionIndex >= 0 ? raw.sessionIndex : (int?)null;

                Debug.Log(
                    "[TcpServerManager] Session context updated: " +
                    $"folder={CurrentOutputDirectory}, label={CurrentSessionLabel}, index={CurrentSessionIndex}"
                );
            }

            return new TCPEvent
            {
                eventName = resolvedName,
                eventID = resolvedId,
                fsmState = raw.fsmState,
                isLocked = raw.isLocked,
                lockTime = raw.lockTime,
                handPosition = raw.handPosition,
                force = raw.force,
                blockCount = raw.blockCount,
                graspCount = raw.graspCount,
                sessionTime = raw.sessionTime,
                outputDirectory = raw.outputDirectory,
                sessionLabel = raw.sessionLabel,
                sessionIndex = raw.sessionIndex,
                predictionRawID = raw.predictionRawID,
                predictionProb = raw.predictionProb,
                predictionTimestamp = raw.predictionTimestamp,
            };
        }
        catch (Exception ex)
        {
            Debug.LogWarning("Failed to parse TCP payload: " + ex.Message + " | Payload: " + payload);
            return new TCPEvent();
        }
    }

    // Call this from other scripts to send a message through the TCP connection
    public void SendMessageToClient(string msg, int? msgID = null)
    {
        if (stream != null && stream.CanWrite)
        {
            string json;

            if (msgID.HasValue)
            {
                json = $"{{\"event\":\"{msg}\",\"event_id\":{msgID.Value}}}\n";
            }
            else
            {
                json = $"{{\"event\":\"{msg}\"}}\n";
            }

            byte[] outBuffer = Encoding.UTF8.GetBytes(json);
            stream.Write(outBuffer, 0, outBuffer.Length);
        }
    }

    void OnApplicationQuit()
    {
        running = false;
        stream?.Close();
        client?.Close();
        server?.Stop();
        listenerThread?.Abort();
    }
}
