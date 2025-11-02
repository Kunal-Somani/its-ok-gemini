# 🤖 "its-ok-gemini" - The Autonomous Generative Agent

Welcome to the repository for "its-ok-gemini," an advanced project that functions as an **autonomous software development lifecycle (SDLC) agent**. This system is built to receive abstract tasks, generate all necessary code using a Large Language Model (LLM), and automatically deploy the resulting application to the internet.

It's a complete **developer-in-a-box**, running as a continuous FastAPI web service inside a Docker container.

## ✨ Project Goal & Capabilities

The primary goal is to demonstrate a fully automated pipeline where an AI system can:
1.  **Interpret** a natural language task brief.
2.  **Generate** the full source code (e.g., HTML, CSS, JavaScript) required to complete the task.
3.  **Manage** source control by creating, committing, and pushing to a new GitHub repository.
4.  **Deploy** the application instantly via GitHub Pages.
5.  **Revise** and update its own deployed code based on new instructions.

## ⚙️ System Architecture

The project is structured around a **FastAPI** application and leverages several external services for maximum automation.

| Component | Role in the System | Key Technology |
| :--- | :--- | :--- |
| **`main.py`** | **The Server & Orchestrator.** This FastAPI server listens for requests, handles security, launches background tasks, and manages the entire sequence of operations (LLM calls, Git commands, API calls). | FastAPI, `asyncio` |
| **Google Gemini API** | **The Brain.** Receives the task brief and existing code (for revisions), and generates new application code in a strict JSON format. | `google-genai` library |
| **GitHub API** | **The Factory Manager.** Used for creating new repositories, enabling GitHub Pages, and handling attachment downloads (via raw URLs). | `httpx` (or `requests`) |
| **GitPython** | **The Hands.** A Python library used locally to initialize repos (`git init`), clone existing repos, stage files (`git add .`), commit changes, and push updates to the remote GitHub account. | `GitPython` |
| **Hugging Face Spaces / Docker** | **The Runtime Environment.** Provides the continuous deployment and hosting for the `main.py` service. The `Dockerfile` provides the build instructions. | Docker, Uvicorn |

## 🚀 Complete Workflow: From Task to Deployment

The agent operates across two distinct, multi-step workflows.

### Workflow 1: The **"Build"** Process (Round 1 - New Application)

This process initiates when the system receives a brand new task.

| Step | Detail: What is happening? | Purpose & Key Action |
| :--- | :--- | :--- |
| **1. Ingestion & Security** | An external server sends a POST request with the task **brief** and a **secret**. The agent immediately validates the `STUDENT_SECRET` via `verify_secret()` to ensure the request is authorized. | **Security & Authentication** |
| **2. Non-blocking Execution** | The server sends a quick `200 OK` response to the instructor to prevent time-outs, and launches the heavy-lifting logic (`generate_files_and_deploy`) as an **asynchronous background task**. | **Robustness & Scalability** |
| **3. Code Generation** | The agent constructs a detailed System Prompt and calls the **Gemini LLM**. The LLM generates the complete, ready-to-use application files (`index.html`, etc.) and returns them as structured JSON data. | **Generative AI Core** |
| **4. Repository Creation** | Using the GitHub API, the agent programmatically **creates a new, empty public repository** (e.g., `task-solver-xyz`) on the configured GitHub account. | **Source Control Setup** |
| **5. Local Commit Sequence** | The agent saves the code received from Gemini, downloads any specified attachments, and uses `GitPython` to run the essential Git commands: `git init`, `git add .`, `git commit`, and **`git push`**. | **Populating the Repository** |
| **6. Continuous Deployment** | The agent makes a final API call to the GitHub service endpoint to **enable GitHub Pages** for the new repository, pointing to the `main` branch. This triggers the instant public deployment. | **Instant Hosting** |
| **7. Final Report Callback** | The agent sends a POST request back to the instructor's `evaluation_url` containing the **live `pages_url`** and the **`repo_url`** as proof of successful completion and deployment. | **Reporting & Hand-off** |

---

### Workflow 2: The **"Revise"** Process (Round 2 - Updating Code)

This process showcases the agent's ability to maintain and iteratively improve its existing code without manual intervention.

| Step | Detail: What is happening? | Purpose & Key Action |
| :--- | :--- | :--- |
| **1. Revision Trigger** | A new POST request is received, identified by a `"round": 2` flag and a specific revision **brief** (e.g., "Change the button color to red"). | **Identifying Iteration** |
| **2. Contextual Cloning** | Instead of creating a new repo, the agent uses `git.Repo.clone_from()` to download the *existing* repository's code into a temporary folder, capturing the current state of the application. | **State Retrieval** |
| **3. Surgical Update** | The agent sends the **old code** AND the **new revision brief** to the Gemini LLM via `call_llm_round2_surgical_update`. The LLM is strictly instructed to make the **minimal, necessary change** to the existing code. | **Smart Code Modification** |
| **4. Overwrite & Push** | The modified file (e.g., the revised `index.html`) is saved, overwriting the old version. A new `git commit` and **`git push`** are performed to the *same* existing repository. | **Version Control Update** |
| **5. Automatic Redeployment** | The push action automatically triggers the pre-configured GitHub Pages pipeline, resulting in the **instant update of the live public website** with the new changes. | **Live Site Update** |
| **6. Revision Report** | The agent notifies the instructor server with the updated `commit_sha` and the `round: 2` flag, confirming the revision was successfully deployed. | **Revision Confirmation** |

## 📦 Key Project Files and Secrets

| File/Component | Description | Importance |
| :--- | :--- | :--- |
| **`main.py`** | The complete Python application containing all logic: API handlers, Git/GitHub functions, and the LLM wrappers. | **The Core Logic** |
| **`Dockerfile`** | Specifies the exact environment (Python version, OS layers) and execution command (`uvicorn main:app --host 0.0.0.0 --port 7860`) for reliable cloud deployment. | **Deployment Instructions** |
| **`requirements.txt`** | Lists all required Python packages for deployment (`fastapi`, `httpx`, `GitPython`, `google-genai`). | **Dependency Management** |
| **`.env` / Secrets** | Contains sensitive keys (`GEMINI_API_KEY`, `GITHUB_TOKEN`, `STUDENT_SECRET`). The file is kept local and excluded by **`.gitignore`**, relying on the deployment platform's secret manager for production use. | **Security & Configuration** |