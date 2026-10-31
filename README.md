# SCADA Alpha-04
## Autonomous Hazardous Gas Leakage Detection and Containment Grid

<div align="center">

![System Status](https://img.shields.io/badge/System%20Status-Production%20Ready-10B981?style=for-the-badge&logo=statuspage&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Arduino%20%7C%20Python%20%7C%20Supabase-0284C7?style=for-the-badge&logo=arduino&logoColor=white)
![License](https://img.shields.io/badge/License-Enterprise%20Internal-F59E0B?style=for-the-badge)
![Cloud](https://img.shields.io/badge/Cloud-Supabase%20Realtime-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)

</div>

---

> **Classification:** Industrial Control & Automation Systems  
> **Subsystem Identifier:** SEC-HAZ-09  
> **Deployment Tier:** Production — Edge-to-Cloud IoT SCADA  
> **Project Reference:** SCADA-ALPHA-04

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Key Features](#2-key-features)
3. [System Architecture](#3-system-architecture)
4. [Hardware Pinout & Wiring](#4-hardware-pinout--wiring)
5. [Repository Structure](#5-repository-structure)
6. [Database & Backend Setup](#6-database--backend-setup)
7. [Deployment & Execution Guide](#7-deployment--execution-guide)
8. [Operational Testing](#8-operational-testing)
9. [Safety Thresholds Reference](#9-safety-thresholds-reference)
10. [Technology Stack](#10-technology-stack)

---

## 1. Project Overview

**SCADA Alpha-04** is a production-grade, three-tier Industrial IoT supervisory control and data acquisition system engineered for continuous real-time monitoring of hazardous hydrocarbon gas concentrations within enclosed industrial environments. The system provides autonomous fail-safe containment actuation, bidirectional cloud-to-edge command propagation, and live supervisory visibility through a responsive HTML5 SCADA dashboard — all operating over Supabase Realtime WebSocket infrastructure.

The platform spans the complete data pipeline: from analog sensor acquisition on an Arduino Uno field device, through a Python serial bridge running at the edge gateway layer, to a cloud-hosted PostgreSQL backend with live WebSocket push streaming to the SCADA operator terminal.

Upon detection of a **CRITICAL** gas concentration event (>1000 PPM), the system autonomously:
- Issues an immediate `VALVE_CLOSED` hardware directive via serial command to isolate the feedstock pipeline.
- Issues a `FAN_ON` directive to engage the forced exhaust ventilation extraction system.
- Synchronizes the updated actuator register state to the Supabase cloud supervisory database in real time.
- Triggers an auditory siren alert on the SCADA operator console.

All supervisory override commands issued through the web interface propagate back to the physical hardware within one polling cycle (~1 second) via the Python edge bridge.

---

## 2. Key Features

### Real-Time Telemetry Streaming
- **1 Hz continuous sampling** from the MQ-2 analog gas sensor via Arduino Uno ADC.
- Each telemetry frame (PPM value + safety envelope classification) is pushed to the Supabase `gas_telemetry` table over HTTPS REST.
- The SCADA dashboard subscribes to `postgres_changes` events via **Supabase Realtime WebSocket**, receiving each new row within milliseconds of insertion.
- A **60-point rolling trend line** (Chart.js) renders concentration history with annotated OSHA warning (600 PPM) and critical (1000 PPM) threshold overlays.

### Bidirectional Cloud-to-Edge Actuation
- The Python bridge polls the `device_controls` Supabase table at 1 Hz for supervisory setpoint changes.
- Delta detection ensures only **state-change events** are transmitted to hardware — preventing redundant relay toggling.
- Actuator commands (`VALVE_OPEN`, `VALVE_CLOSED`, `FAN_ON`, `FAN_OFF`) are transmitted as ASCII strings over the serial UART interface to the Arduino.
- The Arduino parses each command string and drives the corresponding GPIO relay/actuator output pin in real time.
- The web SCADA panel renders live actuator LED indicators and status badges, updating instantly on both operator-initiated and autonomous override events via Supabase Realtime.

### Automated Local Safety Interlocks
- The Python bridge implements a **hardware-independent fail-safe**: even if the web dashboard loses connectivity, the edge process autonomously detects `CRITICAL` threshold breaches and issues direct serial containment commands.
- The Arduino firmware includes a **secondary MCU-level hardware interlock**: the onboard piezo buzzer alarm activates directly from the microcontroller when `ppm > 1000`, operating independently of the Python bridge or cloud connectivity.
- Containment latches are self-resetting: the `autonomous_containment_active` flag clears automatically when readings return to `NORMAL` (<600 PPM).

### Enterprise-Grade Dashboard
- Single-file HTML5 SCADA interface with **Tailwind CSS dark-mode industrial aesthetic** (custom `scada-*` color palette).
- Live metric cards: current concentration, shift peak record, 10-sample moving average, rate of change (PPM/s), and ingestion packet counter.
- **CRT scanline audio terminal** for chronological audit event logging with timestamped entries, color-coded by severity.
- One-click **Emergency SCRAM** button: simultaneously closes the isolation valve and engages exhaust fans in a single cloud transaction.
- Full **Web Audio API** siren synthesizer producing distinct tones for WARNING and CRITICAL events (mutable by operator).
- Supabase credentials stored in `localStorage` — no backend server required for the frontend.

---

## 3. System Architecture

The platform is structured as a **three-tier Industrial IoT architecture**, reflecting standard SCADA/ICS design conventions:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         TIER 3 — CLOUD & SUPERVISORY LAYER                   │
│                                                                              │
│   ┌─────────────────────────┐         ┌──────────────────────────────────┐  │
│   │   Supabase PostgreSQL   │◄────────│     SCADA HTML5 Dashboard        │  │
│   │   gas_telemetry table   │         │   (Vercel / Local Browser)        │  │
│   │   device_controls table │────────►│   Chart.js + Tailwind CSS        │  │
│   │   Realtime Publication  │         │   Supabase JS WebSocket Client   │  │
│   └─────────────────────────┘         └──────────────────────────────────┘  │
│              ▲  │                                                            │
│              │  │  HTTPS REST + WebSocket                                    │
└──────────────┼──┼────────────────────────────────────────────────────────────┘
               │  │
┌──────────────┼──┼────────────────────────────────────────────────────────────┐
│              │  ▼          TIER 2 — EDGE GATEWAY LAYER                       │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                     bridge.py  (Python 3.x)                         │   │
│   │                                                                     │   │
│   │   ┌─────────────────────┐     ┌───────────────────────────────┐    │   │
│   │   │  SerialRTUInterface  │     │  SupabaseIndustrialClient      │    │   │
│   │   │  pyserial / COM9    │     │  requests.Session (REST API)   │    │   │
│   │   │  9600 baud          │     │  push_telemetry()              │    │   │
│   │   │  read_telemetry()   │     │  get_device_controls()         │    │   │
│   │   │  write_command()    │     │  update_device_controls()      │    │   │
│   │   └─────────────────────┘     └───────────────────────────────┘    │   │
│   │                                                                     │   │
│   │   evaluate_threshold() → NORMAL / WARNING / CRITICAL                │   │
│   │   Autonomous Safety Interlock (fail-safe containment logic)         │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                  │ USB-Serial (COM9 / /dev/ttyUSB0)                          │
└──────────────────┼───────────────────────────────────────────────────────────┘
                   │
┌──────────────────┼───────────────────────────────────────────────────────────┐
│                  ▼            TIER 1 — FIELD LAYER                           │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      Arduino Uno (RTU)                               │   │
│   │                                                                     │   │
│   │   [A0]  MQ-2 Gas Sensor ──────────────► ADC → PPM mapping           │   │
│   │   [D8]  Solenoid Isolation Valve ◄────── digitalWrite HIGH/LOW      │   │
│   │   [D9]  Relay / Exhaust Fan ◄──────────── digitalWrite HIGH/LOW      │   │
│   │   [D6]  Piezo Buzzer Alarm ◄───────────── MCU-level interlock       │   │
│   │                                                                     │   │
│   │   Firmware: arduino_firmware.ino                                    │   │
│   │   Serial Output:  "482\n"  (integer PPM, 1 Hz)                     │   │
│   │   Serial Input:   "VALVE_CLOSED\n", "FAN_ON\n"  (ASCII commands)   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Layer Descriptions

**Field Layer (Tier 1)** — The Arduino Uno microcontroller operates as the Remote Terminal Unit (RTU). It samples the MQ-2 gas sensor at 1 Hz via the 10-bit ADC on pin `A0`, maps the raw ADC reading to a calibrated PPM value, and transmits it as a plain integer string over the hardware UART (`Serial.println(ppm)`). Simultaneously, it listens for inbound ASCII control commands and drives GPIO output pins to actuate the physical isolation valve relay and the exhaust fan relay. A hardware-level buzzer interlock activates locally at the MCU when concentration exceeds 1000 PPM — independent of any upstream connectivity.

**Edge Gateway Layer (Tier 2)** — `bridge.py` runs as a persistent foreground process on the operator workstation or an embedded edge compute node. It manages the `pyserial` interface to the Arduino (`COM9`, 9600 baud), parses incoming PPM values, applies the safety envelope classification, and pushes discrete telemetry frames to Supabase via HTTPS REST at 1 Hz. It simultaneously polls the `device_controls` table for supervisory state changes and dispatches actuation commands to hardware only when a state delta is detected. The process also implements the primary autonomous safety interlock — initiating fail-safe containment without requiring any human or cloud interaction when a CRITICAL threshold is detected.

**Cloud & Supervisory Layer (Tier 3)** — The Supabase project hosts the PostgreSQL database with two operational tables: `gas_telemetry` (append-only telemetry log) and `device_controls` (single-row supervisory register). Row-Level Security policies permit authenticated bridge writes and public reads. Both tables are enrolled in a Realtime Publication, enabling the SCADA frontend to subscribe to live row-insert and row-update events via the Supabase JS WebSocket client. The HTML5 dashboard, deployable to any static hosting provider (Vercel, Netlify, GitHub Pages), renders telemetry in real time with no backend middleware layer.

---

## 4. Hardware Pinout & Wiring

### Component-to-Pin Mapping

| Component | Module / Type | Arduino Pin | Signal Type | Notes |
|:---|:---|:---:|:---|:---|
| **Gas Sensor** | MQ-2 / MQ-135 / MQ-7 | `A0` | Analog Input | Connect `VCC → 5V`, `GND → GND`, `AOUT/AO → A0` |
| **Pipeline Isolation Valve** | Solenoid Relay Module | `D8` | Digital Output | `LOW` = Valve OPEN (normal flow); `HIGH` = CLOSED (emergency shutoff) |
| **Exhaust Ventilation Fan** | 5V/12V Relay Module | `D9` | Digital Output | `LOW` = Fan OFF; `HIGH` = Fan ON (active extraction) |
| **Auditory Alarm** | 5V Piezo Buzzer | `D6` | Digital Output | `HIGH` = Active alarm; activates at MCU-level when >1000 PPM |
| **Power Supply (Relay)** | — | `5V`, `GND` | Power Rail | Use external relay power if driving loads >500 mA |

### Schematic Notes

```
 ┌─────────────────┐
 │   Arduino Uno   │
 │                 │          ┌────────────┐
 │  A0  ───────────┼──────────┤  MQ-2 AOUT │
 │  5V  ───────────┼──────────┤  MQ-2 VCC  │
 │  GND ───────────┼──────────┤  MQ-2 GND  │
 │                 │          └────────────┘
 │  D8  ───────────┼────────── IN1 (Valve Relay)
 │  D9  ───────────┼────────── IN1 (Fan Relay)
 │  D6  ───────────┼────────── Buzzer (+)
 │  GND ───────────┼────────── Buzzer (-) / Relay GND
 │                 │
 │  USB ───────────┼────────── PC / Laptop (COM9)
 └─────────────────┘
```

> **Important:** Always use optocoupler-isolated relay modules when switching mains-voltage (AC) loads. The GPIO output pins of the Arduino supply 5V logic signals only — never connect them directly to high-voltage load circuits without appropriate relay driver circuitry.

---

## 5. Repository Structure

```
Industrial Gas Leakage Sensor WebApp/
│
├── index.html              # SCADA supervisory dashboard (single-file, Tailwind + Chart.js)
├── bridge.py               # Python edge-to-cloud RTU serial bridge
├── arduino_firmware.ino    # Arduino Uno RTU field device firmware
├── schema.sql              # Supabase PostgreSQL schema, RLS policies & Realtime setup
├── .env                    # Local environment credentials (not committed to VCS)
└── README.md               # This document
```

---

## 6. Database & Backend Setup

### Prerequisites
- A Supabase account and a new project created at [supabase.com](https://supabase.com).
- Project URL and `anon` public API key available from **Project Settings → Data API**.

### Step 1: Execute the Schema

1. In the Supabase dashboard, navigate to the **SQL Editor** from the left sidebar.
2. Click **"+ New query"**.
3. Paste the entire contents of [`schema.sql`](./schema.sql) into the editor.
4. Click **Run** (or press `Ctrl + Enter`).
5. The output panel should confirm: `Success. No rows returned.`

The script provisions the following:

| Object | Type | Description |
|:---|:---|:---|
| `gas_telemetry` | Table | Append-only telemetry log: `id`, `created_at`, `ppm` (INT4), `status` (TEXT) |
| `gas_telemetry` | Index | Descending index on `created_at` for optimized time-series retrieval |
| `device_controls` | Table | Single-row supervisory register: `id`, `valve_state`, `fan_state`, `updated_at` |
| `device_controls` | Seed Row | Default state: `id=1`, `valve_state='OPEN'`, `fan_state='OFF'` |
| `update_device_controls_timestamp` | Trigger Function | Auto-updates `updated_at` on every row modification |
| RLS Policies | Row Level Security | Permissive read/write for SCADA bridge and dashboard operations |
| `supabase_realtime` | Publication | Enrolls both tables in the Supabase Realtime change feed |

### Step 2: Verify Table Creation

Navigate to **Table Editor** in the Supabase dashboard:
- `device_controls` should contain one row: `id=1 | valve_state=OPEN | fan_state=OFF`.
- `gas_telemetry` should be empty and ready for ingestion.

### Step 3: Verify Realtime Publication

Navigate to **Database → Replication** in the Supabase dashboard and confirm that the `supabase_realtime` publication lists both `gas_telemetry` and `device_controls`.

---

## 7. Deployment & Execution Guide

### 7.1 Flash the Arduino Firmware

1. Connect the Arduino Uno to the workstation via USB.
2. Open the **Arduino IDE** (v1.8.x or v2.x).
3. Open [`arduino_firmware.ino`](./arduino_firmware.ino).
4. Navigate to **Tools → Board** and select **Arduino Uno**.
5. Navigate to **Tools → Port** and select the active COM port (e.g., `COM9`).
6. Click **Upload** and wait for the `Done uploading.` confirmation.
7. **Close the Arduino IDE Serial Monitor** (if open) — only one application may hold the COM port at a time.

### 7.2 Install Python Dependencies

Open a terminal and install the required packages:

```bash
pip install pyserial requests
```

Verify installation:

```bash
pip show pyserial requests
```

### 7.3 Run the Edge RTU Bridge

Execute the bridge with your Arduino's COM port:

```bash
python bridge.py --port COM9
```

Expected console output on successful startup:

```
2026-10-31 17:00:00 [INFO] [SCADA-BRIDGE] ================================================================
2026-10-31 17:00:00 [INFO] [SCADA-BRIDGE]  HAZARDOUS GAS DETECTION & AUTONOMOUS CONTAINMENT BRIDGE ACTIVE
2026-10-31 17:00:00 [INFO] [SCADA-BRIDGE] ================================================================
2026-10-31 17:00:00 [INFO] [SCADA-BRIDGE] Target Serial Port: COM9 | Baud Rate: 9600
2026-10-31 17:00:00 [INFO] [SCADA-BRIDGE] Supabase Gateway Configured: https://wmiavglbygzevjueqwcr.supabase.co
2026-10-31 17:00:02 [INFO] [SCADA-BRIDGE] Industrial RTU link active on COM9.
2026-10-31 17:00:03 [INFO] [SCADA-BRIDGE] Gas Reading:  312 PPM | Safety Envelope: [NORMAL]
2026-10-31 17:00:04 [INFO] [SCADA-BRIDGE] Gas Reading:  308 PPM | Safety Envelope: [NORMAL]
```

**Optional: Run in simulation mode** (no hardware required):

```bash
python bridge.py --simulate
```

### 7.4 Access the SCADA Dashboard

**Option A — Local Browser Access:**

Double-click `index.html` to open it directly in any modern browser (Chrome, Edge, Firefox). Credentials are pre-configured in the file.

**Option B — Vercel Deployment (Cloud):**

1. Install the Vercel CLI: `npm install -g vercel`
2. From the project directory, run: `vercel --prod`
3. The dashboard will be available at the generated `*.vercel.app` URL from any browser globally.

Upon loading, the dashboard will:
- Automatically connect to Supabase Realtime (`CLOUD BUS: REALTIME WS LIVE` — green indicator).
- Pre-fetch the last 25 telemetry records to populate the trend chart.
- Synchronize the current actuator state from the `device_controls` register.

---

## 8. Operational Testing

### 8.1 Baseline Verification (No Gas)

1. With the bridge running and dashboard open, confirm:
   - **Concentration** displays live PPM values (typically 150–400 PPM ambient).
   - **Status Banner** shows `ENVELOPE NOMINAL` (green).
   - **Packet Ingestion** counter increments every second.
   - The trend chart populates continuously.

### 8.2 WARNING Threshold Test (600–1000 PPM)

To simulate a moderate concentration event:

1. Hold an **unlit gas lighter** approximately **10–15 cm** from the MQ-2 sensor.
2. Press the lighter release slowly for 1–2 seconds without igniting.
3. Observe the dashboard respond within 1–2 seconds:
   - **Concentration** value climbs above 600 PPM.
   - **Status Banner** transitions to `ELEVATED GAS WARNING` (amber).
   - The PPM card border changes to amber glow.
   - An advisory audio tone sounds on the dashboard.
4. Remove the lighter. Readings return to NORMAL within 10–30 seconds as the sensor disperses.

### 8.3 CRITICAL Threshold & Autonomous Containment Test (>1000 PPM)

> **Safety Advisory:** Conduct this test in a ventilated area. Do not ignite the lighter. Keep the gas exposure brief.

1. Hold an **unlit gas lighter** approximately **3–5 cm** from the MQ-2 sensor.
2. Press the lighter release fully for 2–4 seconds.
3. Observe the full autonomous containment response:

| Event | Expected Behaviour |
|:---|:---|
| **Console Log** | `CRITICAL GAS LEAKAGE DETECTED! INITIATING AUTONOMOUS CONTAINMENT` |
| **Status Banner** | Turns red, pulsing — `CRITICAL HAZARD DETECTED` |
| **PPM Card** | Red glow border, animating badge |
| **Valve LED** | Changes from green (OPEN) to red (ISOLATED / CLOSED) |
| **Fan LED** | Changes from grey (STANDBY) to pulsing blue (RUNNING / EXTRACTION) |
| **Audit Terminal** | `[SAFETY-INTERLOCK] CRITICAL CONCENTRATION DETECTED: XXXX PPM!` |
| **Supabase DB** | `device_controls` row updates: `valve_state=CLOSED`, `fan_state=ON` |
| **Arduino Pin 8** | GPIO goes HIGH — valve relay activates (or LED turns ON) |
| **Arduino Pin 9** | GPIO goes HIGH — fan relay activates (or LED turns ON) |
| **Arduino Pin 6** | GPIO goes HIGH — onboard buzzer alarm sounds |

### 8.4 Supervisory Manual Override Test

With the system in any state:

1. On the dashboard **Supervisory Override** panel, click **OPEN VALVE**.
2. Verify:
   - `device_controls` table updates in Supabase immediately.
   - The Python bridge console logs: `[SUPERVISORY COMMAND] Pipeline Valve Override -> OPEN`.
   - The serial command `VALVE_OPEN` is transmitted to the Arduino.
   - The valve relay deactivates (Arduino Pin 8 goes LOW).
   - The dashboard LED indicator turns green and badge reads `OPEN (FLOW ACTIVE)`.

3. Click **EMERGENCY SCRAM** and verify all the containment events trigger simultaneously.

---

## 9. Safety Thresholds Reference

| Classification | PPM Range | System Response |
|:---|:---:|:---|
| **NORMAL** | < 600 PPM | No action. Continuous monitoring. Status banner green. |
| **WARNING** | 600 – 1000 PPM | Advisory alert tone. Amber banner. Operator attention required. |
| **CRITICAL** | > 1000 PPM | **Autonomous containment:** valve isolation + exhaust fan activation. Red banner. Buzzer alarm. Cloud sync. |

> Thresholds are aligned to general industrial hydrocarbon gas monitoring conventions and can be recalibrated in `bridge.py` (`THRESHOLD_NORMAL_MAX`, `THRESHOLD_WARNING_MAX`) and `arduino_firmware.ino` without any schema changes.

---

## 10. Technology Stack

| Layer | Technology | Purpose |
|:---|:---|:---|
| **Field Device** | Arduino Uno (ATmega328P) | RTU — Sensor acquisition & actuator control |
| **Gas Sensor** | MQ-2 Semiconductor Sensor | Analog hydrocarbon / combustible gas detection |
| **Firmware** | C++ (Arduino Framework) | ADC sampling, UART serial I/O, GPIO relay control |
| **Edge Bridge** | Python 3.x | Serial-to-cloud telemetry bridge & supervisory dispatcher |
| **Serial Interface** | pyserial | UART communication with Arduino Uno |
| **Cloud API Client** | requests (Python) | HTTPS REST interface to Supabase PostgREST |
| **Cloud Database** | Supabase (PostgreSQL 15) | Managed relational database with RLS & Realtime |
| **Cloud Realtime** | Supabase Realtime (WebSockets) | Sub-second change data capture to dashboard |
| **Frontend Framework** | Tailwind CSS 3 (CDN) | Utility-first dark-mode industrial SCADA UI |
| **Charting Library** | Chart.js 4.4.x | Rolling real-time telemetry trend graph |
| **Cloud Hosting** | Vercel / Any Static Host | Zero-config global CDN deployment of `index.html` |
| **Audio Engine** | Web Audio API | Browser-native emergency siren synthesis |

---

<div align="center">

**SCADA Alpha-04** — Autonomous Hazardous Gas Containment Grid  
Subsystem Reference: `SEC-HAZ-09` · Industrial Control & Automation Division

</div>

