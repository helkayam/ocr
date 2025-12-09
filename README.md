# Protocol Genesis – Stage 1 (Infrastructure & System Skeleton)

## Overview

Protocol Genesis is a knowledge-ingestion engine designed to upload, store, and later process municipal and emergency-related documents.

This document summarizes the results of **Sprint 1 – Infrastructure**.

---

## ✔ Completed in Sprint 1

### 1. Backend (FastAPI)
- FastAPI service running inside Docker  
- Basic health endpoint available at:  
  **http://localhost:8000/health**

### 2. Database (PostgreSQL)
- Running in Docker  
- Ready for Workspaces and Files tables (planned in Sprint 2)

### 3. Object Storage (MinIO)
- Running in Docker  
- Accessible at: **http://localhost:9001**  
  - User: `minioadmin`  
  - Password: `minioadmin`

### 4. Frontend (React + TypeScript)
- React app created and running at: **http://localhost:3000**
- RTL Hebrew support enabled
- Onboarding screen implemented

### 5. SonarCloud (MCP)
- Organization + project created
- `sonar-project.properties` added to backend

### 6. UX Design (Lovable)
Draft screens created for:
- Workspace List
- Workspace Details + File Upload

📎 **Lovable Prototype Link:**  
*(Insert your own link here)*  
`https://dashflow-workspaces.lovable.app`

---

## 🏗 Project Structure


---

## ▶ Running the System

### Backend + DB + MinIO

```bash
cd infra
docker compose up --build

cd frontend
npm start






