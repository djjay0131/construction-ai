# Construction AI

AI-powered web application that automatically calculates material take-off from architectural drawings, generates optimized cut lists to minimize waste, and produces CAD visualizations with labeled components.

## Features

### Phase 1 (MVP) - Currently Implemented
- ✅ **DWG/DXF Parsing** - Parse CAD files using ezdxf with automatic DWG→DXF conversion
- ✅ **PDF Support** - Extract vector-based walls from PDF architectural drawings
- ✅ **Wall Extraction** - Extract wall geometry from architectural drawings
- ✅ **Stud Calculation** - Calculate studs with configurable spacing (12", 16", 24" O.C.)
- ✅ **Plate Calculation** - Calculate top and bottom plates
- ✅ **Web Interface** - React-based UI for file upload and results display
- ✅ **Material Takeoff** - JSON-formatted material lists with quantities

### Planned Features
- 🔲 **Computer Vision** - YOLOv8 for object detection (studs, walls, symbols)
- 🔲 **LLM Integration** - AI-powered interpretation and reasoning
- 🔲 **Complete Materials** - Concrete, drywall, fasteners, tie-downs
- 🔲 **Cut List Optimization** - Minimize waste through optimal cutting
- 🔲 **CAD Output** - Generate labeled DXF/DWG/SVG files
- 🔲 **Image Input** - Support scanned drawings (JPG, PNG)
- 🔲 **Multi-story Support** - Handle buildings up to 2 floors

## Tech Stack

### Backend
- **Python 3.11+** with FastAPI (async, modern, auto-docs)
- **SQLAlchemy** + PostgreSQL/SQLite (data persistence)
- **ezdxf** - DXF parsing
- **LibreDWG** - DWG to DXF conversion
- **PyMuPDF** - PDF vector extraction
- **OR-Tools** - Cut list optimization (future)
- **YOLOv8** - Object detection (future)
- **LangChain** + Claude/GPT-4 - LLM integration (future)

### Frontend
- **React 18+** with TypeScript
- **Vite** - Build tool
- **TailwindCSS** - Styling
- **React Query** - Data fetching
- **Zustand** - State management
- **Three.js** - 3D visualization (future)

### Infrastructure
- **Docker** + Docker Compose
- **PostgreSQL** - Production database
- **Redis** - Celery task queue (future)

## Project Structure

```
construction-ai/
├── backend/                    # Python FastAPI backend
│   ├── app/
│   │   ├── api/                # API endpoints
│   │   │   ├── upload.py       # File upload
│   │   │   └── takeoff.py      # Material takeoff processing
│   │   ├── core/               # Core business logic
│   │   │   ├── parsers/        # DWG/DXF parsers
│   │   │   ├── extraction/     # Material calculation
│   │   │   ├── cv/             # Computer vision (future)
│   │   │   ├── llm/            # LLM integration (future)
│   │   │   └── optimization/   # Cut list optimization (future)
│   │   ├── models/             # Database models
│   │   ├── schemas/            # Pydantic schemas
│   │   └── db/                 # Database setup
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                   # React TypeScript frontend
│   ├── src/
│   │   ├── components/         # React components
│   │   ├── pages/              # Page components
│   │   ├── services/           # API clients
│   │   └── types/              # TypeScript types
│   ├── package.json
│   └── Dockerfile
├── ml/                         # Machine learning models (future)
├── data/                       # Data storage
├── files/                      # Ground truth and test files
├── docker-compose.yml          # Docker orchestration
└── README.md
```

## Getting Started

### Prerequisites

- **Docker** and **Docker Compose** (recommended)
- OR:
  - Python 3.11+
  - Node.js 20+
  - PostgreSQL (optional, SQLite works for development)

### Quick Start with Docker

1. **Clone the repository**
   ```bash
   cd construction-ai
   ```

2. **Start the services**
   ```bash
   docker-compose up --build
   ```

3. **Access the application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/api/docs

### Manual Setup

#### Backend

1. **Navigate to backend directory**
   ```bash
   cd backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Run the backend**
   ```bash
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Backend will be available at http://localhost:8000

#### Frontend

1. **Navigate to frontend directory**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Run the frontend**
   ```bash
   npm run dev
   ```

   Frontend will be available at http://localhost:5173

## Usage

### 1. Upload Drawing

- Navigate to http://localhost:5173
- Click "Upload" or drag and drop a drawing file
- Supported formats: **DWG**, **DXF**, **PDF** (vector-based)
- Maximum file size: 100MB
- Note: DWG files are automatically converted to DXF

### 2. Configure Parameters

- **Wall Height**: Enter wall height in inches (default: 96" = 8')
- **Stud Spacing**: Select 12", 16", or 24" on-center spacing

### 3. Process Takeoff

- Click "Process Drawing"
- The system will:
  1. Parse the CAD file
  2. Extract wall geometry
  3. Calculate stud and plate quantities
  4. Generate material takeoff

### 4. View Results

Results include:
- Total material items
- Lumber breakdown (studs, plates)
- Quantities and specifications
- Linear footage totals
- Processing notes and warnings

## API Documentation

Once the backend is running, visit:
- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

### Key Endpoints

#### Upload Drawing
```http
POST /api/upload/drawing
Content-Type: multipart/form-data

Parameters:
- file: DWG/DXF file
- project_name: Project name (optional)

Returns: Drawing ID and metadata
```

#### Process Takeoff
```http
POST /api/takeoff/process/{drawing_id}?wall_height=96&stud_spacing=16

Returns: MaterialTakeoff JSON
```

#### Get Takeoff Result
```http
GET /api/takeoff/result/{drawing_id}

Returns: MaterialTakeoff JSON or status
```

## Testing

### Test with Sample File

A sample architectural drawing is included:
- **File**: [HFH 9557 Barnes Rd Prefab Plans.dwg](files/HFH%209557%20Barnes%20Rd%20Prefab%20Plans.dwg)
- **Type**: Habitat for Humanity prefab house plan
- **Use**: Upload this file to test the system

### Manual Validation

1. Upload the HFH sample plan
2. Process with default settings (96" walls, 16" O.C.)
3. Compare results with manual takeoff
4. Verify stud counts and plate quantities

## Development

### Backend Development

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

```bash
cd frontend
npm run dev
```

### Database

The application uses SQLite by default. To use PostgreSQL:

1. Update `DATABASE_URL` in `.env`:
   ```
   DATABASE_URL=postgresql://user:password@localhost/construction_ai
   ```

2. The database schema is created automatically on startup

### Adding New Features

1. **Backend**: Add modules in `backend/app/core/`
2. **Frontend**: Add components in `frontend/src/components/`
3. **API**: Add endpoints in `backend/app/api/`
4. **Database**: Add models in `backend/app/models/`

## Roadmap

### Phase 2: Computer Vision
- Train YOLOv8 on construction drawings
- Detect studs, walls, and structural elements
- Improve accuracy with CV + rule-based hybrid

### Phase 3: LLM Enhancement
- Integrate Claude/GPT-4 APIs
- Build RAG system with building specifications
- Interpret annotations and apply construction knowledge

### Phase 4: Complete Material Takeoff
- Expand to all lumber types (joists, beams, rafters)
- Add concrete, drywall, fasteners, tie-downs
- Building code rule engine

### Phase 5: Cut List Optimization
- Implement cutting stock algorithm
- Minimize waste for standard lumber lengths
- Generate labeled cut lists

### Phase 6: CAD Output
- Generate DXF/DWG/SVG with labeled components
- Interactive 3D visualization
- Multiple export formats

### Phase 7: Advanced Features
- PDF and image support
- Multi-story buildings (up to 2 floors)
- Multi-family units
- Batch processing

### Phase 8: Production
- User authentication
- Project management
- Team collaboration
- Cloud deployment

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

See [LICENSE](LICENSE) file for details.

## Acknowledgments

- Based on the CS6604 Construction AI proposal
- Ground truth data from Habitat for Humanity plans
- Building specifications from Modoc renovations standards
