#!/usr/bin/env python3
"""
ESP32 Connection Stability Test
Test ESP32 connection stability and diagnose connection reset issues
"""

import socket
import time
import threading
import select

def continuous_esp32_monitor():
    """Monitor ESP32 connection continuously to catch connection resets"""
    connection_count = 0
    
    while True:
        connection_count += 1
        print(f"\n=== Connection Attempt #{connection_count} ===")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            print(f"[{time.strftime('%H:%M:%S')}] Connecting to ESP32...")
            sock.connect(("172.20.10.3", 4210))
            
            # Get welcome message
            response = sock.recv(1024).decode().strip()
            print(f"[{time.strftime('%H:%M:%S')}] ESP32 Ready: {response}")
            
            # Test initial command
            sock.send("g:0\n".encode())
            response = sock.recv(1024).decode().strip()
            print(f"[{time.strftime('%H:%M:%S')}] Initial command response: {response}")
            
            # Monitor connection for stability
            connection_start = time.time()
            command_count = 0
            
            while True:
                try:
                    # Send a test command every few seconds
                    if time.time() - connection_start > command_count * 3:  # Every 3 seconds
                        command_count += 1
                        test_cmd = f"g:{command_count % 3}"  # Cycle through g:0, g:1, g:2
                        
                        print(f"[{time.strftime('%H:%M:%S')}] Sending: {test_cmd}")
                        sock.send(f"{test_cmd}\n".encode())
                        
                        # Check for response with timeout
                        ready = select.select([sock], [], [], 2.0)
                        if ready[0]:
                            response = sock.recv(1024).decode().strip()
                            print(f"[{time.strftime('%H:%M:%S')}] Response: {response}")
                        else:
                            print(f"[{time.strftime('%H:%M:%S')}] No response - connection may be unstable")
                    
                    # Small delay to prevent overwhelming
                    time.sleep(0.1)
                    
                    # Exit after 30 seconds to restart connection
                    if time.time() - connection_start > 30:
                        print(f"[{time.strftime('%H:%M:%S')}] Closing connection after 30s test")
                        break
                        
                except (ConnectionResetError, BrokenPipeError, OSError) as e:
                    print(f"[{time.strftime('%H:%M:%S')}] *** CONNECTION LOST: {e} ***")
                    print(f"Connection lasted: {time.time() - connection_start:.2f} seconds")
                    break
                except Exception as e:
                    print(f"[{time.strftime('%H:%M:%S')}] Error: {e}")
                    break
                    
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Failed to connect: {e}")
            
        finally:
            try:
                sock.close()
            except:
                pass
            
        # Wait before next connection attempt
        print(f"[{time.strftime('%H:%M:%S')}] Waiting 5 seconds before next test...")
        time.sleep(5)
        
        # Stop after 10 connection attempts
        if connection_count >= 10:
            print("\nCompleted 10 connection stability tests")
            break

def stress_test_esp32():
    """Stress test ESP32 with rapid commands to see if it causes connection resets"""
    print("Starting ESP32 stress test...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect(("172.20.10.3", 4210))
        
        response = sock.recv(1024).decode().strip()
        print(f"ESP32 Ready: {response}")
        
        # Send rapid commands like the EMG system does
        commands = ["g:1", "f:111110", "g:2", "f:222220"] * 50  # 200 commands total
        
        print(f"Sending {len(commands)} rapid commands...")
        start_time = time.time()
        
        for i, cmd in enumerate(commands):
            try:
                sock.send(f"{cmd}\n".encode())
                
                # Try to read response (but don't wait long)
                sock.settimeout(0.1)
                try:
                    response = sock.recv(1024).decode().strip()
                except socket.timeout:
                    pass  # No response is okay for rapid testing
                
                if i % 20 == 0:  # Progress update every 20 commands
                    print(f"Sent {i+1}/{len(commands)} commands")
                    
                time.sleep(0.05)  # 50ms delay like in EMG system
                
            except Exception as e:
                print(f"Command {i+1} failed: {e}")
                break
                
        elapsed = time.time() - start_time
        print(f"Stress test completed in {elapsed:.2f} seconds")
        
    except Exception as e:
        print(f"Stress test failed: {e}")
    finally:
        try:
            sock.close()
        except:
            pass

if __name__ == "__main__":
    print("ESP32 Connection Diagnostics")
    print("="*50)
    
    choice = input("Choose test:\n1. Connection stability monitor\n2. Stress test\nEnter 1 or 2: ").strip()
    
    if choice == "1":
        continuous_esp32_monitor()
    elif choice == "2":
        stress_test_esp32()
    else:
        print("Invalid choice")
