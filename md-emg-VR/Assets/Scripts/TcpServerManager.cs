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
    public static TcpServerManager Instance { get; private set; }

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

                // Parsing the received event message
                TCPEvent eventData = JsonUtility.FromJson<TCPEvent>(msg_received.TrimEnd('\n'));

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
