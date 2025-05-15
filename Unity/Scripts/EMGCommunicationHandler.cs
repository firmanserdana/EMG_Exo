using UnityEngine;
using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Collections.Generic;
using System.Threading;
using System.Collections.Concurrent;
using Newtonsoft.Json;

public class EMGCommunicationHandler : MonoBehaviour
{
    [Header("Connection Settings")]
    [SerializeField] private string ipAddress = "127.0.0.1";
    [SerializeField] private int port = 9000;
    [SerializeField] private bool useUDP = true;
    [SerializeField] private float updateInterval = 0.02f;

    [Header("Debug")]
    [SerializeField] private bool showDebugLogs = true;
    [SerializeField] private bool visualizeIncomingData = true;

    // Connection objects
    private UdpClient udpClient;
    private TcpListener tcpListener;
    private TcpClient tcpClient;
    private Thread listenerThread;
    private ConcurrentQueue<string> messageQueue = new ConcurrentQueue<string>();
    private bool isRunning = false;

    // Latest hand state
    public Dictionary<string, float> HandState { get; private set; } = new Dictionary<string, float>();

    // Events
    public delegate void HandStateUpdatedHandler(Dictionary<string, float> state);
    public event HandStateUpdatedHandler OnHandStateUpdated;

    void Awake()
    {
        Application.runInBackground = true;
    }

    void Start()
    {
        InitializeHandState();
        StartServer();
    }

    void OnEnable()
    {
        if (!isRunning)
        {
            StartServer();
        }
    }

    void OnDisable()
    {
        StopServer();
    }

    void OnDestroy()
    {
        StopServer();
    }

    void OnApplicationQuit()
    {
        StopServer();
    }

    private void InitializeHandState()
    {
        // Initialize with default values (rest position)
        HandState["thumb_flexion"] = 0f;
        HandState["thumb_extension"] = 0f;
        HandState["thumb_pinching"] = 0f;
        HandState["index_flexion"] = 0f;
        HandState["index_extension"] = 0f;
        HandState["index_pinching"] = 0f;
        HandState["middle_flexion"] = 0f;
        HandState["middle_extension"] = 0f;
        HandState["middle_pinching"] = 0f;
        HandState["ring_little_flexion"] = 0f;
        HandState["ring_little_extension"] = 0f;
        HandState["thumb_abduction"] = 0f;
    }

    private void StartServer()
    {
        try
        {
            isRunning = true;

            if (useUDP)
            {
                // Initialize UDP listener
                udpClient = new UdpClient(port);
                DebugLog($"UDP server started on port {port}");
            }
            else
            {
                // Initialize TCP listener
                tcpListener = new TcpListener(IPAddress.Parse(ipAddress), port);
                tcpListener.Start();
                DebugLog($"TCP server started on {ipAddress}:{port}");
            }

            // Start listener thread
            listenerThread = new Thread(new ThreadStart(ListenerThread));
            listenerThread.IsBackground = true;
            listenerThread.Start();
        }
        catch (Exception e)
        {
            Debug.LogError($"Error starting server: {e.Message}");
            isRunning = false;
        }
    }

    private void StopServer()
    {
        isRunning = false;

        if (listenerThread != null && listenerThread.IsAlive)
        {
            listenerThread.Join(1000);
        }

        if (udpClient != null)
        {
            udpClient.Close();
            udpClient = null;
        }

        if (tcpClient != null)
        {
            tcpClient.Close();
            tcpClient = null;
        }

        if (tcpListener != null)
        {
            tcpListener.Stop();
            tcpListener = null;
        }

        DebugLog("Server stopped");
    }

    private void ListenerThread()
    {
        DebugLog("Listener thread started");

        try
        {
            while (isRunning)
            {
                if (useUDP)
                {
                    // Handle UDP messages
                    IPEndPoint remoteEndPoint = new IPEndPoint(IPAddress.Any, 0);
                    byte[] data = udpClient.Receive(ref remoteEndPoint);
                    string message = Encoding.UTF8.GetString(data);
                    messageQueue.Enqueue(message);
                }
                else
                {
                    // Handle TCP connections and messages
                    if (tcpClient == null || !tcpClient.Connected)
                    {
                        tcpClient = tcpListener.AcceptTcpClient();
                        DebugLog("Client connected");
                    }

                    NetworkStream stream = tcpClient.GetStream();
                    byte[] buffer = new byte[4096];
                    int bytesRead = stream.Read(buffer, 0, buffer.Length);

                    if (bytesRead > 0)
                    {
                        string message = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                        messageQueue.Enqueue(message);
                    }
                }
            }
        }
        catch (ThreadAbortException)
        {
            DebugLog("Listener thread aborted");
        }
        catch (SocketException e)
        {
            if (isRunning) // Only log if it's not due to normal shutdown
            {
                Debug.LogError($"Socket error in listener thread: {e.Message}");
            }
        }
        catch (Exception e)
        {
            Debug.LogError($"Error in listener thread: {e.Message}");
        }
    }

    void Update()
    {
        // Process any queued messages
        ProcessMessages();
    }

    private void ProcessMessages()
    {
        string message;
        bool messageProcessed = false;

        // Process all queued messages
        while (messageQueue.TryDequeue(out message))
        {
            try
            {
                messageProcessed = true;
                ProcessCommand(message);
            }
            catch (Exception e)
            {
                Debug.LogError($"Error processing message: {e.Message}");
            }
        }

        // Notify listeners if any message was processed
        if (messageProcessed)
        {
            OnHandStateUpdated?.Invoke(HandState);
        }
    }

    private void ProcessCommand(string jsonMessage)
    {
        try
        {
            // Parse JSON message
            var command = JsonConvert.DeserializeObject<Command>(jsonMessage);

            switch (command.command)
            {
                case "set_hand_state":
                    if (command.parameters != null)
                    {
                        foreach (var entry in command.parameters)
                        {
                            if (HandState.ContainsKey(entry.Key))
                            {
                                HandState[entry.Key] = entry.Value;
                            }
                        }

                        if (visualizeIncomingData)
                        {
                            DebugLog($"Hand state updated: {JsonConvert.SerializeObject(HandState)}");
                        }
                    }
                    break;

                case "disconnect":
                    DebugLog("Received disconnect command");
                    break;

                default:
                    DebugLog($"Unknown command: {command.command}");
                    break;
            }
        }
        catch (Exception e)
        {
            Debug.LogError($"Error parsing command: {e.Message}");
        }
    }

    private void DebugLog(string message)
    {
        if (showDebugLogs)
        {
            Debug.Log($"[EMGCommunication] {message}");
        }
    }

    // Command data structure
    [System.Serializable]
    private class Command
    {
        public string command;
        public Dictionary<string, float> parameters;
        public float timestamp;
    }
}