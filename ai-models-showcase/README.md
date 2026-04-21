# AI Models Showcase

A full-stack web application that showcases AI models, inspired by opencsg.com/models.

## Features

- Browse AI models by category (Multimodal, Computer Vision, NLP, Audio Processing)
- Filter by trending or all models
- Pagination
- Responsive design

## Setup

### Backend

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the server:
   ```
   uvicorn main:app --reload
   ```

The backend will run on http://localhost:8000

### Frontend

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Open index.html in a web browser, or serve it with a static server.

For a simple server, you can use Python:
```
python -m http.server 3000
```

Then open http://localhost:3000 in your browser.

## API Endpoints

- GET /models: Get paginated list of models
  - Query params: page, limit, category, trending
- GET /categories: Get list of categories
- GET /stats: Get total model count