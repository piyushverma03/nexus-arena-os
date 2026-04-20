# Nexus Arena OS
## Virtual Hackathon 2026 Submission

Nexus Arena OS is a proactive, multi-agent orchestration system designed to optimize the physical logistics of large-scale sporting venues through real-time crowd intelligence.

### Chosen Vertical: Physical Event Experience
The system is built as a staff-only OS that predicts bottlenecks and autonomously influences crowd behavior through a mesh of AI agents.

---

### Core Approach & Logic

#### 1. Smart Dynamic Assistant (Google Gemini AI)
The system integrates **Google Gemini 1.5 Flash** to act as the "Brain" of the operation. Unlike static systems, Nexus Arena OS analyzes live stadium metrics (density, queue length, alternate gate availability) and dynamically synthesizes:
- **Employee Directives:** Actionable, context-aware instructions for staff to manage surges.
- **Attendee Nudges:** Polite, behavioral redirects sent to ticket holders to balance venue load.

#### 2. Advanced Flow Physics
We implement the **Greenshields Macroscopic Flow Model** ($J = \rho v$) to calculate crowd flux accurately. 
- **Logic:** The system recognizes that as density ($\rho$) increases, velocity ($v$) naturally decreases. This prevents mathematically impossible "infinite throughput" and ensures the simulation mirrors real-world physics.
- **Queue Theory:** Implements $M/M/1$ queueing calculations to predict wait times at specific chokepoints.

---

### Security Features
To ensure safe and responsible implementation, the platform includes:
- **Brute-Force Protection:** Real-time account lockout after successive failed login attempts.
- **JWT Hardening:** Securely managed asymmetric secret keys via environment variables.
- **Security Headers Middleware:** Protection against common web vulnerabilities (XSS, Clickjacking, MIME-sniffing) via `Strict-Transport-Security`, `CSP`, and `X-Frame-Options`.

---

### System Architecture
The system operates through a three-agent micro-mesh:
* **Spatial Architect:** Maintains the digital twin (weighted graph) of the venue.
* **Flow Physicist:** Computes density scalars and detects emerging bottlenecks.
* **AI Brain (Powered by Google Gemini):** Converts data into actionable intelligence.

---

### How to Run Locally
1. **Prerequisites:** Python 3.10+
2. **Setup:** 
   - Add your `GEMINI_API_KEY` to a local `.env` file.
   - Run `start.bat` to install dependencies and launch the server.
3. **Access:** Open `http://localhost:8000`
   - **Admin Login:** `admin@nexus.com` / `NexusAdmin123`

---

### Built For
PromptWars: Virtual Hackathon 2026

