using PimDeWitte.UnityMainThreadDispatcher;
using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;
using Newtonsoft.Json;

public class TcpServerManager : MonoBehaviour
{
    public static TcpServerManager Instance { get; private set; }

    private TcpListener server;
    private TcpClient client;
    private NetworkStream stream;
    private Thread listenerThread;
    private bool running = false;
    
    [Header("Connection Settings")]
    public int serverPort = 12345;
    public float connectionTimeout = 5f;
    public bool autoReconnect = true;
    
    [Header("Debug Settings")]
    public bool logAllMessages = false;
    public bool logConnectionEvents = true;

    // Events for different message types
    public event Action<TCPEvent> OnMessageReceived;
    public event Action<string> OnProportionalControlReceived;
    public event Action<string> OnSystemStatusReceived;
    public event Action<bool> OnConnectionStatusChanged;
    
    // Connection status
    public bool IsConnected { get; private set; } = false;
    private DateTime lastMessageTime = DateTime.Now;
    
    // Message buffer for handling partial messages
    private StringBuilder messageBuffer = new StringBuilder();

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
        // Load configs
        string configPath = Path.Combine(Application.dataPath, "Config");
        string configFile = Path.Combine(configPath, "TCPServerConfig.json");
        
        if (File.Exists(configFile))
        {
            try
            {
                string json = File.ReadAllText(configFile);
                TCPServerConfig serverConfig = JsonUtility.FromJson<TCPServerConfig>(json);
                serverPort = serverConfig.port;
            }
            catch (Exception e)
            {
                Debug.LogWarning($"Failed to load TCP config: {e.Message}. Using default port {serverPort}");
            }
        }
        else
        {
            Debug.LogWarning($"TCP config file not found at {configFile}. Using default port {serverPort}");
        }

        StartServer(serverPort);
        
        // Start connection monitoring
        InvokeRepeating(nameof(MonitorConnection), 1f, 1f);
    }

    public void StartServer(int port)
    {
        if (!running)
        {
            try
            {
                server = new TcpListener(IPAddress.Any, port);
                server.Start();
                running = true;
                
                listenerThread = new Thread(ListenForClient)
                {
                    IsBackground = true,
                    Name = "TCPServerListener"
                };
                listenerThread.Start();
                
                if (logConnectionEvents)
                    Debug.Log($"TCP Server started on port {port}");
            }
            catch (Exception e)
            {
                Debug.LogError($"Failed to start TCP server: {e.Message}");
            }
        }
    }

    private void ListenForClient()
    {
        try
        {
            if (logConnectionEvents)
                Debug.Log("Waiting for client connection...");
                
            client = server.AcceptTcpClient();
            stream = client.GetStream();
            
            // Set connection status
            UnityMainThreadDispatcher.Instance().Enqueue(() => {
                IsConnected = true;
                OnConnectionStatusChanged?.Invoke(true);
                
                if (logConnectionEvents)
                    Debug.Log("✓ Client connected to TCP server!");
            });

            byte[] buffer = new byte[4096]; // Increased buffer size for proportional data

            while (running && client.Connected)
            {
                int bytesRead = 0;
                try
                {
                    bytesRead = stream.Read(buffer, 0, buffer.Length);
                }
                catch (Exception ex)
                {
                    if (running) // Only log if we weren't intentionally shutting down
                    {
                        Debug.LogWarning($"TCP read error: {ex.Message}");
                    }
                    break;
                }

                if (bytesRead == 0)
                {
                    if (logConnectionEvents)
                        Debug.Log("Client closed connection gracefully.");
                    break;
                }

                string receivedData = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                lastMessageTime = DateTime.Now;
                
                // Handle potentially multiple messages in one buffer
                ProcessReceivedData(receivedData);
            }
        }
        catch (Exception e)
        {
            if (running)
            {
                Debug.LogError($"TCP server error: {e.Message}");
            }
        }
        finally
        {
            // Cleanup and set disconnected status
            UnityMainThreadDispatcher.Instance().Enqueue(() => {
                IsConnected = false;
                OnConnectionStatusChanged?.Invoke(false);
                
                if (logConnectionEvents)
                    Debug.Log("Client disconnected from TCP server");
            });
            
            stream?.Close();
            client?.Close();

            // Auto-reconnect if enabled and still running
            if (running && autoReconnect)
            {
                Thread.Sleep(1000); // Wait 1 second before trying to accept new client
                ListenForClient();
            }
        }
    }
    
    private void ProcessReceivedData(string data)
    {
        // Add to message buffer
        messageBuffer.Append(data);
        
        string bufferContent = messageBuffer.ToString();
        string[] messages = bufferContent.Split('\n');
        
        // Process complete messages (all except the last one, which might be partial)
        for (int i = 0; i < messages.Length - 1; i++)
        {
            string message = messages[i].Trim();
            if (!string.IsNullOrEmpty(message))
            {
                ProcessSingleMessage(message);
            }
        }
        
        // Keep the last message in buffer (might be partial)
        messageBuffer.Clear();
        if (messages.Length > 0)
        {
            string lastMessage = messages[messages.Length - 1];
            if (!string.IsNullOrEmpty(lastMessage))
            {
                messageBuffer.Append(lastMessage);
            }
        }
    }
    
    private void ProcessSingleMessage(string message)
    {
        try
        {
            if (logAllMessages)
                Debug.Log($"Received: {message}");
            
            // Try to parse as generic event first
            var eventData = JsonConvert.DeserializeObject<Dictionary<string, object>>(message);
            
            if (eventData.ContainsKey("event_type"))
            {
                string eventType = eventData["event_type"].ToString();
                
                // Route to appropriate handler on main thread
                UnityMainThreadDispatcher.Instance().Enqueue(() => {
                    RouteMessage(eventType, message, eventData);
                });
            }
            else
            {
                // Fallback to legacy TCPEvent parsing
                TCPEvent legacyEvent = JsonUtility.FromJson<TCPEvent>(message);
                
                UnityMainThreadDispatcher.Instance().Enqueue(() => {
                    OnMessageReceived?.Invoke(legacyEvent);
                });
            }
        }
        catch (Exception e)
        {
            Debug.LogWarning($"Failed to parse TCP message: {e.Message}\nMessage: {message}");
        }
    }
    
    private void RouteMessage(string eventType, string rawMessage, Dictionary<string, object> eventData)
    {
        switch (eventType)
        {
            case "proportional_control":
                OnProportionalControlReceived?.Invoke(rawMessage);
                
                // Also route to ProportionalHandController
                var handController = FindObjectOfType<ProportionalHandController>();
                if (handController != null)
                {
                    handController.HandleProportionalControlEvent(eventData);
                }
                
                // Route to UI Manager
                var uiManager = FindObjectOfType<ProportionalControlUIManager>();
                if (uiManager != null)
                {
                    uiManager.HandleProportionalControlMessage(rawMessage);
                }
                break;
                
            case "system_status":
            case "connection_status":
                OnSystemStatusReceived?.Invoke(rawMessage);
                
                // Route to UI Manager
                var statusUIManager = FindObjectOfType<ProportionalControlUIManager>();
                if (statusUIManager != null)
                {
                    statusUIManager.HandleProportionalControlMessage(rawMessage);
                }
                break;
                
            case "gesture_control":
            case "classification_result":
                // Legacy gesture control events
                try
                {
                    TCPEvent legacyEvent = JsonUtility.FromJson<TCPEvent>(rawMessage);
                    OnMessageReceived?.Invoke(legacyEvent);
                }
                catch
                {
                    Debug.LogWarning($"Failed to parse legacy event: {eventType}");
                }
                break;
                
            default:
                // Generic event handling
                try
                {
                    TCPEvent genericEvent = JsonUtility.FromJson<TCPEvent>(rawMessage);
                    OnMessageReceived?.Invoke(genericEvent);
                }
                catch
                {
                    Debug.LogWarning($"Unknown event type: {eventType}");
                }
                break;
        }
        
        if (logAllMessages)
            Debug.Log($"Routed {eventType} event to appropriate handlers");
    }
    
    /// <summary>
    /// Send a message to the connected Python client
    /// </summary>
    public void SendMessage(string message)
    {
        if (stream != null && stream.CanWrite && IsConnected)
        {
            try
            {
                byte[] data = Encoding.UTF8.GetBytes(message + "\n");
                stream.Write(data, 0, data.Length);
                stream.Flush();
                
                if (logAllMessages)
                    Debug.Log($"Sent: {message}");
            }
            catch (Exception e)
            {
                Debug.LogError($"Failed to send message: {e.Message}");
                IsConnected = false;
                OnConnectionStatusChanged?.Invoke(false);
            }
        }
        else
        {
            Debug.LogWarning("Cannot send message: TCP stream not available or not connected");
        }
    }

    // Legacy method for backward compatibility
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
            stream.Flush();
        }
    }
    
    /// <summary>
    /// Send proportional control command to Python backend
    /// </summary>
    public void SendProportionalControlCommand(string command, Dictionary<string, object> parameters = null)
    {
        var commandData = new Dictionary<string, object>
        {
            ["event_type"] = "control_command",
            ["command"] = command,
            ["timestamp"] = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()
        };
        
        if (parameters != null)
        {
            commandData["parameters"] = parameters;
        }
        
        string jsonMessage = JsonConvert.SerializeObject(commandData);
        SendMessage(jsonMessage);
    }
    
    /// <summary>
    /// Monitor connection health
    /// </summary>
    private void MonitorConnection()
    {
        if (IsConnected)
        {
            // Check if we haven't received messages in a while
            double timeSinceLastMessage = (DateTime.Now - lastMessageTime).TotalSeconds;
            
            if (timeSinceLastMessage > connectionTimeout)
            {
                Debug.LogWarning($"No messages received for {timeSinceLastMessage:F1}s. Connection may be lost.");
                
                // Test connection
                if (client == null || !client.Connected)
                {
                    IsConnected = false;
                    OnConnectionStatusChanged?.Invoke(false);
                }
            }
        }
    }
    
    /// <summary>
    /// Get connection statistics
    /// </summary>
    public Dictionary<string, object> GetConnectionStats()
    {
        return new Dictionary<string, object>
        {
            ["connected"] = IsConnected,
            ["port"] = serverPort,
            ["last_message_age"] = (DateTime.Now - lastMessageTime).TotalSeconds,
            ["auto_reconnect"] = autoReconnect,
            ["client_endpoint"] = client?.Client?.RemoteEndPoint?.ToString() ?? "None"
        };
    }

    void OnApplicationQuit()
    {
        StopServer();
    }
    
    public void StopServer()
    {
        running = false;
        
        try
        {
            stream?.Close();
            client?.Close();
            server?.Stop();
            
            if (listenerThread != null && listenerThread.IsAlive)
            {
                listenerThread.Join(1000); // Wait up to 1 second for thread to finish
                if (listenerThread.IsAlive)
                {
                    listenerThread.Abort();
                }
            }
        }
        catch (Exception e)
        {
            Debug.LogError($"Error stopping TCP server: {e.Message}");
        }
        
        IsConnected = false;
        OnConnectionStatusChanged?.Invoke(false);
        
        if (logConnectionEvents)
            Debug.Log("TCP Server stopped");
    }
    
    void OnDestroy()
    {
        StopServer();
    }
}

/// <summary>
/// Enhanced TCP event structure for proportional control
/// </summary>
[System.Serializable]
public class ProportionalControlEvent
{
    public string event_type;
    public long timestamp;
    public Dictionary<string, FingerControlValues> fingers;
    public string decoder_type;
    public string control_mode;
    public bool mud_enabled;
    public SystemPerformance performance;
}

[System.Serializable]
public class FingerControlValues
{
    public float flexion_speed;
    public float extension_speed;
    public float force;
    public float net_activation;
    public bool is_active;
}

[System.Serializable]
public class SystemPerformance
{
    public float update_rate;
    public float latency;
    public int active_channels;
    public float cpu_usage;
    public float memory_usage;
}

// Legacy event structure for backward compatibility
[System.Serializable]
public class TCPEvent
{
    public string event;
    public int event_id;
    public string timestamp;
    public Dictionary<string, object> data;
}

[System.Serializable]
public class TCPServerConfig
{
    public int port;
    public float timeout;
    public bool auto_reconnect;
    public bool log_messages;
}