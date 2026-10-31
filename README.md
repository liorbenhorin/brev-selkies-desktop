# Brev Selkies Desktop

Personal Brev Launchable for a native Selkies desktop and robotics development environment.

This repository is intentionally Selkies-only. It does not include NV Streamer packages, NV Streamer service recovery, or driver-alignment logic.

The script chooses the Selkies image from the resolved acceleration mode:

- hardware acceleration: `ghcr.io/selkies-project/nvidia-glx-desktop`
- software acceleration: `ghcr.io/selkies-project/nvidia-egl-desktop`

Set `SELKIES_IMAGE` only when you need to override that automatic selection.

## Launchable Script

Use this as the Brev Launchable user script:

```bash
#!/usr/bin/env bash
set -euo pipefail

export SELKIES_ACCELERATION=auto
export SELKIES_DEPLOYMENT=native
export SELKIES_MODE=websockets
export SELKIES_NATIVE_WORKSPACE=1

curl -fsSL "https://raw.githubusercontent.com/liorbenhorin/brev-selkies-desktop/main/assets/brev-selkies-desktop.sh" | sudo -E bash
```

In the Brev Launchable builder, select **VM Mode**, use this fork as the source repository, and paste the script above into the setup script field. These are separate settings: changing the repository does not change a hardcoded setup URL. Use an RTX-capable GPU such as the tested `g7e.4xlarge` (RTX PRO 6000), with at least 250 GiB disk; 500 GiB gives more room for assets.

For this WebSocket configuration, add one authenticated **Secure Link** named `desktop`, targeting port **8080**, and leave custom TCP/UDP ports empty. Open the Secure Link after setup completes. No TURN ports are needed. This does not select the host Ubuntu version: the installer uses Humble on 22.04 and Jazzy on 24.04.

## Modes

`SELKIES_DEPLOYMENT` controls where the desktop runs:

- `container`: run the Selkies all-in-one desktop image.
- `native`, default: host install that runs an Ubuntu GNOME desktop, Selkies 2.1, coturn, and Docker directly on the Brev host with systemd services.

Container deployment also enables host Docker access by default:

```bash
export SELKIES_HOST_DOCKER=1
```

That mounts `/var/run/docker.sock` and the host Docker CLI into the desktop container so Docker commands from the desktop control the Brev host. This is convenient for ROS/dev-container workflows, but it gives the desktop root-equivalent Docker control on the host. Disable it with:

```bash
export SELKIES_HOST_DOCKER=0
```

`SELKIES_ACCELERATION` controls encode/runtime behavior:

- `auto`, default: use NVIDIA hardware acceleration when required GPU prerequisites are healthy; otherwise use software acceleration.
- `hardware`: require NVIDIA GPU readiness, default `SELKIES_ENCODER=nvh264enc` in container mode, and use the NVIDIA GLX desktop image for container mode.
- `software`: do not request Docker GPU access, default `SELKIES_ENCODER=x264enc` in container mode, and use the NVIDIA EGL desktop image for its software fallback path.

Native Selkies 2.x uses `h264enc` with hardware encoding when available, or `--use-cpu=true` for software mode.

In container mode, hardware also requires a healthy NVIDIA container runtime and runs Docker with `--gpus all`. In native mode, hardware requires an NVIDIA-backed Xorg display; the script installs or verifies the matching NVIDIA Xorg driver before choosing hardware mode.

`SELKIES_MODE` controls the browser transport:

- `webrtc`, default: lower-latency Selkies WebRTC. Requires `8080/tcp` plus TURN UDP ports.
- `websockets`: recommended for native Brev deployments; streams through the authenticated Secure Link on `8080`, without TURN or exposed UDP ports. The Launchable example explicitly selects this mode.
- `kasmvnc`: container-only single-port fallback over `8080/tcp`.

## Ports

For native WebSocket streaming, configure only the authenticated `desktop` Secure Link on port `8080`.

WebRTC requires direct, port-preserving network access:

- `8080/tcp`: Brev Secure Link, usually named `desktop`.
- `47998/udp`: Selkies internal TURN listener.
- `47999-48015/udp`: compact Selkies TURN relay range.

**Brev public port mappings may change both the hostname and port numbers.** For example, a public gateway port `30310` may forward to VM port `47999`. The current local TURN configuration assumes direct access to the VM public IP and unchanged relay port numbers; those remapped ports do not satisfy that requirement. Adding the full UDP range alone will not fix it. Use WebSocket streaming for these deployments, or arrange compatible direct networking/external TURN before choosing WebRTC. Inspect the actual mappings with `brev ports ls <instance> --json`.

Do not shrink the relay range to only one or two ports. Reconnects can leave old TURN allocations around briefly, and a too-small relay range can fail with coturn `error 508: Cannot create socket` / `no available ports`. The script now requires at least eight relay ports by default.

For `SELKIES_MODE=kasmvnc`, expose only:

- `8080/tcp`

If the client needs TURN over TCP, set `SELKIES_TURN_PROTOCOL=tcp` and expose the TCP listener on `47998`. Browser TURN still needs the UDP relay range `47999-48015` with unchanged public port numbers.

## Common Configuration

Force hardware acceleration:

```bash
export SELKIES_ACCELERATION=hardware
```

Force software acceleration:

```bash
export SELKIES_ACCELERATION=software
```

Use single-port KasmVNC fallback in container mode:

```bash
export SELKIES_DEPLOYMENT=container
export SELKIES_MODE=kasmvnc
```

Test native host deployment:

```bash
export SELKIES_DEPLOYMENT=native
export SELKIES_ACCELERATION=auto
export SELKIES_MODE=webrtc
```

Native mode installs `coturn` and Firefox on the host. WebSocket mode only needs the desktop Secure Link; WebRTC additionally needs compatible TURN networking. It intentionally avoids the all-in-one Selkies desktop container so Docker commands inside the streamed desktop operate on the Brev host naturally. Firefox is installed from Mozilla's apt repository so the desktop gets a real `.deb` browser instead of Ubuntu's snap transition package.

When `SELKIES_TURN_HOST` is auto-detected, native mode refreshes the advertised TURN host and coturn `external-ip` each time the systemd service starts. This keeps WebRTC reconnects working after a provider stop/start changes the instance public IP.

Native mode defaults to the familiar Ubuntu GNOME desktop with Yaru styling and the left dock:

```bash
export SELKIES_NATIVE_DESKTOP=ubuntu
```

The previous lightweight desktop remains available when install size or simplicity matters more than appearance:

```bash
export SELKIES_NATIVE_DESKTOP=xfce
```

Native mode pins Selkies **2.1.0** and downloads its official standalone AppImage, verifies the release SHA-256 checksum, and extracts it to `/opt/selkies` (no FUSE required). The download is staged before stopping an existing desktop. To select another compatible 2.x release:

```bash
export SELKIES_NATIVE_VERSION=2.1.0
```

Package index refreshes and installs use bounded retries so transient Ubuntu mirror errors do not abort the Launchable after one failed download. The defaults are four outer attempts, three apt acquisition retries per attempt, a 15-second delay between attempts, and up to 120 seconds for a competing dpkg lock to clear. Override them only when the environment needs a different startup budget:

```bash
export APT_MAX_ATTEMPTS=4
export APT_ACQUIRE_RETRIES=3
export APT_RETRY_DELAY_SECONDS=15
export APT_LOCK_TIMEOUT_SECONDS=120
```

For hardware acceleration, native mode uses an NVIDIA-backed Xorg display by default instead of `Xvfb`, so browser workloads such as WebGL can use the GPU. Native hardware mode now refuses to run on `Xvfb`; if NVIDIA Xorg cannot be prepared, the script exits instead of starting a misleading software-rendered desktop with a hardware encoder. Override the display server only when troubleshooting:

```bash
export SELKIES_NATIVE_X_SERVER=auto
# or: nvidia, xvfb
```

Override the image selection:

```bash
export SELKIES_IMAGE="ghcr.io/selkies-project/nvidia-glx-desktop"
export SELKIES_TAG="24.04"
```

Leave `SELKIES_TAG` unset to match the instance Ubuntu version (`22.04` or `24.04`).

Override only the automatic defaults:

```bash
export SELKIES_HARDWARE_IMAGE="ghcr.io/selkies-project/nvidia-glx-desktop"
export SELKIES_SOFTWARE_IMAGE="ghcr.io/selkies-project/nvidia-egl-desktop"
```

## Native robotics workspace

After the native desktop passes its HTTP health check, the installer sets up:

- **uv and Pixi** in `/usr/local/bin`, using their official installers.
- **Isaac Sim 6.2.0.0**, including extension caches and ROS integration, in `~/robotics/isaacsim-6.2/.venv`. uv supplies Python 3.12; the environment installs PyTorch 2.11.0 with CUDA 12.8 and NVIDIA's pip packages.
- **ROS 2 Desktop** and development tools: Humble on Ubuntu 22.04, Jazzy on Ubuntu 24.04. Includes RViz, colcon, and initialized rosdep.
- A user-owned ROS workspace at `~/robotics/ros2_ws/src`.

The owner is `SELKIES_NATIVE_USER` (default `ubuntu`). This setup targets x86_64 Ubuntu. For a new instance, Ubuntu 24.04 is recommended. Isaac Sim needs a supported NVIDIA RTX GPU and driver; an A100 or H100 can stream a desktop but cannot run Isaac Sim's RTX renderer. See [Isaac Sim requirements](https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/requirements.html).

Connect through Brev: select your instance, then open **Secure Links → desktop** (port `8080`). The desktop can be used while the workspace packages are still installing. Wait for `Workspace ready` in the setup log before launching Isaac Sim.

This is NVIDIA's **pip installation**, with the full standard GUI, viewport, editor, and extensions. It is installed in a uv-created Python 3.12 environment, not built from source or installed from the workstation archive.

Open a fresh terminal in the streamed desktop and launch from **any directory**:

```bash
isaacsim
```

No virtual-environment activation is needed. `~/.local/bin/isaacsim` invokes the environment's executable, enables the ROS 2 bridge, selects the bundled Humble/Jazzy libraries, and sets Fast DDS (`rmw_fastrtps_cpp`) by default. If you already activated the virtual environment, invoke `~/.local/bin/isaacsim` explicitly: its `bin/isaacsim` command bypasses our wrapper.

The launcher preserves `ROS_DOMAIN_ID`; leave it unset (domain `0`) or use the same value in both simulator and ROS terminals. First launch prompts for the NVIDIA Omniverse license agreement and may take time to compile shaders/download assets. Installation does not launch the simulator or accept that prompt automatically.

In a **separate terminal**, activate the system ROS installation and any built workspace overlay:

```bash
source ~/robotics/ros2_ws/activate.bash
ros2 topic list
```

`~/robotics/ros2_ws/src` starts empty: it is for your own packages. ROS itself is installed under `/opt/ros/humble` or `/opt/ros/jazzy`; the installer does not clone NVIDIA's ROS example workspace. Once you add packages under `src`, build them:

```bash
source ~/robotics/ros2_ws/activate.bash
cd ~/robotics/ros2_ws
colcon build --symlink-install
```

ROS is deliberately not sourced in `.bashrc`. In particular, Ubuntu 22.04's native Humble uses Python 3.10, while Isaac Sim uses Python 3.12. The launcher explicitly selects the simulator's bundled ROS libraries before starting it. Enabling the bridge alone does not publish scene data: load a ROS-enabled example or configure publishers/subscribers in your scene. Custom ROS interfaces need a compatible Python 3.12 build; see [NVIDIA's ROS integration guide](https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/install_ros.html).

To retry only the workspace setup after a failed download, without restarting the desktop:

```bash
sudo -E bash assets/brev-selkies-desktop.sh --setup-workspace
```

Reruns reuse the Isaac Sim virtual environment and keep ROS source files. uv/Pixi installers update their binaries; package installation rechecks the pinned Isaac Sim dependencies. The initial download is large, so allow ample disk space and deployment time.

To deploy just the desktop, set `SELKIES_NATIVE_WORKSPACE=0`. Container deployments do not run workspace setup.

### Installation status and validation

For the background jobs used when recovering this instance:

```bash
sudo systemctl show brev-workspace-setup -p ActiveState -p ExecMainStatus
sudo tail -n 30 /var/log/brev-workspace-setup.log
```

The initial full deployment was logged to `/var/log/brev-robotics-setup.log`. These job names/logs apply to the manual systemd-run recovery; ordinary Launchables expose their output in Brev. An inactive setup job with `ExecMainStatus=0` and `Workspace ready` means it completed successfully.

The recovered Ubuntu 22.04 instance was verified with uv, Pixi, Isaac Sim `6.2.0.0`, PyTorch `2.11.0+cu128`, an actual CUDA tensor computation on the RTX PRO 6000 Blackwell, and ROS 2 Humble initialization. A subsequent bridge startup failure was traced to the bundled Fast DDS library lookup. The updated launcher passes Isaac Sim's own ROS checker with the bundled path explicitly set. Full scene/topic communication still needs validation in your simulation.

## Authentication

The default is:

```bash
export SELKIES_ENABLE_BASIC_AUTH=false
```

That assumes access is gated by the Brev Secure Link. For direct, non-Secure-Link testing:

```bash
export SELKIES_ENABLE_BASIC_AUTH=true
export REMOTE_DESKTOP_PASSWORD="choose-a-strong-password"
```

## Validation

```bash
bash -n assets/brev-selkies-desktop.sh
SELKIES_DEPLOYMENT=container SELKIES_ACCELERATION=software assets/brev-selkies-desktop.sh --print-config
SELKIES_DEPLOYMENT=native assets/brev-selkies-desktop.sh --print-config
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
(cd assets && sha256sum -c SHA256SUMS)
```

## Troubleshooting

### Isaac Sim: ROS2 Bridge startup failed

If Isaac Sim prints instructions to set `ROS_DISTRO`, `RMW_IMPLEMENTATION`, and `LD_LIBRARY_PATH`, close that Isaac Sim process and relaunch using the updated `~/.local/bin/isaacsim` wrapper. These library paths must be present **before** the process starts; sourcing the system Humble workspace inside the simulator terminal is not the fix.

For an existing Ubuntu 22.04 installation without the updated wrapper, use a fresh terminal:

```bash
export ROS_DISTRO=humble
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
sim_env="$HOME/robotics/isaacsim-6.2/.venv"
ros_lib="$sim_env/lib/python3.12/site-packages/isaacsim/exts/isaacsim.ros2.core/humble/lib"
export LD_LIBRARY_PATH="$ros_lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
"$sim_env/bin/isaacsim" --enable isaacsim.ros2.bridge
```

On Ubuntu 24.04, use `jazzy` for both the distribution and library directory. Fast DDS is the configured default for external ROS nodes too. If choosing Cyclone DDS, set `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` in both terminals and install the corresponding system ROS RMW package for external nodes.

Check the bundled middleware without starting the GUI:

```bash
~/.local/bin/isaacsim --check-ros
```

A zero exit status means Isaac Sim's ROS middleware check passed. The installer now runs this check too.

After relaunching, check the Isaac Sim log for bridge startup success, then load a ROS-enabled scene and check its expected topics from the separate ROS terminal. Merely seeing the GUI or passing `pip check` does not validate the bridge.

### Native desktop recovery

`Downloading Selkies-GStreamer portable release v2.1.0` followed by HTTP 404 means an older copy of this script is running. Selkies 2.x replaced GStreamer and no longer publishes that archive. Use this fork's updated script; setting `SELKIES_NATIVE_VERSION=1.6.2` alone does not fix the removed upstream release. The native service now uses the 2.x launcher, hyphenated CLI flags, and `h264enc`.

Native service logs:

```bash
journalctl -u brev-selkies-native.service -b -n 200
```

If the first stream works but refresh/reconnect later fails while the container still looks healthy, check the container log:

```bash
docker exec brev-selkies-desktop tail -n 200 /tmp/selkies-gstreamer-entrypoint.log
```

Messages such as `create_relay_ioa_sockets: no available ports` or `ALLOCATE processed, error 508: Cannot create socket` mean the exposed TURN relay range is too small. Expose the full default range, `47998-48015/udp`, and rerun the Launchable.

The legacy container images are intended for one active browser session per desktop. Opening the same remote desktop from multiple browsers or users at the same time can disconnect or take over the existing session. Treat multi-user collaboration as unsupported for this Launchable, similar to the earlier NV Streamer desktop path.

## References

- [Selkies 2.x native installation](https://docs.selkies.io/latest/native/)
- [Isaac Sim 6.2 Python installation](https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/install_python.html)

- [docker-selkies-egl-desktop](https://github.com/selkies-project/docker-selkies-egl-desktop)
- [docker-selkies-glx-desktop](https://github.com/selkies-project/docker-selkies-glx-desktop)
- [Selkies encoder components](https://github.com/selkies-project/selkies/blob/main/docs/component.md)
