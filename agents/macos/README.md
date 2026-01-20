# macOS Agent

This directory contains the macOS agent for the EcoFlow Power Management system.

## Requirements

- macOS 10.14 or later
- Mosquitto client tools (`mosquitto_sub`)
- `sudo` privileges for shutdown commands
- **Git** (required for cloning this repository - not installed by default on fresh macOS)

> [!NOTE]
> Git is not installed by default on macOS. If you don't have it, you'll be prompted to install Xcode Command Line Tools when you first try to use `git`. Alternatively, install it manually (see Prerequisites section below).

## Prerequisites

Before installing the agent, ensure you have the necessary tools:

### Installing Git (if needed)

Git is required to clone this repository. Check if you have it:
```bash
git --version
```

If not installed, the easiest way is to trigger the Xcode Command Line Tools installer:
```bash
xcode-select --install
```

This will install Git along with other essential development tools.

### Installing Xcode Command Line Tools (if building from source)

Only needed if you plan to build mosquitto from source:
```bash
xcode-select --install
```

## Installation

### Step 1: Install Mosquitto Client

Choose one of the following methods to install the Mosquitto client tools:

#### Option 1: Homebrew (Recommended)

**Best for:** Most users, easiest installation

If you don't have Homebrew installed, install it first:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Then install Mosquitto:
```bash
brew install mosquitto
```

Verify installation:
```bash
mosquitto_sub --help
```

---

#### Option 2: MacPorts

**Best for:** Users who prefer MacPorts or already have it installed

If you don't have MacPorts, install it from [macports.org](https://www.macports.org/install.php).

Then install Mosquitto:
```bash
sudo port install mosquitto
```

Verify installation:
```bash
mosquitto_sub --help
```

---

#### Option 3: Build from Source

**Best for:** Users who want full control or can't use package managers

> [!CAUTION]
> This method is more complex and requires Xcode Command Line Tools and CMake.

1. **Install prerequisites:**
```bash
# Install Xcode Command Line Tools (if not already installed)
xcode-select --install

# Install CMake (you can download from cmake.org or use a package manager)
# If you have Homebrew: brew install cmake
# If you have MacPorts: sudo port install cmake
```

2. **Download Mosquitto source:**
```bash
cd ~/Downloads
curl -LO https://mosquitto.org/files/source/mosquitto-2.0.18.tar.gz
tar -xzf mosquitto-2.0.18.tar.gz
cd mosquitto-2.0.18
```

3. **Build and install libmosquitto:**
```bash
cd lib
cmake .
make
sudo make install
cd ..
```

4. **Build and install Mosquitto clients:**
```bash
cd client
cmake .
make
sudo make install
```

5. **Verify installation:**
```bash
mosquitto_sub --help
```

> [!NOTE]
> You may need to add `/usr/local/bin` to your PATH if the commands aren't found.

---

### Step 2: Configure the Agent

1. **Copy the example environment file:**
```bash
cd agents/macos
cp .env-example .env
```

2. **Edit `.env` with your settings:**
```bash
nano .env
```

Update the following values:
- `AGENT_ID`: Unique identifier for this agent
- `MQTT_HOST`: Your MQTT broker hostname
- `MQTT_PORT`: Your MQTT broker port (default: 1883)

3. **Make the script executable:**
```bash
chmod +x shutdown-listener.sh
```

## Running the Agent

### Manual Execution
```bash
sudo ./shutdown-listener.sh
```

### As a LaunchDaemon (Recommended)

Create `/Library/LaunchDaemons/com.ecoflow.agent.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ecoflow.agent</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/agents/macos/shutdown-listener.sh</string>
    </array>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/opt/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>MQTT_BROKER</key>
        <string>mosquitto.local</string>
        <key>AGENT_ID</key>
        <string>macos-agent</string>
    </dict>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <true/>
    
    <key>StandardOutPath</key>
    <string>/var/log/ecoflow-agent.log</string>
    
    <key>StandardErrorPath</key>
    <string>/var/log/ecoflow-agent.error.log</string>
</dict>
</plist>
```

> [!IMPORTANT]
> The `PATH` environment variable includes common installation locations:
> - `/opt/homebrew/bin` - Homebrew on Apple Silicon Macs
> - `/usr/local/bin` - Homebrew on Intel Macs
> - `/opt/local/bin` - MacPorts
> - Standard system paths

Load and start the daemon:
```bash
sudo cp com.ecoflow.agent.plist /Library/LaunchDaemons/
sudo chown root:wheel /Library/LaunchDaemons/com.ecoflow.agent.plist
sudo chmod 644 /Library/LaunchDaemons/com.ecoflow.agent.plist
sudo launchctl load /Library/LaunchDaemons/com.ecoflow.agent.plist
```

Check status:
```bash
sudo launchctl list | grep ecoflow
tail -f /var/log/ecoflow-agent.log
```

## Configuration

Set these environment variables before running:

- `MQTT_BROKER`: MQTT broker hostname (default: `mosquitto.local`)
- `MQTT_PORT`: MQTT broker port (default: `1883`)
- `AGENT_ID`: Unique identifier for this agent (default: `macos-agent`)

The agent will subscribe to: `power-manager/{AGENT_ID}/cmd`

## Troubleshooting

If the shutdown command requires a password, configure passwordless sudo for shutdown:

```bash
sudo visudo
# Add this line:
%admin ALL=(ALL) NOPASSWD: /sbin/shutdown
```
