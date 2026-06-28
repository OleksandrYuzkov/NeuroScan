# NeuroScan

A system for automated diagnosis of brain tumors based on MRI images using CNN neural networks (ResNet18).

## Description

NeuroScan uses deep convolutional neural networks for brain tumor classification based on MRI scans. It provides a web interface with detailed interpretation of results through Grad-CAM and a REST API for integration.

## Features

- Classification of tumors into 4 categories: Glioma, Meningioma, Pituitary, No Tumor
- Result interpretation through Grad-CAM (heat maps)
- User authentication and profile management
- Analysis history with export/import functionality
- Administrative panel
- REST API for integration

## Requirements

- Python 3.8+
- pip/pipenv

## Installation

1. Clone and navigate to the project folder:
   ```powershell
   cd NeuroScan
   ```

2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

## Running

1. Start the backend server:
   ```powershell
   python run_backend.py
   ```
   Server will be available at `http://localhost:8000`

2. Set the first admin password (in a new terminal):
   ```powershell
   python backend/scripts/set_admin_password.py admin@neuroscan.ai "your_password" --admin
   ```

3. Open your browser at `http://localhost:8000`

## Project Structure

```
backend/          — FastAPI server
ml/               — model utilities
src/              — frontend interface
models/           — saved model weights
data/             — MRI images for training
alembic/          — database migrations
```

## Usage

1. Register/Login to the system
2. Upload an MRI image (PNG/JPG)
3. Analyze the image using the model
4. View results with Grad-CAM heat map
5. Save to history

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy, Alembic, PyJWT
- **ML:** PyTorch, TorchVision, Grad-CAM
- **Frontend:** HTML5, CSS3, JavaScript

## License

Educational project.
